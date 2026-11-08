"""Reference-only generation and restitution of revision-pinned documentary facts."""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError

from services.ingestion.office.xlsx import _cell_fields, address_coordinates

from .answer_contract import PROPERTY_LABELS, AnswerContract, assessment_message, folded
from .deterministic_calculations import calculation_text
from .errors import ApiError
from .evidence_selection import verified_table_rows
from .office import cell_semantics
from .scope import block_extraction_method

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

    def as_dict(self):
        value: dict[str, Any] = {"version": 1, "mode": self.mode, "references": self.references}
        if self.contract is not None:
            value["question_contract"] = self.contract.prompt(self.references)
        return value

    def schema(self):
        ids = [reference["id"] for reference in self.references]
        reference = {"type": "string", "enum": ids}
        # No additional prose or model-produced values are accepted, even in mixed-format scopes.
        return {"type": "object", "additionalProperties": False, "required": ["references", "comparisons"],
                "properties": {
                    "references": {"type": "array", "items": reference, "maxItems": len(ids)},
                    "comparisons": {"type": "array", "maxItems": len(ids), "items": {
                        "type": "object", "additionalProperties": False, "required": ["references"],
                        "properties": {"references": {"type": "array", "items": reference,
                                                        "minItems": 2, "maxItems": 4}}}}}}

    def prompt(self):
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
        return canonical(payload)

    def assess(self, selected_ids=None, required_documents=()):
        """Passive context/selection diagnosis; no retrieval and no model call."""
        if self.contract is None:
            return {"status": "disabled", "verification": "not_requested"}
        return self.contract.assess(self.references, selected_ids, required_documents)

    def evidence(self):
        schema, catalogue = self.schema(), self.as_dict()
        result = {"schema": schema, "catalogue": catalogue,
                  "schema_sha256": digest(schema), "catalogue_sha256": digest(catalogue), "mode": self.mode}
        if self.contract is not None:
            ledger = self.support_ledger()
            result.update(support_ledger=ledger, support_ledger_sha256=digest(ledger))
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
                "extraction_revision_id", "source_file_sha256", "source_ids", "extraction_method", "index_generation_state")}
            item["locators"] = reference.get("locators") or ([reference["locator"]] if reference.get("locator") else [])
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
                "references": references, "relations": assessment.get("matched_relations", []),
                "rejected_relations": assessment.get("rejected_relations", []),
                "conflicts": assessment.get("conflicts", [])}

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
        required = self.contract.required_ids(self.references, required_documents)
        added = [reference for reference in required if reference not in plan.references]
        # One bounded completion using only references already included in the
        # counted prompt. Exact cell requests and a unique local quantity proof
        # must not disappear merely because the model omitted their IDs.
        selected_ids = [] if self.contract.scope_refusal() else list(dict.fromkeys([*required, *plan.references]))
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
        for reference_id in selected_ids:
            # The operation already reproduces its exact input values, labels
            # and source citations; avoid repeating a whole cell paragraph.
            if reference_id in represented:
                continue
            reference = by_id[reference_id]
            context = reference.get("table_context") or {}
            bundle = [item for item in context.get("reference_ids", []) if item in selected_ids]
            bundle = list(dict.fromkeys([*bundle, reference_id]))
            parts.append({"text": "\n".join(render_reference(by_id[item], include_document=True) for item in bundle),
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
                               "omitted_reference_ids": omitted, "rendered_reference_ids": displayed})
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
            selected = ([] if self.contract.scope_refusal() else list(dict.fromkeys([
                *self.contract.required_ids(self.references, required_documents), *assessment["model_selected_reference_ids"]])))
            if set(selected) - by_id.keys():
                raise ValueError("unknown initial reference")
            omitted = [reference_id for reference_id in selected if reference_id not in displayed]
            initial = self.assess(selected, required_documents)
            expected_status = (initial["status"] if initial["status"] in {"conflict", "ambiguous"}
                               else "partial" if omitted else checked["status"])
            if (assessment["status"] != expected_status or assessment["omitted_reference_ids"] != omitted
                    or assessment["rendered_reference_ids"] != displayed):
                raise ValueError("coverage changed after rendering")
            for field in ("matched_relations", "comparisons", "conflicts"):
                if canonical(assessment.get(field, [])) != canonical(checked.get(field, [])):
                    raise ValueError("unsupported relation or comparison")
            for field in ("kind", "quantity", "missing", "scope_refusal", "rejected_relations"):
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
                        expected = "\n".join(render_reference(by_id[reference_id], include_document=True) for reference_id in refs)
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
        General prose, scope-wide discovery, incomplete relations and ambiguous
        cells keep the reference-selection route. Source identities have already
        been checked by the builder; completeness is rechecked after rendering.
        """
        contract = self.contract
        if contract is not None and contract.scope_refusal():
            return AnswerPlan(references=[], comparisons=[])
        if (contract is not None and not contract.parse_failures
                and (contract.kind in {"value", "interval", "comparison"} and contract.quantity is not None
                     or contract.kind == "mapping" and bool(contract.configurations))):
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


def render_reference(reference, include_document=False):
    heading = f"{quoted(reference['document_name'])} — " if include_document else ""
    if reference["kind"] == "excerpt":
        text = heading + "Extrait : « " + quoted(reference["text"]) + " »"
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

    def parent(self, source, block):
        generation = source["generation_id"]
        if (generation not in self.snapshot.generations
                or source["version_id"] != self.snapshot.versions[generation]
                or source["document_id"] != self.snapshot.documents[generation]):
            integrity_failure()
        key = (generation, block["id"])
        if key not in self.parents:
            row = self.db.one("SELECT text,page_index,source_text_hash,extraction_revision_id,metadata_json FROM blocks WHERE generation_id=? AND id=?", key)
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
                                extraction_method=block_extraction_method(parent["metadata_json"]))
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
        return Catalogue(mode, references, contract)

    def bind_table_context(self, references):
        """Rebuild row geometry from pinned DB metadata, then bind visible IDs.

        Source-block metadata is a hint, never authority. Even exact header text
        is insufficient if its coordinates were changed or its span lies outside
        the counted catalogue. In that case only the literal excerpt survives.
        """
        records_cache = {}
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
            if expected is None or canonical(expected) != canonical({key: value for key, value in proposed.items() if key != "section_heading"}):
                continue
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
            expected["reference_ids"] = ids
            expected["source_ids"] = list(dict.fromkeys(source_id for item in scoped if item["id"] in ids for source_id in item["source_ids"]))
            expected["catalogue_verified"] = True
            reference["table_context"] = expected
