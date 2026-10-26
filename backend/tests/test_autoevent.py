"""Auto-eventing: the vision pipeline finds passes from pixels alone, with accurate distances and speeds."""
import math

import pytest

cv2 = pytest.importorskip("cv2")

from footie.sim.scenarios import load_match  # noqa: E402
from footie.vision.autoevent import Camera, Detector, hex_bgr, run, to_m, to_px  # noqa: E402


def test_pixel_conversion_round_trips():
    for x, y in [(0, 0), (52.5, 34), (105, 68), (88.4, 12.1)]:
        bx, by = to_m(*to_px(x, y))
        assert math.dist((x, y), (bx, by)) < 0.1


def test_detector_finds_ball_and_players_from_pixels():
    m = load_match("comeback")
    cam = Camera(m, degrade=False)
    det = Detector({"home": hex_bgr(m.home.primary), "away": hex_bgr(m.away.primary)}, background=cam.base)
    pos, ball = cam.positions(2900)
    d = det.detect(cam.frame(2900), 2900, None)
    assert d.ball is not None and math.dist(d.ball, ball) < 0.6
    found = sum(any(math.dist(p, (x, y)) < 1.5 for _, x, y in d.players) for p in pos.values())
    assert found >= len(pos) - 1


def test_passes_detected_with_accurate_metrics():
    _, ev = run(load_match("comeback"), 2900, 40)
    s = ev.summary()
    assert s["pass_recall_pct"] >= 80
    assert s["precision_pct"] >= 80
    assert s["pass_distance_error_m"] < 3
    assert s["ball_speed_error_kmh"] < 8
