import numpy as np

from cut_precision.metrics import compute_statistics


def test_compute_statistics_basic():
    values = np.array([0.0, 1.0, 2.0, 3.0], dtype=np.float32)
    stats = compute_statistics(values)
    assert stats.mad == 1.5
    assert np.isclose(stats.std, np.std(values))
    assert np.isclose(stats.p95, np.percentile(values, 95))
    assert stats.max_error == 3.0
