"use client";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronDown, ChevronLeft, ChevronRight, CircleAlert, FileText, List, RotateCw, Search, ZoomIn, ZoomOut } from "lucide-react";
import type { PDFDocumentProxy, PDFPageProxy, RenderTask } from "pdfjs-dist";
import { api } from "@/lib/api";
import { loadPdfJs, PdfJsLoadError } from "@/lib/pdfjs";
import { useWorkspace } from "@/lib/store";
import { boundedCanvasSize, reconcileSelection, visiblePageWindow, wholeBlockSpan } from "@/lib/selection";
import { hasExtractedText, ocrOverlays, pageTextCaption } from "@/lib/ocr-overlay";
import { hasPublishedExtraction } from "@/lib/publication";
import { findNextPdfPage, samePdfReading } from "@/lib/pdf-search";
import { pdfPageAtScroll, pdfPageLayout, pdfScrollTarget, type PdfScrollLayout } from "@/lib/pdf-navigation";
import { groupedWarningTexts } from "@/lib/warnings";
import { blocksKey, citedRevision } from "@/lib/provenance-revision";
import { useCitationRevision } from "@/lib/use-citation-revision";
import { sourcePrecisionLabel, sourceRegionBoxes } from "@/lib/source-location";
import type { Bbox, Source } from "@/lib/types";
import { Button } from "./ui/button";
import { DocumentTools } from "./document-tools";
import { ExtractionBadge } from "./extraction-badge";
import { useErrorText, type Failure } from "./ui/error-text";
import { PanelEmpty, PanelError, PanelHeader, PanelLoading } from "./ui/panel";

const GLOBAL_PIXEL_BUDGET = 24_000_000;
const MAX_CANVASES = 5;
type Viewport = ReturnType<PDFPageProxy["getViewport"]>;

export function viewportRectangle(viewport: Viewport, bbox: Bbox) {
  const points = [[bbox[0], bbox[1]], [bbox[0], bbox[3]], [bbox[2], bbox[1]], [bbox[2], bbox[3]]].map(([x, y]) => viewport.convertToViewportPoint(x, y));
  const xs = points.map(point => point[0]); const ys = points.map(point => point[1]);
  return { left: Math.min(...xs), top: Math.min(...ys), width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys) };
}

