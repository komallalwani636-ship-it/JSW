"""Property-based tests for engine/sequencer_hrpo.py.

# Feature: cpl2-scheduling-system
Properties 7–11 (Tasks 6.2–6.6)

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.7, 3.8, 3.9
"""

from __future__ import annotations

import os
import sys

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.parser import CoilRow
from engine.sequencer_hrpo import TDC_GRADES, sequence_hrpo_hrspo

# ---------------------------------------------------------------------------
# Shared grade lists
# ---------------------------------------------------------------------------

NON_TDC_GRADES = ["GRADE_A", "GRADE_B", "GRADE_C", "GRADE_D", "GRADE_E"]
TDC_GRADES_LIST = sorted(TDC_GRADES)

# ---------------------------------------------------------------------------
# Shared coil-building helper
# ---------------------------------------------------------------------------


def _make_coil(
    thk: float | None = 3.0,
    wdt: float | None = 1000.0,
    age_hours: float | None = 100.0,
    grade: str | None = "GRADE_A",
    product: str = "HRPO",
) -> CoilRow:
    return CoilRow(
        hr_order_no=None,
        hr_coil_no="C001",
        thk=thk,
        wdt=wdt,
        wgt=None,
        grade=grade,
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

_eligible_age = st.floats(
    min_value=72.01,
    max_value=2000.0,
    allow_nan=False,
    allow_infinity=False,
)

_ineligible_age = st.one_of(
    st.none(),
    st.floats(min_value=0.0, max_value=72.0, allow_nan=False, allow_infinity=False),
)

_thk_thick = st.floats(min_value=2.0, max_value=6.0, allow_nan=False, allow_infinity=False)
_thk_thin  = st.floats(min_value=1.6, max_value=1.999, allow_nan=False, allow_infinity=False)
_wdt       = st.floats(min_value=600.0, max_value=2000.0, allow_nan=False, allow_infinity=False)

_product   = st.sampled_from(["HRPO", "HRSPO"])
_non_tdc   = st.sampled_from(NON_TDC_GRADES)
_tdc_grade = st.sampled_from(TDC_GRADES_LIST)
_any_grade = st.one_of(_non_tdc, _tdc_grade)


@st.composite
def _eligible_coil(draw, grade_st=None):
    """Generate one eligible CoilRow (age_hours > 72)."""
    if grade_st is None:
        grade_st = _any_grade
    thk_range = draw(st.sampled_from(["thick", "thin"]))
    thk = draw(_thk_thick if thk_range == "thick" else _thk_thin)
    return _make_coil(
        thk=thk,
        wdt=draw(_wdt),
        age_hours=draw(_eligible_age),
        grade=draw(grade_st),
        product=draw(_product),
    )


@st.composite
def _ineligible_coil(draw):
    """Generate a CoilRow that should be filtered by the age filter."""
    thk_range = draw(st.sampled_from(["thick", "thin"]))
    thk = draw(_thk_thick if thk_range == "thick" else _thk_thin)
    return _make_coil(
        thk=thk,
        wdt=draw(_wdt),
        age_hours=draw(_ineligible_age),
        grade=draw(_any_grade),
        product=draw(_product),
    )


# ---------------------------------------------------------------------------
# Property 7: HRPO/HRSPO age eligibility  (Task 6.2)
# ---------------------------------------------------------------------------


@given(
    eligible=st.lists(_eligible_coil(), min_size=0, max_size=10),
    ineligible=st.lists(_ineligible_coil(), min_size=1, max_size=10),
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property7_age_eligibility(
    eligible: list[CoilRow],
    ineligible: list[CoilRow],
) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 7: HRPO/HRSPO age eligibility

    For any generated HRPO/HRSPO coil set (including coils with age_hours <= 72
    or age_hours=None), no coil with age_hours <= 72 or None should appear in
    the output sequence.

    **Validates: Requirement 3.1**
    """
    coils = eligible + ineligible
    result = sequence_hrpo_hrspo(coils)

    ineligible_ids = {id(c) for c in ineligible}
    for coil in result.sequence:
        # Must have age_hours > 72
        assert coil.age_hours is not None and coil.age_hours > 72, (
            f"Coil with age_hours={coil.age_hours!r} appeared in output sequence; "
            "only age_hours > 72 should be sequenced."
        )
        # Must not be one of the explicitly ineligible coils
        assert id(coil) not in ineligible_ids, (
            f"An ineligible coil (age_hours={coil.age_hours!r}) appeared in the output."
        )


# ---------------------------------------------------------------------------
# Property 8: HRPO/HRSPO thickness constraint  (Task 6.3)
# ---------------------------------------------------------------------------


@st.composite
def _band_conforming_thick_coils(draw):
    """Generate a list of eligible coils all in the 'thick' range (thk >= 2.0).

    We ensure pairs within a band satisfy the thickness window so the sequencer
    can actually group them together, letting us test whether consecutive pairs
    in the output satisfy the constraint.
    """
    anchor_thk = draw(_thk_thick)
    n = draw(st.integers(min_value=1, max_value=15))
    coils = []
    for _ in range(n):
        # ±0.4 ensures any two coils differ by at most 0.8 < 1.0 (the band window)
        thk_offset = draw(st.floats(min_value=-0.4, max_value=0.4,
                                    allow_nan=False, allow_infinity=False))
        thk = max(2.0, min(6.0, anchor_thk + thk_offset))
        coils.append(_make_coil(
            thk=thk,
            wdt=draw(_wdt),
            age_hours=draw(_eligible_age),
            grade=draw(_non_tdc),
            product=draw(_product),
        ))
    return coils


@st.composite
def _band_conforming_thin_coils(draw):
    """Generate eligible coils all in the thin range (thk < 2.0)."""
    anchor_thk = draw(_thk_thin)
    n = draw(st.integers(min_value=1, max_value=15))
    coils = []
    for _ in range(n):
        # ±0.15 ensures any two coils differ by at most 0.3 < 0.4 (the thin band window)
        thk_offset = draw(st.floats(min_value=-0.15, max_value=0.15,
                                    allow_nan=False, allow_infinity=False))
        thk = max(1.6, min(1.999, anchor_thk + thk_offset))
        coils.append(_make_coil(
            thk=thk,
            wdt=draw(_wdt),
            age_hours=draw(_eligible_age),
            grade=draw(_non_tdc),
            product=draw(_product),
        ))
    return coils


@given(
    thick_coils=_band_conforming_thick_coils(),
    thin_coils=_band_conforming_thin_coils(),
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property8_thickness_constraint(
    thick_coils: list[CoilRow],
    thin_coils: list[CoilRow],
) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 8: HRPO/HRSPO thickness constraint

    For any generated HRPO/HRSPO sequence, for every consecutive pair (a, b):
    - If both thk >= 2.0: |a.thk - b.thk| <= 1.0
    - If both thk < 2.0:  |a.thk - b.thk| <= 0.4
    - If either thk is None: skip the check.

    **Validates: Requirements 3.2, 3.3**
    """
    result = sequence_hrpo_hrspo(thick_coils + thin_coils)
    seq = result.sequence

    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        if a.thk is None or b.thk is None:
            continue  # cannot check; spec says skip

        if a.thk >= 2.0 and b.thk >= 2.0:
            diff = abs(a.thk - b.thk)
            assert diff <= 1.0, (
                f"Position {i}-{i+1}: both thk >= 2.0 but Δthk={diff:.4f} > 1.0 "
                f"(a.thk={a.thk}, b.thk={b.thk})"
            )
        elif a.thk < 2.0 and b.thk < 2.0:
            diff = abs(a.thk - b.thk)
            assert diff <= 0.4, (
                f"Position {i}-{i+1}: both thk < 2.0 but Δthk={diff:.4f} > 0.4 "
                f"(a.thk={a.thk}, b.thk={b.thk})"
            )
        # Mixed range (one >= 2.0, one < 2.0): bands are separate, so mixed
        # pairs should not appear in the output; but if they do (e.g. None thk
        # edge), we don't assert here — that case is handled by the band logic.


# ---------------------------------------------------------------------------
# Property 9: HRPO/HRSPO width constraint  (Task 6.4)
# ---------------------------------------------------------------------------


@st.composite
def _band_conforming_mixed_wdt_coils(draw):
    """Generate eligible coils all within one band (same thick range, tight thk/wdt).

    To ensure the width constraint is meaningful, all coils are anchored within the
    band window:
    - thick (>=2.0): Δthk <= 0.8 of anchor, Δwdt < 200 of anchor_wdt
    - thin  (<2.0):  Δthk <= 0.3 of anchor, Δwdt < 100 of anchor_wdt
    This guarantees they land in the same band and avoids cross-band adjacency.
    """
    thick_range = draw(st.sampled_from(["thick", "thin"]))
    anchor_thk = draw(_thk_thick if thick_range == "thick" else _thk_thin)
    anchor_wdt = draw(_wdt)
    n = draw(st.integers(min_value=1, max_value=15))
    coils = []
    for _ in range(n):
        if thick_range == "thick":
            thk_offset = draw(st.floats(min_value=-0.4, max_value=0.4,
                                        allow_nan=False, allow_infinity=False))
            thk = max(2.0, min(6.0, anchor_thk + thk_offset))
            # Keep wdt within < 250 of anchor so two coils differ by < 300
            wdt_offset = draw(st.floats(min_value=-120.0, max_value=120.0,
                                        allow_nan=False, allow_infinity=False))
            wdt = max(600.0, min(2000.0, anchor_wdt + wdt_offset))
        else:
            thk_offset = draw(st.floats(min_value=-0.15, max_value=0.15,
                                        allow_nan=False, allow_infinity=False))
            thk = max(1.6, min(1.999, anchor_thk + thk_offset))
            # Keep wdt within < 120 of anchor so two coils differ by < 150
            wdt_offset = draw(st.floats(min_value=-60.0, max_value=60.0,
                                        allow_nan=False, allow_infinity=False))
            wdt = max(600.0, min(2000.0, anchor_wdt + wdt_offset))
        coils.append(_make_coil(
            thk=thk,
            wdt=wdt,
            age_hours=draw(_eligible_age),
            grade=draw(_non_tdc),
            product=draw(_product),
        ))
    return coils


@given(coils=_band_conforming_mixed_wdt_coils())
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property9_width_constraint(coils: list[CoilRow]) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 9: HRPO/HRSPO width constraint

    For any generated HRPO/HRSPO sequence, for every consecutive pair (a, b):
    - If both thk >= 2.0: |a.wdt - b.wdt| < 300
    - If both thk < 2.0:  |a.wdt - b.wdt| < 150
    - If either thk or wdt is None: skip that pair.

    **Validates: Requirements 3.4, 3.5**
    """
    result = sequence_hrpo_hrspo(coils)
    seq = result.sequence

    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        if a.thk is None or b.thk is None:
            continue
        if a.wdt is None or b.wdt is None:
            continue

        if a.thk >= 2.0 and b.thk >= 2.0:
            diff = abs(a.wdt - b.wdt)
            assert diff < 300.0, (
                f"Position {i}-{i+1}: both thk >= 2.0 but Δwdt={diff:.2f} >= 300 "
                f"(a.wdt={a.wdt}, b.wdt={b.wdt})"
            )
        elif a.thk < 2.0 and b.thk < 2.0:
            diff = abs(a.wdt - b.wdt)
            assert diff < 150.0, (
                f"Position {i}-{i+1}: both thk < 2.0 but Δwdt={diff:.2f} >= 150 "
                f"(a.wdt={a.wdt}, b.wdt={b.wdt})"
            )


# ---------------------------------------------------------------------------
# Property 10: Within-band age ordering  (Task 6.5)
# ---------------------------------------------------------------------------


def _same_band(a: CoilRow, b: CoilRow) -> bool:
    """Return True if (a, b) satisfy the same-band window using a as anchor."""
    if a.thk is None or b.thk is None:
        return False
    if (a.thk >= 2.0) != (b.thk >= 2.0):
        return False  # mixed range
    thk_diff = abs(a.thk - b.thk)
    wdt_diff = abs((a.wdt or 0.0) - (b.wdt or 0.0))
    if a.thk >= 2.0:
        return thk_diff <= 1.0 and wdt_diff < 300.0
    else:
        return thk_diff <= 0.4 and wdt_diff < 150.0


@st.composite
def _age_ordered_band_input(draw):
    """Generate coils all within one band (same thick range, tight thk/wdt)."""
    thick_range = draw(st.sampled_from(["thick", "thin"]))
    base_thk = draw(_thk_thick if thick_range == "thick" else _thk_thin)
    base_wdt = draw(_wdt)
    n = draw(st.integers(min_value=2, max_value=10))

    coils = []
    for _ in range(n):
        if thick_range == "thick":
            thk = max(2.0, min(6.0, base_thk + draw(
                st.floats(min_value=-0.4, max_value=0.4,
                          allow_nan=False, allow_infinity=False))))
            wdt = max(600.0, min(2000.0, base_wdt + draw(
                st.floats(min_value=-100.0, max_value=100.0,
                          allow_nan=False, allow_infinity=False))))
        else:
            thk = max(1.6, min(1.999, base_thk + draw(
                st.floats(min_value=-0.15, max_value=0.15,
                          allow_nan=False, allow_infinity=False))))
            wdt = max(600.0, min(2000.0, base_wdt + draw(
                st.floats(min_value=-50.0, max_value=50.0,
                          allow_nan=False, allow_infinity=False))))
        coils.append(_make_coil(
            thk=thk,
            wdt=wdt,
            age_hours=draw(_eligible_age),
            grade=draw(_non_tdc),
            product=draw(_product),
        ))
    return coils


@given(coils=_age_ordered_band_input())
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property10_within_band_age_ordering(coils: list[CoilRow]) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 10: Within-band age ordering

    For a sequence of coils returned by the sequencer, identify contiguous
    groups that form a band (consecutive pairs that both satisfy the same-band
    window with the first coil as anchor). Within each such group, assert that
    age_hours is non-increasing (descending). Ties are allowed.

    **Validates: Requirement 3.7**
    """
    result = sequence_hrpo_hrspo(coils)
    seq = result.sequence

    if len(seq) < 2:
        return  # nothing to check

    # Walk consecutive pairs; when a pair is in the same band, they are part of
    # the same contiguous run. Collect runs and verify each is age-descending.
    i = 0
    while i < len(seq):
        # Start a run from i
        run_start = i
        j = i
        while j + 1 < len(seq) and _same_band(seq[j], seq[j + 1]):
            j += 1
        run = seq[run_start : j + 1]

        # Verify age_hours is non-increasing within the run
        for k in range(len(run) - 1):
            age_a = run[k].age_hours
            age_b = run[k + 1].age_hours
            if age_a is None or age_b is None:
                continue  # skip None ages
            assert age_a >= age_b, (
                f"Within-band age ordering violated at run positions {k}-{k+1}: "
                f"age_hours went from {age_a} to {age_b} (should be non-increasing)."
            )

        i = j + 1  # move to coil after the end of this run


# ---------------------------------------------------------------------------
# Property 11: TDC non-adjacency  (Task 6.6)
# ---------------------------------------------------------------------------


@st.composite
def _mixed_tdc_coils(draw):
    """Generate a list with some TDC coils and some non-TDC coils (all eligible)."""
    n_total = draw(st.integers(min_value=2, max_value=20))
    # At least 1 TDC, at least 1 non-TDC
    n_tdc = draw(st.integers(min_value=1, max_value=max(1, n_total - 1)))
    n_non_tdc = n_total - n_tdc

    coils = []

    # TDC coils — keep them in a narrow band so swapping is possible
    tdc_thk = draw(_thk_thick)  # put TDCs in thick range
    tdc_wdt = draw(_wdt)
    for _ in range(n_tdc):
        coils.append(_make_coil(
            thk=draw(st.floats(min_value=max(2.0, tdc_thk - 0.4),
                               max_value=min(6.0, tdc_thk + 0.4),
                               allow_nan=False, allow_infinity=False)),
            wdt=draw(st.floats(min_value=max(600.0, tdc_wdt - 100.0),
                               max_value=min(2000.0, tdc_wdt + 100.0),
                               allow_nan=False, allow_infinity=False)),
            age_hours=draw(_eligible_age),
            grade=draw(_tdc_grade),
            product=draw(_product),
        ))

    # Non-TDC coils — also in a compatible band with TDC coils
    for _ in range(n_non_tdc):
        coils.append(_make_coil(
            thk=draw(st.floats(min_value=max(2.0, tdc_thk - 0.4),
                               max_value=min(6.0, tdc_thk + 0.4),
                               allow_nan=False, allow_infinity=False)),
            wdt=draw(st.floats(min_value=max(600.0, tdc_wdt - 100.0),
                               max_value=min(2000.0, tdc_wdt + 100.0),
                               allow_nan=False, allow_infinity=False)),
            age_hours=draw(_eligible_age),
            grade=draw(_non_tdc),
            product=draw(_product),
        ))

    return coils


@given(coils=_mixed_tdc_coils())
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property11_tdc_non_adjacency(coils: list[CoilRow]) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 11: TDC non-adjacency

    For all consecutive pairs in result.sequence:
    - Verify NOT both coils have a TDC grade.
    - If any pair IS adjacent TDC, assert it is listed in
      result.unresolvable_tdc_pairs (flagged, not silently left).

    **Validates: Requirements 3.8, 3.9**
    """
    result = sequence_hrpo_hrspo(coils)
    seq = result.sequence
    flagged_positions = set(result.unresolvable_tdc_pairs)

    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        both_tdc = (a.grade or "").strip() in TDC_GRADES and \
                   (b.grade or "").strip() in TDC_GRADES
        if both_tdc:
            # The pair must have been flagged as unresolvable
            assert (i, i + 1) in flagged_positions, (
                f"Consecutive TDC pair at positions ({i}, {i+1}) was NOT flagged "
                f"in unresolvable_tdc_pairs. Grades: {a.grade!r}, {b.grade!r}. "
                "The sequencer should either separate or flag all TDC-TDC adjacencies."
            )
