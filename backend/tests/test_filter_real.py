"""Unit test for filter pipeline using the real HR Stock XLS file.

Parses the real 'CPL2 HR STOCK FOR SCHEDULING.xls' file, runs the filter
pipeline, and asserts known expected values.

# Feature: cpl2-scheduling-system
# Validates: Requirements 2.7, 2.8
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.filter_pipeline import ELIGIBLE_PRODUCTS, ELIGIBLE_STATUSES, run_filter_pipeline
from engine.parser import parse_hrstock_report

# Path to the real XLS file (relative to this test file's directory)
XLS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "CPL2 HR STOCK FOR SCHEDULING.xls")
XLS_FILE = os.path.abspath(XLS_FILE)

TOTAL_ROWS = 270


@pytest.mark.skipif(
    not os.path.exists(XLS_FILE),
    reason="Real XLS file not available",
)
def test_filter_pipeline_real_xls():
    """
    Parse the real HR Stock XLS file and verify filter pipeline output.

    Validates: Requirements 2.7, 2.8
    """
    # Parse
    parse_result = parse_hrstock_report(XLS_FILE)
    assert parse_result.total_rows == TOTAL_ROWS, (
        f"Expected {TOTAL_ROWS} total rows, got {parse_result.total_rows}"
    )

    # Run filter pipeline
    result = run_filter_pipeline(parse_result.rows)

    # ---- APL7 coils -------------------------------------------------------
    assert result.apl7_count >= 1, (
        f"Expected at least 1 APL7 coil, got {result.apl7_count}"
    )
    assert len(result.apl7_coils) == result.apl7_count

    # ---- Eligible coils exist ---------------------------------------------
    assert len(result.eligible_coils) > 0, (
        "Expected at least one eligible coil after filtering"
    )

    # ---- All rows accounted for -------------------------------------------
    total_accounted = (
        len(result.eligible_coils)
        + result.excluded_product
        + result.excluded_act_path
        + result.excluded_status
        + result.excluded_closed
        + result.apl7_count
    )
    assert total_accounted == TOTAL_ROWS, (
        f"Row count mismatch: {total_accounted} accounted for, "
        f"expected {TOTAL_ROWS}. "
        f"eligible={len(result.eligible_coils)}, "
        f"excluded_product={result.excluded_product}, "
        f"excluded_act_path={result.excluded_act_path}, "
        f"excluded_status={result.excluded_status}, "
        f"excluded_closed={result.excluded_closed}, "
        f"apl7_count={result.apl7_count}"
    )

    # ---- Eligible coil constraints ----------------------------------------
    for i, coil in enumerate(result.eligible_coils):
        # Product constraint (Req 2.1)
        product = (coil.product or "").strip()
        assert product in ELIGIBLE_PRODUCTS, (
            f"Eligible coil[{i}] has invalid product: {coil.product!r}"
        )

        # Act Path + Prev Unit constraint (Req 2.2)
        assert coil.act_path == 0, (
            f"Eligible coil[{i}] has act_path={coil.act_path!r} (expected 0)"
        )
        assert coil.prev_unit == 0, (
            f"Eligible coil[{i}] has prev_unit={coil.prev_unit!r} (expected 0)"
        )

        # Status constraint (Req 2.3)
        status = (coil.status or "").strip()
        assert status in ELIGIBLE_STATUSES, (
            f"Eligible coil[{i}] has invalid status: {coil.status!r}"
        )

        # Order_status constraint (Req 2.4)
        order_status = (coil.order_status or "").strip().upper()
        assert order_status != "CLOSED", (
            f"Eligible coil[{i}] has order_status=CLOSED"
        )

        # Receiving remarks constraint (Req 2.5, 2.6)
        remarks = (coil.receiving_remarks or "").strip().upper()
        assert remarks != "APL7", (
            f"Eligible coil[{i}] has receiving_remarks=APL7"
        )
