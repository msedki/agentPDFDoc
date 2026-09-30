"""Public synthetic facts and split-specific annotations; no business data or runtime calls."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

CATEGORY_QUOTAS = {"factual_fr_en": 35, "technical_identifiers": 15, "tables_units": 12, "comparison": 10, "conversation_followup": 8, "unanswerable_in_scope": 20}
DATASET_VERSION = "qualification-v2.1-synthetic-1"


@dataclass(frozen=True)
class Record:
    split: str
    index: int
    family: str
    document_key: str
    name: str
    identifier: str
    neighbour: str
    subject: str
    facts: tuple[tuple[str, str, str, str, str], ...]
    rows: tuple[tuple[str, str, str], ...]

    @property
    def paragraphs(self) -> list[str]:
        return [f"{self.identifier} — {self.subject}."] + [fact[3] for fact in self.facts] + [f"La référence proche {self.neighbour} appartient à un autre équipement ; ses valeurs ne sont pas celles de {self.identifier}."]


def records(split: str) -> list[Record]:
    output = []
    for index in range(1, 8):
        if split == "development":
            identifier = f"DA-P{index:02d}"
            subject = f"banc pneumatique synthétique Atelier {index}"
            facts = (
                ("pressure", f"{3 + index / 10:.1f}", "bar", f"La pression nominale de {identifier} est de {3 + index / 10:.1f} bar.", "pression nominale"),
                ("tolerance", f"{index + 1:.1f}", "%", f"La tolérance de pression de {identifier} est de ± {index + 1:.1f} %.", "tolérance de pression"),
                ("interval", str(900 + index * 120), "h", f"Le contrôle périodique de {identifier} intervient toutes les {900 + index * 120} h.", "intervalle de contrôle"),
                ("torque", str(10 + index * 2), "N·m", f"Le couple de serrage prescrit pour {identifier} est de {10 + index * 2} N·m.", "couple de serrage"),
                ("voltage", str(20 + index * 2), "V", f"L'alimentation d'essai de {identifier} est de {20 + index * 2} V.", "tension d'alimentation"),
            )
            rows = ((f"{identifier}-IN", str(12 + index), "mm"), (f"{identifier}-OUT", str(8 + index), "mm"), (f"{identifier}-LEAK", f"{index / 10:.1f}", "L/min"))
            family = "development-pneumatic-ateliers"
            name = f"Atelier {index} - Banc pneumatique {identifier}.pdf"
        elif split == "final":
            identifier = f"FT-C{index:02d}"
            subject = f"circuit thermique synthétique station Boréal {index}"
            facts = (
                ("temperature", str(62 + index * 3), "°C", f"La température de consigne de {identifier} est de {62 + index * 3} °C.", "température de consigne"),
                ("tolerance", f"{0.4 + index / 10:.1f}", "°C", f"La tolérance thermique de {identifier} est de ± {0.4 + index / 10:.1f} °C.", "tolérance thermique"),
                ("flow", str(18 + index * 3), "L/min", f"Le débit de circulation de {identifier} est de {18 + index * 3} L/min.", "débit de circulation"),
                ("resistance", str(40 + index * 4), "ohm", f"La résistance du capteur de {identifier} est de {40 + index * 4} ohm.", "résistance du capteur"),
                ("hold", str(15 + index * 5), "min", f"Le palier de stabilisation de {identifier} dure {15 + index * 5} min.", "durée du palier"),
            )
            rows = ((f"{identifier}-HOT", str(9 + index), "mm"), (f"{identifier}-COLD", str(14 + index), "mm"), (f"{identifier}-LOSS", f"{1.2 + index / 10:.1f}", "kPa"))
            family = "final-thermal-boreal"
            name = f"Station Boréal {index} - Circuit {identifier}.pdf"
        else:
            raise ValueError(split)
        output.append(Record(split, index, family, f"{split}-{identifier}", name, identifier, f"{identifier}0", subject, facts, rows))
    return output


def document_descriptor(record: Record) -> dict:
    kind = {2: "image_only_scan", 3: "native_paragraph_scanned_table", 4: "native_two_columns_table"}.get(record.index, "native_text_table")
    return {"key": record.document_key, "split": record.split, "family": record.family, "path": f"qualification-v2.1/{record.split}/Procédures/{record.name}", "type": kind, "license": "CC0-1.0 project-authored synthetic text", "expected_pages": 2, "synthetic": True, "version_id": None, "extraction_revision_id": None}


def unit(record: Record, page: int, required_texts: list[str], role: str = "answer") -> dict:
    return {"document_key": record.document_key, "file_sha256": None, "version_id": None, "extraction_revision_id": None, "page_index": page, "required_texts": required_texts, "role": role, "alternatives": [], "resolved_spans": None, "resolution_status": "NOT_RESOLVED"}


def build_questions(split: str) -> list[dict]:
    documents = records(split)
    questions: list[dict] = []
    prefix = "DEV" if split == "development" else "FINAL"

    def append(category: str, text: str, scope_documents: list[Record], expected: str | None, units: list[dict], values: list[dict] | None = None, language: str = "fr", **extra):
        questions.append({"id": f"{prefix}-{len(questions) + 1:03d}", "split": split, "family": scope_documents[0].family, "category": category, "language": language, "question": text, "scope_template": {"kind": "documents", "document_keys": [record.document_key for record in scope_documents]}, "scope_resolved": None, "answerable": expected is not None, "expected_answer": expected, "important_values": values or [], "expected_units": units, "completeness": "All expected units and important values with their units must be present; no fact from outside scope.", "annotation_state": "SOURCE_TEMPLATE_NOT_RESOLVED", "synthetic": True, **extra})

    factual_ids: dict[tuple[int, int], str] = {}
    for record in documents:
        for fact_index, (key, value, measurement_unit, sentence, label) in enumerate(record.facts):
            ordinal = (record.index - 1) * 5 + fact_index
            french = ordinal % 2 == (0 if split == "development" else 1)
            if french:
                question = f"Quelle est la {label} indiquée pour {record.identifier} ?" if split == "development" else f"À la station Boréal {record.index}, quelle {label} appliquer au circuit {record.identifier} ?"
            else:
                english_labels = {"pressure": "nominal pressure", "tolerance": "allowed tolerance", "interval": "inspection interval", "torque": "tightening torque", "voltage": "test supply voltage", "temperature": "temperature setpoint", "flow": "circulation flow rate", "resistance": "sensor resistance", "hold": "stabilization hold duration"}
                question = f"What is the {english_labels[key]} specified for {record.identifier}?" if split == "development" else f"For the Boréal thermal circuit {record.identifier}, report its {english_labels[key]} and measurement unit."
            append("factual_fr_en", question, [record], sentence, [unit(record, 0, [sentence])], [{"key": key, "value": value, "unit": measurement_unit}], "fr" if french else "en")
            factual_ids[(record.index, fact_index)] = questions[-1]["id"]

    for index in range(15):
        record = documents[index % 7]
        fact = record.facts[(index // 7) % 5]
        if split == "development":
            text = f"Pour la référence exacte {record.identifier}, et non {record.neighbour}, donnez {fact[4]} avec son unité."
        else:
            text = f"Le code de circuit demandé est {record.identifier} ; vérifiez ce code puis restituez {fact[4]}, sans reprendre une valeur d'un code voisin."
        append("technical_identifiers", text, [record], fact[3], [unit(record, 0, [fact[3]])], [{"key": fact[0], "value": fact[1], "unit": fact[2]}], required_identifiers=[record.identifier], forbidden_identifiers=[record.neighbour], tags=["near_identifier", "identifier_in_final_context"])

    for index in range(12):
        record = documents[index % 7]
        row = record.rows[index % 3]
        text = f"Dans le tableau de contrôle de {record.identifier}, quelle valeur et quelle unité correspondent à {row[0]} ?" if split == "development" else f"Relevez la mesure de la ligne {row[0]} du tableau du circuit {record.identifier}, en conservant l'unité de cette ligne."
        table_unit = unit(record, 1, [row[0], row[1], row[2]])
        table_unit["required_row"] = {"identifier": row[0], "value": row[1], "unit": row[2], "headers": ["Référence", "Valeur", "Unité"]}
        append("tables_units", text, [record], f"{row[0]} : {row[1]} {row[2]}", [table_unit], [{"key": row[0], "value": row[1], "unit": row[2]}], tags=["table_header", "unit_required"])

    pairs = [(0, 1), (1, 3), (2, 6), (3, 4), (4, 6), (0, 5), (2, 4), (1, 5), (0, 6), (3, 5)]
    for index, (left, right) in enumerate(pairs):
        first, second = documents[left], documents[right]
        fact_index = index % 5
        a, b = first.facts[fact_index], second.facts[fact_index]
        text = f"Comparez {a[4]} entre {first.identifier} et {second.identifier} ; donnez les deux valeurs et leurs unités." if split == "development" else f"Quels réglages de {a[4]} distinguent les circuits thermiques {first.identifier} et {second.identifier} ? Appuyez chaque valeur sur son document."
        append("comparison", text, [first, second], f"{first.identifier}: {a[1]} {a[2]}; {second.identifier}: {b[1]} {b[2]}.", [unit(first, 0, [a[3]], "first_document"), unit(second, 0, [b[3]], "second_document")], [{"key": first.identifier, "value": a[1], "unit": a[2]}, {"key": second.identifier, "value": b[1], "unit": b[2]}], mode="comparison", tags=["balanced_documents", "multi_evidence"])

    for index in range(8):
        record = documents[index % 7]
        reference_fact = 0 if index < 7 else 2
        target = record.facts[1] if index < 7 else record.facts[4]
        text = "Et quelle est sa tolérance de pression ?" if split == "development" and index < 7 else "What tolerance applies to that thermal circuit?" if index < 7 else "Et quelle est sa tension d'alimentation d'essai ?" if split == "development" else "For that same circuit, how long must the stabilization hold last?"
        append("conversation_followup", text, [record], target[3], [unit(record, 0, [target[3]])], [{"key": target[0], "value": target[1], "unit": target[2]}], "fr" if split == "development" else "en", followup_of_question_id=factual_ids[(record.index, reference_fact)], prior_user_question=next(question["question"] for question in questions if question["id"] == factual_ids[(record.index, reference_fact)]), referent={"kind": "identifier", "identifier": record.identifier}, tags=["user_referent", "no_model_answer_as_evidence"])

    missing_development = ["nom du fabricant", "année de mise en service", "adresse de l'atelier", "numéro de série", "masse de l'équipement", "puissance absorbée", "indice de protection IP", "date du dernier contrôle", "nom de l'opérateur", "couleur du câble de terre", "référence du logiciel", "fréquence électrique", "longueur du câble", "volume du réservoir", "matière du joint", "mode de transport", "prix d'achat", "état de stock", "résultat du dernier essai", "date de garantie"]
    missing_final = ["coolant brand", "factory location", "installation year", "calibration certificate number", "assembly mass", "rated electrical power", "sensor supplier", "last maintenance date", "responsible technician name", "connector pin assignment", "controller firmware release", "coolant chemical composition", "pipe length", "thermal insulation material", "pumping station serial number", "shipping instructions", "purchase contract amount", "warehouse stock", "alarm history", "warranty expiry date"]
    for index in range(20):
        record = documents[index % 7]
        missing = missing_development[index] if split == "development" else missing_final[index]
        text = f"Quel est le {missing} de {record.identifier}, dans le document sélectionné ?" if split == "development" else f"Does the selected {record.identifier} procedure specify its {missing}? If it does not, say the supplied evidence is insufficient."
        append("unanswerable_in_scope", text, [record], None, [], language="fr" if split == "development" else "en", absence_reason=f"The controlled source contains no {missing}; absence reviewed against all generated source text for this document.", tags=["expected_abstention", "scope_documents"])
    return questions


def dataset() -> dict:
    questions = build_questions("development") + build_questions("final")
    return {"schema_version": 1, "dataset_version": DATASET_VERSION, "status": "GENERATED_SOURCE_TEMPLATES_NOT_RUNTIME_QUALIFIED", "purpose": "Engineering qualification on project-authored synthetic documents; not industrial quality.", "license": "CC0-1.0", "split_policy": "Disjoint documentary families: pneumatic workshops for development; thermal circuits for final. Final questions must not be used for tuning.", "final_expected_denominators": {"answerable_questions": 80, "unanswerable_questions": 20}, "category_quotas_per_split": CATEGORY_QUOTAS, "questions": questions}


def frozen_digest(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
