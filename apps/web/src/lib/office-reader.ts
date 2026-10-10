import type { CellRange, OfficeBlocks, OfficeCells, OfficeRepresentation, OfficeCell, SourceLocator } from "./types.ts";

export const OFFICE_ROWS = 50;
export const OFFICE_COLUMNS = 20;
export const MAX_OFFICE_ROW = 1_048_576;
export const MAX_OFFICE_COLUMN = 16_384;

export function cellWindow(range: CellRange): CellRange {
  if (cellRangeError(range)) throw new RangeError("Plage de cellules hors limites");
  return { ...range, rowEnd: Math.min(range.rowEnd, range.rowStart + OFFICE_ROWS - 1), columnEnd: Math.min(range.columnEnd, range.columnStart + OFFICE_COLUMNS - 1) };
}
export function movedCellWindow(row: number, column: number): CellRange {
  const rowStart = Math.max(1, Math.min(MAX_OFFICE_ROW - OFFICE_ROWS + 1, row));
  const columnStart = Math.max(1, Math.min(MAX_OFFICE_COLUMN - OFFICE_COLUMNS + 1, column));
  return { rowStart, rowEnd: rowStart + OFFICE_ROWS - 1, columnStart, columnEnd: columnStart + OFFICE_COLUMNS - 1 };
}
export function cellKeyTarget(key: string, row: number, column: number, range: CellRange, control = false): { row: number; column: number } | null {
  const next = { row, column };
  if (key === "ArrowUp") next.row--;
  else if (key === "ArrowDown") next.row++;
  else if (key === "ArrowLeft") next.column--;
  else if (key === "ArrowRight") next.column++;
  else if (key === "Home") { next.column = range.columnStart; if (control) next.row = range.rowStart; }
  else if (key === "End") { next.column = range.columnEnd; if (control) next.row = range.rowEnd; }
  else return null;
  return { row: Math.max(range.rowStart, Math.min(range.rowEnd, next.row)), column: Math.max(range.columnStart, Math.min(range.columnEnd, next.column)) };
}

export function cellRangeError(range: CellRange): string | null {
  if (![range.rowStart, range.rowEnd, range.columnStart, range.columnEnd].every(Number.isSafeInteger) || range.rowStart < 1 || range.rowEnd < range.rowStart || range.rowEnd > MAX_OFFICE_ROW || range.columnStart < 1 || range.columnEnd < range.columnStart || range.columnEnd > MAX_OFFICE_COLUMN) return "La plage doit avoir des lignes de 1 à 1 048 576 et des colonnes de A à XFD, dans l'ordre.";
  return null;
}

export function columnName(column: number): string {
  if (!Number.isInteger(column) || column < 1 || column > 16_384) throw new RangeError("Colonne hors limites");
  let name = "";
  for (let value = column; value > 0; value = Math.floor((value - 1) / 26)) name = String.fromCharCode(65 + (value - 1) % 26) + name;
  return name;
}

export function rangeLabel(range: CellRange): string { return `${columnName(range.columnStart)}${range.rowStart}:${columnName(range.columnEnd)}${range.rowEnd}`; }

export function parseCellRange(value: string): CellRange | null {
  const match = /^([A-Z]{1,3})([1-9]\d*)(?::([A-Z]{1,3})([1-9]\d*))?$/.exec(value.trim().toUpperCase());
  if (!match) return null;
  const column = (letters: string) => [...letters].reduce((total, letter) => total * 26 + letter.charCodeAt(0) - 64, 0);
  const range = { rowStart: Number(match[2]), rowEnd: Number(match[4] ?? match[2]), columnStart: column(match[1]), columnEnd: column(match[3] ?? match[1]) };
  return cellRangeError(range) ? null : range;
}

export function locatorRange(locator: SourceLocator | undefined): CellRange | null {
  if (locator?.kind !== "xlsx_cells") return null;
  const range = { rowStart: locator.row_start, rowEnd: locator.row_end, columnStart: locator.column_start, columnEnd: locator.column_end };
  return cellRangeError(range) ? null : range;
}

export function officeCellText(cell: OfficeCell): string {
  if (typeof cell.display_text === "string") return cell.display_text;
  const value = cell.formula ? cell.cached_present ? cell.cached_value : undefined : cell.value ?? cell.raw_value;
  return officeValueText(value);
}

export function officeValueText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value !== "object") return String(value);
  const typed = value as Record<string, unknown>;
  if (typed.kind === "excel_date") return `Jour Excel 1900 fictif · série ${String(typed.serial)}`;
  if (typed.value === null || typed.value === undefined) return "";
  return String(typed.value);
}

export function verifyOfficeRepresentation(result: OfficeRepresentation, versionId: string, revision?: string | null): OfficeRepresentation {
  if (result.version_id !== versionId || !["docx", "xlsx"].includes(result.format) || !result.extraction_revision_id || revision && result.extraction_revision_id !== revision || !Array.isArray(result.units) || result.units.length > 100 || new Set(result.units.map(unit => unit.id)).size !== result.units.length) throw new Error("La représentation reçue ne correspond pas à la version et à la révision demandées. Aucune révision récente n'est substituée.");
  return result;
}

export function verifyOfficeBlocks(result: OfficeBlocks, versionId: string, unitId: string, revision: string): OfficeBlocks {
  if (result.version_id !== versionId || result.extraction_revision_id !== revision || result.unit?.id !== unitId || !Array.isArray(result.blocks) || result.blocks.length > 100 || result.blocks.some(block => block.extraction_revision_id !== revision || block.page_index !== null || block.locator?.kind !== "docx_element" || block.locator.unit_id !== unitId)) throw new Error("Les éléments reçus ne correspondent pas à l'unité et à la révision demandées.");
  return result;
}

export function verifyOfficeCells(result: OfficeCells, versionId: string, sheetId: string, revision: string, range: CellRange): OfficeCells {
  const bounds = result.bounds;
  if (cellRangeError(range) || result.version_id !== versionId || result.extraction_revision_id !== revision || result.sheet_id !== sheetId || !bounds || bounds.row_start !== range.rowStart || bounds.row_end !== range.rowEnd || bounds.column_start !== range.columnStart || bounds.column_end !== range.columnEnd || !Array.isArray(result.cells) || new Set(result.cells.map(cell => cell.address)).size !== result.cells.length || result.cells.some(cell => !Number.isInteger(cell.row) || !Number.isInteger(cell.column) || cell.row < range.rowStart || cell.row > range.rowEnd || cell.column < range.columnStart || cell.column > range.columnEnd || cell.address !== `${columnName(cell.column)}${cell.row}`)) throw new Error("Les cellules reçues ne correspondent pas à la feuille, à la fenêtre et à la révision demandées.");
  return result;
}
