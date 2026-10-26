"""The Microsoft Agent Framework path: the narrator -> verifier workflow and the match analyst's tools.

The agents' model calls are replaced by the stubs from the other tests, so this runs offline and checks the
workflow wiring itself: pass, one rewrite after a rejection, and rejection after two failures.
"""
import asyncio

import pytest

from footie.pipeline import orchestration
from footie.pipeline.explain import Narrator
from footie.pipeline.personalize import Profile
from test_narrator import StubLLM, _draft, _goal_session

pytestmark = pytest.mark.skipif(not orchestration.AVAILABLE, reason="agent-framework not installed")


@pytest.fixture(autouse=True)
def framework_on(monkeypatch):
    async def run_json_agent(llm, name, instructions, user, max_tokens, temperature):
        return await llm.complete_json(instructions, user, max_tokens=max_tokens, temperature=temperature)

    monkeypatch.setattr(orchestration, "enabled", lambda llm: True)
    monkeypatch.setattr(orchestration, "run_json_agent", run_json_agent)


def test_workflow_passes_clean_text():
    s, goal = _goal_session()
    stub = StubLLM()
    out = asyncio.run(Narrator(llm=stub).rewrite(goal, Profile(), s.ctx, _draft(s, goal, Profile())))
    assert out["verification"] == {"status": "passed", "orchestrator": "Microsoft Agent Framework"}
    assert len(stub.calls) == 1 and len(stub.verifier_calls) == 1


def test_workflow_sends_a_rejected_draft_back_once():
    s, goal = _goal_session()
    stub = StubLLM(headlines=[
        {"headline": "Thorne scores", "body": "A 140 km/h rocket from 40 m."},  # invented numbers
        {"headline": "Thorne scores", "body": "Struck at 101.5 km/h."},
    ])
    out = asyncio.run(Narrator(llm=stub).rewrite(goal, Profile(), s.ctx, _draft(s, goal, Profile())))
    assert out["body"] == "Struck at 101.5 km/h." and out["verification"]["status"] == "passed_after_rewrite"
    assert "140" in out["verification"]["problems_fixed"][0]
    assert stub.calls[1][1]["fix_these_problems"]


def test_workflow_rejects_after_two_failures():
    s, goal = _goal_session()
    stub = StubLLM(verdicts=[{"problems": ["says the match is over"]}] * 2)
    n = Narrator(llm=stub)
    assert asyncio.run(n.rewrite(goal, Profile(), s.ctx, _draft(s, goal, Profile()))) is None
    assert n.stats == {"checked": 1, "failed_first": 1, "rejected": 1}
    assert len(stub.calls) == 2  # written, rewritten once, then the template stays
