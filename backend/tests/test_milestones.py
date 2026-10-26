"""Milestones: season and career records carried into the match, with the landmarks called out live."""
from footie.pipeline.personalize import Profile
from footie.pipeline.runner import MatchSession
from footie.sim.history import RECORDS
from footie.sim.scenarios import load_match


def _milestones(sid):
    s = MatchSession(load_match(sid))
    s.run_to_end()
    return s, [i for i in s.insights.values() if i["kind"] == "milestone"]


def test_records_are_consistent():
    for r in RECORDS.values():
        assert 0 <= r.season_goals <= r.club_goals <= r.career_goals
        assert r.season_apps <= r.club_apps


def test_goal_milestone_reaches_card_and_goal_reasons():
    s, ms = _milestones("comeback")
    thorne = next(m for m in ms if m["facts"]["player"] == "NBR-9")
    assert (thorne["facts"]["code"], thorne["facts"]["n"], thorne["facts"]["club_goals"]) == ("club_goals", 50, 50)
    goal = next(i for i in s.insights.values() if i["kind"] == "goal" and i["facts"]["scorer"] == "NBR-9")
    assert goal["facts"]["milestones"] == [{"code": "club_goals", "n": 50}]
    casual = s.personalize(next(o for o in s.overlays if o["insight_id"] == goal["id"]), Profile(mode="casual"))
    assert any("50 goals for Northbridge FC" in w for w in casual["text"]["why"])


def test_appearance_milestones_and_debut():
    _, ms = _milestones("comeback")
    codes = {(m["facts"]["player"], m["facts"]["code"], m["facts"]["n"]) for m in ms}
    assert ("NBR-5", "club_apps", 200) in codes
    assert ("RVA-17", "debut", 1) in codes
