
/// <reference types="vitest" />
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createWell, tickWell, harvestWell, formatTimeLeft } from "./magicWell";

describe("tickWell (with mocked Date)", () => {
  let now: number;

  beforeEach(() => {
    now = Date.now();
    vi.spyOn(Date, 'now').mockReturnValue(now);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("initial state", () => {
    const well = createWell();
    expect(well.pending).toBe(1);
    const result = tickWell(well);
    expect(result.well).toEqual(well); // No change if no time passed
    expect(result.filled).toBe(false);
    expect(result.dried).toBe(false);
    // harvestReady is not a property of ManaWellState, but we can compute it
    expect(result.well.pending > 0).toBe(true);
  });

  it("after fill interval: pending increases", () => {
    const well = createWell();
    const FILL_INTERVAL = 6 * 60 * 60 * 1000;
    vi.spyOn(Date, 'now').mockReturnValue(now + FILL_INTERVAL + 1); // Just after fill time
    
    const result = tickWell(well);
    expect(result.well.pending).toBe(2); // 1 + 1
    expect(result.filled).toBe(true);
    expect(result.dried).toBe(false);
    expect(result.well.pending > 0).toBe(true);
  });

  it("after dry interval without harvest: pending=0 then immediately filled to 1", () => {
    const well = createWell();
    const FILL_INTERVAL = 6 * 60 * 60 * 1000;
    const DRY_THRESHOLD = 6 * 60 * 60 * 1000;
    // Advance time to just after dryAt (which is nextFillAt + DRY_THRESHOLD)
    // Initially, nextFillAt = now + FILL_INTERVAL, dryAt = now + FILL_INTERVAL + DRY_THRESHOLD
    vi.spyOn(Date, 'now').mockReturnValue(now + FILL_INTERVAL + DRY_THRESHOLD + 1);
    
    const result = tickWell(well);
    // First, we dry: pending goes to 0, dried=true
    // Then, because we are dried and now >= nextFillAt (original nextFillAt), we fill: pending=1, filled=true
    expect(result.well.pending).toBe(1);
    expect(result.dried).toBe(true);
    expect(result.filled).toBe(true);
    expect(result.well.pending > 0).toBe(true);
  });

  it("harvestWell: removes pending mana and updates statistics", () => {
    const well = createWell();
    // Let's first advance time to get some pending mana
    const FILL_INTERVAL = 6 * 60 * 60 * 1000;
    vi.spyOn(Date, 'now').mockReturnValue(now + FILL_INTERVAL + 1); // pending becomes 2
    let wetWell = tickWell(well);
    // Now harvest
    const harvested = harvestWell(wetWell.well);
    expect(harvested.amount).toBe(2);
    expect(harvested.well.pending).toBe(0);
    expect(harvested.well.totalHarvests).toBe(1);
    expect(harvested.well.totalHarvested).toBe(2);
  });
});

describe("formatTimeLeft (localized units)", () => {
  it("uses Russian units for ru locale", () => {
    const H = 6 * 60 * 60 * 1000;
    expect(formatTimeLeft(H, "ru")).toBe("6ч 0м");
    expect(formatTimeLeft(2 * 1000, "ru")).toBe("2с");
  });

  it("uses English units for non-Russian locales (default)", () => {
    const H = 6 * 60 * 60 * 1000;
    expect(formatTimeLeft(H)).toBe("6h 0m");
    expect(formatTimeLeft(H, "en")).toBe("6h 0m");
    expect(formatTimeLeft(H, "es")).toBe("6h 0m");
    expect(formatTimeLeft(2 * 1000)).toBe("2s");
  });

  it("shows full minutes-seconds breadcrumb for sub-hour values", () => {
    const FIFTEEN_MIN = 15 * 60 * 1000 + 5000; // 15m 5s
    expect(formatTimeLeft(FIFTEEN_MIN, "en")).toBe("15m 5s");
    expect(formatTimeLeft(FIFTEEN_MIN, "ru")).toBe("15м 5с");
  });

  it("reports elapsed time per locale", () => {
    expect(formatTimeLeft(0, "ru")).toBe("пора!");
    expect(formatTimeLeft(-1000)).toBe("ready!");
  });
});