/**
 * API v1 boundary, aligned with packages/contracts/contracts.json (schema_version 3).
 * Les listes d'états et d'événements ci-dessous sont comparées au contrat par tests/unit/contracts.test.ts.
 */
export type Scope =
  | { kind: "library" }
  | { kind: "folder"; folderId: string; recursive: true }
  | { kind: "documents"; documentIds: string[] }
  | { kind: "section"; versionId: string; sectionId: string; extractionRevisionId?: string }
  | { kind: "pages"; versionId: string; pageStart: number; pageEnd: number }
  | { kind: "selection"; versionId: string; spans: SelectedSpan[] }
  | { kind: "sheet"; versionId: string; extractionRevisionId: string; sheetId: string }
  | ({ kind: "cell_range"; versionId: string; extractionRevisionId: string; sheetId: string } & CellRange);
export type SelectedSpan = { extractionRevisionId: string; blockId: string; blockTextSha256: string; offsetUnit: "unicode_code_point"; startOffset: number; endOffset: number };
export type DocumentFormat = "pdf" | "docx" | "xlsx";
export type CellRange = { rowStart: number; rowEnd: number; columnStart: number; columnEnd: number };
export type DocxLocator = { kind: "docx_element"; unit_id: string; part: string; element_path: string };
export type XlsxLocator = { kind: "xlsx_cells"; unit_id: string; sheet_id: string; sheet_name: string; part: string; cell_range: string; row_start: number; row_end: number; column_start: number; column_end: number };
export type SourceLocator = DocxLocator | XlsxLocator | { kind: "pdf_page"; page_index: number };
export type Precision = "span" | "block" | "table" | "page" | "element" | "cell" | "range";
export type Bbox = [number, number, number, number];
export type ApiWarning = string | { code?: string; message?: string; [key: string]: unknown };
/** `document.state` du contrat. */
export const DOCUMENT_STATES = ["queued", "extracting", "indexing", "paused", "cancelled", "error", "ready", "ready_partial", "deleted"] as const;
export type DocumentState = typeof DOCUMENT_STATES[number];
/** `job.state` du contrat ; `Job.state` reste une chaîne pour afficher aussi un état inconnu, avec son code. */
export const JOB_STATES = ["queued", "extracting", "indexing", "pausing", "paused", "cancelling", "cancelled", "error", "ready", "ready_partial"] as const;
export type JobState = typeof JOB_STATES[number];
/** `query_events.types` du contrat : événements SSE d'une question. */
export const QUERY_EVENT_TYPES = ["status", "needs_clarification", "sources", "delta", "warning", "done", "error", "cancelled"] as const;
export type QueryEventType = typeof QUERY_EVENT_TYPES[number];
export interface Folder { id: string; parent_id: string | null; name: string; path: string }
export interface DocumentRecord {
  id: string; folder_id: string | null; name: string; relative_path: string; state: DocumentState;
  active_version_id?: string | null; version_id?: string | null; active_generation_id?: string | null;
  sha256?: string | null; page_count: number | null; coverage?: { total: number; processed: number; ocr: number };
  format?: DocumentFormat; active_extraction_revision_id?: string | null;
  warnings?: ApiWarning[]; error?: string;
}
export interface VersionRecord { id: string; document_id: string; sha256: string; page_count: number | null; created_at: string; file_url?: string; format?: DocumentFormat; mime_type?: string }
export interface DocumentDetail extends DocumentRecord { versions: VersionRecord[]; jobs?: Job[] }
export interface LibraryTree { folders: Folder[]; documents: DocumentRecord[]; total_documents?: number; total?: number; next_cursor?: string | null }
export interface Block {
  id: string; version_id?: string; page_index: number | null; type?: string; kind?: string; text: string;
  format?: DocumentFormat; locator?: SourceLocator; structure?: Record<string, unknown>; source_text?: string;
  raw_text?: string; bbox?: Bbox | null; precision: Precision; section_id?: string | null;
  extraction_revision_id?: string; source_text_hash?: string; source_text_sha256?: string;
  /** Méthode d'extraction du bloc dans une source ou une citation (contrat R26) ; absente = inconnue. */
  extraction_method?: string;
  metadata?: { extraction_method?: "native" | "office_native" | "ocr" | "mixed" | "unknown"; ocr_used?: boolean; ocr_spans?: { start_offset: number; end_offset: number; bbox: Bbox; precision: "span" }[]; [key: string]: unknown };
  spans?: { start_offset: number; end_offset: number; bbox?: Bbox }[];
}
export interface PageRecord {
  page_index: number; page_number?: number; width: number; height: number; rotation: number;
  crop_box: Bbox | null; media_box: Bbox | null; effective_box?: Bbox; label?: string | null; orientation_correction?: number | null;
  extraction_state?: "native" | "ocr" | "mixed" | "blank" | "error";
  ocr_regions?: Bbox[];
}
export interface PageBlocks { version_id: string; generation_id?: string; extraction_revision_id?: string; page: PageRecord; blocks: Block[]; warnings: ApiWarning[] }
export interface Section { id: string; title: string; page_index: number | null; block_ids: string[]; locator?: SourceLocator; parent_id?: string | null; level?: number }
export interface Outline { version_id: string; generation_id?: string; extraction_revision_id?: string; sections: Section[] }
export interface Source {
  source_id?: string; query_id?: string; document_id: string; version_id: string;
  generation_id?: string; extraction_revision_id?: string;
  name?: string; document_name?: string; page_index?: number | null; page_number?: number | null; page_indices?: number[];
  format?: DocumentFormat; locator?: SourceLocator;
  label?: string | null; block_ids?: string[]; text: string; bboxes?: Bbox[]; precision?: Precision;
  blocks?: Block[];
  citation_url?: string; warnings?: ApiWarning[];
  /** Méthodes d'extraction des blocs de la source (native, office_native, ocr, mixed, unknown) ; absentes avant R26 = inconnues. */
  extraction_methods?: string[];
}
export interface SearchResult { source?: Source; source_id?: string; score?: number; text?: string; [key: string]: unknown }
export interface SearchResponse { results: (Source | SearchResult)[]; warnings: ApiWarning[]; scope_snapshot: unknown; elapsed_ms: number }
export interface QueryCreated { query_id: string; events_url: string; conversation_id?: string; state?: "needs_clarification" }
/** Métadonnées persistées : le mode historique n'est pas enregistré et reste inconnu. */
export interface HistoricalQuerySummary {
  query_id: string; conversation_id: string | null; question: string; state: string; mode: null;
  last_event_id: number; created_at: string; updated_at: string; events_url: string;
}
export interface QueryHistoryPage { queries: HistoricalQuerySummary[]; next_cursor: string | null }
export interface HistoricalQuery extends HistoricalQuerySummary {
  scope: Scope; answer: string; warnings: ApiWarning[]; metrics: Record<string, unknown>;
  resolution: Record<string, unknown>;
}
/** `reindex_response` du contrat : `resume_required`, avec `job_state` `paused`, signale le traitement en pause de cette version, à reprendre. */
export interface ReindexResponse { job_id: string; version_id?: string; reused: boolean; job_state?: string; resume_required?: boolean }
export interface Job { id: string; document_id?: string; version_id?: string; generation_id?: string; state?: string; status?: string; stage?: string; progress?: number; coverage?: { total: number; processed: number; ocr?: number }; published?: boolean; published_at?: string | null; active?: boolean; warnings?: ApiWarning[]; error?: string; error_message?: string; message?: string }
/** `jobs_response.generation.device` du contrat (W025) : matériel retenu pour la génération des réponses. */
export const GENERATION_DEVICES = ["gpu", "cpu"] as const;
export type GenerationDevice = typeof GENERATION_DEVICES[number];
/**
 * `fallback` : un échec du chargement sur le GPU a fait passer l'instance sur le processeur jusqu'à son redémarrage.
 * `processor` : dernière occupation du modèle relue par l'API, colonne PROCESSOR d'`ollama ps` (`100% GPU`,
 * `100% CPU`, `25%/75% CPU/GPU` ou `Unknown`), null tant que le modèle n'a pas été vu chargé.
 */
