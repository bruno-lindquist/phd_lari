from __future__ import annotations

import argparse
import json

from .tau import calibrate_tau_from_reports, collect_report_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calibrate IPN tau from report.json files")
    parser.add_argument(
        "--reports",
        nargs="+",
        required=True,
        help="One or more glob patterns pointing to report.json files",
    )
    parser.add_argument(
        "--target-ipn",
        type=float,
        default=80.0,
        help="Desired IPN for the reference reports (0-100)",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
