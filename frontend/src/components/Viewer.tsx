import { useEffect, useState } from "react";
import type { FrameBuffer } from "../useMatchStream";
import type { AgentEvent, Show, Answer, Frame, MatchState, Meta, Mode, Overlay, Profile } from "../types";
import { LANGUAGES, LLM_LANGUAGES, METRICS, MODES } from "../types";
import { speak, stopSpeaking, useVoice } from "../speech";
import { AgentDesk } from "./AgentDesk";
import { Feed, Indices, MetricTracker, Momentum, PlayerCard, StatsTable, WinChance, WinProbChart } from "./Panels";
import { Stage } from "./Stage";

interface Props {
  index: number;
  label: string;
  meta: Meta;
  state: MatchState | null;
  frame: Frame | null;
  frames: React.MutableRefObject<FrameBuffer>;
  overlays: Overlay[];
  answers: Answer[];
  desk: AgentEvent[];
  show: Show | null;
  onShow: () => void;
  profile: Profile;
  onProfile: (p: Profile) => void;
  onReplay: (t: number) => void;
  onAsk: (q: string) => void;
  onFreeze: (t: number) => void;
  layout: "single" | "split";
  replaying: boolean;
}

const SHOW_LABELS_EN = {
  kicker: "Half-time show",
  pundit: "Pundit",
  second_half: "second half",
  back: "Back to the match",
  verified: "AI · verified",
};

const SUGGESTIONS: Record<Mode, string[]> = {
  analyst: ["Why did the momentum shift?", "Who leads on pressures?", "What's the xG?"],
  casual: ["What's the score?", "Who's been the best player?", "Why did that goal matter?"],
  player: ["How is my player doing?", "Who has run the furthest?", "Who is the fastest?"],
  metric: ["Who is the fastest?", "Who has run the furthest?", "What's the xG?"],
};

