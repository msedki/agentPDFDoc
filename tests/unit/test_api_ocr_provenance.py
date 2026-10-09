"""R26-OCR-01 : provenance d'extraction des blocs portée par les sources, les citations et la recherche.

SQLite/FTS5 réels ; embeddings (FakeEmbedding), vecteurs (FakeVectors) et tokenizer (FakeLlmTokenizer) sont des doubles
nommés de test_api_storage. Les méthodes viennent de `metadata.extraction_method`, écrit par l'ingestion pour chaque bloc.
"""
import asyncio
import hashlib
import json

from test_api_storage import FakeEmbedding, import_fixture
from test_api_storage import storage as storage

from services.api.retrieval import SearchService, ocr_evidence_warnings
from services.api.schemas import Scope
from services.api.scope import ScopeResolver, with_extraction_provenance

OCR_TEXT = "La tolérance de pression de DA-P02 est de + 3.0 %."
NATIVE_TEXT = "Le couple de serrage prescrit pour DA-P02 est de 14 N·m."
LEGACY_TEXT = "L'alimentation d'essai de DA-P02 est de 24 V."


def page(blocks, index=0):
    return {"page_index": index, "width": 595, "height": 842, "media_box": [0, 0, 595, 842], "crop_box": [0, 0, 595, 842], "rotation": 0,
            "blocks": blocks}


def block(identifier, text, method=None, section=None, y=700):
    item = {"id": identifier, "type": "text", "text": text, "raw_text": text, "bbox": [10, y, 300, y + 12], "precision": "block"}
    if method is not None:
        item["metadata"] = {"extraction_method": method, "ocr_used": method in {"ocr", "mixed"}}
    if section:
        item["section_id"] = section
    return item


def methods_by_block(storage, pages, sections=None, scope=None):
    imported, _ = import_fixture(storage, text=OCR_TEXT, pages=pages, sections=sections)
    settings, db, vectors, _ = storage
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(scope(imported) if scope else Scope(kind="documents", documentIds=[imported["document_id"]]))
    result = asyncio.run(SearchService(db, resolver, FakeEmbedding(), vectors, settings).search("tolérance couple alimentation DA-P02", snapshot))
    return imported, result


def test_sources_carry_stored_block_methods_and_unknown_when_absent(storage):
    _, result = methods_by_block(storage, [page([block("ocr0", OCR_TEXT, "ocr"), block("nat0", NATIVE_TEXT, "native", y=680),
                                                 block("old0", LEGACY_TEXT, y=660)])])
    by_block = {source["blocks"][0]["id"]: source for source in result["results"]}
    assert {key: source["extraction_methods"] for key, source in by_block.items()} == {"ocr0": ["ocr"], "nat0": ["native"], "old0": ["unknown"]}
    assert {key: source["blocks"][0]["extraction_method"] for key, source in by_block.items()} == {"ocr0": "ocr", "nat0": "native", "old0": "unknown"}


def test_selection_preserves_partial_extraction_coverage_and_warning(storage):
    text = "Lecture vérifiée 😀 : tolérance 3.0 %."
    imported, _ = import_fixture(storage, text=text, pages=[page([block("b0", text, "ocr")])])
    settings, db, vectors, _ = storage
    generation = db.one("SELECT active_generation_id FROM documents WHERE id=?", (imported["document_id"],))["active_generation_id"]
    coverage = {"missing_pages": [1], "low_confidence_pages": [0]}
    extraction_warnings = [{"code": "ocr_low_confidence", "page_index": 0}]
    db.execute("UPDATE index_generations SET state='ready_partial',coverage_json=?,warnings_json=? WHERE id=?",
               (json.dumps(coverage), json.dumps(extraction_warnings), generation))
    stored = db.one("SELECT * FROM blocks WHERE generation_id=? AND id='b0'", (generation,))
    resolver = ScopeResolver(db)
    scope = Scope(kind="selection", versionId=imported["version_id"], spans=[{
        "extractionRevisionId": stored["extraction_revision_id"], "blockId": "b0", "blockTextSha256": stored["source_text_hash"],
        "offsetUnit": "unicode_code_point", "startOffset": 0, "endOffset": len(text)}])
    result = asyncio.run(SearchService(db, resolver, FakeEmbedding(), vectors, settings).search("tolérance", resolver.resolve(scope)))
    source = result["results"][0]
    assert source["text"] == text and source["blocks"][0]["source_text_hash"] == stored["source_text_hash"]
    assert source["coverage"] == coverage and source["extraction_state"] == "ready_partial"
    assert source["extraction_warnings"] == extraction_warnings
    assert [warning["document_id"] for warning in result["warnings"] if warning["code"] == "partial_extraction"] == [imported["document_id"]]


def test_a_source_packing_several_blocks_lists_each_method_once(storage):
    blocks = [block("ocr0", OCR_TEXT, "ocr", "s0"), block("nat0", NATIVE_TEXT, "native", "s0", 680), block("mix0", LEGACY_TEXT, "mixed", "s0", 660)]
    _, result = methods_by_block(storage, [page(blocks)], sections=[{"id": "s0", "title": "Banc", "page_index": 0, "block_ids": ["ocr0", "nat0", "mix0"]}])
    packed = [source for source in result["results"] if len(source["blocks"]) == 3]
    assert packed and packed[0]["extraction_methods"] == ["mixed", "native", "ocr"]


