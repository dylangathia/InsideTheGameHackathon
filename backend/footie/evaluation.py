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


async def evaluate(narrator: Narrator) -> dict:
    rows = []
    started = time.time()
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
                key = (ins_["id"], prof_.mode, prof_.language, prof_.club, prof_.player, prof_.metric)
                rejected = [r for r in narrator.rejections if r["key"] == key and r["insight"] == ins_["id"]]
                status = "rejected" if rejected else "error"
                problems = rejected[-1]["problems"] + ["second draft: " + "; ".join(rejected[-1]["second"])] if rejected else []
            else:
                status = out["verification"]["status"]
                problems = out["verification"].get("problems_fixed", [])
            return {"scenario": sid_, "profile": label_, "kind": ins_["kind"], "minute": ins_["minute"],
                    "status": status, "problems": problems}

        rows += await asyncio.gather(*[run(j) for j in jobs])
    return {"rows": rows, "seconds": round(time.time() - started), "model": narrator.llm.model,
            "provider": narrator.llm.provider}


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
        f"Run on {datetime.now(timezone.utc):%d %B %Y} with {result['provider']} ({result['model']}), "
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
