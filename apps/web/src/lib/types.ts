/** API v1 boundary, aligned with packages/contracts/contracts.json (schema_version 2). */
export type Scope =
  | { kind: "library" }
  | { kind: "folder"; folderId: string; recursive: true }
  | { kind: "documents"; documentIds: string[] }
  | { kind: "section"; versionId: string; sectionId: string }
  | { kind: "pages"; versionId: string; pageStart: number; pageEnd: number }
  | { kind: "selection"; versionId: string; spans: SelectedSpan[] };
export type SelectedSpan = { extractionRevisionId: string; blockId: string; blockTextSha256: string; offsetUnit: "unicode_code_point"; startOffset: number; endOffset: number };
export type Precision = "span" | "block" | "table" | "page";
export type Bbox = [number, number, number, number];
export type ApiWarning = string | { code?: string; message?: string; [key: string]: unknown };
export type DocumentState = "imported" | "queued" | "extracting" | "ocr" | "indexing" | "ready" | "ready_partial" | "error" | "deleted";
export interface Folder { id: string; parent_id: string | null; name: string; path: string }
export interface DocumentRecord {
  id: string; folder_id: string | null; name: string; relative_path: string; state: DocumentState;
  active_version_id?: string | null; version_id?: string | null; active_generation_id?: string | null;
  sha256?: string | null; page_count: number | null; coverage?: { total: number; processed: number; ocr: number };
  warnings?: ApiWarning[]; error?: string;
}
export interface VersionRecord { id: string; document_id: string; sha256: string; page_count: number | null; created_at: string; file_url?: string }
export interface DocumentDetail extends DocumentRecord { versions: VersionRecord[]; jobs?: Job[] }
export interface LibraryTree { folders: Folder[]; documents: DocumentRecord[]; total_documents?: number; total?: number; next_cursor?: string | null }
export interface Block {
  id: string; version_id?: string; page_index: number; type?: string; kind?: string; text: string;
  raw_text?: string; bbox?: Bbox | null; precision: Precision; section_id?: string | null;
  extraction_revision_id?: string; source_text_hash?: string; source_text_sha256?: string;
  metadata?: { extraction_method?: "native" | "ocr" | "mixed" | "unknown"; ocr_used?: boolean; ocr_spans?: { start_offset: number; end_offset: number; bbox: Bbox; precision: "span" }[]; [key: string]: unknown };
  spans?: { start_offset: number; end_offset: number; bbox?: Bbox }[];
}
export interface PageRecord {
  page_index: number; page_number?: number; width: number; height: number; rotation: number;
  crop_box: Bbox | null; media_box: Bbox | null; effective_box?: Bbox; label?: string | null; orientation_correction?: number | null;
  extraction_state?: "native" | "ocr" | "mixed" | "blank" | "error";
  ocr_regions?: Bbox[];
}
export interface PageBlocks { version_id: string; generation_id?: string; extraction_revision_id?: string; page: PageRecord; blocks: Block[]; warnings: ApiWarning[] }
export interface Section { id: string; title: string; page_index: number; block_ids: string[] }
export interface Outline { version_id: string; generation_id?: string; extraction_revision_id?: string; sections: Section[] }
export interface Source {
  source_id?: string; query_id?: string; document_id: string; version_id: string;
  generation_id?: string; extraction_revision_id?: string;
  name?: string; document_name?: string; page_index?: number; page_number?: number; page_indices?: number[];
  label?: string | null; block_ids?: string[]; text: string; bboxes?: Bbox[]; precision?: Precision;
  blocks?: Block[];
  citation_url?: string; warnings?: ApiWarning[];
}
export interface SearchResult { source?: Source; source_id?: string; score?: number; text?: string; [key: string]: unknown }
export interface SearchResponse { results: (Source | SearchResult)[]; warnings: ApiWarning[]; scope_snapshot: unknown; elapsed_ms: number }
export interface QueryCreated { query_id: string; events_url: string; conversation_id?: string }
export interface Job { id: string; document_id?: string; version_id?: string; generation_id?: string; state?: string; status?: string; stage?: string; progress?: number; coverage?: { total: number; processed: number; ocr?: number }; published?: boolean; published_at?: string | null; active?: boolean; warnings?: ApiWarning[]; error?: string; error_message?: string; message?: string }
export interface JobsResponse { jobs: Job[] }
export interface Readiness { ready?: boolean; status?: string; blockers?: string[]; [key: string]: unknown }
export type StreamEvent = { id: string; type: string; data: Record<string, unknown> };
export type QueryState = {
  id: string; question: string; scope: Scope; scopeLabel: string; mode: string; text: string;
  status: string; connection: "connecting" | "connected" | "reconnecting" | "closed";
  sources: Source[]; warnings: string[]; error?: string; lastEventId: string; finishReason?: string;
};