function PdfPage({ document, versionId, pageIndex, width, zoom, rotation, source, search, provenanceReady, onHeight }: {
  document: PDFDocumentProxy; versionId: string; pageIndex: number; width: number; zoom: number; rotation: number;
  source: Source | null; search: string; provenanceReady: boolean; onHeight: (index: number, height: number) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const textLayer = useRef<HTMLDivElement>(null);
  const [renderedViewport, setRenderedViewport] = useState<{ key: string; viewport: Viewport } | null>(null);
  // Limite de sélection rédigée ici, ou échec de rendu gardé tel quel (texte calculé au rendu).
  const [failure, setFailure] = useState<string | Failure>("");
  const errorText = useErrorText();
  const [nativeText, setNativeText] = useState<boolean | null>(null);
  const binding = citedRevision(versionId, source);
  const blocks = useQuery({ queryKey: blocksKey(versionId, pageIndex, binding.revision), queryFn: ({ signal }) => api.blocks(versionId, pageIndex, signal, binding.revision), enabled: provenanceReady && !binding.error, staleTime: 30000 });
  const correction = blocks.data?.page.orientation_correction ?? 0;
  const extractionState = blocks.data?.page.extraction_state;
  const renderKey = `${versionId}:${pageIndex}:${width}:${zoom}:${rotation}:${correction}:${extractionState}`;
  const pageLayout = pdfPageLayout(renderedViewport, renderKey, width, zoom, rotation);
  const viewport = pageLayout.viewport;
  const [previousRender, setPreviousRender] = useState({ document, key: renderKey });
  if (previousRender.document !== document || previousRender.key !== renderKey) {
    setPreviousRender({ document, key: renderKey });
    setFailure("");
    setNativeText(null);
  }

  useEffect(() => {
    let disposed = false;
    let render: RenderTask | undefined;
    let layer: { cancel(): void } | undefined;
    let page: PDFPageProxy | undefined;
    const outputCanvas = canvas.current;
    const layerContainer = textLayer.current;
    const renderPage = async () => {
      const pdfjs = await loadPdfJs();
      page = await document.getPage(pageIndex + 1);
      if (disposed || !outputCanvas || !layerContainer) { page.cleanup(); return; }
      const pageRotation = (page.rotate + rotation + correction) % 360;
      const natural = page.getViewport({ scale: 1, rotation: pageRotation });
      const scale = Math.max(0.1, (width - 48) / natural.width) * zoom;
      const view = page.getViewport({ scale, rotation: pageRotation });
      setRenderedViewport({ key: renderKey, viewport: view });
      onHeight(pageIndex, view.height + 52);
      const raster = boundedCanvasSize(view.width, view.height, window.devicePixelRatio || 1, GLOBAL_PIXEL_BUDGET, MAX_CANVASES);
      const resolution = raster.scale;
      outputCanvas.width = raster.width;
      outputCanvas.height = raster.height;
      const context = outputCanvas.getContext("2d", { alpha: false });
      if (!context) throw new Error("Ce navigateur ne fournit pas de contexte de dessin 2D : la page ne peut pas être affichée.");
      render = page.render({ canvas: outputCanvas, canvasContext: context, viewport: view, transform: resolution === 1 ? undefined : [resolution, 0, 0, resolution, 0, 0] });
      const renderText = async () => {
        const content = await page!.getTextContent();
        if (disposed) return;
        const hasNative = content.items.some(item => "str" in item && item.str.trim()) && extractionState !== "ocr";
        setNativeText(Boolean(hasNative));
        layerContainer.replaceChildren();
        if (hasNative) {
          const nextLayer = new pdfjs.TextLayer({ textContentSource: content, container: layerContainer, viewport: view });
          layer = nextLayer;
          await nextLayer.render();
        }
      };
      // Subscribe to cancellation immediately while text/fonts are still loading.
      await Promise.all([render.promise, renderText()]);
    };
    renderPage().catch(error => { if (!disposed && error?.name !== "RenderingCancelledException") setFailure({ error }); });
    return () => {
      disposed = true;
      render?.cancel();
      layer?.cancel();
      if (outputCanvas) { outputCanvas.width = 0; outputCanvas.height = 0; }
      layerContainer?.replaceChildren();
      page?.cleanup();
    };
  }, [document, pageIndex, width, zoom, rotation, correction, extractionState, onHeight, renderKey]);

  useEffect(() => {
    for (const span of textLayer.current?.querySelectorAll("span") ?? []) {
      span.classList.toggle("local-match", Boolean(search && span.textContent?.toLocaleLowerCase().includes(search.toLocaleLowerCase())));
    }
  }, [search, viewport, nativeText]);

  const sourceBoxes = sourceRegionBoxes(source, versionId, pageIndex);
  const overlays = ocrOverlays(blocks.data?.blocks ?? []);

  const selectText = () => {
    const selected = window.getSelection()?.toString().trim();
    if (!selected) return;
    if (!provenanceReady || binding.error || blocks.isError) { useWorkspace.getState().setSelection(null); setFailure(binding.error ?? (blocks.isError ? "La provenance de cette révision n'est pas disponible ; aucune extraction récente n'est substituée." : "La sélection annotée sera disponible après publication de l'extraction.")); return; }
    const spans = reconcileSelection(selected, blocks.data?.blocks ?? []);
    useWorkspace.getState().setSelection(spans ? { versionId, spans, text: selected } : null);
    if (!spans) setFailure("Cette sélection ne correspond pas de façon unique aux blocs extraits. Utilisez « Analyser cette page » ou choisissez un bloc dans « Texte extrait & provenance ».");
  };
  return <section className="pdf-page-slot" aria-label={`Page ${pageIndex + 1}`} data-page-index={pageIndex}>
    <div className="page-caption"><span>Page {pageIndex + 1}{blocks.data?.page.label && blocks.data.page.label !== String(pageIndex + 1) ? ` · folio ${blocks.data.page.label}` : ""}</span><span>{pageTextCaption({ extractionState: blocks.data?.page.extraction_state, nativeText, blocksLoading: blocks.isLoading, ocrRegions: overlays.length, extractedTextAvailable: hasExtractedText(blocks.data?.blocks ?? []), blocksUnavailable: blocks.isError || !provenanceReady || Boolean(binding.error) })}</span></div>
    <div className="pdf-paper" style={{ width: pageLayout.width, height: pageLayout.height }} onMouseUp={selectText} onKeyUp={selectText}>
      <canvas ref={canvas} aria-label={`Page ${pageIndex + 1} de l'original PDF`} style={{ width: "100%", height: "100%" }} />
      <div ref={textLayer} className="textLayer" style={{ "--total-scale-factor": viewport ? viewport.scale * viewport.userUnit : 1, "--scale-round-x": "1px", "--scale-round-y": "1px" } as React.CSSProperties} />
      {viewport && <div className="ocr-text-layer" aria-label="Texte OCR extrait sélectionnable">
        {overlays.map(overlay => <span key={overlay.key} data-block-id={overlay.blockId} data-precision={overlay.precision} className={search && overlay.text.toLocaleLowerCase().includes(search.toLocaleLowerCase()) ? "local-match" : undefined} style={{ ...viewportRectangle(viewport, overlay.bbox), fontSize: Math.max(5, Math.min(18 * viewport.scale, viewportRectangle(viewport, overlay.bbox).height / Math.max(1, overlay.text.split("\n").length))) }}>{overlay.text}</span>)}
      </div>}
      {viewport && sourceBoxes.map((bbox, index) => <div key={index} className="source-highlight" data-testid="source-highlight" style={viewportRectangle(viewport, bbox)} />)}
    </div>
    {failure && <p className="inline-warning" role="status">{typeof failure === "string" ? failure : errorText(failure.error)}</p>}
    {blocks.isError && <p className="inline-error" role="alert"><CircleAlert size={14} aria-hidden="true" />Provenance indisponible : {errorText(blocks.error)}</p>}
  </section>;
}

export function PdfViewer() {
  const state = useWorkspace();
  const opened = state.opened && "pageIndex" in state.opened ? state.opened : null;
  const versionId = opened?.versionId;
  const pageIndex = opened?.pageIndex;
  const readingSource = state.source;
  const binding = useCitationRevision();
  const metadata = useQuery({ queryKey: ["document", opened?.documentId], queryFn: ({ signal }) => api.document(opened!.documentId, signal, true), enabled: Boolean(opened), staleTime: 30000, refetchInterval: query => hasPublishedExtraction(query.state.data, opened?.versionId) ? false : 3000 });
  const provenanceReady = !binding.error && hasPublishedExtraction(metadata.data, opened?.versionId);
  const outline = useQuery({ queryKey: ["outline", opened?.versionId, binding.revision], queryFn: ({ signal }) => api.outline(opened!.versionId, signal, binding.revision), enabled: Boolean(opened) && provenanceReady, staleTime: 30000 });
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null);
  const [loadError, setLoadError] = useState<Failure | null>(null);
  const [width, setWidth] = useState(600);
  const [search, setSearch] = useState("");
  const [searching, setSearching] = useState(false);
  // Avancement de la recherche rédigé ici, ou échec gardé tel quel (texte calculé au rendu).
  const [searchStatus, setSearchStatus] = useState<string | Failure>("");
  const errorText = useErrorText();
  const [outlineVisible, setOutlineVisible] = useState(false);
  const [extractedVisible, setExtractedVisible] = useState(false);
  const [heights, setHeights] = useState<Record<number, number>>({});
  const scroll = useRef<HTMLDivElement>(null);
  const heightHandler = useCallback((index: number, height: number) => setHeights(current => Math.abs((current[index] ?? 0) - height) > 1 ? { ...current, [index]: height } : current), []);
  const currentCenter = useRef(0);
  const scrollLayout = useRef<PdfScrollLayout | null>(null);
  const searchGeneration = useRef(0);
  const searchLifetime = useRef<AbortController | null>(null);
  const [previousVersion, setPreviousVersion] = useState(versionId);
  const [previousReading, setPreviousReading] = useState({ versionId, source: readingSource });
  const layoutKey = `${versionId}:${state.zoom}:${state.rotation}:${width}`;
  const [previousLayout, setPreviousLayout] = useState(layoutKey);
  if (previousVersion !== versionId) {
    setPreviousVersion(versionId);
    setDocument(null);
    setLoadError(null);
  }
  if (!samePdfReading(previousReading, { versionId, source: readingSource })) {
    setPreviousReading({ versionId, source: readingSource });
    setSearchStatus("");
    setSearching(false);
  }
  if (previousLayout !== layoutKey) {
    setPreviousLayout(layoutKey);
    setHeights({});
  }
  const currentBlocks = useQuery({ queryKey: blocksKey(opened?.versionId, opened?.pageIndex, binding.revision), queryFn: ({ signal }) => api.blocks(opened!.versionId, opened!.pageIndex, signal, binding.revision), enabled: Boolean(opened) && provenanceReady, staleTime: 30000 });

  useEffect(() => {
    if (!scroll.current) return;
    const observer = new ResizeObserver(entries => setWidth(entries[0].contentRect.width));
    observer.observe(scroll.current);
    return () => observer.disconnect();
  }, [versionId]);

  useEffect(() => {
    const lifetime = new AbortController();
    searchLifetime.current = lifetime;
    return () => lifetime.abort();
  }, [versionId, readingSource]);

  useEffect(() => {
    if (!versionId) return;
    let disposed = false;
    let task: { destroy(): Promise<void> } | undefined;
    const load = async () => {
      const pdfjs = await loadPdfJs();
      if (disposed) return;
      const loading = pdfjs.getDocument({ url: api.fileUrl(versionId), cMapUrl: "/pdfjs/cmaps/", cMapPacked: true, standardFontDataUrl: "/pdfjs/standard_fonts/", wasmUrl: "/pdfjs/wasm/", iccUrl: "/pdfjs/iccs/", canvasMaxAreaInBytes: 96_000_000, useSystemFonts: false, enableXfa: false, withCredentials: true });
      task = loading;
      const loaded = await loading.promise;
      if (disposed) { await loading.destroy(); return; }
      const latestOpened = useWorkspace.getState().opened;
      if (!latestOpened || !("pageIndex" in latestOpened) || latestOpened.versionId !== versionId) { await loading.destroy(); return; }
      setDocument(loaded);
      const nextPage = Math.max(0, Math.min(loaded.numPages - 1, latestOpened.pageIndex));
      currentCenter.current = nextPage;
      if (nextPage !== latestOpened.pageIndex) useWorkspace.getState().page(nextPage);
    };
    load().catch(error => { if (!disposed) setLoadError({ error }); });
    return () => { disposed = true; void task?.destroy(); };
    // Page changes keep the PDF instance and do not change scope.
  }, [versionId]);

  const pageCount = document?.numPages ?? 0;
  const estimatedHeight = pdfPageLayout(null, layoutKey, width, state.zoom, state.rotation).height + 52;
  const offsets = [0];
  for (let index = 0; index < pageCount; index++) offsets.push(offsets[index] + (heights[index] ?? estimatedHeight));
  const pageOffset = offsets[pageIndex ?? 0] ?? 0;
  useLayoutEffect(() => {
    const element = scroll.current;
    if (!element || pageIndex === undefined || !document) { scrollLayout.current = null; return; }
    const next = { document, pageIndex, pageOffset };
    const target = pdfScrollTarget(scrollLayout.current, next, currentCenter.current, element.scrollTop);
    if (target !== null) {
      currentCenter.current = pageIndex;
      element.scrollTo({ top: target, behavior: "instant" });
    }
    // Position effective dans la nouvelle géométrie, après un éventuel recadrage par le navigateur.
    scrollLayout.current = { ...next, scrollTop: element.scrollTop };
  }, [pageIndex, document, pageOffset]);

  const onScroll = () => {
    if (!scroll.current || !opened) return;
    // Défilement du lecteur entre deux géométries : base du prochain recalage (rotation, zoom, hauteurs mesurées).
    if (scrollLayout.current) scrollLayout.current = { ...scrollLayout.current, scrollTop: scroll.current.scrollTop };
    const element = scroll.current;
    const page = pdfPageAtScroll(offsets, pageCount, element.scrollTop, element.scrollHeight - element.clientHeight, currentCenter.current);
    if (page !== currentCenter.current) { currentCenter.current = page; state.page(page); }
  };
  const localSearch = async () => {
    const lifetime = searchLifetime.current;
    if (!document || !opened || !search.trim() || !lifetime || lifetime.signal.aborted) return;
    const generation = ++searchGeneration.current;
    const reading = { versionId: opened.versionId, source: readingSource };
    const isCurrent = () => {
      const current = useWorkspace.getState();
      return searchGeneration.current === generation && samePdfReading(reading, { versionId: current.opened?.versionId, source: current.source });
    };
    setSearching(true); setSearchStatus("Recherche dans le texte du document…");
    try {
      const result = await findNextPdfPage({ pageCount: document.numPages, pageIndex: opened.pageIndex, expression: search,
        signal: lifetime.signal, isCurrent,
        readNative: async index => {
          const page = await document.getPage(index + 1);
          if (!isCurrent() || lifetime.signal.aborted) return "";
          const native = await page.getTextContent();
          return native.items.map(item => "str" in item ? item.str : "").join(" ");
        },
        readExtracted: provenanceReady ? async (index, signal) => (await api.blocks(opened.versionId, index, signal, binding.revision)).blocks.map(block => block.raw_text ?? block.text).join(" ") : undefined,
      });
      if (!isCurrent() || lifetime.signal.aborted || result.kind === "cancelled") return;
      if (result.kind === "found") { state.page(result.pageIndex); setSearchStatus(`Expression trouvée page ${result.pageIndex + 1}`); }
      else setSearchStatus("Expression absente du texte disponible de ce document. Le contenu des images sans texte extrait n'est pas lu.");
    } catch (error) { if (isCurrent() && !lifetime.signal.aborted) setSearchStatus({ error }); }
    finally { if (isCurrent() && !lifetime.signal.aborted) setSearching(false); }
  };
  const setPageScope = () => {
    if (opened && binding.actions.allowed) state.setScope({ kind: "pages", versionId: opened.versionId, pageStart: opened.pageIndex, pageEnd: opened.pageIndex }, `${metadata.data?.name ?? "Document"} · page ${opened.pageIndex + 1}`);
  };
  if (!opened) return <section className="viewer-panel"><PanelHeader title="Lecteur" /><PanelEmpty reason="not-started" icon={<FileText size={40} strokeWidth={1} aria-hidden="true" />} title="Aucun document ouvert" description="Ouvrez un document depuis la bibliothèque ou importez un PDF. Une source consultable s'ouvre ici à la page concernée ; le passage est surligné lorsque sa position est connue." /></section>;
  const visible = visiblePageWindow(opened.pageIndex, pageCount);
  const version = metadata.data?.versions.find(value => value.id === opened.versionId);
  return <section className="viewer-panel">
    <div className="viewer-title"><div><p className="eyebrow">Lecture de l'original</p><h2 title={metadata.data?.name}>{metadata.data?.name ?? (metadata.isError ? "Document sans informations" : "Chargement du document…")}</h2></div>{metadata.data && <DocumentTools key={metadata.data.id} document={metadata.data} />}<Button variant="ghost" size="icon" onClick={state.back} disabled={!state.previous} title="Revenir au passage précédent" aria-label="Revenir au passage précédent"><ArrowLeft size={16} /></Button></div>
    {metadata.isError && <PanelError title="Informations du document indisponibles" message={`${errorText(metadata.error)} Sans ces informations, les versions et l'état d'extraction de ce document ne sont pas vérifiés.`} onRetry={() => void metadata.refetch()} />}
    <div className="viewer-toolbar">
      <Button variant="ghost" size="icon" onClick={() => setOutlineVisible(value => !value)} aria-label="Afficher le sommaire" aria-pressed={outlineVisible}><List size={16} /></Button>
      <Button variant="ghost" size="icon" onClick={() => state.page(Math.max(0, opened.pageIndex - 1))} disabled={opened.pageIndex === 0} aria-label="Page précédente"><ChevronLeft size={16} /></Button>
      <label className="page-input"><input aria-label="Numéro de page" type="number" min={1} max={pageCount || 1} value={opened.pageIndex + 1} onChange={event => { const value = Number(event.target.value); if (value >= 1 && value <= pageCount) state.page(value - 1); }} /><span>/ {pageCount || "…"}</span></label>
      <Button variant="ghost" size="icon" onClick={() => state.page(Math.min(pageCount - 1, opened.pageIndex + 1))} disabled={!pageCount || opened.pageIndex >= pageCount - 1} aria-label="Page suivante"><ChevronRight size={16} /></Button>
      <span className="toolbar-separator" />
      <Button variant="ghost" size="icon" onClick={() => state.setZoom(state.zoom - 0.25)} disabled={state.zoom <= .5} aria-label="Réduire le zoom"><ZoomOut size={16} /></Button><span className="zoom-label">{Math.round(state.zoom * 100)} %</span><Button variant="ghost" size="icon" onClick={() => state.setZoom(state.zoom + .25)} disabled={state.zoom >= 3} aria-label="Augmenter le zoom"><ZoomIn size={16} /></Button>
      <Button variant="ghost" size="icon" onClick={state.rotate} aria-label="Pivoter de 90 degrés" title={`Rotation ${state.rotation}°`}><RotateCw size={16} /></Button>
      <Button variant="secondary" size="sm" onClick={setPageScope} disabled={!provenanceReady || !binding.actions.allowed} title={binding.actions.reason ?? undefined}>Analyser cette page</Button>
    </div>
    <p className="viewer-notice">« Analyser » définit le périmètre de la prochaine recherche ou question, sans lancer de traitement.</p>
    <form className="viewer-search" onSubmit={event => { event.preventDefault(); void localSearch(); }}><Search size={14} aria-hidden="true" /><input aria-label="Rechercher dans ce document" placeholder="Rechercher dans ce document" value={search} onChange={event => setSearch(event.target.value)} /><Button variant="ghost" size="sm" disabled={searching || !search.trim()} type="submit" title="Aller à la page suivante qui contient l'expression">{searching ? "Recherche…" : "Chercher plus loin"}</Button></form>
    {searchStatus && <p className="viewer-notice" role="status">{typeof searchStatus === "string" ? searchStatus : errorText(searchStatus.error)}</p>}
    {binding.error ? <p className="viewer-notice inline-warning" role="status">{binding.error}</p> : !provenanceReady && <p className="viewer-notice" role="status">Original consultable ; son extraction n'est pas encore publiée. Les passages, le sommaire et l'analyse de page seront disponibles après publication de l'extraction. Consultez le Suivi : une extraction partielle peut demander votre accord.</p>}
    {binding.actions.reason && !binding.error && <p className="viewer-notice" role="status">{binding.actions.reason}</p>}
    {state.source && <div className="source-navigation" role="status"><strong>{state.source.source_id ?? "Passage retrouvé"}</strong><span>{sourcePrecisionLabel(state.source)} · version <span className="mono">{opened.versionId.slice(0, 8)}</span>{binding.revision ? <> · révision <span className="mono">{binding.revision.slice(0, 8)}</span></> : null}</span><ExtractionBadge source={state.source} /></div>}
    {outlineVisible && <nav className="outline" aria-label="Sommaire"><h3>Sommaire</h3>{outline.isLoading ? <p role="status">Chargement du sommaire…</p> : outline.isError ? <p role="alert" className="inline-error">Sommaire indisponible : {errorText(outline.error)}</p> : !outline.data?.sections.length ? <p>{provenanceReady ? "Aucune section extraite pour cette version." : "Le sommaire sera disponible après publication de l'extraction."}</p> :outline.data.sections.filter((section): section is typeof section & { page_index: number } => typeof section.page_index === "number").map(section => <div key={section.id}><button onClick={() => state.page(section.page_index)}>{section.title}<span>p. {section.page_index + 1}</span></button><Button variant="ghost" size="sm" aria-label={`Analyser la section ${section.title}`} disabled={!binding.actions.allowed} title={binding.actions.reason ?? undefined} onClick={() => { if (binding.actions.allowed) state.setScope({ kind: "section", versionId: opened.versionId, sectionId: section.id }, section.title); }}>Analyser</Button></div>)}</nav>}
    <div className="pdf-scroll" ref={scroll} onScroll={onScroll} data-testid="pdf-scroll" style={{ overflowAnchor: "none" }}>
      {loadError ? <PanelError title={loadError.error instanceof PdfJsLoadError ? "Lecteur PDF indisponible" : "Lecture de l'original impossible"} message={errorText(loadError.error)} onRetry={() => window.location.reload()} retryLabel="Recharger la page" /> : !document ? <PanelLoading label="Chargement de l'original PDF…" /> : <>
        <div aria-hidden="true" style={{ height: offsets[visible[0] ?? 0] }} />
        {visible.map(index => <PdfPage key={`${opened.versionId}:${index}`} document={document} versionId={opened.versionId} pageIndex={index} width={width} zoom={state.zoom} rotation={state.rotation} source={state.source} search={search} provenanceReady={provenanceReady} onHeight={heightHandler} />)}
        <div aria-hidden="true" style={{ height: (offsets[pageCount] ?? 0) - (offsets[(visible.at(-1) ?? -1) + 1] ?? 0) }} />
      </>}
    </div>
    <div className="reader-footer"><button onClick={() => setExtractedVisible(value => !value)} aria-expanded={extractedVisible}>Texte extrait & provenance <ChevronDown size={14} aria-hidden="true" /></button><span title={version?.sha256}>Version <span className="mono">{opened.versionId.slice(0, 8)}</span></span></div>
    {extractedVisible && <div className="extracted-text"><p className="eyebrow">Page {opened.pageIndex + 1} · blocs extraits</p>{currentBlocks.isLoading ? <p role="status">Chargement des blocs extraits…</p> : currentBlocks.isError ? <p role="alert" className="inline-error">Blocs extraits indisponibles : {errorText(currentBlocks.error)}</p> : !currentBlocks.data?.blocks.length ? <p>{provenanceReady ? "Aucun texte extrait pour cette page." : "Les blocs extraits seront disponibles après publication de l'extraction."}</p> :currentBlocks.data.blocks.map(block => <div key={block.id}><p>{block.text}</p><Button variant="secondary" size="sm" disabled={!block.text.trim() || !wholeBlockSpan(block)} title={!wholeBlockSpan(block) ? "Ce bloc n'a pas de révision ou d'empreinte vérifiable : il ne peut pas servir de périmètre." : undefined} onClick={() => { const span = wholeBlockSpan(block); if (span) state.setScope({ kind: "selection", versionId: opened.versionId, spans: [span] }, `Bloc source · page ${opened.pageIndex + 1}`); }}>Analyser ce bloc</Button></div>)}{groupedWarningTexts(currentBlocks.data?.warnings).map(text => <p key={text} className="inline-warning">{text}</p>)}</div>}
  </section>;
}
