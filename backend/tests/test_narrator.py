"""The LLM layer, exercised with a stub model so it runs without Azure credentials."""
import asyncio
import json

from footie.pipeline.explain import Narrator
from footie.pipeline.personalize import Profile
from footie.pipeline.runner import MatchSession
from footie.sim.scenarios import load_match


class StubLLM:
    def __init__(self, fail: bool = False, verdicts=None, headlines=None):
        self.calls: list[tuple[str, dict]] = []
        self.verifier_calls: list[dict] = []
        self.verdicts: list[dict] = list(verdicts or [])
        self.headlines: list[dict] = list(headlines or [])
        self.fail = fail

    async def complete_json(self, system: str, user: str, max_tokens: int = 300, temperature: float = 0.6) -> dict:
        if self.fail:
            raise RuntimeError("service down")
        payload = json.loads(user)
        if "fact-checker" in system:
            self.verifier_calls.append(payload)
            return self.verdicts.pop(0) if self.verdicts else {"verdict": "pass", "problems": []}
        self.calls.append((system, payload))
        if "question" in payload:
            return {"answer": "Stub answer", "cites": ["i1"]}
        if self.headlines:
            return self.headlines.pop(0)
        return {"headline": f"Stub {payload['moment']}", "body": "Grounded body"}


def _goal_session():
    s = MatchSession(load_match("comeback"))
    s.advance_to(1200)
    goal = next(i for i in s.insights.values() if i["kind"] == "goal")
    return s, goal


def test_rewrite_uses_only_facts_and_caches():
    s, goal = _goal_session()
    stub = StubLLM()
    narrator = Narrator(llm=stub)
    prof = Profile(mode="casual", language="sw", club="RVA")
    draft = s.personalize([o for o in s.overlays if o["insight_id"] == goal["id"]][0], prof)["text"]
    out = asyncio.run(narrator.rewrite(goal, prof, s.ctx, draft))
    assert out["headline"] == "Stub goal" and out["source"] == "llm"
    system, payload = stub.calls[0]
    assert "Kiswahili" in system and "Riverside Athletic" in system
    assert payload["why_it_matters"] and payload["facts"]["scorer"]
    asyncio.run(narrator.rewrite(goal, prof, s.ctx, draft))
    assert len(stub.calls) == 1  # cached


def test_rewrite_failure_falls_back_to_template():
    s, goal = _goal_session()
    narrator = Narrator(llm=StubLLM(fail=True))
    assert asyncio.run(narrator.rewrite(goal, Profile(), s.ctx, {"headline": "x"})) is None


def test_answer_with_and_without_llm():
    s, _ = _goal_session()
    ctx = s.ask_context(Profile())
    assert asyncio.run(Narrator(llm=StubLLM()).answer("why?", ctx, Profile(), s.ctx))["answer"] == "Stub answer"
    offline = Narrator(llm=False)
    ans = asyncio.run(offline.answer("What's the score?", ctx, Profile(), s.ctx))
    assert ans["source"] == "rules" and "Northbridge" in ans["answer"]


def _draft(s, goal, prof):
    return s.personalize([o for o in s.overlays if o["insight_id"] == goal["id"]][0], prof)["text"]


def test_verifier_passes_clean_text():
    s, goal = _goal_session()
    stub = StubLLM()
    out = asyncio.run(Narrator(llm=stub).rewrite(goal, Profile(), s.ctx, _draft(s, goal, Profile())))
    assert out["verification"] == {"status": "passed"} and len(stub.verifier_calls) == 1


def test_number_check_catches_invented_numbers_and_rewrite_fixes_it():
    s, goal = _goal_session()
    stub = StubLLM(headlines=[
        {"headline": "Thorne scores", "body": "A 140 km/h rocket from 40 m."},  # invented numbers
        {"headline": "Thorne scores", "body": "Struck at 101.5 km/h."},           # corrected
    ])
    n = Narrator(llm=stub)
    out = asyncio.run(n.rewrite(goal, Profile(), s.ctx, _draft(s, goal, Profile())))
    assert out["body"] == "Struck at 101.5 km/h."
    assert out["verification"]["status"] == "passed_after_rewrite"
    assert "140" in out["verification"]["problems_fixed"][0]
    assert stub.calls[1][1]["fix_these_problems"]  # the Narrator was told what to fix


def test_verifier_rejection_keeps_the_template():
    s, goal = _goal_session()
    stub = StubLLM(verdicts=[{"verdict": "fail", "problems": ["says the match is over"]}] * 2)
    n = Narrator(llm=stub)
    assert asyncio.run(n.rewrite(goal, Profile(), s.ctx, _draft(s, goal, Profile()))) is None
    assert n.stats == {"checked": 1, "failed_first": 1, "rejected": 1}
