from __future__ import annotations

import argparse

from .tau_service import (
    DEFAULT_ACCEPT_IPN,
    DEFAULT_CURVE_MAX_POINTS,
    DEFAULT_TARGET_IPN,
    DEFAULT_TAU_MAX,
    DEFAULT_TAU_MIN,
    DEFAULT_TAU_STATISTIC,
)
from .tau import TAU_POLICY_PRESETS


def build_pipeline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cut precision pipeline")
    parser.add_argument("--template", required=True, help="Path to template image")
    parser.add_argument("--test", required=True, help="Path to real cut image")
    parser.add_argument("--out", default="out", help="Output directory")
    parser.add_argument("--config", default=None, help="Config file (json/yaml)")
    parser.add_argument("--step-px", type=float, default=None, help="Resampling step in px")
    parser.add_argument("--num-points", type=int, default=None, help="Fixed number of contour points")
    parser.add_argument("--tau", type=float, default=None, help="IPN tolerance factor (relative)")
    parser.add_argument(
        "--tau-auto-reports",
        nargs="+",
        default=None,
        help="Glob patterns for report.json files used to auto-calibrate tau",
    )
    parser.add_argument(
        "--tau-auto-target-ipn",
        type=float,
        default=DEFAULT_TARGET_IPN,
        help="Target IPN used when auto-calibrating tau from reports",
    )
    parser.add_argument(
        "--tau-auto-statistic",
        choices=["median", "mean", "p75"],
        default=DEFAULT_TAU_STATISTIC,
        help="Statistic for auto-calibration over multiple reports",
    )
    parser.add_argument(
        "--tau-auto-good-reports",
        nargs="+",
        default=None,
        help="Glob patterns for 'good' labeled reports (class-based tau calibration)",
    )
    parser.add_argument(
        "--tau-auto-bad-reports",
        nargs="+",
        default=None,
        help="Glob patterns for 'bad' labeled reports (class-based tau calibration)",
    )
    parser.add_argument(
        "--tau-auto-accept-ipn",
        type=float,
        default=DEFAULT_ACCEPT_IPN,
        help="IPN acceptance threshold used for class-based tau calibration",
    )
    parser.add_argument(
        "--tau-auto-policy",
        choices=sorted(TAU_POLICY_PRESETS.keys()),
        default=None,
        help="Preset constraints/objective for labeled tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-objective",
        choices=["balanced_accuracy", "balanced_accuracy_then_gap", "gap_then_balanced_accuracy"],
        default=None,
        help="Objective used for labeled tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-max-mean-ipn-bad",
        type=float,
        default=None,
        help="Optional constraint for labeled tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-min-mean-ipn-gap",
        type=float,
        default=None,
        help="Optional constraint for labeled tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-min-tpr",
        type=float,
        default=None,
        help="Optional TPR constraint for labeled tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-min-tnr",
        type=float,
        default=None,
        help="Optional TNR constraint for labeled tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-prefer-px",
        action="store_true",
        help="Prefer px-based report metrics for tau auto-calibration",
    )
    parser.add_argument(
        "--tau-auto-min",
        type=float,
        default=DEFAULT_TAU_MIN,
        help="Lower bound when auto-calibrating tau",
    )
    parser.add_argument(
        "--tau-auto-max",
        type=float,
        default=DEFAULT_TAU_MAX,
        help="Upper bound when auto-calibrating tau",
    )
    parser.add_argument(
        "--tau-auto-curve-csv",
        default=None,
        help="Save labeled tau calibration curve CSV (only labeled auto mode)",
    )
    parser.add_argument(
        "--tau-auto-curve-png",
        default=None,
        help="Save labeled tau calibration curve PNG (only labeled auto mode)",
    )
    parser.add_argument(
        "--tau-auto-curve-max-points",
        type=int,
        default=DEFAULT_CURVE_MAX_POINTS,
        help="Max points for labeled tau calibration curve export",
    )
    parser.add_argument(
        "--manual-mm-per-px",
        type=float,
        default=None,
        help="Override automatic ruler calibration",
    )
    parser.add_argument("--no-kd-validate", action="store_true", help="Disable KDTree validation")
    parser.add_argument("--debug", action="store_true", help="Save intermediate artifacts")
    return parser
