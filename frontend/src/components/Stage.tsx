import { useRef, useState } from "react";
import type { FrameBuffer } from "../useMatchStream";
import type { Breakdown, Frame, MatchState, Meta, Overlay, Profile } from "../types";
import { type Camera, FULL_VIEW, Pitch, toPct } from "./Pitch";

interface Props {
  meta: Meta;
  state: MatchState | null;
  frame: Frame | null;
  frames: React.MutableRefObject<FrameBuffer>;
  overlays: Overlay[];
  profile: Profile;
  replaying?: boolean;
  board?: Breakdown | null;
  onCloseBoard?: () => void;
}

/** Overlays stay on screen for `ttl` seconds of wall time after they arrive, so they stay readable at 10x. */
function isActive(o: Overlay, now: number) {
  return o.receivedAt !== undefined && now - o.receivedAt < o.ttl * 1000;
}

export function Stage({ meta, state, frame, frames, overlays, profile, replaying, board, onCloseBoard }: Props) {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [camOn, setCamOn] = useState(true);
  const camera = useRef<Camera>({ ...FULL_VIEW });
  const focusInfo = profile.player
    ? [meta.match.home, meta.match.away].flatMap((c) => c.players).find((p) => p.id === profile.player)
    : undefined;
  const playerCam = profile.mode === "player" && !!focusInfo && camOn;
  const now = performance.now();
  const active = overlays.filter((o) => o.ttl > 0 && isActive(o, now) && !dismissed.has(o.id));
  const pick = (type: Overlay["type"], n: number) =>
    active
      .filter((o) => o.type === type)
      .sort((a, b) => b.priority - a.priority || b.t - a.t)
      .slice(0, n);

  const lower = pick("key_moment", 1)[0];
  const small = lower ? [] : [...pick("pass_card", 1), ...pick("shot_card", 1)].sort((a, b) => b.t - a.t).slice(0, 2);
  const alert = pick("index_alert", 1)[0];
  const tags = pick("player_tag", 4);
  const panel = pick("stat_panel", 1)[0];
  const recap = pick("recap", 1)[0];
  const { home, away } = meta.match;
  const positions = new Map(frame?.players.map((p) => [p[0], p]) ?? []);
  const dismiss = (id: string) => setDismissed((d) => new Set(d).add(id));

  // A goal that just arrived makes the stage flash in the scoring team's colour for a moment.
  const freshGoal = overlays.find((o) => o.kind === "goal" && o.receivedAt !== undefined && now - o.receivedAt < 2500);
  const flashColor = freshGoal?.side ? meta.match[freshGoal.side].primary : undefined;

  return (
    <div
      className={`stage ${freshGoal ? "goal-flash" : ""} ${playerCam ? "cam-on" : ""}`}
      style={flashColor ? ({ "--flash": flashColor } as React.CSSProperties) : undefined}
    >
      <Pitch
        frames={frames}
        home={home}
        away={away}
        focusPlayer={profile.player}
        favClub={profile.club}
        playerCam={playerCam}
        camera={camera}
        board={board ?? null}
      />

      {board && (
        <aside className={`board-panel ${boardSide(board) === "left" ? "left" : ""}`} aria-label="Tactical breakdown">
          <div className="board-kicker">Breakdown · {board.team}</div>
          <div className="board-head">{board.headline}</div>
          <ol className="board-steps">
            {board.steps.map((st) => (
              <li key={st.n} className={`board-step board-${st.kind}`}>
                <span className="board-n">{st.n}</span>
                <span>
                  <strong>{st.label}</strong>
                  {st.detail ? <em> · {st.detail}</em> : null}
                  <span className="board-who">
                    {st.player}
                    {st.to ? ` → ${st.to}` : ""}
                  </span>
                </span>
              </li>
            ))}
          </ol>
          {board.shape && (
            <p className="board-shape">
              <strong>{board.shape.team}</strong> ({board.shape.formation}) defending: back line {board.shape.back_line_m} m
              from goal, {board.shape.box.defenders} defenders v {board.shape.box.attackers} attacker
              {board.shape.box.attackers === 1 ? "" : "s"} in the box.
            </p>
          )}
          <button onClick={onCloseBoard}>Close breakdown</button>
        </aside>
      )}

      {profile.mode === "player" && focusInfo && (
        <div className="cam-hud">
          <span className="cam-tag">{playerCam ? "Player cam" : "Full pitch"}</span>
          <strong>
            #{focusInfo.number} {focusInfo.short}
          </strong>
          {playerCam && (
            <span className="cam-legend" aria-label="Pass option colours">
              <i className="easy" /> easy <i className="risky" /> risky <i className="hard" /> hard pass
            </span>
          )}
          <button onClick={() => setCamOn(!camOn)} aria-pressed={playerCam}>
            {playerCam ? "Full pitch" : "Player cam"}
          </button>
        </div>
      )}

      {replaying && (
        <div className="replay-banner" role="status">
          Replay · 2×
        </div>
      )}

      {state && (
        <div className={`scorebug ${freshGoal ? "pulse" : ""}`} role="status">
          <span className="sb-team" style={{ background: home.primary, color: home.secondary }}>{home.short}</span>
          <span className="sb-score">
            {state.score.home}–{state.score.away}
          </span>
          <span className="sb-team" style={{ background: away.primary, color: away.secondary }}>{away.short}</span>
          <span className="sb-clock">{state.finished ? "FT" : state.minute}</span>
        </div>
      )}

      {!board && tags.map((o) => {
        const pid = o.anchor.player_id;
        const p = pid ? positions.get(pid) : undefined;
        if (!p) return null;
        const pos = toPct(p[1], p[2], camera.current);
        if (pos.left < 2 || pos.left > 98 || pos.top < 4 || pos.top > 100) return null; // off-screen while zoomed
        return (
          <div key={o.id} className={`tag tag-${o.kind}`} style={{ left: `${pos.left}%`, top: `${pos.top}%` }}>
            <strong>{o.text.headline}</strong>
            <span>{o.text.body}</span>
          </div>
        );
      })}

      {!board && alert && (
        <div className="alert" key={alert.id}>
          <div className="alert-kicker">{alert.minute}</div>
          <div className="alert-head">{alert.text.headline}</div>
          {alert.text.body && <div className="alert-body">{alert.text.body}</div>}
          <AiBadge o={alert} />
        </div>
      )}

      {panel && profile.mode === "analyst" && panel.rows && (
        <div className="panel" key={panel.id}>
          <div className="panel-head">{panel.text.headline}</div>
          <StatRows rows={panel.rows} home={home.short} away={away.short} />
        </div>
      )}

      {!board && lower && (
        <div className={`lower lower-${lower.kind}`} key={lower.id}>
          <div className="lower-bar" style={{ background: lower.side ? meta.match[lower.side].primary : "#ffb547" }} />
          <div className="lower-main">
            <div className="lower-head">
              {lower.text.headline}
              {lower.text.sub && <span className="lower-sub">{lower.text.sub}</span>}
            </div>
            {lower.text.body && <div className="lower-body">{lower.text.body}</div>}
            {lower.text.why && lower.text.why.length > 0 && (
              <ul className="lower-why">
                {lower.text.why.slice(0, profile.mode === "analyst" ? 4 : 3).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </div>
          <AiBadge o={lower} />
        </div>
      )}

      {!board && small.length > 0 && (
        <div className="smalls">
          {small.map((o) => (
            <div className="small" key={o.id}>
              <div className="small-head">{o.text.headline}</div>
              <div className="small-body">{o.text.body}</div>
            </div>
          ))}
        </div>
      )}

      {recap && (
        <div className="recap" onClick={() => dismiss(recap.id)} title="Click to close">
          <div className="recap-card">
            <div className="recap-kicker">{recap.text.headline}</div>
            <div className="recap-score">{recap.text.sub}</div>
            <p>{recap.text.body}</p>
            {recap.rows && <StatRows rows={recap.rows} home={home.short} away={away.short} />}
            <AiBadge o={recap} />
          </div>
        </div>
      )}
    </div>
  );
}

function StatRows({ rows, home, away }: { rows: (string | number)[][]; home: string; away: string }) {
  return (
    <table className="stat-rows">
      <thead>
        <tr>
          <th />
          <th>{home}</th>
          <th>{away}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={String(r[0])}>
            <td>{r[0]}</td>
            <td>{r[1]}</td>
            <td>{r[2]}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** The caption panel goes on the side away from the move, so it never covers the arrows. */
export function boardSide(board: Breakdown): "left" | "right" {
  const xs = board.steps.flatMap((st) => [st.x, st.end_x]).filter((v): v is number => v !== null);
  const centre = xs.length ? (Math.min(...xs) + Math.max(...xs)) / 2 : 52.5;
  return centre > 52.5 ? "left" : "right";
}

export function AiBadge({ o }: { o: Overlay }) {
  if (o.text.source !== "llm") return null;
  const verified = o.text.verification && o.text.verification.status !== "unchecked";
  return verified ? (
    <span className="ai-badge verified" title="Written by the Narrator agent, fact-checked by the Verifier agent against the computed facts">
      AI · verified
    </span>
  ) : (
    <span className="ai-badge" title="Written by the AI model from the computed facts">
      AI
    </span>
  );
}
