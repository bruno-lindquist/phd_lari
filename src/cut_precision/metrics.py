from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


@dataclass
class MetricsSummary:
    mad: float
    std: float
    p95: float
    max_error: float


def compute_statistics(distances: np.ndarray) -> MetricsSummary:
    if distances.size == 0:
        raise ValueError("Distance array is empty")
    arr = distances.astype(np.float64)
    return MetricsSummary(
        mad=float(np.mean(arr)),
        std=float(np.std(arr)),
        p95=float(np.percentile(arr, 95)),
        max_error=float(np.max(arr)),
    )


def bbox_diagonal(points: np.ndarray) -> float:
    if points.size == 0:
        return 0.0
    min_xy = points.min(axis=0)
    max_xy = points.max(axis=0)
    w, h = max_xy - min_xy
    return float(math.hypot(float(w), float(h)))


def compute_ipn(
    mad: float,
    scale: float,
    tau: float,
    clamp_low: float = 0.0,
    clamp_high: float = 100.0,
) -> tuple[float, float]:
    if scale <= 0.0:
        raise ValueError("Scale must be positive")
    if tau <= 0.0:
        raise ValueError("Tau must be positive")
    tolerance = tau * scale
    raw = 100.0 * (1.0 - mad / tolerance)
    clipped = min(clamp_high, max(clamp_low, raw))
    return clipped, tolerance


def to_mm(values_px: np.ndarray, mm_per_px: float | None) -> np.ndarray | None:
    if mm_per_px is None:
        return None
    return values_px.astype(np.float64) * float(mm_per_px)
