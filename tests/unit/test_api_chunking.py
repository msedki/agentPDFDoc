"""Découpage section-pack-v1 : regroupement des blocs courts d'une même section, frontières et provenance au bloc."""
import asyncio
import hashlib

from test_api_storage import FakeEmbedding
from test_api_storage import storage as storage

from services.api.indexing import CHUNKER_REVISION, chunk_plan
from services.api.schemas import Scope
from services.api.scope import ScopeResolver


def text_block(identifier, text, section="s1", kind="text"):
    return {"id": identifier, "type": kind, "text": text, "raw_text": text, "section_id": section, "bbox": [10, 10, 100, 30], "precision": "block"}


def plan_ids(plan):
    return [[(block["id"], start, end) for block, start, end in parts] for parts in plan]


def test_consecutive_blocks_of_one_section_share_a_chunk_until_the_target():
    blocks = [text_block("h", "Réglage du distributeur", kind="heading"), text_block("a", "Pression de service 3,1 bar."), text_block("b", "Contrôler au manomètre.")]
    assert plan_ids(chunk_plan(blocks, FakeEmbedding(), target=320)) == [[("h", 0, 23), ("a", 0, 28), ("b", 0, 23)]]
    # Cible atteinte : le bloc suivant ouvre un nouveau chunk, sans couper un bloc qui tient seul.
    # Faux tokenizer : len // 4 + 3, soit h = 8, a = 10, b = 8, h + a joints = 16.
    assert plan_ids(chunk_plan(blocks, FakeEmbedding(), target=16)) == [[("h", 0, 23), ("a", 0, 28)], [("b", 0, 23)]]
    assert plan_ids(chunk_plan(blocks, FakeEmbedding(), target=12)) == [[("h", 0, 23)], [("a", 0, 28)], [("b", 0, 23)]]


def test_structure_boundaries_are_never_crossed():
    blocks = [text_block("a", "Premier paragraphe."), text_block("b", "Autre section.", section="s2"), text_block("t", "| A | B |", kind="table"),
              text_block("c", "Après le tableau."), text_block("d", "Sans section.", section=None), text_block("e", "Encore s1.")]
    assert plan_ids(chunk_plan(blocks, FakeEmbedding())) == [[("a", 0, 19)], [("b", 0, 14)], [("t", 0, 9)], [("c", 0, 17)], [("d", 0, 13)], [("e", 0, 10)]]


def test_a_block_longer_than_the_target_is_split_alone_as_before():
    long_text = "alimentation " * 120
    blocks = [text_block("a", "Court."), text_block("long", long_text), text_block("b", "Court aussi.")]
    plan = plan_ids(chunk_plan(blocks, FakeEmbedding(), target=320, overlap=0))
    assert plan[0] == [("a", 0, 6)] and plan[-1] == [("b", 0, 12)]
    windows = plan[1:-1]
    assert len(windows) >= 2 and all(len(parts) == 1 and parts[0][0] == "long" for parts in windows)
    assert windows[0][0][1] == 0 and windows[-1][0][2] == len(long_text)


def test_indexed_chunk_keeps_every_block_as_a_cited_source_and_the_scope_cut(storage):
    settings, db, vectors, indexer = storage
    blocks = [text_block("h", "Réglage du distributeur SW4", kind="heading"), text_block("a", "Pression de service 3,1 bar."),
              text_block("b", "Contrôler au manomètre.", section="s2")]
    payload = b"%PDF-1.7\nsection-pack"
    digest = hashlib.sha256(payload).hexdigest()
    blob = settings.data_dir / "originals" / (digest + ".pdf")
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(payload)
    imported = db.import_original("manuel/sections.pdf", digest, blob)
    extraction = {"sha256": digest, "fingerprint": "fixture-sections-v1", "page_count": 1, "status": "ready",
                  "sections": [{"id": "s1", "title": "Distributeur", "page_index": 0, "block_ids": ["h", "a"]},
                               {"id": "s2", "title": "Contrôle", "page_index": 0, "block_ids": ["b"]}],
                  "pages": [{"page_index": 0, "width": 595, "height": 842, "blocks": blocks}]}
    asyncio.run(indexer.index(imported["job_id"], extraction))
    merged = db.one("SELECT * FROM chunks WHERE parent_id='h'")
    assert merged["text"] == "Réglage du distributeur SW4\nPression de service 3,1 bar." and merged["section_title"] == "Distributeur"
    sources = db.rows("SELECT block_id,start_offset,end_offset,position FROM chunk_sources WHERE chunk_uuid=? ORDER BY position", (merged["chunk_uuid"],))
    assert [(row["block_id"], row["start_offset"], row["end_offset"], row["position"]) for row in sources] == [("h", 0, 27, 0), ("a", 0, 28, 1)]
    assert vectors.points[merged["chunk_uuid"]]["payload"]["block_ids"] == ["h", "a"]
    assert db.one("SELECT count(*) n FROM chunks")["n"] == 2
    resolver = ScopeResolver(db)
    library = resolver.resolve(Scope(kind="library"))
    source = resolver.source_for_chunk(merged, library)
    # La source reconstruite à la lecture a exactement le texte indexé et cite chaque bloc avec ses offsets.
    assert source["text"] == merged["text"] and [block["id"] for block in source["blocks"]] == ["h", "a"]
    generation = library.generations[0]
    section = resolver.resolve(Scope(kind="section", versionId=imported["version_id"], sectionId="s1"))
    assert section.generations == [generation]
    # Périmètre restreint à un bloc : le chunk qui l'intersecte est coupé au bloc autorisé avant tout contexte.
    narrowed = type(section)(section.scope, section.generations, section.versions, section.documents, None, ["a"], [], [])
    cut = resolver.source_for_chunk(merged, narrowed)
    assert cut["text"] == "Pression de service 3,1 bar." and [block["id"] for block in cut["blocks"]] == ["a"]


def test_chunker_revision_is_part_of_the_generation_fingerprint(storage):
    _, _, _, indexer = storage
    assert CHUNKER_REVISION == "section-pack-v1"
    assert indexer.generation_fingerprint("extraction") != indexer.generation_fingerprint("autre-extraction")
