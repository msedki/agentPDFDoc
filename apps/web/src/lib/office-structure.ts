export function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
export function objects(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter(item => item && typeof item === "object" && !Array.isArray(item)).map(record) : [];
}
export function text(value: unknown): string {
  return typeof value === "string" ? value : typeof value === "number" || typeof value === "boolean" ? String(value) : "";
}

export type TableWindowCell = { source: Record<string, unknown>; column: number; rowSpan: number; columnSpan: number; clipped: boolean; header: boolean; missing?: true };
/** Project actual origins into a bounded window; continuation cells never duplicate source text. */
export function docxTableWindow(structure: Record<string, unknown>, rowStart: number, columnStart: number, rowLimit = 20, columnLimit = 10) {
  const rows = objects(structure.rows);
  const columnCount = typeof structure.column_count === "number" ? structure.column_count : 0;
  const rowEnd = Math.min(rows.length, rowStart + rowLimit);
  const columnEnd = Math.min(columnCount, columnStart + columnLimit);
  const result = rows.slice(rowStart, rowEnd).map(row => ({ source: row, cells: [] as TableWindowCell[] }));
  for (const row of rows) for (const cell of objects(row.cells)) {
    if (cell.merge_origin_id || !Number.isSafeInteger(cell.row) || !Number.isSafeInteger(cell.column)) continue;
    const sourceRow = cell.row as number, sourceColumn = cell.column as number;
    const rowSpan = Math.max(1, typeof cell.row_span === "number" ? cell.row_span : 1);
    const columnSpan = Math.max(1, typeof cell.column_span === "number" ? cell.column_span : 1);
    if (sourceRow >= rowEnd || sourceColumn >= columnEnd || sourceRow + rowSpan <= rowStart || sourceColumn + columnSpan <= columnStart) continue;
    const projectedRow = Math.max(rowStart, sourceRow), projectedColumn = Math.max(columnStart, sourceColumn);
    result[projectedRow - rowStart]?.cells.push({ source: cell, column: projectedColumn,
      rowSpan: Math.min(rowEnd, sourceRow + rowSpan) - projectedRow,
      columnSpan: Math.min(columnEnd, sourceColumn + columnSpan) - projectedColumn,
      clipped: sourceRow < rowStart || sourceColumn < columnStart || sourceRow + rowSpan > rowEnd || sourceColumn + columnSpan > columnEnd,
      header: row.is_header === true });
  }
  const occupied = result.map(() => new Set<number>());
  result.forEach((row, rowIndex) => {
    for (const cell of row.cells) for (let offset = 0; offset < cell.rowSpan; offset++) for (let column = cell.column; column < cell.column + cell.columnSpan; column++) occupied[rowIndex + offset]?.add(column);
  });
  result.forEach((row, rowIndex) => {
    for (let column = columnStart; column < columnEnd; column++) {
      if (occupied[rowIndex].has(column)) continue;
      const start = column;
      while (column + 1 < columnEnd && !occupied[rowIndex].has(column + 1)) column++;
      row.cells.push({ source: {}, column: start, rowSpan: 1, columnSpan: column - start + 1, clipped: false, header: false, missing: true });
    }
    row.cells.sort((left, right) => left.column - right.column);
  });
  return result;
}

export function officeTableColumnNames(table: Record<string, unknown>): string[] {
  return objects(table.columns).map(column => text(column.label) || text(record(column.attributes).name) || (column.name === "tableColumn" ? "Colonne sans nom" : text(column.name) || "Colonne sans nom"));
}

export function rasterAsset(image: Record<string, unknown>): { id: string; alt: string; width: number; height: number } | null {
  const mime = text(image.content_type).toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(text(image.sha256)) || !["image/png", "image/jpeg", "image/gif", "image/bmp", "image/webp"].includes(mime)) return null;
  const extent = record(image.extent_emu);
  const width = typeof extent.cx === "number" && extent.cx > 0 ? extent.cx : 400;
  const height = typeof extent.cy === "number" && extent.cy > 0 ? extent.cy : 300;
  return { id: text(image.sha256), alt: text(image.alt_text) || text(image.title) || text(image.name) || "Illustration du document source",
    width: 800, height: Math.max(1, Math.min(1600, Math.round(800 * height / width))) };
}
