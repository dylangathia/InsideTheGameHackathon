"""The half-time show, presented by the Pundit agent.

The Pundit works on the match as it stood at the half-time whistle (a separate session stopped there), so it
can never use second-half knowledge. With the Analyst's read-only tools plus `get_breakdown`, it picks the two
or three moments that decided the half and writes what a viewer hears while each move is drawn on the pitch.

Its script goes through the same Agent Framework workflow as the narration: the Verifier checks every number
against what the Pundit's tools returned, then fact-checks the rest; one rewrite, else a template show built
from the breakdowns. Without an LLM the template show is used directly.
"""
from __future__ import annotations

import json
import logging

from ..i18n import tr
from . import orchestration
from .agent import PUNDIT_TOOLS, MatchTools, _step_label
from .explain import PERSONAS, _language_name, allowed_numbers, numbers_in, reasons

log = logging.getLogger(__name__)

MAX_SEGMENTS = 3

PUNDIT_PROMPT = """You are the studio pundit presenting the half-time analysis on a live football broadcast.
The first half has just ended: {score}. The match is NOT over.
- Use the tools. Call find_moments with to_minute 45, pick the 2 or 3 moments that decided the half (goals and big
  chances first), and call get_breakdown for each one you pick.
- For each moment write "talk": up to 40 words the viewer hears while the move is drawn on screen. Say how it was
  built and why it worked: where the ball was won, the key pass, the defending shape.
- "closing": one sentence on what to watch in the second half, from the trends (get_match_state or get_trend).
- Use only facts from the tools. Copy numbers exactly. Never invent players, events or history.
- Write in {language}, for {persona}
Reply with only JSON: {{"title": "<max 6 words>", "segments": [{{"moment_id": "<id from find_moments>", "talk": "..."}}], "closing": "..."}}"""

SHOW_VERIFIER_PROMPT = """You are the fact-checker for a half-time analysis script on a live football broadcast.
EVIDENCE is the exact output of the match tools the pundit used, and it is correct. Numbers have already been
checked by software. List a problem only if the SCRIPT gets a player, team, score or outcome wrong, says or implies
the match is over, describes a move differently from its breakdown, or adds events that are not in the evidence.
Ignore style and wording. If there are no errors, return an empty list.
Return only JSON: {"problems": ["<short description in English>", ...]}"""


def _first_half_moments(session) -> list[dict]:
    return [i for i in session.insights.values()
            if i["key"] and i["period"] == 1 and i["kind"] in ("goal", "big_chance")]


def _assemble(session, show: dict, source: str, status: str) -> dict:
    segments = []
    for seg in show.get("segments", [])[:MAX_SEGMENTS]:
        ins = session.insights.get(str(seg.get("moment_id", "")))
        if not ins or not str(seg.get("talk", "")).strip():
            continue
        segments.append({"moment_id": ins["id"], "minute": ins["minute"], "kind": ins["kind"], "t": ins["t"],
                         "talk": seg["talk"].strip(), "breakdown": session.grounding(ins["id"]).get("breakdown")})
    segments.sort(key=lambda s: s["t"])
    return {"title": show.get("title") or "", "segments": segments, "closing": show.get("closing") or "",
            "source": source, "verification": status}


def template_show(session, profile) -> dict:
    """The show without a model: the half's goals and biggest chances, each with its breakdown and reasons."""
    lang = profile.language
    picks = sorted(_first_half_moments(session), key=lambda i: i["importance"], reverse=True)[:MAX_SEGMENTS]
    segments = []
    for ins in picks:
        board = session.grounding(ins["id"]).get("breakdown")
        why = [tr(lang, c, **p) for c, p in reasons(ins, session.ctx)][:1]
        talk = " ".join(x for x in ([f"{board['headline']}."] if board else []) + why)
        segments.append({"moment_id": ins["id"], "talk": talk})
    return _assemble(session, {"title": tr(lang, "recap_ht_h"), "segments": segments}, "template", "template")


def _score(session) -> str:
    st = session.state()
    return f"{session.ctx.team('home')} {st['score']['home']}-{st['score']['away']} {session.ctx.team('away')}"


async def build_show(llm, session, profile, on_step=None) -> dict:
    """The half-time show for one viewer profile. `session` must be stopped at the half-time whistle."""
    if not orchestration.enabled(llm) or not _first_half_moments(session):
        return template_show(session, profile)

    def emit(agent: str, action: str, detail: str = "") -> None:
        if on_step:
            try:
                on_step(agent, action, detail)
            except Exception as exc:  # the desk is a display; it must never break the show
                log.warning("agent desk update failed: %s", exc)

    tools = MatchTools(session)
    evidence: list[dict] = []

    def call_tool(name: str, args: dict) -> dict:
        emit("pundit", "looked up", _step_label(name, args))
        result = tools.run(name, args)
        evidence.append({"tool": _step_label(name, args), "result": result})
        return result

    persona = PERSONAS.get(profile.mode, PERSONAS["casual"]).format(
        player=session.ctx.player(profile.player), metric=profile.metric or "speed")
    system = PUNDIT_PROMPT.format(score=_score(session), language=_language_name(profile.language), persona=persona)

    async def write(payload: dict) -> dict | None:
        try:
            text = await orchestration.run_match_analyst(llm, system, json.dumps(payload, ensure_ascii=False),
                                                         PUNDIT_TOOLS, call_tool, max_steps=10, name="pundit",
                                                         max_tokens=700)
            show = orchestration.parse_json(text)
        except Exception as exc:
            log.warning("pundit failed: %s", exc)
            return None
        emit("pundit", "drafted" if "rejected_draft" not in payload else "rewrote", f"“{show.get('title', '')}”")
        return show

    async def check(show: dict) -> list[str]:
        problems = []
        known = {s["moment_id"] for s in show.get("segments", []) if s.get("moment_id") in session.insights}
        if not known:
            problems.append("No segment uses a moment id returned by find_moments.")
        script = " ".join([show.get("title", ""), *(s.get("talk", "") for s in show.get("segments", [])),
                           show.get("closing", "")])
        evidence_text = json.dumps(evidence, ensure_ascii=False)
        allowed = allowed_numbers({"facts": {}, "minute": "45+"}, session.ctx, [evidence_text, _score(session)])
        stray = [n for n in numbers_in(script) if n not in allowed]
        if stray:
            problems.append(f"Numbers not in the tool results: {', '.join(stray)}")
        if not problems:
            try:
                verdict = await orchestration.run_json_agent(
                    llm, "verifier", SHOW_VERIFIER_PROMPT,
                    json.dumps({"score_at_half_time": _score(session), "evidence": evidence, "script": show},
                               ensure_ascii=False), max_tokens=300, temperature=0.0)
                problems = [str(p) for p in verdict.get("problems", []) if str(p).strip()][:5]
            except Exception as exc:
                log.warning("show verifier unavailable: %s", exc)
                problems = ["verifier unavailable"]
        emit("verifier", "flagged" if problems else "passed", problems[0] if problems else "the half-time script")
        return problems

    outcome = await orchestration.narrate_and_verify({"task": "Present the half-time show."}, write, check)
    if outcome.status in ("passed", "passed_after_rewrite") and outcome.out:
        show = _assemble(session, outcome.out, "llm", outcome.status)
        if show["segments"]:
            emit("pundit", "presenting", show["title"])
            return show
    emit("verifier", "rejected", "the half-time script: the template show runs instead")
    return template_show(session, profile)
