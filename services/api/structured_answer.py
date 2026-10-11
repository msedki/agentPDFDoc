"""Reference-only generation and restitution of revision-pinned documentary facts."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from services.ingestion.office.xlsx import _cell_fields, address_coordinates

from .errors import ApiError
from .office import cell_semantics

STRUCTURED_INSTRUCTION = (
    "\nRestitution structurée : produis uniquement le plan JSON demandé, avec references et comparisons. "
    "Choisis les références Rxxx utiles à la question parmi le catalogue fourni. "
    "references contient les faits ou extraits à restituer ; comparisons contient des groupes de deux à quatre "
    "références à rapprocher. Traite séparément les documents demandés. "
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


@dataclass
class Catalogue:
    mode: str
    references: list[dict[str, Any]]

    def as_dict(self):
        return {"version": 1, "mode": self.mode, "references": self.references}

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
        return canonical({"reference_catalogue": items})

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
            if len(selected) > len(ids) or len(selected) != len(set(selected)) or set(selected) - ids:
                raise ValueError("invalid selection")
            if len(plan.comparisons) > len(ids):
                raise ValueError("too many comparisons")
            groups = []
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


def quoted(text):
    # React renders source text literally. Only renderer-generated spans designate citations.
    return str(text)


def render_reference(reference, include_document=False):
    heading = f"{quoted(reference['document_name'])} — " if include_document else ""
    if reference["kind"] == "excerpt":
        return heading + "Extrait : « " + quoted(reference["text"]) + " »"
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
    def __init__(self, db, snapshot):
        self.db, self.snapshot = db, snapshot
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
            row = self.db.one("SELECT text,source_text_hash,extraction_revision_id,metadata_json FROM blocks WHERE generation_id=? AND id=?", key)
            if not row:
                integrity_failure()
            self.parents[key] = dict(row)
        parent = self.parents[key]
        start, end = block["start_offset"], block["end_offset"]
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(parent["text"])
                or parent["source_text_hash"] != block["source_text_hash"]
                or hashlib.sha256(parent["text"].encode()).hexdigest() != block["source_text_hash"]
                or parent["extraction_revision_id"] != block["extraction_revision_id"]
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

    def catalogue(self, sources, mode):
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
        return Catalogue(mode, references)
