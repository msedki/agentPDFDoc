-- Référence SQLite exécutable pour tester FTS5 ; compléter par les migrations métier.
-- Les generations actives autoritaires sont obtenues depuis les tables métier.
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
PRAGMA cache_size=-32768;

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    chunk_uuid TEXT NOT NULL UNIQUE,
    generation_id TEXT NOT NULL,
    version_id TEXT NOT NULL,
    section_title TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_generation ON chunks(generation_id);
CREATE INDEX IF NOT EXISTS idx_chunks_version ON chunks(version_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    section_title,
    text,
    content='chunks',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, section_title, text)
  VALUES (new.id, new.section_title, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, section_title, text)
  VALUES ('delete', old.id, old.section_title, old.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, section_title, text)
  VALUES ('delete', old.id, old.section_title, old.text);
  INSERT INTO chunks_fts(rowid, section_title, text)
  VALUES (new.id, new.section_title, new.text);
END;

-- Pour un scope étendu, joindre à une table temporaire de générations permises
-- ou produire une clause IN avec paramètres. Ne pas interpoler les valeurs.
-- SELECT c.chunk_uuid, bm25(chunks_fts, 2.0, 1.0) AS lexical_score
-- FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid
-- WHERE chunks_fts MATCH :match_expr
--   AND c.generation_id = :allowed_generation
-- ORDER BY lexical_score ASC, c.id ASC
-- LIMIT 24;
