import json

import pytest

from cut_precision.tau import (
    TAU_POLICY_PRESETS,
    build_labeled_tau_curve,
    calibrate_tau_from_labeled_reports,
    calibrate_tau_from_reports,
    collect_report_paths,
    resolve_labeled_policy,
)


def _write_report(path, mad_px, scale_px, mad_mm=None, scale_mm=None):
    payload = {
        "metrics": {
            "mad_px": mad_px,
            "scale_px": scale_px,
            "mad_mm": mad_mm,
            "scale_mm": scale_mm,
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_collect_report_paths(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text("{}", encoding="utf-8")
    b.write_text("{}", encoding="utf-8")
    paths = collect_report_paths([str(tmp_path / "*.json")])
    assert paths == sorted([str(a.resolve()), str(b.resolve())])


def test_calibrate_tau_from_reports_prefers_mm(tmp_path):
    # target_ipn=80 -> denom factor = 0.2
    # tau = mad_mm / (0.2 * scale_mm)
    r1 = tmp_path / "r1.json"
    r2 = tmp_path / "r2.json"
    _write_report(r1, mad_px=10.0, scale_px=100.0, mad_mm=4.0, scale_mm=40.0)  # tau=0.5
    _write_report(r2, mad_px=8.0, scale_px=100.0, mad_mm=2.0, scale_mm=40.0)  # tau=0.25
    out = calibrate_tau_from_reports(
        [str(r1), str(r2)],
        target_ipn=80.0,
        prefer_mm=True,
        statistic_name="median",
        tau_min=0.01,
        tau_max=1.0,
    )
    assert out.units == "mm"
    assert out.reports_used == 2
    assert out.tau == pytest.approx(0.375)


def test_calibrate_tau_from_reports_clamps(tmp_path):
    r1 = tmp_path / "r1.json"
    _write_report(r1, mad_px=100.0, scale_px=50.0)
    out = calibrate_tau_from_reports(
        [str(r1)],
        target_ipn=80.0,
        prefer_mm=False,
        statistic_name="median",
        tau_min=0.01,
        tau_max=0.2,
    )
    assert out.tau == 0.2


def test_calibrate_tau_from_labeled_reports_balanced_separation(tmp_path):
    good1 = tmp_path / "good1.json"
    good2 = tmp_path / "good2.json"
    bad1 = tmp_path / "bad1.json"
    bad2 = tmp_path / "bad2.json"
    _write_report(good1, mad_px=8.0, scale_px=100.0)
    _write_report(good2, mad_px=10.0, scale_px=100.0)
    _write_report(bad1, mad_px=40.0, scale_px=100.0)
    _write_report(bad2, mad_px=45.0, scale_px=100.0)

    out = calibrate_tau_from_labeled_reports(
        good_report_paths=[str(good1), str(good2)],
        bad_report_paths=[str(bad1), str(bad2)],
        accept_ipn=70.0,
        prefer_mm=False,
        tau_min=0.05,
        tau_max=0.5,
    )
    assert out.units == "px"
    assert out.good_reports_used == 2
    assert out.bad_reports_used == 2
    assert out.balanced_accuracy == pytest.approx(1.0)
    assert out.tp == 2
    assert out.tn == 2
    assert out.fp == 0
    assert out.fn == 0


def test_build_labeled_tau_curve_has_ipn_tracks(tmp_path):
    good1 = tmp_path / "good1.json"
    bad1 = tmp_path / "bad1.json"
    _write_report(good1, mad_px=10.0, scale_px=100.0)
    _write_report(bad1, mad_px=40.0, scale_px=100.0)

    curve = build_labeled_tau_curve(
        good_report_paths=[str(good1)],
        bad_report_paths=[str(bad1)],
        accept_ipn=70.0,
        prefer_mm=False,
        tau_min=0.05,
        tau_max=0.6,
        max_points=50,
    )
    assert curve.points
    taus = [p.tau for p in curve.points]
    assert taus == sorted(taus)
    # At the best operating point, good should score above bad.
    best = max(curve.points, key=lambda p: p.balanced_accuracy)
    assert best.mean_ipn_good > best.mean_ipn_bad
    # Somewhere on the curve, the class gap must appear.
    assert any(p.mean_ipn_good > p.mean_ipn_bad for p in curve.points)
    assert all(0.0 <= p.mean_ipn_good <= 100.0 for p in curve.points)
    assert all(0.0 <= p.mean_ipn_bad <= 100.0 for p in curve.points)


def test_labeled_calibration_with_constraints(tmp_path):
    good1 = tmp_path / "good1.json"
    good2 = tmp_path / "good2.json"
    bad1 = tmp_path / "bad1.json"
    bad2 = tmp_path / "bad2.json"
    _write_report(good1, mad_px=20.0, scale_px=100.0)
    _write_report(good2, mad_px=22.0, scale_px=100.0)
    _write_report(bad1, mad_px=24.0, scale_px=100.0)
    _write_report(bad2, mad_px=26.0, scale_px=100.0)

    out = calibrate_tau_from_labeled_reports(
        good_report_paths=[str(good1), str(good2)],
        bad_report_paths=[str(bad1), str(bad2)],
        accept_ipn=70.0,
        prefer_mm=False,
        tau_min=0.05,
        tau_max=1.0,
        objective="balanced_accuracy_then_gap",
        max_mean_ipn_bad=40.0,
    )
    assert out.constraints_satisfied is True
    assert out.feasible_points > 0
    assert out.mean_ipn_bad <= 40.0
    assert out.objective == "balanced_accuracy_then_gap"


def test_labeled_calibration_constraint_fallback(tmp_path):
    good = tmp_path / "good.json"
    bad = tmp_path / "bad.json"
    _write_report(good, mad_px=20.0, scale_px=100.0)
    _write_report(bad, mad_px=40.0, scale_px=100.0)

    out = calibrate_tau_from_labeled_reports(
        good_report_paths=[str(good)],
        bad_report_paths=[str(bad)],
        accept_ipn=70.0,
        prefer_mm=False,
        tau_min=0.05,
        tau_max=1.0,
        max_mean_ipn_bad=1.0,
        min_tpr=1.0,
    )
    assert out.constraints_satisfied is False
    assert out.feasible_points == 0
    assert out.fallback_reason == "no_feasible_points_for_constraints"


def test_resolve_labeled_policy_custom_defaults():
    out = resolve_labeled_policy(
        policy=None,
        objective=None,
        max_mean_ipn_bad=None,
        min_mean_ipn_gap=None,
        min_tpr=None,
        min_tnr=None,
    )
    assert out["policy"] == "custom"
    assert out["objective"] == "balanced_accuracy_then_gap"
    assert out["max_mean_ipn_bad"] is None
    assert out["min_mean_ipn_gap"] is None
    assert out["min_tpr"] is None
    assert out["min_tnr"] is None


def test_resolve_labeled_policy_preset_with_overrides():
    strict = TAU_POLICY_PRESETS["strict"]
    out = resolve_labeled_policy(
        policy="strict",
        objective=None,
        max_mean_ipn_bad=None,
        min_mean_ipn_gap=None,
        min_tpr=0.9,
        min_tnr=None,
    )
    assert out["policy"] == "strict"
    assert out["objective"] == strict.objective
    assert out["max_mean_ipn_bad"] == strict.max_mean_ipn_bad
    assert out["min_mean_ipn_gap"] == strict.min_mean_ipn_gap
    assert out["min_tpr"] == 0.9
    assert out["min_tnr"] == strict.min_tnr
