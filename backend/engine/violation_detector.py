"""Violation detector for the CPL-2 scheduling system.

Detects rule violations in any consecutive coil sequence, covering
HRPO/HRSPO thickness, width, and TDC checks, plus NGO FP silicon
compatibility checks.

# Feature: cpl2-scheduling-system
# Validates: Requirements 7.1, 7.2, 7.3
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.parser import CoilRow
from engine.sequencer_hrpo import TDC_GRADES
from engine.sequencer_ngo import classify_silicon_band, is_compatible


@dataclass
class ViolationRecord:
    """A rule violation between two consecutive coils.

    Attributes:
        position_a: 0-indexed position of the first coil in the pair.
        position_b: position_a + 1.
        rule_type:  One of 'thickness', 'width', 'tdc', 'ngo_compatibility'.
        detail:     Measured vs allowed values for the violated rule.
    """
    position_a: int
    position_b: int
    rule_type: str   # 'thickness' | 'width' | 'tdc' | 'ngo_compatibility'
    detail: dict


def detect_violations(items: list[CoilRow]) -> list[ViolationRecord]:
    """Detect all rule violations in a consecutive coil sequence.

    Checks each consecutive pair (items[i], items[i+1]):

    HRPO/HRSPO pairs:
      - thickness: |Δthk| > 1.0 when both thk >= 2.0, or |Δthk| > 0.4 when both thk < 2.0
      - width:     |Δwdt| >= 300 when both thk >= 2.0, or |Δwdt| >= 150 when both thk < 2.0
      - tdc:       both grades are in TDC_GRADES

    NGO FP pairs:
      - ngo_compatibility: silicon bands are not compatible per NGO_COMPATIBILITY matrix

    Args:
        items: Ordered list of CoilRow objects (the full scheduled sequence).

    Returns:
        List of ViolationRecord objects for each detected violation.
    """
    violations: list[ViolationRecord] = []

    for i in range(len(items) - 1):
        a = items[i]
        b = items[i + 1]

        # ---- HRPO / HRSPO checks ----------------------------------------
        if a.product in {"HRPO", "HRSPO"} and b.product in {"HRPO", "HRSPO"}:

            # -- Thickness check --
            if a.thk is not None and b.thk is not None:
                if a.thk >= 2.0 and b.thk >= 2.0:
                    diff = abs(a.thk - b.thk)
                    if diff > 1.0:
                        violations.append(ViolationRecord(
                            position_a=i,
                            position_b=i + 1,
                            rule_type="thickness",
                            detail={
                                "measured_diff": diff,
                                "allowed_diff": 1.0,
                                "thk_a": a.thk,
                                "thk_b": b.thk,
                            },
                        ))
                elif a.thk < 2.0 and b.thk < 2.0:
                    diff = abs(a.thk - b.thk)
                    if diff > 0.4:
                        violations.append(ViolationRecord(
                            position_a=i,
                            position_b=i + 1,
                            rule_type="thickness",
                            detail={
                                "measured_diff": diff,
                                "allowed_diff": 0.4,
                                "thk_a": a.thk,
                                "thk_b": b.thk,
                            },
                        ))
                # Mixed range (one >= 2.0, one < 2.0): no check

            # -- Width check --
            if a.wdt is not None and b.wdt is not None:
                if a.thk is not None and b.thk is not None:
                    if a.thk >= 2.0 and b.thk >= 2.0:
                        diff = abs(a.wdt - b.wdt)
                        if diff >= 300:
                            violations.append(ViolationRecord(
                                position_a=i,
                                position_b=i + 1,
                                rule_type="width",
                                detail={
                                    "measured_diff": diff,
                                    "allowed_diff": 300,
                                    "wdt_a": a.wdt,
                                    "wdt_b": b.wdt,
                                },
                            ))
                    elif a.thk < 2.0 and b.thk < 2.0:
                        diff = abs(a.wdt - b.wdt)
                        if diff >= 150:
                            violations.append(ViolationRecord(
                                position_a=i,
                                position_b=i + 1,
                                rule_type="width",
                                detail={
                                    "measured_diff": diff,
                                    "allowed_diff": 150,
                                    "wdt_a": a.wdt,
                                    "wdt_b": b.wdt,
                                },
                            ))

            # -- TDC check --
            # TDC planning grades live in 'Tdc' in real XLS, but we also check 'grade'
            # for robustness against data format variations and tests.
            tdc_a = (a.tdc or "").strip() or (a.grade or "").strip()
            tdc_b = (b.tdc or "").strip() or (b.grade or "").strip()
            if tdc_a in TDC_GRADES and tdc_b in TDC_GRADES:
                violations.append(ViolationRecord(
                    position_a=i,
                    position_b=i + 1,
                    rule_type="tdc",
                    detail={
                        "coil_a": a.hr_coil_no,
                        "coil_b": b.hr_coil_no,
                        "grade_a": tdc_a,
                        "grade_b": tdc_b,
                        "tdc_a": tdc_a,
                        "tdc_b": tdc_b,
                    },
                ))

        # ---- NGO FP checks ----------------------------------------------
        elif a.product == "NGO FP" and b.product == "NGO FP":
            if a.silicon_pct is not None and b.silicon_pct is not None:
                band_a = classify_silicon_band(a.silicon_pct)
                band_b = classify_silicon_band(b.silicon_pct)
                if not is_compatible(band_a, band_b):
                    violations.append(ViolationRecord(
                        position_a=i,
                        position_b=i + 1,
                        rule_type="ngo_compatibility",
                        detail={
                            "band_a": band_a,
                            "band_b": band_b,
                            "silicon_pct_a": a.silicon_pct,
                            "silicon_pct_b": b.silicon_pct,
                        },
                    ))

    return violations
