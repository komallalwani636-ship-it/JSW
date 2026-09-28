"""Uploads router for the CPL-2 Scheduling System.

Endpoints:
    POST /api/uploads              — upload and parse an HR Stock XLS file
    GET  /api/uploads/{upload_id}  — retrieve upload record

Design references: Requirements 1.1, 1.2, 1.6, 1.7, 12.1
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, get_db, require_planner
from api.schemas import ParseSummary, ParseWarning
from db.crud import (
    create_audit_event,
    create_coils_bulk,
    create_upload_file,
    get_upload_file,
)
from db.models import User
from engine.filter_pipeline import run_filter_pipeline
from engine.parser import parse_hrstock_report
from engine.sequencer_ngo import classify_silicon_band

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


# ---------------------------------------------------------------------------
# POST /api/uploads
# ---------------------------------------------------------------------------


@router.post("", status_code=200)
def upload_file(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_planner),
) -> dict:
    """Upload an HR Stock XLS/XLSX file, parse it, and store coils.

    Requirements: 1.1, 1.2, 1.6, 1.7, 12.1
    """
    # ---- Validate extension --------------------------------------------------
    original_filename = file.filename or ""
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in (".xls", ".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported file format. Upload .xls or .xlsx only.",
        )

    # ---- Save file to disk ---------------------------------------------------
    import tempfile
    upload_dir = os.environ.get("UPLOAD_PATH") or os.path.join(tempfile.gettempdir(), "cpl2_uploads")
    Path(upload_dir).mkdir(parents=True, exist_ok=True)
    saved_filename = f"{uuid4()}_{original_filename}"
    saved_path = os.path.join(upload_dir, saved_filename)

    file_bytes = file.file.read()
    with open(saved_path, "wb") as fh:
        fh.write(file_bytes)

    # ---- Parse ---------------------------------------------------------------
    try:
        parse_result = parse_hrstock_report(saved_path)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # ---- Filter pipeline (for summary stats) ---------------------------------
    filter_result = run_filter_pipeline(parse_result.rows)

    # ---- Build coil dicts ----------------------------------------------------
    coil_dicts: list[dict] = []
    for row in parse_result.rows:
        rr = (row.receiving_remarks or "").strip().upper()
        is_apl7 = rr == "APL7"

        # silicon_band: only for NGO FP coils with a known silicon_pct
        silicon_band = None
        if row.product == "NGO FP" and row.silicon_pct is not None:
            silicon_band = classify_silicon_band(row.silicon_pct)

        coil_dicts.append(
            {
                # upload_file_id will be filled in after the upload record is created
                "hr_order_no": row.hr_order_no,
                "hr_coil_no": row.hr_coil_no,
                "thk": row.thk,
                "wdt": row.wdt,
                "wgt": row.wgt,
                "grade": row.grade,
                "age_hours": row.age_hours,
                "status": row.status,
                "cust": row.cust,
                "cr_coil_no": row.cr_coil_no,
                "routing": row.routing,
                "product": row.product,
                "act_path": row.act_path,
                "prev_unit": row.prev_unit,
                "silicon_pct": row.silicon_pct,
                "receiving_remarks": row.receiving_remarks,
                "order_status": row.order_status,
                "tdc": row.tdc,
                "edge_condth": row.edge_condth,
                "ord_wdth_min": row.ord_wdth_min,
                "ord_wdth_max": row.ord_wdth_max,
                "target_width": row.target_width,
                "next_work_center": row.next_work_center,
                "all_columns": row.all_columns,
                "is_apl7": is_apl7,
                "silicon_band": silicon_band,
                "parse_warning": None,
            }
        )

    # ---- Persist (single transaction) ----------------------------------------
    parse_warnings_json = [
        {"row": w.row, "column": w.column, "message": w.message}
        for w in parse_result.warnings
    ]

    upload_record = create_upload_file(
        db=db,
        filename=original_filename,
        file_path=saved_path,
        uploaded_by=current_user.id,
        row_count=parse_result.total_rows,
        parse_warnings=parse_warnings_json,
    )

    # Inject upload_file_id into each coil dict
    for coil_dict in coil_dicts:
        coil_dict["upload_file_id"] = upload_record.id

    create_coils_bulk(db=db, coils=coil_dicts)

    create_audit_event(
        db=db,
        event_type="upload",
        user_id=current_user.id,
        upload_file_id=upload_record.id,
    )

    db.commit()

    # ---- Build response ------------------------------------------------------
    parse_summary = ParseSummary(
        total_rows=parse_result.total_rows,
        eligible_count=len(filter_result.eligible_coils),
        apl7_count=filter_result.apl7_count,
        excluded_product=filter_result.excluded_product,
        excluded_act_path=filter_result.excluded_act_path,
        excluded_status=filter_result.excluded_status,
        excluded_closed=filter_result.excluded_closed,
        parse_warnings=[
            ParseWarning(row=w.row, column=w.column, message=w.message)
            for w in parse_result.warnings
        ],
    )

    return {
        "upload_id": upload_record.id,
        "parse_summary": parse_summary.model_dump(),
    }


# ---------------------------------------------------------------------------
# GET /api/uploads/{upload_id}
# ---------------------------------------------------------------------------


@router.get("/{upload_id}", status_code=200)
def get_upload(
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the stored upload record by ID.

    Requirements: 1.6
    """
    record = get_upload_file(db, upload_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload {upload_id} not found.",
        )

    return {
        "id": record.id,
        "filename": record.filename,
        "uploaded_at": record.uploaded_at,
        "uploaded_by": record.uploaded_by,
        "row_count": record.row_count,
        "parse_warnings": record.parse_warnings,
    }
