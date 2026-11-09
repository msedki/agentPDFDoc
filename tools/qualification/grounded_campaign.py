"""Rejeu contrôlé apparié : Office, SQLite, FTS et QueryService réels.

Le transport vectoriel, les embeddings et le sélecteur de références sont des
doubles nommés. Le compteur de caractères par défaut n'est pas un tokenizer.
Ce harnais ne mesure ni un modèle 4B, ni la qualité sémantique générale du RAG.
Il vérifie des oracles littéraux gelés et conserve chaque erreur/refus au
dénominateur. Une révision applicative est importée par processus.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import importlib
import io
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import threading
import time
import zipfile
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid5
from xml.etree import ElementTree

FIXTURE_TIME = datetime(2026, 11, 8, 0, 0, 0)
LIMIT_NOTICE = re.compile(
    r"insuffis|ne suffi|ne permet|ne peux pas|ne peut pas|n['’]est pas (?:entièrement )?établi"
    r"|ne sont pas établ|aucune référence|aucune preuve|hors (?:du )?périmètre|en dehors"
    r"|ambigu|pas accessible|pas disponible|indisponible|sans cache|couverture.*partiel"
    r"|périmètre sélectionné autorise seulement|élargissez la sélection"
    r"|n['’]établ(?:it|issent) pas|n['’]est pas retenu(?:e)? comme (?:valeur|donnée) affirmée",
    re.IGNORECASE,
)


def digest_file(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def load_fixture(path: Path) -> dict[str, Any]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    if fixture.get("schema_version") != 1 or not isinstance(fixture.get("cases"), list):
        raise ValueError("Format de matrice inconnu")
    ids = [case["id"] for case in fixture["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Identifiant de cas dupliqué")
    for case in fixture["cases"]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", case["id"]):
            raise ValueError("Identifiant de cas invalide")
        keys = [document["key"] for document in case["documents"]]
        if len(keys) != len(set(keys)):
            raise ValueError("Identifiant de document dupliqué")
        patterns = [*case.get("required_answer_patterns", []), *case.get("forbidden_answer_patterns", [])]
        for fact in case.get("facts", []):
            if fact["document"] not in keys:
                raise ValueError("Fait sans document de référence")
            patterns += [*fact["source_patterns"], *fact["answer_patterns"]]
        for pattern in patterns:
            re.compile(pattern)
    return fixture


def load_application(root: Path) -> SimpleNamespace:
    root = root.resolve(strict=True)
    if any(name == "services" or name.startswith("services.") for name in sys.modules):
        raise RuntimeError("Une application est déjà importée dans ce processus")
    sys.path.insert(0, str(root))
    exports = {
        "db": ("Database",), "settings": ("Settings",), "indexing": ("Indexer",),
        "retrieval": ("SearchService",), "scope": ("ScopeResolver",),
        "context": ("ContextBuilder", "LlmTokenizer"), "query": ("QueryService",),
        "schemas": ("Scope", "QueryRequest"), "execution_trace": ("read_verified_trace",),
    }
    members = {}
    for module, names in exports.items():
        loaded = importlib.import_module("services.api." + module)
        members.update({name: getattr(loaded, name) for name in names})
    office = importlib.import_module("services.ingestion.office.pipeline")
    members.update(extract_office=office.extract_office, office_content_hash=office.office_content_hash)
    for name, loaded in sys.modules.items():
        filename = getattr(loaded, "__file__", None)
        if name.startswith("services.") and filename and not Path(filename).resolve().is_relative_to(root):
            raise RuntimeError("Import applicatif provenant d'une autre révision : " + name)
    return SimpleNamespace(**members)


def canonical_office_bytes(payload: bytes, formula_cache: dict[str, str] | None = None) -> bytes:
    """Fixer les dates ZIP/propriétés, sans changer le contenu documentaire.

    Le cache synthétique est explicite : openpyxl n'évalue aucune formule.
    Le même JSON doit produire les mêmes octets dans les deux bras.
    """
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(payload)) as source, zipfile.ZipFile(output, "w") as target:
        for name in sorted(source.namelist()):
            content = source.read(name)
            if name == "docProps/core.xml":
                content = re.sub(
                    rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:(?:created|modified)>)",
                    rb"\g<1>2026-11-08T00:00:00Z\2", content,
                )
            if name == "xl/worksheets/sheet1.xml" and formula_cache:
                tree = ElementTree.fromstring(content)
                namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                for cell in tree.iter(namespace + "c"):
                    address = cell.attrib.get("r")
                    if address in formula_cache:
                        if cell.find(namespace + "f") is None:
                            raise ValueError("Le cache demandé ne correspond pas à une formule")
                        value = cell.find(namespace + "v")
                        if value is None:
                            value = ElementTree.SubElement(cell, namespace + "v")
                        value.text = formula_cache[address]
                content = ElementTree.tostring(tree, encoding="utf-8")
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 8, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            target.writestr(info, content)
    return output.getvalue()


def generate_document(spec: dict[str, Any], destination: Path) -> str:
    """Créer un vrai DOCX/XLSX synthétique; retourne le hash de l'original."""
    output = io.BytesIO()
    if spec["format"] == "docx":
        from docx import Document

        document = Document()
        document.core_properties.created = FIXTURE_TIME
        document.core_properties.modified = FIXTURE_TIME
        for paragraph in spec.get("paragraphs", []):
            document.add_paragraph(paragraph)
        for rows in spec.get("tables", []):
            table = document.add_table(rows=len(rows), cols=max(map(len, rows)))
            for row_index, row in enumerate(rows):
                for column, value in enumerate(row):
                    table.cell(row_index, column).text = str(value)
        document.save(output)
    elif spec["format"] == "xlsx":
        from openpyxl import Workbook

        workbook = Workbook()
        workbook.remove(workbook.active)
        workbook.properties.created = FIXTURE_TIME
        workbook.properties.modified = FIXTURE_TIME
        for sheet in spec["sheets"]:
            worksheet = workbook.create_sheet(sheet["name"])
            for address, value in sheet["cells"].items():
                worksheet[address] = value
        workbook.save(output)
        workbook.close()
    else:
        raise ValueError("Format de fixture non pris en charge")
    payload = canonical_office_bytes(output.getvalue(), spec.get("formula_cache"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(payload)
    return hashlib.sha256(payload).hexdigest()


class CharacterCounterDouble:
    """Double fixe, non qualifié comme compte de tokens du modèle."""

    def count(self, text):
        return len(text) // 4 + 1

    def count_messages(self, messages):
        return sum(self.count(message["content"]) + 5 for message in messages)


class ConstantEmbeddingDouble:
    def count(self, text, passage=True):
        return len(text) // 4 + 3

    def embed(self, texts, passage=True):
        return [[1.0] + [0.0] * 383 for _ in texts]


class LexicalOnlyVectorDouble:
    """Stockage de points pour les contrats d'index; branche dense vide."""

    def __init__(self):
        self.points: dict[str, dict] = {}

    async def ensure_collection(self):
        pass

    async def upsert(self, points):
        self.points.update({point["id"]: point for point in points})

    async def verify(self, expected):
        actual = {key: self.points[key]["payload"]["text_hash"] for key in expected}
        if actual != expected:
            raise ValueError("Index du double incohérent")

    async def query(self, vector, snapshot, limit=24):
        return []


class ControlledSelectorDouble:
    """Choisir toutes les références autorisées; attaques de schéma explicites."""

    def __init__(self, mode="all"):
        self.mode = mode
        self.calls: list[dict] = []

    async def stream(self, messages, cancelled, output_tokens=None, response_format=None):
        self.calls.append({"messages": copy.deepcopy(messages), "response_format": response_format,
                           "output_tokens": output_tokens, "double": type(self).__name__})
        if response_format is None:
            raw = "UNSOURCED_GENERATOR_999 [S001]"
        else:
            ids = response_format["properties"]["references"]["items"]["enum"]
            payload: dict[str, Any] = {"references": ids, "comparisons": []}
            if self.mode == "invented_field":
                payload["answer"] = "UNSOURCED_GENERATOR_999"
            elif self.mode == "unknown_reference":
                payload["references"] = ["R999"]
            raw = json.dumps(payload)
        yield {"type": "delta", "text": raw}
        yield {"type": "done", "finish_reason": "stop", "metrics": {"eval_count": 0}}


class RecordingSearch:
    """Capturer le passage réel, sans réexécuter une recherche de diagnostic."""

    def __init__(self, service, fault=None):
        self.service, self.fault = service, fault
        self.results: list[dict] = []

    def __getattr__(self, name):
        return getattr(self.service, name)

    def capture(self, result):
        value = copy.deepcopy(result)
        if self.fault:
            for source in value["results"]:
                if self.fault == "remove_locator":
                    source.pop("locator", None)
                    for block in source.get("blocks", []):
                        block.pop("locator", None)
                elif self.fault == "tamper_source_text":
                    source["text"] = "TAMPERED_SOURCE_999 " + source["text"]
                    for block in source.get("blocks", []):
                        block["text"] = "TAMPERED_SOURCE_999 " + block.get("text", "")
                else:
                    raise ValueError("Corruption de fixture inconnue")
        self.results.append(copy.deepcopy(value))
        return value

    async def search(self, *args, **kwargs):
        return self.capture(await self.service.search(*args, **kwargs))

    async def refine_once(self, *args, **kwargs):
        return self.capture(await self.service.refine_once(*args, **kwargs))


class ProcessMemorySampler:
    """Pic échantillonné du seul processus de rejeu; aucun modèle résident."""

    def __init__(self):
        import psutil

        self.process = psutil.Process()
        self.stop = threading.Event()
        self.peaks: dict[str, float | int] = {"samples": 0}
        self.thread = threading.Thread(target=self.run, daemon=True)

    def sample(self):
        info = self.process.memory_full_info()
        self.peaks["samples"] += 1
        for field in ("rss", "pss", "uss"):
            if hasattr(info, field):
                key = field + "_sampled_peak_mib"
                self.peaks[key] = max(float(self.peaks.get(key, 0)), getattr(info, field) / 1048576)

    def run(self):
        while not self.stop.is_set():
            self.sample()
            self.stop.wait(0.02)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=5)
        self.sample()


def all_patterns(patterns: list[str], text: str) -> bool:
    # A terminal sentence point is not a decimal digit. Keep the raw string and
    # accept the same oracle on this punctuation-normalized view; never change
    # a decimal separator followed by a digit, sign, unit or source text.
    punctuation_view = re.sub(r"(?<=\d)\.(?=\s|$)", "", text)
    return all(re.search(pattern, text) is not None or re.search(pattern, punctuation_view) is not None
               for pattern in patterns)


def source_text(source: dict[str, Any]) -> str:
    return "\n".join([str(source.get("text", "")), *[str(block.get("text", "")) for block in source.get("blocks", [])]])


def facts_in_sources(facts, sources, documents):
    results = {}
    for fact in facts:
        document_id = documents[fact["document"]]["document_id"]
        # A relation must be in one source bundle, not assembled from two documents.
        results[fact["id"]] = any(source.get("document_id") == document_id
                                 and all_patterns(fact["source_patterns"], source_text(source)) for source in sources)
    return results


def conflict_assertions_supported(case, fact, record):
    """Un désaccord cite des assertions séparées, sans fusionner leurs valeurs.

    Seulement pour un contrôle de conflit déjà déclaré dans la matrice : chaque
    paragraphe pertinent de l'original figé doit être cité intégralement dans la
    réponse et présent dans un seul extrait du document attendu. Les conditions,
    rôles et unités restent donc attachés à chaque assertion. La règle des faits
    simples (une relation dans un seul bundle) ne change pas.
    """
    if case.get("answerable") or case.get("expected") != "conflict":
        return False
    specification: dict[str, Any] = next((item for item in case.get("documents", []) if item["key"] == fact["document"]), {})
    assertions = [paragraph for paragraph in specification.get("paragraphs", [])
                  if any(all_patterns([pattern], paragraph) for pattern in fact["source_patterns"])]
    if len(assertions) < 2 or not all_patterns(fact["source_patterns"], "\n".join(assertions)):
        return False
    expected_document = record["documents"][fact["document"]]
    sources = [source for source in record.get("citations", [])
               if source.get("document_id") == expected_document["document_id"]
               and source.get("version_id") == expected_document["version_id"]]
    # Whitespace is a serialization detail; numbers, qualifiers and sentence
    # contents are unchanged. Never join different excerpts to rebuild a claim.
    answer = " ".join(record.get("answer", "").split())
    return all(" ".join(assertion.split()) in answer
               and any(" ".join(assertion.split()) in " ".join(source_text(source).split()) for source in sources)
               for assertion in assertions)


def validate_citations(citations, documents, db):
    """Vérifier identité et offsets; cela ne juge pas l'implication sémantique."""
    known = {item["version_id"]: item for item in documents.values()}
    checks = []
    for citation in citations:
        reasons = []
        document = known.get(citation.get("version_id"))
        if document is None or citation.get("document_id") != document["document_id"]:
            reasons.append("unknown_document_or_version")
        if citation.get("page_number") is not None or citation.get("page_index") is not None:
            reasons.append("invented_office_page")
        for block in citation.get("blocks", []):
            row = db.one("SELECT text,source_text_hash,extraction_revision_id FROM blocks WHERE generation_id=? AND id=?",
                         (citation["generation_id"], block["id"]))
            if row is None:
                reasons.append("unknown_block")
                continue
            start, end = block.get("start_offset", 0), block.get("end_offset", len(row["text"]))
            if row["text"][start:end] != block.get("text", ""):
                reasons.append("text_offset_mismatch")
            if hashlib.sha256(row["text"].encode()).hexdigest() != block.get("source_text_hash"):
                reasons.append("source_hash_mismatch")
            if citation.get("extraction_revision_id") != row["extraction_revision_id"]:
                reasons.append("extraction_revision_mismatch")
        if not citation.get("blocks"):
            reasons.append("empty_citation")
        checks.append({"source_id": citation.get("source_id"), "valid": not reasons, "reasons": reasons})
    return checks


def grade_case(case, record):
    """Oracles gelés et mécaniques, indépendants du statut answer_contract."""
    answer = record.get("answer", "")
    # Only public text, not private structured_delta holding a rejected plan.
    public = "\n".join([answer, *record.get("public_deltas", [])])
    facts = []
    citation_sources = record.get("citations", [])
    for fact in case.get("facts", []):
        supported = facts_in_sources([fact], citation_sources, record["documents"])[fact["id"]]
        if not supported:
            supported = conflict_assertions_supported(case, fact, record)
        shown = all_patterns(fact["answer_patterns"], answer)
        facts.append({"id": fact["id"], "rendered": shown, "literal_source_support": supported,
                      "rendered_and_supported": shown and supported})
    # The first paragraph is the system's qualification, not a negative source quotation.
    preamble = answer.split("\n\n", 1)[0]
    limitation = bool(LIMIT_NOTICE.search(preamble))
    missing_patterns = [pattern for pattern in case.get("required_answer_patterns", []) if not re.search(pattern, answer)]
    forbidden = [pattern for pattern in case.get("forbidden_answer_patterns", []) if re.search(pattern, public)]
    if "UNSOURCED_GENERATOR_999" in public or "TAMPERED_SOURCE_999" in public:
        forbidden.append("unsupported_sentinel_published")
    integrity = all(check["valid"] for check in record.get("citation_checks", []))
    terminated = record.get("state") == "done"
    error_allowed = record.get("error_code") in case.get("allowed_errors", [])
    facts_ok = all(fact["rendered_and_supported"] for fact in facts)
    if case["answerable"]:
        passed = terminated and facts_ok and not missing_patterns and not forbidden and integrity and not limitation
    elif case.get("expected") == "invalid_plan":
        # If the production contract bypasses generation, the malformed output was not exercised.
        passed = error_allowed and record.get("selector_calls", 0) > 0 and not forbidden and integrity
    elif case.get("expected") == "provenance":
        passed = (terminated or error_allowed) and not forbidden and integrity
    else:
        passed = (terminated and facts_ok and not missing_patterns and not forbidden and integrity
                  and (not case.get("must_limit") or limitation))
    return {"passed": passed, "answerable": case["answerable"], "facts": facts,
            "limitation_notice": limitation, "missing_answer_patterns": missing_patterns,
            "forbidden_published": forbidden, "citation_integrity": integrity,
            "expected_error_observed": error_allowed, "method": "frozen_literal_and_control_flow_oracles",
            "semantic_entailment_judgment": "not_a_general_semantic_judgment"}


def apply_extraction_fault(application, extraction, fault, version_id):
    result = copy.deepcopy(extraction)
    if fault["kind"] != "drop_text":
        raise ValueError("Défaut d'extraction inconnu")
    kept: set[str] = set()
    for unit in result["units"]:
        unit["blocks"] = [block for block in unit["blocks"] if fault["contains"] not in block["text"]]
        kept.update(block["id"] for block in unit["blocks"])
    for section in result.get("sections", []):
        section["block_ids"] = [key for key in section.get("block_ids", []) if key in kept]
    result["status"] = "ready_partial"
    result["parser_complete"] = False
    result.setdefault("warnings", []).append({"code": "controlled_missing_block", "message": "Bloc supprimé dans la fixture de contrôle."})
    source_hash = application.office_content_hash(result)
    fingerprint = result["pipeline_fingerprint"]
    revision = str(uuid5(UUID(version_id), fingerprint + ":" + source_hash))
    result.update(source_hash=source_hash, extraction_revision_id=revision)
    for unit in result["units"]:
        for block in unit["blocks"]:
            block["extraction_revision_id"] = revision
    return result


def scope_for_case(application, case, documents):
    scope = case.get("scope")
    if not scope:
        return application.Scope(kind="documents", documentIds=[item["document_id"] for item in documents.values()])
    from openpyxl.utils.cell import range_boundaries

    document = documents[scope.get("document", "a")]
    extraction = document["extraction"]
    column_start, row_start, column_end, row_end = range_boundaries(scope["range"])
    return application.Scope(kind="cell_range", versionId=document["version_id"],
                             extractionRevisionId=extraction["extraction_revision_id"],
                             sheetId=extraction["units"][0]["id"], rowStart=row_start, rowEnd=row_end,
                             columnStart=column_start, columnEnd=column_end)


async def run_case(application, case, settings, folder: Path, tokenizer_directory: Path | None = None):
    """Interface réutilisable; les doubles restent explicitement imposés ici."""
    folder.mkdir(parents=True, exist_ok=False)
    settings.profile["app"]["data_dir"] = str(folder / "data")
    settings.profile["sqlite"]["path"] = str(folder / "data/app.sqlite3")
    settings.profile["trace"].update(mode="full", max_bytes_per_query=8388608)
    tokenizer = CharacterCounterDouble()
    if tokenizer_directory:
        settings.profile["llm"]["tokenizer_dir"] = str(tokenizer_directory)
        tokenizer = application.LlmTokenizer(settings)
    db = application.Database(settings.db_path)
    db.initialize()
    embedding, vectors = ConstantEmbeddingDouble(), LexicalOnlyVectorDouble()
    indexer = application.Indexer(db, embedding, vectors, settings, tokenizer)
    resolver = (application.ScopeResolver(db, explicit_pdf_lists=True)
                if settings.value("enhanced", "explicit_pdf_lists", False) else application.ScopeResolver(db))
    search = RecordingSearch(application.SearchService(db, resolver, embedding, vectors, settings, projector=indexer),
                             case.get("retrieval_fault"))
    selector = ControlledSelectorDouble(case.get("gateway", "all"))
    service = application.QueryService(db, resolver, search, application.ContextBuilder(settings, tokenizer), selector, settings)
    documents = {}
    for spec in case["documents"]:
        name = case["id"] + "_" + spec["key"] + "." + spec["format"]
        original = folder / "originals" / name
        sha256 = generate_document(spec, original)
        imported = db.import_original(name, sha256, original, spec["format"])
        extraction = application.extract_office(original, folder / "extracted" / spec["key"], {},
                                                imported["version_id"], spec["format"])
        if case.get("extraction_fault"):
            extraction = apply_extraction_fault(application, extraction, case["extraction_fault"], imported["version_id"])
        extraction_path = folder / (spec["key"] + ".extraction.json")
        save_json(extraction_path, extraction)
        generation = await indexer.index(imported["job_id"], extraction, str(extraction_path))
        if extraction["status"] == "ready_partial":
            count = db.one("SELECT actual_chunks FROM index_generations WHERE id=?", (generation,))["actual_chunks"]
            indexer.publish(imported["job_id"], generation, count, partial=True, allow_partial=True)
        documents[spec["key"]] = {**imported, "generation_id": generation, "sha256": sha256, "extraction": extraction}
    scope = scope_for_case(application, case, documents)
    response = await service.create_async(application.QueryRequest(question=case["question"], scope=scope,
                                                                   mode=case.get("mode", "question")))
    query_id = response["query_id"]
    task = service.tasks.get(query_id)
    if task is not None:
        await asyncio.wait_for(asyncio.shield(task), timeout=60)
    run = service.run_detail(query_id)
    events = [{**row, "data": json.loads(row["data_json"])} for row in db.rows(
        "SELECT * FROM events WHERE query_id=? ORDER BY id", (query_id,))]
    terminals = [row for row in events if row["type"] in {"done", "error", "cancelled"}]
    terminal = terminals[-1]["data"] if terminals else {}
    citations = terminal.get("citations", [])
    trace_path = settings.data_dir / "traces" / (query_id + ".jsonl")
    trace = application.read_verified_trace(trace_path) if trace_path.exists() else []
    contexts = [row["data"] for row in trace if row["phase"] == "context"]
    retained = contexts[-1].get("retained", []) if contexts else []
    context_messages = contexts[-1].get("messages", []) if contexts else []
    candidates = search.results[-1].get("top10", []) if search.results else []
    serialized_messages = "\n".join(message["content"] for message in context_messages)
    fact_context = facts_in_sources(case.get("facts", []), retained, documents)
    for fact in case.get("facts", []):
        fact_context[fact["id"]] &= all_patterns(fact["source_patterns"], serialized_messages)
    record = {
        "case_id": case["id"], "question": case["question"], "scope": scope.model_dump(),
        "state": run["state"], "answer": run["answer"], "warnings": run["warnings"], "metrics": run["metrics"],
        "error_code": terminal.get("code"), "terminal_count": len(terminals),
        "public_deltas": [row["data"]["text"] for row in events if row["type"] == "delta"],
        "citations": citations, "citation_checks": validate_citations(citations, documents, db),
        "documents": {key: {field: value for field, value in item.items() if field != "extraction"}
                      for key, item in documents.items()},
        "retrieval_fact_recall_at_10": facts_in_sources(case.get("facts", []), candidates, documents),
        "context_literal_fact_coverage": fact_context,
        "context_coverage_limitation": "Source binding checked in retained bundles; patterns also required in serialized messages. This is not semantic entailment.",
        "selector_calls": len(selector.calls), "selector_kind": type(selector).__name__,
        "query_called_model_metric_is_double": True, "query_record": run, "events": events,
        "captured_selector_calls": selector.calls, "trace_path": str(trace_path),
    }
    record["judgment"] = grade_case(case, record)
    await service.close()
    return record


def summarize(records):
    positives = [record for record in records if record["judgment"]["answerable"]]
    controls = [record for record in records if not record["judgment"]["answerable"]]
    facts = [fact for record in positives for fact in record["judgment"]["facts"]]
    citations = [check for record in records for check in record.get("citation_checks", [])]
    retrieval = [value for record in positives for value in record.get("retrieval_fact_recall_at_10", {}).values()]
    context = [value for record in positives for value in record.get("context_literal_fact_coverage", {}).values()]
    latencies = [record["metrics"]["elapsed_ms"] for record in records if "elapsed_ms" in record.get("metrics", {})]
    return {
        "submissions": len(records), "answerable_pass": sum(record["judgment"]["passed"] for record in positives),
        "answerable_total": len(positives), "control_pass": sum(record["judgment"]["passed"] for record in controls),
        "control_total": len(controls), "errors": sum(record["state"] == "error" for record in records),
        "answerable_with_limitation_notice": sum(record["judgment"]["limitation_notice"] for record in positives),
        "answerable_errors": sum(record["state"] == "error" for record in positives),
        "literal_facts_rendered_and_supported": sum(fact["rendered_and_supported"] for fact in facts),
        "required_literal_facts": len(facts), "retrieval_fact_recall_at_10": {"found": sum(retrieval), "total": len(retrieval)},
        "context_literal_fact_coverage": {"found": sum(context), "total": len(context)},
        "citation_integrity": {"valid": sum(check["valid"] for check in citations), "total": len(citations)},
        "forbidden_publication_cases": sum(bool(record["judgment"]["forbidden_published"]) for record in records),
        "query_latency_ms": {"n": len(latencies), "median": statistics.median(latencies) if latencies else None,
                             "max": max(latencies) if latencies else None,
                             "scope": "controlled QueryService with named doubles, not model latency"},
    }


async def campaign(args):
    if any(os.environ.get(key) for key in ("RAG_DATA_DIR", "RAG_DB_PATH")):
        raise ValueError("Un override de stockage empêche l'isolation")
    fixture = load_fixture(args.fixtures)
    if args.output.exists() or args.work_dir.exists():
        raise FileExistsError("Une sortie ou un dossier de travail existe déjà")
    args.work_dir.mkdir(parents=True)
    sources = {str(path.relative_to(args.application_root)): digest_file(path)
               for path in sorted((args.application_root / "services").rglob("*.py"))}
    versions: dict[str, str | None] = {}
    for name in ("pydantic", "httpx", "openpyxl", "python-docx", "lxml", "defusedxml", "psutil", "tokenizers"):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = None
    frozen = {
        "created_utc": datetime.now(UTC).isoformat(), "fixtures_sha256": digest_file(args.fixtures),
        "harness_sha256": digest_file(Path(__file__)), "application_root": str(args.application_root),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.application_root, text=True).strip(),
        "source_files": sources, "libraries": versions, "platform": platform.platform(), "python": sys.version,
        "profile_sha256": digest_file(args.profile), "tokenizer_directory": str(args.tokenizer_dir) if args.tokenizer_dir else None,
        "test_kind": "controlled_native_office_and_query_with_doubles", "model_inference": "NOT_RUN",
        "doubles": ["ConstantEmbeddingDouble", "LexicalOnlyVectorDouble", "ControlledSelectorDouble"]
                   + ([] if args.tokenizer_dir else ["CharacterCounterDouble"]),
        "not_exercised": ["Ollama", "4B generation", "E5", "Qdrant", "PDF ingestion", "OCR", "HTTP", "browser", "resource governor"],
        "case_order": [case["id"] for case in fixture["cases"]],
    }
    save_json(args.work_dir / "protocol-frozen.json", frozen)
    application = load_application(args.application_root)
    base = application.Settings.load(args.profile)
    records = []
    for case in fixture["cases"]:
        settings = application.Settings(args.application_root, copy.deepcopy(base.profile))
        memory = ProcessMemorySampler()
        memory.thread.start()
        started = time.perf_counter()
        try:
            record = await run_case(application, case, settings, args.work_dir / case["id"], args.tokenizer_dir)
        except Exception as error:
            record = {"case_id": case["id"], "state": "harness_error", "answer": "", "documents": {},
                      "error_type": type(error).__name__, "error_message": str(error),
                      "retrieval_fact_recall_at_10": {fact["id"]: False for fact in case.get("facts", [])},
                      "context_literal_fact_coverage": {fact["id"]: False for fact in case.get("facts", [])},
                      "judgment": {"passed": False, "answerable": case["answerable"], "facts": [
                          {"id": fact["id"], "rendered": False, "literal_source_support": False,
                           "rendered_and_supported": False} for fact in case.get("facts", [])],
                                   "limitation_notice": False, "forbidden_published": [], "method": "harness_exception"}}
        finally:
            memory.close()
        record["whole_controlled_case_ms"] = round((time.perf_counter() - started) * 1000, 3)
        record["process_memory"] = {**memory.peaks, "scope": "replay process only; 20 ms point sampling, no model or service"}
        save_json(args.work_dir / (case["id"] + ".json"), record)
        records.append(record)
        print(json.dumps({"case_id": case["id"], "state": record["state"], "pass": record["judgment"]["passed"]}), flush=True)
    changed = [name for name, digest in sources.items()
               if not (args.application_root / name).exists() or digest_file(args.application_root / name) != digest]
    report = {"protocol": frozen, "acceptance": fixture["acceptance"], "summary": summarize(records),
              "source_stability": {"changed_during_run": changed}, "cases": records}
    save_json(args.output, report)
    print(json.dumps({"output": str(args.output), "summary": report["summary"], "source_stability": changed}), flush=True)
    if changed:
        raise RuntimeError("La révision a changé pendant le rejeu")
    return report