export interface Generation { device: GenerationDevice; fallback: boolean; processor: string | null; model?: string }
/** `generation` est null quand l'API tourne avec un double de la passerelle Ollama, absent d'une API antérieure à W025. */
export interface JobsResponse { jobs: Job[]; total?: number; runtime_mode?: "interactive" | "ingestion" | null; generation?: Generation | null }
export interface Readiness { ready?: boolean; status?: string; blockers?: string[]; [key: string]: unknown }
export interface OfficeUnit { id: string; kind: string; title: string; part: string; order_index: number; parent_id?: string | null; metadata: Record<string, unknown> }
export interface OfficeRepresentation {
  version_id: string; generation_id?: string; extraction_revision_id: string; format: "docx" | "xlsx";
  units: OfficeUnit[]; next_cursor: number | null; total: number; metadata: Record<string, unknown>;
  coverage: Record<string, unknown>; warnings: ApiWarning[]; limits: Record<string, unknown>;
}
export interface OfficeBlocks { version_id: string; generation_id?: string; extraction_revision_id: string; unit: OfficeUnit; blocks: Block[]; cursor?: number; next_cursor: number | null; total: number; warnings?: ApiWarning[] }
export interface OfficeCell {
  address: string; row: number; column: number; data_type: string; raw_value?: unknown; value?: unknown; display_text?: string;
  number_format?: string; formula?: { raw_text?: string | null; effective_text?: string | null; type?: string; [key: string]: unknown } | null; cached_value?: unknown; cached_present: boolean; cache_freshness: "unknown" | "absent";
  [key: string]: unknown;
}
export interface OfficeCells {
  version_id: string; generation_id?: string; extraction_revision_id: string; sheet_id: string;
  bounds: { row_start: number; row_end: number; column_start: number; column_end: number };
  cells: OfficeCell[]; tables?: Record<string, unknown>[]; metadata: Record<string, unknown>; warnings: ApiWarning[];
}
export type StreamEvent = { id: string; type: string; data: Record<string, unknown> };
export type QueryState = {
  id: string; question: string; scope: Scope; scopeLabel: string; mode: string | null; text: string;
  status: string; connection: "connecting" | "connected" | "reconnecting" | "closed";
  sources: Source[]; warnings: ApiWarning[]; error?: string; lastEventId: string; finishReason?: string; historicalState?: string;
};
