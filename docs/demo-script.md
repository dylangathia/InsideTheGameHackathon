# Demo video script: "FootieManager Deep Dive" (1 minute 55 seconds)

A developer deep dive, the style of a game studio's feature video: the team on camera for one line each, then
straight into the app. The rules say the video must be **under 2 minutes** (judges can stop at 2:00), must show the
app actually running, must be in **English**, and must not use copyrighted music. Upload it publicly to YouTube or
Vimeo.

We entered **Best Multi-Agent System**, so each section is one agent at work.

## Ground rules

- **The app is the star.** Keep at least three quarters of the video on the screen recording. Faces are 3–6 second
  bridges between sections, never longer.
- **Our own look only.** No music, footage, logos or graphic style from EA, the Premier League or any broadcaster.
  Royalty-free music (e.g. the YouTube Audio Library) or none.
- **Faces:** a window or lamp in front of you, camera at eye level, a quiet room, the phone's or laptop's mic close
  to you. Bad audio hurts more than no face at all.
- **Voice-over:** the person on camera for a section also talks over its screen footage, so the voices stay
  consistent. Record the voice-over separately if that is easier, and lay it over the footage in editing.
- **Presenters: Rico and Liz.** Dylan isn't on camera; he's credited on the closing card with the rest of the team.
- **Name captions** the first time each person appears: name and role (e.g. "Rico · developer").

## Before recording the screen

- Use the live Azure app (https://footiemanager.lemonisland-55346052.eastus2.azurecontainerapps.io) or your local
  one (port 8010). The badges at the top should say **Foundry on** and **Fabric on**.
- Record at 1600 × 900 or larger, so overlay text is readable.
- **Rehearse every take once before recording it.** AI text and the half-time show are cached on the server, and on
  a repeat the Agent desk replays the exact steps that produced them. So the rehearsal "warms up" each moment: if the
  Verifier caught something in rehearsal, the recording shows the same catch, instantly. (Restarting the server
  clears the cache.)
- Open these links in separate tabs:
  - **A (the opener, split screen):** `/?scenario=comeback&t=400&speed=2`
  - **B (the Verifier's catch, then a question):** `/?scenario=comeback&t=4100&speed=1&split=0`
  - **C (the half-time show):** `/?scenario=comeback&t=2870&speed=1&split=0`
- Have a KQL query ready in Fabric (from `docs/fabric.md`), e.g. shots and goals by team.
- Add English subtitles whenever Spanish or Swahili text is on screen.

## Script

Section cards are short full-screen titles (white on dark, 1 second) before each section.

| Time | Section card | On camera (one line) | Screen | Voice-over over the screen |
|---|---|---|---|---|
| 0:00–0:08 | *FootieManager · Deep Dive* | **Rico:** "We built a live match desk run by four AI agents. Let's show you how it works." | Tab A, split screen, match playing | (none, the line on camera covers it) |
| 0:08–0:30 | **THE NARRATOR** | **Liz:** "Every goal gets explained, and differently for every fan." | Tab A: the 8' goal lands on both sides, the ★ ribbon "K. Thorne reaches 50 goals for Northbridge FC", the **AI · verified** text, then click **Sources** on the left | "Same goal, two viewers: an analyst on the left, a Riverside fan in Spanish on the right, told it's bad news. The Narrator writes from computed facts only, even Thorne's fiftieth goal for the club, and Sources shows exactly what it was given." |
| 0:30–0:52 | **THE VERIFIER** | **Liz:** "Nothing goes on air unchecked." | Tab B: the 67' goal, hold on the **Agent desk**: Narrator drafted "Breaks Deadlock" → Verifier flagged → Narrator rewrote → Verifier passed. Overlay card: **44 / 44 planted errors caught** | "Here the Narrator called it 'breaks the deadlock', but it was two-all. The Verifier caught it and sent it back, and only the fixed line aired. We tested it by planting 44 errors: it caught every one." |
| 0:52–1:07 | **ASK THE MATCH** | (no face) | Tab B: type "How did Riverside turn this around?" The desk shows the Analyst's lookups, then the answer and its steps | **Liz:** "Fans can ask the match anything. The Analyst agent picks which live-data tools to use, and shows its working." |
| 1:07–1:37 | **THE HALF-TIME SHOW** | **Rico:** "I wanted those half-time breakdowns you get on TV, with the arrows." | Tab C: click **▶ Half-time show** on the desk; the desk shows the Pundit looking things up and the Verifier passing the script. Moment 1/3: arrows draw the move with the Pundit's caption. Press ▶ for moment 2 | **Rico:** "So the Pundit agent presents one. It only looks at the first half, picks the moments that decided it, and pulls each move's breakdown. Once the Verifier signs off, every pass and run is drawn on the pitch." |
| 1:37–1:47 | **UNDER THE HOOD** | (no face) | Fabric KQL query, then click **How it works** in the app (the four agents and the Microsoft stack) | **Rico:** "Four agents on Microsoft Agent Framework and Foundry, every event streaming into Fabric, running on Azure Container Apps." |
| 1:47–1:55 | Closing card: *FootieManager* + repo link + the team: Dylan, Rico, Liz | **Rico and Liz, together:** "FootieManager." | The app behind the end card | (none) |

## Tips

- AI text appears a second or two after the template text; cut the waits in editing.
- The Verifier's catch at 67' depends on what the Narrator writes and doesn't happen every time. If the rehearsal
  shows no catch, rehearse that goal again in another language (Language: Swahili or Spanish usually gives one), and
  change the line to "every line is fact-checked before it airs" over a clean pass.
- The half-time show takes about 10–15 seconds to prepare the first time; after the rehearsal it starts instantly.
- Rehearse with a timer. If you're over 1:55, shorten Ask the match first, then the Narrator section.
- Optional, only if there's time: Player focus → 11 Pavel Dembe at `/?scenario=comeback&t=3266&speed=0.5&split=0`
  (Player Cam), or 5 seconds of `docs/media/auto-eventing.mp4` ("we even recover events from video"). Never at the
  expense of the agents.
