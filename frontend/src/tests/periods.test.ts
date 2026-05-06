import { describe, expect, it } from "vitest";
import {
  isoDate,
  isValidRange,
  parseDate,
  pickGranularity,
  presetRange,
  previousPeriod,
  rangeDays,
} from "@/lib/periods";

describe("isoDate / parseDate", () => {
  it("round-trips a date", () => {
    const d = new Date(2026, 4, 15);
    expect(parseDate(isoDate(d))?.getTime()).toBe(d.getTime());
  });
  it("rejects malformed strings", () => {
    expect(parseDate("not-a-date")).toBeNull();
    expect(parseDate("2026-13-99")).toBeNull();
  });
});

describe("presetRange", () => {
  const today = new Date(2026, 4, 15); // 2026-05-15
  it("last7d gives 7 days inclusive", () => {
    const r = presetRange("last7d", today);
    expect(rangeDays(r.from, r.to)).toBe(7);
    expect(r.to.getTime()).toBe(today.getTime());
  });
  it("today gives a single day", () => {
    const r = presetRange("today", today);
    expect(rangeDays(r.from, r.to)).toBe(1);
  });
});

describe("previousPeriod", () => {
  it("matches the current span and ends the day before from", () => {
    const f = new Date(2026, 4, 8); // 2026-05-08
    const t = new Date(2026, 4, 14); // 2026-05-14 (7 days inclusive)
    const prev = previousPeriod(f, t);
    expect(prev.to.getDate()).toBe(7); // day before from
  });
});

describe("isValidRange", () => {
  it("accepts a normal range", () => {
    expect(isValidRange("2026-01-01", "2026-01-31")).toBe(true);
  });
  it("rejects from > to", () => {
    expect(isValidRange("2026-02-01", "2026-01-01")).toBe(false);
  });
  it("rejects too-wide ranges", () => {
    expect(isValidRange("2020-01-01", "2026-12-31")).toBe(false);
  });
  it("rejects null inputs", () => {
    expect(isValidRange(null, "2026-01-01")).toBe(false);
    expect(isValidRange("2026-01-01", null)).toBe(false);
  });
});

describe("pickGranularity", () => {
  it("picks hour for ≤ 2 days", () => {
    expect(pickGranularity(1)).toBe("hour");
    expect(pickGranularity(2)).toBe("hour");
  });
  it("picks day for 3-60 days", () => {
    expect(pickGranularity(7)).toBe("day");
    expect(pickGranularity(60)).toBe("day");
  });
  it("picks week for 61-365 days", () => {
    expect(pickGranularity(90)).toBe("week");
  });
  it("picks month past a year", () => {
    expect(pickGranularity(400)).toBe("month");
  });
});
