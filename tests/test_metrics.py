import numpy as np

from cut_precision.metrics import compute_bidirectional_diagnostics, compute_statistics


def test_compute_statistics_basic():
    values = np.array([0.0, 1.0, 2.0, 3.0], dtype=np.float32)
    stats = compute_statistics(values)
    assert stats.mad == 1.5
    assert np.isclose(stats.std, np.std(values))
    assert np.isclose(stats.p95, np.percentile(values, 95))
    assert stats.max_error == 3.0


def test_bidirectional_diagnostics():
    r2i = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    i2r = np.array([2.0, 4.0], dtype=np.float32)
    diag = compute_bidirectional_diagnostics(r2i, i2r)
    assert diag.mad_real_to_ideal == 2.0
    assert diag.mad_ideal_to_real == 3.0
    assert diag.bidirectional_mad == 2.5
    assert diag.hausdorff == 4.0
