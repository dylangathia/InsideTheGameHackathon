"""Runs auto-eventing over windows of the demo matches and writes docs/auto-eventing.md."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from ..sim.scenarios import SCENARIOS, load_match
from .autoevent import FPS, run

# Five-minute windows that include goals, so shots are tested too.
WINDOWS = {"comeback": 3990.0, "red_card": 4180.0, "derby": 5050.0}
CLIP = ("comeback", 394.7, 37.0)  # the 8' opener: a 7-pass move ending in a goal


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "n/a"


def build_report(clip_path: str | None, seconds: float = 300.0) -> str:
    rows, totals = [], {"tp": 0, "ts": 0, "mp": 0, "ms": 0, "det": 0, "oc": 0, "base": 0,
                        "de": [], "se": [], "sse": [], "frames": 0}
    started = time.time()
    for sid, start in WINDOWS.items():
        match = load_match(sid)
        events, ev = run(match, start, seconds)
        s = ev.summary()
        truth = [e for e in match.events if e["type"] == "pass" and start + 0.2 <= e["t"] <= start + seconds - 2.5]
        base = sum(e["outcome"] == "complete" for e in truth)
        rows.append((SCENARIOS[sid].title, s, base, len(truth)))
        totals["tp"] += ev.truth_passes
        totals["ts"] += ev.truth_shots
        totals["mp"] += ev.matched_passes
        totals["ms"] += ev.matched_shots
        totals["det"] += ev.detected
        totals["oc"] += ev.outcome_correct
        totals["base"] += base
        totals["de"] += ev.distance_errors
        totals["se"] += ev.speed_errors
        totals["sse"] += ev.shot_speed_errors
        totals["frames"] += ev.frames
    if clip_path:
        sid, start, secs = CLIP
        run(load_match(sid), start, secs, clip_path=clip_path)
    mean = lambda xs: f"{sum(xs) / len(xs):.1f}" if xs else "n/a"  # noqa: E731
    t = totals
    lines = [
        "# Auto-eventing from video",
        "",
        f"Run on {datetime.now(timezone.utc):%d %B %Y}: {t['frames']} video frames ({t['frames'] / FPS / 60:.0f} minutes of "
        f"play at {FPS} fps) in {time.time() - started:.0f} s. Regenerate with `python cli.py autoevent` in `backend/`.",
        "",
        "The brief suggests \"running a model over an incoming video feed to generate the pass and speed metrics "
        "automatically, rather than tagging them by hand\". Because our matches are synthetic, we know the exact truth "
        "of every event, so we can measure the result.",
        "",
        "**How it works** ([backend/footie/vision/autoevent.py](../backend/footie/vision/autoevent.py)):",
        "",
        "1. **Camera:** the match is rendered as a top-down video feed with sensor noise, blur, camera shake, "
        "lighting drift, dropped frames (3%) and a ball that is sometimes hidden (4%).",
        "2. **Detector:** computer vision finds players by kit colour and the ball as a small round bright blob, from "
        "the pixels alone. It never sees the tracking data.",
        "3. **Events:** the ball is tracked frame to frame; fast movement (over 8 m/s) is a flight. Each flight becomes "
        "a pass (distance, ball speed) or, if it ends at the goal mouth, a shot (shot speed). Possession is chained "
        "from receiver to the next passer.",
        "4. **Evaluation:** each true pass and shot is matched to a detection that starts within 0.6 s.",
        "",
        "## Results",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Passes detected | **{t['mp']} of {t['tp']} ({_pct(t['mp'], t['tp'])})** |",
        f"| Shots detected | **{t['ms']} of {t['ts']} ({_pct(t['ms'], t['ts'])})** |",
        f"| Detections that were real events (precision) | {_pct(t['mp'] + t['ms'], t['det'])} |",
        f"| Pass distance error | **{mean(t['de'])} m** on average |",
        f"| Ball speed error | **{mean(t['se'])} km/h** on average |",
        f"| Shot speed error | **{mean(t['sse'])} km/h** on average |",
        f"| Pass completed or lost | {_pct(t['oc'], t['mp'])} correct, but always guessing \"completed\" scores "
        f"{_pct(t['base'], t['tp'])}, so this part is **not yet useful** |",
        "",
        "## By match window (5 minutes each, around goals)",
        "",
        "| Match | Passes found | Shots found | Precision | Distance error | Ball speed error | Shot speed error |",
        "|---|---|---|---|---|---|---|",
    ]
    for title, s, base, n in rows:
        lines.append(f"| {title} | {s['pass_recall_pct']}% of {s['truth_passes']} | {s['shot_recall_pct']}% of "
                     f"{s['truth_shots']} | {s['precision_pct']}% | {s['pass_distance_error_m']} m | "
                     f"{s['ball_speed_error_kmh']} km/h | {s['shot_speed_error_kmh'] or 'n/a'} km/h |")
    lines += [
        "",
        "An annotated clip (the 8' opener in The Comeback, a 7-pass move ending in a goal, with every detection drawn "
        "on the frames) is in [media/auto-eventing.mp4](media/auto-eventing.mp4).",
        "",
        "## Limits",
        "",
        "- **Not tested on real footage.** A clean top-down render is far easier than broadcast video, which has camera "
        "pans, perspective, crowds and heavy occlusion. This shows and measures the method; it is not a claim of "
        "real-world accuracy.",
        "- **Classic computer vision, not a trained model.** A production system would use a trained detector (e.g. a "
        "YOLO-style model) for players and the ball; the event logic downstream would stay the same.",
        "- **Pass outcome is weak.** Telling a completed pass from a lost one needs reliable player identity at the "
        "moment of the pass; our colour-only detection can't separate a passer from a defender pressing them.",
        "- The ingest stage accepts any event source, so a production auto-eventing model could replace the synthetic "
        "engine without changing the rest of the pipeline.",
        "",
    ]
    return "\n".join(lines)
