import { useState } from "react";
import type { FrameBuffer } from "../useMatchStream";
import type { Answer, Frame, MatchState, Meta, Mode, Overlay, Profile } from "../types";
import { LANGUAGES, LLM_LANGUAGES, METRICS, MODES } from "../types";
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
  profile: Profile;
  onProfile: (p: Profile) => void;
  onReplay: (t: number) => void;
  onAsk: (q: string) => void;
  onFreeze: (t: number) => void;
  layout: "single" | "split";
  replaying: boolean;
}

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
            board={board?.grounding?.breakdown ?? null}
            onCloseBoard={() => setBoard(null)}
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
