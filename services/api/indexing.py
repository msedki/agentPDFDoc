import asyncio
import hashlib
import json
import math
import struct
import threading
from typing import Any
from uuid import UUID, uuid5

from .context import LlmTokenizer
from .db import json_dump, now, uid
from .errors import ApiError
from .retrieval import identifiers, normalized_identifier


def extraction_content_hash(extraction):
    content = {"pages": extraction["pages"], "sections": extraction.get("sections", []), "tables": extraction.get("tables", [])}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def split_text(text, embedding, target=320, overlap=48):
    """Character offsets remain exact; tokenizer counts include the E5 prefix."""
    offset = 0
    while offset < len(text):
        low, high = offset + 1, len(text)
        best = offset
        while low <= high:
            middle = (low + high) // 2
            if embedding.count(text[offset:middle]) <= target:
                best, low = middle, middle + 1
            else:
                high = middle - 1
        if best <= offset:
            raise ApiError("unchunkable_text", "Un caractère dépasse la capacité du tokenizer.")
        if best < len(text):
            boundary = max(text.rfind(" ", offset, best), text.rfind("\n", offset, best))
            if boundary > offset + (best - offset) // 2:
                best = boundary + 1
        if embedding.count(text[offset:best]) > 448:
            raise ApiError("chunk_too_long", "Chunk E5 hors limite.")
        yield offset, best
        if best == len(text):
            break
        next_offset = best
        if overlap:
            lo, hi = offset + 1, best
            while lo <= hi:
                mid = (lo + hi) // 2
                if embedding.count(text[mid:best]) <= overlap:
                    next_offset, hi = mid, mid - 1
                else:
                    lo = mid + 1
        offset = max(offset + 1, next_offset)


# W012 : une zone graphique non interprétée est une limite déclarée, pas une perte de texte ;
# une page sans rien à lire (préflight « graphique incertain » ou « blanche », aucun caractère) non plus.
LOSS_FREE_REGION_REASONS = frozenset({"GRAPHIC_INTERPRETATION_UNAVAILABLE"})
NO_TEXT_CLASSIFICATIONS = frozenset({"graphic_uncertain", "blank"})


def text_loss(extraction):
    """Vrai si du texte manque : la publication reste alors une décision explicite (extraction partielle)."""
    pages = extraction.get("pages", [])
    if len(pages) < extraction.get("page_count", 0):
        return True
    if extraction.get("status") != "ready_partial":
        return False
    # Extraction antérieure sans l'indicateur du parseur : prudence, elle reste partielle.
    if extraction.get("parser_complete") is not True:
        return True
    for page in pages:
        if any(region.get("reason") not in LOSS_FREE_REGION_REASONS for region in page.get("unresolved_regions", [])):
            return True
        nothing_to_read = (page.get("classification") in NO_TEXT_CLASSIFICATIONS and not page.get("blocks")
                           and not page.get("alphanumeric_count"))
        if page.get("extraction_state") == "error" and not nothing_to_read:
            return True
    return False

