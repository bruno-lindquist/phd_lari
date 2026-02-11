from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import glob
import json
import statistics


@dataclass
class TauCandidate:
    report_path: str
    tau: float
    units: str


@dataclass
class TauCalibrationResult:
    tau: float
    units: str
    reports_used: int
    target_ipn: float
    statistic: str
    tau_min: float
    tau_max: float
    candidates: list[TauCandidate]


def collect_report_paths(patterns: Iterable[str]) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        for path in glob.glob(pattern):
            p = str(Path(path).resolve())
            if p not in paths:
                paths.append(p)
    return sorted(paths)


def calibrate_tau_from_reports(
    report_paths: Iterable[str],
    target_ipn: float = 80.0,
    prefer_mm: bool = True,
    statistic_name: str = "median",
    tau_min: float = 0.005,
    tau_max: float = 0.2,
) -> TauCalibrationResult:
    if not (0.0 < target_ipn < 100.0):
        raise ValueError("target_ipn must be between 0 and 100")
    if tau_min <= 0.0:
        raise ValueError("tau_min must be > 0")
    if tau_max <= tau_min:
        raise ValueError("tau_max must be greater than tau_min")

    candidates: list[TauCandidate] = []
    for report_path in report_paths:
        candidate = _tau_from_single_report(report_path, target_ipn, prefer_mm)
        if candidate is not None:
            candidates.append(candidate)

    if not candidates:
        raise ValueError("No valid reports found for tau calibration")

    tau_values = [c.tau for c in candidates]
    raw_tau = _aggregate(tau_values, statistic_name)
    clipped_tau = min(tau_max, max(tau_min, raw_tau))
    units = candidates[0].units
    return TauCalibrationResult(
        tau=float(clipped_tau),
        units=units,
        reports_used=len(candidates),
        target_ipn=float(target_ipn),
        statistic=statistic_name,
        tau_min=float(tau_min),
        tau_max=float(tau_max),
        candidates=candidates,
    )


def _tau_from_single_report(
    report_path: str, target_ipn: float, prefer_mm: bool
) -> TauCandidate | None:
    try:
        payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except Exception:
        return None

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return None

    # Prefer mm when available to stabilize across capture scales.
    options: list[tuple[str, str]] = []
    if prefer_mm:
        options = [("mad_mm", "scale_mm"), ("mad_px", "scale_px")]
    else:
        options = [("mad_px", "scale_px"), ("mad_mm", "scale_mm")]

    for mad_key, scale_key in options:
        mad = metrics.get(mad_key)
        scale = metrics.get(scale_key)
        if mad is None or scale is None:
            continue
        try:
            mad_f = float(mad)
            scale_f = float(scale)
        except (TypeError, ValueError):
            continue
        if mad_f < 0.0 or scale_f <= 0.0:
            continue

        # target_ipn = 100 * (1 - mad / (tau * scale))
        # tau = mad / ((1 - target_ipn/100) * scale)
        denom = (1.0 - target_ipn / 100.0) * scale_f
        if denom <= 0.0:
            continue
        tau = mad_f / denom
        units = "mm" if mad_key.endswith("_mm") else "px"
        return TauCandidate(report_path=str(Path(report_path).resolve()), tau=float(tau), units=units)

    return None


def _aggregate(values: list[float], statistic_name: str) -> float:
    if not values:
        raise ValueError("No values to aggregate")
    stat = statistic_name.strip().lower()
    if stat == "mean":
        return float(statistics.mean(values))
    if stat == "p75":
        sorted_vals = sorted(values)
        idx = int(0.75 * (len(sorted_vals) - 1))
        return float(sorted_vals[idx])
    return float(statistics.median(values))
