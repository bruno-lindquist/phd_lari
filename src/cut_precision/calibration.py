from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .config import CalibrationConfig


@dataclass
class CalibrationResult:
    mm_per_px: float | None
    status: str
    method: str
    details: dict[str, float]


def estimate_mm_per_px_from_ruler(image_bgr: np.ndarray, cfg: CalibrationConfig) -> CalibrationResult:
    if cfg.manual_mm_per_px is not None:
        return CalibrationResult(
            mm_per_px=float(cfg.manual_mm_per_px),
            status="ok",
            method="manual",
            details={"ruler_mm": float(cfg.ruler_mm)},
        )

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, cfg.canny_low, cfg.canny_high)
    h, w = gray.shape[:2]
    min_len = int(max(h, w) * cfg.ruler_min_line_ratio)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180.0,
        threshold=cfg.hough_threshold,
        minLineLength=min_len,
        maxLineGap=cfg.hough_max_gap,
    )
    if lines is None:
        return CalibrationResult(
            mm_per_px=None,
            status="missing",
            method="ruler_detection",
            details={"reason": 1.0},
        )

    horiz: list[float] = []
    vert: list[float] = []
    for line in lines[:, 0, :]:
        x1, y1, x2, y2 = map(float, line.tolist())
        dx, dy = x2 - x1, y2 - y1
        length = float(np.hypot(dx, dy))
        if length < min_len:
            continue
        if abs(dy) <= max(2.0, 0.2 * abs(dx)):
            horiz.append(length)
        if abs(dx) <= max(2.0, 0.2 * abs(dy)):
            vert.append(length)

    candidates: list[float] = []
    if horiz:
        candidates.append(float(np.median(horiz)))
    if vert:
        candidates.append(float(np.median(vert)))

    if not candidates:
        return CalibrationResult(
            mm_per_px=None,
            status="missing",
            method="ruler_detection",
            details={"reason": 2.0},
        )

    px_120 = float(np.median(np.array(candidates)))
    if px_120 <= 0:
        return CalibrationResult(
            mm_per_px=None,
            status="missing",
            method="ruler_detection",
            details={"reason": 3.0},
        )

    mm_per_px = float(cfg.ruler_mm / px_120)
    return CalibrationResult(
        mm_per_px=mm_per_px,
        status="ok",
        method="ruler_detection",
        details={
            "px_120": px_120,
            "horiz_median": float(np.median(horiz)) if horiz else 0.0,
            "vert_median": float(np.median(vert)) if vert else 0.0,
        },
    )
