import * as fc from "fast-check";
import { describe, expect, it } from "vitest";
import { applyReorder, verifyReorderIntegrity } from "../components/ScheduleTable";
import type { CoilRecord, ScheduleItem } from "../api/types";

function makeItem(id: number, position: number): ScheduleItem {
  const coil: CoilRecord = {
    id,
    hr_coil_no: `C${id}`,
    thk: 1,
    wdt: 100,
    wgt: 1,
    grade: "G",
    age_hours: 100,
    status: "TA",
    product: "HRPO",
    silicon_pct: null,
    silicon_band: null,
    is_apl7: false,
    all_columns: {},
  };
  return { id, position, coil, is_apl7: false };
}

function shuffleArray<T>(arr: T[]): T[] {
  const copy = [...arr];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

describe("reorder sequence integrity", () => {
  // Feature: cpl2-scheduling-system, Property 19 (frontend): Reorder produces valid sequence
  it("property: reorder preserves all coils with contiguous positions", () => {
    fc.assert(
      fc.property(
        fc.uniqueArray(fc.integer({ min: 1, max: 100 }), { minLength: 1, maxLength: 20 }),
        (ids) => {
          const items = ids.map((id, idx) => makeItem(id, idx + 1));
          const shuffledIds = shuffleArray(ids);
          const reordered = applyReorder(items, shuffledIds);
          expect(verifyReorderIntegrity(items, reordered)).toBe(true);
        },
      ),
      { numRuns: 100 },
    );
  });
});
