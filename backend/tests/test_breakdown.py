"""Tactical breakdown: every goal gets a move that ends in the shot, with the defenders' shape."""
from footie.pipeline import breakdown
from footie.sim.scenarios import SCENARIOS, load_match


def test_every_goal_has_a_breakdown():
    for sid in SCENARIOS:
        m = load_match(sid)
        for shot in (e for e in m.events if e["type"] == "shot" and e["outcome"] == "goal"):
            b = breakdown.build(m, shot, 0.2)
            assert b["steps"][-1]["kind"] == "shot"
            assert [s["n"] for s in b["steps"]] == list(range(1, len(b["steps"]) + 1))
            assert all(s["t"] <= shot["t"] for s in b["steps"])
            assert b["headline"]
            assert b["shape"] is None or b["shape"]["lines"]
