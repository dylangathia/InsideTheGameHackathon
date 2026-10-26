"""Tactical breakdown of a goal or big chance: the move that led to it, and the defending team's shape.

This is the "half-time analysis" view. From the event stream it rebuilds the possession that ended in the
shot (where the ball was won, each pass and carry), names the patterns a pundit would point out (switch of
play, one-two, through ball, cross, counter-attack), and from the tracking data reads the defending team's
shape at the moment of the shot (formation, how deep their back line was, attackers v defenders in the box).
"""
from __future__ import annotations

import math

from ..sim.simulator import SimulatedMatch, other, to_frame

REGAINS = {"tackle": "Tackle", "interception": "Interception", "recovery": "Loose ball won"}
RESTARTS = {"throw_in": "Throw-in", "corner": "Corner", "goal_kick": "Goal kick"}
LOOKBACK_S = 45.0
MAX_STEPS = 12


def _name(match: SimulatedMatch, pid: str | None) -> str | None:
    return match.player(pid).short if pid else None


def _pass_label(e: dict, side: str, prev: dict | None) -> str:
    x0, y0 = to_frame(side, e["x"], e["y"])
    x1, y1 = to_frame(side, e["end_x"], e["end_y"])
    dist = math.hypot(x1 - x0, y1 - y0)
    ptype = e.get("pass_type", "ground")
    if ptype == "through":
        return "Through ball"
    if ptype == "cross":
        return "Cross into the box"
    if ptype in ("corner", "free_kick", "kick_off", "throw_in", "goal_kick"):
        return {"corner": "Corner delivery", "free_kick": "Free kick", "kick_off": "Kick-off",
                "throw_in": "Throw-in", "goal_kick": "Goal kick"}[ptype]
    if prev and prev["type"] == "pass" and prev.get("recipient") == e["player"] and e.get("recipient") == prev["player"]:
        return "One-two"
    if abs(y1 - y0) >= 28 and dist >= 28:
        return "Switch of play"
    if x1 - x0 >= 18:
        return "Forward pass breaks a line"
    if x1 - x0 <= -6:
        return "Recycled back"
    return "Pass"


def _shape(match: SimulatedMatch, defending: str, t: float) -> dict | None:
    """Defending team's shape at time t from tracking: their lines (back to front, e.g. "6-3-1" for a deep
    block), how far their back line is from goal, and attackers v defenders in the box."""
    tr = match.tracking
    if tr is None:
        return None
    frame = tr.frame(tr.index(t))
    club = match.club(defending)
    gk = {p.id for p in club.players if p.position == "GK"}
    outfield = []
    box = {"attackers": 0, "defenders": 0}
    for pid, x, y in frame["players"]:
        side = match.side_of(pid)
        fx, fy = to_frame(defending, x, y)  # in the defenders' frame their own goal is at x = 0
        if fx <= 16.5 and abs(fy - 34) <= 20.16:
            box["defenders" if side == defending else "attackers"] += 1
        if side == defending and pid not in gk:
            outfield.append((fx, x, y))
    if len(outfield) < 6:
        return None
    outfield.sort()
    # Lines the way a pundit reads them: the back line is everyone level with the deepest defender (within 6 m),
    # the front line everyone level with the most advanced player (within 7 m), and the rest is midfield.
    deepest, furthest = outfield[0][0], outfield[-1][0]
    back = [p for p in outfield if p[0] <= deepest + 6]
    front = [p for p in outfield if p[0] >= furthest - 7 and p not in back]
    mid = [p for p in outfield if p not in back and p not in front]
    lines = [line for line in (back, mid, front) if line]
    return {
        "team": club.name,
        "side": defending,
        "formation": club.formation,  # their system; the lines below show how they actually stood
        "back_line_m": round(sum(p[0] for p in back) / len(back)),
        "back_line_players": len(back),
        "lines": [[[round(x, 1), round(y, 1)] for _, x, y in sorted(line, key=lambda p: p[2])] for line in lines],
        "box": box,
    }