class Indexer:
    def __init__(self, db, embedding, vectors, settings, llm_tokenizer=None):
        self.db, self.embedding, self.vectors, self.settings = db, embedding, vectors, settings
        self.llm_tokenizer = llm_tokenizer or LlmTokenizer(settings)
        self._telemetry_lock = threading.Lock()
        self._telemetry: dict[str, Any] = {"requests": 0, "cache_hits": 0, "cache_misses": 0,
                           "embedding_requests": 0, "embedding_texts_submitted": 0,
                           "embedding_requests_completed": 0, "last_request": None}

    def diagnostics(self):
        with self._telemetry_lock:
            return {**self._telemetry, "scope": "current_process",
                    "hit_definition": "A cached vector with matching full model identity/text hash, dimension, finite values and L2 norm was used",
                    "embedding_request_definition": "A call to embedding.embed; actual session.run batches are reported separately"}

    def generation_fingerprint(self, extraction_fingerprint):
        identity = self.embedding.identity() if hasattr(self.embedding, "identity") else {"fingerprint": "explicit-test-embedding"}
        return hashlib.sha256(json_dump({"extraction": extraction_fingerprint, "embedding": identity,
            "llm_tokenizer": self.llm_tokenizer.identity() if hasattr(self.llm_tokenizer, "identity") else "explicit-test-tokenizer",
            "chunking": self.settings.profile.get("chunking", {}), "chunker_revision": "codepoint-block-v1"}).encode()).hexdigest()

    def stage(self, job_id, extraction, extraction_path=None):
        job = self.db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not job:
            raise ApiError("job_not_found", "Travail inconnu.", 404)
        version = self.db.version(job["version_id"])
        if extraction.get("sha256") and extraction["sha256"] != version["sha256"]:
            raise ApiError("original_integrity_failure", "L'extraction ne correspond pas à l'original.")
        generation_id = job["generation_id"] or uid()
        extraction_fingerprint = extraction.get("pipeline_fingerprint", extraction.get("fingerprint", ""))
        if not extraction_fingerprint:
            raise ApiError("missing_fingerprint", "Empreinte de pipeline absente.")
        fingerprint = self.generation_fingerprint(extraction_fingerprint)
        extraction_hash = extraction_content_hash(extraction)
        extraction_revision_id = extraction.get("extraction_revision_id") or str(uuid5(UUID(version["id"]), extraction_fingerprint + ":" + extraction_hash))
        page_count = extraction.get("page_count", len(extraction.get("pages", [])))
        if page_count > self.settings.value("pdf", "max_document_pages", 2000):
            raise ApiError("document_too_many_pages", "Document trop long.")
        chunks = []
        for page in extraction["pages"]:
            for block in page.get("blocks", []):
                text = block.get("raw_text", block.get("text", ""))
                if not text.strip():
                    continue
                for start, end in split_text(text, self.embedding, self.settings.value("chunking", "target_tokens", 320), self.settings.value("chunking", "overlap_max_tokens", 48)):
                    chunk_id = str(uuid5(UUID(generation_id), f"{block['id']}:{start}:{end}"))
                    chunk_text = text[start:end]
                    chunks.append({"id": chunk_id, "block_id": block["id"], "page_index": page["page_index"],
                                   "text": chunk_text, "start": start, "end": end, "section_id": block.get("section_id"),
                                   "hash": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(), "tokens": self.embedding.count(chunk_text),
                                   "llm_tokens": self.llm_tokenizer.count(chunk_text)})
        coverage = extraction.get("coverage", {"total": page_count, "processed": len(extraction["pages"]), "ocr": 0})
        warnings = list(extraction.get("warnings", []))
        if not chunks and not any(isinstance(warning, dict) and warning.get("code") == "no_exploitable_text" for warning in warnings):
            warnings.append({"code": "no_exploitable_text", "message": "Aucun texte exploitable dans les pages extraites ; original conservé.",
                             "severity": "warning"})
        with self.db.transaction() as connection:
            connection.execute("INSERT OR IGNORE INTO extraction_revisions VALUES(?,?,?,?,?,?)", (extraction_revision_id, version["id"], extraction_fingerprint, extraction_hash, str(extraction_path) if extraction_path else None, now()))
            revision = connection.execute("SELECT * FROM extraction_revisions WHERE id=?", (extraction_revision_id,)).fetchone()
            if revision["source_hash"] != extraction_hash or revision["version_id"] != version["id"]:
                raise ApiError("extraction_revision_drift", "Une révision immutable ne peut pas changer de contenu.")
            connection.execute("INSERT OR IGNORE INTO index_generations(id,version_id,fingerprint,expected_chunks,extraction_path,coverage_json,warnings_json,created_at,extraction_revision_id) VALUES(?,?,?,?,?,?,?,?,?)", (generation_id, version["id"], fingerprint, len(chunks), str(extraction_path) if extraction_path else None, json_dump(coverage), json_dump(warnings), now(), extraction_revision_id))
            existing = connection.execute("SELECT fingerprint,expected_chunks,extraction_revision_id FROM index_generations WHERE id=?", (generation_id,)).fetchone()
            if existing["fingerprint"] != fingerprint or existing["expected_chunks"] != len(chunks) or existing["extraction_revision_id"] != extraction_revision_id:
                raise ApiError("generation_drift", "La reprise a changé le contenu de la génération.")
            connection.execute("UPDATE document_versions SET page_count=?,metadata_json=? WHERE id=?", (page_count, json_dump(extraction.get("metadata", {})), version["id"]))
            for page in extraction["pages"]:
                geometry = {key: value for key, value in page.items() if key != "blocks"}
                geometry.setdefault("page_number", page["page_index"] + 1)
                connection.execute("INSERT OR IGNORE INTO pages VALUES(?,?,?,?)", (generation_id, page["page_index"], json_dump(geometry), page.get("extraction_state", "ready")))
                for block in page.get("blocks", []):
                    bbox = block.get("bbox")
                    precision = block.get("precision", "block" if bbox else "page")
                    source_text = block.get("raw_text", block.get("text", ""))
                    source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
                    if block.get("source_text_hash", source_hash) != source_hash:
                        raise ApiError("source_text_integrity_failure", "Hash du texte source invalide.")
                    connection.execute("INSERT OR IGNORE INTO blocks VALUES(?,?,?,?,?,?,?,?,?,?,?)", (generation_id, block["id"], page["page_index"], block.get("type", block.get("kind", "text")), source_text, json_dump(bbox) if bbox else None, precision, block.get("section_id"), json_dump({key: value for key, value in block.items() if key not in {"text", "raw_text", "bbox"}}), extraction_revision_id, source_hash))
            for section in extraction.get("sections", []):
                connection.execute("INSERT OR IGNORE INTO sections VALUES(?,?,?,?,?)", (generation_id, section["id"], section.get("title", ""), section.get("page_index", section.get("page_start")), json_dump(section.get("block_ids", []))))
            for table in extraction.get("tables", []):
                connection.execute("INSERT OR IGNORE INTO tables_data VALUES(?,?,?)", (generation_id, table["id"], json_dump(table)))
            section_titles = {section["id"]: section.get("title", "") for section in extraction.get("sections", [])}
            for chunk in chunks:
                connection.execute("INSERT OR IGNORE INTO chunks(chunk_uuid,generation_id,version_id,parent_id,section_title,text,e5_tokens,llm_tokens,text_hash,extraction_revision_id) VALUES(?,?,?,?,?,?,?,?,?,?)", (chunk["id"], generation_id, version["id"], chunk["block_id"], section_titles.get(chunk["section_id"], ""), chunk["text"], chunk["tokens"], chunk["llm_tokens"], chunk["hash"], extraction_revision_id))
                connection.execute("INSERT OR IGNORE INTO chunk_sources VALUES(?,?,?,?,?,0)", (chunk["id"], chunk["block_id"], chunk["page_index"], chunk["start"], chunk["end"]))
                for identifier in identifiers(chunk["text"]):
                    connection.execute("INSERT OR IGNORE INTO identifiers VALUES(?,?,?)", (chunk["id"], identifier, normalized_identifier(identifier)))
            connection.execute("UPDATE jobs SET generation_id=?,state='indexing',stage='embedding',progress=0.65,updated_at=? WHERE id=?", (generation_id, now(), job_id))
            connection.execute("UPDATE documents SET state='indexing',updated_at=? WHERE id=? AND active_generation_id IS NULL", (now(), version["document_id"]))
        return generation_id, chunks

    def cached_embeddings(self, chunks):
        identity = self.embedding.identity()["fingerprint"] if hasattr(self.embedding, "identity") else "explicit-test-embedding"
        vectors: list[list[float] | None] = [None] * len(chunks)
        missing = []
        for position, chunk in enumerate(chunks):
            row = self.db.one("SELECT vector,dimensions FROM embedding_cache WHERE model_identity=? AND text_hash=?", (identity, chunk["hash"]))
            if row and row["dimensions"] == 384 and len(row["vector"]) == 384 * 4:
                cached = list(struct.unpack("<384f", row["vector"]))
                if all(math.isfinite(value) for value in cached) and abs(sum(value * value for value in cached) - 1.0) < 0.01:
                    vectors[position] = cached
            if vectors[position] is None:
                missing.append(position)
        with self._telemetry_lock:
            self._telemetry["requests"] += 1
            self._telemetry["cache_hits"] += len(chunks) - len(missing)
            self._telemetry["cache_misses"] += len(missing)
            self._telemetry["last_request"] = {"requested": len(chunks), "hits": len(chunks) - len(missing), "misses": len(missing), "model_identity": identity}
        if missing:
            with self._telemetry_lock:
                self._telemetry["embedding_requests"] += 1
                self._telemetry["embedding_texts_submitted"] += len(missing)
            encoded = self.embedding.embed([chunks[position]["text"] for position in missing])
            with self._telemetry_lock:
                self._telemetry["embedding_requests_completed"] += 1
            with self.db.transaction() as connection:
                for position, vector in zip(missing, encoded, strict=True):
                    if len(vector) != 384:
                        raise ApiError("invalid_embedding_output", "Dimensions du vecteur invalides.", 503)
                    vectors[position] = vector
                    connection.execute("INSERT OR REPLACE INTO embedding_cache VALUES(?,?,?,?,?)", (identity, chunks[position]["hash"], struct.pack("<384f", *vector), 384, now()))
        return vectors

    async def index(self, job_id, extraction, extraction_path=None, cancelled=None):
        generation_id, chunks = await asyncio.to_thread(self.stage, job_id, extraction, extraction_path)
        job = self.db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        await self.vectors.ensure_collection()
        batch_size = self.settings.value("qdrant", "upsert_batch_size", 64)
        for offset in range(0, len(chunks), batch_size):
            if cancelled and cancelled():
                raise ApiError("cancelled", "Indexation annulée.", 409)
            batch = chunks[offset:offset + batch_size]
            vectors = await asyncio.to_thread(self.cached_embeddings, batch)
            points = [{"id": chunk["id"], "vector": {"dense": vector}, "payload": {"generation_id": generation_id, "version_id": job["version_id"], "document_id": job["document_id"], "page_indices": [chunk["page_index"]], "block_ids": [chunk["block_id"]], "text_hash": chunk["hash"]}} for chunk, vector in zip(batch, vectors, strict=True)]
            await self.vectors.upsert(points)
            await self.vectors.verify({chunk["id"]: chunk["hash"] for chunk in batch})
            self.db.execute("UPDATE jobs SET progress=?,heartbeat_at=?,stage='vectors',updated_at=? WHERE id=?", (0.65 + 0.3 * (offset + len(batch)) / max(1, len(chunks)), now(), now(), job_id))
        self.publish(job_id, generation_id, len(chunks), partial=text_loss(extraction))
        return generation_id

    def publish(self, job_id, generation_id, count, partial=False, allow_partial=False):
        with self.db.transaction() as connection:
            generation = connection.execute("SELECT * FROM index_generations WHERE id=?", (generation_id,)).fetchone()
            job = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            actual = connection.execute("SELECT count(*) FROM chunks WHERE generation_id=?", (generation_id,)).fetchone()[0]
            if not generation or actual != count or generation["expected_chunks"] != count:
                raise ApiError("index_integrity_failure", "Génération incomplète ; publication refusée.", 409)
            if job["cancel_requested"]:
                raise ApiError("cancelled", "Publication annulée.", 409)
            document = connection.execute("SELECT active_generation_id,deleted_at FROM documents WHERE id=?", (job["document_id"],)).fetchone()
            if not document or document["deleted_at"]:
                raise ApiError("source_removed", "Publication refusée : document retiré.", 409)
            state = "ready_partial" if partial else "ready"
            connection.execute("UPDATE index_generations SET state=?,actual_chunks=?,published_at=? WHERE id=?", (state, count, now() if not partial or allow_partial else None, generation_id))
            if not partial or allow_partial:
                connection.execute("UPDATE documents SET active_generation_id=?,state=?,updated_at=? WHERE id=? AND deleted_at IS NULL", (generation_id, state, now(), job["document_id"]))
                previous = document["active_generation_id"]
                if previous and previous != generation_id:
                    connection.execute("INSERT OR IGNORE INTO vector_cleanup VALUES(?,?,'pending',NULL,?,?)", (previous, "superseded", now(), now()))
            connection.execute("UPDATE jobs SET state=?,stage='complete',progress=1,lease_pid=NULL,updated_at=? WHERE id=?", (state, now(), job_id))
            # Partiel non publié : le document annonce une extraction partielle à publier, pas une indexation en cours.
            self.db.align_document_states(connection, [job["document_id"]])
