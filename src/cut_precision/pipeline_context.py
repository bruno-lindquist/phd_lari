from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TauCalibrationContext:
    mode: str = "fixed"
    source: str = "config_or_cli"
    policy: str = "custom"
    target_ipn: float | None = None
    accept_ipn: float | None = None
    reports_used: int = 0
    good_reports_used: int = 0
    bad_reports_used: int = 0
    report_patterns: list[str] = field(default_factory=list)
    good_report_patterns: list[str] = field(default_factory=list)
    bad_report_patterns: list[str] = field(default_factory=list)
    report_paths: list[str] = field(default_factory=list)
    good_report_paths: list[str] = field(default_factory=list)
    bad_report_paths: list[str] = field(default_factory=list)
    statistic: str | None = None
    units: str | None = None
    objective: str | None = None
    max_mean_ipn_bad: float | None = None
    min_mean_ipn_gap: float | None = None
    min_tpr: float | None = None
    min_tnr: float | None = None
    constraints_satisfied: bool | None = None
    feasible_points: int | None = None
    fallback_reason: str | None = None
    balanced_accuracy: float | None = None
    tpr: float | None = None
    tnr: float | None = None
    mean_ipn_good: float | None = None
    mean_ipn_bad: float | None = None
    mean_ipn_gap: float | None = None
    tp: int | None = None
    fn: int | None = None
    tn: int | None = None
    fp: int | None = None
    curve_csv: str | None = None
    curve_png: str | None = None
    curve_points: int | None = None

    @classmethod
    def fixed(cls) -> "TauCalibrationContext":
        return cls()

    @classmethod
    def from_auto_reports(
        cls,
        report_patterns: list[str],
        calibration: Any,
    ) -> "TauCalibrationContext":
        return cls(
            mode="auto_from_reports",
            source="reports",
            policy="custom",
            target_ipn=calibration.target_ipn,
            reports_used=calibration.reports_used,
            report_patterns=report_patterns,
            report_paths=[item.report_path for item in calibration.candidates],
            statistic=calibration.statistic,
            units=calibration.units,
        )

    @classmethod
    def from_auto_labeled_reports(
        cls,
        good_report_patterns: list[str],
        bad_report_patterns: list[str],
        policy_name: str,
        labeled: Any,
        curve_csv: str | None,
        curve_png: str | None,
        curve_points: int,
    ) -> "TauCalibrationContext":
        return cls(
            mode="auto_from_labeled_reports",
            source="reports_labeled",
            policy=policy_name,
            accept_ipn=labeled.accept_ipn,
            reports_used=labeled.good_reports_used + labeled.bad_reports_used,
            good_reports_used=labeled.good_reports_used,
            bad_reports_used=labeled.bad_reports_used,
            good_report_patterns=good_report_patterns,
            bad_report_patterns=bad_report_patterns,
            good_report_paths=labeled.good_paths,
            bad_report_paths=labeled.bad_paths,
            units=labeled.units,
            objective=labeled.objective,
            max_mean_ipn_bad=labeled.max_mean_ipn_bad,
            min_mean_ipn_gap=labeled.min_mean_ipn_gap,
            min_tpr=labeled.min_tpr,
            min_tnr=labeled.min_tnr,
            constraints_satisfied=labeled.constraints_satisfied,
            feasible_points=labeled.feasible_points,
            fallback_reason=labeled.fallback_reason,
            balanced_accuracy=labeled.balanced_accuracy,
            tpr=labeled.tpr,
            tnr=labeled.tnr,
            mean_ipn_good=labeled.mean_ipn_good,
            mean_ipn_bad=labeled.mean_ipn_bad,
            mean_ipn_gap=labeled.mean_ipn_gap,
            tp=labeled.tp,
            fn=labeled.fn,
            tn=labeled.tn,
            fp=labeled.fp,
            curve_csv=curve_csv,
            curve_png=curve_png,
            curve_points=curve_points,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "source": self.source,
            "policy": self.policy,
            "target_ipn": self.target_ipn,
            "accept_ipn": self.accept_ipn,
            "reports_used": self.reports_used,
            "good_reports_used": self.good_reports_used,
            "bad_reports_used": self.bad_reports_used,
            "report_patterns": self.report_patterns,
            "good_report_patterns": self.good_report_patterns,
            "bad_report_patterns": self.bad_report_patterns,
            "report_paths": self.report_paths,
            "good_report_paths": self.good_report_paths,
            "bad_report_paths": self.bad_report_paths,
            "statistic": self.statistic,
            "units": self.units,
            "objective": self.objective,
            "max_mean_ipn_bad": self.max_mean_ipn_bad,
            "min_mean_ipn_gap": self.min_mean_ipn_gap,
            "min_tpr": self.min_tpr,
            "min_tnr": self.min_tnr,
            "constraints_satisfied": self.constraints_satisfied,
            "feasible_points": self.feasible_points,
            "fallback_reason": self.fallback_reason,
            "balanced_accuracy": self.balanced_accuracy,
            "tpr": self.tpr,
            "tnr": self.tnr,
            "mean_ipn_good": self.mean_ipn_good,
            "mean_ipn_bad": self.mean_ipn_bad,
            "mean_ipn_gap": self.mean_ipn_gap,
            "tp": self.tp,
            "fn": self.fn,
            "tn": self.tn,
            "fp": self.fp,
            "curve_csv": self.curve_csv,
            "curve_png": self.curve_png,
            "curve_points": self.curve_points,
        }