def review_report(source: Path, fixtures: Path, output: Path):
    """Recalcul sans nouvelle soumission; conserver le rapport brut inchangé."""
    fixture = load_fixture(fixtures)
    report = json.loads(source.read_text(encoding="utf-8"))
    if report["protocol"]["fixtures_sha256"] != digest_file(fixtures):
        raise ValueError("Une relecture ne peut changer les oracles gelés")
    cases = {case["id"]: case for case in fixture["cases"]}
    changes = []
    for record in report["cases"]:
        if record["state"] == "harness_error":
            continue
        previous = record["judgment"]
        record["judgment"] = grade_case(cases[record["case_id"]], record)
        if previous != record["judgment"]:
            changes.append({"case_id": record["case_id"], "previous": previous, "revised": record["judgment"]})
    report["summary"] = summarize(report["cases"])
    report["reassessment"] = {
        "created_utc": datetime.now(UTC).isoformat(), "source_report": str(source),
        "source_report_sha256": digest_file(source), "review_harness_sha256": digest_file(Path(__file__)),
        "new_queries": 0, "changed_oracles": False, "changes": changes,
        "grader_revision": "literal-review-20261108-v2",
        "reason": "Correction mécanique du lecteur : ponctuation après entier, formulations explicites de limitation, et assertions de conflit distinctes citées intégralement dans le bon document/version. La règle du bundle unique reste applicable aux relations simples. Les sources, questions, sorties et seuils sont inchangés.",
    }
    save_json(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--application-root", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tokenizer-dir", type=Path)
    parser.add_argument("--review-report", type=Path)
    args = parser.parse_args()
    for name in ("application_root", "profile", "fixtures", "work_dir", "output", "tokenizer_dir", "review_report"):
        if getattr(args, name) is not None:
            setattr(args, name, getattr(args, name).resolve())
    if args.review_report:
        report = review_report(args.review_report, args.fixtures, args.output)
        print(json.dumps({"output": str(args.output), "summary": report["summary"], "new_queries": 0}))
    else:
        if any(getattr(args, name) is None for name in ("application_root", "profile", "work_dir")):
            parser.error("--application-root, --profile et --work-dir sont requis pour exécuter des cas")
        asyncio.run(campaign(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
