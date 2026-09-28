"""Property-based tests for engine/parser.py.

# Feature: cpl2-scheduling-system

Covers:
  Property 2:  Column extraction completeness        (Task 4.2) — Req 1.2, 13.1
  Property 3:  Missing column error lists exactly missing columns (Task 4.3) — Req 1.4
  Property 24: Parse warnings for non-numeric fields (Task 4.4) — Req 13.2
  Property 23: Coil record round-trip parsing        (Task 4.5) — Req 13.3, 13.4
"""

from __future__ import annotations

import ast
import os
import sys
import tempfile

import openpyxl
import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Ensure backend/ is on sys.path when running from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.parser import (
    NUMERIC_COLUMNS,
    REQUIRED_COLUMNS,
    parse_hrstock_report,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A "valid" data row that satisfies all required columns in order.
# Values are chosen so that no parse warnings are generated.
_VALID_ROW_VALUES = [
    "ORD001",     # HR Order No
    "COIL001",    # HR Coil No
    2.5,          # Thk
    1200.0,       # Wdt
    20.0,         # Wgt
    "GRADE1",     # Grade
    100.0,        # Age Hours
    "TA",         # Status
    "CUST1",      # Cust
    "CR001",      # CR Coil No
    "R1",         # Routing
    "HRPO",       # Product
    0,            # Act Path
    0,            # Prev Unit
    0.035,        # Silicon %
    "",           # Receiving Remarks
    "OPEN",       # Order_status
    "N",          # Tdc
    "MILL",       # Edge Condth
    1190.0,       # Ord Wdth Min
    1210.0,       # Ord Wdth Max
    1200.0,       # Taget Width
    "CPL2",       # Next Work Center
]

assert len(_VALID_ROW_VALUES) == len(REQUIRED_COLUMNS), (
    "Mismatch between _VALID_ROW_VALUES length and REQUIRED_COLUMNS"
)


def _build_xlsx(
    headers: list,
    data_rows: list[list],
    sheet_name: str = "Hrstock Report",
) -> str:
    """Write an xlsx to a NamedTemporaryFile and return its path."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(headers)
    for row in data_rows:
        ws.append(row)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
        path = tf.name
    wb.save(path)
    wb.close()
    return path


# ---------------------------------------------------------------------------
# Property 2: Column extraction completeness
# Task 4.2 — Validates: Requirements 1.2, 13.1
# ---------------------------------------------------------------------------

# Strategy: generate a list of extra (non-required) column names
_extra_col_names = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=65),
        min_size=1,
        max_size=12,
    ),
    min_size=0,
    max_size=3,
).filter(lambda extras: all(e not in REQUIRED_COLUMNS for e in extras))

# Number of data rows to write (1–3)
_num_data_rows = st.integers(min_value=1, max_value=3)


@given(extra_cols=_extra_col_names, num_rows=_num_data_rows)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property2_column_extraction_completeness(
    extra_cols: list[str], num_rows: int
) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 2: Column extraction completeness

    For any valid .xlsx file with a "Hrstock Report" sheet containing all 23
    required columns (plus any number of extras), every parsed CoilRow must
    have all required column names present as keys in its `all_columns` dict.
    No silent omissions.

    **Validates: Requirements 1.2, 13.1**
    """
    headers = REQUIRED_COLUMNS + extra_cols
    # Extend the base row with empty strings for extra columns
    base_row = _VALID_ROW_VALUES + [""] * len(extra_cols)
    data_rows = [list(base_row) for _ in range(num_rows)]

    path = _build_xlsx(headers, data_rows)
    try:
        result = parse_hrstock_report(path)
        assert result.total_rows == num_rows, (
            f"Expected {num_rows} rows, got {result.total_rows}"
        )
        for i, coil_row in enumerate(result.rows):
            for col in REQUIRED_COLUMNS:
                assert col in coil_row.all_columns, (
                    f"Row {i}: required column {col!r} missing from all_columns. "
                    f"extra_cols={extra_cols}"
                )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Property 3: Missing column error lists exactly missing columns
# Task 4.3 — Validates: Requirement 1.4
# ---------------------------------------------------------------------------

# Strategy: pick a non-empty proper subset of required columns to omit.
# "HR Coil No" must NOT be omitted: the parser uses its presence to detect
# the header row.  Omitting it causes a "sheet not found" error before the
# missing-column check is reached, which is a separate parser code path.
_OMITTABLE_COLS = [c for c in REQUIRED_COLUMNS if c != "HR Coil No"]

_omitted_cols = st.lists(
    st.sampled_from(_OMITTABLE_COLS),
    min_size=1,
    max_size=len(_OMITTABLE_COLS),  # can omit all omittable cols
    unique=True,
)


@given(omitted=_omitted_cols)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property3_missing_column_error_lists_exactly_missing(
    omitted: list[str],
) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 3: Missing column error lists exactly missing columns

    For any non-empty proper subset of the 23 required columns that is absent
    from the file, the ValueError raised must list each missing column name —
    no more, no fewer.

    **Validates: Requirement 1.4**
    """
    omitted_set = set(omitted)
    present_cols = [c for c in REQUIRED_COLUMNS if c not in omitted_set]
    # Build a file with only the present columns
    path = _build_xlsx(present_cols, data_rows=[])
    try:
        with pytest.raises(ValueError) as exc_info:
            parse_hrstock_report(path)
        msg = str(exc_info.value)
        # The error message must contain a Python-parseable sorted list
        assert "[" in msg and "]" in msg, (
            f"ValueError message does not contain a list: {msg!r}"
        )
        list_str = msg[msg.index("[") : msg.index("]") + 1]
        reported_missing = ast.literal_eval(list_str)
        assert sorted(reported_missing) == sorted(omitted), (
            f"Reported missing {sorted(reported_missing)} != expected {sorted(omitted)}"
        )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Property 24: Parse warnings for non-numeric fields
# Task 4.4 — Validates: Requirement 13.2
# ---------------------------------------------------------------------------

# Strategy: a non-numeric string (only alphabetic chars — cannot be parsed as float)
_non_numeric_text = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    min_size=1,
    max_size=8,
)

_numeric_col_name = st.sampled_from(sorted(NUMERIC_COLUMNS))


@given(col_name=_numeric_col_name, bad_value=_non_numeric_text)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property24_parse_warnings_for_non_numeric_fields(
    col_name: str, bad_value: str
) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 24: Parse warnings for non-numeric fields

    For any file where a numeric column contains a non-numeric string value in
    a specific row, the parse result must include a warning for that row and
    column name, and the corresponding field on the CoilRow must be None.

    **Validates: Requirement 13.2**
    """
    col_idx = REQUIRED_COLUMNS.index(col_name)
    row = list(_VALID_ROW_VALUES)
    row[col_idx] = bad_value  # inject non-numeric value

    path = _build_xlsx(REQUIRED_COLUMNS, data_rows=[row])
    try:
        result = parse_hrstock_report(path)
        assert result.total_rows == 1

        # Must have at least one warning for the injected column
        col_warnings = [w for w in result.warnings if w.column == col_name]
        assert len(col_warnings) >= 1, (
            f"Expected a warning for column {col_name!r} with value {bad_value!r}, "
            f"got warnings: {result.warnings}"
        )

        # The corresponding typed field on CoilRow must be None
        coil = result.rows[0]
        _FIELD_MAP = {
            "Thk": "thk",
            "Wdt": "wdt",
            "Wgt": "wgt",
            "Age Hours": "age_hours",
            "Silicon %": "silicon_pct",
            "Act Path": "act_path",
            "Prev Unit": "prev_unit",
        }
        field_name = _FIELD_MAP[col_name]
        field_value = getattr(coil, field_name)
        assert field_value is None, (
            f"CoilRow.{field_name} should be None for non-numeric input {bad_value!r}, "
            f"got {field_value!r}"
        )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Property 23: Coil record round-trip parsing
# Task 4.5 — Validates: Requirements 13.3, 13.4
# ---------------------------------------------------------------------------

# Strategies for each field of a CoilRow
_opt_float = st.one_of(st.none(), st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
_opt_pos_float = st.one_of(st.none(), st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False))
_short_text = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=65),
        min_size=0,
        max_size=8,
    ),
)
_opt_int = st.one_of(st.none(), st.integers(min_value=0, max_value=100))


