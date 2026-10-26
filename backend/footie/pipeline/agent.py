""""Ask the match" as a tool-using agent.

Instead of stuffing a summary into the prompt, the model gets a small set of
read-only tools over the live match (the same analytics the overlays use) and
decides which to call: state, player stats, rankings, key moments, trends and
raw event counts. Every answer is built from tool results, and the tool calls
are returned as visible "steps" so viewers and judges can see how the answer
was reached.

Tools only see what has been ingested so far, so the agent never knows the
future of the match.
"""
from __future__ import annotations

import json
import logging

from ..i18n import tr
from .explain import PERSONAS, NameContext, _language_name, reasons

log = logging.getLogger(__name__)

MOMENT_KINDS = ["goal", "big_chance", "red_card", "control_shift", "pressure_surge", "milestone"]
PLAYER_METRICS = ["rating", "goals", "assists", "xg", "shots", "distance_km", "top_speed_kmh", "sprints",
                  "pass_accuracy_pct", "ball_wins", "pressures", "difficult_completed"]
TREND_METRICS = ["win_probability", "control", "pressure", "momentum", "rhythm"]
EVENT_TYPES = ["pass", "carry", "shot", "pressure", "tackle", "interception", "recovery", "save", "foul",
               "card", "corner", "throw_in", "goal_kick", "substitution"]

_minute_range = {
    "from_minute": {"type": "integer", "description": "Only include from this match minute (optional)"},
    "to_minute": {"type": "integer", "description": "Only include up to this match minute (optional)"},
}
_team = {"type": "string", "description": "Club name or code, optional"}


def _fn(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required or []},
    }}


TOOLS = [
    _fn("get_match_state", "Current score, minute, possession, shots, xG, pass completion, win probability, "
        "and the story indices (control vs chaos, pressure per team, rhythm, momentum).", {}),
    _fn("get_player_stats", "Live stats for one player: goals, assists, shots, xG, passing, ball wins, "
        "pressures, distance, top speed, sprints.",
        {"player": {"type": "string", "description": "Player name or surname, e.g. 'Dembe'"}}, ["player"]),
    _fn("top_players", "Rank the players by one metric, optionally for one team. 'rating' is the overall "
        "match rating (goals, assists, xG, shots on target, hard passes completed, ball wins, passing volume): "
        "use it for 'best', 'standout' or 'man of the match' questions.",
        {"metric": {"type": "string", "enum": PLAYER_METRICS}, "team": _team,
         "limit": {"type": "integer", "description": "How many players, default 5"}}, ["metric"]),
    _fn("find_moments", "Key moments so far, each with the computed reasons it mattered. Filter by kind, "
        "team, player or minute range.",
        {"kind": {"type": "string", "enum": MOMENT_KINDS}, "team": _team,
         "player": {"type": "string", "description": "Player name, optional"}, **_minute_range}),
    _fn("get_trend", "How one measure moved over a stretch of the match, sampled by minute. Use it to explain shifts.",
        {"metric": {"type": "string", "enum": TREND_METRICS}, **_minute_range}, ["metric"]),
    _fn("count_events", "Count raw match events by team with optional filters, for questions the stats "
        "don't cover (e.g. fouls in the second half, corners, tackles by one player).",
        {"type": {"type": "string", "enum": EVENT_TYPES}, "team": _team,
         "player": {"type": "string", "description": "Player name, optional"},
         "outcome": {"type": "string", "description": "e.g. complete, incomplete, goal, saved, won"},
         **_minute_range}, ["type"]),
]

AGENT_PROMPT = """You are the live match analyst inside a football broadcast companion app.
Answer the viewer's question about the match in progress (now at {minute}).
- Get facts with the tools. Never guess a number, name or event. If the tools cannot answer, say so.
- Use as few tool calls as you need, usually one to three.
- For "best player" or "standout" questions, rank by the overall rating, then explain with the player's stats.
- Answer in {language}, for {persona}
- Reply with only a JSON object: {{"answer": "<your answer>", "cites": ["<ids of key moments from find_moments you relied on>"]}}
- Do not put moment ids in the answer text."""


