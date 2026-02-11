from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .tau import (
    TauCurve,
    TauCurvePoint,
    build_labeled_tau_curve,
    calibrate_tau_from_labeled_reports,
    calibrate_tau_from_reports,
    collect_report_paths,
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
        result = calibrate_tau_from_labeled_reports(
            good_report_paths=good_paths,
            bad_report_paths=bad_paths,
            accept_ipn=args.accept_ipn,
            prefer_mm=not args.prefer_px,
            tau_min=args.tau_min,
            tau_max=args.tau_max,
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
        if args.curve_csv:
            _write_curve_csv(args.curve_csv, curve)
        if args.curve_png:
            _write_curve_png(args.curve_png, curve, best_tau=result.tau)
        payload = {
            "mode": "labeled",
            "tau": result.tau,
            "units": result.units,
            "good_reports_used": result.good_reports_used,
            "bad_reports_used": result.bad_reports_used,
            "accept_ipn": result.accept_ipn,
            "objective": result.objective,
            "balanced_accuracy": result.balanced_accuracy,
            "tpr": result.tpr,
            "tnr": result.tnr,
            "tp": result.tp,
            "fn": result.fn,
            "tn": result.tn,
            "fp": result.fp,
            "tau_min": result.tau_min,
            "tau_max": result.tau_max,
            "good_paths": result.good_paths,
            "bad_paths": result.bad_paths,
            "curve_csv": str(Path(args.curve_csv).resolve()) if args.curve_csv else None,
            "curve_png": str(Path(args.curve_png).resolve()) if args.curve_png else None,
            "curve_points": len(curve.points),
        }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _write_curve_csv(path: str, curve: TauCurve) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "tau",
                "threshold_ratio",
                "balanced_accuracy",
                "tpr",
                "tnr",
                "tp",
                "fn",
                "tn",
                "fp",
            ]
        )
        for p in curve.points:
            writer.writerow(
                [
                    p.tau,
                    p.threshold_ratio,
                    p.balanced_accuracy,
                    p.tpr,
                    p.tnr,
                    p.tp,
                    p.fn,
                    p.tn,
                    p.fp,
                ]
            )


def _write_curve_png(path: str, curve: TauCurve, best_tau: float) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise RuntimeError("matplotlib is required to export --curve-png") from exc

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tau = [p.tau for p in curve.points]
    bal = [p.balanced_accuracy for p in curve.points]
    tpr = [p.tpr for p in curve.points]
    tnr = [p.tnr for p in curve.points]

    plt.figure(figsize=(9, 5))
    plt.plot(tau, bal, label="Balanced Accuracy", color="#1f77b4", linewidth=2)
    plt.plot(tau, tpr, label="TPR", color="#2ca02c", linestyle="--")
    plt.plot(tau, tnr, label="TNR", color="#d62728", linestyle="--")
    plt.axvline(best_tau, color="#111111", linestyle=":", label=f"Best tau={best_tau:.4f}")
    plt.ylim(0.0, 1.02)
    plt.xlabel("Tau")
    plt.ylabel("Score")
    plt.title(f"Tau Calibration Curve (accept_ipn={curve.accept_ipn:.1f}, units={curve.units})")
    plt.grid(alpha=0.2)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


if __name__ == "__main__":
    raise SystemExit(main())
