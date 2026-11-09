"""Reference-only generation and restitution of revision-pinned documentary facts."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError

from services.ingestion.office.xlsx import _cell_fields, address_coordinates
from services.ingestion.table_geometry import table_general_condition_fragments

from .answer_contract import (
    OBLIGATION_SCHEMA_VERSION,
    PROPERTY_LABELS,
    AnswerContract,
    assessment_message,
    folded,
    reference_span_quality,
    relation_supports_obligation,
)
from .deterministic_calculations import calculation_text
from .errors import ApiError
from .evidence_selection import verified_list_context, verified_table_rows
from .literal_evidence import exact_intervals, merged_spans, projected_text
from .office import cell_semantics
from .scope import block_extraction_method
from .table_subjects import page_subject_applies, prose_page_subject, table_page_subject

STRUCTURED_INSTRUCTION = (
    "\nRestitution structurée : produis uniquement le plan JSON demandé, avec references et comparisons. "
    "Choisis les références Rxxx utiles à la question parmi le catalogue fourni. "
    "references contient les faits ou extraits à restituer ; comparisons contient des groupes de deux à quatre "
    "références à rapprocher. Traite séparément les documents demandés. "
    "Chaque référence de comparisons doit aussi figurer dans references à la racine, une seule fois. "
    "Aucun texte, calcul, valeur ni conclusion ne figure dans le plan. Le serveur restitue les données sources. "
    "Un tableau vide indique qu'aucune référence retenue ne répond à la demande."
)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def comparison_text(comparison, by_id):
    label = PROPERTY_LABELS.get(comparison["property"], comparison["property"] or comparison["quantity"])
    if comparison.get("subject"):
        label += " — " + comparison["subject"]
    names = ", ".join(dict.fromkeys(by_id[reference_id]["document_name"] for reference_id in comparison["reference_ids"]))
    qualification = (" dans les mêmes conditions explicites" if comparison["conditions_explicit"] else
                     " sous les rôles indiqués ; aucune équivalence de conditions d'essai supplémentaires n'est établie")
    conclusion = {"equal": "les valeurs citées concordent" + qualification,
                  "different": "les valeurs citées divergent" + qualification,
                  "context_differs": "les rôles ou conditions cités diffèrent ; aucune conclusion d'accord n'est établie",
                  "context_unestablished": "le rôle d'au moins une valeur n'est pas établi ; aucune conclusion d'accord n'est établie"}[comparison["status"]]
    return f"Comparaison — {label} ({names}) : {conclusion}."


def condition_text(condition):
    return (f"Condition d'essai de {condition['label']} : {condition['condition']}. "
            "Le lien vérifié porte sur la colonne des conditions d'essai ; cette condition ne définit pas à elle seule une limite de la grandeur mesurée.")


RENDER_NOTICES = {
    "operating_guarantee_limitation": "La source précise que les limites absolues ne garantissent pas le fonctionnement normal.",
    "comparison_independence": "La concordance éventuelle des valeurs n'établit pas l'indépendance des documents.",
    "output_omitted": "Restitution limitée par le budget de réponse : certaines références entières ne sont pas affichées.",
    "empty": "Aucune référence sélectionnée dans les preuves retenues ne permet de répondre à la demande.",
    "retrieval_coverage_incomplete": ("La sélection au budget disponible n'a pas conservé toutes les variantes de relations retrouvées. "
                                      "La réponse reste partielle ; aucune conclusion globale ni résolution d'un éventuel conflit n'est établie."),
    "retrieval_unassessed": ("Le budget de recherche a limité les passages retenus. "
                              "Ce diagnostic de sélection n'établit pas la couverture documentaire d'une demande non analysée."),
}


def integrity_failure():
    raise ApiError("source_text_integrity_failure", "Une référence structurée ne correspond pas aux preuves autorisées.", 409)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


class Comparison(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    references: list[str] = Field(min_length=2, max_length=4)


class AnswerPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    references: list[str]
    comparisons: list[Comparison]
    _normalization: list[dict[str, Any]] = PrivateAttr(default_factory=list)

    @property
    def normalization(self):
        return list(self._normalization)


@dataclass
class Catalogue:
    mode: str
    references: list[dict[str, Any]]
    contract: AnswerContract | None = None
    retrieval_limitations: list[dict[str, Any]] = field(default_factory=list)
    required_documents: tuple[str, ...] = ()

    def _retrieval_limitations(self):
        """Only a bounded machine code/count may cross the renderer boundary."""
        if (not isinstance(self.retrieval_limitations, list) or len(self.retrieval_limitations) > 1
                or any(not isinstance(item, dict) or set(item) != {"code", "missing_relation_variants"}
                       or item["code"] != "evidence_coverage_incomplete"
                       or type(item["missing_relation_variants"]) is not int
                       or not 0 < item["missing_relation_variants"] <= 4096 for item in self.retrieval_limitations)):
            raise ApiError("invalid_retrieval_limitation", "Le diagnostic de couverture de la recherche n'est pas vérifiable.", 503)
        return [dict(item) for item in self.retrieval_limitations]

    def as_dict(self):
        value: dict[str, Any] = {"version": 1, "mode": self.mode, "references": self.references}
        if self.contract is not None:
            value["question_contract"] = self.contract.prompt(self.references, self.required_documents)
            value["retrieval_limitations"] = self._retrieval_limitations()
            value["required_documents"] = list(self.required_documents)
        return value

    def schema(self):
        ids = self.model_view()["reference_ids"] if self.contract is not None else [reference["id"] for reference in self.references]
        reference = {"type": "string", **({"enum": ids} if ids else {})}
        # No additional prose or model-produced values are accepted, even in mixed-format scopes.
        return {"type": "object", "additionalProperties": False, "required": ["references", "comparisons"],
                "properties": {
                    "references": {"type": "array", "items": reference, "maxItems": len(ids)},
                    "comparisons": {"type": "array", "maxItems": len(ids), "items": {
                        "type": "object", "additionalProperties": False, "required": ["references"],
                        "properties": {"references": {"type": "array", "items": reference,
                                                        "minItems": 2, "maxItems": 4}}}}}}

    def prompt(self):
        if self.contract is not None:
            return canonical(self.model_view()["payload"])
        items = []
        for reference in self.references:
            item = {key: reference[key] for key in ("id", "kind", "source_ids", "document_id", "document_name")}
            if reference["kind"] == "cell":
                item.update({"cell": reference["cell_facts"]["address"],
                             "formula_present": reference["cell_facts"]["formula_present"],
                             "cached_present": reference["cell_facts"]["cached_present"],
                             "fields": [{key: field[key] for key in ("field", "text", "complete")}
                                        for field in reference["fields"]]})
            else:
                item.update(text=reference["text"], locators=reference["locators"])
            items.append(item)
        payload: dict[str, Any] = {"reference_catalogue": items}
        if self.contract is not None:
            payload["question_contract"] = self.contract.prompt(self.references)
            payload["retrieval_limitations"] = self._retrieval_limitations()
        return canonical(payload)

    def model_view(self):
        """Only admissible exact proofs and their dependencies reach the 4B.

        The complete catalogue remains internal/auditable. This view never
        gives the generator a raw uncertain paragraph to interpret or repair.
        """
        assert self.contract is not None
        publication = self.publication([item["id"] for item in self.references])
        assessment = self.assess(publication["selected_ids"])
        ids = publication["selected_ids"]
        if self.contract.kind == "general" or assessment["status"] == "unassessed":
            ids = []
        allowed = set(ids)
        items = []
        for reference in self.references:
            if reference["id"] not in allowed:
                continue
            item = {key: reference[key] for key in ("id", "kind", "source_ids", "document_id", "document_name")}
            if reference["kind"] == "cell":
                item.update({"cell": reference["cell_facts"]["address"],
                             "formula_present": reference["cell_facts"]["formula_present"],
                             "cached_present": reference["cell_facts"]["cached_present"],
                             "fields": [{key: field[key] for key in ("field", "text", "complete")} for field in reference["fields"]]})
            else:
                item.update(text=projected_text(reference, publication["publication_spans"][reference["id"]]),
                            locators=reference["locators"],
                            source_intervals=publication["publication_spans"][reference["id"]])
            items.append(item)
        obligations = []
        for obligation in assessment.get("obligations", []):
            refs = [ref for ref in obligation["reference_ids"] if ref in allowed]
            obligations.append({**obligation, "reference_ids": refs,
                                "covered": obligation["covered"] and bool(refs) and set(obligation["reference_ids"]) <= allowed})
        diagnostics = [{"reference_ids": [ref for ref in item["reference_ids"] if ref in allowed],
                        "reasons": item.get("reasons", [])}
                       for item in [*assessment.get("rejected_relations", []), *assessment.get("rejected_qualitative_relations", [])]
                       if set(item["reference_ids"]) <= allowed]
        payload = {"reference_catalogue": items,
                   "question_contract": {"kind": self.contract.kind, "status": assessment["status"],
                                         "obligation_schema_version": OBLIGATION_SCHEMA_VERSION, "obligations": obligations,
                                         "required_document_ids": list(self.required_documents),
                                         "required_reference_ids": [ref for ref in self.contract.required_ids(self.references, self.required_documents) if ref in allowed],
                                         "diagnostic_evidence": diagnostics,
                                         "coverage_scope": "retained_catalogue_only"},
                   "retrieval_limitations": self._retrieval_limitations()}
        return {"reference_ids": ids, "payload": payload, "sha256": digest(payload)}

    def assess(self, selected_ids=None, required_documents=()):
        """Passive context/selection diagnosis; no retrieval and no model call."""
        if self.contract is None:
            return {"status": "disabled", "verification": "not_requested"}
        required_documents = tuple(dict.fromkeys((*self.required_documents, *required_documents)))
        assessment = self.contract.assess(self.references, selected_ids, required_documents)
        limitations = self._retrieval_limitations()
        if limitations:
            assessment["retrieval_limitations"] = limitations
            # Search diagnostics do not establish missing facts for a question
            # whose relations are not interpreted. Keep both causes separate.
            if not (assessment["kind"] == "general" and assessment["status"] == "unassessed"):
                assessment["missing"].extend({"requirement": "retrieval_coverage_incomplete", **item} for item in limitations)
                if assessment["status"] not in {"conflict", "ambiguous"}:
                    assessment["status"] = "partial"
            # A value agreement on the retained subset cannot resolve an
            # omitted variant. Exact facts/calculation inputs remain literal.
            assessment["comparisons"] = []
        return assessment

    def evidence(self):
        schema, catalogue = self.schema(), self.as_dict()
        result = {"schema": schema, "catalogue": catalogue,
                  "schema_sha256": digest(schema), "catalogue_sha256": digest(catalogue), "mode": self.mode}
        if self.contract is not None:
            ledger = self.support_ledger()
            result.update(support_ledger=ledger, support_ledger_sha256=digest(ledger))
            view = self.model_view()
            result.update(model_reference_ids=view["reference_ids"], model_evidence_sha256=view["sha256"])
        return result

    def support_ledger(self):
        """Bind each available literal or local relation to the counted sources.

        A quote proves its own source wording, not general semantic entailment.
        Keeping that distinction here prevents a copied but irrelevant passage
        from being reported as a fully established answer to the question.
        """
        assessment = self.assess()
        references = []
        for reference in self.references:
            item = {key: reference.get(key) for key in (
                "id", "kind", "document_id", "document_name", "version_id", "generation_id",
                "extraction_revision_id", "source_file_sha256", "source_ids", "extraction_method", "index_generation_state",
                "source_span_complete")}
            item["locators"] = reference.get("locators") or ([reference["locator"]] if reference.get("locator") else [])
            quality = reference.get("source_quality")
            item["source_quality"] = ({key: quality.get(key) for key in ("state", "policy", "sha256", "reading_ids", "reasons")}
                                      if quality is not None else None)
            item["table_quality"] = reference.get("table_quality")
            literal: list[dict[str, Any]] | dict[str, Any]
            if reference["kind"] == "cell":
                literal = [{key: value.get(key) for key in ("field", "text", "complete", "segments")}
                           for value in reference["fields"]]
            else:
                literal = {"text": reference["text"], "segments": reference.get("segments", [])}
            item.update(literal=literal, literal_sha256=digest(literal), support_kind="source_literal")
            references.append(item)
        return {"version": 1, "scope": "retained_catalogue_only", "verification": assessment.get("verification"),
                "question_status": assessment["status"], "general_semantic_entailment_verified": False,
                "original_extraction_fidelity_verified": False,
                "partial_generation_ids": list(dict.fromkeys(reference.get("generation_id") for reference in self.references
                                                              if reference.get("index_generation_state") == "ready_partial")),
                "references": references, "relations": [*assessment.get("matched_relations", []),
                                                          *assessment.get("matched_qualitative_relations", [])],
                "qualitative_request": assessment.get("qualitative_request"),
                "obligations": assessment.get("obligations", []),
                "retrieval_limitations": self._retrieval_limitations(),
                "rejected_relations": [*assessment.get("rejected_relations", []),
                                       *assessment.get("rejected_qualitative_relations", [])],
                "conflicts": assessment.get("conflicts", [])}

    def publication(self, model_ids, required_documents=()):
        """Project exact proofs and dependencies before admitting a public plan.

        Model IDs only order available proofs. They cannot authorize an extra
        paragraph or remove an established requirement. Diagnostic quotations
        retain explicit negations/conflicts but never uncertified OCR/table data.
        """
        assert self.contract is not None
        contract = self.contract
        required_documents = tuple(dict.fromkeys((*self.required_documents, *required_documents)))
        by_id = {item["id"]: item for item in self.references}
        required = contract.required_ids(self.references, required_documents)
        requested = [] if contract.scope_refusal() else list(dict.fromkeys([*required, *model_ids]))
        assessment = self.assess(requested, required_documents)
        obligations = assessment.get("obligations", [])
        proofs = []
        for fact in assessment.get("matched_relations", []):
            if not fact.get("quantity") or any(relation_supports_obligation(fact, item) for item in obligations):
                proofs.append(fact)
        proofs.extend(assessment.get("matched_qualitative_relations", []))
        proofs.extend(assessment.get("rejected_relations", []))
        proofs.extend(assessment.get("rejected_qualitative_relations", []))
        intervals: dict[str, list[tuple[int, int]]] = {}
        eligible: set[str] = set()
        blocked = {}
        completed_prose_dependencies = {}
        prose_subject_dependencies = {}
        for fact in proofs:
            refs = fact.get("reference_ids", [fact.get("reference_id")])
            primary = fact.get("reference_id") or next((ref for ref in refs if ref in by_id and fact.get("quote") in by_id[ref].get("text", "")), None)
            if primary is None or primary not in by_id:
                continue
            unverified = [reason for reason in fact.get("reasons", []) if reason.startswith("source_quality_")
                          or reason in {"table_general_conditions_unverified", "table_source_binding_unverified",
                                        "table_ancestor_condition_scope_unverified"}]
            if unverified:
                blocked[primary] = unverified
                continue
            reference = by_id[primary]
            if reference["kind"] == "cell":
                eligible.update(ref for ref in refs if ref in by_id)
                continue
            start, end = fact.get("source_start"), fact.get("source_end")
            spans = ([(start, end)] if type(start) is int and type(end) is int
                     and reference["text"][start:end] == fact.get("quote") else exact_intervals(reference["text"], fact.get("quote", "")))
            if len(spans) != 1:
                continue  # repeated wording cannot acquire a convenient offset
            proof_spans = {primary: spans}
            for ref in refs:
                if ref != primary and ref in by_id and by_id[ref]["kind"] == "excerpt":
                    declared = fact.get("dependency_spans", {}).get(ref)
                    proof_spans[ref] = ([(item["start_offset"], item["end_offset"]) for item in declared]
                                        if declared else [(0, len(by_id[ref]["text"]))])
            # A proved value and its conditions/headers form one admission
            # unit. Dropping an unreadable dependency cannot leave the value
            # publicly associated with the remaining, incomplete context.
            dependency_failures = []
            for ref, ranges in proof_spans.items():
                checked = [reference_span_quality(by_id[ref], low, high) for low, high in ranges]
                quality = by_id[ref].get("table_quality")
                if any(item is not None and item["state"] not in {"native", "corroborated"} for item in checked):
                    dependency_failures.append("dependency_source_quality_unavailable")
                if quality is not None and quality.get("state") != "supported":
                    dependency_failures.append("dependency_table_binding_unverified")
            if dependency_failures or not set(refs) <= set(by_id):
                blocked[primary] = list(dict.fromkeys(dependency_failures or ["dependency_not_retained"]))
                continue
            # Selecting a diagnostic's primary quotation does not authorize
            # dropping its already verified page identity. Complete only this
            # dependency; never select a new diagnostic on the model's behalf.
            binding = fact.get("page_subject_binding") or {}
            if binding.get("schema_version") == "prose-page-subject-v1" and primary in requested:
                dependency = binding["header"]["reference_id"]
                prose_subject_dependencies[primary] = [dependency]
                if dependency not in requested:
                    requested.append(dependency)
                    completed_prose_dependencies[dependency] = primary
            eligible.add(primary)
            intervals.setdefault(primary, []).extend(spans)
            for ref in refs:
                if ref != primary and ref in by_id:
                    eligible.add(ref)
                    if by_id[ref]["kind"] == "excerpt":
                        declared_spans = fact.get("dependency_spans", {}).get(ref)
                        intervals.setdefault(ref, []).extend([(item["start_offset"], item["end_offset"]) for item in declared_spans]
                                                            if declared_spans else [(0, len(by_id[ref]["text"]))])
        # Exact structured cell operations and legacy literal requests have
        # their own checked support. Unknown prose is explicitly unassessed.
        literal_route = contract.kind in {"general", "cell_values", "calculation", "mapping"} or assessment["status"] == "unassessed"
        literal_required = set(required)
        if contract.kind in {"cell_values", "calculation"}:
            _, addresses = contract._cells(self.references)
            literal_required.update(reference["id"] for reference in self.references if reference["kind"] == "cell"
                                    and reference["cell_facts"]["address"] in addresses)
        for ref in requested:
            reference = by_id[ref]
            context = reference.get("list_context") or {}
            if (reference.get("prose_context") or {}).get("page_subject") and ref not in eligible:
                continue  # no legacy-literal fallback around a broken subject dependency
            if (literal_route and ref in literal_required or context.get("catalogue_verified") and assessment["status"] != "covered") and ref not in eligible:
                eligible.add(ref)
                if reference["kind"] == "excerpt":
                    intervals.setdefault(ref, []).append((0, len(reference["text"])))
        spans_by_id = {}
        selected = []
        for ref in requested:
            if ref not in eligible:
                continue
            reference = by_id[ref]
            if reference["kind"] == "cell":
                selected.append(ref)
                continue
            spans = merged_spans(intervals.get(ref, []), reference["text"])
            if not spans:
                continue
            quality = [reference_span_quality(reference, item["start_offset"], item["end_offset"]) for item in spans]
            table_quality = reference.get("table_quality")
            reasons = [reason for item in quality if item is not None and item["state"] not in {"native", "corroborated"}
                       for reason in item.get("reasons", ["source_quality_unavailable"])]
            if table_quality is not None and table_quality.get("state") != "supported":
                reasons.extend(table_quality.get("reasons", []) or ["table_binding_unverified"])
            if reasons:
                blocked[ref] = list(dict.fromkeys(reasons))
                continue
            selected.append(ref)
            spans_by_id[ref] = spans
        excluded = [ref for ref in model_ids if ref not in selected]
        blocked = {ref: reasons for ref, reasons in blocked.items() if ref not in selected}
        added = [ref for ref in selected if (ref in required or ref in completed_prose_dependencies) and ref not in model_ids]
        journal = ([{"operation": "complete_prose_subject_dependency", "reference_id": ref,
                     "for_reference_id": completed_prose_dependencies[ref]} if ref in completed_prose_dependencies
                    else {"operation": "complete_required_reference", "reference_id": ref} for ref in added]
                   + [{"operation": "exclude_unverified_source" if ref in blocked else "exclude_unrelated_reference",
                       "reference_id": ref, "reasons": blocked.get(ref, [])} for ref in excluded])
        return {"selected_ids": selected, "added_ids": added, "excluded_ids": excluded,
                "publication_spans": spans_by_id, "selection_journal": journal,
                "prose_subject_dependencies": {ref: dependencies for ref, dependencies in prose_subject_dependencies.items()
                                               if ref in selected},
                "blocked_reference_ids": blocked}

    def validate(self, raw):
        try:
            if len(raw.encode()) > 131_072:
                raise ValueError("plan too large")
            plan = AnswerPlan.model_validate(json.loads(raw, object_pairs_hook=unique_object))
            ids = {reference["id"] for reference in self.references}
            selected = plan.references
            if self.contract is not None:
                # Validate every original reference before repairing redundancy.
                # A known group member may be restored to the root selection;
                # unknown references, extra fields and invalid JSON never are.
                if len(selected) > max(4, len(ids) * 4) or len(plan.comparisons) > max(4, len(ids) * 4):
                    raise ValueError("plan redundancy limit")
                if set(selected) - ids or any(set(group.references) - ids for group in plan.comparisons):
                    raise ValueError("unknown reference")
                normalized = list(dict.fromkeys(selected))
                events: list[dict[str, Any]] = []
                if normalized != selected:
                    events.append({"operation": "deduplicate_root_references"})
                normalized_groups: list[Comparison] = []
                seen = set()
                for comparison in plan.comparisons:
                    group = list(dict.fromkeys(comparison.references))
                    for reference in group:
                        if reference not in normalized:
                            normalized.append(reference)
                            events.append({"operation": "restore_group_reference", "reference_id": reference})
                    key = tuple(sorted(group))
                    if len(group) < 2 or key in seen:
                        events.append({"operation": "remove_redundant_comparison", "reference_ids": group})
                        continue
                    if group != comparison.references:
                        events.append({"operation": "deduplicate_group_references", "reference_ids": group})
                    normalized_groups.append(Comparison(references=group))
                    seen.add(key)
                plan = AnswerPlan(references=normalized, comparisons=normalized_groups)
                plan._normalization = events
                return plan
            if len(selected) > len(ids) or len(selected) != len(set(selected)) or set(selected) - ids:
                raise ValueError("invalid selection")
            if len(plan.comparisons) > len(ids):
                raise ValueError("too many comparisons")
            groups: list[tuple[str, ...]] = []
            for comparison in plan.comparisons:
                group = comparison.references
                if len(group) != len(set(group)) or set(group) - set(selected):
                    raise ValueError("comparison outside selection")
                key = tuple(sorted(group))
                if key in groups:
                    raise ValueError("duplicate comparison")
                groups.append(key)
            return plan
        except (ValidationError, ValueError) as failure:
            raise ApiError("structured_answer_invalid", "Le plan généré ne référence pas uniquement des preuves autorisées.", 503) from failure

    def render(self, plan, tokenizer, output_tokens, required_documents=()):
        if self.contract is not None:
            return self._render_contract(plan, tokenizer, output_tokens, required_documents)
        return self._render_legacy(plan, tokenizer, output_tokens, required_documents)

    def _render_legacy(self, plan, tokenizer, output_tokens, required_documents=()):
        by_id = {reference["id"]: reference for reference in self.references}
        selected = [by_id[ref] for ref in plan.references]
        sections: dict[str, list[dict[str, Any]]] = {}
        names = {}
        cited: list[str] = []
        for reference in selected:
            document = reference["document_id"]
            names[document] = reference["document_name"]
            sections.setdefault(document, []).append(reference)
            cited.extend(reference["source_ids"])
        parts: list[tuple[str, list[str]]] = []
        for document, items in sections.items():
            parts.append((names[document], []))
            parts.extend((render_reference(reference), reference["source_ids"]) for reference in items)
        if plan.comparisons:
            parts.append(("Rapprochements des données enregistrées :", []))
            for comparison in plan.comparisons:
                refs = [by_id[ref] for ref in comparison.references]
                parts.extend((render_reference(reference, include_document=True), reference["source_ids"]) for reference in refs)
                parts.append(("Ce rapprochement n'établit ni concordance globale ni indépendance des documents.", []))
        warnings = []
        for reference in selected:
            if reference["kind"] != "cell":
                continue
            if any(not field["complete"] for field in reference["fields"]):
                warnings.append({"code": "structured_field_partial", "source_ids": reference["source_ids"],
                                 "address": reference["cell_facts"]["address"],
                                 "message": "La restitution de cette cellule ne contient que les caractères autorisés retenus."})
            if reference["cell_facts"]["formula_present"] and not reference["cell_facts"]["cached_present"]:
                warnings.append({"code": "structured_formula_cache_absent", "source_ids": reference["source_ids"],
                                 "address": reference["cell_facts"]["address"],
                                 "message": "Formule enregistrée sans cache source ; son résultat est indisponible."})
        missing = [document for document in required_documents if document not in sections]
        if missing:
            warnings.append({"code": "structured_document_not_selected", "document_ids": missing,
                             "message": "Le plan ne sélectionne pas de fait pour certains documents demandés ; restitution partielle."})
            parts.append(("Restitution partielle : certains documents demandés n'ont pas de fait sélectionné.", []))
        if not selected:
            parts.insert(0, ("Aucune référence sélectionnée dans les preuves retenues ne permet de répondre à la demande.", []))
        else:
            parts.append(("Périmètre de restitution : seules les cellules et les extraits référencés ci-dessus ; aucun inventaire complet ni total calculé.", []))
        answer = ""
        citation_spans = []
        for text, source_ids in parts:
            answer += ("\n\n" if answer else "") + text
            for source_id in source_ids:
                answer += " "
                start = len(answer)
                answer += f"[{source_id}]"
                citation_spans.append({"source_id": source_id, "start_offset": start, "end_offset": len(answer)})
        tokens = tokenizer.count(answer)
        if tokens > output_tokens:
            raise ApiError("structured_answer_render_budget_exceeded", "Les faits sélectionnés dépassent la limite de restitution. Réduisez la demande ou le périmètre.", 503)
        return {"text": answer, "source_ids": list(dict.fromkeys(cited)), "warnings": warnings,
                "tokens": tokens, "citation_spans": citation_spans}

    def _render_contract(self, plan, tokenizer, output_tokens, required_documents):
        assert self.contract is not None
        by_id = {reference["id"]: reference for reference in self.references}
        publication = self.publication(plan.references, required_documents)
        selected_ids, added = publication["selected_ids"], publication["added_ids"]
        publication_spans = publication["publication_spans"]
        initial = self.assess(selected_ids, required_documents)
        parts = []
        calculation = initial.get("calculation")
        calculation_ids = [item["reference_id"] for item in calculation["inputs"]] if calculation else []
        if calculation and calculation.get("unit_reference"):
            calculation_ids.append(calculation["unit_reference"]["reference_id"])
        if calculation:
            parts.append({"text": calculation_text(calculation), "source_ids": calculation["source_ids"],
                          "reference_ids": calculation_ids, "kind": "calculation"})
        derived = initial.get("derived_calculations", [])
        represented = set(calculation_ids)
        if derived:
            derived_ids = list(dict.fromkeys(reference_id for result in derived for reference_id in result["reference_ids"]))
            text = "\n\n".join([*(calculation_text(result) for result in derived),
                                  *(render_reference(by_id[reference_id], include_document=True) for reference_id in derived_ids)])
            parts.append({"text": text, "source_ids": list(dict.fromkeys(source_id for result in derived for source_id in result["source_ids"])),
                          "reference_ids": derived_ids, "kind": "relation_calculations"})
            represented.update(derived_ids)
        prose_dependencies = publication["prose_subject_dependencies"]
        prose_headers = {dependency for dependencies in prose_dependencies.values() for dependency in dependencies}
        for reference_id in selected_ids:
            # The operation already reproduces its exact input values, labels
            # and source citations; avoid repeating a whole cell paragraph.
            if reference_id in represented or reference_id in prose_headers:
                continue
            reference = by_id[reference_id]
            context = reference.get("table_context") or reference.get("list_context") or {}
            bundle = [item for item in context.get("reference_ids", []) if item in selected_ids]
            bundle.extend(item for item in prose_dependencies.get(reference_id, []) if item in selected_ids)
            bundle = list(dict.fromkeys([*bundle, reference_id]))
            parts.append({"text": "\n".join(render_reference(by_id[item], include_document=True,
                                                          spans=publication_spans.get(item)) for item in bundle),
                          "source_ids": list(dict.fromkeys(source_id for item in bundle for source_id in by_id[item]["source_ids"])),
                          "reference_ids": bundle, "kind": "reference"})
            represented.update(bundle)

        def compose(parts, assessment, omitted):
            answer = ""
            spans = []
            support = []

            def append_text(text, kind, reference_ids=(), source_ids=(), *, index=None, notice=None, separator="\n\n"):
                nonlocal answer
                answer += separator if answer else ""
                start = len(answer)
                answer += text
                support.append({"kind": kind, "reference_ids": list(reference_ids), "source_ids": list(source_ids),
                                "start_offset": start, "end_offset": len(answer), "index": index, "notice": notice})

            def append_citations(source_ids, reference_ids):
                for source_id in source_ids:
                    linked = [reference_id for reference_id in reference_ids if source_id in by_id[reference_id]["source_ids"]]
                    append_text(f"[{source_id}]", "citation", linked, [source_id], separator=" ")
                    spans.append({"source_id": source_id, "start_offset": support[-1]["start_offset"],
                                  "end_offset": support[-1]["end_offset"]})

            if assessment.get("retrieval_limitations"):
                notice = ("retrieval_unassessed" if assessment["kind"] == "general" and assessment["status"] == "unassessed"
                          else "retrieval_coverage_incomplete")
                append_text(RENDER_NOTICES[notice], "notice", notice=notice)
            message = assessment_message(assessment)
            if message:
                append_text(message, "notice", notice="assessment")
            for part in parts:
                append_text(part["text"], part["kind"], part["reference_ids"], part["source_ids"])
                append_citations(part["source_ids"], part["reference_ids"])
            for index, comparison in enumerate(assessment.get("comparisons", [])):
                refs = comparison["reference_ids"]
                sources = list(dict.fromkeys(source for reference_id in refs for source in by_id[reference_id]["source_ids"]))
                append_text(comparison_text(comparison, by_id), "comparison", refs, sources, index=index)
                append_citations(sources, refs)
            for index, fact in enumerate(assessment.get("matched_relations", [])):
                if fact["kind"] not in {"test_condition", "operating_guarantee_limitation"}:
                    continue
                text = condition_text(fact) if fact["kind"] == "test_condition" else RENDER_NOTICES[fact["kind"]]
                refs = fact["reference_ids"]
                append_text(text, fact["kind"], refs, fact["source_ids"], index=index)
                append_citations(fact["source_ids"], refs)
            if assessment.get("comparisons"):
                append_text(RENDER_NOTICES["comparison_independence"], "notice", notice="comparison_independence", separator=" ")
            if omitted:
                append_text(RENDER_NOTICES["output_omitted"], "notice", notice="output_omitted")
            if not answer:
                append_text(RENDER_NOTICES["empty"], "notice", notice="empty")
            return answer, spans, support

        def evaluate(candidate_parts):
            displayed = list(dict.fromkeys(reference for part in candidate_parts for reference in part["reference_ids"]))
            omitted = [reference for reference in selected_ids if reference not in displayed]
            assessment = self.assess(displayed, required_documents)
            if initial["status"] in {"conflict", "ambiguous"}:
                # Not showing one conflicting excerpt must not turn the result
                # into an apparently resolved single-valued answer.
                assessment["status"] = initial["status"]
                assessment["conflicts"] = initial["conflicts"]
                assessment["ambiguous"] = initial["ambiguous"]
            elif omitted:
                assessment["status"] = "partial"
            assessment.update({"model_selected_reference_ids": plan.references, "added_reference_ids": added,
                               "omitted_reference_ids": omitted, "rendered_reference_ids": displayed,
                               "excluded_reference_ids": publication["excluded_ids"],
                               "publication_spans": {ref: publication_spans[ref] for ref in displayed if ref in publication_spans},
                               "publication_control": {"version": 1, "selection_journal": publication["selection_journal"],
                                                       "blocked_reference_ids": publication["blocked_reference_ids"],
                                                       "omitted_reference_ids": omitted}})
            if plan.normalization:
                assessment["plan_normalization"] = plan.normalization
            if not any(part["kind"] == "calculation" for part in candidate_parts):
                assessment["calculation"] = None
            if not any(part["kind"] == "relation_calculations" for part in candidate_parts):
                assessment["derived_calculations"] = []
            answer, spans, support = compose(candidate_parts, assessment, omitted)
            tokens = tokenizer.count(answer)
            return displayed, omitted, assessment, answer, spans, support, tokens

        # Admit whole references in stable priority order. An oversized first
        # excerpt must not erase later useful excerpts that fit. Evaluate all
        # first: intermediate partial-coverage notices can cost more than the
        # complete answer's notice. Never truncate a fact/condition/calculation.
        displayed, omitted, assessment, answer, spans, support, tokens = evaluate(parts)
        if tokens > output_tokens:
            admitted: list[dict[str, Any]] = []
            for part in parts:
                candidate = [*admitted, part]
                if evaluate(candidate)[-1] <= output_tokens:
                    admitted.append(part)
            parts = admitted
            displayed, omitted, assessment, answer, spans, support, tokens = evaluate(parts)
            if tokens > output_tokens:
                raise ApiError("structured_answer_render_budget_exceeded", "Le budget de restitution ne permet pas même d'afficher les limites de la réponse.", 503)
        warnings = []
        if plan.normalization:
            warnings.append({"code": "answer_contract_plan_normalized", "operations": plan.normalization,
                             "message": "Les références autorisées ont été préservées et les doublons retirés du plan."})
        message = assessment_message(assessment)
        if message:
            warnings.append({"code": "answer_contract_" + assessment["status"], "message": message,
                             "verification": assessment["verification"], "missing": assessment["missing"]})
        if omitted:
            warnings.append({"code": "answer_contract_output_partial", "reference_ids": omitted,
                             "message": "Certaines références complètes dépassent le budget de restitution ; elles ne sont pas affichées."})
        if added:
            warnings.append({"code": "answer_contract_selection_completed", "reference_ids": added,
                             "message": "Des références déjà présentes au contexte ont été réintégrées pour couvrir la demande explicite."})
        if publication["excluded_ids"]:
            warnings.append({"code": "answer_contract_selection_filtered", "reference_ids": publication["excluded_ids"],
                             "message": "Les ajouts sans preuve pertinente admissible ont été retirés du plan."})
        for reference_id in displayed:
            reference = by_id[reference_id]
            if reference["kind"] != "cell":
                continue
            if any(not field["complete"] for field in reference["fields"]):
                warnings.append({"code": "structured_field_partial", "source_ids": reference["source_ids"],
                                 "address": reference["cell_facts"]["address"],
                                 "message": "La restitution de cette cellule ne contient que les caractères autorisés retenus."})
            if reference["cell_facts"]["formula_present"] and not reference["cell_facts"]["cached_present"]:
                warnings.append({"code": "structured_formula_cache_absent", "source_ids": reference["source_ids"],
                                 "address": reference["cell_facts"]["address"],
                                 "message": "Formule enregistrée sans cache source ; son résultat est indisponible."})
        effective_plan = {"references": displayed,
                          "comparisons": [comparison.model_dump() for comparison in plan.comparisons
                                          if set(comparison.references) <= set(displayed)]}
        result = {"text": answer, "source_ids": list(dict.fromkeys(source for part in parts for source in part["source_ids"])),
                  "warnings": warnings, "tokens": tokens, "citation_spans": spans,
                  "answer_contract": assessment, "effective_plan": effective_plan,
                  "support_ledger": {"version": 1, "catalogue_sha256": digest(self.as_dict()),
                                     "required_documents": list(required_documents), "segments": support,
                                     "answer_sha256": hashlib.sha256(answer.encode()).hexdigest()}}
        result["support_ledger_sha256"] = digest(result["support_ledger"])
        result["support_validation"] = self.verify_rendered(result)
        return result

    def verify_rendered(self, rendered):
        """Reconstruct each output segment from sources or checked operations.

        Model text never enters this contract. The check also detects an added
        tail, an altered number, an uncited quotation, a forged source ID and a
        catalogue changed between planning and publication. Source truth and
        unrestricted semantic entailment remain outside this structural gate.
        """
        if self.contract is None:
            return {"status": "disabled", "method": "legacy_catalogue"}
        try:
            text, ledger = rendered["text"], rendered["support_ledger"]
            if (not isinstance(text, str) or ledger["version"] != 1
                    or rendered["support_ledger_sha256"] != digest(ledger)
                    or ledger["catalogue_sha256"] != digest(self.as_dict())
                    or ledger["answer_sha256"] != hashlib.sha256(text.encode()).hexdigest()):
                raise ValueError("answer or catalogue digest mismatch")
            by_id = {reference["id"]: reference for reference in self.references}
            displayed = rendered["effective_plan"]["references"]
            if len(displayed) != len(set(displayed)) or set(displayed) - by_id.keys():
                raise ValueError("unknown or repeated rendered reference")
            assessment = rendered["answer_contract"]
            required_documents = ledger["required_documents"]
            checked = self.assess(displayed, required_documents)
            publication = self.publication(assessment["model_selected_reference_ids"], required_documents)
            for reference_id in displayed:
                if not set(publication["prose_subject_dependencies"].get(reference_id, [])) <= set(displayed):
                    raise ValueError("rendered prose without its exact page subject")
            selected = publication["selected_ids"]
            if set(selected) - by_id.keys():
                raise ValueError("unknown initial reference")
            omitted = [reference_id for reference_id in selected if reference_id not in displayed]
            initial = self.assess(selected, required_documents)
            expected_status = (initial["status"] if initial["status"] in {"conflict", "ambiguous"}
                               else "partial" if omitted else checked["status"])
            if (assessment["status"] != expected_status or assessment["omitted_reference_ids"] != omitted
                    or assessment["rendered_reference_ids"] != displayed):
                raise ValueError("coverage changed after rendering")
            expected_spans = {ref: publication["publication_spans"][ref] for ref in displayed if ref in publication["publication_spans"]}
            expected_control = {"version": 1, "selection_journal": publication["selection_journal"],
                                "blocked_reference_ids": publication["blocked_reference_ids"], "omitted_reference_ids": omitted}
            if (canonical(assessment.get("publication_spans")) != canonical(expected_spans)
                    or canonical(assessment.get("publication_control")) != canonical(expected_control)
                    or assessment.get("excluded_reference_ids") != publication["excluded_ids"]
                    or assessment.get("added_reference_ids") != publication["added_ids"]):
                raise ValueError("publication proof or completion changed")
            for field in ("matched_relations", "matched_qualitative_relations", "comparisons", "conflicts"):
                if canonical(assessment.get(field, [])) != canonical(checked.get(field, [])):
                    raise ValueError("unsupported relation or comparison")
            for field in ("kind", "quantity", "missing", "scope_refusal", "rejected_relations", "qualitative_request",
                          "rejected_qualitative_relations", "retrieval_limitations", "obligations", "interpretation_limitations",
                          "required_reference_ids", "requested_properties", "requested_subjects"):
                if canonical(assessment.get(field)) != canonical(checked.get(field)):
                    raise ValueError("unsupported coverage explanation")
            expected_ambiguities = (initial.get("ambiguous", []) if initial["status"] in {"conflict", "ambiguous"}
                                    else checked.get("ambiguous", []))
            if canonical(assessment.get("ambiguous", [])) != canonical(expected_ambiguities):
                raise ValueError("ambiguity explanation changed")
            segments, cursor, seen_references, citation_spans = ledger["segments"], 0, [], []
            if not isinstance(segments, list) or len(segments) > 4096:
                raise ValueError("invalid support segment count")
            pending_citations: list[str] = []
            expected: str | None
            for segment in segments:
                start, end = segment["start_offset"], segment["end_offset"]
                if (type(start) is not int or type(end) is not int or not cursor <= start < end <= len(text)
                        or text[cursor:start].strip()):
                    raise ValueError("uncovered text or invalid support offsets")
                refs, sources = segment["reference_ids"], segment["source_ids"]
                if set(refs) - set(displayed) or len(refs) != len(set(refs)) or len(sources) != len(set(sources)):
                    raise ValueError("support outside displayed references")
                expected_sources = list(dict.fromkeys(source_id for reference_id in refs for source_id in by_id[reference_id]["source_ids"]))
                kind = segment["kind"]
                if kind == "citation":
                    if len(sources) != 1 or not refs or sources[0] not in expected_sources or not pending_citations:
                        raise ValueError("citation without supporting content")
                    if sources[0] != pending_citations.pop(0):
                        raise ValueError("citation does not match preceding claim")
                    expected = f"[{sources[0]}]"
                    citation_spans.append({"source_id": sources[0], "start_offset": start, "end_offset": end})
                else:
                    if pending_citations:
                        raise ValueError("uncited documentary content")
                    if set(sources) != set(expected_sources):
                        raise ValueError("missing or substituted documentary source")
                    if kind == "reference":
                        expected = "\n".join(render_reference(by_id[reference_id], include_document=True,
                                                            spans=expected_spans.get(reference_id)) for reference_id in refs)
                        seen_references.extend(refs)
                    elif kind == "calculation":
                        calculation = checked.get("calculation")
                        if not calculation or canonical(calculation) != canonical(assessment.get("calculation")):
                            raise ValueError("unverified calculation")
                        expected = calculation_text(calculation)
                        expected_refs = [item["reference_id"] for item in calculation["inputs"]]
                        if calculation.get("unit_reference"):
                            expected_refs.append(calculation["unit_reference"]["reference_id"])
                        if refs != expected_refs:
                            raise ValueError("calculation inputs lost")
                        seen_references.extend(refs)
                    elif kind == "relation_calculations":
                        calculations = checked.get("derived_calculations")
                        if not calculations or canonical(calculations) != canonical(assessment.get("derived_calculations")):
                            raise ValueError("unverified relation calculation")
                        expected_refs = list(dict.fromkeys(reference_id for result in calculations for reference_id in result["reference_ids"]))
                        if refs != expected_refs:
                            raise ValueError("relation calculation dependencies lost")
                        expected = "\n\n".join([*(calculation_text(result) for result in calculations),
                                               *(render_reference(by_id[reference_id], include_document=True) for reference_id in refs)])
                        seen_references.extend(refs)
                    elif kind == "comparison":
                        comparison = checked["comparisons"][segment["index"]]
                        if refs != comparison["reference_ids"]:
                            raise ValueError("comparison dependencies lost")
                        expected = comparison_text(comparison, by_id)
                    elif kind in {"test_condition", "operating_guarantee_limitation"}:
                        fact = checked["matched_relations"][segment["index"]]
                        if fact["kind"] != kind or refs != fact["reference_ids"]:
                            raise ValueError("relation dependencies lost")
                        expected = condition_text(fact) if kind == "test_condition" else RENDER_NOTICES[kind]
                    elif kind == "notice":
                        if refs or sources:
                            raise ValueError("notice impersonates a documentary claim")
                        notice = segment["notice"]
                        if (notice == "output_omitted" and not omitted
                                or notice == "comparison_independence" and not checked["comparisons"]
                                or notice in {"retrieval_coverage_incomplete", "retrieval_unassessed"}
                                and (not checked.get("retrieval_limitations")
                                     or (notice == "retrieval_unassessed") != (checked["kind"] == "general" and checked["status"] == "unassessed"))
                                or notice == "empty" and displayed):
                            raise ValueError("unsupported notice")
                        expected = assessment_message(assessment) if notice == "assessment" else RENDER_NOTICES[notice]
                    else:
                        raise ValueError("unknown support kind")
                    pending_citations = list(sources)
                if not expected or text[start:end] != expected:
                    raise ValueError("published content differs from its support")
                cursor = end
            if (pending_citations or text[cursor:].strip() or list(dict.fromkeys(seen_references)) != displayed
                    or citation_spans != rendered["citation_spans"]
                    or list(dict.fromkeys(item["source_id"] for item in citation_spans)) != rendered["source_ids"]):
                raise ValueError("incomplete output support")
            return {"status": "passed", "method": "deterministic_source_reconstruction", "segments_checked": len(segments),
                    "unsupported_characters": 0, "question_status": assessment["status"],
                    "general_semantic_entailment_verified": False, "answer_sha256": ledger["answer_sha256"]}
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ApiError("structured_answer_support_invalid", "La restitution ne correspond pas intégralement à ses preuves vérifiées.", 503) from error

    def deterministic_plan(self, required_documents=()) -> AnswerPlan | None:
        """Complete local relations or exact scoped cells need no model choice.

        Expected deterministic refusals (missing formula cache, division by
        zero, unavailable unit) still render their actual reason and sources.
        An empty verified projection has a deterministic limit route. Incomplete
        relations and ambiguous cells with admissible diagnostics keep the
        reference-selection route. Completeness is rechecked after rendering.
        """
        contract = self.contract
        required_documents = tuple(dict.fromkeys((*self.required_documents, *required_documents)))
        if contract is not None and contract.scope_refusal():
            return AnswerPlan(references=[], comparisons=[])
        if contract is not None and not self.model_view()["reference_ids"]:
            return AnswerPlan(references=[], comparisons=[])
        if (contract is not None and not contract.parse_failures
                and (contract.kind in {"value", "interval", "comparison"} and contract.quantity is not None
                     or contract.kind == "mapping" and bool(contract.configurations)
                     or contract.kind in {"qualitative", "composite"})):
            required = contract.required_ids(self.references, required_documents)
            if required and self.assess(required, required_documents)["status"] == "covered":
                # Selection is already established by local relation checks.
                # Running a model cannot add a useful fact to this exact set.
                return AnswerPlan(references=required, comparisons=[])
        if (contract is None or contract.scope.get("kind") != "cell_range"
                or contract.kind not in {"cell_values", "calculation"}
                or not contract.requested_cells or contract.parse_failures or contract.subjects):
            return None
        if contract.kind == "cell_values" and not re.match(
                r"^(?:quelles?\s+(?:valeurs?|formules?|unites?)|what\s+(?:(?:are|is)\s+the\s+)?(?:values?|formulas?|units?))\b",
                folded(contract.question)):
            return None
        required = contract.required_ids(self.references)
        selected = [reference for reference in self.references if reference["id"] in required]
        if (len(required) != len(contract.requested_cells)
                or any(reference["kind"] != "cell" or any(not field["complete"] for field in reference["fields"])
                       for reference in selected)):
            return None
        if self.assess(required)["status"] in {"ambiguous", "conflict", "unassessed"}:
            return None
        return AnswerPlan(references=required, comparisons=[])


def quoted(text):
    # React renders source text literally. Only renderer-generated spans designate citations.
    return str(text)


def render_reference(reference, include_document=False, *, spans=None):
    heading = f"{quoted(reference['document_name'])} — " if include_document else ""
    if reference["kind"] == "excerpt":
        literal = projected_text(reference, spans) if spans is not None else reference["text"]
        text = heading + "Extrait : « " + quoted(literal) + " »"
        context = reference.get("table_context") or {}
        if context.get("catalogue_verified") and context.get("row_role") == "data":
            bound = [(cell, [header for header in cell["headers"] if header.get("role") in
                            {"minimum", "maximum", "typical", "nominal", "condition", "unit"}]) for cell in context["cells"]]
            labels = [f"{header['text'].strip()} = {cell['text'].strip()}" for cell, headers in bound for header in headers]
            if labels:
                text += " Liaisons aux en-têtes : " + "; ".join(labels) + "."
        return text
    facts = reference["cell_facts"]
    fields = {field["field"]: field for field in reference["fields"]}
    heading += quoted(reference["locator"].get("sheet_name") or reference["locator"]["unit_id"]) + " / " + facts["address"] + " : "
    parts = []
    for field_name, label in (("value", "Cache source" if facts["formula_present"] else "Valeur littérale"),
                              ("formula", "Formule enregistrée"), ("comment", "Commentaire source")):
        field = fields.get(field_name)
        if field is not None:
            part = label + " « " + quoted(field["text"]) + " »"
            if not field["complete"]:
                part += " (champ partiel, caractères autorisés uniquement)"
            parts.append(part)
    if facts["formula_present"]:
        if "formula" not in fields:
            parts.append("formule présente, expression absente des caractères retenus")
        if facts["cached_present"]:
            parts.append("cache enregistré de fraîcheur inconnue" if "value" in fields
                         else "cache présent, valeur absente des caractères retenus")
        else:
            parts.append("résultat indisponible : cache source absent")
        parts.append("aucun calcul effectué par cette application ; activité et historique d'exécution non établis")
    if not parts:
        parts.append("aucune valeur dans les caractères retenus")
    return heading + "; ".join(parts) + "."


class StructuredAnswerBuilder:
    def __init__(self, db, snapshot, question=None, enforce_contract=False):
        self.db, self.snapshot = db, snapshot
        self.question, self.enforce_contract = question, enforce_contract
        self.parents: dict[tuple[str, str], dict[str, Any]] = {}
        self.cells: dict[tuple[str, str, int, int], dict[str, Any]] = {}
        self.versions: dict[str, dict[str, Any]] = {}
        self.generations: dict[str, dict[str, Any]] = {}
        self.source_qualities: dict[tuple[str, str], dict[str, Any]] = {}
        self.table_qualities: dict[tuple[str, str], dict[str, Any]] = {}
        self.page_geometries: dict[tuple[str, int], dict[str, Any] | None] = {}

    def parent(self, source, block):
        generation = source["generation_id"]
        if (generation not in self.snapshot.generations
                or source["version_id"] != self.snapshot.versions[generation]
                or source["document_id"] != self.snapshot.documents[generation]):
            integrity_failure()
        key = (generation, block["id"])
        if key not in self.parents:
            row = self.db.one("SELECT kind,text,page_index,bbox_json,source_text_hash,extraction_revision_id,metadata_json FROM blocks WHERE generation_id=? AND id=?", key)
            if not row:
                integrity_failure()
            self.parents[key] = dict(row)
        parent = self.parents[key]
        start, end = block["start_offset"], block["end_offset"]
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(parent["text"])
                or parent["source_text_hash"] != block["source_text_hash"]
                or hashlib.sha256(parent["text"].encode()).hexdigest() != block["source_text_hash"]
                or parent["extraction_revision_id"] != block["extraction_revision_id"]
                or block.get("page_index") != parent["page_index"]
                or source["extraction_revision_id"] != block["extraction_revision_id"]
                or parent["text"][start:end] != block["text"]):
            integrity_failure()
        snapshot = self.snapshot
        if (snapshot.block_ids is not None and block["id"] not in snapshot.block_ids
                or snapshot.page_indices is not None and block.get("page_index") not in snapshot.page_indices
                or snapshot.spans and not any(span["blockId"] == block["id"] and span["startOffset"] <= start
                                             and end <= span["endOffset"] for span in snapshot.spans)):
            integrity_failure()
        return parent, json.loads(parent["metadata_json"])

    def cell(self, generation, unit, binding):
        row, column = binding["row"], binding["column"]
        if type(row) is not int or type(column) is not int or address_coordinates(binding["address"]) != (row, column):
            integrity_failure()
        key = (generation, unit, row, column)
        if key not in self.cells:
            value = self.db.one("SELECT data_json FROM office_cells WHERE generation_id=? AND unit_id=? AND row_index=? AND column_index=?", key)
            if not value:
                integrity_failure()
            self.cells[key] = json.loads(value["data_json"])
        scope = self.snapshot.scope
        if scope["kind"] == "cell_range" and (scope["sheetId"] != unit or not scope["rowStart"] <= row <= scope["rowEnd"]
                                               or not scope["columnStart"] <= column <= scope["columnEnd"]):
            integrity_failure()
        if self.snapshot.cell_ranges is not None and not any(
                bounds["row_start"] <= row <= bounds["row_end"] and bounds["column_start"] <= column <= bounds["column_end"]
                for bounds in self.snapshot.cell_ranges):
            integrity_failure()
        return self.cells[key]

    def catalogue(self, sources, mode) -> Catalogue:
        entries: dict[tuple, dict[str, Any]] = {}
        for source in sources:
            if (source["generation_id"] not in self.snapshot.generations
                    or self.snapshot.versions[source["generation_id"]] != source["version_id"]
                    or self.snapshot.documents[source["generation_id"]] != source["document_id"]):
                integrity_failure()
            version_id = source["version_id"]
            if version_id not in self.versions:
                self.versions[version_id] = dict(self.db.version(version_id))
            version = self.versions[version_id]
            if source.get("format", "pdf") != version["format"]:
                integrity_failure()
            if self.enforce_contract and source["generation_id"] not in self.generations:
                generation = self.db.one("SELECT state,version_id,extraction_revision_id FROM index_generations WHERE id=?",
                                         (source["generation_id"],))
                if (not generation or generation["version_id"] != source["version_id"]
                        or generation["extraction_revision_id"] != source["extraction_revision_id"]):
                    integrity_failure()
                self.generations[source["generation_id"]] = dict(generation)
            for block in source["blocks"]:
                parent, metadata = self.parent(source, block)
                base = {"source_ids": [source["source_id"]], "document_id": source["document_id"],
                        "document_name": version["document_name"],
                        "version_id": source["version_id"], "generation_id": source["generation_id"],
                        "source_file_sha256": version.get("sha256"),
                        "extraction_revision_id": source["extraction_revision_id"]}
                if self.enforce_contract:
                    base.update(index_generation_state=self.generations[source["generation_id"]]["state"],
                                extraction_method=block_extraction_method(parent["metadata_json"]),
                                source_format=version["format"],
                                source_span_complete=block["start_offset"] == 0 and block["end_offset"] == len(parent["text"]))
                    if version["format"] == "pdf":
                        from services.ingestion.source_quality import verified_source_quality
                        from services.ingestion.table_geometry import validate_table_quality

                        quality_key = (source["generation_id"], block["id"])
                        page_key = (source["generation_id"], parent["page_index"])
                        if quality_key not in self.source_qualities:
                            if page_key not in self.page_geometries:
                                page_row = self.db.one("SELECT geometry_json FROM pages WHERE generation_id=? AND page_index=?", page_key)
                                try:
                                    geometry = json.loads(page_row["geometry_json"]) if page_row else None
                                except (TypeError, ValueError):
                                    geometry = None
                                self.page_geometries[page_key] = geometry if isinstance(geometry, dict) else None
                            self.source_qualities[quality_key] = verified_source_quality(
                                parent["text"], metadata.get("metadata", {}), version.get("sha256"), parent["page_index"],
                                page=self.page_geometries[page_key])
                        base.update(source_quality=self.source_qualities[quality_key], source_parent_start=block["start_offset"])
                        nested = metadata.get("metadata", {})
                        if isinstance(nested, dict) and isinstance(nested.get("table_data"), dict):
                            if quality_key not in self.table_qualities:
                                try:
                                    table_bbox = json.loads(parent["bbox_json"]) if parent["bbox_json"] else None
                                except (TypeError, ValueError):
                                    table_bbox = None
                                self.table_qualities[quality_key] = validate_table_quality(
                                    parent["text"], metadata, source_sha256=version.get("sha256"), page_index=parent["page_index"],
                                    page=self.page_geometries[page_key], table_bbox=table_bbox)
                            base["table_quality"] = {"state": "unavailable", "reasons": ["table_relation_scope_unverified"]}
                segment = {"source_id": source["source_id"], "block_id": block["id"],
                           "source_text_hash": block["source_text_hash"], "start_offset": block["start_offset"],
                           "end_offset": block["end_offset"]}
                if source.get("format") != "xlsx":
                    locator = block.get("locator") or {"page_index": block["page_index"]}
                    if self.enforce_contract:
                        if version["format"] == "docx":
                            stored_locator = metadata.get("locator")
                            if (not isinstance(stored_locator, dict) or stored_locator.get("kind") != "docx_element"
                                    or canonical(block.get("locator")) != canonical(stored_locator)):
                                raise ApiError("invalid_source_locator", "Le passage ne possède pas de localisateur documentaire vérifiable.", 409)
                            locator = stored_locator
                        else:
                            # A PDF page is the registered physical page; an
                            # arbitrary locator hint cannot rename its section.
                            locator = {"page_index": parent["page_index"]}
                    key = (source["generation_id"], block["id"], block["start_offset"], block["end_offset"])
                    item = entries.setdefault(key, {**base, "kind": "excerpt", "text": block["text"],
                                                   "locators": [locator], "segments": []})
                    item["segments"].append(segment)
                    if self.enforce_contract:
                        if block.get("table_context"):
                            item["_table_context"] = block["table_context"]
                        if block.get("list_context"):
                            item["_list_context"] = block["list_context"]
                    if source["source_id"] not in item["source_ids"]:
                        item["source_ids"].append(source["source_id"])
                    continue
                locator = metadata.get("locator", {})
                if locator.get("kind") != "xlsx_cells":
                    integrity_failure()
                for binding in metadata.get("bindings", []):
                    low, high = max(block["start_offset"], binding["start"]), min(block["end_offset"], binding["end"])
                    if low >= high or (block.get("field") is not None and block["field"] != binding["field"]):
                        continue
                    cell = self.cell(source["generation_id"], locator["unit_id"], binding)
                    facts = cell_semantics(cell)
                    if not any(canonical(fact) == canonical(facts) for fact in source.get("cell_facts", [])):
                        integrity_failure()
                    cell_key = (source["generation_id"], locator["unit_id"], binding["address"])
                    item = entries.setdefault(cell_key, {**base, "kind": "cell", "cell_facts": facts,
                                                   "locator": {**locator, "cell_range": binding["address"],
                                                               "row_start": binding["row"], "row_end": binding["row"],
                                                               "column_start": binding["column"], "column_end": binding["column"]},
                                                   "fields": [], "_expected": dict(_cell_fields(cell))})
                    if source["source_id"] not in item["source_ids"]:
                        item["source_ids"].append(source["source_id"])
                    field = next((field for field in item["fields"] if field["field"] == binding["field"]), None)
                    if field is None:
                        field = {"field": binding["field"], "text": "", "complete": False, "segments": []}
                        item["fields"].append(field)
                    offset = binding.get("source_start", 0) + low - binding["start"]
                    piece = {**segment, "start_offset": low, "end_offset": high,
                             "source_start": offset, "source_end": offset + high - low,
                             "text": parent["text"][low:high]}
                    field["segments"].append(piece)
        for item in entries.values():
            if item["kind"] != "cell":
                continue
            expected = item.pop("_expected")
            for field in item["fields"]:
                value = expected.get(field["field"])
                if value is None:
                    integrity_failure()
                pieces = sorted(field["segments"], key=lambda piece: (piece["source_start"], piece["source_end"]))
                seen_end = 0
                text = ""
                complete = True
                for piece in pieces:
                    low, high = piece["source_start"], piece["source_end"]
                    if not 0 <= low < high <= len(value) or value[low:high] != piece["text"]:
                        integrity_failure()
                    complete = complete and low <= seen_end
                    if high > seen_end:
                        # Disjoint spans stay visibly disjoint; no hidden intervening characters are fetched.
                        text += (" […] " if low > seen_end and text else "") + value[max(low, seen_end):high]
                    seen_end = max(seen_end, high)
                    piece.pop("text")
                field["text"], field["complete"] = text, complete and seen_end == len(value)
        references = [{"id": f"R{index:03d}", **item} for index, item in enumerate(entries.values(), 1)]
        if self.enforce_contract:
            self.bind_table_context(references)
            self.bind_list_context(references)
            self.bind_prose_subject(references)
        contract_scope = dict(self.snapshot.scope)
        if self.enforce_contract and contract_scope.get("kind") in {"sheet", "cell_range"}:
            # The physical XML filename is not a sheet-order guarantee. Read
            # only the already authorized unit's pinned extraction metadata.
            sheet_id = contract_scope.get("sheetId")
            for generation in self.snapshot.generations:
                row = self.db.one("SELECT id,title,order_index FROM office_units WHERE generation_id=? AND id=?",
                                  (generation, sheet_id))
                if row and type(row["order_index"]) is int:
                    contract_scope["authorized_sheet"] = {"id": row["id"], "name": row["title"], "ordinal": row["order_index"] + 1}
                    break
        contract = AnswerContract(self.question or "", mode, contract_scope,
                                  cell_context=any(reference["kind"] == "cell" for reference in references)) if self.enforce_contract else None
        required_documents = (tuple(dict.fromkeys(self.snapshot.documents.values()))
                              if self.snapshot.scope.get("kind") == "documents" else ())
        return Catalogue(mode, references, contract, required_documents=required_documents)

    def bind_prose_subject(self, references):
        """Bind complete PDF body text to an independently retained page header.

        The DB classification also closes the filename fallback for this route
        when no page authority can be proved. It never converts a table into
        prose or repairs a truncated/unreadable retained paragraph.
        """
        for reference in references:
            if reference["kind"] != "excerpt" or reference.get("source_format") != "pdf":
                continue
            blocks = {segment["block_id"] for segment in reference.get("segments", [])}
            if len(blocks) != 1:
                continue
            block_id = next(iter(blocks))
            parent = self.parents[(reference["generation_id"], block_id)]
            metadata = json.loads(parent["metadata_json"]).get("metadata", {})
            if (parent["kind"] not in {"text", "list_item"} or not isinstance(metadata, dict)
                    or metadata.get("label") not in {"text", "list_item"} or "table_data" in metadata
                    or reference.get("table_context") or reference.get("table_quality")):
                continue
            context: dict[str, Any] = {"schema_version": "pdf-prose-subject-v1", "catalogue_verified": True,
                                      "block_id": block_id, "reference_ids": [], "reference_spans": {}, "source_ids": []}
            binding = prose_page_subject(self.db, self.snapshot, reference, block_id, parent, references)
            if binding is not None:
                header = binding["header"]
                dependency = next(item for item in references if item["id"] == header["reference_id"])
                context.update(page_subject=binding, reference_ids=[dependency["id"]], source_ids=dependency["source_ids"],
                               reference_spans={dependency["id"]: [{"start_offset": header["start_offset"],
                                                                    "end_offset": header["end_offset"]}]})
            reference["prose_context"] = context

    def bind_list_context(self, references):
        """Verify written list structure and bind its exact, visible pieces.

        The heading remains a separate citation. Its nearest geometric
        neighbour alone never qualifies an otherwise unlabelled number.
        """
        cache: dict[tuple, Any] = {}
        for reference in references:
            proposed = reference.pop("_list_context", None)
            if not isinstance(proposed, dict) or not isinstance(proposed.get("item"), dict):
                continue
            expected = verified_list_context(self.db, self.snapshot, reference["generation_id"],
                                             proposed["item"].get("block_id"), _cache=cache)
            if expected is None or canonical(expected) != canonical(proposed):
                continue
            item = expected["item"]
            if reference["text"] != item["text"] or not any(
                    segment["block_id"] == item["block_id"] and segment["source_text_hash"] == item["source_text_hash"]
                    and segment["start_offset"] == item["start_offset"] and segment["end_offset"] == item["end_offset"]
                    for segment in reference.get("segments", [])):
                continue
            scoped = [candidate for candidate in references if candidate["generation_id"] == reference["generation_id"]]

            def covering_ids(piece, scoped=scoped):
                covered = []
                for candidate in scoped:
                    if candidate["extraction_revision_id"] != piece["extraction_revision_id"]:
                        continue
                    for segment in candidate.get("segments", []):
                        if (segment["block_id"] == piece["block_id"] and segment["source_text_hash"] == piece["source_text_hash"]
                                and segment["start_offset"] <= piece["start_offset"] < piece["end_offset"] <= segment["end_offset"]
                                and candidate["text"][piece["start_offset"] - segment["start_offset"]:
                                                      piece["end_offset"] - segment["start_offset"]] == piece["text"]):
                            covered.append(candidate["id"])
                            break
                return covered

            bindings = [covering_ids(piece) for piece in [expected["heading"], item, *expected["dependencies"]]]
            if any(not binding for binding in bindings):
                continue
            ids = list(dict.fromkeys([bindings[0][0], reference["id"], *(binding[0] for binding in bindings[1:])]))
            reference["list_context"] = {**expected, "reference_ids": ids, "catalogue_verified": True,
                "source_ids": list(dict.fromkeys(source for candidate in scoped if candidate["id"] in ids
                                                   for source in candidate["source_ids"]))}
        for reference in references:
            context = reference.get("list_context")
            if not context:
                continue
            visible = {candidate["list_context"]["item_index"] for candidate in references if candidate.get("list_context")
                       and candidate["generation_id"] == reference["generation_id"]
                       and candidate["list_context"]["group_id"] == context["group_id"]}
            context["visible_item_count"] = len(visible)
            context["catalogue_group_complete"] = context["complete"] and visible == set(range(context["item_count"]))

    def bind_table_context(self, references):
        """Rebuild row geometry from pinned DB metadata, then bind visible IDs.

        Source-block metadata is a hint, never authority. Even exact header text
        is insufficient if its coordinates were changed or its span lies outside
        the counted catalogue. The literal remains auditable; unverified PDF
        table associations cannot enter the generator or public value bindings.
        """
        records_cache = {}
        page_subject_cache = {}
        for reference in references:
            proposed = reference.pop("_table_context", None)
            if proposed is None:
                continue
            block_id = proposed.get("table_block_id")
            key = (reference["generation_id"], block_id)
            parent = self.parents.get(key)
            if parent is None:
                continue
            if key not in records_cache:
                records_cache[key] = verified_table_rows(parent["text"], json.loads(parent["metadata_json"]))
            records = records_cache[key]
            if (not records or proposed.get("revision") != "verified-table-relations-v1"
                    or proposed.get("source_text_hash") != parent["source_text_hash"]
                    or proposed.get("extraction_revision_id") != parent["extraction_revision_id"]):
                continue
            record = next((item for item in records if item["index"] == proposed.get("row_index")), None)
            if record is None or not record.get("column_bindings_verified"):
                continue
            if reference["text"] != record["text"] or not any(
                    segment["block_id"] == block_id and segment["source_text_hash"] == parent["source_text_hash"]
                    and segment["start_offset"] == record["start"] and segment["end_offset"] == record["end"]
                    for segment in reference.get("segments", [])):
                continue  # another authorized row's context is not this row's proof
            # Reconstruct only from DB rows; compare geometry/header bindings as
            # well as text to prevent an altered MIN/MAX label from being trusted.
            from .evidence_selection import _table_context
            expected = _table_context(records, record, {"id": block_id, "source_text_hash": parent["source_text_hash"],
                                      "extraction_revision_id": parent["extraction_revision_id"]}, records)
            heading = proposed.get("section_heading")
            if expected is None or canonical(expected) != canonical({key: value for key, value in proposed.items()
                                                                    if key not in {"section_heading", "general_conditions"}}):
                continue
            if reference.get("source_format") == "pdf":
                quality = self.table_qualities.get(key, {"state": "unavailable", "cells": {}, "reasons": ["table_quality_unavailable"]})
                pieces_to_verify = [*expected["cells"], *(header for cell in expected["cells"] for header in cell["headers"])]
                bindings = [quality["cells"].get((cell["row_start"], cell["column_start"])) for cell in pieces_to_verify]
                bindings.extend(quality["cells"].get((dependency["source_row"], dependency["source_column"]))
                                for dependency in quality.get("dependencies", []) if dependency["row_index"] == record["index"])
                supported = quality["state"] != "unavailable" and all(binding and binding["state"] == "supported" for binding in bindings)
                summary = {"state": "supported" if supported else "unavailable",
                           "bindings": list({canonical(binding): binding for binding in bindings if binding}.values()),
                           "reasons": [] if supported else quality.get("reasons", []) or ["table_binding_unverified"]}
                witness = json.loads(parent["metadata_json"]).get("metadata", {}).get("table_quality", {})
                summary.update(policy=witness.get("policy"), observations_sha256=witness.get("observations_sha256"))
                if not supported:
                    reference["table_quality"] = summary
                    continue
                expected["binding_quality"] = summary
            scoped = [item for item in references if item["generation_id"] == reference["generation_id"]]

            def covering_ids(piece, parent=parent, scoped=scoped, block_id=block_id):
                low, high = piece["start_offset"], piece["end_offset"]
                if type(low) is not int or type(high) is not int or not 0 <= low <= high <= len(parent["text"]):
                    return []
                if parent["text"][low:high] != piece["text"]:
                    return []
                return [item["id"] for item in scoped if any(segment["block_id"] == block_id
                        and segment["source_text_hash"] == parent["source_text_hash"]
                        and segment["start_offset"] <= low <= high <= segment["end_offset"]
                        for segment in item.get("segments", []))]

            pieces = [*expected["dependencies"], *expected["cells"],
                      *(header for cell in expected["cells"] for header in cell["headers"])]
            bindings = [covering_ids(piece) for piece in pieces]
            if any(not binding for binding in bindings):
                continue
            ids = list(dict.fromkeys([reference["id"], *(binding[0] for binding in bindings)]))
            reference_spans: dict[str, list[tuple[int, int]]] = {}
            for piece, binding in zip(pieces, bindings, strict=True):
                target = next(item for item in scoped if item["id"] == binding[0])
                segment = next(segment for segment in target["segments"] if segment["block_id"] == block_id
                               and segment["start_offset"] <= piece["start_offset"] <= piece["end_offset"] <= segment["end_offset"])
                low, high = piece["start_offset"] - segment["start_offset"], piece["end_offset"] - segment["start_offset"]
                if low < high:
                    reference_spans.setdefault(target["id"], []).append((low, high))
            if heading:
                sections = self.db.rows(
                    "SELECT b.section_id,s.title,s.block_ids_json,h.id heading_id,h.kind heading_kind,h.section_id heading_section "
                    "FROM blocks b JOIN sections s ON s.generation_id=b.generation_id AND s.id=b.section_id "
                    "JOIN blocks h ON h.generation_id=b.generation_id AND h.section_id=s.id "
                    "WHERE b.generation_id=? AND b.id=? AND h.kind IN ('heading','section_header') AND h.text=s.title LIMIT 2",
                    key)
                section = sections[0] if len(sections) == 1 else None
                heading_parent = self.parents.get((reference["generation_id"], heading.get("block_id")))
                heading_refs = [item for item in scoped if any(segment["block_id"] == heading.get("block_id")
                                and segment["start_offset"] <= heading.get("start_offset", -1)
                                and heading.get("end_offset", -1) <= segment["end_offset"]
                                and segment["source_text_hash"] == heading.get("source_text_hash")
                                for segment in item.get("segments", []))]
                if (not section or not heading_parent or not heading_refs
                        or section["heading_kind"] not in {"heading", "section_header"}
                        or section["section_id"] != heading.get("section_id") or section["heading_section"] != section["section_id"]
                        or heading.get("block_id") != section["heading_id"]
                        or not {block_id, heading["block_id"]} <= set(json.loads(section["block_ids_json"]))
                        or heading.get("start_offset") != 0 or heading.get("end_offset") != len(heading_parent["text"])
                        or heading.get("text") != section["title"] or heading["text"] != heading_parent["text"]
                        or heading.get("source_text_hash") != heading_parent["source_text_hash"]
                        or heading.get("extraction_revision_id") != parent["extraction_revision_id"]):
                    continue
                expected["section_heading"] = heading
                ids = list(dict.fromkeys([*ids, heading_refs[0]["id"]]))
            if reference.get("source_format") == "pdf":
                from .table_conditions import table_conditions_bundle

                _, annotation, _ = table_conditions_bundle(
                    self.db, self.snapshot, reference, {"id": block_id, "page_index": parent["page_index"],
                                                       "extraction_revision_id": parent["extraction_revision_id"]}, parent)
                if annotation is not None:
                    bound_pieces: list[dict[str, Any]] = []
                    general_ids: list[str] = []
                    general_spans: dict[str, list[tuple[int, int]]] = {}
                    condition_fragments = table_general_condition_fragments(annotation)
                    for piece in condition_fragments:
                        piece_parent = self.parents.get((reference["generation_id"], piece["block_id"]))
                        low, high = piece["start_offset"], piece["end_offset"]
                        candidates = [item for item in scoped if item["kind"] == "excerpt" and any(
                            segment["block_id"] == piece["block_id"] and segment["source_text_hash"] == piece["source_text_hash"]
                            and segment["start_offset"] <= low < high <= segment["end_offset"] for segment in item.get("segments", []))]
                        candidates.sort(key=lambda item: (len(item["text"]), item["id"]))
                        if (piece_parent is None or not candidates or piece_parent["source_text_hash"] != piece["source_text_hash"]
                                or piece_parent["extraction_revision_id"] != parent["extraction_revision_id"]
                                or piece_parent["text"][low:high] != piece["text"]):
                            break
                        target = candidates[0]
                        segment = next(segment for segment in target["segments"] if segment["block_id"] == piece["block_id"]
                                       and segment["start_offset"] <= low < high <= segment["end_offset"])
                        start, end = low - segment["start_offset"], high - segment["start_offset"]
                        checked_quality = reference_span_quality(target, start, end)
                        if checked_quality is None or checked_quality["state"] not in {"native", "corroborated"}:
                            break
                        bound_pieces.append({"kind": "general_condition", **piece})
                        general_ids.append(target["id"])
                        general_spans.setdefault(target["id"], []).append((start, end))
                    complete = annotation["state"] == "supported" and bool(bound_pieces) and len(bound_pieces) == len(condition_fragments)
                    expected["general_conditions"] = ({**annotation, "reference_ids": list(dict.fromkeys(general_ids))}
                                                      if complete else {"state": "unavailable", "pieces": [],
                                                                        "reasons": ["general_conditions_not_retained_or_unverified"]})
                    if complete:
                        expected["dependencies"].extend(bound_pieces)
                        ids = list(dict.fromkeys([*ids, *general_ids]))
                        for ref, spans in general_spans.items():
                            reference_spans.setdefault(ref, []).extend(spans)
                if key not in page_subject_cache:
                    page_subject_cache[key] = table_page_subject(
                        self.db, self.snapshot, reference, block_id, parent, scoped)
                page_subject = page_subject_cache[key]
                if page_subject_applies(page_subject, reference, expected):
                    expected["page_subject"] = page_subject
                    subject_header = page_subject["header"]
                    subject_ref = subject_header["reference_id"]
                    ids = list(dict.fromkeys([*ids, subject_ref]))
                    reference_spans.setdefault(subject_ref, []).append((0, subject_header["end_offset"]))
            expected["reference_ids"] = ids
            by_id = {item["id"]: item for item in scoped}
            expected["reference_spans"] = {ref: merged_spans(spans, by_id[ref]["text"]) for ref, spans in reference_spans.items()}
            expected["source_ids"] = list(dict.fromkeys(source_id for item in scoped if item["id"] in ids for source_id in item["source_ids"]))
            expected["catalogue_verified"] = True
            if "binding_quality" in expected:
                reference["table_quality"] = expected["binding_quality"]
            reference["table_context"] = expected
