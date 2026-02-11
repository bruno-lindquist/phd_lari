from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .tau import (
    TauCalibrationResult,
    TauClassCalibrationResult,
    build_labeled_tau_curve,
    calibrate_tau_from_labeled_reports,
    calibrate_tau_from_reports,
    collect_report_paths,
    resolve_labeled_policy,
)
from .tau_export import write_tau_curve_csv, write_tau_curve_png

DEFAULT_TARGET_IPN = 80.0
DEFAULT_ACCEPT_IPN = 70.0
DEFAULT_TAU_MIN = 0.005
DEFAULT_TAU_MAX = 0.5
DEFAULT_CURVE_MAX_POINTS = 400
DEFAULT_TAU_STATISTIC = "median"


@dataclass
class TauTargetCalibrationOutput:
    result: TauCalibrationResult
    report_patterns: list[str]

    @property
    def report_paths(self) -> list[str]:
        return [item.report_path for item in self.result.candidates]


@dataclass
class TauLabeledCalibrationOutput:
    result: TauClassCalibrationResult
    policy_cfg: dict[str, Any]
    good_report_patterns: list[str]
    bad_report_patterns: list[str]
    curve_csv: str | None
    curve_png: str | None
    curve_points: int


def calibrate_target_tau_from_patterns(
    *,
    report_patterns: Iterable[str],
    target_ipn: float = DEFAULT_TARGET_IPN,
    prefer_px: bool = False,
    statistic_name: str = DEFAULT_TAU_STATISTIC,
    tau_min: float = DEFAULT_TAU_MIN,
    tau_max: float = DEFAULT_TAU_MAX,
) -> TauTargetCalibrationOutput:
    patterns = list(report_patterns)
    report_paths = collect_report_paths(patterns)
    result = calibrate_tau_from_reports(
        report_paths=report_paths,
        target_ipn=target_ipn,
        prefer_mm=not prefer_px,
        statistic_name=statistic_name,
        tau_min=tau_min,
        tau_max=tau_max,
    )
    return TauTargetCalibrationOutput(result=result, report_patterns=patterns)


def calibrate_labeled_tau_from_patterns(
    *,
    good_report_patterns: Iterable[str],
    bad_report_patterns: Iterable[str],
    accept_ipn: float = DEFAULT_ACCEPT_IPN,
    prefer_px: bool = False,
    tau_min: float = DEFAULT_TAU_MIN,
    tau_max: float = DEFAULT_TAU_MAX,
    curve_max_points: int = DEFAULT_CURVE_MAX_POINTS,
    policy: str | None = None,
    objective: str | None = None,
    max_mean_ipn_bad: float | None = None,
    min_mean_ipn_gap: float | None = None,
    min_tpr: float | None = None,
    min_tnr: float | None = None,
    curve_csv_path: str | None = None,
    curve_png_path: str | None = None,
) -> TauLabeledCalibrationOutput:
    good_patterns = list(good_report_patterns)
    bad_patterns = list(bad_report_patterns)
    good_paths = collect_report_paths(good_patterns)
    bad_paths = collect_report_paths(bad_patterns)
    policy_cfg = resolve_labeled_policy(
        policy=policy,
        objective=objective,
        max_mean_ipn_bad=max_mean_ipn_bad,
        min_mean_ipn_gap=min_mean_ipn_gap,
        min_tpr=min_tpr,
        min_tnr=min_tnr,
    )
    result = calibrate_tau_from_labeled_reports(
        good_report_paths=good_paths,
        bad_report_paths=bad_paths,
        accept_ipn=accept_ipn,
        prefer_mm=not prefer_px,
        tau_min=tau_min,
        tau_max=tau_max,
        objective=policy_cfg["objective"],
        max_mean_ipn_bad=policy_cfg["max_mean_ipn_bad"],
        min_mean_ipn_gap=policy_cfg["min_mean_ipn_gap"],
        min_tpr=policy_cfg["min_tpr"],
        min_tnr=policy_cfg["min_tnr"],
    )
    curve = build_labeled_tau_curve(
        good_report_paths=good_paths,
        bad_report_paths=bad_paths,
        accept_ipn=accept_ipn,
        prefer_mm=not prefer_px,
        tau_min=tau_min,
        tau_max=tau_max,
        max_points=curve_max_points,
    )
    curve_csv = write_tau_curve_csv(curve_csv_path, curve) if curve_csv_path else None
    curve_png = write_tau_curve_png(curve_png_path, curve, best_tau=result.tau) if curve_png_path else None
    return TauLabeledCalibrationOutput(
        result=result,
        policy_cfg=policy_cfg,
        good_report_patterns=good_patterns,
        bad_report_patterns=bad_patterns,
        curve_csv=curve_csv,
        curve_png=curve_png,
        curve_points=len(curve.points),
    )


def build_target_tau_payload(calibration: TauTargetCalibrationOutput) -> dict[str, Any]:
    return {
        "mode": "target_ipn",
        "tau": calibration.result.tau,
        "units": calibration.result.units,
        "reports_used": calibration.result.reports_used,
        "target_ipn": calibration.result.target_ipn,
        "statistic": calibration.result.statistic,
        "tau_min": calibration.result.tau_min,
        "tau_max": calibration.result.tau_max,
        "report_paths": calibration.report_paths,
        "tau_candidates": [c.tau for c in calibration.result.candidates],
    }


def build_labeled_tau_payload(calibration: TauLabeledCalibrationOutput) -> dict[str, Any]:
    result = calibration.result
    return {
        "mode": "labeled",
        "tau": result.tau,
        "units": result.units,
        "good_reports_used": result.good_reports_used,
        "bad_reports_used": result.bad_reports_used,
        "accept_ipn": result.accept_ipn,
        "policy": calibration.policy_cfg["policy"],
        "objective": result.objective,
        "max_mean_ipn_bad": result.max_mean_ipn_bad,
        "min_mean_ipn_gap": result.min_mean_ipn_gap,
        "min_tpr": result.min_tpr,
        "min_tnr": result.min_tnr,
        "constraints_satisfied": result.constraints_satisfied,
        "feasible_points": result.feasible_points,
        "fallback_reason": result.fallback_reason,
        "balanced_accuracy": result.balanced_accuracy,
        "tpr": result.tpr,
        "tnr": result.tnr,
        "mean_ipn_good": result.mean_ipn_good,
        "mean_ipn_bad": result.mean_ipn_bad,
        "mean_ipn_gap": result.mean_ipn_gap,
        "tp": result.tp,
        "fn": result.fn,
        "tn": result.tn,
        "fp": result.fp,
        "tau_min": result.tau_min,
        "tau_max": result.tau_max,
        "good_paths": result.good_paths,
        "bad_paths": result.bad_paths,
        "curve_csv": calibration.curve_csv,
        "curve_png": calibration.curve_png,
        "curve_points": calibration.curve_points,
    }
