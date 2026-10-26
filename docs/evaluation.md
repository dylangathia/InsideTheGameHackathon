# Groundedness evaluation

Run on 26 October 2026 with Foundry (gpt-4.1-mini), 206 AI narrations in 215 s.
Regenerate with `python cli.py evaluate` in `backend/`.

Every key moment of all three demo matches (goals, big chances, red cards, control shifts, pressure surges, recaps) was written by the **Narrator agent** for four viewer profiles, then checked by the **Verifier agent** before it could reach the screen. The Verifier runs a deterministic check that every number appears in the computed facts, then an LLM fact-check of players, teams, score, outcome and fan framing. A failed draft goes back to the Narrator once with the problems listed. If it fails again, the template text stays on screen.

## Results

| Outcome | Narrations | Share |
|---|---|---|
| Passed first time | 131 | 64% |
| Caught by the Verifier, fixed by a rewrite | 27 | 13% |
| Rejected twice: template text shown instead | 27 | 13% |
| Model or network error: template text shown | 21 | 10% |
| **AI text that reached the screen verified** | **158** | **77%** |

Leaving out network errors (a property of the connection, not the agents), **158 of 185 narrations (85%) reached the screen as verified AI text**, and every other one fell back to the correct template text. No unverified AI text was ever shown.

## By viewer profile

| Profile | Narrations | Passed first time | Fixed by rewrite | Rejected |
|---|---|---|---|---|
| Analyst · English | 57 | 39 | 8 | 6 |
| Analyst · French | 57 | 41 | 6 | 4 |
| Away fan · Spanish | 46 | 29 | 5 | 6 |
| Home fan · Swahili | 46 | 22 | 8 | 11 |

## What the Verifier caught

- **The Comeback, 45+2' goal** (Analyst · English, rejected): The draft incorrectly states that the goal ends Northbridge FC's 10-minute dominance, whereas the facts say the goal came against the run of play, meaning Northbridge FC had been on top before the goal but the goal did not end their dominance.; second draft: The draft incorrectly states that the goal reduces Riverside Athletic's deficit to 2-1, implying Riverside was behind by 2 goals before the goal. However, the score before was Northbridge FC 2, Riverside Athletic 0, so the goal actually reduces the deficit from 2-0 to 2-1, not just reducing the deficit to 2-1. The draft wording is slightly ambiguous but acceptable. No clear misleading error found.
- **The Comeback, 45+3' recap** (Analyst · English, rejected): Numbers not supported by the facts: 78.7; second draft: The draft says 'Oskar Coulter's 45+2' goal reduces Northbridge's control,' which implies a negative impact on Northbridge FC, but the facts show Northbridge FC is still leading 2-1 at half-time, so this framing may mislead viewers about the current advantage.
- **The Comeback, 67' goal** (Analyst · English, fixed): The headline 'P. Dembe Breaks Deadlock' is incorrect because the score was 2-2 before the goal, so the deadlock was already broken. This goal puts Riverside Athletic ahead, not breaks the deadlock.
- **The Comeback, 45+2' goal** (Analyst · French, rejected): The draft incorrectly states that Oskar Coulter plays for Northbridge FC, but he actually plays for Riverside Athletic.; second draft: no rewrite
- **The Comeback, 52' pressure surge** (Analyst · French, fixed): The draft incorrectly states 'Cette domination territoriale' implying territorial dominance, but the facts do not confirm territorial dominance, only increased pressing and high regains.
- **The Comeback, 75' pressure surge** (Away fan · Spanish, fixed): The draft frames the pressure surge as bad news for Riverside Athletic, but the facts say Northbridge FC is behind and chasing the game, so this pressure surge is a positive development for Northbridge FC and bad news for Riverside Athletic. The draft's framing is correct and matches the facts, so no problem.
- **The Comeback, 36' pressure surge** (Home fan · Swahili, rejected): Headline 'Northbridge FC Yashika Dakika 36'' is unclear and misleading; it suggests 'holding 36 minutes' rather than indicating the time of the event; second draft: The draft implies Northbridge FC is already winning and can strengthen their victory, but the facts do not say the match is over or that they have won.
- **The Comeback, 36' pressure surge** (Home fan · Swahili, rejected): The draft implies the moment is good news for Riverside Athletic, but the viewer supports Northbridge FC, so it should be framed as bad news for Northbridge FC.; second draft: Draft implies the moment is good news for Riverside Athletic, but the viewer supports Northbridge FC, so it should be framed as bad news for Northbridge FC, not good news for Riverside Athletic.
- **The Comeback, 45+2' goal** (Home fan · Swahili, rejected): The draft incorrectly states the score after the goal as 2-1 in favor of Riverside Athletic, but the correct score is Northbridge FC 2-1 Riverside Athletic. The draft implies Riverside Athletic is leading, which is incorrect.; second draft: verifier unavailable
- **The Comeback, 46' goal** (Home fan · Swahili, rejected): verifier unavailable; second draft: no rewrite
- **The Comeback, 52' pressure surge** (Home fan · Swahili, rejected): The draft incorrectly states that Riverside Athletic regained the ball 5 times in the middle of Northbridge FC, but the facts specify the regains were in the opposition half, not necessarily the middle.; second draft: The draft implies the match is over or a decisive outcome has been reached, which is not supported by the facts.
- **The Comeback, 69' control shift** (Home fan · Swahili, rejected): The draft incorrectly states that Northbridge FC is losing control, but the facts show Riverside Athletic is in control, which is bad news for Northbridge FC, so the framing is correct. No errors found.; second draft: verifier unavailable
- **The Comeback, 90+6' recap** (Home fan · Swahili, rejected): verifier unavailable; second draft: Draft implies the match is ongoing or recent, but facts confirm the match is finished.
- **Ten Men, 28' control shift** (Analyst · English, fixed): verifier unavailable
- **Ten Men, 36' pressure surge** (Analyst · English, fixed): Numbers not supported by the facts: 31
- **Ten Men, 45+3' recap** (Analyst · English, rejected): verifier unavailable; second draft: verifier unavailable
- **Ten Men, 69' goal** (Analyst · English, rejected): verifier unavailable; second draft: verifier unavailable
- **Ten Men, 81' goal** (Analyst · English, fixed): Headline 'O. Coulter doubles lead' is incorrect because the lead was already 2-0 and the goal made it 3-0, so the lead was not doubled but increased to three.
- **Ten Men, 83' control shift** (Analyst · English, fixed): verifier unavailable
- **Ten Men, 28' control shift** (Analyst · French, fixed): verifier unavailable

## Limits

- The number check is exact. The fact-check is itself a model, so this measures what passes our checks, not a human rating. Native speakers should still review the non-English text.
- Matches are the three scripted demo scenarios, so results on other matches may differ.
