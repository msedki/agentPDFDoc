"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import { isOfficeLocation, useWorkspace } from "@/lib/store";
import { useCitationRevision } from "@/lib/use-citation-revision";
import { formatLabel } from "@/lib/document-format";
import { groupedWarningTexts } from "@/lib/warnings";
import { objects, text } from "@/lib/office-structure";
import { sourceLocationLabel } from "@/lib/source-location";
import { hasPublishedExtraction } from "@/lib/publication";
import { Button } from "./ui/button";
import { useErrorText } from "./ui/error-text";
import { DocumentTools } from "./document-tools";
import { DocxContent } from "./office-docx-reader";
import { XlsxContent } from "./office-xlsx-reader";
export function OfficeReader() {
  const state = useWorkspace(); const errorText = useErrorText(); const binding = useCitationRevision(); const [catalogCursor, setCatalogCursor] = useState(0);
  const opened = isOfficeLocation(state.opened) ? state.opened : null;
  const pinnedRevision = opened?.extractionRevisionId ?? binding.revision;
  const metadata = useQuery({ queryKey: ["document", opened?.documentId], queryFn: ({ signal }) => api.document(opened!.documentId, signal, true), enabled: Boolean(opened), staleTime: 30000, refetchInterval: query => pinnedRevision || hasPublishedExtraction(query.state.data, opened?.versionId) ? false : 3000 });
  const provenanceReady = !binding.error && Boolean(pinnedRevision || hasPublishedExtraction(metadata.data, opened?.versionId));
  const activeGeneration = metadata.data?.active_generation_id;
  const representation = useQuery({ queryKey: ["office-representation", opened?.versionId, pinnedRevision, catalogCursor, activeGeneration], queryFn: ({ signal }) => api.representation(opened!.versionId, signal, pinnedRevision, catalogCursor), enabled: Boolean(opened) && provenanceReady, staleTime: 30000 });
  const outline = useQuery({ queryKey: ["outline", opened?.versionId, representation.data?.extraction_revision_id], queryFn: ({ signal }) => api.outline(opened!.versionId, signal, representation.data!.extraction_revision_id), enabled: opened?.format === "docx" && Boolean(representation.data?.extraction_revision_id), staleTime: 30000 });
  if (!opened) return null;
  const units = representation.data?.units ?? [];
  const unit = units.find(item => item.id === opened.unitId) ?? (!opened.unitId ? units.find(item => item.metadata.visibility !== "hidden" && item.metadata.visibility !== "veryHidden") ?? units[0] : undefined);
  const unitId = opened.unitId ?? unit?.id;
  const revision = representation.data?.extraction_revision_id;
  const sourceName = state.source?.locator?.kind === "xlsx_cells" ? state.source.locator.sheet_name : undefined;
  return <div className="office-viewer" data-testid="office-reader"><div className="office-toolbar"><Button variant="ghost" size="icon" aria-label="Retour au passage précédent" disabled={!state.previous} onClick={state.back}><ArrowLeft size={16} /></Button><strong>{metadata.data?.name ?? formatLabel(opened.format)}</strong><span>{formatLabel(opened.format)}</span>{metadata.data && <DocumentTools document={metadata.data} />}
    <a className="office-original" href={api.fileUrl(opened.versionId)} download><Download size={16} />Original</a></div>
    {metadata.isError && <p role="alert" className="inline-error">Métadonnées du document indisponibles : {errorText(metadata.error)}</p>}
    {!provenanceReady && !binding.error && <p role="status" className="office-help">L'original est conservé ; sa représentation n'est pas encore publiée. Les éléments, les feuilles et leurs périmètres seront disponibles après publication. Consultez le Suivi si une extraction partielle demande votre accord.</p>}
    {binding.error && <p role="alert" className="inline-error">{binding.error}</p>}{representation.isLoading && <p role="status">Chargement de la représentation documentaire…</p>}{representation.isError && <p role="alert" className="inline-error">{errorText(representation.error)}</p>}
    {representation.data && <><div className="office-unit-controls"><label>{opened.format === "xlsx" ? "Feuille" : "Partie du document"}<select value={unitId ?? ""} onChange={event => state.officeLocation({ unitId: event.target.value, elementPath: undefined, blockId: undefined, cellRange: undefined })}>{opened.unitId && !units.some(item => item.id === opened.unitId) && <option value={opened.unitId}>{sourceName ?? opened.unitId} · source citée</option>}{units.map(item => <option value={item.id} key={item.id}>{item.title}{item.metadata.visibility === "hidden" || item.metadata.visibility === "veryHidden" ? " · masquée" : ""}</option>)}</select></label><Button size="sm" variant="ghost" disabled={catalogCursor === 0} onClick={() => setCatalogCursor(Math.max(0, catalogCursor - 50))}><ChevronLeft size={14} />Unités précédentes</Button><Button size="sm" variant="ghost" disabled={representation.data.next_cursor === null} onClick={() => setCatalogCursor(representation.data!.next_cursor!)}>Unités suivantes<ChevronRight size={14} /></Button></div>
      {state.source && <div className="source-navigation" role="status"><strong>{state.source.source_id ?? "Passage retrouvé"}</strong><span>{sourceLocationLabel(state.source)} · version <span className="mono">{opened.versionId.slice(0, 8)}</span> · révision <span className="mono">{revision?.slice(0, 8)}</span></span></div>}
      {opened.format === "docx" && <details className="office-outline"><summary>Sommaire</summary>{outline.isError ? <p role="alert" className="inline-error">{errorText(outline.error)}</p> : outline.isLoading ? <p role="status">Chargement du sommaire…</p> : !outline.data?.sections.length ? <p>Aucune section extraite dans cette révision.</p> : <nav aria-label="Sections du document">{outline.data.sections.map(section => <div key={section.id} style={{ paddingInlineStart: `${Math.min(6, Math.max(0, (section.level ?? 1) - 1)) * 12}px` }}><Button size="sm" variant="ghost" disabled={section.locator?.kind !== "docx_element" || !section.block_ids[0]} title={section.locator?.kind !== "docx_element" ? "La section ne fournit pas d'élément source navigable." : undefined} onClick={() => { if (section.locator?.kind === "docx_element") state.officeLocation({ unitId: section.locator.unit_id, blockId: section.block_ids[0], elementPath: section.locator.element_path }); }}>{section.title}</Button><Button size="sm" variant="secondary" onClick={() => state.setScope({ kind: "section", versionId: opened.versionId, extractionRevisionId: revision!, sectionId: section.id }, `${metadata.data?.name ?? "Document"} · ${section.title}`)}>Analyser</Button></div>)}</nav>}</details>}
      {unit && (unit.metadata.visibility === "hidden" || unit.metadata.visibility === "veryHidden") && <p className="inline-warning">Cette feuille est masquée dans le classeur. Elle reste consultable ; son inclusion dans un périmètre dépend de votre choix explicite.</p>}
      {opened.format === "xlsx" && <p className="office-help">Le périmètre du classeur entier inclut ses feuilles indexées, y compris celles masquées.</p>}
      <div className="office-reading-area">{unitId && revision ? opened.format === "docx" ? <DocxContent key={`${opened.versionId}:${revision}:${unitId}`} opened={opened} unitId={unitId} revision={revision} source={state.source} /> : <XlsxContent key={`${opened.versionId}:${revision}:${unitId}`} opened={opened} sheetId={unitId} revision={revision} source={state.source} sheetName={unit?.title ?? sourceName ?? unitId} unit={unit} /> : <p>Aucune unité documentaire consultable dans cette révision.</p>}
      <details className="office-metadata"><summary>Métadonnées du document</summary>{opened.format === "xlsx" && <><p>Système de dates : {text(representation.data.metadata.date_system) || "Non renseigné"}. Le programme ne recalcule aucune formule.</p><h3>Noms définis</h3>{objects(representation.data.metadata.defined_names).length ? objects(representation.data.metadata.defined_names).slice(0, 100).map((name, index) => <p key={index}>{text(name.name)} : {text(name.text ?? name.value ?? name.reference)}</p>) : <p>Aucun nom défini enregistré.</p>}</>}<p>Les limites et les avertissements portent sur l'extraction publiée ; ils ne certifient pas la complétude métier du document.</p></details></div>
      {groupedWarningTexts(representation.data.warnings).map(message => <p className="inline-warning" key={message}>{message}</p>)}
    </>}
  </div>;
}
