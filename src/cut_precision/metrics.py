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


@dataclass
class ContourDiagnostics:
    mad_real_to_ideal: float
    mad_ideal_to_real: float
    bidirectional_mad: float
    hausdorff: float


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


def compute_bidirectional_diagnostics(
    dist_real_to_ideal: np.ndarray, dist_ideal_to_real: np.ndarray
) -> ContourDiagnostics:
    if dist_real_to_ideal.size == 0 or dist_ideal_to_real.size == 0:
        raise ValueError("Diagnostic arrays must be non-empty")

    r2i = dist_real_to_ideal.astype(np.float64)
    i2r = dist_ideal_to_real.astype(np.float64)
    mad_r2i = float(np.mean(r2i))
    mad_i2r = float(np.mean(i2r))
    return ContourDiagnostics(
        mad_real_to_ideal=mad_r2i,
        mad_ideal_to_real=mad_i2r,
        bidirectional_mad=float(0.5 * (mad_r2i + mad_i2r)),
        hausdorff=float(max(np.max(r2i), np.max(i2r))),
    )
