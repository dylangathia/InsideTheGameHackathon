import { useEffect, useRef } from "react";
import type { FrameBuffer } from "../useMatchStream";
import type { Club } from "../types";

// View box in metres: the 105 x 68 pitch plus a 3 m margin.
export const VIEW = { x0: -3, y0: -3, w: 111, h: 74 };

/** What the canvas is looking at: centre in pitch metres and zoom (1 = whole pitch). */
export interface Camera {
  cx: number;
  cy: number;
  z: number;
}
export const FULL_VIEW: Camera = { cx: VIEW.x0 + VIEW.w / 2, cy: VIEW.y0 + VIEW.h / 2, z: 1 };

/** Pitch metres -> percentage position inside the stage (y grows upwards on the pitch). */
export function toPct(x: number, y: number, cam: Camera = FULL_VIEW) {
  return { left: (((x - cam.cx) * cam.z) / VIEW.w + 0.5) * 100, top: (((cam.cy - y) * cam.z) / VIEW.h + 0.5) * 100 };
}

interface Props {
  frames: React.MutableRefObject<FrameBuffer>;
  home: Club;
  away: Club;
  focusPlayer: string | null;
  favClub: string | null;
  playerCam: boolean;
  camera: React.MutableRefObject<Camera>;
}

const FRAME_MS = 100;
const CAM_ZOOM = 2.2;
const TRAIL_SECONDS = 10;
const SPRINT_MS = 7; // 25.2 km/h

// Same formula as backend/footie/football_models.py pass_difficulty, so the cam agrees with the analytics.
function passDifficulty(distance: number, pressure: number, progress: number, long: boolean) {
  const z = -3 + 0.055 * distance + 1.6 * pressure + 0.02 * Math.max(0, progress) + (long ? 0.4 : 0);
  return Math.min(0.99, Math.max(0.01, 1 / (1 + Math.exp(-z))));
}

function distToSegment(px: number, py: number, ax: number, ay: number, bx: number, by: number) {
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy || 1;
  const t = ((px - ax) * dx + (py - ay) * dy) / len2;
  const cx = ax + t * dx;
  const cy = ay + t * dy;
  return { d: Math.hypot(px - cx, py - cy), t };
}

