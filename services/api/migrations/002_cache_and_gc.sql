CREATE TABLE IF NOT EXISTS embedding_cache(
 model_identity TEXT NOT NULL,text_hash TEXT NOT NULL,vector BLOB NOT NULL,
 dimensions INTEGER NOT NULL,created_at TEXT NOT NULL,
 PRIMARY KEY(model_identity,text_hash)
);
CREATE TABLE IF NOT EXISTS vector_cleanup(
 generation_id TEXT PRIMARY KEY REFERENCES index_generations(id),
 reason TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',
 error_code TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_version VALUES(2);