class MatchTools:
    """Read-only tools over a MatchSession, limited to what has been ingested so far."""

    def __init__(self, session):
        self.s = session
        self.ctx: NameContext = session.ctx
        self.cited_ids: set[str] = set()

    # ---------------------------------------------------------------- lookups
    def _side(self, team: str | None) -> str | None:
        if not team:
            return None
        t = team.strip().lower()
        for side in ("home", "away"):
            club = self.s.match.club(side)
            if t in (side, club.short.lower()) or t in club.name.lower() or club.name.lower() in t:
                return side
        return None

    def _players(self, name: str) -> list[str]:
        n = name.strip().lower().replace(".", "")
        hits = [pid for pid, full in self.ctx.full_names.items()
                if n == pid.lower() or n in full.lower() or full.lower().split()[-1] in n.split()]
        return hits

    @staticmethod
    def _in_range(clock: float, args: dict, period: int | None = None) -> bool:
        """Minute filters use the minute as displayed: 45+2' counts as 45, 90+4' as 90."""
        minute = int(clock // 60) + 1
        if period == 1:
            minute = min(minute, 45)
        elif period == 2:
            minute = min(max(minute, 46), 90)
        try:
            lo = int(args["from_minute"]) if args.get("from_minute") is not None else None
            hi = int(args["to_minute"]) if args.get("to_minute") is not None else None
        except (TypeError, ValueError):
            raise ValueError("from_minute and to_minute must be whole minutes")
        return (lo is None or minute >= lo) and (hi is None or minute <= hi)

    # ---------------------------------------------------------------- tools
    def get_match_state(self, args: dict) -> dict:
        st = self.s.state()
        home, away = self.ctx.team("home"), self.ctx.team("away")
        wp = st["win_probability"]
        ix = st["indices"]
        return {
            "minute": st["minute"],
            "finished": st["finished"],
            "score": {home: st["score"]["home"], away: st["score"]["away"]},
            "stats": {home: st["stats"]["home"], away: st["stats"]["away"]},
            "win_probability_pct": {home: round(100 * wp["home"]), "draw": round(100 * wp["draw"]),
                                    away: round(100 * wp["away"])},
            "story_indices_0_to_100": {
                "control_vs_chaos (high = controlled)": ix["control"],
                "rhythm (high = frantic)": ix["tempo"],
                f"pressure_{home}": ix["pressure"]["home"],
                f"pressure_{away}": ix["pressure"]["away"],
                "momentum_last_10_min (-100 away .. +100 home)": ix["momentum"],
            },
        }

    def _player_row(self, p: dict) -> dict:
        return {
            "name": self.ctx.full_names.get(p["id"], p["name"]), "team": self.ctx.team(p["side"]),
            "on_pitch": p["on_pitch"], "minutes": p["minutes"], "goals": p["goals"], "assists": p["assists"],
            "shots": p["shots"], "on_target": p["on_target"], "xg": p["xg"],
            "passes": p["passes"], "pass_accuracy_pct": p["pass_accuracy_pct"],
            "avg_pass_difficulty": p["avg_pass_difficulty"], "difficult_completed": p["difficult_completed"],
            "ball_wins": p["tackles"] + p["interceptions"], "pressures": p["pressures"],
            "distance_km": p["distance_km"], "top_speed_kmh": p["top_speed_kmh"], "sprints": p["sprints"],
            "cards": {"yellow": p["yellow"], "red": p["red"]},
            "rating": p["rating"],
            # Totals including this match so far (season, club and career records are synthetic, like the match).
            "records_incl_this_match": self.s.analyzer.history[p["id"]].to_dict(),
        }

    def get_player_stats(self, args: dict) -> dict:
        players = self.s.state()["players"]
        hits = [pid for pid in self._players(args.get("player", "")) if pid in players]
        if not hits:
            return {"error": f"No player matching '{args.get('player')}' has played yet."}
        if len(hits) > 1:
            return {"ambiguous": [self.ctx.full_names[h] for h in hits]}
        return self._player_row(players[hits[0]])

    def top_players(self, args: dict) -> dict:
        metric = args.get("metric", "goals")
        side = self._side(args.get("team"))
        rows = [self._player_row(p) for p in self.s.state()["players"].values()
                if p["minutes"] > 0 and (side is None or p["side"] == side)]
        rows = [r for r in rows if r.get(metric) is not None]
        rows.sort(key=lambda r: r[metric], reverse=True)
        limit = max(1, min(int(args.get("limit") or 5), 10))
        return {"metric": metric, "ranking": [{"name": r["name"], "team": r["team"], metric: r[metric]} for r in rows[:limit]]}

    def find_moments(self, args: dict) -> dict:
        side = self._side(args.get("team"))
        pids = set(self._players(args["player"])) if args.get("player") else None
        out = []
        for ins in self.s.insights.values():
            if not ins["key"] or ins["kind"] == "recap":
                continue
            if args.get("kind") and ins["kind"] != args["kind"]:
                continue
            if side and ins["side"] != side:
                continue
            if pids is not None and not pids & set(ins["players"]):
                continue
            if not self._in_range(ins["clock"], args, ins["period"]):
                continue
            self.cited_ids.add(ins["id"])
            moment = {
                "id": ins["id"], "minute": ins["minute"], "kind": ins["kind"],
                "team": self.ctx.team(ins["side"]) if ins["side"] else None,
                "why_it_mattered": [tr("en", c, **p) for c, p in reasons(ins, self.ctx)],
            }
            f = ins["facts"]
            name = lambda pid: self.ctx.full_names.get(pid, pid)  # noqa: E731
            if ins["kind"] == "goal":
                moment["scorer"] = name(f["scorer"])
                if f.get("assist"):
                    moment["assisted_by"] = name(f["assist"])
                moment["score_after"] = f"{f['score_after'][0]}-{f['score_after'][1]} ({self.ctx.team('home')} first)"
            elif ins["kind"] in ("big_chance", "red_card"):
                moment["player"] = name(f.get("shooter") or f.get("player"))
            elif ins["kind"] == "milestone":
                moment["milestone"] = tr("en", f"ms_{f['code']}", player=name(f["player"]), n=f["n"],
                                         team=self.ctx.team(ins["side"]))
            out.append(moment)
        return {"count": len(out), "moments": out[-15:]}

    def get_trend(self, args: dict) -> dict:
        metric = args.get("metric", "win_probability")
        home, away = self.ctx.team("home"), self.ctx.team("away")
        rows = [r for r in self.s.analyzer.series if self._in_range(r["minute"] * 60, args)]  # series minutes are display minutes
        if not rows:
            return {"error": "No data for that stretch yet."}
        step = max(1, len(rows) // 12)
        sample = rows[::step] + ([rows[-1]] if rows[-1] is not rows[::step][-1] else [])

        def value(r):
            if metric == "win_probability":
                return {home: round(100 * r["wp"][0]), "draw": round(100 * r["wp"][1]), away: round(100 * r["wp"][2])}
            if metric == "pressure":
                return {home: r["pressure_home"], away: r["pressure_away"]}
            return r[{"control": "control", "momentum": "momentum", "rhythm": "tempo"}.get(metric, "control")]

        scale = "percent" if metric == "win_probability" else (
            "-100 (away on top) to +100 (home on top)" if metric == "momentum" else "0-100 index, not a percentage")
        return {"metric": metric, "scale": scale,
                "points": [{"minute": int(r["minute"]) + 1, "value": value(r)} for r in sample]}

    def count_events(self, args: dict) -> dict:
        side = self._side(args.get("team"))
        pids = set(self._players(args["player"])) if args.get("player") else None
        seen = self.s.match.events[: self.s.feed._ei]
        counts = {self.ctx.team("home"): 0, self.ctx.team("away"): 0}
        for e in seen:
            if e["type"] != args.get("type"):
                continue
            if side and e["side"] != side:
                continue
            if pids is not None and e.get("player") not in pids:
                continue
            if args.get("outcome") and str(e.get("outcome") or e.get("card") or "") != args["outcome"]:
                continue
            if not self._in_range(e["clock"], args, e["period"]):
                continue
            counts[self.ctx.team(e["side"])] += 1
        return {"type": args.get("type"), "filters": {k: v for k, v in args.items() if k != "type"}, "counts": counts}

    def run(self, name: str, args: dict) -> dict:
        fn = getattr(self, name, None)
        if name not in {t["function"]["name"] for t in TOOLS} or fn is None:
            return {"error": f"Unknown tool {name}"}
        try:
            return fn(args or {})
        except Exception as exc:  # a bad argument should not end the conversation
            log.warning("tool %s failed: %s", name, exc)
            return {"error": f"{name} failed: {exc}"}


def _step_label(name: str, args: dict) -> str:
    shown = ", ".join(f"{v}" for v in args.values() if v not in (None, ""))
    return f"{name}({shown})"


async def ask_agent(llm, question: str, session, profile, max_steps: int = 5) -> dict:
    """Run the tool loop. Returns {answer, cites, steps, source}."""
    tools = MatchTools(session)
    persona = PERSONAS.get(profile.mode, PERSONAS["casual"]).format(
        player=session.ctx.player(profile.player), metric=profile.metric or "speed")
    system = AGENT_PROMPT.format(minute=session.state()["minute"], language=_language_name(profile.language),
                                 persona=persona)
    messages: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": question}]
    steps: list[str] = []
    out = {"content": None, "tool_calls": []}
    for _ in range(max_steps):
        out = await llm.chat(messages, tools=TOOLS)
        if not out["tool_calls"]:
            break
        messages.append({
            "role": "assistant", "content": out["content"] or "",
            "tool_calls": [{"id": c["id"], "type": "function",
                            "function": {"name": c["name"], "arguments": c["arguments"]}} for c in out["tool_calls"]],
        })
        for call in out["tool_calls"]:
            try:
                args = json.loads(call["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.run(call["name"], args)
            steps.append(_step_label(call["name"], args))
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    else:
        out = await llm.chat(messages)  # step budget used up: answer with what it has

    text = (out["content"] or "").strip()
    answer, cites = text, []
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            answer = parsed.get("answer", text)
            cites = parsed.get("cites", []) or []
        except json.JSONDecodeError:
            pass
    # Only keep citations the agent actually looked up, so a cite always points at real evidence.
    cites = [c for c in cites if c in tools.cited_ids]
    return {"answer": answer, "cites": cites, "steps": steps, "source": "agent"}
