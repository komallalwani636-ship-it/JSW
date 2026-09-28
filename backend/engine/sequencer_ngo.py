"""NGO FP sequencing engine for the CPL-2 scheduling system.

Implements silicon band classification, NGO compatibility matrix, and a
greedy Warnsdorff-heuristic Hamiltonian path algorithm that produces an
ordered NGO FP sequence from eligible coils.

# Feature: cpl2-scheduling-system
# Validates: Requirements 4.1, 4.2, 4.3, 4.4
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.parser import CoilRow

# ---------------------------------------------------------------------------
# Silicon band boundary table
# ---------------------------------------------------------------------------

SILICON_BANDS: list[tuple[str, float]] = [
    ("LSQ2L", 0.45),
    ("MSQ1",  0.90),
    ("MSQ2",  1.30),
    ("MSQ3",  1.55),
    ("HSQ1",  1.70),
    ("HSQ2",  2.00),
    ("HSQ3",  2.20),
    ("HSQ5",  2.60),
]


def classify_silicon_band(silicon_pct: float) -> str:
    """Return the silicon band name for a given silicon_pct value.

    Bands are defined by inclusive upper bounds in ascending order.
    Any value above 2.6% is treated as HSQ5 (highest band).

    Args:
        silicon_pct: Silicon percentage as a float (e.g. 0.44, 1.55, 2.7).

    Returns:
        Band name string, e.g. "LSQ2L", "MSQ1", … "HSQ5".
    """
    for band_name, upper_bound in SILICON_BANDS:
        if silicon_pct <= upper_bound:
            return band_name
    return "HSQ5"  # above 2.6% — treat as highest band


# ---------------------------------------------------------------------------
# Compatibility matrix
# ---------------------------------------------------------------------------

NGO_COMPATIBILITY: dict[str, set[str]] = {
    "LSQ2L": {"LSQ2L", "MSQ1", "MSQ2", "MSQ3", "HSQ1"},
    "MSQ1":  {"LSQ2L", "MSQ1", "MSQ2", "MSQ3", "HSQ1"},
    "MSQ2":  {"LSQ2L", "MSQ1", "MSQ2", "MSQ3", "HSQ1", "HSQ2"},
    "MSQ3":  {"LSQ2L", "MSQ1", "MSQ2", "MSQ3", "HSQ1", "HSQ2", "HSQ3"},
    "HSQ1":  {"LSQ2L", "MSQ1", "MSQ2", "MSQ3", "HSQ1", "HSQ2", "HSQ3", "HSQ5"},
    "HSQ2":  {"LSQ2L", "MSQ1", "MSQ2", "MSQ3", "HSQ1", "HSQ2"},
    "HSQ3":  {"MSQ3", "HSQ1"},
    "HSQ5":  {"HSQ1"},
}


def is_compatible(band_a: str, band_b: str) -> bool:
    """Return True if transitioning from band_a to band_b is allowed.

    Args:
        band_a: Silicon band of the preceding coil.
        band_b: Silicon band of the following coil.

    Returns:
        True when the NGO_COMPATIBILITY matrix permits a → b.
    """
    return band_b in NGO_COMPATIBILITY.get(band_a, set())


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class UnsequencedCoil:
    """A coil that could not be placed in the sequence.

    Attributes:
        coil:   The CoilRow that was excluded.
        reason: Either "missing_silicon_pct" or "no_compatible_neighbor".
    """
    coil: CoilRow
    reason: str  # "missing_silicon_pct" | "no_compatible_neighbor"


@dataclass
class NgoSequenceResult:
    """Result returned by sequence_ngo_fp.

    Attributes:
        sequence:     Ordered list of CoilRow objects forming a valid NGO path.
        unsequenced:  Coils excluded from the sequence with an explanation flag.
    """
    sequence: list[CoilRow]
    unsequenced: list[UnsequencedCoil] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _count_forward_options(coil_idx: int,
                            bands: list[str],
                            visited: list[bool],
                            adjacency: list[list[int]]) -> int:
    """Count how many unvisited neighbors coil_idx still has."""
    return sum(1 for j in adjacency[coil_idx] if not visited[j])


def _warnsdorff_path(coils: list[CoilRow],
                     bands: list[str],
                     adjacency: list[list[int]]) -> list[int]:
    """Find a Hamiltonian path using Warnsdorff's heuristic with one-level backtrack.

    Algorithm:
      1. Start from the node with the fewest forward options (most constrained).
         Ties broken by lowest silicon_pct (ascending order preference).
      2. At each step, extend to the unvisited compatible neighbour with the
         fewest remaining forward options (Warnsdorff's rule).
      3. On a dead-end, attempt a one-level backtrack: undo the last step, try
         the next-best option from the backtrack point.  If backtrack also
         fails, terminate the path.

    Returns:
        List of indices (into *coils*) in sequence order.
    """
    n = len(coils)
    if n == 0:
        return []

    visited = [False] * n

    # ---- Choose starting node: fewest forward options, tie-break by silicon_pct ----
    start = min(
        range(n),
        key=lambda i: (_count_forward_options(i, bands, visited, adjacency),
                       coils[i].silicon_pct or 0.0),
    )

    path: list[int] = [start]
    visited[start] = True
    max_iterations = n * n + n  # absolute upper bound to prevent infinite loops

    iteration = 0
    while iteration < max_iterations:
        current = path[-1]

        # Gather unvisited neighbours sorted by Warnsdorff score (fewest forward options)
        candidates = [
            j for j in adjacency[current] if not visited[j]
        ]

        if not candidates:
            # Dead-end — attempt one-level backtrack
            if len(path) >= 2:
                # Undo last step
                visited[current] = False
                path.pop()
                backtrack_node = path[-1]

                # Collect neighbours of the backtrack node excluding the dead-end node
                remaining_candidates = [
                    j for j in adjacency[backtrack_node]
                    if not visited[j] and j != current
                ]

                if remaining_candidates:
                    # Pick the best of the remaining candidates
                    next_node = min(
                        remaining_candidates,
                        key=lambda j: _count_forward_options(j, bands, visited, adjacency),
                    )
                    path.append(next_node)
                    visited[next_node] = True
                    iteration += 1
                    continue  # resume from next_node
                else:
                    # Backtrack also failed — restore and stop
                    path.append(current)
                    visited[current] = True
            break  # path is done (no candidates and no backtrack)

        # Normal step: pick neighbour with fewest onward moves
        next_node = min(
            candidates,
            key=lambda j: _count_forward_options(j, bands, visited, adjacency),
        )
        path.append(next_node)
        visited[next_node] = True
        iteration += 1

    return path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sequence_ngo_fp(coils: list[CoilRow]) -> NgoSequenceResult:
    """Sequence NGO FP coils using silicon band classification and Warnsdorff's heuristic.

    Steps:
      1. Classify silicon bands; exclude coils with missing silicon_pct.
      2. Build directed adjacency list from the NGO_COMPATIBILITY matrix.
      3. Sort eligible coils ascending by silicon_pct (most constrained first).
      4. Run Warnsdorff greedy path with one-level backtrack.
      5. Collect unvisited coils as unsequenced with "no_compatible_neighbor".

    Args:
        coils: List of CoilRow objects (typically pre-filtered NGO FP coils).

    Returns:
        NgoSequenceResult with .sequence (ordered CoilRow list) and
        .unsequenced (list of UnsequencedCoil with reason flags).
    """
    unsequenced: list[UnsequencedCoil] = []

    # ---- Step 1: Classify silicon bands; partition eligible vs. missing ----
    eligible: list[CoilRow] = []
    bands_for_eligible: list[str] = []

    for coil in coils:
        if coil.silicon_pct is None:
            unsequenced.append(UnsequencedCoil(coil=coil, reason="missing_silicon_pct"))
        else:
            eligible.append(coil)
            bands_for_eligible.append(classify_silicon_band(coil.silicon_pct))

    if not eligible:
        return NgoSequenceResult(sequence=[], unsequenced=unsequenced)

    # ---- Step 2: Sort eligible coils by silicon_pct ascending ----
    order = sorted(range(len(eligible)), key=lambda i: eligible[i].silicon_pct or 0.0)
    eligible = [eligible[i] for i in order]
    bands_for_eligible = [bands_for_eligible[i] for i in order]

    n = len(eligible)

    # ---- Step 3: Build directed adjacency list ----
    adjacency: list[list[int]] = [[] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j and is_compatible(bands_for_eligible[i], bands_for_eligible[j]):
                adjacency[i].append(j)

    # ---- Step 4: Run Warnsdorff path ----
    path_indices = _warnsdorff_path(eligible, bands_for_eligible, adjacency)

    # ---- Step 5: Collect unsequenced coils ----
    visited_set = set(path_indices)
    for i in range(n):
        if i not in visited_set:
            unsequenced.append(
                UnsequencedCoil(coil=eligible[i], reason="no_compatible_neighbor")
            )

    sequence = [eligible[i] for i in path_indices]

    return NgoSequenceResult(sequence=sequence, unsequenced=unsequenced)
