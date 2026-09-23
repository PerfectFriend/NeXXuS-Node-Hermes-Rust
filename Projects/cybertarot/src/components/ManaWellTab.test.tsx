
// Component tests: ManaWellTab renders timers, banners, stats, harvest button
// (EVOLUTION_PLAN.md 1.4: "Component: ManaWellTab рендерит таймеры")

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, cleanup } from "@testing-library/react";
import { ManaWellTab } from "@/components/ManaWellTab";
import type { ManaWellState } from "@/services/magicWell";

afterEach(cleanup);

const HOUR = 60 * 60 * 1000;

function makeWell(overrides: Partial<ManaWellState> = {}): ManaWellState {
  const now = Date.now();
  return {
    pending: 3,
    nextFillAt: now + 5 * HOUR, // > 1h until next fill
    dryAt: now + 11 * HOUR, // > 1h until dry
    totalHarvests: 2,
    totalHarvested: 7,
    totalDryouts: 1,
    ...overrides,
  };
}

function renderTab(well: ManaWellState, props = {}) {
  return render(
    <ManaWellTab
      locale="en"
      well={well}
      onHarvest={vi.fn()}
      harvestReady={well.pending > 0}
      filled={false}
      dried={false}
      {...props}
    />,
  );
}

describe("ManaWellTab", () => {
  it("renders pending mana amount in the well circle", () => {
    const { getByText } = renderTab(makeWell());
    expect(getByText("3")).toBeTruthy();
    expect(getByText("mana")).toBeTruthy();
  });

  it("renders localized fill timer in h/m format when > 1h remains", () => {
    const { getAllByText } = renderTab(makeWell());
    // Both timers (fill + dry) show h/m format for this fixture
    const timers = getAllByText(/^\d+(?:h|ч)\s+\d+(?:m|м)$/u);
    expect(timers.length).toBe(2);
  });

  it("renders 'ready!' when the well is empty (timers overdue)", () => {
    const now = Date.now();
    const emptyWell = makeWell({
      pending: 0,
      nextFillAt: now - 1000,
      dryAt: now - 1000,
    });
    const { getAllByText } = renderTab(emptyWell);
    expect(getAllByText("ready!").length).toBe(2);
  });

  it("shows Russian units with ru locale", () => {
    const { getAllByText } = render(<ManaWellTab locale="ru" well={makeWell()} onHarvest={vi.fn()} harvestReady filled={false} dried={false} />);
    expect(getAllByText(/^\d+(?:h|ч)\s+\d+(?:m|м)$/u).length).toBe(2);
  });

  it("enables harvest button when ready and fires onHarvest on click", () => {
    const onHarvest = vi.fn();
    const { getByRole } = renderTab(makeWell(), { onHarvest });
    const btn = getByRole("button");
    expect(btn.hasAttribute("disabled")).toBe(false);
    fireEvent.click(btn);
    expect(onHarvest).toHaveBeenCalledTimes(1);
  });

  it("disables harvest button when well is empty", () => {
    const onHarvest = vi.fn();
    const now = Date.now();
    const emptyWell = makeWell({ pending: 0, nextFillAt: now - 1000, dryAt: now - 1000 });
    const { getByRole } = renderTab(emptyWell, { onHarvest });
    const btn = getByRole("button");
    expect(btn.hasAttribute("disabled")).toBe(true);
    expect(btn.textContent).toContain("Well is empty");
    fireEvent.click(btn);
    expect(onHarvest).not.toHaveBeenCalled();
  });

  it("shows filled banner only when filled=true", () => {
    const { getByText, queryByText } = renderTab(makeWell(), { filled: true });
    expect(getByText(/The well is full!/)).toBeTruthy();
    expect(queryByText(/The well ran dry!/)).toBeNull();
  });

  it("shows dried banner only when dried=true", () => {
    const { getByText, queryByText } = renderTab(makeWell(), { dried: true });
    expect(getByText(/The well ran dry!/)).toBeTruthy();
    expect(queryByText(/The well is full!/)).toBeNull();
  });

  it("renders no banners when neither filled nor dried", () => {
    const { queryByText } = renderTab(makeWell());
    expect(queryByText(/The well is full!/)).toBeNull();
    expect(queryByText(/The well ran dry!/)).toBeNull();
  });

  it("renders harvest stats (harvests, total mana, dry-outs)", () => {
    const { getByText } = renderTab(makeWell());
    expect(getByText("Harvests")).toBeTruthy();
    expect(getByText("Total mana")).toBeTruthy();
    expect(getByText("Dry-outs")).toBeTruthy();
    // Stat values from fixture: 2 harvests, 7 mana, 1 dry-out
    expect(getByText("7")).toBeTruthy();
    expect(getByText("1")).toBeTruthy();
  });
});
