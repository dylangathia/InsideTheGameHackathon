# Groundedness evaluation

Run on 26 October 2026 with Foundry (gpt-4.1-mini) on Microsoft Agent Framework (narrator -> verifier workflow), 206 AI narrations in 325 s.
Regenerate with `python cli.py evaluate` in `backend/`.

Every key moment of all three demo matches (goals, big chances, red cards, control shifts, pressure surges, recaps) was written by the **Narrator agent** for four viewer profiles, then checked by the **Verifier agent** before it could reach the screen. The Verifier runs a deterministic check that every number appears in the computed facts, then an LLM fact-check of players, teams, score, outcome and fan framing. A failed draft goes back to the Narrator once with the problems listed. If it fails again, the template text stays on screen.

## Results

| Outcome | Narrations | Share |
|---|---|---|
| Passed first time | 192 | 93% |
| Caught by the Verifier, fixed by a rewrite | 12 | 6% |
| Rejected twice: template text shown instead | 2 | 1% |
| Model or network error: template text shown | 0 | 0% |
| **AI text that reached the screen verified** | **204** | **99%** |

Leaving out network errors (a property of the connection, not the agents), **204 of 206 narrations (99%) reached the screen as verified AI text**, and every other one fell back to the correct template text. No unverified AI text was ever shown.

## By viewer profile

| Profile | Narrations | Passed first time | Fixed by rewrite | Rejected |
|---|---|---|---|---|
| Analyst · English | 57 | 54 | 3 | 0 |
| Analyst · French | 57 | 54 | 3 | 0 |
| Away fan · Spanish | 46 | 43 | 2 | 1 |
| Home fan · Swahili | 46 | 41 | 4 | 1 |

## Sabotage test: does the Verifier catch planted errors?

For every goal in the three matches we wrote wrong versions of the narration, each with one planted error and no numbers, so only the AI fact-check (not the number check) can catch it. Clean template text is the control: it should pass.

| Planted error | Caught |
|---|---|
| Goal credited to the wrong club | 11 of 11 |
| Wrong scorer | 11 of 11 |
| Says the match is over | 11 of 11 |
| Good news framed for the wrong fans | 11 of 11 |
| **All planted errors** | **44 of 44 (100%)** |

Control: 11 of 11 clean template narrations passed (0 flagged as false alarms).

## What the Verifier caught

- **The Comeback, 90+6' recap** (Analyst · English, fixed): The headline 'Riverside Athletic Leads' implies the match is ongoing, but the facts confirm the match is finished with Riverside Athletic winning 3-2.
- **The Comeback, 75' pressure surge** (Away fan · Spanish, fixed): The draft frames the pressure surge as bad news for Riverside Athletic, but the viewer supports Riverside Athletic, so this framing is misleading.
- **The Comeback, 19' goal** (Home fan · Swahili, fixed): The goal was scored from open play, not a free kick as stated in the draft.
- **The Comeback, 36' pressure surge** (Home fan · Swahili, rejected): The draft incorrectly states that Riverside Athletic regained the ball 3 times in midfield, but the facts say the regains were in the opposition half (high regains).; second draft: The draft incorrectly states that Riverside Athletic regained the ball in the middle of the pitch, but the facts say the regains were in the opposition half (high regains).
- **The Comeback, 46' goal** (Home fan · Swahili, fixed): The headline implies Riverside Athletic won the goal, but it was an equalizer, not a winning goal.
- **The Comeback, 67' goal** (Home fan · Swahili, fixed): The draft headline says Pavel Dembe 'asawazisha tena' (scores an equalizer again), but the goal actually puts Riverside Athletic ahead 3-2, not equalizing.
- **Ten Men, 75' goal** (Analyst · English, fixed): The headline 'T. Corrigan Breaks Deadlock' is incorrect because the score was already 1-0 before this goal, so it did not break the deadlock.
- **Ten Men, 9' control shift** (Analyst · French, fixed): The draft implies Kingsport United is dominating, but the facts indicate a chaotic state with no team advantage specified.
- **Ten Men, 36' pressure surge** (Away fan · Spanish, fixed): Numbers not supported by the facts: 31
- **Ten Men, 77' pressure surge** (Away fan · Spanish, rejected): The draft incorrectly states that Kingsport United recovered the ball 4 times in the opposition penalty area, but the facts say it was in the opposition half, not specifically the penalty area.; second draft: The draft implies the moment is good news for Ashford Rovers, but since Ashford Rovers are leading by 2 goals and Kingsport United is pressing to reduce the deficit, it is actually bad news for Ashford Rovers.
- **Ten Men, 56' pressure surge** (Home fan · Swahili, fixed): The draft incorrectly states that Ashford Rovers regained the ball 3 times in the middle of the pitch, but the facts say the regains were in the opposition half (high regains).
- **Late Drama, 69' pressure surge** (Analyst · English, fixed): Numbers not supported by the facts: 64
- **Late Drama, 45+2' recap** (Analyst · French, fixed): Numbers not supported by the facts: 76.5
- **Late Drama, 78' pressure surge** (Analyst · French, fixed): The draft implies the match is at 0-0 and that the pressure surge could 'unlock the score', but the facts only state the score difference is 0, not the actual score or that the match is goalless.

## Limits

- The Verifier can be wrong too. In this run it wrongly said the 19' goal in The Comeback was open play, not a free kick; the only effect was an unnecessary rewrite.
- The number check is exact. The fact-check is itself a model, so this measures what passes our checks, not a human rating. Native speakers should still review the non-English text.
- Matches are the three scripted demo scenarios, so results on other matches may differ.
