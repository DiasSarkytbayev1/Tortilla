// Display helpers. Currency symbol is hardcoded to € to match design-doc §5
// (single chain currency, configured server-side). If we ever need
// per-locale, surface from /api/config.

export const CURRENCY = "€";

export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${CURRENCY}${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatInteger(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString();
}

export function formatPct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${value.toFixed(1)}%`;
}

export function formatDelta(current: number | null, previous: number | null): {
  pct: number | null;
  direction: "up" | "down" | "flat" | "unknown";
} {
  if (current == null || previous == null || previous === 0) {
    return { pct: null, direction: "unknown" };
  }
  const pct = ((current - previous) / previous) * 100;
  const direction = pct > 0.5 ? "up" : pct < -0.5 ? "down" : "flat";
  return { pct, direction };
}

export function formatHour(hour: number | null | undefined): string {
  if (hour == null) return "—";
  return `${hour.toString().padStart(2, "0")}:00`;
}

const DOW_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
export function dowLabel(dow: number): string {
  return DOW_LABELS[dow] ?? "?";
}

// Mon-first ordering (European convention, design-doc §10 open question 2).
export const DOW_ORDER_MON_FIRST = [1, 2, 3, 4, 5, 6, 0];
