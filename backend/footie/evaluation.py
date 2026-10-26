"""Groundedness evaluation: run every key moment through the Narrator and Verifier agents.

For each scenario and viewer profile, every AI-eligible key moment is written by
the Narrator agent and checked by the Verifier agent (a deterministic number
check plus an LLM fact-check against the computed facts). We report how many
drafts passed first time, how many the Verifier caught and the Narrator fixed,
and how many were rejected so the template text stayed on screen.
"""
from __future__ import annotations

import asyncio
import time
from collections import Counter
from datetime import datetime, timezone

from .pipeline import orchestration
from .pipeline.explain import Narrator
from .pipeline.personalize import Profile
from .pipeline.runner import MatchSession
from .sim.scenarios import SCENARIOS, load_match

# Two analysts and two fans, four languages, both clubs' fans represented across matches.
PROFILES = [
    ("Analyst · English", lambda home, away: Profile(mode="analyst", language="en")),
    ("Analyst · French", lambda home, away: Profile(mode="analyst", language="fr")),
    ("Away fan · Spanish", lambda home, away: Profile(mode="casual", language="es", club=away)),
    ("Home fan · Swahili", lambda home, away: Profile(mode="casual", language="sw", club=home)),
]


def _sabotage(ins: dict, session) -> list[tuple[str, Profile, dict]]:
    """Wrong versions of a goal's narration, each with one planted error and no numbers (so only the AI check can
    catch them), plus the viewer profile each is aimed at."""
    ctx, f, side = session.ctx, ins["facts"], ins["side"]
    other = "away" if side == "home" else "home"
    scorer, team, rival = ctx.full_names[f["scorer"]], ctx.team(side), ctx.team(other)
    rival_player = ctx.full_names[next(p.id for p in session.match.club(other).starters if p.position == "ST")]
    rival_short = session.match.club(other).short
    neutral = Profile(mode="analyst", language="en")
    return [
        ("goal credited to the wrong club", neutral,
         {"headline": f"Goal for {rival}!", "body": f"{scorer} scores for {rival} and the away end erupts."}),
        ("wrong scorer", neutral,
         {"headline": f"Goal! {rival_player} scores", "body": f"{rival_player} finishes it off for {team}."}),
        ("says the match is over", neutral,
         {"headline": f"{team} have won it", "body": f"That's full time: {scorer}'s goal wins the match for {team}."}),
        ("good news framed for the wrong fans", Profile(mode="casual", language="en", club=rival_short),
         {"headline": f"Brilliant news for {rival} fans!", "body": f"{scorer} scores and {rival} supporters are celebrating."}),
    ]


async def sabotage_test(narrator: Narrator) -> dict:
    """Plant known errors in goal narrations and count how many the Verifier catches; clean template text as control."""
    cases = []
    for sid in SCENARIOS:
        session = MatchSession(load_match(sid))
        session.run_to_end()
        for ins in (i for i in session.insights.values() if i["kind"] == "goal"):
            ov = next(o for o in session.overlays if o["insight_id"] == ins["id"])
            for error, prof, out in _sabotage(ins, session):
                cases.append((error, ins, prof, session, out))
            clean = session.personalize(ov, Profile(mode="analyst", language="en"))["text"]
            cases.append(("clean template text (control)", ins, Profile(mode="analyst", language="en"), session,
                          {"headline": clean["headline"], "body": " ".join([clean.get("body", ""), *clean["why"]])}))

    async def run(case):
        error, ins, prof, session, out = case
        draft = session.personalize(next(o for o in session.overlays if o["insight_id"] == ins["id"]), prof)["text"]
        payload = narrator.payload(ins, prof, session.ctx, draft)
        problems = await narrator.check(ins, prof, session.ctx, out, payload, draft)
        if problems == ["verifier unavailable"]:
            return error, None
        return error, bool(problems)

    results = await asyncio.gather(*[run(c) for c in cases])
    by: dict[str, list[bool]] = {}
    for error, caught in results:
        if caught is not None:
            by.setdefault(error, []).append(caught)
    return by


async def evaluate(narrator: Narrator) -> dict:
    rows = []
    started = time.time()
    narrator.llm.sem = asyncio.Semaphore(2)  # stay under the deployment's tokens-per-minute quota
    for sid in SCENARIOS:
        match = load_match(sid)
        session = MatchSession(match)
        session.run_to_end()
        keys = [i for i in session.insights.values() if i["key"] and i["kind"] in Narrator.LLM_KINDS]
        jobs = []
        for label, make in PROFILES:
            prof = make(match.home.short, match.away.short)
            for ins in keys:
                ov = next(o for o in session.overlays if o["insight_id"] == ins["id"])
                p = session.personalize(ov, prof)
                if p is not None:
                    jobs.append((sid, label, ins, prof, p["text"]))

        async def run(job):
            sid_, label_, ins_, prof_, draft = job
            out = await narrator.rewrite(ins_, prof_, session.ctx, draft)
            if out is None:
                key = narrator.cache_key(ins_, prof_, session.ctx)
                rejected = [r for r in narrator.rejections if r["key"] == key and r["insight"] == ins_["id"]]
                status = "rejected" if rejected else "error"
                problems = rejected[-1]["problems"] + ["second draft: " + "; ".join(rejected[-1]["second"])] if rejected else []
            else:
                status = out["verification"]["status"]
                problems = out["verification"].get("problems_fixed", [])
            # An unreachable Verifier is a network failure, not a catch: count it with the errors (or as a pass,
            # if the retry was verified).
            if any("verifier unavailable" in p for p in problems):
                if status == "rejected":
                    status, problems = "error", []
                elif status == "passed_after_rewrite" and all("verifier unavailable" in p for p in problems):
                    status, problems = "passed", []
            return {"scenario": sid_, "profile": label_, "kind": ins_["kind"], "minute": ins_["minute"],
                    "status": status, "problems": problems}

        rows += await asyncio.gather(*[run(j) for j in jobs])
    sabotage = await sabotage_test(narrator)
    return {"rows": rows, "sabotage": sabotage, "seconds": round(time.time() - started), "model": narrator.llm.model,
            "provider": narrator.llm.provider, "agent_framework": orchestration.enabled(narrator.llm)}