export function Pitch({ frames, home, away, focusPlayer, favClub, playerCam, camera }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const props = useRef({ home, away, focusPlayer, favClub, playerCam });
  props.current = { home, away, focusPlayer, favClub, playerCam };

  useEffect(() => {
    const el = canvas.current!;
    const ctx = el.getContext("2d")!;
    let raf = 0;
    const resize = () => {
      const r = el.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      el.width = Math.round(r.width * dpr);
      el.height = Math.round(r.height * dpr);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    // Player-cam memory: the focused player's recent path and smoothed velocity.
    let trail: { t: number; x: number; y: number }[] = [];
    let trailFor: string | null = null;
    let lastFrameT = -1;
    let vel = { x: 0, y: 0 };

    const draw = () => {
      raf = requestAnimationFrame(draw);
      const { home, away, focusPlayer, favClub, playerCam } = props.current;
      const { prev, cur, at } = frames.current;
      const a = Math.min(1, (performance.now() - at) / FRAME_MS);
      const prevPos = new Map(prev?.players.map((p) => [p[0], p]) ?? []);
      const pos = new Map<string, { x: number; y: number }>();
      for (const [pid, x1, y1] of cur?.players ?? []) {
        const p0 = prevPos.get(pid);
        pos.set(pid, p0 ? { x: p0[1] + (x1 - p0[1]) * a, y: p0[2] + (y1 - p0[2]) * a } : { x: x1, y: y1 });
      }
      const ball = cur
        ? prev
          ? { x: prev.ball[0] + (cur.ball[0] - prev.ball[0]) * a, y: prev.ball[1] + (cur.ball[1] - prev.ball[1]) * a }
          : { x: cur.ball[0], y: cur.ball[1] }
        : null;
      const clubOf = (pid: string) => (pid.startsWith(home.short + "-") ? home : away);
      const isHome = (pid: string) => pid.startsWith(home.short + "-");
      const focus = focusPlayer ? pos.get(focusPlayer) : undefined;
      const camOn = playerCam && !!focus;

      // New frame: update the focused player's trail and velocity (match time, so it works at any speed).
      if (cur && cur.t !== lastFrameT) {
        if (focusPlayer !== trailFor || cur.t < lastFrameT) {
          trail = [];
          trailFor = focusPlayer;
          vel = { x: 0, y: 0 };
        }
        const pNow = focusPlayer ? cur.players.find((p) => p[0] === focusPlayer) : undefined;
        const pPrev = focusPlayer ? prev?.players.find((p) => p[0] === focusPlayer) : undefined;
        if (pNow && pPrev && prev && cur.t > prev.t) {
          const dt = cur.t - prev.t;
          vel = { x: vel.x * 0.5 + ((pNow[1] - pPrev[1]) / dt) * 0.5, y: vel.y * 0.5 + ((pNow[2] - pPrev[2]) / dt) * 0.5 };
        }
        if (pNow) trail.push({ t: cur.t, x: pNow[1], y: pNow[2] });
        trail = trail.filter((p) => cur.t - p.t <= TRAIL_SECONDS);
        lastFrameT = cur.t;
      }

      // Camera: glide towards the focused player (or back to the full pitch), clamped to the pitch.
      const cam = camera.current;
      const target = camOn ? { cx: focus!.x, cy: focus!.y, z: CAM_ZOOM } : FULL_VIEW;
      cam.z += (target.z - cam.z) * 0.08;
      cam.cx += (target.cx - cam.cx) * 0.1;
      cam.cy += (target.cy - cam.cy) * 0.1;
      const halfW = VIEW.w / (2 * cam.z);
      const halfH = VIEW.h / (2 * cam.z);
      cam.cx = Math.min(VIEW.x0 + VIEW.w - halfW, Math.max(VIEW.x0 + halfW, cam.cx));
      cam.cy = Math.min(VIEW.y0 + VIEW.h - halfH, Math.max(VIEW.y0 + halfH, cam.cy));

      const s0 = el.width / VIEW.w;
      const S = s0 * cam.z; // pixels per metre for geometry
      const ms = s0 * Math.min(cam.z, 1.6); // pixels per metre for markers and text, so zooming doesn't make them huge
      const X = (x: number) => (x - cam.cx) * S + el.width / 2;
      const Y = (y: number) => (cam.cy - y) * S + el.height / 2;
      drawPitch(ctx, el.width, el.height, X, Y, S);
      if (!cur) return;

      const labels: (() => void)[] = [];
      if (camOn && focusPlayer && focus) {
        const mine = isHome(focusPlayer);
        const attack = mine ? 1 : -1;
        const opponents = [...pos].filter(([pid]) => isHome(pid) !== mine);
        const mates = [...pos].filter(([pid]) => isHome(pid) === mine && pid !== focusPlayer);
        const speed = Math.hypot(vel.x, vel.y);

        // Trail: where they have been in the last 10 seconds.
        for (let i = 1; i < trail.length; i++) {
          const age = (cur.t - trail[i].t) / TRAIL_SECONDS;
          ctx.strokeStyle = `rgba(255,181,71,${0.75 * (1 - age)})`;
          ctx.lineWidth = 0.45 * ms * (1 - age * 0.6);
          ctx.beginPath();
          ctx.moveTo(X(trail[i - 1].x), Y(trail[i - 1].y));
          ctx.lineTo(X(trail[i].x), Y(trail[i].y));
          ctx.stroke();
        }

        // Vision cone: the way they are moving, or towards goal when standing still.
        const dir = speed > 1 ? Math.atan2(vel.y, vel.x) : attack > 0 ? 0 : Math.PI;
        const R = 22;
        const half = (35 * Math.PI) / 180;
        const grad = ctx.createRadialGradient(X(focus.x), Y(focus.y), 0, X(focus.x), Y(focus.y), R * S);
        grad.addColorStop(0, "rgba(255,181,71,0.28)");
        grad.addColorStop(1, "rgba(255,181,71,0)");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(X(focus.x), Y(focus.y));
        ctx.arc(X(focus.x), Y(focus.y), R * S, -dir - half, -dir + half); // canvas y is flipped
        ctx.closePath();
        ctx.fill();

        // Pressure: nearest opponent and the gap to them.
        let nearest: { x: number; y: number; d: number } | null = null;
        for (const [, o] of opponents) {
          const d = Math.hypot(o.x - focus.x, o.y - focus.y);
          if (!nearest || d < nearest.d) nearest = { ...o, d };
        }

        // Pass options, when they have the ball: one line per teammate, coloured by difficulty.
        // In the tracking data the ball can run a few metres ahead of the dribbler, so "has the ball" means
        // closest player to it and within 3.5 m.
        let closest: string | null = null;
        if (ball) {
          let best = Infinity;
          for (const [pid, p] of pos) {
            const d = Math.hypot(p.x - ball.x, p.y - ball.y);
            if (d < best) [best, closest] = [d, pid];
          }
        }
        const hasBall = !!ball && closest === focusPlayer && Math.hypot(ball.x - focus.x, ball.y - focus.y) < 3.5;
        if (hasBall) {
          const pressure = nearest ? Math.min(1, Math.max(0, (6 - nearest.d) / 6)) : 0;
          for (const [, m] of mates) {
            const dist = Math.hypot(m.x - focus.x, m.y - focus.y);
            if (dist > 45) continue;
            let diff = passDifficulty(dist, pressure, (m.x - focus.x) * attack, dist > 32);
            // An opponent standing in the passing lane makes it much harder.
            if (opponents.some(([, o]) => {
              const seg = distToSegment(o.x, o.y, focus.x, focus.y, m.x, m.y);
              return seg.d < 1.8 && seg.t > 0.1 && seg.t < 0.95;
            })) diff = Math.min(0.99, diff + 0.25);
            const color = diff < 0.3 ? "76,211,138" : diff < 0.55 ? "255,181,71" : "255,93,93";
            ctx.strokeStyle = `rgba(${color},0.85)`;
            ctx.lineWidth = 0.32 * ms;
            ctx.setLineDash([]);
            ctx.beginPath();
            ctx.moveTo(X(focus.x), Y(focus.y));
            ctx.lineTo(X(m.x), Y(m.y));
            ctx.stroke();
            const lx = focus.x + (m.x - focus.x) * 0.6;
            const ly = focus.y + (m.y - focus.y) * 0.6;
            labels.push(() => pill(ctx, X(lx), Y(ly), `${Math.round(diff * 100)}`, `rgb(${color})`, ms));
          }
        }

        if (nearest && nearest.d < 12) {
          const pressed = nearest.d < 3;
          ctx.strokeStyle = pressed ? "rgba(255,93,93,0.9)" : "rgba(255,255,255,0.5)";
          ctx.lineWidth = 0.22 * ms;
          ctx.setLineDash([0.6 * ms, 0.5 * ms]);
          ctx.beginPath();
          ctx.moveTo(X(focus.x), Y(focus.y));
          ctx.lineTo(X(nearest.x), Y(nearest.y));
          ctx.stroke();
          ctx.setLineDash([]);
          const n = nearest;
          // When the opponent is close, the midpoint sits on top of the player, so put the label below them.
          const [lx, ly] = n.d < 5 ? [X(focus.x), Y(focus.y) + 3.4 * ms] : [X((focus.x + n.x) / 2), Y((focus.y + n.y) / 2)];
          labels.push(() => pill(ctx, lx, ly, `${pressed ? "PRESSED " : ""}${n.d.toFixed(1)} m`, pressed ? "#ff5d5d" : "#cfd8e5", ms));
        }

        // Live speed next to the player; it lights up when they sprint.
        const kmh = speed * 3.6;
        const sprinting = speed > SPRINT_MS;
        labels.push(() =>
          pill(ctx, X(focus.x) + 3.2 * ms, Y(focus.y) - 2.6 * ms, `${sprinting ? "SPRINT " : ""}${kmh.toFixed(1)} km/h`,
            sprinting ? "#ffb547" : "#e8edf4", ms, sprinting),
        );
      }

      const numberOf = (pid: string) => pid.split("-")[1];
      const order = [...pos.keys()].sort((p, q) => Number(p === focusPlayer) - Number(q === focusPlayer));
      for (const pid of order) {
        const { x, y } = pos.get(pid)!;
        const club = clubOf(pid);
        const focused = pid === focusPlayer;
        const dim = favClub && club.short !== favClub && !focused;
        const r = (focused ? 1.7 : 1.25) * ms;
        ctx.globalAlpha = dim ? 0.6 : 1;
        if (focused) {
          ctx.beginPath();
          ctx.arc(X(x), Y(y), r + 0.7 * ms, 0, Math.PI * 2);
          ctx.strokeStyle = "#ffb547";
          ctx.lineWidth = 0.35 * ms;
          ctx.stroke();
        }
        ctx.beginPath();
        ctx.arc(X(x), Y(y), r, 0, Math.PI * 2);
        ctx.fillStyle = club.primary;
        ctx.fill();
        ctx.lineWidth = 0.25 * ms;
        ctx.strokeStyle = club.secondary;
        ctx.stroke();
        ctx.fillStyle = club.secondary;
        ctx.font = `600 ${(focused ? 1.5 : 1.15) * ms}px "IBM Plex Mono", monospace`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(numberOf(pid), X(x), Y(y) + 0.05 * ms);
      }
      ctx.globalAlpha = 1;

      if (ball) {
        ctx.beginPath();
        ctx.arc(X(ball.x), Y(ball.y), 0.65 * ms, 0, Math.PI * 2);
        ctx.fillStyle = "#ffffff";
        ctx.shadowColor = "rgba(0,0,0,0.6)";
        ctx.shadowBlur = 0.8 * ms;
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.lineWidth = 0.15 * ms;
        ctx.strokeStyle = "#111";
        ctx.stroke();
      }
      for (const drawLabel of labels) drawLabel();
    };
    draw();
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [frames, camera]);

  return <canvas ref={canvas} className="pitch-canvas" aria-label="Live pitch view" />;
}

/** A small rounded label drawn on the canvas. */
function pill(ctx: CanvasRenderingContext2D, x: number, y: number, text: string, color: string, ms: number, glow = false) {
  ctx.font = `600 ${0.95 * ms}px "IBM Plex Mono", monospace`;
  const w = ctx.measureText(text).width + 0.9 * ms;
  const h = 1.5 * ms;
  ctx.fillStyle = "rgba(10,14,22,0.88)";
  if (glow) {
    ctx.shadowColor = color;
    ctx.shadowBlur = 0.9 * ms;
  }
  ctx.beginPath();
  ctx.roundRect(x - w / 2, y - h / 2, w, h, 0.35 * ms);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.fillStyle = color;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, x, y + 0.05 * ms);
}

function drawPitch(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  X: (x: number) => number,
  Y: (y: number) => number,
  s: number,
) {
  ctx.fillStyle = "#24543a";
  ctx.fillRect(0, 0, w, h);
  const stripes = 14;
  for (let i = 0; i < stripes; i++) {
    if (i % 2) continue;
    ctx.fillStyle = "#2a5f42";
    ctx.fillRect(X((105 / stripes) * i), Y(68), (105 / stripes) * s, 68 * s);
  }
  ctx.strokeStyle = "rgba(255,255,255,0.82)";
  ctx.lineWidth = 0.18 * s;
  const rect = (x: number, y: number, rw: number, rh: number) => ctx.strokeRect(X(x), Y(y + rh), rw * s, rh * s);
  rect(0, 0, 105, 68);
  ctx.beginPath();
  ctx.moveTo(X(52.5), Y(0));
  ctx.lineTo(X(52.5), Y(68));
  ctx.stroke();
  const circle = (x: number, y: number, r: number, a0 = 0, a1 = Math.PI * 2, fill = false) => {
    ctx.beginPath();
    ctx.arc(X(x), Y(y), r * s, a0, a1);
    fill ? ctx.fill() : ctx.stroke();
  };
  circle(52.5, 34, 9.15);
  ctx.fillStyle = "rgba(255,255,255,0.82)";
  circle(52.5, 34, 0.3, 0, Math.PI * 2, true);
  for (const left of [true, false]) {
    const gx = left ? 0 : 105;
    const dir = left ? 1 : -1;
    rect(left ? 0 : 105 - 16.5, 34 - 20.16, 16.5, 40.32);
    rect(left ? 0 : 105 - 5.5, 34 - 9.16, 5.5, 18.32);
    circle(gx + dir * 11, 34, 0.3, 0, Math.PI * 2, true);
    const ang = Math.acos(5.5 / 9.15);
    if (left) circle(11, 34, 9.15, -ang, ang);
    else circle(94, 34, 9.15, Math.PI - ang, Math.PI + ang);
    ctx.strokeRect(left ? X(-2) : X(105), Y(34 + 3.66), 2 * s, 7.32 * s);
  }
}
