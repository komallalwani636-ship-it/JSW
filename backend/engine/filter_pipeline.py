"""Filter pipeline for the CPL-2 scheduling system.

Applies the 6 SOP filtering steps in order to produce the eligible coil set
and the APL7 coil set, recording per-step exclusion counts.

# Feature: cpl2-scheduling-system
# Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.parser import CoilRow

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ELIGIBLE_PRODUCTS = {"HRPO", "HRSPO", "NGO FP"}
ELIGIBLE_STATUSES = {"TA", "TW"}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class FilterResult:
    eligible_coils: list[CoilRow]
    apl7_coils: list[CoilRow]
    excluded_product: int    # step 1 — product not in {HRPO, HRSPO, NGO FP}
    excluded_act_path: int   # step 2 — act_path != 0 OR prev_unit != 0
    excluded_status: int     # step 3 — status not in {TA, TW}
    excluded_closed: int     # step 4 — order_status == CLOSED
    apl7_count: int          # step 5 — receiving_remarks == APL7


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_filter_pipeline(rows: list[CoilRow]) -> FilterResult:
    """Apply all 6 SOP filter steps and return a FilterResult.

    Steps applied in order:
      1. Product filter       — keep Product ∈ {HRPO, HRSPO, NGO FP}
      2. Act Path + Prev Unit — keep Act_Path == 0 AND Prev_Unit == 0
      3. Status filter        — keep Status ∈ {TA, TW}
      4. Order_status filter  — exclude Order_status == CLOSED
      5. APL7 extraction      — rows where Receiving_Remarks == APL7
      6. Remaining rows       → eligible_coils
    """

    # ---- Step 1: Product filter ----------------------------------------
    after_step1: list[CoilRow] = []
    excluded_product = 0
    for row in rows:
        product = (row.product or "").strip()
        if product in ELIGIBLE_PRODUCTS:
            after_step1.append(row)
        else:
            excluded_product += 1

    # ---- Step 2: Act Path + Prev Unit filter ---------------------------
    after_step2: list[CoilRow] = []
    excluded_act_path = 0
    for row in after_step1:
        # None is treated as non-zero → excluded
        if row.act_path == 0 and row.prev_unit == 0:
            after_step2.append(row)
        else:
            excluded_act_path += 1

    # ---- Step 3: Status filter -----------------------------------------
    after_step3: list[CoilRow] = []
    excluded_status = 0
    for row in after_step2:
        status = (row.status or "").strip()
        if status in ELIGIBLE_STATUSES:
            after_step3.append(row)
        else:
            excluded_status += 1

    # ---- Step 4: Order_status (CLOSED) filter --------------------------
    after_step4: list[CoilRow] = []
    excluded_closed = 0
    for row in after_step3:
        order_status = (row.order_status or "").strip().upper()
        if order_status == "CLOSED":
            excluded_closed += 1
        else:
            after_step4.append(row)

    # ---- Step 5: APL7 extraction ---------------------------------------
    apl7_coils: list[CoilRow] = []
    eligible_coils: list[CoilRow] = []
    for row in after_step4:
        remarks = (row.receiving_remarks or "").strip().upper()
        if remarks == "APL7":
            apl7_coils.append(row)
        else:
            eligible_coils.append(row)

    apl7_count = len(apl7_coils)

    # ---- Step 6: Remaining rows = eligible_coils (already collected) ---

    return FilterResult(
        eligible_coils=eligible_coils,
        apl7_coils=apl7_coils,
        excluded_product=excluded_product,
        excluded_act_path=excluded_act_path,
        excluded_status=excluded_status,
        excluded_closed=excluded_closed,
        apl7_count=apl7_count,
    )
