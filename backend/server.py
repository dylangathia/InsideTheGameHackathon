"""FootieManager API: streams a live synthetic match through the five-stage pipeline.

Run:  uvicorn server:app --reload --port 8000     (from the backend folder)

WebSocket /ws/match/{scenario}
  client -> server
    {"type": "hello", "viewers": [Profile, ...], "speed": 10}
    {"type": "profiles", "viewers": [Profile, ...]}
    {"type": "control", "action": "play" | "pause"}
    {"type": "speed", "value": 20}
    {"type": "seek", "t": 2700}
    {"type": "ask", "viewer": 0, "question": "Why did they concede?"}
  server -> client
    meta, frame (10/s), state (2/s), overlay, overlay_text (LLM upgrade),
    history (after profile change or seek), answer, status
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from footie.i18n import LANGUAGES, LLM_ONLY_LANGUAGES  # noqa: E402
from footie.pipeline import orchestration  # noqa: E402
from footie.pipeline.agent import ask_agent  # noqa: E402
from footie.pipeline.pundit import build_show  # noqa: E402
from footie.pipeline.explain import Narrator  # noqa: E402
from footie.pipeline.ingest import FabricEventstreamSink  # noqa: E402
from footie.pipeline.personalize import METRICS, MODES, Profile  # noqa: E402
from footie.pipeline.runner import MatchSession  # noqa: E402
from footie.sim.scenarios import SCENARIOS, load_match  # noqa: E402

logging.basicConfig(level=logging.INFO)
logging.getLogger("azure").setLevel(logging.WARNING)  # the Event Hubs client logs every AMQP link change
log = logging.getLogger("footie")

app = FastAPI(title="FootieManager", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

NARRATOR = Narrator()
LLM_PROVIDER = NARRATOR.llm.provider if NARRATOR.llm else None
AGENT_FRAMEWORK = orchestration.enabled(NARRATOR.llm)
FABRIC_ENABLED = bool(os.getenv("FABRIC_EVENTSTREAM_CONNECTION_STRING"))
# One Fabric connection for the whole server. A sink per session leaked a connection and a thread on every seek.
FABRIC_SINK = FabricEventstreamSink.from_env()
TICK = 0.1  # seconds of wall time per server tick


@app.on_event("startup")
async def warm_cache() -> None:
    """Build (or load from disk) every scenario in the background so the first viewer doesn't wait."""
    async def warm():
        for sid in SCENARIOS:
            await run_in_threadpool(load_match, sid)
            log.info("scenario %s ready", sid)
    asyncio.create_task(warm())


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "llm": NARRATOR.enabled, "llm_provider": LLM_PROVIDER, "agent_framework": AGENT_FRAMEWORK,
            "fabric": FABRIC_ENABLED}


@app.get("/api/scenarios")
def scenarios() -> list[dict]:
    return [s.summary() for s in SCENARIOS.values()]


@app.get("/api/options")
def options() -> dict:
    langs = dict(LANGUAGES)
    if NARRATOR.enabled:
        langs.update(LLM_ONLY_LANGUAGES)
    return {"modes": MODES, "metrics": METRICS, "languages": langs, "llm": NARRATOR.enabled}


@app.get("/api/match/{scenario}/meta")
async def match_meta(scenario: str) -> dict:
    m = await _load(scenario)
    return m.metadata()


@app.get("/api/match/{scenario}/events.jsonl", response_class=PlainTextResponse)
async def match_events(scenario: str) -> str:
    m = await _load(scenario)
    return "\n".join(json.dumps(e) for e in m.events)


async def _load(scenario: str):
    if scenario not in SCENARIOS:
        raise HTTPException(404, f"unknown scenario {scenario}")
    return await run_in_threadpool(load_match, scenario)


def _meta_message(scenario: str, m) -> dict:
    meta = m.metadata()
    meta.pop("anchors", None)
    return {
        "type": "meta",
        "scenario": SCENARIOS[scenario].summary(),
        "match": meta,
        "llm": NARRATOR.enabled,
        "llm_provider": LLM_PROVIDER,
        "agent_framework": AGENT_FRAMEWORK,
        "fabric": FABRIC_ENABLED,
    }


