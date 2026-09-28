"""HRPO/HRSPO sequencing engine for the CPL-2 scheduling system.

Implements the 4-step banding + TDC-adjacency algorithm that produces an ordered
sequence from eligible HRPO and HRSPO coils.

# Feature: cpl2-scheduling-system
# Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.parser import CoilRow

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TDC_GRADES: set[str] = {
    "JVPST01C00",
    "JVPFB60AJS",
    "JVPTR14AJS",
    "JVPTR15AJS",
    "JVPTR13AJS",
}

# Thickness range boundaries
_THICK_BOUNDARY = 2.0

# Band windows — (max_thk_diff, max_wdt_diff)
_WINDOW_THICK = (1.0, 300.0)   # both thk >= 2.0:  Δthk <= 1.0, Δwdt < 300
_WINDOW_THIN  = (0.4, 150.0)   # both thk <  2.0:  Δthk <= 0.4, Δwdt < 150


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class HrpoSequenceResult:
    """Result returned by sequence_hrpo_hrspo.

    Attributes:
        sequence: Ordered list of CoilRow objects.
        unresolvable_tdc_pairs: 0-indexed (pos_a, pos_b) of consecutive TDC
            pairs that could not be separated by a swap.
    """
    sequence: list[CoilRow]
    unresolvable_tdc_pairs: list[tuple[int, int]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_tdc(coil: CoilRow) -> bool:
    """Return True if coil's Tdc column or Grade field is a TDC scheduling grade.

    NOTE: In the real HR Stock XLS, TDC scheduling grades live in the 'Tdc' column.
    We check both coil.tdc and coil.grade to be resilient across real XLS uploads
    and synthetic test scenarios.
    """
    return (coil.tdc or "").strip() in TDC_GRADES or (coil.grade or "").strip() in TDC_GRADES


def _in_thick_range(thk: float | None) -> str | None:
    """Return 'thick', 'thin', or None (unknown) for a coil thickness value."""
    if thk is None:
        return None
    return "thick" if thk >= _THICK_BOUNDARY else "thin"


def _fits_in_band(anchor: CoilRow, candidate: CoilRow) -> bool:
    """Check whether *candidate* belongs in the same band as *anchor*.

    Rules:
    - Both must be in the same thickness range (thick/thin).
    - Mixed-range pairs are never in the same band.
    - If either thk is None, the candidate starts a new band (None goes last).
    """
    a_thk = anchor.thk
    c_thk = candidate.thk

    # None thk → always a new band
    if a_thk is None or c_thk is None:
        return False

    a_range = _in_thick_range(a_thk)
    c_range = _in_thick_range(c_thk)

    # Mixed ranges never share a band
    if a_range != c_range:
        return False

    thk_diff = abs(a_thk - c_thk)
    wdt_diff = abs((anchor.wdt or 0.0) - (candidate.wdt or 0.0))

    if a_range == "thick":
        max_thk_diff, max_wdt_diff = _WINDOW_THICK
        return thk_diff <= max_thk_diff and wdt_diff < max_wdt_diff
    else:  # thin
        max_thk_diff, max_wdt_diff = _WINDOW_THIN
        return thk_diff <= max_thk_diff and wdt_diff < max_wdt_diff


def _form_bands(coils: list[CoilRow]) -> list[list[CoilRow]]:
    """Greedy band formation (Step 2).

    Sort all eligible coils by thk ascending (None thk goes last), then
    greedily assign each coil to the current band or start a new one.
    The anchor for each band is always its *first* coil.
    """
    # Sort: None thk → very large value so it goes last
    sorted_coils = sorted(coils, key=lambda c: (c.thk is None, c.thk or 0.0))

    if not sorted_coils:
        return []

    bands: list[list[CoilRow]] = []
    current_band: list[CoilRow] = [sorted_coils[0]]

    for coil in sorted_coils[1:]:
        if _fits_in_band(current_band[0], coil):
            current_band.append(coil)
        else:
            bands.append(current_band)
            current_band = [coil]

    bands.append(current_band)
    return bands


def _sort_band_by_age(band: list[CoilRow]) -> list[CoilRow]:
    """Sort a band by age_hours descending (None age goes last). (Step 3)."""
    return sorted(band, key=lambda c: (c.age_hours is None, -(c.age_hours or 0.0)))


def _is_compatible_neighbors(prev_coil: CoilRow | None, next_coil: CoilRow | None,
                              candidate: CoilRow) -> bool:
    """Return True if inserting *candidate* between *prev_coil* and *next_coil*
    doesn't introduce a TDC adjacency violation.

    We only check TDC adjacency here — thickness/width bands are not rechecked
    because swapping within the same sequence can't improve band placement anyway.
    The goal is only to break TDC-TDC adjacency.
    """
    # If candidate itself is TDC, swapping it in won't help break the adjacency
    if _is_tdc(candidate):
        return False

    # Check that the candidate is not a TDC (already done above)
    # prev_coil can be TDC — we are inserting between them, so the new
    # arrangement is: ..., prev_coil, candidate, (old candidate location)
    # The pair (prev_coil, candidate) must NOT both be TDC — but candidate
    # is non-TDC, so that's always fine.
    # The pair (candidate, next_coil) must NOT both be TDC — candidate is
    # non-TDC, so that's also always fine.
    return True


def _fix_tdc_adjacency(sequence: list[CoilRow]) -> tuple[list[CoilRow], list[tuple[int, int]]]:
    """Single-pass TDC adjacency fix (Step 4, TDC sub-step).

    For each consecutive TDC-TDC pair at (i, i+1):
    - Find the nearest non-TDC coil at j > i+1 that is compatible with both
      coil[i] (preceding) and coil[i+2] (following, if it exists).
    - Swap coil[i+1] with coil[j].
    - If no swap is possible, record (i, i+1) in unresolvable_tdc_pairs and
      leave in place.

    Returns (modified_sequence, unresolvable_tdc_pairs).
    """
    seq = list(sequence)  # work on a copy
    unresolvable: list[tuple[int, int]] = []
    i = 0

    while i < len(seq) - 1:
        if _is_tdc(seq[i]) and _is_tdc(seq[i + 1]):
            # Try to find a non-TDC coil to swap with seq[i+1]
            swapped = False
            for j in range(i + 2, len(seq)):
                candidate = seq[j]
                if _is_tdc(candidate):
                    continue  # skip other TDC coils

                # Determine neighbors that will adjoin the candidate's new position.
                # New position is i+1: neighbors are seq[i] and seq[i+2] (if exists).
                # The candidate is non-TDC, so seq[i] / seq[i+2] will not create a
                # new immediate TDC-TDC adjacency with it.

                # Also check what fills position j after the swap:
                # the displaced TDC from i+1 will move to j, and we must ensure it
                # does not create a new TDC adjacency with its new left/right neighbors.
                new_left_neighbor = seq[j - 1] if j - 1 >= 0 else None
                new_right_neighbor = seq[j + 1] if j + 1 < len(seq) else None

                # The displaced TDC at j must not be adjacent to another TDC.
                if (
                    new_left_neighbor is not None
                    and _is_tdc(new_left_neighbor)
                    and new_left_neighbor is not seq[i + 1]
                ):
                    continue
                if new_right_neighbor is not None and _is_tdc(new_right_neighbor):
                    continue

                # After swap: at position j-1 is seq[j-1], then displaced TDC,
                # then seq[j+1].  seq[j-1] is the old seq[j-1] which is either
                # the same as seq[i+1]'s new left (if j == i+2, that's seq[i+1]
                # itself moving) — need careful accounting.
                # Simpler: after the swap, at index j sits the displaced TDC.
                # Left neighbor = seq[j-1] (unchanged, since j > i+1 and swap
                # only touches positions i+1 and j).
                # But if j == i+2 then new_left_neighbor after swap would be
                # seq[i] (TDC) — bad.
                if j == i + 2:
                    # After swap: seq[i], candidate (at i+1), displaced_TDC (at i+2)
                    # Pair (seq[i], candidate): TDC + non-TDC → ok
                    # Pair (candidate, displaced_TDC): non-TDC + TDC → ok
                    # Pair (displaced_TDC, seq[i+3]): TDC + ?
                    next_after_displaced = seq[i + 3] if i + 3 < len(seq) else None
                    if next_after_displaced is not None and _is_tdc(next_after_displaced):
                        continue  # would create new TDC pair at (i+2, i+3)
                    swapped = True
                    seq[i + 1], seq[j] = seq[j], seq[i + 1]
                    break
                else:
                    # General case: j > i+2
                    # After swap:
                    #   position i+1: candidate (non-TDC)
                    #   position j:   displaced_TDC
                    # Check new neighbors of displaced_TDC at j:
                    #   left:  seq[j-1] (the coil that was at j-1, unchanged)
                    #   right: seq[j+1] (the coil that was at j+1, unchanged)
                    # Note: seq[j-1] hasn't been changed; it's what was there before.
                    left_of_j  = seq[j - 1]  # same object, unchanged in this loop iter
                    right_of_j = seq[j + 1] if j + 1 < len(seq) else None

                    # The displaced TDC would be adjacent to left_of_j and right_of_j.
                    # left_of_j is a non-candidate coil. If it's TDC, that creates a new
                    # TDC pair at (j-1, j).
                    if _is_tdc(left_of_j):
                        continue
                    if right_of_j is not None and _is_tdc(right_of_j):
                        continue

                    swapped = True
                    seq[i + 1], seq[j] = seq[j], seq[i + 1]
                    break

            if not swapped:
                unresolvable.append((i, i + 1))
            # Always advance i — single-pass scan regardless of swap outcome
        i += 1

    return seq, unresolvable


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sequence_hrpo_hrspo(coils: list[CoilRow]) -> HrpoSequenceResult:
    """Sequence HRPO/HRSPO coils using the 4-step banding algorithm.

    Steps:
      1. Age filter    — exclude coils with age_hours <= 72 (or None).
      2. Band formation — greedy banding by thk ascending.
      3. Within-band sort — each band sorted by age_hours descending.
      4. Concatenate bands + TDC adjacency fix.

    Returns an HrpoSequenceResult with the sequenced list and any
    unresolvable TDC pairs (0-indexed position tuples).

    Coils excluded by the age filter are dropped (not returned).
    """

    # ---- Step 1: Age filter -------------------------------------------
    eligible: list[CoilRow] = [
        c for c in coils
        if c.age_hours is not None and c.age_hours > 72
    ]

    # ---- Step 2: Band formation ---------------------------------------
    bands = _form_bands(eligible)

    # ---- Step 3: Within-band sort by age_hours descending -------------
    sorted_bands = [_sort_band_by_age(band) for band in bands]

    # ---- Step 4a: Concatenate bands -----------------------------------
    sequence: list[CoilRow] = []
    for band in sorted_bands:
        sequence.extend(band)

    # ---- Step 4b: TDC adjacency fix -----------------------------------
    sequence, unresolvable = _fix_tdc_adjacency(sequence)

    return HrpoSequenceResult(
        sequence=sequence,
        unresolvable_tdc_pairs=unresolvable,
    )
