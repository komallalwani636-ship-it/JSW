"""KPI calculator for the CPL-2 scheduling system.

Computes dashboard KPI metrics from an eligible coil set and violation list.

# Feature: cpl2-scheduling-system
# Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.parser import CoilRow
from engine.violation_detector import ViolationRecord


@dataclass
class KpiResult:
    """Computed KPI metrics for a schedule.

    Attributes:
        total_eligible:  Total count of HRPO + HRSPO + NGO FP coils.
        hrpo_count:      Count of HRPO coils.
        hrpo_weight:     Total weight (tonnes) of HRPO coils.
        hrspo_count:     Count of HRSPO coils.
        hrspo_weight:    Total weight (tonnes) of HRSPO coils.
        ngo_count:       Count of NGO FP coils.
        ngo_weight:      Total weight (tonnes) of NGO FP coils.
        age_gt_72h:      Count of coils with age_hours > 72.
        age_gt_120h:     Count of coils with age_hours > 120.
        age_gt_168h:     Count of coils with age_hours > 168.
        violation_count: Number of detected violations.
        schedule_status: 'draft' or 'final'.
        version_label:   Human-readable version identifier.
    """
    total_eligible: int
    hrpo_count: int
    hrpo_weight: float
    hrspo_count: int
    hrspo_weight: float
    ngo_count: int
    ngo_weight: float
    age_gt_72h: int
    age_gt_120h: int
    age_gt_168h: int
    violation_count: int
    schedule_status: str
    version_label: str


def compute_kpis(
    eligible_coils: list[CoilRow],
    violations: list[ViolationRecord],
    schedule_status: str,
    version_label: str,
) -> KpiResult:
    """Compute KPI metrics from the eligible coil set and violation list.

    APL7 coils are already excluded before being passed in — this function
    does not re-filter for APL7.

    Args:
        eligible_coils:   Pre-filtered list of CoilRow objects (no APL7).
        violations:       List of ViolationRecord objects from detect_violations.
        schedule_status:  'draft' or 'final'.
        version_label:    Human-readable schedule version string.

    Returns:
        KpiResult with all computed metrics.
    """
    hrpo_count = 0
    hrpo_weight = 0.0
    hrspo_count = 0
    hrspo_weight = 0.0
    ngo_count = 0
    ngo_weight = 0.0

    age_gt_72h = 0
    age_gt_120h = 0
    age_gt_168h = 0

    for coil in eligible_coils:
        wgt = coil.wgt if coil.wgt is not None else 0.0

        if coil.product == "HRPO":
            hrpo_count += 1
            hrpo_weight += wgt
        elif coil.product == "HRSPO":
            hrspo_count += 1
            hrspo_weight += wgt
        elif coil.product == "NGO FP":
            ngo_count += 1
            ngo_weight += wgt

        # Age bands — only count when age_hours is not None
        if coil.age_hours is not None:
            if coil.age_hours > 72:
                age_gt_72h += 1
            if coil.age_hours > 120:
                age_gt_120h += 1
            if coil.age_hours > 168:
                age_gt_168h += 1

    total_eligible = hrpo_count + hrspo_count + ngo_count

    return KpiResult(
        total_eligible=total_eligible,
        hrpo_count=hrpo_count,
        hrpo_weight=hrpo_weight,
        hrspo_count=hrspo_count,
        hrspo_weight=hrspo_weight,
        ngo_count=ngo_count,
        ngo_weight=ngo_weight,
        age_gt_72h=age_gt_72h,
        age_gt_120h=age_gt_120h,
        age_gt_168h=age_gt_168h,
        violation_count=len(violations),
        schedule_status=schedule_status,
        version_label=version_label,
    )
