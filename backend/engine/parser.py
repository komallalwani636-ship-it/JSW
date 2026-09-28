from __future__ import annotations
import os
from dataclasses import dataclass, field

REQUIRED_COLUMNS = [
    "HR Order No", "HR Coil No", "Thk", "Wdt", "Wgt", "Grade", "Age Hours",
    "Status", "Cust", "CR Coil No", "Routing", "Product", "Act Path",
    "Prev Unit", "Silicon %", "Receiving Remarks", "Order_status", "Tdc",
    "Edge Condth", "Ord Wdth Min", "Ord Wdth Max", "Taget Width",
    "Next Work Center",
]

NUMERIC_COLUMNS = {"Thk", "Wdt", "Wgt", "Age Hours", "Silicon %", "Act Path", "Prev Unit"}
INT_COLUMNS = {"Act Path", "Prev Unit"}


@dataclass
class ParseWarning:
    row: int
    column: str
    message: str


@dataclass
class CoilRow:
    hr_order_no: "str | None"
    hr_coil_no: str
    thk: "float | None"
    wdt: "float | None"
    wgt: "float | None"
    grade: "str | None"
    age_hours: "float | None"
    status: "str | None"
    cust: "str | None"
    cr_coil_no: "str | None"
    routing: "str | None"
    product: "str | None"
    act_path: "int | None"
    prev_unit: "int | None"
    silicon_pct: "float | None"
    receiving_remarks: "str | None"
    order_status: "str | None"
    tdc: "str | None"
    edge_condth: "str | None"
    ord_wdth_min: "float | None"
    ord_wdth_max: "float | None"
    target_width: "float | None"
    next_work_center: "str | None"
    all_columns: "dict[str, str]" = field(default_factory=dict)


@dataclass
class ParseResult:
    rows: "list[CoilRow]"
    warnings: "list[ParseWarning]"
    total_rows: int


def _stringify(val):
    return "" if val is None else str(val)


def _is_empty_row(values):
    return all(v is None or v == "" for v in values)


def _parse_numeric(val, col_name, row_num, warnings, as_int=False):
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return int(val) if as_int else float(val)
    # Also accept numeric strings (e.g. '0') without warning
    if isinstance(val, str):
        stripped = val.strip()
        if stripped == "":
            return None
        try:
            fval = float(stripped)
            return int(fval) if as_int else fval
        except ValueError:
            pass
    warnings.append(ParseWarning(row=row_num, column=col_name,
                                  message=f"Non-numeric value: {val}"))
    return None


def _parse_str(val):
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _try_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _read_xls(file_path):
    import xlrd
    wb = xlrd.open_workbook(file_path)
    if "Hrstock Report" not in wb.sheet_names():
        raise ValueError("Sheet 'Hrstock Report' not found in uploaded file.")
    ws = wb.sheet_by_name("Hrstock Report")
    header_row_idx = None
    for r in range(min(10, ws.nrows)):
        row_vals = [ws.cell_value(r, c) for c in range(ws.ncols)]
        if "HR Coil No" in row_vals:
            header_row_idx = r
            break
    if header_row_idx is None:
        raise ValueError("Sheet 'Hrstock Report' not found in uploaded file.")
    headers = [str(ws.cell_value(header_row_idx, c)) for c in range(ws.ncols)]
    data_rows = [[ws.cell_value(r, c) for c in range(ws.ncols)]
                 for r in range(header_row_idx + 1, ws.nrows)]
    return headers, data_rows, header_row_idx


def _read_xlsx(file_path):
    import openpyxl
    wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    if "Hrstock Report" not in wb.sheetnames:
        raise ValueError("Sheet 'Hrstock Report' not found in uploaded file.")
    ws = wb["Hrstock Report"]
    all_sheet_rows = [list(row) for row in ws.iter_rows(values_only=True)]
    wb.close()
    header_row_idx = None
    for r, row_vals in enumerate(all_sheet_rows[:10]):
        if "HR Coil No" in row_vals:
            header_row_idx = r
            break
    if header_row_idx is None:
        raise ValueError("Sheet 'Hrstock Report' not found in uploaded file.")
    headers = [str(v) if v is not None else "" for v in all_sheet_rows[header_row_idx]]
    data_rows = all_sheet_rows[header_row_idx + 1:]
    return headers, data_rows, header_row_idx


def parse_hrstock_report(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".xls":
        headers, data_rows, header_row_idx = _read_xls(file_path)
    elif ext == ".xlsx":
        headers, data_rows, header_row_idx = _read_xlsx(file_path)
    else:
        raise ValueError("Unsupported file format. Upload .xls or .xlsx only.")

    header_set = set(headers)
    missing = [c for c in REQUIRED_COLUMNS if c not in header_set]
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    col_idx = {h: i for i, h in enumerate(headers)}
    warnings = []
    coil_rows = []
    total_rows = 0

    for row_offset, row_vals in enumerate(data_rows):
        if len(row_vals) < len(headers):
            row_vals = row_vals + [None] * (len(headers) - len(row_vals))
        if _is_empty_row(row_vals):
            continue
        total_rows += 1
        sheet_row_num = header_row_idx + row_offset + 2

        def get_val(col_name, _rv=row_vals, _ci=col_idx):
            idx = _ci.get(col_name)
            if idx is None:
                return None
            return _rv[idx] if idx < len(_rv) else None

        all_columns = {h: _stringify(row_vals[i] if i < len(row_vals) else None)
                       for i, h in enumerate(headers)}

        thk = _parse_numeric(get_val("Thk"), "Thk", sheet_row_num, warnings)
        wdt = _parse_numeric(get_val("Wdt"), "Wdt", sheet_row_num, warnings)
        wgt = _parse_numeric(get_val("Wgt"), "Wgt", sheet_row_num, warnings)
        age_hours = _parse_numeric(get_val("Age Hours"), "Age Hours", sheet_row_num, warnings)
        silicon_pct = _parse_numeric(get_val("Silicon %"), "Silicon %", sheet_row_num, warnings)
        act_path = _parse_numeric(get_val("Act Path"), "Act Path", sheet_row_num, warnings, as_int=True)
        prev_unit = _parse_numeric(get_val("Prev Unit"), "Prev Unit", sheet_row_num, warnings, as_int=True)

        coil_rows.append(CoilRow(
            hr_order_no=_parse_str(get_val("HR Order No")),
            hr_coil_no=_parse_str(get_val("HR Coil No")) or "",
            thk=thk,
            wdt=wdt,
            wgt=wgt,
            grade=_parse_str(get_val("Grade")),
            age_hours=age_hours,
            status=_parse_str(get_val("Status")),
            cust=_parse_str(get_val("Cust")),
            cr_coil_no=_parse_str(get_val("CR Coil No")),
            routing=_parse_str(get_val("Routing")),
            product=_parse_str(get_val("Product")),
            act_path=act_path,
            prev_unit=prev_unit,
            silicon_pct=silicon_pct,
            receiving_remarks=_parse_str(get_val("Receiving Remarks")),
            order_status=_parse_str(get_val("Order_status")),
            tdc=_parse_str(get_val("Tdc")),
            edge_condth=_parse_str(get_val("Edge Condth")),
            ord_wdth_min=_try_float(get_val("Ord Wdth Min")),
            ord_wdth_max=_try_float(get_val("Ord Wdth Max")),
            target_width=_try_float(get_val("Taget Width")),
            next_work_center=_parse_str(get_val("Next Work Center")),
            all_columns=all_columns,
        ))

    return ParseResult(rows=coil_rows, warnings=warnings, total_rows=total_rows)
