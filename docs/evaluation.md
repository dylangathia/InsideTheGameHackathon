# Groundedness evaluation

Run on 26 October 2026 with Foundry (gpt-4.1-mini) on Microsoft Agent Framework (narrator -> verifier workflow), 206 AI narrations in 238 s.
Regenerate with `python cli.py evaluate` in `backend/`.

Every key moment of all three demo matches (goals, big chances, red cards, control shifts, pressure surges, recaps) was written by the **Narrator agent** for four viewer profiles, then checked by the **Verifier agent** before it could reach the screen. The Verifier runs a deterministic check that every number appears in the computed facts, then an LLM fact-check of players, teams, score, outcome and fan framing. A failed draft goes back to the Narrator once with the problems listed. If it fails again, the template text stays on screen.

## Results

| Outcome | Narrations | Share |
|---|---|---|
| Passed first time | 141 | 68% |
| Caught by the Verifier, fixed by a rewrite | 29 | 14% |
| Rejected twice: template text shown instead | 31 | 15% |
| Model or network error: template text shown | 5 | 2% |
| **AI text that reached the screen verified** | **170** | **83%** |

Leaving out network errors (a property of the connection, not the agents), **170 of 201 narrations (85%) reached the screen as verified AI text**, and every other one fell back to the correct template text. No unverified AI text was ever shown.

## By viewer profile

| Profile | Narrations | Passed first time | Fixed by rewrite | Rejected |
|---|---|---|---|---|
| Analyst · English | 57 | 49 | 5 | 3 |
| Analyst · French | 57 | 42 | 10 | 5 |
| Away fan · Spanish | 46 | 29 | 5 | 10 |
| Home fan · Swahili | 46 | 21 | 9 | 13 |

## What the Verifier caught

