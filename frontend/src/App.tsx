import { useEffect, useState } from "react";
import { FirstVisitTips, HowItWorks } from "./components/HowItWorks";
import { Viewer } from "./components/Viewer";
import type { Profile } from "./types";
import { useMatchStream } from "./useMatchStream";

interface ScenarioSummary {
  id: string;
  title: string;
  description: string;
  home: string;
  away: string;
}

const SPEEDS = [1, 5, 10, 20, 60];

const DEFAULT_VIEWERS: Profile[] = [
  { mode: "analyst", language: "en", club: null, player: null, metric: "speed" },
  { mode: "casual", language: "es", club: null, player: null, metric: "speed" },
];

// Deep links for demos: ?scenario=red_card&t=3400&speed=5&split=0
const params = new URLSearchParams(location.search);

export default function App() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [scenario, setScenario] = useState(params.get("scenario") ?? "comeback");
  const [split, setSplit] = useState(params.get("split") !== "0");
  const [profiles, setProfiles] = useState<Profile[]>(DEFAULT_VIEWERS);
  const viewers = split ? profiles : profiles.slice(0, 1);
  const { meta, state, frame, frames, status, views, send, connected } = useMatchStream(
    scenario,
    viewers,
    Number(params.get("speed") ?? 5),
  );
  const [scrub, setScrub] = useState<number | null>(null);
  const [jumped, setJumped] = useState(false);
  const [showHow, setShowHow] = useState(false);

  useEffect(() => {
    const t = params.get("t");
    if (connected && meta && t && !jumped) {
      send({ type: "seek", t: Number(t) });
      setJumped(true);
    }
  }, [connected, meta, jumped, send]);

  useEffect(() => {
    fetch("/api/scenarios")
      .then((r) => r.json())
      .then(setScenarios)
      .catch(() => setScenarios([]));
  }, []);

  // Give the second viewer a favourite club (the away side) when a match loads, for the demo.
  useEffect(() => {
    if (!meta) return;
    setProfiles((ps) => {
      const shorts = [meta.match.home.short, meta.match.away.short];
      return ps.map((p, i) => ({
        ...p,
        club: p.club && shorts.includes(p.club) ? p.club : i === 1 ? meta.match.away.short : null,
        player: p.player && p.player.split("-")[0] && shorts.includes(p.player.split("-")[0]) ? p.player : null,
      }));
    });
  }, [meta?.match.match_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const duration = meta?.match.duration ?? 5700;
  const t = scrub ?? state?.t ?? 0;
  const playing = status?.playing ?? true;
  const speed = status?.speed ?? 10;

  const clockLabel = (secs: number) => {
    const p2 = meta?.match.period_starts[1] ?? 2800;
    const m = secs >= p2 ? 45 + (secs - p2) / 60 : secs / 60;
    return `${Math.floor(m)}'`;
  };
  // Replays play 8 s before the moment at 2x, show a banner, and restore the previous speed afterwards.
  const [replayInfo, setReplayInfo] = useState<{ end: number; prevSpeed: number; armed: boolean } | null>(null);
  const replay = (at: number) => {
    setReplayInfo({ end: at + 6, prevSpeed: replayInfo ? replayInfo.prevSpeed : speed, armed: false });
    send({ type: "seek", t: Math.max(0, at - 8) });
    send({ type: "speed", value: 2 });
    send({ type: "control", action: "play" });
  };
  useEffect(() => {
    if (!replayInfo || !state) return;
    // Wait until the seek has landed (time before the end) before watching for the end of the replay.
    if (!replayInfo.armed && state.t < replayInfo.end - 1) setReplayInfo({ ...replayInfo, armed: true });
    else if (replayInfo.armed && state.t >= replayInfo.end) {
      send({ type: "speed", value: replayInfo.prevSpeed });
      setReplayInfo(null);
    }
  }, [state?.t]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden>
            ◢
          </span>
          FootieManager
          <span className="brand-sub">Inside the Game</span>
        </div>
        <label className="scenario">
          <span className="sr-only">Match</span>
          <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
            {(scenarios.length ? scenarios : [{ id: "comeback", title: "The Comeback", home: "", away: "", description: "" }]).map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
                {s.home ? `: ${s.home} v ${s.away}` : ""}
              </option>
            ))}
          </select>
        </label>
        <div className="controls">
          <button onClick={() => send({ type: "control", action: playing ? "pause" : "play" })} className="btn-primary">
            {playing ? "Pause" : "Play"}
          </button>
          <label>
            Speed
            <select value={speed} onChange={(e) => send({ type: "speed", value: Number(e.target.value) })}>
              {SPEEDS.includes(speed) ? null : <option value={speed}>{speed}×</option>}
              {SPEEDS.map((s) => (
                <option key={s} value={s}>
                  {s}×
                </option>
              ))}
            </select>
          </label>
          <button onClick={() => setSplit(!split)} aria-pressed={split}>
            {split ? "Single view" : "Split screen"}
          </button>
        </div>
        <button onClick={() => setShowHow(true)}>How it works</button>
        <div className="badges">
          <span className={`badge ${connected ? "on" : "off"}`}>{connected ? "Live" : "Connecting…"}</span>
          <span className={`badge ${meta?.llm ? "on" : "off"}`} title="AI model for narration and Q&A">
            {meta?.llm_provider ?? "AI"} {meta?.llm ? "on" : "off"}
          </span>
          <span className={`badge ${meta?.fabric ? "on" : "off"}`} title="Events forwarded to a Fabric Eventstream">
            Fabric {meta?.fabric ? "on" : "off"}
          </span>
        </div>
      </header>

      <div className="timeline">
        <span className="num">{clockLabel(t)}</span>
        <input
          type="range"
          min={0}
          max={duration}
          step={5}
          value={t}
          onChange={(e) => setScrub(Number(e.target.value))}
          onPointerUp={() => {
            if (scrub !== null) send({ type: "seek", t: scrub });
            setScrub(null);
          }}
          onKeyUp={() => {
            if (scrub !== null) send({ type: "seek", t: scrub });
            setScrub(null);
          }}
          aria-label="Match time"
        />
        <span className="num">{clockLabel(duration)}</span>
      </div>

      {meta?.scenario && <p className="scenario-desc">{meta.scenario.description}</p>}
      <FirstVisitTips onHow={() => setShowHow(true)} />
      {showHow && <HowItWorks onClose={() => setShowHow(false)} />}

      {!meta ? (
        <div className="loading">Building the match… (first run simulates and caches it, about 10 seconds)</div>
      ) : (
        <main className={`viewers ${split ? "split" : "single"}`}>
          {viewers.map((p, i) => (
            <Viewer
              key={i}
              index={i}
              label={split ? (i === 0 ? "Viewer A" : "Viewer B") : "Viewer"}
              meta={meta}
              state={state}
              frame={frame}
              frames={frames}
              overlays={views[i]?.overlays ?? []}
              answers={views[i]?.answers ?? []}
              profile={p}
              onProfile={(np) => setProfiles((ps) => ps.map((x, j) => (j === i ? np : x)))}
              onReplay={replay}
              onAsk={(q) => send({ type: "ask", viewer: i, question: q })}
              onFreeze={(at) => {
                send({ type: "seek", t: at });
                send({ type: "control", action: "pause" });
              }}
              layout={split ? "split" : "single"}
              replaying={!!replayInfo}
            />
          ))}
        </main>
      )}
    </div>
  );
}
