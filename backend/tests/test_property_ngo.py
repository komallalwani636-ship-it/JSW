"""Property-based tests for engine/sequencer_ngo.py.

# Feature: cpl2-scheduling-system
Properties 12–14 (Tasks 7.2–7.4)

Validates: Requirements 4.1, 4.2, 4.3, 4.4
"""

from __future__ import annotations

import os
import sys

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.parser import CoilRow
from engine.sequencer_ngo import (
    SILICON_BANDS,
    classify_silicon_band,
    is_compatible,
    sequence_ngo_fp,
)

# ---------------------------------------------------------------------------
# Shared helper — build a minimal CoilRow with a silicon_pct
# ---------------------------------------------------------------------------

def _make_ngo_coil(silicon_pct: float | None = 1.0, hr_coil_no: str = "C001") -> CoilRow:
    """Return a CoilRow configured as an NGO FP coil."""
    return CoilRow(
        hr_order_no=None,
        hr_coil_no=hr_coil_no,
        thk=None,
        wdt=None,
        wgt=None,
        grade=None,
        age_hours=None,
        status=None,
        cust=None,
        cr_coil_no=None,
        routing=None,
        product="NGO FP",
        act_path=None,
        prev_unit=None,
        silicon_pct=silicon_pct,
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

# All silicon % values in [0.0, 2.7] — defined as a function to avoid
# Hypothesis eager evaluation at module import time (which causes slow startup).
def _silicon_float():
    return st.floats(
        min_value=0.0,
        max_value=2.7,
        allow_nan=False,
        allow_infinity=False,
        allow_subnormal=False,
    )

# All band names
ALL_BANDS = [name for name, _ in SILICON_BANDS]


@st.composite
def _ngo_coil_with_silicon(draw, silicon_st=None):
    """Generate one CoilRow with a valid silicon_pct."""
    if silicon_st is None:
        silicon_st = _silicon_float()
    pct = draw(silicon_st)
    idx = draw(st.integers(min_value=0, max_value=999))
    return _make_ngo_coil(silicon_pct=pct, hr_coil_no=f"C{idx:04d}")


# ---------------------------------------------------------------------------
# Property 12: Silicon band classification correctness  (Task 7.2)
# ---------------------------------------------------------------------------


@given(silicon_pct=_silicon_float())
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property12_silicon_band_classification(silicon_pct: float) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 12: Silicon band classification correctness

    For any silicon_pct in [0.0, 2.7], classify_silicon_band must return the
    band whose upper bound is the smallest value >= silicon_pct.  That is, the
    first band in ascending boundary order whose upper bound is >= silicon_pct.
    Values above 2.6 always map to HSQ5.

    Boundary spot-checks: 0.45 → LSQ2L, 0.451 → MSQ1.

    **Validates: Requirement 4.1**
    """
    result = classify_silicon_band(silicon_pct)

    # ---- Compute expected band manually ----
    expected: str | None = None
    for band_name, upper_bound in SILICON_BANDS:
        if silicon_pct <= upper_bound:
            expected = band_name
            break
    if expected is None:
        expected = "HSQ5"  # above all explicit upper bounds

    assert result == expected, (
        f"classify_silicon_band({silicon_pct!r}) returned {result!r}; "
        f"expected {expected!r}."
    )


def test_property12_boundary_values() -> None:
    """Verify exact boundary values as specified.

    0.45  → LSQ2L  (at the upper bound of LSQ2L)
    0.451 → MSQ1   (just above the LSQ2L boundary)

    **Validates: Requirement 4.1**
    """
    assert classify_silicon_band(0.45) == "LSQ2L", (
        "0.45 should map to LSQ2L (inclusive upper bound)."
    )
    assert classify_silicon_band(0.451) == "MSQ1", (
        "0.451 is above LSQ2L upper bound (0.45), so should map to MSQ1."
    )
    # Also verify the very top: anything above 2.6 → HSQ5
    assert classify_silicon_band(2.61) == "HSQ5", (
        "2.61 is above all explicit bounds; should map to HSQ5."
    )
    assert classify_silicon_band(2.60) == "HSQ5", (
        "2.60 is the HSQ5 upper bound; should map to HSQ5."
    )


# ---------------------------------------------------------------------------
# Property 13: NGO FP compatibility in sequence  (Task 7.3)
# ---------------------------------------------------------------------------


@given(
    coils=st.lists(
        _ngo_coil_with_silicon(),
        min_size=0,
        max_size=8,
    )
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property13_ngo_compatibility_in_sequence(coils: list[CoilRow]) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 13: NGO FP compatibility in sequence

    For any generated NGO coil set, after running sequence_ngo_fp every
    consecutive pair (a, b) in the result sequence must satisfy
    is_compatible(classify_silicon_band(a.silicon_pct),
                  classify_silicon_band(b.silicon_pct)).

    **Validates: Requirements 4.2, 4.3**
    """
    result = sequence_ngo_fp(coils)
    seq = result.sequence

    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]

        # Both coils in the sequence must have silicon_pct (missing ones are excluded)
        assert a.silicon_pct is not None, (
            f"Position {i}: coil in sequence has silicon_pct=None; "
            "coils with missing silicon_pct should not be sequenced."
        )
        assert b.silicon_pct is not None, (
            f"Position {i+1}: coil in sequence has silicon_pct=None; "
            "coils with missing silicon_pct should not be sequenced."
        )

        band_a = classify_silicon_band(a.silicon_pct)
        band_b = classify_silicon_band(b.silicon_pct)

        assert is_compatible(band_a, band_b), (
            f"Position ({i}, {i+1}): transition {band_a!r} → {band_b!r} is NOT "
            f"in the NGO compatibility matrix.  "
            f"silicon_pct values: {a.silicon_pct}, {b.silicon_pct}."
        )


