"""The 'Ask the match' agent: tools return the same facts as the analytics, and the loop works."""
import asyncio
import json

import pytest

from footie.pipeline.agent import TOOLS, MatchTools, ask_agent
from footie.pipeline.personalize import Profile
from footie.pipeline.runner import MatchSession
from footie.sim.scenarios import load_match


@pytest.fixture(scope="module")
def late():
    s = MatchSession(load_match("comeback"))
    s.advance_to(4300)  # just after the 67' winner
    return s


def test_tools_match_the_analytics(late):
    t = MatchTools(late)
    state = t.get_match_state({})
    assert state["score"] == {"Northbridge FC": 2, "Riverside Athletic": 3}
    dembe = t.get_player_stats({"player": "Dembe"})
    assert dembe["name"] == "Pavel Dembe" and dembe["goals"] == 2
    top = t.top_players({"metric": "goals", "limit": 1})["ranking"][0]
    assert top["name"] == "Pavel Dembe"
    goals = t.find_moments({"kind": "goal"})
    assert goals["count"] == 5
    second_half = t.find_moments({"kind": "goal", "from_minute": 46})
    assert [m["minute"] for m in second_half["moments"]] == ["46'", "67'"]
    corners = t.count_events({"type": "corner"})["counts"]
    assert sum(corners.values()) == sum(late.state()["stats"][s]["corners"] for s in ("home", "away"))
    trend = t.get_trend({"metric": "win_probability", "from_minute": 60, "to_minute": 70})
    assert trend["points"] and "Riverside Athletic" in trend["points"][-1]["value"]


def test_tools_cannot_see_the_future():
    s = MatchSession(load_match("comeback"))
    s.advance_to(1200)
    t = MatchTools(s)
    assert t.find_moments({"kind": "goal"})["count"] == 2
    assert "error" in t.get_player_stats({"player": "Lowry"}) or t.get_player_stats({"player": "Lowry"})["minutes"] == 0


def test_bad_tool_input_does_not_crash(late):
    t = MatchTools(late)
    assert "error" in t.run("drop_tables", {})
    assert "error" in t.get_player_stats({"player": "Nobody At All"})
    assert t.run("get_trend", {"metric": "control", "from_minute": "x"})  # returns an error dict, not an exception


class ScriptedLLM:
    """Plays back tool calls, then a final answer, like a real model would."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.seen: list[list[dict]] = []

    async def chat(self, messages, tools=None, max_tokens=500):
        self.seen.append([dict(m) for m in messages])
        return self.turns.pop(0)


def test_agent_loop_runs_tools_and_filters_cites(late):
    goal_ids = [m["id"] for m in MatchTools(late).find_moments({"kind": "goal"})["moments"]]
    llm = ScriptedLLM([
        {"content": None, "tool_calls": [
            {"id": "c1", "name": "find_moments", "arguments": json.dumps({"kind": "goal", "player": "Dembe"})},
            {"id": "c2", "name": "get_player_stats", "arguments": json.dumps({"player": "Dembe"})},
        ]},
        {"content": json.dumps({"answer": "Dembe scored twice.", "cites": [goal_ids[-1], "i99999"]}), "tool_calls": []},
    ])
    out = asyncio.run(ask_agent(llm, "How is Dembe doing?", late, Profile(mode="analyst")))
    assert out["answer"] == "Dembe scored twice."
    assert out["cites"] == [goal_ids[-1]]  # the made-up id is dropped
    assert out["steps"] == ["find_moments(goal, Dembe)", "get_player_stats(Dembe)"]
    tool_msgs = [m for m in llm.seen[1] if m["role"] == "tool"]
    assert len(tool_msgs) == 2 and json.loads(tool_msgs[1]["content"])["goals"] == 2


def test_tool_schemas_are_valid():
    names = [t["function"]["name"] for t in TOOLS]
    assert len(names) == len(set(names))
    for t in TOOLS:
        assert hasattr(MatchTools, t["function"]["name"])
        assert t["function"]["parameters"]["type"] == "object"
