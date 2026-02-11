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


@dataclass
class TauClassCalibrationResult:
    tau: float
    units: str
    good_reports_used: int
    bad_reports_used: int
    accept_ipn: float
    tau_min: float
    tau_max: float
    objective: str
    balanced_accuracy: float
    tpr: float
    tnr: float
    tp: int
    fn: int
    tn: int
    fp: int
    good_paths: list[str]
    bad_paths: list[str]


@dataclass
class TauCurvePoint:
    tau: float
    threshold_ratio: float
    balanced_accuracy: float
    tpr: float
    tnr: float
    mean_ipn_good: float
    mean_ipn_bad: float
    mean_ipn_gap: float
    tp: int
    fn: int
    tn: int
    fp: int


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


def calibrate_tau_from_labeled_reports(
    good_report_paths: Iterable[str],
    bad_report_paths: Iterable[str],
    accept_ipn: float = 70.0,
    prefer_mm: bool = True,
    tau_min: float = 0.005,
    tau_max: float = 0.2,
) -> TauClassCalibrationResult:
    if not (0.0 < accept_ipn < 100.0):
        raise ValueError("accept_ipn must be between 0 and 100")
    if tau_min <= 0.0:
        raise ValueError("tau_min must be > 0")
    if tau_max <= tau_min:
        raise ValueError("tau_max must be greater than tau_min")

    good_paths = [str(Path(p).resolve()) for p in good_report_paths]
    bad_paths = [str(Path(p).resolve()) for p in bad_report_paths]
    if not good_paths or not bad_paths:
        raise ValueError("Both good and bad report sets are required")

    units, good_values, bad_values = _prepare_labeled_ratio_values(
        good_paths, bad_paths, prefer_mm=prefer_mm
    )
    curve = build_labeled_tau_curve(
        good_report_paths=good_paths,
        bad_report_paths=bad_paths,
        accept_ipn=accept_ipn,
        prefer_mm=prefer_mm,
        tau_min=tau_min,
        tau_max=tau_max,
    )
    if not curve.points:
        raise ValueError("No tau candidates available for labeled calibration")

    best = None
    for point in curve.points:
        # Conservative tie-breaker: lower tau for same balanced accuracy.
        key = (point.balanced_accuracy, -point.tau)
        if best is None or key > best["key"]:
            best = {"point": point, "key": key}

    assert best is not None
    point = best["point"]
    return TauClassCalibrationResult(
        tau=float(point.tau),
        units=units,
        good_reports_used=len(good_values),
        bad_reports_used=len(bad_values),
        accept_ipn=float(accept_ipn),
        tau_min=float(tau_min),
        tau_max=float(tau_max),
        objective="balanced_accuracy",
        balanced_accuracy=float(point.balanced_accuracy),
        tpr=float(point.tpr),
        tnr=float(point.tnr),
        tp=int(point.tp),
        fn=int(point.fn),
        tn=int(point.tn),
        fp=int(point.fp),
        good_paths=[p for p, _ in good_values],
        bad_paths=[p for p, _ in bad_values],
    )


@dataclass
class TauCurve:
    units: str
    accept_ipn: float
    tau_min: float
    tau_max: float
    good_reports_used: int
    bad_reports_used: int
    points: list[TauCurvePoint]


