"""Season and career records for the fictional players, as they stood before kick-off.

Synthetic like everything else: generated per player from position and quality, seeded by the player id so
it is the same every run. A few players are written with storylines (one goal short of 50 for the club, yet
to score this season, about to make a debut) so the demo matches contain milestones to call out.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass

from .teams import CLUBS, Player

SEASON = "2026/27"
MATCHWEEK = 11  # the demo matches are all matchweek 11

GOALS_PER_GAME = {"ST": 0.45, "LW": 0.3, "RW": 0.3, "AM": 0.25, "LM": 0.15, "RM": 0.15, "CM": 0.1, "DM": 0.05,
                  "LB": 0.03, "RB": 0.03, "CB": 0.04, "GK": 0.0}
ASSISTS_PER_GAME = {"ST": 0.15, "LW": 0.25, "RW": 0.25, "AM": 0.3, "LM": 0.2, "RM": 0.2, "CM": 0.15, "DM": 0.08,
                    "LB": 0.1, "RB": 0.1, "CB": 0.02, "GK": 0.0}

STORYLINES: dict[str, dict[str, int]] = {
    "NBR-9": {"club_goals": 49},              # K. Thorne: one short of 50 for Northbridge
    "NBR-8": {"season_goals": 0},             # C. Marchetti: yet to score this season
    "NBR-5": {"club_apps": 199},              # R. Wren: 200th appearance for the club
    "RVA-11": {"season_goals": 8},            # P. Dembe: two short of double figures
    "RVA-17": {"club_apps": 0},               # I. Santoro: on the bench for a first appearance
    "ASH-9": {"career_goals": 98},            # O. Coulter: two short of a career century
    "ASH-5": {"club_goals": 0},               # T. Corrigan: yet to score for Ashford
    "KSU-6": {"club_apps": 99},               # J. Tembo: 100th appearance for the club
}


@dataclass
class Record:
    club_apps: int
    season_apps: int
    season_goals: int
    season_assists: int
    club_goals: int
    career_goals: int

    def to_dict(self) -> dict:
        return asdict(self)


def _avoid_round(n: int, steps: tuple[int, ...]) -> int:
    """Generated (non-storyline) totals never sit one short of a milestone, so only storylines fire."""
    return n + 2 if n + 1 in steps else n


def _record(p: Player) -> Record:
    rng = random.Random(f"history-{p.id}")
    starter = p.number <= 11
    season_apps = rng.randint(7, MATCHWEEK - 1) if starter else rng.randint(1, 6)
    club_apps = season_apps + rng.randint(15, 180)
    club_apps = _avoid_round(club_apps, tuple(range(100, 1000, 50)))
    quality = 0.7 + 0.6 * p.shooting + (0.3 if p.star else 0.0)
    g, a = GOALS_PER_GAME[p.position] * quality, ASSISTS_PER_GAME[p.position] * (0.6 + 0.6 * p.passing)
    season_goals = sum(rng.random() < g for _ in range(season_apps))
    season_assists = sum(rng.random() < a for _ in range(season_apps))
    club_goals = season_goals + round(g * (club_apps - season_apps) * rng.uniform(0.7, 1.2))
    career_goals = club_goals + round(g * rng.randint(0, 150) * rng.uniform(0.6, 1.1))
    rec = Record(
        club_apps=club_apps,
        season_apps=season_apps,
        season_goals=_avoid_round(season_goals, (1, 10, 20)) if season_goals else (1 if g >= 0.1 else 0),
        season_assists=_avoid_round(season_assists, (10, 20)),
        club_goals=_avoid_round(club_goals, (25, 50, 100, 150, 200)),
        career_goals=_avoid_round(career_goals, tuple(range(50, 1000, 50))),
    )
    for k, v in STORYLINES.get(p.id, {}).items():
        setattr(rec, k, v)
    # Keep the totals consistent: season <= club <= career, and a debutant has no history at the club.
    if rec.club_apps == 0:
        rec.season_apps = rec.season_goals = rec.season_assists = rec.club_goals = 0
    rec.season_goals = min(rec.season_goals, rec.club_goals)
    rec.club_goals = max(rec.club_goals, rec.season_goals)
    rec.career_goals = max(rec.career_goals, rec.club_goals)
    return rec


RECORDS: dict[str, Record] = {p.id: _record(p) for c in CLUBS.values() for p in c.players}


def record(pid: str) -> Record:
    return Record(**RECORDS[pid].to_dict())  # a copy: the match adds to it as it goes