def test_search_warns_once_per_document_with_ocr_and_never_for_native_or_unknown(storage):
    imported, result = methods_by_block(storage, [page([block("ocr0", OCR_TEXT, "ocr"), block("old0", LEGACY_TEXT, y=660)]),
                                                  page([block("ocr1", NATIVE_TEXT, "ocr")], 1)])
    warnings = [warning for warning in result["warnings"] if warning["code"] == "ocr_evidence"]
    assert len(warnings) == 1
    assert warnings[0]["document_id"] == imported["document_id"] and warnings[0]["extraction_methods"] == ["ocr"]
    # POST /search n'attribue pas d'identifiant de source : liste vide, les résultats portent leur propre provenance.
    assert warnings[0]["source_ids"] == []
    assert "OCR" in warnings[0]["message"] and "page originale" in warnings[0]["message"]


def test_selected_span_keeps_the_block_method(storage):
    def selection(imported):
        row = storage[1].one("SELECT extraction_revision_id,source_text_hash FROM blocks WHERE id='ocr0'")
        return Scope(kind="selection", versionId=imported["version_id"], spans=[{
            "extractionRevisionId": row["extraction_revision_id"], "blockId": "ocr0", "blockTextSha256": row["source_text_hash"],
            "offsetUnit": "unicode_code_point", "startOffset": 0, "endOffset": 12}])
    _, result = methods_by_block(storage, [page([block("ocr0", OCR_TEXT, "ocr")])], scope=selection)
    assert [source["extraction_methods"] for source in result["results"]] == [["ocr"]]
    assert result["results"][0]["blocks"][0]["extraction_method"] == "ocr"
    # La sélection (12 premiers caractères) ne contient pas DA-P02 : identifier_not_found_in_scope l'accompagne.
    assert [warning["code"] for warning in result["warnings"]] == ["identifier_not_found_in_scope", "ocr_evidence"]


def test_parent_expansion_keeps_methods(storage):
    imported, result = methods_by_block(storage, [page([block("ocr0", OCR_TEXT, "ocr")])])
    db = storage[1]
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="documents", documentIds=[imported["document_id"]]))

    class WholeTokenizer:
        def count(self, text):
            return 1
    expanded = resolver.expand_parent(result["results"][0], snapshot, WholeTokenizer())
    assert expanded["extraction_methods"] == ["ocr"] and expanded["blocks"][0]["extraction_method"] == "ocr"


def test_ocr_evidence_groups_retained_sources_by_document():
    sources = [{"source_id": "S001", "document_id": "A", "document_name": "a.pdf", "extraction_methods": ["native"]},
               {"source_id": "S002", "document_id": "B", "document_name": "b.pdf", "extraction_methods": ["mixed"]},
               {"source_id": "S003", "document_id": "A", "document_name": "a.pdf", "extraction_methods": ["native", "ocr"]},
               {"source_id": "S004", "document_id": "B", "document_name": "b.pdf", "extraction_methods": ["ocr"]},
               {"source_id": "S005", "document_id": "C", "document_name": "c.pdf", "extraction_methods": ["unknown"]},
               {"source_id": "S006", "document_id": "D", "document_name": "d.pdf"}]
    warnings = ocr_evidence_warnings(sources)
    assert [(warning["document_id"], warning["source_ids"], warning["extraction_methods"]) for warning in warnings] == [
        ("B", ["S002", "S004"], ["mixed", "ocr"]), ("A", ["S003"], ["ocr"])]
    assert warnings[1]["message"] == ("Passages de « a.pdf » lus par reconnaissance optique de caractères (OCR) : des signes, unités ou "
                                      "références peuvent être faux même sans alerte de faible confiance. Comparez les valeurs utilisées "
                                      "avec la page originale.")
    assert ocr_evidence_warnings([]) == []


def test_citation_recorded_before_r26_reads_unknown_never_native():
    legacy = {"source_id": "S001", "blocks": [{"id": "b0", "text": "72 V"}], "text": "72 V"}
    assert with_extraction_provenance(legacy) == {"source_id": "S001", "blocks": [{"id": "b0", "text": "72 V", "extraction_method": "unknown"}],
                                                  "text": "72 V", "extraction_methods": ["unknown"]}
    assert "extraction_methods" not in legacy and "extraction_method" not in legacy["blocks"][0]
    current = {"source_id": "S001", "blocks": [{"id": "b0", "extraction_method": "ocr"}], "extraction_methods": ["ocr"]}
    assert with_extraction_provenance(current) == current


def test_partial_extraction_message_no_longer_implies_extracted_regions_are_proof(storage):
    payload = b"%PDF-1.7\npartial"
    settings, db, vectors, indexer = storage
    digest = hashlib.sha256(payload).hexdigest()
    blob = settings.data_dir / "originals" / (digest + ".pdf")
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(payload)
    imported = db.import_original("folder/partial.pdf", digest, blob)
    extraction = {"sha256": digest, "fingerprint": "partial-v1", "page_count": 2, "status": "ready_partial",
                  "pages": [page([block("ocr0", OCR_TEXT, "ocr")])]}
    generation = asyncio.run(indexer.index(imported["job_id"], extraction))
    indexer.publish(imported["job_id"], generation, 1, partial=True, allow_partial=True)
    resolver = ScopeResolver(db)
    snapshot = resolver.resolve(Scope(kind="documents", documentIds=[imported["document_id"]]))
    result = asyncio.run(SearchService(db, resolver, FakeEmbedding(), vectors, settings).search("tolérance DA-P02", snapshot))
    partial = [warning for warning in result["warnings"] if warning["code"] == "partial_extraction"]
    assert partial == [{"code": "partial_extraction", "document_id": imported["document_id"], "message":
                        "Extraction partielle : des pages ou des régions de ce document sont absentes de l'extraction ou ont été lues "
                        "avec une confiance insuffisante. Des informations peuvent manquer ; vérifiez les passages retrouvés sur la "
                        "page originale."}]
    assert "constituent" not in partial[0]["message"]
