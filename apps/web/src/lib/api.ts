import type { DocumentDetail, JobsResponse, LibraryTree, Outline, PageBlocks, QueryCreated, Readiness, Scope, SearchResponse, Source } from "./types";
import { blocksPath, outlinePath, verifyPinnedBlocks, verifyPinnedOutline } from "./provenance-revision";

const prefix = "/api/v1";
export class ApiError extends Error {
  constructor(public code: string, message: string, public requestId?: string) { super(message); this.name = "ApiError"; }
}
export function sameOriginPath(path: string): string {
  if (!path.startsWith("/api/v1/") || path.startsWith("//") || /[\r\n]/.test(path)) throw new ApiError("INVALID_URL", "L'adresse de la ressource n'est pas autorisée.");
  const url = new URL(path, typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1");
  if (!url.pathname.startsWith("/api/v1/")) throw new ApiError("INVALID_URL", "Adresse de ressource invalide.");
  return url.pathname + url.search;
}
async function request<T>(path: string, options: RequestInit = {}, acceptedStatuses: number[] = []): Promise<T> {
  const response = await fetch(sameOriginPath(prefix + path), { ...options, credentials: "same-origin", cache: "no-store", headers: { Accept: "application/json", ...options.headers } });
  if (!response.ok && !acceptedStatuses.includes(response.status)) {
    const data = await response.json().catch(() => null);
    throw new ApiError(data?.code ?? `HTTP_${response.status}`, data?.message ?? `Le service répond ${response.status}.`, data?.request_id);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
const post = <T>(path: string, data: unknown) => request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
export const api = {
  async readiness(signal?: AbortSignal): Promise<Readiness> {
    const value = await request<Readiness>("/readiness", { signal }, [503]);
    return { ...value, ready: value.ready ?? value.status === "ready" };
  },
  async tree(signal?: AbortSignal): Promise<LibraryTree> {
    const folders = new Map<string, LibraryTree["folders"][number]>();
    const documents: LibraryTree["documents"] = [];
    let cursor: string | null | undefined = null;
    let offset = 0;
    let total = 0;
    do {
      const page: LibraryTree = await request<LibraryTree>(`/library/tree?limit=100&offset=${offset}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, { signal });
      for (const folder of page.folders) folders.set(folder.id, folder);
      documents.push(...page.documents);
      total = page.total_documents ?? page.total ?? documents.length;
      cursor = page.next_cursor;
      offset += page.documents.length;
      if (!page.documents.length) break;
      if (cursor === undefined && offset < total) cursor = String(offset);
    } while (cursor && documents.length < 10000);
    return { folders: [...folders.values()], documents, total_documents: total };
  },
  document: (id: string, signal?: AbortSignal) => request<DocumentDetail>(`/documents/${encodeURIComponent(id)}`, { signal }),
  outline: (versionId: string, signal?: AbortSignal, revision?: string | null) => request<Outline>(outlinePath(versionId, revision), { signal }).then(result => verifyPinnedOutline(result, versionId, revision)),
  blocks: (versionId: string, page: number, signal?: AbortSignal, revision?: string | null) => request<PageBlocks>(blocksPath(versionId, page, revision), { signal }).then(result => verifyPinnedBlocks(result, versionId, page, revision)),
  jobs: (signal?: AbortSignal) => request<JobsResponse>("/jobs", { signal }),
  import: (files: File[], onProgress?: (progress: number) => void) => new Promise<unknown>((resolve, reject) => {
    const form = new FormData();
    for (const file of files) form.append("files", file, file.name);
    form.append("relative_paths", JSON.stringify(files.map(file => file.webkitRelativePath || file.name)));
    const xhr = new XMLHttpRequest();
    xhr.open("POST", prefix + "/documents/import");
    xhr.withCredentials = true;
    xhr.upload.onprogress = event => { if (event.lengthComputable) onProgress?.(event.loaded / event.total); };
    xhr.onerror = () => reject(new ApiError("NETWORK_ERROR", "Import interrompu : connexion au service perdue."));
    xhr.onload = () => {
      let data: Record<string, unknown> = {};
      try { data = JSON.parse(xhr.responseText); } catch { /* The HTTP status still conveys failure. */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new ApiError(String(data.code ?? `HTTP_${xhr.status}`), String(data.message ?? "Import refusé par le service.")));
    };
    xhr.send(form);
  }),
  search: (question: string, scope: Scope) => post<SearchResponse>("/search", { question, scope }),
  query: (question: string, scope: Scope, mode: string, conversationId: string | null = null, followupOf?: string, focus?: { query_id: string; source_id: string }) => post<QueryCreated>("/queries", { question, scope, mode, conversation_id: conversationId, ...(followupOf ? { followup_of: followupOf } : {}), ...(focus ? { focus } : {}) }),
  cancelQuery: (id: string) => post(`/queries/${encodeURIComponent(id)}/cancel`, {}),
  cancelJob: (id: string) => post(`/jobs/${encodeURIComponent(id)}/cancel`, {}),
  pauseJob: (id: string) => post(`/jobs/${encodeURIComponent(id)}/pause`, {}),
  resumeJob: (id: string) => post(`/jobs/${encodeURIComponent(id)}/resume`, {}),
  publishPartial: (id: string) => post(`/jobs/${encodeURIComponent(id)}/publish-partial`, {}),
  runtimeMode: (mode: "interactive" | "ingestion") => post("/runtime/mode", { mode }),
  reindex: (id: string) => post(`/documents/${encodeURIComponent(id)}/reindex`, {}),
  remove: (id: string) => request(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
  citation: (queryId: string, sourceId: string) => request<Source>(`/citations/${encodeURIComponent(queryId)}/${encodeURIComponent(sourceId)}`),
  fileUrl: (versionId: string) => prefix + `/versions/${encodeURIComponent(versionId)}/file`,
};
