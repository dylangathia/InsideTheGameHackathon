# FootieManager: long description

Football fans want more than the scoreline: they want to know why a moment mattered, told in a way that suits them. FootieManager turns a live match into intelligence that explains itself, for every kind of fan.

Four AI agents, built on Microsoft Agent Framework with Microsoft Foundry, work as a broadcast crew:

- **The Narrator** writes every key moment from computed facts only, tailored to each viewer's mode, favourite club and language.
- **The Verifier** fact-checks every line before it reaches the screen and sends wrong drafts back to be rewritten. In testing it caught all 44 errors we planted, and 99% of AI text reached the screen verified.
- **The Analyst** answers fans' questions by choosing among live-data tools, and shows every step it took.
- **The Pundit** presents a half-time show. It picks the moments that decided the half and draws each move on the pitch with animated arrows, its analysis as the caption.

An Agent desk shows the agents handing work to each other as it happens, and a Sources panel shows exactly what each one was given.

Underneath, our own engine generates realistic synthetic matches with 5 Hz player tracking. A five-stage pipeline computes pass difficulty, shot speed, xG, live win probability and story indices such as control vs chaos. It also calls out milestones, and outputs a machine-readable overlay feed for broadcast graphics. Viewers can watch side by side in English, Spanish, French or Swahili. Every event streams into Microsoft Fabric for live analysis, and the app runs on Azure Container Apps, built and tested with GitHub Actions.
