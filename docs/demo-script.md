# Demo video script (1 minute 55 seconds)

The rules say the video must be **under 2 minutes** (judges can stop at 2:00), must show the app actually running, must be in **English**, and must not use copyrighted music. Upload it publicly to YouTube or Vimeo.

We entered **Best Multi-Agent System**, so the video leads with the four agents working together: the Narrator, the Verifier, the Ask-the-match Analyst and the Pundit, all on Microsoft Agent Framework with Microsoft Foundry.

## Before recording

- Use the live Azure app (https://footiemanager.lemonisland-55346052.eastus2.azurecontainerapps.io) or your local one (port 8010). The badges at the top should say **Foundry on** and **Fabric on**.
- Record at 1600 × 900 or larger, so overlay text is readable.
- **Rehearse every take once before recording it.** AI text and the half-time show are cached on the server, and on a repeat the Agent desk replays the exact steps that produced them. So the rehearsal "warms up" each moment: if the Verifier caught something in rehearsal, the recording shows the same catch, instantly. (Restarting the server clears the cache.)
- Open these links in separate tabs:
  - **A (the opener, split screen):** `/?scenario=comeback&t=400&speed=2`
  - **B (the Verifier's catch, then a question):** `/?scenario=comeback&t=4100&speed=1&split=0`
  - **C (the half-time show):** `/?scenario=comeback&t=2870&speed=1&split=0`
- Have a KQL query ready in Fabric (from `docs/fabric.md`), e.g. shots and goals by team.
- Add English subtitles whenever Spanish or Swahili text is on screen.

## Script

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:08 | Tab A, split screen, match playing | "FootieManager is a live match desk run by four AI agents, built on Microsoft Agent Framework and Foundry. It turns a match into intelligence that explains itself, for every kind of fan." |
| 0:08–0:28 | The 8' goal lands on both sides: the ★ ribbon "K. Thorne reaches 50 goals for Northbridge FC", then the **AI · verified** text. Click **Sources** on the left | "Same goal, two viewers: an analyst on the left, a Riverside fan in Spanish on the right, told it's bad news. The Narrator agent writes from computed facts only, including Thorne's fiftieth goal for the club. Sources shows exactly what it was given." |
| 0:28–0:48 | Tab B. The 67' goal arrives; hold on the **Agent desk**: Narrator drafted "Breaks Deadlock" → Verifier flagged → Narrator rewrote → Verifier passed | "Nothing airs unchecked. Here the Narrator called it 'breaks the deadlock', but it was two-all. The Verifier agent caught it and sent it back, and only the corrected line went on air. In our sabotage test it caught all 44 errors we planted." |
| 0:48–1:03 | Still Tab B: type in Ask the match "How did Riverside turn this around?" The desk shows the Analyst's lookups, then the answer with its steps | "Fans can ask the match anything. The Analyst agent decides which live-data tools to call, and shows every step." |
| 1:03–1:35 | Tab C: click **▶ Half-time show** on the desk. The desk shows the Pundit's lookups and the Verifier's pass. Moment 1/3: arrows draw the move, the Pundit's caption. Press ▶ for moment 2 | "At half-time, the Pundit agent presents the show. It looks back only at the first half, picks the moments that decided it, and pulls each move's tactical breakdown. The Verifier checks the script, then every pass and run is drawn on the pitch, like a studio analyst." |
| 1:35–1:45 | Cut to the KQL query in Fabric | "Every event streams into Microsoft Fabric, so analysts can query the match live." |
| 1:45–1:55 | Click **How it works** (the four agents and the Microsoft stack) | "Four agents, one shared match state, every word checked. FootieManager: built on Agent Framework, Foundry, Fabric, Azure Container Apps and GitHub." |

## Tips

- AI text appears a second or two after the template text, so pause briefly before moving on. Cut any waits in editing.
- The Verifier's catch at 67' depends on what the Narrator writes, and it doesn't happen every time. If the rehearsal shows no catch, rehearse that goal again in another language (Language: Swahili or Spanish usually gives one), or use the line "every line is fact-checked before it airs" over a clean pass.
- The half-time show takes about 10–15 seconds to prepare the first time; after the rehearsal it starts instantly.
- Rehearse once with a timer. If you're over 1:55, shorten the Ask segment first.
- Optional, only if there's time to spare: Player focus → 11 Pavel Dembe at `/?scenario=comeback&t=3266&speed=0.5&split=0` (Player Cam), or 5 seconds of `docs/media/auto-eventing.mp4` ("we even recover events from video"). Never at the expense of the agents.
