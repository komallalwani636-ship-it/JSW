"""Property-based tests for engine/kpi_calculator.py.

# Feature: cpl2-scheduling-system
Property 22: KPI consistency (Task 8.3)

Validates: Requirements 8.1, 8.2
"""

from __future__ import annotations

import os
import sys

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.parser import CoilRow
from engine.kpi_calculator import compute_kpis


# ---------------------------------------------------------------------------
# Helper — build a minimal CoilRow for KPI testing
# ---------------------------------------------------------------------------

def _make_coil(
    product: str | None,
    wgt: float | None,
    age_hours: float | None,
    hr_coil_no: str = "C001",
) -> CoilRow:
    """Return a CoilRow with only the fields relevant to KPI computation set."""
    return CoilRow(
        hr_order_no=None,
        hr_coil_no=hr_coil_no,
        thk=None,
        wdt=None,
        wgt=wgt,
        grade=None,
        age_hours=age_hours,
        status=None,
        cust=None,
        cr_coil_no=None,
        routing=None,
        product=product,
        act_path=None,
        prev_unit=None,
        silicon_pct=None,
        receiving_remarks=None,
        order_status=None,
        tdc=None,
        edge_condth=None,
        ord_wdth_min=None,
        ord_wdth_max=None,
        target_width=None,
        next_work_center=None,
        all_columns={},
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_product_st = st.sampled_from(["HRPO", "HRSPO", "NGO FP", "OTHER"])

_wgt_st = st.one_of(
    st.none(),
    st.floats(
        min_value=0.0,
        max_value=100.0,
        allow_nan=False,
        allow_infinity=False,
        allow_subnormal=False,
    ),
)

_age_hours_st = st.one_of(
    st.none(),
    st.floats(
        min_value=0.0,
        max_value=500.0,
        allow_nan=False,
        allow_infinity=False,
        allow_subnormal=False,
    ),
)


@st.composite
def _eligible_coil_list(draw):
    """Generate a list of CoilRow objects with random product, wgt, and age_hours."""
    n = draw(st.integers(min_value=0, max_value=30))
    coils = []
    for k in range(n):
        coils.append(_make_coil(
            product=draw(_product_st),
            wgt=draw(_wgt_st),
            age_hours=draw(_age_hours_st),
            hr_coil_no=f"C{k:04d}",
        ))
    return coils


# ---------------------------------------------------------------------------
# Property 22: KPI consistency  (Task 8.3)
# ---------------------------------------------------------------------------


@given(eligible_coils=_eligible_coil_list())
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property22_kpi_consistency(eligible_coils: list[CoilRow]) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 22: KPI consistency

    For any list of eligible CoilRow objects and an empty violations list,
    the computed KpiResult must satisfy:

    1. total_eligible == hrpo_count + hrspo_count + ngo_count
    2. hrpo_weight  == sum(c.wgt or 0.0 for c in eligible_coils if c.product == "HRPO")
       hrspo_weight == sum(c.wgt or 0.0 for c in eligible_coils if c.product == "HRSPO")
       ngo_weight   == sum(c.wgt or 0.0 for c in eligible_coils if c.product == "NGO FP")
    3. age_gt_72h == sum(1 for c in eligible_coils
                         if c.age_hours is not None and c.age_hours > 72)

    **Validates: Requirements 8.1, 8.2**
    """
    result = compute_kpis(
        eligible_coils=eligible_coils,
        violations=[],
        schedule_status="draft",
        version_label="test-v1",
    )

    # ---- Property 1: total_eligible arithmetic -------------------------
    assert result.total_eligible == result.hrpo_count + result.hrspo_count + result.ngo_count, (
        f"total_eligible ({result.total_eligible}) != "
        f"hrpo_count ({result.hrpo_count}) + "
        f"hrspo_count ({result.hrspo_count}) + "
        f"ngo_count ({result.ngo_count})"
    )

    # ---- Property 2: weight totals -------------------------------------
    expected_hrpo_weight = sum(
        c.wgt if c.wgt is not None else 0.0
        for c in eligible_coils
        if c.product == "HRPO"
    )
    expected_hrspo_weight = sum(
        c.wgt if c.wgt is not None else 0.0
        for c in eligible_coils
        if c.product == "HRSPO"
    )
    expected_ngo_weight = sum(
        c.wgt if c.wgt is not None else 0.0
        for c in eligible_coils
        if c.product == "NGO FP"
    )

    assert abs(result.hrpo_weight - expected_hrpo_weight) < 1e-9, (
        f"hrpo_weight mismatch: got {result.hrpo_weight}, expected {expected_hrpo_weight}"
    )
    assert abs(result.hrspo_weight - expected_hrspo_weight) < 1e-9, (
        f"hrspo_weight mismatch: got {result.hrspo_weight}, expected {expected_hrspo_weight}"
    )
    assert abs(result.ngo_weight - expected_ngo_weight) < 1e-9, (
        f"ngo_weight mismatch: got {result.ngo_weight}, expected {expected_ngo_weight}"
    )

    # ---- Property 3: age band count ------------------------------------
    expected_age_gt_72h = sum(
        1 for c in eligible_coils
        if c.age_hours is not None and c.age_hours > 72
    )
    assert result.age_gt_72h == expected_age_gt_72h, (
        f"age_gt_72h mismatch: got {result.age_gt_72h}, expected {expected_age_gt_72h}"
    )
