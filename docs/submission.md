# Submission text (for the Projects page)

Copy the sections below into the hackathon form at aka.ms/insidethegame. Replace the bracketed links before submitting.

## Project name

FootieManager

## Category

Best Multi-Agent System

## Elevator pitch

FootieManager is a live match desk run by three cooperating AI agents built on Microsoft Agent Framework, with Microsoft Foundry (gpt-4.1-mini) as their model. It turns a synthetic football match into intelligence that explains itself, then personalises it for every viewer.

**Three agents, distinct roles, one shared match state.**
- The **Narrator agent** writes on-screen narration and recaps from the computed facts only.
- The **Verifier agent** fact-checks every line before it airs. Software checks each number against the facts, and an AI check at temperature 0 covers players, teams, score, outcome and fan framing.
- The **"Ask the match" agent** answers viewers by choosing among six read-only tools over the live match (state, player stats, rankings, key moments, trends, event counts), and shows each step it took.

**Handoffs and recovery.** The Narrator and Verifier are wired together as an Agent Framework workflow: a rejected draft goes back to the Narrator once, with the Verifier's list of problems. If it fails again, the system recovers by showing correct template text, so unverified AI text never reaches the screen. The agent falls back to a simpler answer, then to rules, if a model call fails. Across 206 narrations in four languages, the Verifier caught and fixed 14% of drafts (for example, "breaks the deadlock" for a goal that made it 3-2, and a Swahili draft that called a player's first goal of the season his second). 85% reached the screen as verified AI text, with the rest falling back to template text (docs/evaluation.md). Every key moment has a Sources panel showing what the agents were given and what the Verifier fixed.

**What the agents work on.** Our own match engine generates realistic event streams with 5 Hz tracking of all 22 players and the ball. A five-stage pipeline ingests events as they happen, interprets them (pass difficulty, ball and shot speed, sprints, xG, live win probability, and three story indices: control vs chaos, pressure and rhythm), explains why each moment matters (including season and career milestones such as a striker's 50th goal for the club), renders a timed, machine-readable overlay feed, and personalises it. An analyst and a casual fan of the other club watch the same match side by side and get genuinely different experiences, in English, Spanish, French or Swahili. In Player focus, a Player Cam follows one player with their speed, trail, vision cone, the pressure on them, and every pass option scored by difficulty. Every event also streams into Microsoft Fabric for live KQL analysis. For the brief's auto-eventing item, computer vision over a rendered video feed recovers 99% of passes with distances within 1.2 m, measured against the synthetic ground truth (docs/auto-eventing.md; not yet tested on real footage).

**Problem it solves:** broadcasters and streaming platforms need match intelligence that is fast, trustworthy and tailored to each audience. A single AI writer can't be verified and treats every fan the same. Here one agent writes, another checks, and a third answers questions from live data.

## Microsoft and Azure technologies used

- **Microsoft Agent Framework**: the Narrator, Verifier and "Ask the match" analyst are Agent Framework agents. Narrator → Verifier is an Agent Framework workflow with a one-rewrite loop, and the analyst's six read-only match tools run through the framework's tool-calling loop
- **Microsoft Foundry**, Azure OpenAI gpt-4.1-mini: the model behind all three agents
- **Microsoft Fabric** Real-Time Intelligence: Eventstream custom endpoint to an Eventhouse (KQL database) with live match events
- **GitHub**: public repository, GitHub Actions CI (tests and front-end build)
- **Azure Container Apps**: the live demo runs as a container on Azure Container Apps, built by GitHub Actions and published to GitHub Container Registry on every push to `main`

## Links

- Code: https://github.com/dylangathia/InsideTheGameHackathon
- Demo video: [YouTube/Vimeo link]
- Live demo: https://footiemanager.lemonisland-55346052.eastus2.azurecontainerapps.io/

## Testing instructions

**Live demo:** open https://footiemanager.lemonisland-55346052.eastus2.azurecontainerapps.io/. Pick a match at the top and press Play. Use **Split screen** to compare two viewers, and change each viewer's mode, language and club. Click **Sources** on any key moment. Type a question into **Ask the match**.

**Run locally** (Python 3.11+, Node 20+):

```
git clone https://github.com/dylangathia/InsideTheGameHackathon
cd InsideTheGameHackathon/backend && pip install -r requirements.txt && uvicorn server:app --port 8000
cd ../frontend && npm install && npm run build      # then open http://localhost:8000
```

It runs without any keys, using template narration and rule-based answers. To enable Foundry and Fabric, copy `backend/.env.example` to `backend/.env` and fill in the values. `docker compose up --build` also works.
