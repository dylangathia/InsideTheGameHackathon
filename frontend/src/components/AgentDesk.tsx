import type { AgentEvent } from "../types";

const AGENTS: { id: AgentEvent["agent"]; name: string; role: string }[] = [
  { id: "narrator", name: "Narrator", role: "writes each key moment from the facts" },
  { id: "verifier", name: "Verifier", role: "fact-checks every draft before it airs" },
  { id: "analyst", name: "Analyst", role: "answers questions with live match tools" },
  { id: "pundit", name: "Pundit", role: "presents the half-time show" },
];

const ACTIVE_MS = 4000;

/** The agents' handoffs as they happen: who did what, and what the Verifier caught. */
export function AgentDesk({ events, framework, onShow, showPending }: {
  events: AgentEvent[];
  framework: boolean;
  onShow?: () => void;
  showPending?: boolean;
}) {
  const now = performance.now();
  const recent = [...events].reverse().slice(0, 5);
  return (
    <div className="card desk">
      <div className="card-head">
        <span>Agent desk</span>
        <span className="hint">{framework ? "live handoffs · Microsoft Agent Framework" : "live handoffs"}</span>
      </div>
      {onShow && (
        <button className="show-btn" onClick={onShow} disabled={showPending}>
          {showPending ? "The Pundit is preparing the half-time show…" : "▶ Half-time show, presented by the Pundit"}
        </button>
      )}
      <div className="desk-roster">
        {AGENTS.map((a) => {
          const busy = events.some((e) => e.agent === a.id && e.receivedAt !== undefined && now - e.receivedAt < ACTIVE_MS);
          return (
            <span key={a.id} className={`desk-agent desk-${a.id} ${busy ? "busy" : ""}`} title={`${a.name}: ${a.role}`}>
              <i />
              {a.name}
            </span>
          );
        })}
      </div>
      {recent.length === 0 ? (
        <div className="panel-empty">The agents report here as they work on goals, big chances and your questions.</div>
      ) : (
        <ol className="desk-log">
          {recent.map((e) => (
            <li key={e.seq} className={`desk-${e.agent} act-${e.action.replace(" ", "-")}`} title={e.detail}>
              <span className="feed-min">{e.minute}</span>
              <b>{AGENTS.find((a) => a.id === e.agent)?.name ?? e.agent}</b>
              <span className="desk-action">{e.action}</span>
              <span className="desk-detail">{e.detail}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
