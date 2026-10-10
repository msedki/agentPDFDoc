"use client";
import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWorkspace, type OfficeLocation } from "@/lib/store";
import { reconcileSelection, wholeBlockSpan } from "@/lib/selection";
import { groupedWarningTexts } from "@/lib/warnings";
import { docxTableWindow, rasterAsset, record, objects, text } from "@/lib/office-structure";
import type { Block, Source } from "@/lib/types";
import { Button } from "./ui/button";
import { useErrorText } from "./ui/error-text";
function DocxTable({ structure, depth = 0 }: { structure: Record<string, unknown>; depth?: number }) {
  const rows = objects(structure.rows);
  const [rowCursor, setRowCursor] = useState(0);
  const [columnCursor, setColumnCursor] = useState(0);
  const columns = typeof structure.column_count === "number" ? structure.column_count : 0;
  const visibleRows = docxTableWindow(structure, rowCursor, columnCursor);
  if (depth > 3) return <p className="inline-warning">Tableau imbriqué conservé dans la source ; cette prévisualisation est limitée à quatre niveaux.</p>;
  return <div className="office-table-block">
    <div className="office-window-controls"><span>Lignes {rowCursor + 1}–{Math.min(rows.length, rowCursor + 20)} sur {rows.length} · colonnes {columnCursor + 1}–{Math.min(columns, columnCursor + 10)}</span>
      <Button size="sm" variant="ghost" disabled={rowCursor === 0} onClick={() => setRowCursor(Math.max(0, rowCursor - 20))}>Lignes précédentes</Button><Button size="sm" variant="ghost" disabled={rowCursor + 20 >= rows.length} onClick={() => setRowCursor(rowCursor + 20)}>Lignes suivantes</Button>
      <Button size="sm" variant="ghost" disabled={columnCursor === 0} onClick={() => setColumnCursor(Math.max(0, columnCursor - 10))}>Colonnes précédentes</Button><Button size="sm" variant="ghost" disabled={columnCursor + 10 >= columns} onClick={() => setColumnCursor(columnCursor + 10)}>Colonnes suivantes</Button></div>
    <div className="office-table-scroll"><table><caption>Tableau source · fenêtre affichée ; le texte d’indexation est un dérivé.</caption><tbody>{visibleRows.map((row, index) => <tr key={text(row.source.element_path) || index}>{row.cells.map((projected, cellIndex) => {
      if (projected.missing) return <td key={`gap-${projected.column}`} colSpan={projected.columnSpan} className="office-table-gap" aria-label="Aucune cellule source à cette position" />;
      const cell = projected.source;
      const contents = objects(cell.contents); const content = contents.length ? contents.map((item, itemIndex) => item.kind === "table" ? <DocxTable key={text(item.id) || itemIndex} structure={record(item.structure)} depth={depth + 1} /> : <p key={text(item.id) || itemIndex}>{text(record(item.structure).source_text ?? item.text)}</p>) : text(cell.text);
      const rendered = <>{content}{projected.clipped && <small>Cellule fusionnée partiellement affichée ; origine ligne {Number(cell.row) + 1}, colonne {Number(cell.column) + 1}.</small>}</>;
      return projected.header ? <th key={text(cell.id) || cellIndex} scope={projected.columnSpan > 1 ? "colgroup" : "col"} colSpan={projected.columnSpan} rowSpan={projected.rowSpan}>{rendered}</th> : <td key={text(cell.id) || cellIndex} colSpan={projected.columnSpan} rowSpan={projected.rowSpan}>{rendered}</td>;
    })}</tr>)}</tbody></table></div>
  </div>;
}

function DocxFigure({ image, opened, revision }: { image: Record<string, unknown>; opened: OfficeLocation; revision: string }) {
  const asset = rasterAsset(image); const [failed, setFailed] = useState(false);
  return <figure className="office-figure">
    {asset && !failed ? <Image unoptimized src={api.assetUrl(opened.versionId, asset.id, revision)} alt={asset.alt} width={asset.width} height={asset.height} onError={() => setFailed(true)} /> : <p className="inline-warning">{failed ? "L'image source n'a pas pu être chargée." : "Ce type d'image n'est pas prévisualisé. Consultez l'original."}</p>}
    <figcaption>{asset?.alt ?? (text(image.alt_text) || text(image.title) || "Figure sans description")} · contenu visuel non analysé.<small>Partie source : {text(image.part)} · {text(image.placement)}</small></figcaption>
  </figure>;
}

