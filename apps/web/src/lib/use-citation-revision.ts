"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { useWorkspace } from "./store";
import { citedRevision, revisionActionGuard } from "./provenance-revision";

export function useCitationRevision() {
  const { opened, source } = useWorkspace();
  const binding = citedRevision(opened?.versionId, source);
  // The existing tree cache also tracks publication while the library panel
  // is hidden. A new active generation must trigger a fresh revision check.
  const tree = useQuery({ queryKey: ["tree"], queryFn: ({ signal }) => api.tree(signal), enabled: binding.pinned, refetchInterval: binding.pinned ? 3000 : false });
  const activeGeneration = tree.data?.documents.find(document => document.id === opened?.documentId)?.active_generation_id;
  const latest = useQuery({
    queryKey: ["current-extraction-revision", opened?.versionId, source?.query_id, source?.source_id, binding.revision, activeGeneration],
    queryFn: ({ signal }) => api.outline(opened!.versionId, signal),
    enabled: Boolean(opened) && Boolean(binding.revision), staleTime: 0,
  });
  const currentRevision = latest.isFetching ? undefined : latest.data?.extraction_revision_id;
  const actions = revisionActionGuard(binding, currentRevision, latest.isError || latest.isSuccess && !latest.data?.extraction_revision_id);
  return { ...binding, actions };
}
