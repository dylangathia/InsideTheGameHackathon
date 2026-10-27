"""The five-stage pipeline for one match.

    ingest -> interpret -> explain -> render -> personalise

Ingest, interpret and render run once per match and are shared by every
viewer. Explain (text) and personalise run per viewer profile, so one match
can feed an analyst and a casual fan side by side.
"""
from __future__ import annotations

from ..i18n import tr
from ..sim.simulator import SimulatedMatch
from . import breakdown as tactics
from .explain import NameContext, readable_facts, reasons
from .ingest import FabricEventstreamSink, MatchFeed
from .interpret import MatchAnalyzer, minute_label
from .personalize import Profile, personalize
from .render import to_overlay


class MatchSession:
    def __init__(self, match: SimulatedMatch, sink: FabricEventstreamSink | None = None):
        self.match = match
        self.feed = MatchFeed(match, sink)
        self.analyzer = MatchAnalyzer(match)
        self.ctx = NameContext.from_match(match)
        self.insights: dict[str, dict] = {}
        self.overlays: list[dict] = []
        self._events = {e["id"]: e for e in match.events}
        self._grounding: dict[str, dict] = {}

    @property
    def t(self) -> float:
        return self.feed.t

    def advance_to(self, t: float) -> list[dict]:
        """Ingest everything up to match time t; return the new raw overlays."""
        events, frames = self.feed.advance_to(t)
        an = self.analyzer
        new: list[dict] = []
        i = j = 0
        while i < len(events) or j < len(frames):
            if j >= len(frames) or (i < len(events) and events[i]["t"] <= frames[j]["t"]):
                new += an.ingest_event(events[i])
                i += 1
            else:
                new += an.ingest_frame(frames[j])
                j += 1
        new += an.tick(self.feed.t)
        overlays = []
        for ins in new:
            self.insights[ins["id"]] = ins
            ov = to_overlay(ins)
            overlays.append(ov)
        self.overlays += overlays
        return overlays

    def run_to_end(self, step: float = 5.0) -> None:
        t = self.t
        while t < self.match.duration:
            t += step
            self.advance_to(t)

    def personalize(self, ov: dict, profile: Profile) -> dict | None:
        p = personalize(ov, self.insights[ov["insight_id"]], profile, self.ctx, self.insights)
        if p and p["key"] and p["kind"] != "recap":
            p["grounding"] = self.grounding(ov["insight_id"], profile.language)
        return p

    def grounding(self, insight_id: str, lang: str = "en") -> dict:
        """What a key moment rests on: the facts and reasons given to the model, and the raw events.

        The breakdown board is drawn in the viewer's language; the facts stay as the model saw them.
        """
        key = (insight_id, lang)
        if key not in self._grounding:
            ins = self.insights[insight_id]
            facts = {}
            for k, v in readable_facts(ins["facts"], self.ctx).items():
                if isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) for x in v):
                    facts[k] = f"{v[0]}–{v[1]}"  # scorelines
                elif v is not None and not isinstance(v, (dict, list)):
                    facts[k] = v
            board = None
            if ins["kind"] in ("goal", "big_chance") and ins["evidence"] and ins["evidence"][0] in self._events:
                board = tactics.build(self.match, self._events[ins["evidence"][0]], ins["facts"].get("xg"), lang)
            self._grounding[key] = {
                "breakdown": board,
                "facts": facts,
                "reasons": [tr("en", c, **p) for c, p in reasons(ins, self.ctx)],
                "events": [self._event_summary(self._events[i]) for i in ins["evidence"] if i in self._events],
            }
        return self._grounding[key]

    def _event_summary(self, e: dict) -> dict:
        detail = e.get("outcome") or e.get("card") or e.get("pass_type")
        return {
            "id": e["id"],
            "minute": minute_label(e["period"], e["clock"]),
            "type": e["type"],
            "team": e["team"],
            "player": self.ctx.full_names.get(e.get("player") or "", e.get("player")),
            "detail": detail,
        }

    def frame(self) -> dict | None:
        f = self.feed.frame_at(self.t)
        if not f:
            return None
        return {
            "t": round(self.t, 2),
            "ball": [round(f["ball"][0], 2), round(f["ball"][1], 2)],
            "players": [[pid, round(x, 2), round(y, 2)] for pid, x, y in f["players"]],
        }

    def state(self) -> dict:
        return self.analyzer.snapshot()

    def key_moments(self, profile: Profile) -> list[dict]:
        out = []
        for ins in self.insights.values():
            if not ins["key"] or ins["kind"] == "recap":
                continue
            ov = self.personalize(to_overlay(ins), profile)
            if ov:
                out.append(ov)
        return out

    def ask_context(self, profile: Profile) -> dict:
        """Compact, grounded match context for 'Ask the match'.

        Kept small on purpose: free-tier model APIs cap tokens per minute, and the
        "why" sentences already carry the meaning of each moment's raw facts.
        """
        state = self.state()
        moments = []
        for ins in self.insights.values():
            if ins["key"] and ins["kind"] != "recap":
                moments.append({
                    "id": ins["id"],
                    "minute": ins["minute"],
                    "kind": ins["kind"],
                    "team": self.ctx.team(ins["side"]) if ins["side"] else None,
                    "players": [self.ctx.full_names.get(p, p) for p in ins["players"]],
                    "why": [tr("en", c, **p) for c, p in reasons(ins, self.ctx)],
                })
        players = {
            pid: {
                "name": p["name"],
                "team": self.ctx.team(p["side"]),
                "minutes": p["minutes"],
                "goals": p["goals"],
                "assists": p["assists"],
                "shots": p["shots"],
                "xg": p["xg"],
                "pass_accuracy_pct": p["pass_accuracy_pct"],
                "ball_wins": p["tackles"] + p["interceptions"],
                "distance_km": p["distance_km"],
                "top_speed_kmh": p["top_speed_kmh"],
            }
            for pid, p in state.pop("players").items()
            if p["minutes"] > 0
        }
        state.pop("series", None)
        state.pop("on_pitch", None)
        return {
            "home": self.match.home.name,
            "away": self.match.away.name,
            "state": state,
            "key_moments": moments[-20:],
            "players": players,
        }
