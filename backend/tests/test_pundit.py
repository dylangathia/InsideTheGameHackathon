"""The half-time show: built only from first-half data, fact-checked, with a template fallback."""
import asyncio
import json

import pytest

from footie.pipeline import orchestration, pundit
from footie.pipeline.personalize import Profile
from footie.pipeline.runner import MatchSession
from footie.sim.scenarios import load_match


def _half_time(sid="comeback"):
    m = load_match(sid)
    s = MatchSession(m)
    s.advance_to(m.period_ends[0] + 0.5)
    return s


def test_template_show_uses_first_half_goals_with_breakdowns():
    show = pundit.template_show(_half_time(), Profile())
    assert show["source"] == "template" and 1 <= len(show["segments"]) <= 3
    assert all(seg["breakdown"] and seg["t"] < 2900 for seg in show["segments"])
    assert [seg["t"] for seg in show["segments"]] == sorted(seg["t"] for seg in show["segments"])


@pytest.mark.skipif(not orchestration.AVAILABLE, reason="agent-framework not installed")
def test_pundit_script_is_checked_and_rewritten(monkeypatch):
    s = _half_time()
    goal = next(i for i in s.insights.values() if i["kind"] == "goal")
    scripts = [
        {"title": "Half-time", "segments": [{"moment_id": goal["id"], "talk": "A 999 km/h strike."}], "closing": "x"},
        {"title": "Half-time", "segments": [{"moment_id": goal["id"], "talk": "Won high, finished fast."}], "closing": "x"},
    ]
    seen = []

    async def fake_agent(llm, system, question, specs, call_tool, max_steps, name="", max_tokens=0):
        seen.append(json.loads(question))
        call_tool("find_moments", {"to_minute": 45})
        return json.dumps(scripts[len(seen) - 1])

    async def fake_verifier(llm, name, instructions, user, max_tokens, temperature):
        return {"problems": []}

    monkeypatch.setattr(orchestration, "enabled", lambda llm: True)
    monkeypatch.setattr(orchestration, "run_match_analyst", fake_agent)
    monkeypatch.setattr(orchestration, "run_json_agent", fake_verifier)
    steps = []
    show = asyncio.run(pundit.build_show(object(), s, Profile(), on_step=lambda *a: steps.append(a[:2])))
    assert show["source"] == "llm" and show["verification"] == "passed_after_rewrite"
    assert "999" in seen[1]["fix_these_problems"][0]  # the invented number was caught by software
    assert show["segments"][0]["talk"] == "Won high, finished fast." and show["segments"][0]["breakdown"]
    assert ("verifier", "flagged") in steps and ("pundit", "presenting") in steps
