import { describe, expect, it } from "vitest";
import {
  CURRENCY,
  dowLabel,
  DOW_ORDER_MON_FIRST,
  formatCurrency,
  formatDelta,
  formatHour,
  formatInteger,
  formatPct,
} from "@/lib/format";

describe("formatCurrency", () => {
  it("formats with 2 decimals + currency symbol", () => {
    const v = formatCurrency(1234.5);
    expect(v).toContain(CURRENCY);
    expect(v).toMatch(/1[,.]?234\.50/);
  });
  it("renders em dash for null/undefined", () => {
    expect(formatCurrency(null)).toBe("—");
    expect(formatCurrency(undefined)).toBe("—");
  });
});

describe("formatInteger", () => {
  it("groups thousands", () => {
    expect(formatInteger(1234)).toMatch(/1[,.]?234/);
  });
  it("renders em dash for null", () => {
    expect(formatInteger(null)).toBe("—");
  });
});

describe("formatPct", () => {
  it("formats with 1 decimal", () => {
    expect(formatPct(12.345)).toBe("12.3%");
  });
  it("renders em dash for null", () => {
    expect(formatPct(null)).toBe("—");
  });
});

describe("formatHour", () => {
  it("zero-pads", () => {
    expect(formatHour(7)).toBe("07:00");
    expect(formatHour(13)).toBe("13:00");
  });
  it("em dash for null", () => {
    expect(formatHour(null)).toBe("—");
  });
});

describe("formatDelta", () => {
  it("up direction for big increases", () => {
    expect(formatDelta(110, 100)).toEqual({ pct: 10, direction: "up" });
  });
  it("down direction for big decreases", () => {
    expect(formatDelta(90, 100)).toEqual({ pct: -10, direction: "down" });
  });
  it("flat for tiny changes", () => {
    expect(formatDelta(100.1, 100)).toMatchObject({ direction: "flat" });
  });
  it("unknown when previous is zero", () => {
    expect(formatDelta(100, 0)).toEqual({ pct: null, direction: "unknown" });
  });
  it("unknown when either side is null", () => {
    expect(formatDelta(null, 100)).toEqual({ pct: null, direction: "unknown" });
    expect(formatDelta(100, null)).toEqual({ pct: null, direction: "unknown" });
  });
});

describe("dowLabel + DOW_ORDER_MON_FIRST", () => {
  it("returns short labels", () => {
    expect(dowLabel(0)).toBe("Sun");
    expect(dowLabel(1)).toBe("Mon");
    expect(dowLabel(6)).toBe("Sat");
  });
  it("Mon-first ordering", () => {
    expect(DOW_ORDER_MON_FIRST).toEqual([1, 2, 3, 4, 5, 6, 0]);
  });
});
