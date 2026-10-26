# Submission text (for the Projects page)

Copy the sections below into the hackathon form at aka.ms/insidethegame. Replace the bracketed links before submitting.

## Project name

FootieManager

## Category

Best Use of Microsoft Foundry Project

## Elevator pitch

FootieManager turns a live, synthetic football match into intelligence that explains itself, then personalises it for every viewer. Our own match engine generates realistic event streams with 5 Hz player tracking. A five-stage pipeline ingests events as they happen, interprets them (pass difficulty, ball and shot speed, player sprints, xG, live win probability, and three story indices: control vs chaos, pressure and rhythm), explains why each moment matters through auditable reason codes, renders a timed, machine-readable overlay feed any broadcast graphics engine can draw, and personalises it. An analyst and a casual fan of the other club watch the same match side by side and get genuinely different experiences, in English, Spanish, French or Swahili.

Microsoft Foundry (gpt-4.1-mini) writes the on-screen narration from computed facts only, and every key moment has a Sources panel showing exactly what the model was given. "Ask the match" is a Foundry agent that chooses among six tools over the live match and shows each step it took. Every event streams into Microsoft Fabric (Eventstream to Eventhouse) for live KQL analysis.

**Problem it solves:** broadcasters and streaming platforms need match intelligence that is fast, trustworthy and tailored to each audience. Generic AI commentary can't be verified and treats every fan the same. FootieManager's insights are grounded and auditable, and personalised by design.

## Microsoft and Azure technologies used

- **Microsoft Foundry**, Azure OpenAI gpt-4.1-mini: grounded narration and recaps, plus the tool-calling "Ask the match" agent
- **Microsoft Fabric** Real-Time Intelligence: Eventstream custom endpoint to an Eventhouse (KQL database) with live match events
- **GitHub**: public repository, GitHub Actions CI (tests and front-end build)
- **Azure Container Apps**: [delete this line if not deployed] containerised deployment from the included Dockerfile

## Links

- Code: https://github.com/dylangathia/InsideTheGameHackathon
- Demo video: [YouTube/Vimeo link]
- Live demo: [Azure Container Apps URL, or delete]

## Testing instructions

**Live demo:** open [URL]. Pick a match at the top and press Play. Use **Split screen** to compare two viewers, and change each viewer's mode, language and club. Click **Sources** on any key moment. Type a question into **Ask the match**.

**Run locally** (Python 3.11+, Node 20+):

```
git clone https://github.com/dylangathia/InsideTheGameHackathon
cd InsideTheGameHackathon/backend && pip install -r requirements.txt && uvicorn server:app --port 8000
cd ../frontend && npm install && npm run build      # then open http://localhost:8000
```

It runs without any keys, using template narration and rule-based answers. To enable Foundry and Fabric, copy `backend/.env.example` to `backend/.env` and fill in the values. `docker compose up --build` also works.