export function Viewer(props: Props) {
  const { meta, state, profile, onProfile, overlays } = props;
  const { home, away } = meta.match;
  const set = (patch: Partial<Profile>) => onProfile({ ...profile, ...patch });
  const goals = overlays.filter((o) => o.kind === "goal");
  const focusClub = profile.player?.startsWith(home.short + "-") ? home : away;
  const languages = meta.llm ? { ...LANGUAGES, ...LLM_LANGUAGES } : LANGUAGES;
  // Tactical breakdown: freeze the match at the shot and draw the move on the pitch.
  const [board, setBoard] = useState<Overlay | null>(null);
  // The Pundit's half-time show: freeze on each moment in turn, draw its breakdown, caption it with the pundit.
  const [showPending, setShowPending] = useState(false);
  const [run, setRun] = useState<{ show: Show; idx: number; resumeT: number } | null>(null);
  const htDone = !!state && meta.match.period_ends.length > 0 && state.t >= meta.match.period_ends[0];
  const requestShow = () => {
    setShowPending(true);
    props.onShow();
  };
  const goTo = (show: Show, idx: number, resumeT: number) => {
    setBoard(null);
    if (idx < show.segments.length) props.onFreeze(show.segments[idx].t);
    setRun({ show, idx, resumeT });
  };
  const endShow = () => {
    stopSpeaking();
    if (run) props.onFreeze(run.resumeT);
    setRun(null);
  };
  // Optional: the Pundit's words read aloud, only where the browser has a voice for this language.
  const voice = useVoice(profile.language);
  const [voiceOn, setVoiceOn] = useState(false);
  useEffect(() => {
    if (!props.show) return;
    setShowPending(false);
    goTo(props.show, 0, state?.t ?? 0);
    // a new show object means a new request; state.t is read once, when it starts
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.show]);
  useEffect(() => {
    if (!run) return;
    const seg = run.idx < run.show.segments.length ? run.show.segments[run.idx] : null;
    const speaking = voiceOn && !!voice;
    if (speaking) {
      // Let the arrows start drawing, then the pundit talks; the next moment follows when the voice finishes.
      // Each moment stays up at least 7 s, even if the speech engine fails or finishes instantly.
      let next: ReturnType<typeof setTimeout> | undefined;
      const shownAt = performance.now();
      const start = setTimeout(() => speak(seg ? seg.talk : run.show.closing, voice!, () => {
        const wait = Math.max(1500, 7000 - (performance.now() - shownAt));
        if (seg) next = setTimeout(() => goTo(run.show, run.idx + 1, run.resumeT), wait);
      }), 700);
      return () => {
        clearTimeout(start);
        if (next) clearTimeout(next);
        stopSpeaking();
      };
    }
    if (!seg) return;
    const ms = 6000 + (seg.breakdown?.steps.length ?? 0) * 650 + seg.talk.split(" ").length * 120;
    const timer = setTimeout(() => goTo(run.show, run.idx + 1, run.resumeT), ms);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, voiceOn]);
  const segment = run && run.idx < run.show.segments.length ? run.show.segments[run.idx] : null;
  const showView = run
    ? {
        title: run.show.title,
        idx: run.idx,
        total: run.show.segments.length,
        talk: segment?.talk ?? null,
        minute: segment?.minute ?? "",
        closing: segment ? null : run.show.closing,
        ai: run.show.source === "llm",
        onPrev: () => goTo(run.show, Math.max(0, run.idx - 1), run.resumeT),
        onNext: () => goTo(run.show, run.idx + 1, run.resumeT),
        onClose: endShow,
        voice: voice ? { on: voiceOn, name: voice.name, toggle: () => setVoiceOn((v) => !v) } : null,
        labels: run.show.labels ?? SHOW_LABELS_EN,
      }
    : null;

  const openBoard = (o: Overlay) => {
    if (!o.grounding?.breakdown) return;
    setBoard(o);
    props.onFreeze(o.grounding.breakdown.t_shot);
  };

  return (
    <section className="viewer" aria-label={props.label}>
      <div className="profile-bar">
        <span className="viewer-label">{props.label}</span>
        <label>
          Mode
          <select value={profile.mode} onChange={(e) => set({ mode: e.target.value as Mode })}>
            {Object.entries(MODES).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Language
          <select value={profile.language} onChange={(e) => set({ language: e.target.value })}>
            {Object.entries(languages).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Club
          <select value={profile.club ?? ""} onChange={(e) => set({ club: e.target.value || null })}>
            <option value="">Neutral</option>
            <option value={home.short}>{home.name}</option>
            <option value={away.short}>{away.name}</option>
          </select>
        </label>
        {profile.mode === "player" && (
          <label>
            Player
            <select value={profile.player ?? ""} onChange={(e) => set({ player: e.target.value || null })}>
              <option value="">Choose…</option>
              {[home, away].map((c) => (
                <optgroup key={c.short} label={c.name}>
                  {c.players.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.number} {p.name} ({p.position}){p.star ? " ★" : ""}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
        )}
        {profile.mode === "metric" && (
          <label>
            Metric
            <select value={profile.metric} onChange={(e) => set({ metric: e.target.value })}>
              {Object.entries(METRICS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {(() => {
        const stage = (
          <Stage
            meta={meta}
            state={state}
            frame={props.frame}
            frames={props.frames}
            overlays={overlays}
            profile={profile}
            replaying={props.replaying}
            board={segment ? segment.breakdown : (board?.grounding?.breakdown ?? null)}
            onCloseBoard={() => setBoard(null)}
            show={showView}
            onShow={htDone ? requestShow : undefined}
          />
        );
        if (!state) return stage;
        const feed =
          profile.mode === "analyst" ? (
            <Feed onBreakdown={openBoard} overlays={overlays} onReplay={props.onReplay} title="Commentary & key moments" />
          ) : profile.mode === "casual" ? (
            <Feed onBreakdown={openBoard} overlays={overlays.filter((o) => o.key || o.type === "ticker")} onReplay={props.onReplay} title="The story so far" />
          ) : profile.mode === "player" ? (
            <Feed
              onBreakdown={openBoard}
              overlays={overlays.filter((o) => (profile.player && o.players.includes(profile.player)) || o.kind === "goal" || o.type === "ticker")}
              onReplay={props.onReplay}
              title="Their match"
            />
          ) : (
            <Feed onBreakdown={openBoard} overlays={overlays} onReplay={props.onReplay} title="Moments" />
          );
        const ask = (
          <AskBox
            answers={props.answers}
            onAsk={props.onAsk}
            suggestions={SUGGESTIONS[profile.mode]}
            provider={meta.llm ? (meta.agent_framework ? `Agent Framework + ${meta.llm_provider}` : meta.llm_provider) : null}
            overlays={overlays}
            onReplay={props.onReplay}
          />
        );
        const desk = (
          <AgentDesk
            events={props.desk}
            framework={!!meta.agent_framework}
            onShow={htDone ? requestShow : undefined}
            showPending={showPending}
          />
        );
        const panels = (
          <>
            {profile.mode === "analyst" && (
              <>
                <WinProbChart state={state} home={home} away={away} goals={goals} />
                <Indices state={state} home={home} away={away} />
                <StatsTable state={state} home={home} away={away} />
              </>
            )}
            {profile.mode === "casual" && (
              <>
                <WinChance state={state} home={home} away={away} />
                <div className="card">
                  <Momentum value={state.indices.momentum} home={home} away={away} big />
                </div>
              </>
            )}
            {profile.mode === "player" && (
              <PlayerCard p={profile.player ? state.players[profile.player] : undefined} club={focusClub} />
            )}
            {profile.mode === "metric" && <MetricTracker metric={profile.metric} state={state} home={home} away={away} />}
          </>
        );
        // Single view: broadcast layout, with the live feed and Ask beside the pitch so it all fits one screen.
        if (props.layout === "single") {
          return (
            <>
              <div className="viewer-main">
                {stage}
                <aside className="rail">
                  {feed}
                  {desk}
                  {ask}
                </aside>
              </div>
              <div className={`panels panels-${profile.mode}`}>{panels}</div>
            </>
          );
        }
        return (
          <>
            {stage}
            <div className={`panels panels-${profile.mode}`}>
              {panels}
              {feed}
              {desk}
              {ask}
            </div>
          </>
        );
      })()}
    </section>
  );
}

/** Moment ids belong in the citation chips, not the prose: drops "[i42]", "(i326, i482)" and bare "i42". */
const stripIds = (text: string) =>
  text
    .replace(/\s*[[(]\s*i\d+(?:\s*[,;]\s*i\d+)*\s*[\])]/g, "")
    .replace(/\s*\bi\d+\b/g, "")
    .replace(/\s+([.,;:])/g, "$1");

function AskBox({ answers, onAsk, suggestions, provider, overlays, onReplay }: {
  answers: Answer[];
  onAsk: (q: string) => void;
  suggestions: string[];
  provider: string | null;
  overlays: Overlay[];
  onReplay: (t: number) => void;
}) {
  // Cited moments, looked up from this viewer's own overlays so they read in the viewer's language.
  const byInsight = new Map(overlays.filter((o) => o.key).map((o) => [o.insight_id, o]));
  const [q, setQ] = useState("");
  const submit = (text: string) => {
    if (!text.trim()) return;
    onAsk(text.trim());
    setQ("");
  };
  return (
    <div className="card ask">
      <div className="card-head">
        <span>Ask the match</span>
        <span className="hint">{provider ? `an AI agent (${provider}) that queries the live match` : "rule-based answers (add AI keys in .env)"}</span>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(q);
        }}
      >
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Why did they concede?" aria-label="Question" />
        <button type="submit">Ask</button>
      </form>
      <div className="chips">
        {suggestions.map((s) => (
          <button key={s} className="chip" onClick={() => submit(s)}>
            {s}
          </button>
        ))}
      </div>
      <ol className="answers">
        {[...answers].reverse().map((a, i) => (
          <li key={i}>
            <div className="q">{a.question}</div>
            <div className="a">
              {stripIds(a.answer)}
              {(a.source === "llm" || a.source === "agent") && <span className="ai-badge">AI</span>}
              {a.source === "agent_framework" && (
                <span className="ai-badge" title="The match_analyst agent on Microsoft Agent Framework, using Microsoft Foundry">
                  AI · Agent Framework
                </span>
              )}
            </div>
            {a.steps && a.steps.length > 0 && (
              <ol className="agent-steps" aria-label="What the agent looked up">
                <span>Agent looked up:</span>
                {a.steps.map((st, j) => (
                  <li key={j} className="num">
                    {st}
                  </li>
                ))}
              </ol>
            )}
            {(a.cites.length > 0 || a.as_of) && (
              <div className="cites">
                {a.as_of && <span>Based on the match up to {a.as_of}</span>}
                {a.cites
                  .map((c) => byInsight.get(c))
                  .filter((o): o is Overlay => !!o)
                  .map((o) => (
                    <button key={o.id} className="chip" onClick={() => onReplay(o.t)} title="Replay this moment">
                      {o.minute} {o.text.headline}
                    </button>
                  ))}
              </div>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
