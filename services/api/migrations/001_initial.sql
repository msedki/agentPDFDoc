PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES(1);
CREATE TABLE IF NOT EXISTS folders(
 id TEXT PRIMARY KEY,parent_id TEXT REFERENCES folders(id),name TEXT NOT NULL,path TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS documents(
 id TEXT PRIMARY KEY,folder_id TEXT REFERENCES folders(id),name TEXT NOT NULL,
 relative_path TEXT NOT NULL UNIQUE,state TEXT NOT NULL DEFAULT 'queued',
 active_generation_id TEXT,deleted_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_versions(
 id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES documents(id),sha256 TEXT NOT NULL,
 blob_path TEXT NOT NULL,page_count INTEGER,metadata_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,
 UNIQUE(document_id,sha256)
);
CREATE TABLE IF NOT EXISTS extraction_revisions(
 id TEXT PRIMARY KEY,version_id TEXT NOT NULL REFERENCES document_versions(id),fingerprint TEXT NOT NULL,
 source_hash TEXT NOT NULL,path TEXT,created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS index_generations(
 id TEXT PRIMARY KEY,version_id TEXT NOT NULL REFERENCES document_versions(id),fingerprint TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'staging',expected_chunks INTEGER NOT NULL DEFAULT 0,
 actual_chunks INTEGER NOT NULL DEFAULT 0,extraction_path TEXT,coverage_json TEXT NOT NULL DEFAULT '{}',
 warnings_json TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL,published_at TEXT,
 extraction_revision_id TEXT REFERENCES extraction_revisions(id)
);
CREATE INDEX IF NOT EXISTS generation_version ON index_generations(version_id,state);
CREATE TABLE IF NOT EXISTS pages(
 generation_id TEXT NOT NULL REFERENCES index_generations(id),page_index INTEGER NOT NULL,
 geometry_json TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'ready',PRIMARY KEY(generation_id,page_index)
);
CREATE TABLE IF NOT EXISTS sections(
 generation_id TEXT NOT NULL REFERENCES index_generations(id),id TEXT NOT NULL,title TEXT NOT NULL,
 page_index INTEGER,block_ids_json TEXT NOT NULL DEFAULT '[]',PRIMARY KEY(generation_id,id)
);
CREATE TABLE IF NOT EXISTS blocks(
 generation_id TEXT NOT NULL REFERENCES index_generations(id),id TEXT NOT NULL,page_index INTEGER NOT NULL,
 kind TEXT NOT NULL,text TEXT NOT NULL,bbox_json TEXT,precision TEXT NOT NULL,section_id TEXT,
 metadata_json TEXT NOT NULL DEFAULT '{}',extraction_revision_id TEXT NOT NULL REFERENCES extraction_revisions(id),
 source_text_hash TEXT NOT NULL,PRIMARY KEY(generation_id,id)
);
CREATE TABLE IF NOT EXISTS tables_data(
 generation_id TEXT NOT NULL REFERENCES index_generations(id),id TEXT NOT NULL,data_json TEXT NOT NULL,
 PRIMARY KEY(generation_id,id)
);
CREATE TABLE IF NOT EXISTS chunks(
 id INTEGER PRIMARY KEY,chunk_uuid TEXT NOT NULL UNIQUE,
 generation_id TEXT NOT NULL REFERENCES index_generations(id),version_id TEXT NOT NULL REFERENCES document_versions(id),
 parent_id TEXT,section_title TEXT NOT NULL DEFAULT '',text TEXT NOT NULL,
 e5_tokens INTEGER NOT NULL,llm_tokens INTEGER NOT NULL DEFAULT 0,text_hash TEXT NOT NULL,
 extraction_revision_id TEXT NOT NULL REFERENCES extraction_revisions(id)
);
CREATE INDEX IF NOT EXISTS chunks_generation ON chunks(generation_id);
CREATE TABLE IF NOT EXISTS chunk_sources(
 chunk_uuid TEXT NOT NULL REFERENCES chunks(chunk_uuid),block_id TEXT NOT NULL,page_index INTEGER NOT NULL,
 start_offset INTEGER NOT NULL,end_offset INTEGER NOT NULL,position INTEGER NOT NULL,
 PRIMARY KEY(chunk_uuid,position)
);
CREATE TABLE IF NOT EXISTS identifiers(
 chunk_uuid TEXT NOT NULL REFERENCES chunks(chunk_uuid),raw TEXT NOT NULL,normalized TEXT NOT NULL,
 PRIMARY KEY(chunk_uuid,normalized)
);
CREATE INDEX IF NOT EXISTS identifier_normalized ON identifiers(normalized);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
 section_title,text,content='chunks',content_rowid='id',tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
 INSERT INTO chunks_fts(rowid,section_title,text) VALUES(new.id,new.section_title,new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
 INSERT INTO chunks_fts(chunks_fts,rowid,section_title,text) VALUES('delete',old.id,old.section_title,old.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
 INSERT INTO chunks_fts(chunks_fts,rowid,section_title,text) VALUES('delete',old.id,old.section_title,old.text);
 INSERT INTO chunks_fts(rowid,section_title,text) VALUES(new.id,new.section_title,new.text);
END;
CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES documents(id),version_id TEXT NOT NULL REFERENCES document_versions(id),
 generation_id TEXT REFERENCES index_generations(id),state TEXT NOT NULL,stage TEXT NOT NULL,
 progress REAL NOT NULL DEFAULT 0,attempts INTEGER NOT NULL DEFAULT 0,checkpoint_json TEXT NOT NULL DEFAULT '{}',
 error_code TEXT,error_message TEXT,lease_pid INTEGER,heartbeat_at TEXT,cancel_requested INTEGER NOT NULL DEFAULT 0,
 pause_requested INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state,created_at);
CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS query_runs(
 id TEXT PRIMARY KEY,conversation_id TEXT REFERENCES conversations(id),question TEXT NOT NULL,
 scope_json TEXT NOT NULL,snapshot_json TEXT NOT NULL,state TEXT NOT NULL,answer TEXT NOT NULL DEFAULT '',
 resolution_json TEXT NOT NULL DEFAULT '{}',
 warnings_json TEXT NOT NULL DEFAULT '[]',metrics_json TEXT NOT NULL DEFAULT '{}',last_event_id INTEGER NOT NULL DEFAULT 0,
 cancel_requested INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages(
 id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL REFERENCES conversations(id),query_id TEXT NOT NULL REFERENCES query_runs(id),
 role TEXT NOT NULL,content TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS citations(
 query_id TEXT NOT NULL REFERENCES query_runs(id),source_id TEXT NOT NULL,version_id TEXT NOT NULL REFERENCES document_versions(id),
 document_id TEXT NOT NULL REFERENCES documents(id),source_json TEXT NOT NULL,PRIMARY KEY(query_id,source_id)
);
CREATE TABLE IF NOT EXISTS events(
 query_id TEXT NOT NULL REFERENCES query_runs(id),id INTEGER NOT NULL,type TEXT NOT NULL,data_json TEXT NOT NULL,
 created_at TEXT NOT NULL,PRIMARY KEY(query_id,id)
);