@given(
    hr_order_no=_short_text,
    hr_coil_no=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=65),
        min_size=1,
        max_size=8,
    ),
    thk=_opt_pos_float,
    wdt=_opt_pos_float,
    wgt=_opt_pos_float,
    grade=_short_text,
    age_hours=_opt_pos_float,
    status=_short_text,
    cust=_short_text,
    cr_coil_no=_short_text,
    routing=_short_text,
    product=_short_text,
    act_path=_opt_int,
    prev_unit=_opt_int,
    silicon_pct=_opt_pos_float,
    receiving_remarks=_short_text,
    order_status=_short_text,
    tdc=_short_text,
    edge_condth=_short_text,
    ord_wdth_min=_opt_pos_float,
    ord_wdth_max=_opt_pos_float,
    target_width=_opt_pos_float,
    next_work_center=_short_text,
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=3, deadline=None)
def test_property23_coil_record_round_trip_parsing(
    hr_order_no,
    hr_coil_no,
    thk,
    wdt,
    wgt,
    grade,
    age_hours,
    status,
    cust,
    cr_coil_no,
    routing,
    product,
    act_path,
    prev_unit,
    silicon_pct,
    receiving_remarks,
    order_status,
    tdc,
    edge_condth,
    ord_wdth_min,
    ord_wdth_max,
    target_width,
    next_work_center,
) -> None:
    """
    # Feature: cpl2-scheduling-system, Property 23: Coil record round-trip parsing

    For any valid coil record produced by the parser, writing its field values
    back to an xlsx row and re-parsing produces an equivalent record within
    numeric precision (1e-6 tolerance for floats, exact equality for strings).

    **Validates: Requirements 13.3, 13.4**
    """
    TOLERANCE = 1e-6

    # Build a row in REQUIRED_COLUMNS order from the generated field values
    row = [
        hr_order_no if hr_order_no is not None else "",   # HR Order No
        hr_coil_no,                                        # HR Coil No
        thk if thk is not None else "",                   # Thk
        wdt if wdt is not None else "",                   # Wdt
        wgt if wgt is not None else "",                   # Wgt
        grade if grade is not None else "",               # Grade
        age_hours if age_hours is not None else "",       # Age Hours
        status if status is not None else "",             # Status
        cust if cust is not None else "",                 # Cust
        cr_coil_no if cr_coil_no is not None else "",     # CR Coil No
        routing if routing is not None else "",           # Routing
        product if product is not None else "",           # Product
        act_path if act_path is not None else "",         # Act Path
        prev_unit if prev_unit is not None else "",       # Prev Unit
        silicon_pct if silicon_pct is not None else "",   # Silicon %
        receiving_remarks if receiving_remarks is not None else "",  # Receiving Remarks
        order_status if order_status is not None else "",  # Order_status
        tdc if tdc is not None else "",                   # Tdc
        edge_condth if edge_condth is not None else "",   # Edge Condth
        ord_wdth_min if ord_wdth_min is not None else "",  # Ord Wdth Min
        ord_wdth_max if ord_wdth_max is not None else "",  # Ord Wdth Max
        target_width if target_width is not None else "",  # Taget Width
        next_work_center if next_work_center is not None else "",  # Next Work Center
    ]

    path = _build_xlsx(REQUIRED_COLUMNS, data_rows=[row])
    try:
        result = parse_hrstock_report(path)
        # Rows with all-empty non-hr_coil_no fields might still be skipped, but
        # hr_coil_no is always non-empty (min_size=1), so the row is never empty.
        assert result.total_rows == 1, (
            f"Expected 1 parsed row, got {result.total_rows}. "
            f"hr_coil_no={hr_coil_no!r}"
        )
        coil = result.rows[0]

        # --- String fields: exact equality (None → "" maps to None in parser) ---
        def norm_str(v):
            """Parser returns None for blank strings."""
            if v is None or (isinstance(v, str) and v.strip() == ""):
                return None
            return str(v).strip() or None

        assert coil.hr_coil_no == hr_coil_no, (
            f"hr_coil_no mismatch: {coil.hr_coil_no!r} != {hr_coil_no!r}"
        )
        assert coil.hr_order_no == norm_str(hr_order_no), (
            f"hr_order_no mismatch: {coil.hr_order_no!r} != {norm_str(hr_order_no)!r}"
        )
        assert coil.grade == norm_str(grade), (
            f"grade mismatch: {coil.grade!r} != {norm_str(grade)!r}"
        )
        assert coil.status == norm_str(status), (
            f"status mismatch: {coil.status!r} != {norm_str(status)!r}"
        )
        assert coil.product == norm_str(product), (
            f"product mismatch: {coil.product!r} != {norm_str(product)!r}"
        )

        # --- Numeric float fields: within tolerance ---
        def _approx_eq(a, b, tol=TOLERANCE):
            if a is None and b is None:
                return True
            if a is None or b is None:
                return False
            return abs(a - b) <= tol

        assert _approx_eq(coil.thk, thk), (
            f"thk mismatch: {coil.thk} vs {thk}"
        )
        assert _approx_eq(coil.wdt, wdt), (
            f"wdt mismatch: {coil.wdt} vs {wdt}"
        )
        assert _approx_eq(coil.wgt, wgt), (
            f"wgt mismatch: {coil.wgt} vs {wgt}"
        )
        assert _approx_eq(coil.age_hours, age_hours), (
            f"age_hours mismatch: {coil.age_hours} vs {age_hours}"
        )
        assert _approx_eq(coil.silicon_pct, silicon_pct), (
            f"silicon_pct mismatch: {coil.silicon_pct} vs {silicon_pct}"
        )
        assert _approx_eq(coil.ord_wdth_min, ord_wdth_min), (
            f"ord_wdth_min mismatch: {coil.ord_wdth_min} vs {ord_wdth_min}"
        )
        assert _approx_eq(coil.ord_wdth_max, ord_wdth_max), (
            f"ord_wdth_max mismatch: {coil.ord_wdth_max} vs {ord_wdth_max}"
        )
        assert _approx_eq(coil.target_width, target_width), (
            f"target_width mismatch: {coil.target_width} vs {target_width}"
        )

        # --- Integer fields: exact match or None ---
        def norm_int(v):
            return None if v is None else int(v)

        assert coil.act_path == norm_int(act_path), (
            f"act_path mismatch: {coil.act_path} != {norm_int(act_path)}"
        )
        assert coil.prev_unit == norm_int(prev_unit), (
            f"prev_unit mismatch: {coil.prev_unit} != {norm_int(prev_unit)}"
        )

    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
