import { addDays, format, startOfMonth, startOfYear, subDays, subYears } from "date-fns";

export type PeriodPreset = "today" | "yesterday" | "last7d" | "last30d" | "mtd" | "last90d" | "ytd";

export function presetRange(preset: PeriodPreset, today: Date = new Date()): { from: Date; to: Date } {
  switch (preset) {
    case "today":
      return { from: today, to: today };
    case "yesterday": {
      const y = subDays(today, 1);
      return { from: y, to: y };
    }
    case "last7d":
      return { from: subDays(today, 6), to: today };
    case "last30d":
      return { from: subDays(today, 29), to: today };
    case "mtd":
      return { from: startOfMonth(today), to: today };
    case "last90d":
      return { from: subDays(today, 89), to: today };
    case "ytd":
      return { from: startOfYear(today), to: today };
  }
}

export function isoDate(d: Date): string {
  return format(d, "yyyy-MM-dd");
}

export function parseDate(iso: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  // Reject overflowed values like 2026-13-99 — JS Date silently wraps them.
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;
  const out = new Date(y, mo - 1, d);
  if (out.getFullYear() !== y || out.getMonth() !== mo - 1 || out.getDate() !== d) return null;
  return out;
}

// "previous period of equal length" used by Overview deltas.
export function previousPeriod(from: Date, to: Date): { from: Date; to: Date } {
  const span = (to.getTime() - from.getTime()) / (1000 * 60 * 60 * 24);
  const prevTo = subDays(from, 1);
  const prevFrom = subDays(prevTo, span);
  return { from: prevFrom, to: prevTo };
}

// Defaults for the global filter bar. Last 7 days, ending today.
export function defaultRange(): { from: string; to: string } {
  const { from, to } = presetRange("last7d");
  return { from: isoDate(from), to: isoDate(to) };
}

// Default 1-year retention guard (matches backend's MAX_RANGE_DAYS=730).
export const MAX_RANGE_DAYS = 730;

export function rangeDays(from: Date, to: Date): number {
  return Math.round((to.getTime() - from.getTime()) / (1000 * 60 * 60 * 24)) + 1;
}

// Used to throw away stale `?from=...&to=...` URLs.
export function isValidRange(from: string | null, to: string | null): boolean {
  if (!from || !to) return false;
  const f = parseDate(from);
  const t = parseDate(to);
  if (!f || !t) return false;
  if (f > t) return false;
  if ((t.getTime() - f.getTime()) / (1000 * 60 * 60 * 24) > MAX_RANGE_DAYS) return false;
  return true;
}

// Auto-pick a sensible default granularity for time series (design-doc §9.3).
export function pickGranularity(rangeDaysCount: number): "hour" | "day" | "week" | "month" {
  if (rangeDaysCount <= 2) return "hour";
  if (rangeDaysCount <= 60) return "day";
  if (rangeDaysCount <= 365) return "week";
  return "month";
}

// Reduce subDays import to keep tree-shaking happy: re-export helpers used elsewhere.
export { addDays, subDays, subYears };