# ---------------------------------------------------------------------------
# Property 14: NGO FP partial sequence validity  (Task 7.4)
# ---------------------------------------------------------------------------


@st.composite
def _disconnected_ngo_dataset(draw):
    """Generate a dataset with at least one HSQ5 coil and at least one LSQ2L coil.

    HSQ5 (silicon_pct just above 2.6) is only compatible *from* HSQ1 (band that
    can reach HSQ5), but HSQ5 itself can only transition *to* HSQ1.
    LSQ2L (silicon_pct <= 0.45) cannot transition to HSQ5.

    Mixing these two groups creates an intentionally disconnected graph:
    HSQ5 coils cannot be reached from LSQ2L coils, so the path must be
    partial when the only coils are from these two incompatible groups.
    """
    # HSQ5 coils: silicon_pct just above 2.6 (maps to HSQ5 via the "> 2.6" fallback)
    n_hsq5 = draw(st.integers(min_value=1, max_value=5))
    hsq5_coils = [
        _make_ngo_coil(
            silicon_pct=draw(st.floats(
                min_value=2.61, max_value=3.0,
                allow_nan=False, allow_infinity=False, allow_subnormal=False,
            )),
            hr_coil_no=f"HSQ5_{k:03d}",
        )
        for k in range(n_hsq5)
    ]

    # LSQ2L coils: silicon_pct <= 0.45
    n_lsq2l = draw(st.integers(min_value=1, max_value=5))
    lsq2l_coils = [
        _make_ngo_coil(
            silicon_pct=draw(st.floats(
                min_value=0.0, max_value=0.45,
                allow_nan=False, allow_infinity=False, allow_subnormal=False,
            )),
            hr_coil_no=f"LSQ2L_{k:03d}",
        )
        for k in range(n_lsq2l)
    ]

    return hsq5_coils + lsq2l_coils


@given(coils=_disconnected_ngo_dataset())
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property14_ngo_partial_sequence_validity(coils: list[CoilRow]) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 14: NGO FP partial sequence validity

    For NGO datasets where the compatibility graph is intentionally disconnected
    (HSQ5 coils mixed with LSQ2L coils — they cannot transition to each other):

    (a) All consecutive pairs in the partial sequence satisfy is_compatible.
    (b) Every coil NOT in the sequence appears in result.unsequenced.

    **Validates: Requirement 4.4**
    """
    result = sequence_ngo_fp(coils)
    seq = result.sequence

    # (a) All consecutive pairs in partial sequence are compatible
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        assert a.silicon_pct is not None
        assert b.silicon_pct is not None
        band_a = classify_silicon_band(a.silicon_pct)
        band_b = classify_silicon_band(b.silicon_pct)
        assert is_compatible(band_a, band_b), (
            f"Partial-sequence pair ({i}, {i+1}): "
            f"{band_a!r} → {band_b!r} is NOT compatible.  "
            f"silicon_pct values: {a.silicon_pct}, {b.silicon_pct}."
        )

    # (b) Every coil not in the sequence is in unsequenced
    sequenced_ids = {id(c) for c in seq}
    unsequenced_ids = {id(u.coil) for u in result.unsequenced}
    all_input_ids = {id(c) for c in coils}

    for coil in coils:
        if id(coil) not in sequenced_ids:
            assert id(coil) in unsequenced_ids, (
                f"Coil {coil.hr_coil_no!r} (silicon_pct={coil.silicon_pct}) is "
                "neither in the sequence nor in unsequenced."
            )

    # Sanity: sequence + unsequenced covers all input coils (no coil is lost)
    covered = sequenced_ids | unsequenced_ids
    assert covered == all_input_ids, (
        "Some input coils are missing from both sequence and unsequenced list."
    )
