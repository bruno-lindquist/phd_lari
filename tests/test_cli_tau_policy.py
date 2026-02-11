import json
from pathlib import Path

import pytest

pytest.importorskip("cv2")

from cut_precision.cli import main as pipeline_main
from cut_precision.tau_cli import main as tau_cli_main


def _write_report(path: Path, mad_px: float, scale_px: float) -> None:
    payload = {
        "metrics": {
            "mad_px": mad_px,
            "scale_px": scale_px,
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_tau_cli_policy_balanced_outputs_policy_fields(tmp_path, capsys):
    _write_report(tmp_path / "good1.json", mad_px=8.0, scale_px=100.0)
    _write_report(tmp_path / "good2.json", mad_px=10.0, scale_px=100.0)
    _write_report(tmp_path / "bad1.json", mad_px=35.0, scale_px=100.0)
    _write_report(tmp_path / "bad2.json", mad_px=40.0, scale_px=100.0)

    rc = tau_cli_main(
        [
            "--good-reports",
            str(tmp_path / "good*.json"),
            "--bad-reports",
            str(tmp_path / "bad*.json"),
            "--accept-ipn",
            "70",
            "--prefer-px",
            "--tau-min",
            "0.05",
            "--tau-max",
            "0.5",
            "--policy",
            "balanced",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "labeled"
    assert payload["policy"] == "balanced"
    assert payload["objective"] == "balanced_accuracy_then_gap"
    assert payload["max_mean_ipn_bad"] == 25.0
    assert payload["min_mean_ipn_gap"] == 10.0
    assert payload["constraints_satisfied"] is True


def test_pipeline_cli_labeled_policy_is_recorded_in_report(tmp_path):
    _write_report(tmp_path / "good1.json", mad_px=8.0, scale_px=100.0)
    _write_report(tmp_path / "good2.json", mad_px=10.0, scale_px=100.0)
    _write_report(tmp_path / "bad1.json", mad_px=35.0, scale_px=100.0)
    _write_report(tmp_path / "bad2.json", mad_px=40.0, scale_px=100.0)

    template_path = "original.jpeg" if Path("original.jpeg").exists() else "original.jpg"

    out_dir = tmp_path / "out"
    rc = pipeline_main(
        [
            "--template",
            template_path,
            "--test",
            "teste_1.jpg",
            "--out",
            str(out_dir),
            "--tau-auto-good-reports",
            str(tmp_path / "good*.json"),
            "--tau-auto-bad-reports",
            str(tmp_path / "bad*.json"),
            "--tau-auto-policy",
            "balanced",
            "--tau-auto-prefer-px",
            "--no-kd-validate",
        ]
    )
    assert rc == 0

    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    tau_calibration = report["tau_calibration"]
    assert tau_calibration["mode"] == "auto_from_labeled_reports"
    assert tau_calibration["policy"] == "balanced"
    assert tau_calibration["objective"] == "balanced_accuracy_then_gap"
    assert tau_calibration["constraints_satisfied"] is True
    assert tau_calibration["feasible_points"] >= 1
