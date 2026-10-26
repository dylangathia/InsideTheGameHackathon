"""Auto-eventing: computer vision over a match video feed, scored against ground truth.

The brief suggests "running a model over an incoming video feed to generate the
pass and speed metrics automatically, rather than tagging them by hand". Our
matches are synthetic, which gives us something real footage can't: the exact
truth of every event. So we can measure how accurate the vision is.

    Camera    renders the tracking data as a top-down video feed (10 fps) with
              realistic degradations: sensor noise, blur, camera shake, lighting
              drift, dropped frames and a ball that is sometimes hidden.
    Detector  finds players (by kit colour) and the ball (small round white blob)
              from the pixels alone; it never sees the tracking data.
    Events    tracks the ball, splits its movement into flights, and infers passes
              (with distance, ball speed and outcome) and shots (with shot speed).
    Evaluate  matches detected events to the true events in the same window.

Limits: a clean top-down render is far easier than broadcast footage (camera
pans, perspective, crowds, occlusion), and this is classic computer vision, not
a trained model. It demonstrates and measures the method; it is not a claim of
real-footage accuracy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from ..sim.simulator import SimulatedMatch, to_frame

PX_PER_M = 8
MARGIN_M = 3
W = int((105 + 2 * MARGIN_M) * PX_PER_M)
H = int((68 + 2 * MARGIN_M) * PX_PER_M)
FPS = 10
PLAYER_R = 7  # px
BALL_R = 3  # px
FLIGHT_MS = 8.0  # ball faster than this (m/s) is a pass or shot; dribbles top out around 7


def to_px(x: float, y: float) -> tuple[int, int]:
    return int(round((x + MARGIN_M) * PX_PER_M)), int(round((68 + MARGIN_M - y) * PX_PER_M))


def to_m(px: float, py: float) -> tuple[float, float]:
    return px / PX_PER_M - MARGIN_M, 68 + MARGIN_M - py / PX_PER_M


def hex_bgr(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return b, g, r


# ---------------------------------------------------------------------------------------------- camera
class Camera:
    """Turns tracking data into the kind of video feed an auto-eventing model would receive."""

    def __init__(self, match: SimulatedMatch, seed: int = 7, degrade: bool = True):
        self.m = match
        self.tr = match.tracking
        self.rng = np.random.default_rng(seed)
        self.degrade = degrade
        self.base = self._pitch()
        self.kit = {}
        for club in (match.home, match.away):
            for p in club.players:
                self.kit[p.id] = (hex_bgr(club.primary), hex_bgr(club.secondary))
        # Pre-made sensor noise, added and subtracted, so degrading a frame stays cheap.
        self.noise = [(self.rng.integers(0, 14, (H, W, 3), dtype=np.uint8),
                       self.rng.integers(0, 14, (H, W, 3), dtype=np.uint8)) for _ in range(6)]
        self.last: np.ndarray | None = None

    def _pitch(self) -> np.ndarray:
        img = np.zeros((H, W, 3), np.uint8)
        img[:] = hex_bgr("#24543a")
        for i in range(0, 14, 2):
            x0, _ = to_px(105 / 14 * i, 0)
            x1, _ = to_px(105 / 14 * (i + 1), 0)
            cv2.rectangle(img, (x0, 0), (x1, H), hex_bgr("#2a5f42"), -1)
        line = (235, 240, 235)
        p = to_px
        cv2.rectangle(img, p(0, 68), p(105, 0), line, 2)
        cv2.line(img, p(52.5, 0), p(52.5, 68), line, 2)
        cv2.circle(img, p(52.5, 34), int(9.15 * PX_PER_M), line, 2)
        for left in (True, False):
            x = 0 if left else 105
            d = 1 if left else -1
            cv2.rectangle(img, p(x, 34 + 20.16), p(x + d * 16.5, 34 - 20.16), line, 2)
            cv2.rectangle(img, p(x, 34 + 9.16), p(x + d * 5.5, 34 - 9.16), line, 2)
            cv2.circle(img, p(x + d * 11, 34), 1, line, -1)  # penalty spot: tiny, so it never looks like a ball
        cv2.circle(img, p(52.5, 34), 1, line, -1)
        return img

    def positions(self, t: float) -> tuple[dict[str, tuple[float, float]], tuple[float, float]]:
        """Tracking positions at time t, interpolated between the 5 Hz samples."""
        tr = self.tr
        f = t * tr.hz
        i = max(0, min(tr.n - 2, int(f)))
        a = min(1.0, max(0.0, f - i))
        pos = {}
        for pid, xs in tr.px.items():
            x0, x1 = xs[i], xs[i + 1]
            if x0 != x0:  # NaN: not on the pitch
                continue
            if x1 != x1:
                x1 = x0
            y0, y1 = tr.py[pid][i], tr.py[pid][i + 1]
            y1 = y0 if y1 != y1 else y1
            pos[pid] = (x0 + (x1 - x0) * a, y0 + (y1 - y0) * a)
        ball = (tr.ball_x[i] + (tr.ball_x[i + 1] - tr.ball_x[i]) * a, tr.ball_y[i] + (tr.ball_y[i + 1] - tr.ball_y[i]) * a)
        return pos, ball

    def frame(self, t: float) -> np.ndarray:
        rng = self.rng
        if self.degrade and self.last is not None and rng.random() < 0.03:
            return self.last  # dropped frame: the feed repeats the last image
        pos, ball = self.positions(t)
        img = self.base.copy()
        for pid, (x, y) in pos.items():
            primary, secondary = self.kit[pid]
            c = to_px(x, y)
            cv2.circle(img, c, PLAYER_R, primary, -1, cv2.LINE_AA)
            cv2.circle(img, c, PLAYER_R, secondary, 1, cv2.LINE_AA)
        if not (self.degrade and rng.random() < 0.04):  # the ball is sometimes hidden
            cv2.circle(img, to_px(*ball), BALL_R, (250, 250, 250), -1, cv2.LINE_AA)
        if self.degrade:
            shake = np.float32([[1, 0, rng.normal(0, 0.8)], [0, 1, rng.normal(0, 0.8)]])
            img = cv2.warpAffine(img, shake, (W, H), borderMode=cv2.BORDER_REPLICATE)
            img = cv2.GaussianBlur(img, (3, 3), 0)
            img = cv2.convertScaleAbs(img, alpha=1 + rng.normal(0, 0.03), beta=rng.normal(0, 3))
            plus, minus = self.noise[int(rng.integers(0, len(self.noise)))]
            img = cv2.subtract(cv2.add(img, plus), minus)
        self.last = img
        return img


# -------------------------------------------------------------------------------------------- detector
@dataclass
class Detection:
    t: float
    ball: tuple[float, float] | None
    players: list[tuple[str, float, float]]  # (side, x, y) in metres


class Detector:
    """Finds players by kit colour and the ball as a small, round, bright blob."""

    def __init__(self, kits: dict[str, tuple[int, int, int]], tolerance: float = 22.0,
                 background: np.ndarray | None = None):
        self.kits = {side: self._lab(bgr) for side, bgr in kits.items()}
        self.tol = tolerance
        self.ball_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        # Small kernel for kits: a player with the ball on top of them is only a thin ring of colour.
        self.kit_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.player_area = math.pi * PLAYER_R**2
        self.missed = 0  # frames since the ball was last seen
        # Background subtraction, as with any fixed camera: the empty pitch, so its white lines never look like a ball.
        self.background = cv2.GaussianBlur(background, (3, 3), 0) if background is not None else None

    @staticmethod
    def _lab(bgr: tuple[int, int, int]) -> np.ndarray:
        return cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)

    def detect(self, img: np.ndarray, t: float, prev_ball: tuple[float, float] | None) -> Detection:
        # Ball: bright pixels, then an opening that erases thin pitch lines and kit outlines.
        bright = cv2.inRange(img, (200, 200, 200), (255, 255, 255))
        if self.background is not None:
            changed = cv2.cvtColor(cv2.absdiff(img, self.background), cv2.COLOR_BGR2GRAY)
            bright = cv2.bitwise_and(bright, cv2.inRange(changed, 60, 255))
        bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, self.ball_kernel)
        n, _, stats, cents = cv2.connectedComponentsWithStats(bright)
        candidates = []  # (shape score, position): lower score = more like a ball
        ball_area = math.pi * BALL_R**2
        for k in range(1, n):
            area = stats[k, cv2.CC_STAT_AREA]
            w, h = stats[k, cv2.CC_STAT_WIDTH], stats[k, cv2.CC_STAT_HEIGHT]
            if 8 <= area <= 70 and 0.5 <= w / max(h, 1) <= 2.0:
                fill = area / max(1, w * h)  # a disc fills ~78% of its box; a line junction far less
                score = abs(area - ball_area) / ball_area + 2 * abs(fill - 0.78)
                candidates.append((score, to_m(*cents[k])))
        ball = None
        # A ball covers at most ~4 m per frame, so a farther blob is something else. The allowed distance grows
        # with every frame the ball was unseen (e.g. crossing a white line). After a second, reacquire by shape.
        if prev_ball is not None and self.missed < FPS:
            reach = 5.0 + 4.0 * self.missed
            near = [c for c in candidates if math.dist(c[1], prev_ball) < reach]
            if near:
                ball = min(near, key=lambda c: math.dist(c[1], prev_ball))[1]
        elif candidates:
            ball = min(candidates)[1]
        self.missed = 0 if ball else self.missed + 1

        # Players: pixels close to each team's kit colour (in Lab space), split merged blobs by area.
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        players: list[tuple[str, float, float]] = []
        for side, kit in self.kits.items():
            # A colour box around the kit in Lab space: native and fast, unlike a per-pixel distance.
            lo = tuple(int(max(0, c - self.tol)) for c in kit)
            hi = tuple(int(min(255, c + self.tol)) for c in kit)
            mask = cv2.inRange(lab, lo, hi)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kit_kernel)
            n, labels, stats, cents = cv2.connectedComponentsWithStats(mask)
            for k in range(1, n):
                area = stats[k, cv2.CC_STAT_AREA]
                if area < 0.35 * self.player_area:
                    continue
                count = max(1, round(area / self.player_area))
                if count == 1:
                    players.append((side, *to_m(*cents[k])))
                    continue
                ys, xs = np.nonzero(labels == k)
                pts = np.float32(np.column_stack([xs, ys]))
                _, _, centres = cv2.kmeans(pts, min(count, 4), None,
                                           (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5), 2,
                                           cv2.KMEANS_PP_CENTERS)
                players += [(side, *to_m(cx, cy)) for cx, cy in centres]
        return Detection(t, ball, players)


# ---------------------------------------------------------------------------------------------- events
@dataclass
class VisionEvent:
    type: str  # "pass" or "shot"
    t: float  # when the ball left the player
    t_end: float
    start: tuple[float, float]
    end: tuple[float, float]
    side: str | None
    outcome: str  # pass: complete / lost; shot: on goal line
    distance_m: float
    speed_kmh: float
    receiver: str | None = None


def ball_track(dets: list[Detection]) -> list[tuple[float, float] | None]:
    """Ball positions per frame, with short gaps (hidden ball, dropped frames) filled by interpolation."""
    track = [d.ball for d in dets]
    i = 0
    while i < len(track):
        if track[i] is None:
            j = i
            while j < len(track) and track[j] is None:
                j += 1
            if 0 < i and j < len(track) and j - i <= 6:  # up to 0.6 s, e.g. the ball crossing a white line
                a, b = track[i - 1], track[j]
                for k in range(i, j):
                    f = (k - i + 1) / (j - i + 1)
                    track[k] = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            i = j
        else:
            i += 1
    return track


def _nearest(players: list[tuple[str, float, float]], pt: tuple[float, float], radius: float) -> str | None:
    best, side = radius, None
    for s, x, y in players:
        d = math.hypot(x - pt[0], y - pt[1])
        if d < best:
            best, side = d, s
    return side


def _passer(dets: list[Detection], start: tuple[float, float], end: tuple[float, float], frames) -> str | None:
    """The passer is the player the ball moves away from: close to the launch point and behind it
    along the direction of travel. A defender pressing from in front scores worse."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    norm = math.hypot(dx, dy) or 1.0
    ux, uy = dx / norm, dy / norm
    best, side = 7.0, None
    for k in frames:
        for s, x, y in dets[k].players:
            d = math.hypot(x - start[0], y - start[1])
            ahead = (x - start[0]) * ux + (y - start[1]) * uy
            score = d + (4.0 if ahead > 0.5 else 0.0)
            if score < best:
                best, side = score, s
    return side