def build_labeled_tau_curve(
    good_report_paths: Iterable[str],
    bad_report_paths: Iterable[str],
    accept_ipn: float = 70.0,
    prefer_mm: bool = True,
    tau_min: float = 0.005,
    tau_max: float = 0.2,
    max_points: int = 400,
) -> TauCurve:
    if not (0.0 < accept_ipn < 100.0):
        raise ValueError("accept_ipn must be between 0 and 100")
    if tau_min <= 0.0:
        raise ValueError("tau_min must be > 0")
    if tau_max <= tau_min:
        raise ValueError("tau_max must be greater than tau_min")
    if max_points <= 0:
        raise ValueError("max_points must be > 0")

    good_paths = [str(Path(p).resolve()) for p in good_report_paths]
    bad_paths = [str(Path(p).resolve()) for p in bad_report_paths]
    if not good_paths or not bad_paths:
        raise ValueError("Both good and bad report sets are required")

    units, good_values, bad_values = _prepare_labeled_ratio_values(
        good_paths, bad_paths, prefer_mm=prefer_mm
    )

    factor = 1.0 - accept_ipn / 100.0
    boundaries = [tau_min, tau_max]
    for _, ratio in good_values + bad_values:
        boundaries.append(ratio / factor)
    candidates = _midpoint_candidates(boundaries, tau_min=tau_min, tau_max=tau_max)
    candidates = sorted(set(candidates))
    if not candidates:
        candidates = [tau_min, tau_max]
    candidates = _downsample_sorted_values(candidates, max_points=max_points)

    points: list[TauCurvePoint] = []
    for tau in candidates:
        score = _evaluate_tau_classifier(good_values, bad_values, tau=tau, accept_ipn=accept_ipn)
        mean_ipn_good = _mean_ipn_from_ratios(good_values, tau)
        mean_ipn_bad = _mean_ipn_from_ratios(bad_values, tau)
        points.append(
            TauCurvePoint(
                tau=float(tau),
                threshold_ratio=float((1.0 - accept_ipn / 100.0) * tau),
                balanced_accuracy=float(score["balanced_accuracy"]),
                tpr=float(score["tpr"]),
                tnr=float(score["tnr"]),
                mean_ipn_good=float(mean_ipn_good),
                mean_ipn_bad=float(mean_ipn_bad),
                mean_ipn_gap=float(mean_ipn_good - mean_ipn_bad),
                tp=int(score["tp"]),
                fn=int(score["fn"]),
                tn=int(score["tn"]),
                fp=int(score["fp"]),
            )
        )

    return TauCurve(
        units=units,
        accept_ipn=float(accept_ipn),
        tau_min=float(tau_min),
        tau_max=float(tau_max),
        good_reports_used=len(good_values),
        bad_reports_used=len(bad_values),
        points=points,
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


def _extract_ratio_values(paths: list[str], units: str) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    mad_key = "mad_mm" if units == "mm" else "mad_px"
    scale_key = "scale_mm" if units == "mm" else "scale_px"
    for report_path in paths:
        metrics = _load_metrics(report_path)
        if metrics is None:
            continue
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
        out.append((report_path, mad_f / scale_f))
    return out


def _load_metrics(report_path: str) -> dict | None:
    try:
        payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except Exception:
        return None
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return None
    return metrics


def _choose_units(paths: list[str], prefer_mm: bool) -> str:
    has_mm = True
    has_px = True
    for report_path in paths:
        metrics = _load_metrics(report_path)
        if metrics is None:
            continue
        if metrics.get("mad_mm") is None or metrics.get("scale_mm") is None:
            has_mm = False
        if metrics.get("mad_px") is None or metrics.get("scale_px") is None:
            has_px = False
    if prefer_mm and has_mm:
        return "mm"
    if has_px:
        return "px"
    if has_mm:
        return "mm"
    raise ValueError("No usable metrics (px/mm) found in report set")


def _prepare_labeled_ratio_values(
    good_paths: list[str], bad_paths: list[str], prefer_mm: bool
) -> tuple[str, list[tuple[str, float]], list[tuple[str, float]]]:
    units = _choose_units(good_paths + bad_paths, prefer_mm=prefer_mm)
    good_values = _extract_ratio_values(good_paths, units)
    bad_values = _extract_ratio_values(bad_paths, units)
    if not good_values or not bad_values:
        raise ValueError("No valid reports available for labeled calibration")
    return units, good_values, bad_values


def _midpoint_candidates(boundaries: list[float], tau_min: float, tau_max: float) -> list[float]:
    vals = sorted({min(tau_max, max(tau_min, float(v))) for v in boundaries if np_isfinite(v)})
    if not vals:
        return []
    candidates: list[float] = [vals[0], vals[-1]]
    for left, right in zip(vals[:-1], vals[1:], strict=True):
        candidates.append(0.5 * (left + right))
        candidates.append(left)
        candidates.append(right)
    # Remove duplicates while preserving order.
    uniq: list[float] = []
    for v in candidates:
        if not any(abs(v - u) <= 1e-12 for u in uniq):
            uniq.append(v)
    return uniq


def _downsample_sorted_values(values: list[float], max_points: int) -> list[float]:
    if len(values) <= max_points:
        return values
    if max_points <= 1:
        return [values[0]]
    idxs = np_linspace_indices(len(values), max_points)
    return [values[i] for i in idxs]


def _evaluate_tau_classifier(
    good_values: list[tuple[str, float]],
    bad_values: list[tuple[str, float]],
    tau: float,
    accept_ipn: float,
) -> dict[str, float | int]:
    factor = 1.0 - accept_ipn / 100.0
    threshold = tau * factor
    tp = sum(1 for _, ratio in good_values if ratio <= threshold)
    fn = len(good_values) - tp
    tn = sum(1 for _, ratio in bad_values if ratio > threshold)
    fp = len(bad_values) - tn
    tpr = tp / len(good_values) if good_values else 0.0
    tnr = tn / len(bad_values) if bad_values else 0.0
    bal_acc = 0.5 * (tpr + tnr)
    return {
        "tp": tp,
        "fn": fn,
        "tn": tn,
        "fp": fp,
        "tpr": tpr,
        "tnr": tnr,
        "balanced_accuracy": bal_acc,
    }


def _mean_ipn_from_ratios(values: list[tuple[str, float]], tau: float) -> float:
    if not values:
        return 0.0
    acc = 0.0
    for _, ratio in values:
        acc += _ipn_from_ratio(ratio, tau)
    return acc / len(values)


def _ipn_from_ratio(ratio: float, tau: float) -> float:
    if tau <= 0.0:
        return 0.0
    raw = 100.0 * (1.0 - ratio / tau)
    if raw < 0.0:
        return 0.0
    if raw > 100.0:
        return 100.0
    return raw


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


def np_isfinite(value: float) -> bool:
    return not (value != value or value == float("inf") or value == float("-inf"))


def np_linspace_indices(n: int, k: int) -> list[int]:
    if k <= 1:
        return [0]
    if n <= 1:
        return [0]
    out: list[int] = []
    for i in range(k):
        idx = int(round(i * (n - 1) / (k - 1)))
        if not out or idx != out[-1]:
            out.append(idx)
    return out
