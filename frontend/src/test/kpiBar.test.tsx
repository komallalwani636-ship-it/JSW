import { render, screen } from "@testing-library/react";
import * as fc from "fast-check";
import { describe, expect, it } from "vitest";
import { KpiBar, verifyKpiArithmetic } from "../components/KpiBar";
import type { KpiResult } from "../api/types";

function makeKpi(overrides: Partial<KpiResult> = {}): KpiResult {
  return {
    total_eligible: 10,
    hrpo_count: 4,
    hrpo_weight: 40,
    hrspo_count: 3,
    hrspo_weight: 30,
    ngo_count: 3,
    ngo_weight: 15,
    age_gt_72h: 5,
    age_gt_120h: 2,
    age_gt_168h: 1,
    violation_count: 0,
    schedule_status: "draft",
    version_label: "2024-01-01-v1",
    ...overrides,
  };
}

describe("KpiBar", () => {
  it("renders KPI values", () => {
    render(<KpiBar kpis={makeKpi()} />);
    expect(screen.getByTestId("kpi-total-eligible")).toHaveTextContent("10");
  });

  // Feature: cpl2-scheduling-system, Property 22 (frontend): KPI consistency
  it("property: total_eligible equals sum of product counts", () => {
    fc.assert(
      fc.property(
        fc.nat({ max: 50 }),
        fc.nat({ max: 50 }),
        fc.nat({ max: 50 }),
        (hrpo, hrspo, ngo) => {
          const kpis = makeKpi({
            hrpo_count: hrpo,
            hrspo_count: hrspo,
            ngo_count: ngo,
            total_eligible: hrpo + hrspo + ngo,
          });
          expect(verifyKpiArithmetic(kpis)).toBe(true);
        },
      ),
      { numRuns: 100 },
    );
  });
});
