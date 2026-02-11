from __future__ import annotations

import argparse
import json

from .tau import (
    TAU_POLICY_PRESETS,
    build_labeled_tau_curve,
    calibrate_tau_from_labeled_reports,
    calibrate_tau_from_reports,
    collect_report_paths,
    resolve_labeled_policy,
)
from .tau_export import write_tau_curve_csv, write_tau_curve_png


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
        default=80.0,
        help="Desired IPN for the reference reports (0-100)",
    )
    parser.add_argument(
        "--accept-ipn",
        type=float,
        default=70.0,
        help="Acceptance threshold used for labeled calibration",
    )
    parser.add_argument(
        "--statistic",
        choices=["median", "mean", "p75"],
        default="median",
        help="Aggregation statistic over per-report tau estimates",
    )
    parser.add_argument("--prefer-px", action="store_true", help="Prefer px-based metrics over mm")
    parser.add_argument("--tau-min", type=float, default=0.005)
    parser.add_argument("--tau-max", type=float, default=0.2)
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
        default=400,
        help="Max points sampled on tau curve",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.reports:
        if args.curve_csv or args.curve_png:
            raise ValueError("--curve-csv/--curve-png are only available in labeled mode")
        paths = collect_report_paths(args.reports)
        result = calibrate_tau_from_reports(
            report_paths=paths,
            target_ipn=args.target_ipn,
            prefer_mm=not args.prefer_px,
            statistic_name=args.statistic,
            tau_min=args.tau_min,
            tau_max=args.tau_max,
        )
        payload = {
            "mode": "target_ipn",
            "tau": result.tau,
            "units": result.units,
            "reports_used": result.reports_used,
            "target_ipn": result.target_ipn,
            "statistic": result.statistic,
            "tau_min": result.tau_min,
            "tau_max": result.tau_max,
            "report_paths": [c.report_path for c in result.candidates],
            "tau_candidates": [c.tau for c in result.candidates],
        }
    else:
        if not args.bad_reports:
            raise ValueError("--bad-reports is required when --good-reports is used")
        good_paths = collect_report_paths(args.good_reports)
        bad_paths = collect_report_paths(args.bad_reports)
        policy_cfg = resolve_labeled_policy(
            policy=args.policy,
            objective=args.objective,
            max_mean_ipn_bad=args.max_mean_ipn_bad,
            min_mean_ipn_gap=args.min_mean_ipn_gap,
            min_tpr=args.min_tpr,
            min_tnr=args.min_tnr,
        )
        result = calibrate_tau_from_labeled_reports(
            good_report_paths=good_paths,
            bad_report_paths=bad_paths,
            accept_ipn=args.accept_ipn,
            prefer_mm=not args.prefer_px,
            tau_min=args.tau_min,
            tau_max=args.tau_max,
            objective=policy_cfg["objective"],
            max_mean_ipn_bad=policy_cfg["max_mean_ipn_bad"],
            min_mean_ipn_gap=policy_cfg["min_mean_ipn_gap"],
            min_tpr=policy_cfg["min_tpr"],
            min_tnr=policy_cfg["min_tnr"],
        )
        curve = build_labeled_tau_curve(
            good_report_paths=good_paths,
            bad_report_paths=bad_paths,
            accept_ipn=args.accept_ipn,
            prefer_mm=not args.prefer_px,
            tau_min=args.tau_min,
            tau_max=args.tau_max,
            max_points=args.curve_max_points,
        )
        curve_csv_path = None
        curve_png_path = None
        if args.curve_csv:
            curve_csv_path = write_tau_curve_csv(args.curve_csv, curve)
        if args.curve_png:
            curve_png_path = write_tau_curve_png(args.curve_png, curve, best_tau=result.tau)
        payload = {
            "mode": "labeled",
            "tau": result.tau,
            "units": result.units,
            "good_reports_used": result.good_reports_used,
            "bad_reports_used": result.bad_reports_used,
            "accept_ipn": result.accept_ipn,
            "policy": policy_cfg["policy"],
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
            "curve_csv": curve_csv_path,
            "curve_png": curve_png_path,
            "curve_points": len(curve.points),
        }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
