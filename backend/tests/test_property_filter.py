"""Property-based tests for engine/filter_pipeline.py.

# Feature: cpl2-scheduling-system, Property 5: Filter pipeline correctness

Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

from __future__ import annotations

import os
import sys

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.filter_pipeline import ELIGIBLE_PRODUCTS, ELIGIBLE_STATUSES, run_filter_pipeline
from engine.parser import CoilRow

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Optional string (including None) — short ascii to keep generation fast
_opt_str = st.one_of(st.none(), st.text(alphabet=st.characters(whitelist_categories=("Lu","Ll")), min_size=0, max_size=8))

# Optional numeric
_opt_float = st.one_of(
    st.none(),
    st.floats(min_value=0.0, max_value=9999.0, allow_nan=False, allow_infinity=False),
)
_opt_int = st.one_of(st.none(), st.integers(min_value=0, max_value=10))


@st.composite
def coil_row_strategy(draw) -> CoilRow:
    """Generate a CoilRow with fully random field values."""
    return CoilRow(
        hr_order_no=draw(_opt_str),
        hr_coil_no=draw(st.text(min_size=1, max_size=16)),
        thk=draw(_opt_float),
        wdt=draw(_opt_float),
        wgt=draw(_opt_float),
        grade=draw(_opt_str),
        age_hours=draw(_opt_float),
        status=draw(_opt_str),
        cust=draw(_opt_str),
        cr_coil_no=draw(_opt_str),
        routing=draw(_opt_str),
        product=draw(_opt_str),
        act_path=draw(_opt_int),
        prev_unit=draw(_opt_int),
        silicon_pct=draw(_opt_float),
        receiving_remarks=draw(_opt_str),
        order_status=draw(_opt_str),
        tdc=draw(_opt_str),
        edge_condth=draw(_opt_str),
        ord_wdth_min=draw(_opt_float),
        ord_wdth_max=draw(_opt_float),
        target_width=draw(_opt_float),
        next_work_center=draw(_opt_str),
        all_columns={},
    )


_rows_strategy = st.lists(coil_row_strategy(), min_size=0, max_size=20)

# ---------------------------------------------------------------------------
# Property 5: Filter pipeline correctness
# Task 5.2 — Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
# ---------------------------------------------------------------------------


@given(rows=_rows_strategy)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property5_filter_pipeline_correctness(rows: list[CoilRow]) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 5: Filter pipeline correctness

    For any dataset processed by the filter pipeline, ALL of the following
    must hold simultaneously on the result:

    1. Every eligible_coil.product is in {HRPO, HRSPO, NGO FP}
    2. Every eligible_coil.act_path == 0 AND prev_unit == 0
    3. Every eligible_coil.status is in {TA, TW}
    4. No eligible_coil.order_status (stripped, case-insensitive) == CLOSED
    5. No eligible_coil.receiving_remarks (stripped, case-insensitive) == APL7
    6. Every row with receiving_remarks == APL7 from the original input
       appears in apl7_coils, not eligible_coils
    7. Exclusion counts sum correctly:
       excluded_product + excluded_act_path + excluded_status +
       excluded_closed + apl7_count + len(eligible_coils) == len(rows)

    **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**
    """
    result = run_filter_pipeline(rows)

    # ---- Property 1: product membership --------------------------------
    for coil in result.eligible_coils:
        product = (coil.product or "").strip()
        assert product in ELIGIBLE_PRODUCTS, (
            f"Eligible coil has invalid product: {coil.product!r}"
        )

    # ---- Property 2: act_path and prev_unit must both be 0 -------------
    for coil in result.eligible_coils:
        assert coil.act_path == 0, (
            f"Eligible coil has act_path={coil.act_path!r} (expected 0)"
        )
        assert coil.prev_unit == 0, (
            f"Eligible coil has prev_unit={coil.prev_unit!r} (expected 0)"
        )

    # ---- Property 3: status membership ---------------------------------
    for coil in result.eligible_coils:
        status = (coil.status or "").strip()
        assert status in ELIGIBLE_STATUSES, (
            f"Eligible coil has invalid status: {coil.status!r}"
        )

    # ---- Property 4: no CLOSED order_status ---------------------------
    for coil in result.eligible_coils:
        order_status = (coil.order_status or "").strip().upper()
        assert order_status != "CLOSED", (
            f"Eligible coil has order_status=CLOSED: {coil.order_status!r}"
        )

    # ---- Property 5: no APL7 receiving_remarks in eligible_coils ------
    for coil in result.eligible_coils:
        remarks = (coil.receiving_remarks or "").strip().upper()
        assert remarks != "APL7", (
            f"Eligible coil has receiving_remarks=APL7: {coil.receiving_remarks!r}"
        )

    # ---- Property 6: APL7 rows from original input go to apl7_coils --
    # Identify original rows that passed through steps 1-4 and have APL7 remarks.
    # We check by identity (id) — the pipeline passes the same objects through.
    apl7_ids = {id(c) for c in result.apl7_coils}
    eligible_ids = {id(c) for c in result.eligible_coils}

    # First, find which input rows WOULD reach step 5 (i.e. pass steps 1–4)
    def passes_steps_1_to_4(row: CoilRow) -> bool:
        product = (row.product or "").strip()
        if product not in ELIGIBLE_PRODUCTS:
            return False
        if row.act_path != 0 or row.prev_unit != 0:
            return False
        status = (row.status or "").strip()
        if status not in ELIGIBLE_STATUSES:
            return False
        order_status = (row.order_status or "").strip().upper()
        if order_status == "CLOSED":
            return False
        return True

    for row in rows:
        if passes_steps_1_to_4(row):
            remarks = (row.receiving_remarks or "").strip().upper()
            if remarks == "APL7":
                assert id(row) in apl7_ids, (
                    "A row with receiving_remarks=APL7 (that passed steps 1–4) "
                    "did not appear in apl7_coils"
                )
                assert id(row) not in eligible_ids, (
                    "A row with receiving_remarks=APL7 appeared in eligible_coils"
                )

    # ---- Property 7: exclusion count identity --------------------------
    total_accounted = (
        result.excluded_product
        + result.excluded_act_path
        + result.excluded_status
        + result.excluded_closed
        + result.apl7_count
        + len(result.eligible_coils)
    )
    assert total_accounted == len(rows), (
        f"Count mismatch: {total_accounted} accounted for, "
        f"but {len(rows)} rows were input. "
        f"excluded_product={result.excluded_product}, "
        f"excluded_act_path={result.excluded_act_path}, "
        f"excluded_status={result.excluded_status}, "
        f"excluded_closed={result.excluded_closed}, "
        f"apl7_count={result.apl7_count}, "
        f"eligible={len(result.eligible_coils)}"
    )