SHOWS: dict[tuple, dict] = {}  # half-time shows by (scenario, profile): the first half never changes


class Connection:
    """One browser connection: a shared match clock and 1-2 viewer profiles."""

    def __init__(self, ws: WebSocket, scenario: str):
        self.ws = ws
        self.scenario = scenario
        self.lock = asyncio.Lock()
        self.viewers: list[Profile] = [Profile()]
        self.playing = True
        self.speed = 10.0
        self.session: MatchSession | None = None
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.tasks: set[asyncio.Task] = set()
        self.desk_seq = 0

    async def send(self, msg: dict) -> None:
        async with self.lock:
            await self.ws.send_text(json.dumps(msg, ensure_ascii=False))

    async def send_quietly(self, msg: dict) -> None:
        """For background updates (the agent desk): the viewer may have left by the time they arrive."""
        try:
            await self.send(msg)
        except Exception:
            pass

    def spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def deliver(self, overlays: list[dict]) -> None:
        s = self.session
        for ov in overlays:
            ins = s.insights[ov["insight_id"]]
            for vi, prof in enumerate(self.viewers):
                p = s.personalize(ov, prof)
                if not p:
                    continue
                await self.send({"type": "overlay", "viewer": vi, "overlay": p})
                if NARRATOR.wants(ins):
                    self.spawn(self.upgrade(vi, prof, ins, p))

    def desk(self, vi: int):
        """A callback the agents call as they act; each step goes to the browser's agent desk.

        Agent Framework may run tools on a worker thread, so the send is handed to the event loop thread-safely.
        """
        loop = asyncio.get_running_loop()

        def send_step(agent: str, action: str, detail: str) -> None:
            self.desk_seq += 1
            self.spawn(self.send_quietly({"type": "agent", "viewer": vi, "event": {
                "seq": self.desk_seq, "agent": agent, "action": action, "detail": detail,
                "minute": self.session.analyzer.label() if self.session else ""}}))

        def on_step(agent: str, action: str, detail: str = "") -> None:
            loop.call_soon_threadsafe(send_step, agent, action, detail)
        return on_step

    async def upgrade(self, vi: int, prof: Profile, ins: dict, p: dict) -> None:
        text = await NARRATOR.rewrite(ins, prof, self.session.ctx, p["text"], on_step=self.desk(vi))
        if text:
            await self.send({"type": "overlay_text", "viewer": vi, "id": p["id"], "text": text})

    async def halftime_show(self, vi: int, prof: Profile) -> None:
        """The Pundit's half-time show, from a session stopped at the half-time whistle."""
        key = (self.scenario, prof.mode, prof.language, prof.club, prof.player, prof.metric)
        on_step = self.desk(vi)
        show = SHOWS.get(key)
        if show is None:
            m = self.session.match
            ht = MatchSession(m)  # no Fabric sink: these events were already streamed
            await run_in_threadpool(ht.advance_to, m.period_ends[0] + 0.5)
            show = await build_show(NARRATOR.llm, ht, prof, on_step=on_step)
            if show["source"] == "llm":
                SHOWS[key] = show
        else:
            for step in show.get("trace", []):
                on_step(*step)
        await self.send({"type": "show", "viewer": vi, "show": show})

    async def send_history(self) -> None:
        s = self.session
        for vi, prof in enumerate(self.viewers):
            items = []
            for ov in s.overlays:
                ins = s.insights[ov["insight_id"]]
                if not (ins["key"] or ins["kind"] == "ticker"):
                    continue
                p = s.personalize(ov, prof)
                if p:
                    items.append(p)
            await self.send({"type": "history", "viewer": vi, "overlays": items[-80:]})

    async def status(self) -> None:
        await self.send({"type": "status", "playing": self.playing, "speed": self.speed,
                         "t": round(self.session.t, 1), "duration": self.session.match.duration})

    async def reset_to(self, t: float) -> None:
        m = await _load(self.scenario)
        session = MatchSession(m)  # catch up without the sink: those events were already streamed
        await run_in_threadpool(session.advance_to, max(0.0, t))
        session.feed.sink = FABRIC_SINK  # from here on, new events stream to Fabric
        self.session = session
        await self.send_history()
        await self.send({"type": "state", "state": session.state()})

    async def handle(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "profiles":
            self.viewers = [Profile.from_dict(v) for v in msg.get("viewers", [{}])][:2]
            await self.send_history()
        elif kind == "control":
            self.playing = msg.get("action") == "play"
        elif kind == "speed":
            self.speed = max(0.5, min(120.0, float(msg.get("value", 10))))
        elif kind == "seek":
            await self.reset_to(float(msg.get("t", 0)))
        elif kind == "show":
            vi = int(msg.get("viewer", 0))
            if self.session.match.period_ends:
                self.spawn(self.halftime_show(vi, self.viewers[vi] if vi < len(self.viewers) else Profile()))
        elif kind == "ask":
            vi = int(msg.get("viewer", 0))
            prof = self.viewers[vi] if vi < len(self.viewers) else Profile()
            question = str(msg.get("question", ""))[:500]
            as_of = self.session.state()["minute"]
            ans = None
            if NARRATOR.enabled:
                try:
                    ans = await ask_agent(NARRATOR.llm, question, self.session, prof, on_step=self.desk(vi))
                except Exception as exc:  # fall back to the single-shot answer below
                    log.warning("agent failed, falling back: %s", exc)
            if ans is None:
                ans = await NARRATOR.answer(question, self.session.ask_context(prof), prof, self.session.ctx)
            await self.send({"type": "answer", "viewer": vi, "question": question, "as_of": as_of, **ans})
            if ans.get("source") in ("agent", "agent_framework"):
                self.desk(vi)("analyst", "answered", question)
        await self.status()

    async def reader(self) -> None:
        while True:
            msg = await self.ws.receive_json()
            await self.inbox.put(msg)

    async def run(self) -> None:
        hello = await self.ws.receive_json()
        self.viewers = [Profile.from_dict(v) for v in hello.get("viewers", [{}])][:2] or [Profile()]
        self.speed = float(hello.get("speed", 10))
        m = await _load(self.scenario)
        await self.send(_meta_message(self.scenario, m))
        self.session = MatchSession(m, FABRIC_SINK)
        await self.status()
        reader = asyncio.create_task(self.reader())
        n = 0
        loop = asyncio.get_running_loop()
        last = loop.time()
        try:
            while True:
                while not self.inbox.empty():
                    await self.handle(self.inbox.get_nowait())
                if reader.done():
                    reader.result()  # re-raise disconnects
                now = loop.time()
                dt, last = now - last, now
                s = self.session
                if self.playing and s.t < s.match.duration:
                    overlays = s.advance_to(s.t + dt * self.speed)
                    await self.deliver(overlays)
                    if s.t >= s.match.duration:
                        self.playing = False
                        await self.status()
                frame = s.frame()
                if frame:
                    await self.send({"type": "frame", **frame})
                if n % 5 == 0:
                    await self.send({"type": "state", "state": s.state()})
                n += 1
                await asyncio.sleep(max(0.0, TICK - (loop.time() - now)))
        finally:
            reader.cancel()
            for t in list(self.tasks):
                t.cancel()


@app.websocket("/ws/match/{scenario}")
async def ws_match(ws: WebSocket, scenario: str) -> None:
    await ws.accept()
    if scenario not in SCENARIOS:
        await ws.close(code=4404)
        return
    conn = Connection(ws, scenario)
    try:
        await conn.run()
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("connection failed")
        try:
            await ws.close(code=1011)
        except Exception:
            pass


# Serve the built front end (frontend/dist) when present, e.g. in the container image.
_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
