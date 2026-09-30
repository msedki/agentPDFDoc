from dataclasses import dataclass, field
import json

from .errors import ApiError
from .schemas import Scope


@dataclass
class ScopeSnapshot:
    scope: dict
    generations: list[str]
    versions: dict[str, str]
    documents: dict[str, str]
    page_indices: list[int] | None = None
    block_ids: list[str] | None = None
    spans: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)

    def as_dict(self):
        # Les avertissements accompagnent la réponse ; le snapshot persisté reste le seul périmètre autoritaire.
        return {key: value for key, value in self.__dict__.items() if key != "warnings"}

    def narrowed(self, document_id):
        generations = [g for g in self.generations if self.documents[g] == document_id]
        return ScopeSnapshot(self.scope, generations, {g: self.versions[g] for g in generations},
                             {g: document_id for g in generations}, self.page_indices, self.block_ids, self.spans)

    def sql_filter(self, alias="c"):
        if not self.generations:
            return "0", []
        parameters = list(self.generations)
        clause = f"{alias}.generation_id IN ({','.join('?' for _ in self.generations)})"
        source_conditions = []
        if self.page_indices is not None:
            if not self.page_indices:
                return "0", []
            source_conditions.append(f"cs.page_index IN ({','.join('?' for _ in self.page_indices)})")
            parameters.extend(self.page_indices)
        if self.block_ids is not None:
            if not self.block_ids:
                return "0", []
            source_conditions.append(f"cs.block_id IN ({','.join('?' for _ in self.block_ids)})")
            parameters.extend(self.block_ids)
        if source_conditions:
            clause += " AND EXISTS(SELECT 1 FROM chunk_sources cs WHERE cs.chunk_uuid=" + alias + ".chunk_uuid AND " + " AND ".join(source_conditions) + ")"
        return clause, parameters

    def vector_filter(self):
        must = [{"key": "generation_id", "match": {"any": self.generations}}]
        if self.page_indices is not None:
            must.append({"key": "page_indices", "match": {"any": self.page_indices}})
        if self.block_ids is not None:
            must.append({"key": "block_ids", "match": {"any": self.block_ids}})
        return {"must": must}


