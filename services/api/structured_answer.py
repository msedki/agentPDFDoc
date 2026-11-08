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
        return {"schema": schema, "catalogue": catalogue,
                "schema_sha256": digest(schema), "catalogue_sha256": digest(catalogue), "mode": self.mode}

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
            message = assessment_message(assessment)
            if message:
                answer = message
            for part in parts:
                answer += ("\n\n" if answer else "") + part["text"]
                for source_id in part["source_ids"]:
                    answer += " "
                    start = len(answer)
                    answer += f"[{source_id}]"
                    spans.append({"source_id": source_id, "start_offset": start, "end_offset": len(answer)})
            for comparison in assessment.get("comparisons", []):
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
                answer += ("\n\n" if answer else "") + f"Comparaison — {label} ({names}) : {conclusion}."
                for source_id in dict.fromkeys(source for reference_id in comparison["reference_ids"]
                                              for source in by_id[reference_id]["source_ids"]):
                    answer += " "
                    start = len(answer)
                    answer += f"[{source_id}]"
                    spans.append({"source_id": source_id, "start_offset": start, "end_offset": len(answer)})
            for condition in (fact for fact in assessment.get("matched_relations", []) if fact["kind"] == "test_condition"):
                answer += ("\n\n" if answer else "") + (f"Condition d'essai de {condition['label']} : {condition['condition']}. "
                    "Le lien vérifié porte sur la colonne des conditions d'essai ; cette condition ne définit pas à elle seule une limite de la grandeur mesurée.")
                for source_id in condition["source_ids"]:
                    answer += " "
                    start = len(answer)
                    answer += f"[{source_id}]"
                    spans.append({"source_id": source_id, "start_offset": start, "end_offset": len(answer)})
            for limitation in (fact for fact in assessment.get("matched_relations", []) if fact["kind"] == "operating_guarantee_limitation"):
                answer += ("\n\n" if answer else "") + "La source précise que les limites absolues ne garantissent pas le fonctionnement normal."
                for source_id in limitation["source_ids"]:
                    answer += " "
                    start = len(answer)
                    answer += f"[{source_id}]"
                    spans.append({"source_id": source_id, "start_offset": start, "end_offset": len(answer)})
            if assessment.get("comparisons"):
                answer += " La concordance éventuelle des valeurs n'établit pas l'indépendance des documents."
            if omitted:
                answer += ("\n\n" if answer else "") + "Restitution limitée par le budget de réponse : certaines références entières ne sont pas affichées."
            if not answer:
                answer = "Aucune référence sélectionnée dans les preuves retenues ne permet de répondre à la demande."
            return answer, spans

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
            answer, spans = compose(candidate_parts, assessment, omitted)
            tokens = tokenizer.count(answer)
            return displayed, omitted, assessment, answer, spans, tokens

        # Admit whole references in stable priority order. An oversized first
        # excerpt must not erase later useful excerpts that fit. Evaluate all
        # first: intermediate partial-coverage notices can cost more than the
        # complete answer's notice. Never truncate a fact/condition/calculation.
        displayed, omitted, assessment, answer, spans, tokens = evaluate(parts)
        if tokens > output_tokens:
            admitted: list[dict[str, Any]] = []
            for part in parts:
                candidate = [*admitted, part]
                if evaluate(candidate)[-1] <= output_tokens:
                    admitted.append(part)
            parts = admitted
            displayed, omitted, assessment, answer, spans, tokens = evaluate(parts)
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
        return {"text": answer, "source_ids": list(dict.fromkeys(source for part in parts for source in part["source_ids"])),
                "warnings": warnings, "tokens": tokens, "citation_spans": spans,
                "answer_contract": assessment, "effective_plan": effective_plan}

    def deterministic_plan(self) -> AnswerPlan | None:
        """Exact, explicitly named cells in a pinned range need no model choice.

        Expected deterministic refusals (missing formula cache, division by
        zero, unavailable unit) still render their actual reason and sources.
        General properties, scope-wide discovery and ambiguous cells do not use
        this path. The existing builder has already checked source identities.
        """
        contract = self.contract
        if contract is not None and contract.scope_refusal():
            return AnswerPlan(references=[], comparisons=[])
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
            version_id = source["version_id"]
            if version_id not in self.versions:
                self.versions[version_id] = dict(self.db.version(version_id))
            version = self.versions[version_id]
            if source.get("format", "pdf") != version["format"]:
                integrity_failure()
            for block in source["blocks"]:
                parent, metadata = self.parent(source, block)
                base = {"source_ids": [source["source_id"]], "document_id": source["document_id"],
                        "document_name": version["document_name"],
                        "version_id": source["version_id"], "generation_id": source["generation_id"],
                        "extraction_revision_id": source["extraction_revision_id"]}
                segment = {"source_id": source["source_id"], "block_id": block["id"],
                           "source_text_hash": block["source_text_hash"], "start_offset": block["start_offset"],
                           "end_offset": block["end_offset"]}
                if source.get("format") != "xlsx":
                    key = (source["generation_id"], block["id"], block["start_offset"], block["end_offset"])
                    item = entries.setdefault(key, {**base, "kind": "excerpt", "text": block["text"],
                                                   "locators": [block.get("locator") or {"page_index": block["page_index"]}], "segments": []})
                    item["segments"].append(segment)
                    if self.enforce_contract:
                        item["extraction_method"] = block.get("extraction_method", "unknown")
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