function DocxBlock({ block, opened, cited }: { block: Block; opened: OfficeLocation; cited: boolean }) {
  const state = useWorkspace(); const structure = record(block.structure); const span = wholeBlockSpan(block);
  const body = block.source_text ?? block.raw_text ?? block.text;
  const images = objects(structure.images);
  const references = objects(structure.references);
  const Heading = `h${Math.min(6, Math.max(2, (typeof structure.outline_level === "number" ? structure.outline_level : 1) + 2))}` as "h2" | "h3" | "h4" | "h5" | "h6";
  return <article className={`office-element ${cited ? "is-cited" : ""}`} id={`office-block-${block.id}`} data-office-block={block.id} aria-label={cited ? "Élément source cité" : undefined}>
    {block.type === "table" || block.kind === "table" ? <DocxTable structure={structure} /> : block.kind === "textbox" ? null : <>
      {record(structure.numbering).label != null && <small className="office-numbering" title="Numérotation structurée ; ce libellé est dérivé.">{text(record(structure.numbering).label)}</small>}
      {block.type === "heading" || block.kind === "heading" ? <Heading>{body}</Heading> : <p className="office-source-text">{body}</p>}
    </>}
    {block.kind === "textbox" && <div className="office-textbox">{objects(structure.contents).map((item, index) => item.kind === "table" ? <DocxTable key={text(item.id) || index} structure={record(item.structure)} /> : <p key={text(item.id) || index}>{text(record(item.structure).source_text ?? item.text)}</p>)}<small>Zone de texte rattachée à son élément source ; l'ordre visuel de la page n'est pas reconstruit.</small></div>}
    {images.map((image, index) => <DocxFigure key={text(image.sha256 ?? image.element_path) || index} image={image} opened={opened} revision={block.extraction_revision_id!} />)}
    {references.length > 0 && <details><summary>Notes et références ({references.length})</summary>{references.map((reference, index) => <p key={index}>{text(reference.kind)} {text(reference.id)} · {text(reference.target_part)}{typeof reference.target_unit_id === "string" && <Button size="sm" variant="ghost" onClick={() => state.officeLocation({ unitId: reference.target_unit_id as string, blockId: undefined, elementPath: undefined })}>Lire cette référence</Button>}</p>)}</details>}
    {(objects(structure.revisions).length > 0 || objects(structure.links).length > 0 || objects(structure.fields).length > 0) && <details><summary>Révisions, liens et champs sources</summary>{objects(structure.revisions).map((change, index) => <p key={`revision-${index}`}>{text(change.kind)} · {text(change.author)} · {text(change.date)} · {change.included === false ? "Texte exclu de l'extraction" : "Texte inclus"} : {text(change.text)}</p>)}{objects(structure.links).map((link, index) => <p key={`link-${index}`}>Lien source : {text(link.target ?? link.uri ?? link.anchor)} · lecture seule, aucune liaison ouverte.</p>)}{objects(structure.fields).map((field, index) => <p key={`field-${index}`}>Champ source : {text(field.instruction ?? field.code ?? field.kind)} · aucune exécution.</p>)}</details>}
    <details className="office-element-provenance"><summary>Localisation de l'élément</summary><dl><dt>Partie</dt><dd>{block.locator?.kind === "docx_element" ? block.locator.part : "Non disponible"}</dd><dt>Élément</dt><dd className="mono">{block.locator?.kind === "docx_element" ? block.locator.element_path : "Non disponible"}</dd><dt>Style</dt><dd>{text(structure.style_name) || text(structure.style_id) || "Non renseigné"}</dd><dt>Empreinte du texte source</dt><dd className="mono">{block.source_text_hash ?? "Non disponible"}</dd></dl></details>
    <Button size="sm" variant="secondary" disabled={!span || !body.trim()} title={!span ? "Révision ou empreinte source absente : ce bloc ne peut pas servir de périmètre." : undefined} onClick={() => { if (span) state.setScope({ kind: "selection", versionId: opened.versionId, spans: [span] }, "Élément source sélectionné"); }}>Analyser cet élément</Button>
  </article>;
}

export function DocxContent({ opened, unitId, revision, source }: { opened: OfficeLocation; unitId: string; revision: string; source: Source | null }) {
  const state = useWorkspace(); const errorText = useErrorText(); const [cursor, setCursor] = useState(0); const [selectionError, setSelectionError] = useState(""); const area = useRef<HTMLDivElement>(null);
  const anchor = cursor === 0 ? opened.blockId : undefined;
  const blocks = useQuery({ queryKey: ["office-blocks", opened.versionId, revision, unitId, cursor, anchor], queryFn: ({ signal }) => api.officeBlocks(opened.versionId, unitId, revision, cursor, signal, anchor), staleTime: 30000 });
  const currentCursor = blocks.data?.cursor ?? cursor;
  useEffect(() => { if (opened.blockId && blocks.data?.blocks.some(block => block.id === opened.blockId)) document.getElementById(`office-block-${opened.blockId}`)?.scrollIntoView({ block: "center" }); }, [opened.blockId, blocks.data]);
  const selection = () => {
    const native = window.getSelection();
    if (!native || !area.current?.contains(native.anchorNode) || !area.current.contains(native.focusNode)) return;
    const selected = native.toString(); const spans = reconcileSelection(selected, blocks.data?.blocks ?? []);
    state.setSelection(spans ? { versionId: opened.versionId, spans, text: selected } : null);
    setSelectionError(selected && !spans ? "Cette sélection ne correspond pas à un passage source unique. Utilisez « Analyser cet élément » pour conserver sa provenance." : "");
  };
  return <div className="office-narrative" ref={area} onMouseUp={selection} onKeyUp={selection}>
    {blocks.isLoading && <p role="status">Chargement des éléments…</p>}{blocks.isError && <p role="alert" className="inline-error">{errorText(blocks.error)}</p>}
    {blocks.data && <><div className="office-window-controls"><span>Éléments {currentCursor + 1}–{currentCursor + blocks.data.blocks.length} sur {blocks.data.total}</span><Button size="sm" variant="ghost" disabled={currentCursor === 0} onClick={() => setCursor(Math.max(0, currentCursor - 50))}>Précédents</Button><Button size="sm" variant="ghost" disabled={blocks.data.next_cursor === null} onClick={() => setCursor(blocks.data!.next_cursor!)}>Suivants</Button></div>
      {blocks.data.blocks.map(block => <DocxBlock key={block.id} block={block} opened={opened} cited={source?.version_id === opened.versionId && source.extraction_revision_id === revision && (source.block_ids?.includes(block.id) === true || source.locator?.kind === "docx_element" && block.locator?.kind === "docx_element" && source.locator.unit_id === unitId && source.locator.element_path === block.locator.element_path)} />)}
      {!blocks.data.blocks.length && <p>Aucun élément dans cette unité.</p>}{groupedWarningTexts(blocks.data.warnings).map(message => <p className="inline-warning" key={message}>{message}</p>)}
    </>}{selectionError && <p role="status" className="inline-warning">{selectionError}</p>}
  </div>;
}
