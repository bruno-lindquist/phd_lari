from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from .logging_config import build_run_id, log_stage, setup_logging
from .tau import TAU_POLICY_PRESETS
from .tau_service import (
    DEFAULT_ACCEPT_IPN,
    DEFAULT_CURVE_MAX_POINTS,
    DEFAULT_TARGET_IPN,
    DEFAULT_TAU_MAX,
    DEFAULT_TAU_MIN,
    DEFAULT_TAU_STATISTIC,
    build_labeled_tau_payload,
    build_target_tau_payload,
    calibrate_labeled_tau_from_patterns,
    calibrate_target_tau_from_patterns,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibrate IPN tau from report.json files")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--reports",
        nargs="+",
        help="One or more glob patterns pointing to report.json files",
    )
    mode.add_argument(
        "--good-reports",
        nargs="+",
        help="Glob patterns for 'good' reference reports",
    )
    parser.add_argument(
        "--bad-reports",
        nargs="+",
        default=None,
        help="Glob patterns for 'bad' reference reports (required with --good-reports)",
    )
    parser.add_argument(
        "--target-ipn",
        type=float,
        default=DEFAULT_TARGET_IPN,
        help="Desired IPN for the reference reports (0-100)",
    )
    parser.add_argument(
        "--accept-ipn",
        type=float,
        default=DEFAULT_ACCEPT_IPN,
        help="Acceptance threshold used for labeled calibration",
    )
    parser.add_argument(
        "--statistic",
        choices=["median", "mean", "p75"],
        default=DEFAULT_TAU_STATISTIC,
        help="Aggregation statistic over per-report tau estimates",
    )
    parser.add_argument("--prefer-px", action="store_true", help="Prefer px-based metrics over mm")
    parser.add_argument("--tau-min", type=float, default=DEFAULT_TAU_MIN)
    parser.add_argument("--tau-max", type=float, default=DEFAULT_TAU_MAX)
    parser.add_argument(
        "--policy",
        choices=sorted(TAU_POLICY_PRESETS.keys()),
        default=None,
        help="Preset constraints/objective for labeled mode",
    )
    parser.add_argument(
        "--objective",
        choices=["balanced_accuracy", "balanced_accuracy_then_gap", "gap_then_balanced_accuracy"],
        default=None,
        help="Objective used to select tau in labeled mode",
    )
    parser.add_argument(
        "--max-mean-ipn-bad",
        type=float,
        default=None,
        help="Optional constraint for labeled mode",
    )
    parser.add_argument(
        "--min-mean-ipn-gap",
        type=float,
        default=None,
        help="Optional constraint for labeled mode",
    )
    parser.add_argument("--min-tpr", type=float, default=None, help="Optional constraint for labeled mode")
    parser.add_argument("--min-tnr", type=float, default=None, help="Optional constraint for labeled mode")
    parser.add_argument(
        "--curve-csv",
        default=None,
        help="Path to save labeled calibration curve as CSV (only labeled mode)",
    )
    parser.add_argument(
        "--curve-png",
        default=None,
        help="Path to save labeled calibration curve plot (only labeled mode)",
    )
    parser.add_argument(
        "--curve-max-points",
        type=int,
        default=DEFAULT_CURVE_MAX_POINTS,
        help="Max points sampled on tau curve",
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="Directory for logs (defaults to system temp dir)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG level on console logs",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_dir = Path(args.log_dir) if args.log_dir else Path(tempfile.gettempdir()) / "cut_precision_logs"
    log = setup_logging(out_dir=log_dir, run_id=build_run_id(), debug=args.debug)
    with log_stage(log, "tau_calibration"):
        if args.reports:
            with log_stage(log, "tau.target_ipn"):
                if args.curve_csv or args.curve_png:
                    raise ValueError("--curve-csv/--curve-png are only available in labeled mode")
                calibration = calibrate_target_tau_from_patterns(
                    report_patterns=args.reports,
                    target_ipn=args.target_ipn,
                    prefer_px=args.prefer_px,
                    statistic_name=args.statistic,
                    tau_min=args.tau_min,
                    tau_max=args.tau_max,
                )
                payload = build_target_tau_payload(calibration)
        else:
            with log_stage(log, "tau.labeled"):
                if not args.bad_reports:
                    raise ValueError("--bad-reports is required when --good-reports is used")
                calibration = calibrate_labeled_tau_from_patterns(
                    good_report_patterns=args.good_reports,
                    bad_report_patterns=args.bad_reports,
                    accept_ipn=args.accept_ipn,
                    prefer_px=args.prefer_px,
                    tau_min=args.tau_min,
                    tau_max=args.tau_max,
                    curve_max_points=args.curve_max_points,
                    policy=args.policy,
                    objective=args.objective,
                    max_mean_ipn_bad=args.max_mean_ipn_bad,
                    min_mean_ipn_gap=args.min_mean_ipn_gap,
                    min_tpr=args.min_tpr,
                    min_tnr=args.min_tnr,
                    curve_csv_path=args.curve_csv,
                    curve_png_path=args.curve_png,
                )
                if calibration.curve_csv:
                    log.bind(
                        event="artifact.write",
                        stage="tau.labeled",
                        status="ok",
                        artifact="tau_curve_csv",
                        path=str(Path(calibration.curve_csv).resolve()),
                    ).info("artifact_written")
                if calibration.curve_png:
                    log.bind(
                        event="artifact.write",
                        stage="tau.labeled",
                        status="ok",
                        artifact="tau_curve_png",
                        path=str(Path(calibration.curve_png).resolve()),
                    ).info("artifact_written")
                payload = build_labeled_tau_payload(calibration)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