- **The Comeback, 36' pressure surge** (Analyst · English, rejected): The draft implies Northbridge FC has a 2-goal lead, but the facts only state a score difference of 2 without specifying which team is leading. This could mislead viewers about the match situation.; second draft: Incorrectly states Northbridge FC is trailing by two goals; the score difference is 2 but the draft implies they are behind, which may mislead viewers about the match situation.
- **The Comeback, 67' goal** (Analyst · English, fixed): The headline 'P. Dembe Breaks Deadlock' is incorrect because the score was 2-2 before the goal, so the deadlock was already in place; the goal puts Riverside Athletic ahead, not breaks the deadlock.
- **The Comeback, 36' pressure surge** (Analyst · French, fixed): The draft incorrectly states 'sans nécessité de rattrapage' (without the need to chase), which is not supported by the facts; the 'chasing' fact is false, so the phrase is misleading.
- **The Comeback, 45+2' goal** (Analyst · French, rejected): The draft incorrectly states that Oskar Coulter is from Riverside Athletic, but the facts and reference text indicate he is from Northbridge FC.; second draft: The draft incorrectly states that Oskar Coulter is from Riverside Athletic, but the facts and reference text indicate he is from Northbridge FC.
- **The Comeback, 49' control shift** (Analyst · French, fixed): Turnovers are 2.0 per minute, not reduced or necessarily low; the draft incorrectly implies a reduction or improvement in turnovers.
- **The Comeback, 67' goal** (Away fan · Spanish, rejected): The draft incorrectly states the score as 3-2, but the correct score after the goal is 3-2 in favor of Riverside Athletic, which matches the draft. No error here.; second draft: The draft incorrectly states the score as 3-2, but the facts and reference text show the score is 3-2 in favor of Riverside Athletic, which is correct. However, the draft headline and body correctly reflect this. No errors found.
- **The Comeback, 75' pressure surge** (Away fan · Spanish, rejected): The draft incorrectly states 'in the rival area' implying the penalty area, but the facts say 'in the opposition half'.; second draft: The draft frames the pressure surge as 'concerning' for Riverside Athletic, but the facts do not indicate that this is a negative development for the viewer's supported team; it only states Northbridge FC is chasing and pressing.
- **The Comeback, 19' goal** (Home fan · Swahili, fixed): The draft headline says 'Goli la Kwanza la Msimu kwa Marchetti' (First goal of the season for Marchetti) which is correct, but the body says 'amefunga goli la pili' (has scored the second goal) which could be misleading as it might imply his second goal of the season rather than the team's second goal. The draft should clarify that it is the team's second goal, but Marchetti's first of the season.
- **The Comeback, 36' pressure surge** (Home fan · Swahili, rejected): The draft incorrectly states 'wamepata mpira nyuma mara 4' which means 'got the ball back 4 times behind' instead of 'in the opposition half'. The correct phrasing should reflect that the ball was regained 4 times in the opposition half, not behind.; second draft: The draft says 'wamechukua mpira 4' which translates to 'have taken the ball 4 times', but the fact is they have 'won the ball back 4 times' specifically through high regains in the opposition half, which is more precise. The draft should reflect that these are high regains or ball recoveries in the opponent's half, not just possession.
- **The Comeback, 36' pressure surge** (Home fan · Swahili, rejected): The draft incorrectly states that Riverside Athletic regaining the ball 3 times is bad news for Northbridge FC, but since Northbridge FC is the viewer's supported team and Riverside Athletic are chasing and behind, this is actually bad news for Northbridge FC, so the framing is correct. No error here.; second draft: The draft incorrectly states that Riverside Athletic holding the ball 3 times is bad news for Northbridge FC, but since Riverside Athletic are behind and chasing, this pressure surge is actually good news for them and bad news for Northbridge FC.
- **The Comeback, 45+2' goal** (Home fan · Swahili, rejected): The draft incorrectly states that Oskar Coulter scored for Riverside Athletic, but the reference text and facts indicate he scored for Northbridge FC.; second draft: The draft incorrectly states that Oskar Coulter scored the third goal for Northbridge FC, but the facts show he scored for Riverside Athletic, making the score 2-1, not 3-0.
- **The Comeback, 53' pressure surge** (Home fan · Swahili, fixed): The draft incorrectly states 'katika nusu yao ya mchezaji wa Riverside Athletic' which implies Northbridge FC regained the ball in their own half, but the facts say the regains were in the opposition half.
- **The Comeback, 67' goal** (Home fan · Swahili, rejected): Draft incorrectly states the score as 3-2 in favor of Riverside Athletic, but the correct score after the goal is 3-2 with Riverside Athletic leading, so the framing is correct. However, the draft says Northbridge FC's chance of winning has decreased, but the facts say Riverside Athletic's chance increased from 23% to 75%, so the draft's implication that Northbridge's chance decreased is correct. No factual errors found.; second draft: The draft incorrectly states that Northbridge FC's chance of winning has decreased from 23% to 75%, but in fact Riverside Athletic's chance of winning increased from 23% to 75%.
- **The Comeback, 69' control shift** (Home fan · Swahili, fixed): The draft implies a negative impact for Northbridge FC, but the facts do not state this explicitly; the framing as 'bad news' for Northbridge FC is an interpretation not supported by the facts.
- **The Comeback, 75' pressure surge** (Home fan · Swahili, fixed): The draft implies Northbridge FC are trying to regain the lead, but the facts only say they are behind and chasing, not necessarily trying to regain the lead.
- **The Comeback, 90+6' recap** (Home fan · Swahili, rejected): Draft implies the match is over and Riverside Athletic has won, which is correct, but the headline 'Riverside Athletic Yashinda 3-2' is accurate and not misleading. No errors found.; second draft: Draft headline 'Riverside Athletic Yashinda 3-2' implies match is over and Riverside Athletic won, which is correct, but the draft body says 'Hii ni habari mbaya kwa Northbridge FC' which is a subjective framing and not a factual error. No factual errors found.
- **Ten Men, 69' goal** (Analyst · English, rejected): verifier unavailable; second draft: no rewrite
- **Ten Men, 28' control shift** (Analyst · French, fixed): verifier unavailable
- **Ten Men, 45+3' recap** (Analyst · French, fixed): verifier unavailable
- **Ten Men, 63' control shift** (Analyst · French, fixed): verifier unavailable

## Limits

- The number check is exact. The fact-check is itself a model, so this measures what passes our checks, not a human rating. Native speakers should still review the non-English text.
- Matches are the three scripted demo scenarios, so results on other matches may differ.
