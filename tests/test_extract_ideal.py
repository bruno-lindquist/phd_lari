import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from cut_precision.config import ExtractionConfig
from cut_precision.extract import _select_ideal_component_group


def test_select_ideal_component_group_prefers_central_components():
    mask = np.zeros((200, 200), dtype=np.uint8)
    cv2.circle(mask, (85, 100), 18, 255, -1)
    cv2.circle(mask, (115, 100), 18, 255, -1)
    cv2.rectangle(mask, (0, 40), (30, 140), 255, -1)  # border-touching distraction

    cfg = ExtractionConfig(
        ideal_min_area_ratio=0.001,
        ideal_group_area_ratio_to_max=0.3,
        ideal_group_center_radius_ratio=0.5,
        ideal_group_close_kernel=11,
    )
    grouped = _select_ideal_component_group(mask, cfg)

    # Border region should be filtered out.
    assert np.count_nonzero(grouped[:, :20]) == 0

    # Central region should remain present and connected.
    num, _, stats, _ = cv2.connectedComponentsWithStats((grouped > 0).astype(np.uint8), 8)
    assert num >= 2
    area = int(stats[1, cv2.CC_STAT_AREA])
    assert area > 1500