def report(result: dict) -> str:
    rows = result["rows"]
    total = len(rows)
    c = Counter(r["status"] for r in rows)
    shown = c["passed"] + c["passed_after_rewrite"]

    def pct(n: int) -> str:
        return f"{100 * n / total:.0f}%" if total else "n/a"

    lines = [
        "# Groundedness evaluation",
        "",
        f"Run on {datetime.now(timezone.utc):%d %B %Y} with {result['provider']} ({result['model']})"
        f"{' on Microsoft Agent Framework (narrator -> verifier workflow)' if result.get('agent_framework') else ''}, "
        f"{total} AI narrations in {result['seconds']} s.",
        "Regenerate with `python cli.py evaluate` in `backend/`.",
        "",
        "Every key moment of all three demo matches (goals, big chances, red cards, control shifts, pressure "
        "surges, recaps) was written by the **Narrator agent** for four viewer profiles, then checked by the "
        "**Verifier agent** before it could reach the screen. The Verifier runs a deterministic check that every "
        "number appears in the computed facts, then an LLM fact-check of players, teams, score, outcome and fan "
        "framing. A failed draft goes back to the Narrator once with the problems listed. If it fails again, the "
        "template text stays on screen.",
        "",
        "## Results",
        "",
        "| Outcome | Narrations | Share |",
        "|---|---|---|",
        f"| Passed first time | {c['passed']} | {pct(c['passed'])} |",
        f"| Caught by the Verifier, fixed by a rewrite | {c['passed_after_rewrite']} | {pct(c['passed_after_rewrite'])} |",
        f"| Rejected twice: template text shown instead | {c['rejected']} | {pct(c['rejected'])} |",
        f"| Model or network error: template text shown | {c['error']} | {pct(c['error'])} |",
        f"| **AI text that reached the screen verified** | **{shown}** | **{pct(shown)}** |",
        "",
        f"Leaving out network errors (a property of the connection, not the agents), **{shown} of {total - c['error']} "
        f"narrations ({100 * shown / max(1, total - c['error']):.0f}%) reached the screen as verified AI text**, "
        f"and every other one fell back to the correct template text. No unverified AI text was ever shown.",
        "",
        "## By viewer profile",
        "",
        "| Profile | Narrations | Passed first time | Fixed by rewrite | Rejected |",
        "|---|---|---|---|---|",
    ]
    for label, _ in PROFILES:
        rs = [r for r in rows if r["profile"] == label]
        pc = Counter(r["status"] for r in rs)
        lines.append(f"| {label} | {len(rs)} | {pc['passed']} | {pc['passed_after_rewrite']} | {pc['rejected']} |")
    sab = result.get("sabotage") or {}
    if sab:
        planted = {k: v for k, v in sab.items() if "control" not in k}
        hits = sum(sum(v) for v in planted.values())
        n = sum(len(v) for v in planted.values())
        lines += ["", "## Sabotage test: does the Verifier catch planted errors?", "",
                  "For every goal in the three matches we wrote wrong versions of the narration, each with one planted "
                  "error and no numbers, so only the AI fact-check (not the number check) can catch it. Clean template "
                  "text is the control: it should pass.", "",
                  "| Planted error | Caught |", "|---|---|"]
        for k, v in sab.items():
            if "control" in k:
                continue
            lines.append(f"| {k[0].upper() + k[1:]} | {sum(v)} of {len(v)} |")
        lines.append(f"| **All planted errors** | **{hits} of {n} ({100 * hits / max(1, n):.0f}%)** |")
        for k, v in sab.items():
            if "control" in k:
                lines += ["", f"Control: {len(v) - sum(v)} of {len(v)} clean template narrations passed "
                              f"({sum(v)} flagged as false alarms)."]
    caught = [r for r in rows if r["problems"]]
    lines += ["", "## What the Verifier caught", ""]
    if not caught:
        lines.append("Nothing: every draft passed first time.")
    for r in caught[:20]:
        outcome = "fixed" if r["status"] == "passed_after_rewrite" else "rejected"
        lines.append(f"- **{SCENARIOS[r['scenario']].title}, {r['minute']} {r['kind'].replace('_', ' ')}** "
                     f"({r['profile']}, {outcome}): {'; '.join(r['problems'])}")
    lines += [
        "",
        "## Limits",
        "",
        "- The number check is exact. The fact-check is itself a model, so this measures what passes our "
        "checks, not a human rating. Native speakers should still review the non-English text.",
        "- Matches are the three scripted demo scenarios, so results on other matches may differ.",
        "",
    ]
    return "\n".join(lines)


def run_evaluation() -> str:
    narrator = Narrator()
    if not narrator.enabled:
        raise SystemExit("No AI model configured: set the Foundry (AZURE_OPENAI_*) settings in backend/.env")
    return report(asyncio.run(evaluate(narrator)))
