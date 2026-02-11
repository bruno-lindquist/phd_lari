from __future__ import annotations

import csv
from pathlib import Path

from .tau import TauCurve


def write_tau_curve_csv(path: str, curve: TauCurve) -> str:
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
                "mean_ipn_good",
                "mean_ipn_bad",
                "mean_ipn_gap",
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
                    p.mean_ipn_good,
                    p.mean_ipn_bad,
                    p.mean_ipn_gap,
                    p.tp,
                    p.fn,
                    p.tn,
                    p.fp,
                ]
            )
    return str(out.resolve())


def write_tau_curve_png(path: str, curve: TauCurve, best_tau: float) -> str:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required to export tau curve PNG") from exc

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tau = [p.tau for p in curve.points]
    bal = [p.balanced_accuracy for p in curve.points]
    tpr = [p.tpr for p in curve.points]
    tnr = [p.tnr for p in curve.points]
    ipn_good = [p.mean_ipn_good for p in curve.points]
    ipn_bad = [p.mean_ipn_bad for p in curve.points]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    axes[0].plot(tau, bal, label="Balanced Accuracy", color="#1f77b4", linewidth=2)
    axes[0].plot(tau, tpr, label="TPR", color="#2ca02c", linestyle="--")
    axes[0].plot(tau, tnr, label="TNR", color="#d62728", linestyle="--")
    axes[0].axvline(best_tau, color="#111111", linestyle=":", label=f"Best tau={best_tau:.4f}")
    axes[0].set_ylim(0.0, 1.02)
    axes[0].set_xlabel("Tau")
    axes[0].set_ylabel("Score")
    axes[0].set_title("Classification Metrics")
    axes[0].grid(alpha=0.2)
    axes[0].legend(loc="lower right")

    axes[1].plot(tau, ipn_good, label="Mean IPN (good)", color="#2ca02c", linewidth=2)
    axes[1].plot(tau, ipn_bad, label="Mean IPN (bad)", color="#d62728", linewidth=2)
    axes[1].axhline(curve.accept_ipn, color="#666666", linestyle="--", label="accept_ipn")
    axes[1].axvline(best_tau, color="#111111", linestyle=":")
    axes[1].set_ylim(0.0, 100.0)
    axes[1].set_xlabel("Tau")
    axes[1].set_ylabel("IPN")
    axes[1].set_title("Mean IPN by Class")
    axes[1].grid(alpha=0.2)
    axes[1].legend(loc="lower right")

    fig.suptitle(f"Tau Calibration Curve (accept_ipn={curve.accept_ipn:.1f}, units={curve.units})")
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return str(out.resolve())
