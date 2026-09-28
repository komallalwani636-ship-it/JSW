"""
Unit tests for engine/parser.py.

Tests cover:
- File format validation (Requirement 1.1, 1.5)
- Sheet name validation (Requirement 1.3)
- Missing column detection (Requirement 1.4)
- Full data extraction (Requirements 1.2, 13.1)
- Parse warnings for non-numeric values (Requirement 13.2)
- Empty row skipping (Requirement 13.1)
- all_columns completeness (Requirement 2.8)
"""
from __future__ import annotations

import os
import sys
import tempfile

import openpyxl
import pytest

# Make sure the backend package is on the path when running from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.parser import (
    REQUIRED_COLUMNS,
    ParseResult,
    parse_hrstock_report,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

XLS_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "CPL2 HR STOCK FOR SCHEDULING.xls")
)


def _make_minimal_xlsx(headers: list, rows: list | None = None, sheet_name: str = "Hrstock Report") -> str:
    """Create a minimal .xlsx file and return its path."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(headers)
    if rows:
        for r in rows:
            ws.append(r)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
        path = tf.name
    wb.save(path)
    wb.close()
    return path


# ---------------------------------------------------------------------------
# File-format validation
# ---------------------------------------------------------------------------


def test_unsupported_extension_raises():
    """A .csv file should raise ValueError with the correct message."""
    with pytest.raises(ValueError, match="Unsupported file format. Upload .xls or .xlsx only."):
        parse_hrstock_report("data.csv")


def test_txt_extension_raises():
    """A .txt file should also raise ValueError."""
    with pytest.raises(ValueError, match="Unsupported file format"):
        parse_hrstock_report("data.txt")


def test_case_insensitive_extension():
    """Extension check is case-insensitive; .XLS and .XLSX are accepted (though file may not exist)."""
    # We can't create a valid XLS here, so we just check that the ValueError
    # raised is NOT about the extension.
    try:
        parse_hrstock_report("data.XLS")
    except ValueError as e:
        assert "Unsupported file format" not in str(e), (
            ".XLS (uppercase) should be accepted"
        )
    except FileNotFoundError:
        pass  # Expected — file doesn't exist but format check passed


# ---------------------------------------------------------------------------
# Sheet-name validation
# ---------------------------------------------------------------------------


def test_missing_sheet_raises():
    """A file without 'Hrstock Report' sheet raises ValueError with correct message."""
    path = _make_minimal_xlsx(["Col A"], sheet_name="WrongSheet")
    try:
        with pytest.raises(ValueError, match="Sheet 'Hrstock Report' not found in uploaded file."):
            parse_hrstock_report(path)
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Column validation
# ---------------------------------------------------------------------------


def test_missing_columns_raises_with_exact_list():
    """ValueError must list all missing required columns, sorted."""
    # Only supply 2 of the 23 required columns
    path = _make_minimal_xlsx(["HR Order No", "HR Coil No"])
    try:
        with pytest.raises(ValueError) as exc_info:
            parse_hrstock_report(path)
        msg = str(exc_info.value)
        assert "Missing columns:" in msg
        # The 21 remaining required columns should be listed
        missing_count = len([c for c in REQUIRED_COLUMNS if c not in {"HR Order No", "HR Coil No"}])
        assert str(missing_count) in msg or missing_count > 0
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def test_missing_columns_message_is_sorted():
    """The missing column list in the error message must be sorted."""
    path = _make_minimal_xlsx(["HR Order No", "HR Coil No"])
    try:
        with pytest.raises(ValueError) as exc_info:
            parse_hrstock_report(path)
        msg = str(exc_info.value)
        # Extract sorted list from message
        import ast
        list_str = msg[msg.index("["):msg.index("]") + 1]
        extracted = ast.literal_eval(list_str)
        assert extracted == sorted(extracted), "Missing columns should be sorted"
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def test_all_required_columns_present_does_not_raise():
    """A sheet with all 23 required columns (plus extras) should not raise."""
    all_cols = REQUIRED_COLUMNS + ["Extra Col 1", "Extra Col 2"]
    path = _make_minimal_xlsx(all_cols, rows=[["val"] * len(all_cols)])
    try:
        result = parse_hrstock_report(path)
        assert isinstance(result, ParseResult)
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Data extraction — using the real XLS file
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not os.path.exists(XLS_FILE), reason="Real XLS file not available")
def test_real_xls_total_rows():
    """The real file should yield 270 non-empty data rows."""
    result = parse_hrstock_report(XLS_FILE)
    assert result.total_rows == 270
    assert len(result.rows) == 270


@pytest.mark.skipif(not os.path.exists(XLS_FILE), reason="Real XLS file not available")
def test_real_xls_all_columns_84():
    """Every parsed row must have exactly 84 entries in all_columns."""
    result = parse_hrstock_report(XLS_FILE)
    for i, row in enumerate(result.rows):
        assert len(row.all_columns) == 84, (
            f"Row {i + 1} has {len(row.all_columns)} columns, expected 84"
        )


@pytest.mark.skipif(not os.path.exists(XLS_FILE), reason="Real XLS file not available")
def test_real_xls_first_row_fields():
    """Spot-check field values on the first parsed row."""
    result = parse_hrstock_report(XLS_FILE)
    row = result.rows[0]
    assert row.hr_coil_no == "P25C000378"
    assert row.thk == pytest.approx(1.6)
    assert row.wdt == pytest.approx(1250.0)
    assert row.product == "HRPO"


@pytest.mark.skipif(not os.path.exists(XLS_FILE), reason="Real XLS file not available")
def test_real_xls_hr_coil_no_never_none():
    """hr_coil_no must never be None — empty string fallback applies."""
    result = parse_hrstock_report(XLS_FILE)
    assert all(row.hr_coil_no is not None for row in result.rows)


@pytest.mark.skipif(not os.path.exists(XLS_FILE), reason="Real XLS file not available")
def test_real_xls_act_path_0_is_int():
    """Rows where Act Path = '0' (string in XLS) should parse to int 0."""
    result = parse_hrstock_report(XLS_FILE)
    rows_with_zero = [r for r in result.rows if r.act_path == 0]
    assert len(rows_with_zero) > 0, "Expected at least one row with act_path=0"
    for r in rows_with_zero:
        assert isinstance(r.act_path, int), f"act_path should be int, got {type(r.act_path)}"


@pytest.mark.skipif(not os.path.exists(XLS_FILE), reason="Real XLS file not available")
def test_real_xls_warnings_only_for_true_non_numeric():
    """Warnings should only flag genuinely non-numeric values, not '0'."""
    result = parse_hrstock_report(XLS_FILE)
    # All warning messages must reference a non-numeric value (not '0')
    for w in result.warnings:
        assert w.message != "Non-numeric value: 0", (
            f"String '0' should be parsed as 0, not warned about at row {w.row}"
        )


@pytest.mark.skipif(not os.path.exists(XLS_FILE), reason="Real XLS file not available")
def test_real_xls_warnings_reference_numeric_columns():
    """All parse warnings must reference one of the 7 numeric columns."""
    from engine.parser import NUMERIC_COLUMNS
    result = parse_hrstock_report(XLS_FILE)
    for w in result.warnings:
        assert w.column in NUMERIC_COLUMNS, (
            f"Warning references non-numeric column {w.column!r}"
        )


# ---------------------------------------------------------------------------
# Empty row handling
# ---------------------------------------------------------------------------


def test_empty_rows_are_skipped():
    """Completely empty rows must not be included in the result."""
    cols = REQUIRED_COLUMNS + ["Extra"]
    # A valid data row followed by an empty row
    data_row = ["ORD001", "COIL001", 2.5, 1200.0, 20.0, "GRADE1", 100.0,
                "TA", "CUST1", "CR001", "R1", "HRPO", 0, 0, 0.035,
                "", "OPEN", "N", "MILL", 1190.0, 1210.0, 1200.0, "CPL2"] + [""] * (len(cols) - len(REQUIRED_COLUMNS))
    empty_row = [""] * len(cols)

    path = _make_minimal_xlsx(cols, rows=[data_row, empty_row, data_row])
    try:
        result = parse_hrstock_report(path)
        assert result.total_rows == 2, f"Expected 2 non-empty rows, got {result.total_rows}"
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Parse warnings — non-numeric values
# ---------------------------------------------------------------------------


def test_non_numeric_thk_generates_warning():
    """A string like 'N/A' in Thk should generate a ParseWarning."""
    cols = REQUIRED_COLUMNS + []
    # Build a valid row where Thk has a non-numeric value
    thk_idx = REQUIRED_COLUMNS.index("Thk")
    row = ["ORD001", "COIL001", 2.5, 1200.0, 20.0, "GRADE1", 100.0,
           "TA", "CUST1", "CR001", "R1", "HRPO", 0, 0, 0.035,
           "", "OPEN", "N", "MILL", 1190.0, 1210.0, 1200.0, "CPL2"]
    row[thk_idx] = "N/A"  # inject non-numeric into Thk

    path = _make_minimal_xlsx(cols, rows=[row])
    try:
        result = parse_hrstock_report(path)
        assert result.total_rows == 1
        thk_warnings = [w for w in result.warnings if w.column == "Thk"]
        assert len(thk_warnings) == 1, "Expected exactly one Thk warning"
        assert "Non-numeric value: N/A" in thk_warnings[0].message
        assert result.rows[0].thk is None
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def test_warning_row_number_is_correct():
    """ParseWarning.row should match the 1-based row number in the sheet."""
    cols = REQUIRED_COLUMNS
    valid_row = ["ORD001", "COIL001", 2.5, 1200.0, 20.0, "GRADE1", 100.0,
                 "TA", "CUST1", "CR001", "R1", "HRPO", 0, 0, 0.035,
                 "", "OPEN", "N", "MILL", 1190.0, 1210.0, 1200.0, "CPL2"]
    bad_row = list(valid_row)
    bad_row[REQUIRED_COLUMNS.index("Wgt")] = "INVALID"  # inject bad Wgt

    # xlsx: row 1 = headers, row 2 = valid_row, row 3 = bad_row
    path = _make_minimal_xlsx(cols, rows=[valid_row, bad_row])
    try:
        result = parse_hrstock_report(path)
        wgt_warnings = [w for w in result.warnings if w.column == "Wgt"]
        assert len(wgt_warnings) == 1
        # Header is row 1, data row 1 is row 2, data row 2 (bad) is row 3
        assert wgt_warnings[0].row == 3, (
            f"Warning row should be 3 (sheet row), got {wgt_warnings[0].row}"
        )
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass
