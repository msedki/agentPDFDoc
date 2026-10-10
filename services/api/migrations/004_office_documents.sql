-- Native Office locations are not PDF pages. Existing PDF columns and values
-- are copied explicitly; FTS/chunks/citations and their IDs remain untouched.
ALTER TABLE document_versions ADD COLUMN format TEXT NOT NULL DEFAULT 'pdf' CHECK(format IN ('pdf','docx','xlsx'));
ALTER TABLE document_versions ADD COLUMN mime_type TEXT NOT NULL DEFAULT 'application/pdf';

CREATE TABLE blocks_v4(
 generation_id TEXT NOT NULL REFERENCES index_generations(id),id TEXT NOT NULL,page_index INTEGER CHECK(page_index IS NULL OR page_index>=0),
 kind TEXT NOT NULL,text TEXT NOT NULL,bbox_json TEXT,precision TEXT NOT NULL,section_id TEXT,
 metadata_json TEXT NOT NULL DEFAULT '{}',extraction_revision_id TEXT NOT NULL REFERENCES extraction_revisions(id),
 source_text_hash TEXT NOT NULL,PRIMARY KEY(generation_id,id)
);
INSERT INTO blocks_v4(generation_id,id,page_index,kind,text,bbox_json,precision,section_id,metadata_json,extraction_revision_id,source_text_hash)
 SELECT generation_id,id,page_index,kind,text,bbox_json,precision,section_id,metadata_json,extraction_revision_id,source_text_hash FROM blocks;
DROP TABLE blocks;
ALTER TABLE blocks_v4 RENAME TO blocks;

CREATE TABLE chunk_sources_v4(
 chunk_uuid TEXT NOT NULL REFERENCES chunks(chunk_uuid),block_id TEXT NOT NULL,page_index INTEGER CHECK(page_index IS NULL OR page_index>=0),
 start_offset INTEGER NOT NULL,end_offset INTEGER NOT NULL,position INTEGER NOT NULL,
 PRIMARY KEY(chunk_uuid,position)
);
INSERT INTO chunk_sources_v4(chunk_uuid,block_id,page_index,start_offset,end_offset,position)
 SELECT chunk_uuid,block_id,page_index,start_offset,end_offset,position FROM chunk_sources;
DROP TABLE chunk_sources;
ALTER TABLE chunk_sources_v4 RENAME TO chunk_sources;

CREATE TABLE office_units(
 generation_id TEXT NOT NULL REFERENCES index_generations(id),id TEXT NOT NULL,kind TEXT NOT NULL,
 title TEXT NOT NULL,part TEXT NOT NULL,order_index INTEGER NOT NULL,parent_id TEXT,
 metadata_json TEXT NOT NULL DEFAULT '{}',PRIMARY KEY(generation_id,id)
);
CREATE TABLE office_documents(
 generation_id TEXT PRIMARY KEY REFERENCES index_generations(id),metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX office_units_order ON office_units(generation_id,order_index,id);
CREATE TABLE office_unit_blocks(
 generation_id TEXT NOT NULL,unit_id TEXT NOT NULL,block_id TEXT NOT NULL,order_index INTEGER NOT NULL,
 PRIMARY KEY(generation_id,unit_id,block_id),
 FOREIGN KEY(generation_id,unit_id) REFERENCES office_units(generation_id,id),
 FOREIGN KEY(generation_id,block_id) REFERENCES blocks(generation_id,id)
);
CREATE INDEX office_blocks_order ON office_unit_blocks(generation_id,unit_id,order_index);
CREATE TABLE office_cells(
 generation_id TEXT NOT NULL,unit_id TEXT NOT NULL,row_index INTEGER NOT NULL,column_index INTEGER NOT NULL,
 address TEXT NOT NULL,data_json TEXT NOT NULL,
 PRIMARY KEY(generation_id,unit_id,row_index,column_index),
 FOREIGN KEY(generation_id,unit_id) REFERENCES office_units(generation_id,id)
);
CREATE TABLE office_cell_bindings(
 generation_id TEXT NOT NULL,unit_id TEXT NOT NULL,row_index INTEGER NOT NULL,column_index INTEGER NOT NULL,
 block_id TEXT NOT NULL,start_offset INTEGER NOT NULL,end_offset INTEGER NOT NULL,field TEXT NOT NULL,
 PRIMARY KEY(generation_id,unit_id,row_index,column_index,block_id,start_offset,end_offset,field),
 FOREIGN KEY(generation_id,unit_id,row_index,column_index) REFERENCES office_cells(generation_id,unit_id,row_index,column_index),
 FOREIGN KEY(generation_id,block_id) REFERENCES blocks(generation_id,id)
);
CREATE INDEX office_bindings_block ON office_cell_bindings(generation_id,block_id);
INSERT INTO schema_version VALUES(4);
