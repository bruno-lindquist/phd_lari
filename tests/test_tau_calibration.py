import json

import pytest

from cut_precision.tau import (
    calibrate_tau_from_labeled_reports,
    calibrate_tau_from_reports,
    collect_report_paths,
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