def build(match: SimulatedMatch, shot: dict, xg: float | None = None) -> dict:
    """The possession that ended in `shot`, step by step, plus the defenders' shape at the shot."""
    side = shot["side"]
    idx = next(i for i, e in enumerate(match.events) if e["id"] == shot["id"])
    collected: list[dict] = []
    for e in reversed(match.events[:idx]):
        if e["t"] < shot["t"] - LOOKBACK_S or len(collected) >= MAX_STEPS:
            break
        if e["type"] == "foul" and e["side"] != side:
            collected.append(e)  # a free kick: the move starts with the set piece
            break
        if e["side"] != side and e["type"] in ("pass", "carry", "shot", "save", *REGAINS, *RESTARTS):
            break  # the other team had the ball before this
        if e["type"] == "pass" and e["side"] == side and e.get("outcome") != "complete":
            break  # this pass gave the ball away; our move started after it
        if e["type"] in REGAINS and e["side"] == side:
            collected.append(e)
            break
        if e["type"] in RESTARTS and e["side"] == side:
            collected.append(e)
            break
        if e["type"] == "pass" and e["side"] == side:
            collected.append(e)
        elif e["type"] == "carry" and e["side"] == side:
            if math.hypot(e["end_x"] - e["x"], e["end_y"] - e["y"]) >= 8:
                collected.append(e)  # only runs worth drawing
        elif e["type"] == "period_start":
            break
    collected.reverse()

    steps = []
    prev_pass = None
    for e in collected + [shot]:
        step = {"t": e["t"], "x": e.get("x"), "y": e.get("y"), "end_x": e.get("end_x"), "end_y": e.get("end_y"),
                "player": _name(match, e.get("player"))}
        if e["type"] in REGAINS:
            fx, _ = to_frame(side, e["x"], e["y"])
            step.update(kind="regain", label=f"{REGAINS[e['type']]}{' high up the pitch' if fx >= 60 else ''}")
        elif e["type"] in RESTARTS:
            step.update(kind="restart", label=RESTARTS[e["type"]])
        elif e["type"] == "foul":
            step.update(kind="restart", label="Free kick won", detail=f"foul by {_name(match, e.get('player'))}",
                        player=_name(match, e.get("fouled")))
        elif e["type"] == "pass":
            dist = math.hypot(e["end_x"] - e["x"], e["end_y"] - e["y"])
            step.update(kind="pass", label=_pass_label(e, side, prev_pass), detail=f"{dist:.0f} m",
                        to=_name(match, e.get("recipient")))
            prev_pass = e
        elif e["type"] == "carry":
            dist = math.hypot(e["end_x"] - e["x"], e["end_y"] - e["y"])
            step.update(kind="carry", label="Drives forward with the ball", detail=f"{dist:.0f} m")
        else:  # the shot
            if e.get("set_piece") == "free_kick":
                label = "Direct free kick: goal" if e["outcome"] == "goal" else "Direct free kick"
            else:
                label = "Goal" if e["outcome"] == "goal" else {"saved": "Shot saved", "post": "Hits the post",
                                                            "off_target": "Shot wide", "blocked": "Shot blocked"}[e["outcome"]]
                label = label
            step.update(kind="shot", label=label, detail=f"{xg:.2f} xG" if xg is not None else None)
        steps.append(step)
    for n, s in enumerate(steps, 1):
        s["n"] = n

    first = collected[0] if collected else shot
    secs = shot["t"] - first["t"]
    x_start, _ = to_frame(side, first.get("x", 52.5), first.get("y", 34))
    x_shot, _ = to_frame(side, shot["x"], shot["y"])
    passes = sum(1 for e in collected if e["type"] == "pass")
    if shot.get("set_piece") == "free_kick":
        headline = "Straight from the free kick"
    elif collected and collected[0]["type"] == "foul":
        headline = f"From a free kick: {passes} passes in {secs:.0f} seconds"
    elif collected and collected[0]["type"] in RESTARTS:
        headline = f"From a {RESTARTS[collected[0]['type']].lower()}"
    elif secs <= 15 and x_shot - x_start >= 40:
        headline = f"Counter-attack: {x_shot - x_start:.0f} m in {secs:.0f} seconds"
    elif passes >= 7:
        headline = f"Patient build-up: {passes} passes in {secs:.0f} seconds"
    elif collected and collected[0]["type"] in REGAINS and x_start >= 60:
        headline = "Won high, punished quickly"
    else:
        headline = f"{passes}-pass move in {secs:.0f} seconds"
    return {"headline": headline, "team": match.club(side).name, "side": side, "t_shot": shot["t"],
            "steps": steps, "shape": _shape(match, other(side), shot["t"])}