def _closest_by_team(dets: list[Detection], track: list, frames) -> dict[str, float]:
    """Each team's closest approach to the ball over these frames (metres)."""
    best: dict[str, float] = {}
    for k in frames:
        if track[k] is None:
            continue
        for s, x, y in dets[k].players:
            d = math.hypot(x - track[k][0], y - track[k][1])
            if d < best.get(s, 1e9):
                best[s] = d
    return best


def _receiver(dets: list[Detection], track: list, frames) -> str | None:
    """The receiver is the team whose player gets closest to the ball as it arrives."""
    best = _closest_by_team(dets, track, frames)
    side = min(best, key=best.get) if best else None
    return side if side and best[side] < 6.0 else None


def infer_events(dets: list[Detection], fps: int = FPS) -> list[VisionEvent]:
    track = ball_track(dets)
    n = len(track)
    speed = [0.0] * n
    for i in range(1, n):
        a, b = track[i - 1], track[i]
        if a is not None and b is not None:
            speed[i] = math.dist(a, b) * fps
    # A repeated (dropped) frame shows zero movement for one step; don't let it split a flight.
    flying = [s > FLIGHT_MS for s in speed]
    for i in range(1, n - 1):
        if not flying[i] and flying[i - 1] and flying[i + 1]:
            flying[i] = True
    events: list[VisionEvent] = []
    i = 1
    while i < n:
        if not flying[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and flying[j + 1]:
            j += 1
        if j - i + 1 >= 2 and track[i - 1] is not None and track[j] is not None:
            start, end = track[i - 1], track[j]
            dur = (j - (i - 1)) / fps
            dist = math.dist(start, end)
            kmh = dist / dur * 3.6
            receiver = _receiver(dets, track, range(j, min(n, j + 8)))
            # Possession chain: whoever received the previous ball is the next passer, if it was recent.
            # Receivers are far easier to read than passers (who often have a defender on top of them).
            prev = events[-1] if events else None
            if prev is not None and prev.receiver and dets[i - 1].t - prev.t_end < 6.0:
                passer = prev.receiver
            else:
                passer = _receiver(dets, track, range(max(0, i - 2), i))
            at_goal = (end[0] <= 1.5 or end[0] >= 103.5) and abs(end[1] - 34) < 9
            if at_goal and kmh > 30:
                events.append(VisionEvent("shot", dets[i - 1].t, dets[j].t, start, end, passer, "at goal", dist, kmh, None))
            elif dist >= 3:
                # Call a pass lost only when an opponent clearly reaches the ball first; a close call stays
                # with the passing team, which is right most of the time in football.
                close = _closest_by_team(dets, track, range(j, min(n, j + 8)))
                mine = close.get(passer, 1e9) if passer else 1e9
                theirs = min((d for s, d in close.items() if s != passer), default=1e9)
                outcome = "lost" if passer and theirs < 2.5 and theirs + 1.5 < mine else "complete"
                events.append(VisionEvent("pass", dets[i - 1].t, dets[j].t, start, end, passer, outcome, dist, kmh, receiver))
        i = j + 1
    return events


# ------------------------------------------------------------------------------------------ evaluation
@dataclass
class Evaluation:
    window: tuple[float, float]
    frames: int
    truth_passes: int
    truth_shots: int
    detected: int
    matched_passes: int
    matched_shots: int
    false_detections: int
    outcome_correct: int
    distance_errors: list[float] = field(default_factory=list)
    speed_errors: list[float] = field(default_factory=list)
    shot_speed_errors: list[float] = field(default_factory=list)

    def summary(self) -> dict:
        mean = lambda xs: round(sum(xs) / len(xs), 1) if xs else None  # noqa: E731
        return {
            "window_s": [round(self.window[0]), round(self.window[1])],
            "frames": self.frames,
            "pass_recall_pct": round(100 * self.matched_passes / max(1, self.truth_passes)),
            "shot_recall_pct": round(100 * self.matched_shots / max(1, self.truth_shots)),
            "precision_pct": round(100 * (self.matched_passes + self.matched_shots) / max(1, self.detected)),
            "pass_outcome_accuracy_pct": round(100 * self.outcome_correct / max(1, self.matched_passes)),
            "pass_distance_error_m": mean(self.distance_errors),
            "ball_speed_error_kmh": mean(self.speed_errors),
            "shot_speed_error_kmh": mean(self.shot_speed_errors),
            "truth_passes": self.truth_passes,
            "truth_shots": self.truth_shots,
            "detected": self.detected,
        }


def _truth_metrics(e: dict, side: str) -> tuple[float, float]:
    x0, y0 = to_frame(side, e["x"], e["y"])
    x1, y1 = to_frame(side, e["end_x"], e["end_y"])
    dist = math.hypot(x1 - x0, y1 - y0)
    return dist, (dist / e["duration"] * 3.6 if e.get("duration") else 0.0)


def evaluate(match: SimulatedMatch, events: list[VisionEvent], window: tuple[float, float], frames: int) -> Evaluation:
    lo, hi = window
    # Truth and detections use the same window: events that start too close to either edge can't be judged.
    truth = [e for e in match.events if e["type"] in ("pass", "shot") and lo + 0.2 <= e["t"] <= hi - 2.5
             and e.get("duration")]
    events = [d for d in events if lo + 0.2 <= d.t <= hi - 2.5]
    ev = Evaluation(window, frames, sum(e["type"] == "pass" for e in truth), sum(e["type"] == "shot" for e in truth),
                    len(events), 0, 0, 0, 0)
    used: set[int] = set()
    for e in truth:
        best, best_k = 0.6, None  # a detection must start within 0.6 s of the true event
        for k, d in enumerate(events):
            if k in used:
                continue
            dt = abs(d.t - e["t"])
            if dt <= best and (d.type == e["type"] or (e["type"] == "shot" and e["outcome"] in ("blocked", "saved"))):
                best, best_k = dt, k
        if best_k is None:
            continue
        used.add(best_k)
        d = events[best_k]
        dist, kmh = _truth_metrics(e, e["side"])
        if e["type"] == "pass":
            ev.matched_passes += 1
            ev.outcome_correct += (d.outcome == "complete") == (e["outcome"] == "complete")
            ev.distance_errors.append(abs(d.distance_m - dist))
            ev.speed_errors.append(abs(d.speed_kmh - kmh))
        else:
            ev.matched_shots += 1
            ev.shot_speed_errors.append(abs(d.speed_kmh - kmh))
    ev.false_detections = len(events) - len(used)
    return ev


# ------------------------------------------------------------------------------------------- pipeline
def run(match: SimulatedMatch, start: float, seconds: float, clip_path: str | None = None, seed: int = 7):
    """Render the window, detect, infer events, evaluate; optionally write an annotated video clip."""
    cam = Camera(match, seed=seed)
    sides = {"home": hex_bgr(match.home.primary), "away": hex_bgr(match.away.primary)}
    det = Detector(sides, background=cam.base)
    t0, t1 = max(0.0, start), min(match.duration, start + seconds)
    times = [t0 + k / FPS for k in range(int((t1 - t0) * FPS))]
    frames, dets = [], []
    prev = None
    for t in times:
        img = cam.frame(t)
        d = det.detect(img, t, prev)
        prev = d.ball or prev
        dets.append(d)
        if clip_path:
            frames.append(img)
    events = infer_events(dets)
    result = evaluate(match, events, (t0, t1), len(times))
    if clip_path:
        write_clip(clip_path, frames, dets, events, match)
    return events, result


def write_clip(path: str, frames: list[np.ndarray], dets: list[Detection], events: list[VisionEvent],
               match: SimulatedMatch) -> None:
    fourcc = "VP90" if path.endswith(".webm") else "mp4v"
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*fourcc), FPS, (W, H + 40))
    track = ball_track(dets)  # draw the tracked ball, so the marker stays on while the ball crosses a player
    trail: list[tuple[int, int]] = []
    passes = shots = 0
    for img, d, ball in zip(frames, dets, track):
        canvas = np.zeros((H + 40, W, 3), np.uint8)
        # Detection ran on the noisy frame; the copy written to video is lightly smoothed so it compresses well.
        canvas[40:] = cv2.medianBlur(img, 3)
        view = canvas[40:]
        for side, x, y in d.players:
            cx, cy = to_px(x, y)
            colour = (255, 220, 120) if side == "home" else (120, 200, 255)
            cv2.rectangle(view, (cx - 10, cy - 10), (cx + 10, cy + 10), colour, 1)
        if ball:
            bx, by = to_px(*ball)
            trail = (trail + [(bx, by)])[-12:]
            cv2.circle(view, (bx, by), 7, (0, 255, 255), 2)
        for a, b in zip(trail, trail[1:]):
            cv2.line(view, a, b, (0, 220, 255), 1, cv2.LINE_AA)
        for e in events:
            if e.t_end <= d.t < e.t_end + 1.5:  # label each event for 1.5 s after it ends
                ex, ey = to_px(*e.end)
                label = (f"PASS {e.distance_m:.0f} m  {e.speed_kmh:.0f} km/h" if e.type == "pass"
                         else f"SHOT {e.speed_kmh:.0f} km/h")
                (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                ex = ex - tw - 20 if ex + 10 + tw > W - 4 else ex  # keep the label inside the frame
                ey = max(ey, 24)
                cv2.putText(view, label, (ex + 10, ey - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(view, label, (ex + 10, ey - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            if abs(e.t_end - d.t) < 0.05:
                passes += e.type == "pass"
                shots += e.type == "shot"
        period, clock = match.clock(d.t)
        cv2.putText(canvas, f"AUTO-EVENTING  computer vision on the video feed   {int(clock // 60)}:{int(clock % 60):02d}"
                    f"   passes detected: {passes}   shots: {shots}", (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (80, 200, 255), 1, cv2.LINE_AA)
        out.write(canvas)
    out.release()
