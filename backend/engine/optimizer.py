"""Automated schedule sequence optimizer for CPL-2 Scheduling System.

Resolves width jump, thickness jump, critical TDC adjacency, and NGO silicon
compatibility violations through targeted constraint-guided permutation search.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from engine.violation_detector import detect_violations

if TYPE_CHECKING:
    from engine.parser import CoilRow


def optimize_schedule_sequence(
    sequence: list[CoilRow],
    max_iter: int = 8000,
    seed: int | None = 42,
) -> list[CoilRow]:
    """Auto-resolve rule violations in a scheduled coil sequence.

    Preserves product campaign separation (HRPO/HRSPO campaign first, NGO FP
    campaign second). Performs targeted local search swapping coils involved in
    violations with compatible positions until violations are eliminated (0) or
    minimized.

    Args:
        sequence: The ordered list of eligible coils.
        max_iter: Maximum search iterations for HRPO/HRSPO sequence.
        seed: Optional RNG seed for deterministic behavior.

    Returns:
        The optimized sequence with violations minimized/eliminated.
    """
    if len(sequence) <= 1:
        return sequence

    rng = random.Random(seed)

    # Segregate by campaign product to maintain campaign integrity
    hrpo_coils = [c for c in sequence if c.product in ("HRPO", "HRSPO")]
    ngo_coils = [c for c in sequence if c.product == "NGO FP"]
    other_coils = [c for c in sequence if c.product not in ("HRPO", "HRSPO", "NGO FP")]

    # 1. Optimize HRPO / HRSPO sequence
    if len(hrpo_coils) > 1:
        curr_hrpo = list(hrpo_coils)
        hrpo_violations = detect_violations(curr_hrpo)
        best_count = len(hrpo_violations)

        for _ in range(max_iter):
            if best_count == 0:
                break

            # Targeted selection: pick a violation, then one of its offending coils
            v = rng.choice(hrpo_violations)
            p1 = v.position_a if rng.random() < 0.5 else v.position_b

            # Pick another candidate position
            p2 = rng.randint(0, len(curr_hrpo) - 1)
            if p1 == p2:
                continue

            # Swap
            curr_hrpo[p1], curr_hrpo[p2] = curr_hrpo[p2], curr_hrpo[p1]
            new_violations = detect_violations(curr_hrpo)
            new_count = len(new_violations)

            if new_count < best_count:
                best_count = new_count
                hrpo_violations = new_violations
            else:
                # Revert swap
                curr_hrpo[p1], curr_hrpo[p2] = curr_hrpo[p2], curr_hrpo[p1]

        hrpo_coils = curr_hrpo

    # 2. Optimize NGO FP sequence
    if len(ngo_coils) > 1:
        curr_ngo = list(ngo_coils)
        ngo_violations = detect_violations(curr_ngo)
        best_ngo_count = len(ngo_violations)

        for _ in range(1500):
            if best_ngo_count == 0:
                break

            v = rng.choice(ngo_violations)
            p1 = v.position_a if rng.random() < 0.5 else v.position_b
            p2 = rng.randint(0, len(curr_ngo) - 1)
            if p1 == p2:
                continue

            curr_ngo[p1], curr_ngo[p2] = curr_ngo[p2], curr_ngo[p1]
            new_violations = detect_violations(curr_ngo)
            new_count = len(new_violations)

            if new_count < best_ngo_count:
                best_ngo_count = new_count
                ngo_violations = new_violations
            else:
                curr_ngo[p1], curr_ngo[p2] = curr_ngo[p2], curr_ngo[p1]

        ngo_coils = curr_ngo

    return hrpo_coils + ngo_coils + other_coils