class ScopeResolver:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def document_warnings(connection, requested, rows, mode):
        """Un document demandé mais absent du snapshot est signalé ; aucun document restant est une erreur."""
        available = {row["document_id"] for row in rows}
        missing = [document_id for document_id in requested if document_id not in available]
        known = {row["id"]: row["deleted_at"] for row in connection.execute(f"SELECT id,deleted_at FROM documents WHERE id IN ({','.join('?' for _ in missing)})", missing)} if missing else {}
        details = [{"document_id": document_id, "reason": "unknown" if document_id not in known else "deleted" if known[document_id] else "not_indexed"} for document_id in missing]
        if not available:
            raise ApiError("no_document_in_scope", "Aucun document demandé n'est indexé et autorisé.", 409, {"documents": details})
        warnings = [{"code": "document_not_in_scope", **detail, "message": "Document demandé ignoré : inconnu, retiré ou non indexé."} for detail in details]
        if mode == "comparison" and len(available) < len(requested):
            warnings.append({"code": "comparison_incomplete", "requested_documents": len(requested), "compared_documents": len(available),
                             "message": "Comparaison limitée aux documents disponibles dans le périmètre."})
        return warnings

    def resolve(self, scope: Scope, mode=None):
        with self.db.connect() as connection:
            connection.execute("BEGIN")
            query = "SELECT g.id,g.version_id,v.document_id,g.extraction_revision_id,d.active_generation_id FROM index_generations g JOIN document_versions v ON v.id=g.version_id JOIN documents d ON d.id=v.document_id WHERE d.deleted_at IS NULL AND g.state IN ('ready','ready_partial') AND g.published_at IS NOT NULL"
            parameters = []
            pages = blocks = None
            spans = []
            if scope.kind in {"library", "folder", "documents"}:
                query += " AND g.id=d.active_generation_id"
                if scope.kind == "documents":
                    document_ids = sorted(set(scope.documentIds))
                    query += f" AND d.id IN ({','.join('?' for _ in document_ids)})"
                    parameters.extend(document_ids)
                if scope.kind == "folder":
                    if not connection.execute("SELECT 1 FROM folders WHERE id=?", (scope.folderId,)).fetchone():
                        raise ApiError("folder_not_found", "Dossier inconnu.", 404)
                    query += " AND d.folder_id IN (WITH RECURSIVE subtree(id) AS (SELECT id FROM folders WHERE id=? UNION ALL SELECT f.id FROM folders f JOIN subtree s ON f.parent_id=s.id) SELECT id FROM subtree)"
                    parameters.append(scope.folderId)
            else:
                version = connection.execute("SELECT v.page_count,d.deleted_at FROM document_versions v JOIN documents d ON d.id=v.document_id WHERE v.id=?", (scope.versionId,)).fetchone()
                if not version or version["deleted_at"]:
                    raise ApiError("source_removed", "Version absente ou supprimée.", 404)
                query += " AND g.version_id=?"
                parameters.append(scope.versionId)
                if scope.kind == "selection":
                    revisions = {span.extractionRevisionId for span in scope.spans}
                    if len(revisions) != 1:
                        raise ApiError("invalid_selection", "Une sélection doit appartenir à une seule révision d'extraction.")
                    query += " AND g.extraction_revision_id=?"
                    parameters.append(next(iter(revisions)))
                query += " ORDER BY g.published_at DESC LIMIT 1"
                if scope.kind == "pages":
                    if version["page_count"] is None or scope.pageEnd >= version["page_count"]:
                        raise ApiError("invalid_page_range", "Plage hors du document.")
                    pages = list(range(scope.pageStart, scope.pageEnd + 1))
            rows = connection.execute(query, parameters).fetchall()
            if scope.kind == "selection" and not rows:
                raise ApiError("extraction_revision_not_found", "Révision absente ou non publiée pour cette version.", 404)
            warnings = self.document_warnings(connection, document_ids, rows, mode) if scope.kind == "documents" else []
            # Une génération remplacée reste citable mais ses vecteurs sont retirés : la branche dense ne peut rien rendre.
            if scope.kind in {"pages", "section"} and rows and rows[0]["id"] != rows[0]["active_generation_id"] \
                    and connection.execute("SELECT 1 FROM vector_cleanup WHERE generation_id=? AND state='complete'", (rows[0]["id"],)).fetchone():
                warnings.append({"code": "dense_unavailable_for_historical_revision", "generation_id": rows[0]["id"], "version_id": rows[0]["version_id"],
                                 "extraction_revision_id": rows[0]["extraction_revision_id"],
                                 "message": "Révision historique : vecteurs retirés, recherche lexicale seule sur ce périmètre."})
            generations = [row["id"] for row in rows]
            if scope.kind == "section" and generations:
                section = connection.execute("SELECT 1 FROM sections WHERE generation_id=? AND id=?", (generations[0], scope.sectionId)).fetchone()
                if not section:
                    raise ApiError("section_not_found", "Section inconnue.", 404)
                blocks = [row[0] for row in connection.execute("SELECT id FROM blocks WHERE generation_id=? AND section_id=?", (generations[0], scope.sectionId))]
            if scope.kind == "selection" and generations:
                blocks = []
                for span in scope.spans:
                    row = connection.execute("SELECT text,page_index,extraction_revision_id,source_text_hash FROM blocks WHERE generation_id=? AND id=?", (generations[0], span.blockId)).fetchone()
                    if not row or span.endOffset > len(row["text"]) or span.extractionRevisionId != row["extraction_revision_id"] or span.blockTextSha256 != row["source_text_hash"]:
                        raise ApiError("invalid_selection", "Bloc ou offsets de sélection invalides.")
                    blocks.append(span.blockId)
                    spans.append(span.model_dump())
            return ScopeSnapshot(scope.model_dump(exclude_none=True), generations,
                                 {row["id"]: row["version_id"] for row in rows},
                                 {row["id"]: row["document_id"] for row in rows}, pages, blocks, spans, warnings)

    def source_for_chunk(self, chunk, snapshot):
        generation_id = chunk["generation_id"]
        if generation_id not in snapshot.generations:
            return None
        rows = self.db.rows("SELECT s.*,b.text,b.bbox_json,b.precision,b.kind,b.section_id,b.extraction_revision_id,b.source_text_hash,p.geometry_json FROM chunk_sources s JOIN blocks b ON b.generation_id=? AND b.id=s.block_id JOIN pages p ON p.generation_id=b.generation_id AND p.page_index=b.page_index WHERE s.chunk_uuid=? ORDER BY s.position", (generation_id, chunk["chunk_uuid"]))
        allowed = []
        for row in rows:
            if snapshot.page_indices is not None and row["page_index"] not in snapshot.page_indices:
                continue
            if snapshot.block_ids is not None and row["block_id"] not in snapshot.block_ids:
                continue
            start, end = row["start_offset"], row["end_offset"]
            selected = [span for span in snapshot.spans if span["blockId"] == row["block_id"]]
            ranges = [(max(start, span["startOffset"]), min(end, span["endOffset"])) for span in selected] if snapshot.spans else [(start, end)]
            for range_start, range_end in ranges:
                if range_start >= range_end:
                    continue
                geometry = json.loads(row["geometry_json"])
                allowed.append({"id": row["block_id"], "block_id": row["block_id"], "page_index": row["page_index"],
                                "text": row["text"][range_start:range_end], "start_offset": range_start, "end_offset": range_end,
                                "bbox": json.loads(row["bbox_json"]) if row["bbox_json"] else None,
                                "precision": row["precision"], "type": row["kind"], "page": geometry,
                                "extraction_revision_id": row["extraction_revision_id"], "source_text_hash": row["source_text_hash"]})
        if not allowed:
            return None
        return {"chunk_id": chunk["chunk_uuid"], "generation_id": generation_id, "extraction_revision_id": chunk["extraction_revision_id"],
                "version_id": snapshot.versions[generation_id], "document_id": snapshot.documents[generation_id],
                "text": "\n".join(row["text"] for row in allowed), "blocks": allowed,
                "page_indices": sorted({row["page_index"] for row in allowed}), "parent_id": chunk.get("parent_id")}

    def selected_sources(self, snapshot):
        if not snapshot.generations:
            return []
        generation_id = snapshot.generations[0]
        sources = []
        for span in snapshot.spans:
            row = self.db.one("SELECT b.*,p.geometry_json FROM blocks b JOIN pages p ON p.generation_id=b.generation_id AND p.page_index=b.page_index WHERE b.generation_id=? AND b.id=?", (generation_id, span["blockId"]))
            text = row["text"][span["startOffset"]:span["endOffset"]]
            block = {"id": row["id"], "block_id": row["id"], "text": text, "page_index": row["page_index"],
                     "start_offset": span["startOffset"], "end_offset": span["endOffset"], "type": row["kind"],
                     "bbox": json.loads(row["bbox_json"]) if row["bbox_json"] else None,
                     "precision": row["precision"], "page": json.loads(row["geometry_json"]),
                     "extraction_revision_id": row["extraction_revision_id"], "source_text_hash": row["source_text_hash"]}
            sources.append({"chunk_id": None, "generation_id": generation_id, "extraction_revision_id": row["extraction_revision_id"],
                            "version_id": snapshot.versions[generation_id], "document_id": snapshot.documents[generation_id],
                            "text": text, "blocks": [block], "page_indices": [row["page_index"]], "parent_id": row["id"]})
        return sources

    def expand_parent(self, source, snapshot, tokenizer, maximum_tokens=900):
        """Expand a block only through source records authorized by the same snapshot."""
        if snapshot.spans or source["generation_id"] not in snapshot.generations:
            return source
        expanded = []
        for block in source["blocks"]:
            if snapshot.page_indices is not None and block["page_index"] not in snapshot.page_indices:
                raise ApiError("scope_leakage", "Expansion de parent hors périmètre refusée.", 409)
            if snapshot.block_ids is not None and block["id"] not in snapshot.block_ids:
                raise ApiError("scope_leakage", "Expansion de bloc hors périmètre refusée.", 409)
            row = self.db.one("SELECT text,source_text_hash,extraction_revision_id FROM blocks WHERE generation_id=? AND id=?", (source["generation_id"], block["id"]))
            if not row or row["source_text_hash"] != block["source_text_hash"] or row["extraction_revision_id"] != block["extraction_revision_id"]:
                raise ApiError("source_text_integrity_failure", "Le parent ne correspond pas à la révision de la preuve.", 409)
            expanded.append({**block, "text": row["text"], "start_offset": 0, "end_offset": len(row["text"])})
        text = "\n".join(block["text"] for block in expanded)
        if tokenizer.count(text) > maximum_tokens:
            return source
        return {**source, "text": text, "blocks": expanded, "parent_expanded": text != source["text"]}
