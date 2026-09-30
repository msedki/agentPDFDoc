export function warningText(value: unknown): string {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    const warning = value as { message?: unknown; code?: unknown };
    if (typeof warning.message === "string") return warning.message;
    if (typeof warning.code === "string") return warning.code;
  }
  return "Le service signale une limite.";
}
