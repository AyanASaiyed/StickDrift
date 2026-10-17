"""Synthetic garden recordings for the pattern model.

The apple, butterfly, and water courses match Controller Data - Zain/Games/garden.py.
What changes is how the hand travels: late, slow, smaller, steadily shaky,
one-sided, a single jerk, an apple reached too far or too short and then
corrected, or a slow curve off the butterfly and watering paths.

Diabetes is not a 4–12 Hz shake. The outbound reach uses a normal duration,
lands past the apple or short of it, then comes back onto it. Ataxia is not
that shake either. The hand weaves off the moving path and passes the target
at well under 1 Hz. Folder names are the labels. On apple files the ataxia
label is masked; on butterfly and water files the diabetes label is masked.
"""

import csv
import math
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HZ = 100
CENTER = 128
SCALE = 120
GYRO_NOISE = 8.0
CORRECT_S = 0.36

# Same course as Controller Data - Zain/Games/garden.py.
APPLES = ((270, 0.60), (180, 0.40), (135, 0.60), (315, 0.40), (90, 0.40), (225, 0.60))
FLY_R0, FLY_RA, FLY_LOBES, FLY_LAP = 0.40, 0.06, 2, 12.0
WATER_CTRL = ((-0.55, 0.25), (-0.30, -0.10), (0.0, 0.20), (0.30, -0.10), (0.55, 0.20))
WATER_SECS = 15.0
WATER_N = 241

COLUMNS = (
    "t", "lx", "ly", "rx", "ry",
    "gyro_x", "gyro_y", "gyro_z",
    "acc_x", "acc_y", "acc_z",
    "phase",
    "target_lx", "target_ly", "target_rx", "target_ry",
    "cursor_lx", "cursor_ly", "cursor_rx", "cursor_ry",
    "label",
)


@dataclass(frozen=True)
class Condition:
    folder: str
    parkinson: float
    stroke: float
    tremor: float
    weak_hand: str | None = None
    tremor_hand: str | None = None
    shake_hand: str | None = None
    latency_s: float = 0.10
    move_s: float = 0.42
    gain_left: float = 1.0
    gain_right: float = 1.0
    shrink: float = 1.0
    tremor_hz: float = 6.5
    gyro_amp: float = 0.0
    stick_shake: float = 0.0
    jerk: bool = False
    still_hand: str | None = None
    diabetes: float = 0.0
    ataxia: float = 0.0
    aim: str | None = None
    wander: str | None = None
    levels: tuple[str, ...] = ("apples", "butterfly_left", "butterfly_right", "water")


CONDITIONS = (
    Condition("Baseline", 0, 0, 0),
    Condition("Parkinson Mild", 45, 0, 0, latency_s=0.28, move_s=0.75, shrink=0.97),
    Condition("Parkinson Strong", 85, 0, 0, latency_s=0.50, move_s=1.05, shrink=0.92, gain_left=0.95, gain_right=0.95),
    Condition("Tremor Mild", 0, 0, 45, gyro_amp=280, stick_shake=0.012, tremor_hz=6.0),
    Condition("Tremor Strong", 0, 0, 85, gyro_amp=650, stick_shake=0.028, tremor_hz=7.0),
    Condition("Stroke Left Mild", 0, 45, 0, weak_hand="left", gain_left=0.70, move_s=0.55),
    Condition("Stroke Left Strong", 0, 85, 0, weak_hand="left", gain_left=0.50, move_s=0.60, latency_s=0.18),
    Condition("Stroke Right Mild", 0, 45, 0, weak_hand="right", gain_right=0.70, move_s=0.55),
    Condition("Stroke Right Strong", 0, 85, 0, weak_hand="right", gain_right=0.50, move_s=0.60, latency_s=0.18),
    Condition("Parkinson and Tremor", 70, 0, 70, latency_s=0.40, move_s=0.95, shrink=0.94, gyro_amp=520, stick_shake=0.022),
    Condition(
        "Stroke Left and Tremor", 0, 70, 70, weak_hand="left", shake_hand="left",
        gain_left=0.55, move_s=0.65, gyro_amp=520, stick_shake=0.022,
    ),
    Condition(
        "Stroke Right and Tremor", 0, 70, 70, weak_hand="right", shake_hand="right",
        gain_right=0.55, move_s=0.65, gyro_amp=520, stick_shake=0.022,
    ),
    Condition(
        "Parkinson and Stroke Left", 50, 35, 0, weak_hand="left",
        latency_s=0.40, move_s=1.00, shrink=0.94, gain_left=0.62, gain_right=0.92,
    ),
    Condition(
        "Parkinson and Stroke Right", 50, 35, 0, weak_hand="right",
        latency_s=0.40, move_s=1.00, shrink=0.94, gain_left=0.92, gain_right=0.62,
    ),
    Condition("Jerk", 0, 0, 0, jerk=True),
    Condition(
        "Left Hand Slow", 70, 0, 0, latency_s=0.40, move_s=1.00, still_hand="right",
        levels=("apples", "butterfly_left", "water"),
    ),
    Condition(
        "Right Hand Shake", 0, 0, 70, tremor_hand="right", shake_hand="right", gyro_amp=560, stick_shake=0.024,
        still_hand="left", levels=("apples", "butterfly_right", "water"),
    ),
    Condition("Diabetes Mild", 0, 0, 0, diabetes=45, aim="mild", levels=("apples",)),
    Condition("Diabetes Strong", 0, 0, 0, diabetes=85, aim="strong", levels=("apples",)),
    Condition(
        "Ataxia Mild", 0, 0, 0, ataxia=45, wander="mild",
        levels=("butterfly_left", "butterfly_right", "water"),
    ),
    Condition(
        "Ataxia Strong", 0, 0, 0, ataxia=85, wander="strong",
        levels=("butterfly_left", "butterfly_right", "water"),
    ),
    Condition(
        "Tremor and Diabetes", 0, 0, 70, diabetes=70, aim="strong",
        gyro_amp=520, stick_shake=0.022, tremor_hz=6.5,
    ),
    Condition(
        "Tremor and Ataxia", 0, 0, 70, ataxia=70, wander="strong",
        gyro_amp=520, stick_shake=0.022, tremor_hz=6.5,
    ),
)


def write_synthetic(root: str | Path, apple_seeds: int = 3) -> int:
    """Write one folder per condition under `root`. Returns the file count."""
    destination = Path(root)
    if destination.exists():
        shutil.rmtree(destination)
    count = 0
    for condition in CONDITIONS:
        for level in condition.levels:
            seeds = range(1, apple_seeds + 1) if level == "apples" else range(1, 2)
            for seed in seeds:
                folder = destination / condition.folder / f"{level}_s{seed}"
                folder.mkdir(parents=True)
                rows = _recording(condition, level, seed)
                _write(folder / "controller_data.csv", rows, condition)
                count += 1
    return count


def _recording(condition: Condition, level: str, seed: int) -> list[list]:
    rng = np.random.default_rng(seed + sum(ord(char) for char in condition.folder))
    rows: list[list] = []
    clock = _Clock()
    if level == "apples":
        _rest(rows, clock, rng, condition, 0.45, ((0.0, 0.0), (0.0, 0.0)))
        for index, (deg, dist) in enumerate(APPLES):
            target = _polar(deg, dist)
            shrink = condition.shrink ** index
            _reach_pair(rows, clock, rng, condition, target, shrink, jerk=condition.jerk and index == 0, index=index)
            _return_pair(rows, clock, rng, condition, target, shrink)
            _rest(rows, clock, rng, condition, 0.35, ((0.0, 0.0), (0.0, 0.0)))
        return rows
    target_fn = fly_at if level.startswith("butterfly") else water_at
    hand = "left" if level.endswith("left") else "right" if level.endswith("right") else "both"
    duration = FLY_LAP if level.startswith("butterfly") else WATER_SECS
    _rest(rows, clock, rng, condition, 0.40, ((0.0, 0.0), (0.0, 0.0)))
    _track(rows, clock, rng, condition, target_fn, hand, duration)
    return rows


def _reach_pair(rows, clock, rng, condition, target, shrink, jerk: bool, index: int) -> None:
    miss = _miss_gain(condition, index)
    if miss is None:
        duration = condition.latency_s + condition.move_s + 0.28
    else:
        duration = condition.latency_s + condition.move_s + CORRECT_S + 0.24
    jerk_at = condition.latency_s + condition.move_s * 0.55
    mirrored = _mirror(target)

    def place(elapsed: float) -> tuple[float, float, float, float]:
        left = _hand_point("left", target, condition, shrink, elapsed, condition.latency_s, condition.move_s, clock.t, miss)
        right = _hand_point("right", mirrored, condition, shrink, elapsed, condition.latency_s, condition.move_s, clock.t, miss)
        return (*left, *right)

    _emit(rows, clock, rng, condition, duration, "cue", place, lambda _elapsed: (target, mirrored), jerk_at if jerk else None)


def _return_pair(rows, clock, rng, condition, target, shrink) -> None:
    duration = 0.35
    mirrored = _mirror(target)

    def place(elapsed: float) -> tuple[float, float, float, float]:
        ease = 1.0 - _ease(elapsed / duration)
        left = _scaled("left", target, condition, shrink, ease)
        right = _scaled("right", mirrored, condition, shrink, ease)
        return (*left, *right)

    _emit(rows, clock, rng, condition, duration, "return", place, lambda _elapsed: ((0.0, 0.0), (0.0, 0.0)), None)


def _track(rows, clock, rng, condition, target_fn, hand: str, duration: float) -> None:
    """Follow the moving course in hops fast enough to count as movement.

    The opening reach is phase wait, matching the game's move to the start,
    so it is not an ataxia sample. Later hops stay on the path unless this
    condition wanders.
    """
    active = ("left", "right") if hand == "both" else (hand,)
    origin = {"left": (0.0, 0.0), "right": (0.0, 0.0)}
    landed = _hands_at(condition, target_fn, 0.0, active)
    _slide(rows, clock, rng, condition, origin, landed, 0.45, "wait", lambda _elapsed: _pair(target_fn, 0.0, active))
    _coast(rows, clock, rng, condition, landed, 0.25, "wait", lambda _elapsed: _pair(target_fn, 0.0, active))

    elapsed = 0.0
    while elapsed < duration - 0.05:
        if condition.latency_s > 0.08 and elapsed > 0.0:
            pause = min(condition.latency_s, duration - elapsed)
            pair = _pair(target_fn, elapsed, active)
            pos = {
                "left": _shifted(condition, pair[0], elapsed, "left", clock.t),
                "right": _shifted(condition, pair[1], elapsed, "right", clock.t),
            }
            _coast(rows, clock, rng, condition, pos, pause, "track", _moving_target(target_fn, elapsed, active, duration))
            elapsed += pause
            if elapsed >= duration - 0.05:
                break
        hop = min(0.30, duration - elapsed)
        if hop < 0.2:
            break
        span = _span_for(target_fn, elapsed, hop, duration)
        _along(rows, clock, rng, condition, target_fn, active, elapsed, hop, span, duration)
        elapsed += hop
        hold = min(max(0.0, span - hop), duration - elapsed, 0.45)
        if hold > 0.05:
            # Stay where the hop finished, on the course at t0+span, until the target arrives.
            arrived = min(duration, (elapsed - hop) + span)
            finished = {
                "left": _shifted(condition, _pair(target_fn, arrived, active)[0], arrived, "left", clock.t),
                "right": _shifted(condition, _pair(target_fn, arrived, active)[1], arrived, "right", clock.t),
            }
            _coast(rows, clock, rng, condition, finished, hold, "track", _moving_target(target_fn, elapsed, active, duration))
            elapsed += hold


def _rest(rows, clock, rng, condition, duration: float, targets) -> None:
    _emit(
        rows, clock, rng, condition, duration, "wait",
        lambda _elapsed: (0.0, 0.0, 0.0, 0.0),
        lambda _elapsed: targets,
        None,
    )


def _slide(rows, clock, rng, condition, start, dest, duration, phase, target_of) -> None:
    def place(local: float) -> tuple[float, float, float, float]:
        unit = 0.0 if duration <= 0.0 else local / duration
        ease = _ease(unit)
        points = []
        for name in ("left", "right"):
            ax, ay = start[name]
            bx, by = dest[name]
            x = ax + (bx - ax) * ease
            y = ay + (by - ay) * ease
            if condition.still_hand == name:
                x, y = 0.0, 0.0
            wobble = _wobble(clock.t, name)
            points.extend((x + wobble[0], y + wobble[1]))
        return tuple(points)

    _emit(rows, clock, rng, condition, duration, phase, place, target_of, None)


def _coast(rows, clock, rng, condition, pos, duration, phase, target_of) -> None:
    def place(_local: float) -> tuple[float, float, float, float]:
        points = []
        for name in ("left", "right"):
            x, y = pos[name]
            if condition.still_hand == name:
                x, y = 0.0, 0.0
            wobble = _wobble(clock.t, name)
            points.extend((x + wobble[0], y + wobble[1]))
        return tuple(points)

    _emit(rows, clock, rng, condition, duration, phase, place, target_of, None)


def _emit(rows, clock, rng, condition, duration, phase, place, target_of, jerk_at) -> None:
    count = max(2, int(round(duration * HZ)))
    for index in range(count):
        elapsed = index / HZ
        lx, ly, rx, ry = place(elapsed)
        shaking = phase in {"cue", "track"}
        lx, ly = _stick_shake(condition, "left", lx, ly, clock.t, shaking)
        rx, ry = _stick_shake(condition, "right", rx, ry, clock.t, shaking)
        gyro = np.array(_controller_shake(condition, clock.t, shaking), dtype=float)
        if jerk_at is not None:
            gyro += _jerk(elapsed, jerk_at) * 3.0
            lx += 0.07 * _jerk_envelope(elapsed, jerk_at)
        gyro += rng.normal(0.0, GYRO_NOISE, size=3)
        left_target, right_target = target_of(elapsed)
        rows.append([
            round(clock.t, 4),
            _stick(lx), _stick(ly), _stick(rx), _stick(ry),
            int(round(gyro[0])), int(round(gyro[1])), int(round(gyro[2])),
            int(round(rng.normal(0, 30))),
            int(round(7800 + rng.normal(0, 40))),
            int(round(1340 + rng.normal(0, 30))),
            phase,
            *_point(left_target),
            *_point(right_target),
            f"{lx:.4f}", f"{ly:.4f}", f"{rx:.4f}", f"{ry:.4f}",
        ])
        clock.t += 1.0 / HZ


def _span_for(target_fn, t0: float, hop: float, duration: float) -> float:
    """How far ahead on the course the hand must travel to clear the movement gate."""
    span = hop
    need = 0.15
    while t0 + span < duration and math.dist(target_fn(t0), target_fn(t0 + span)) < need:
        span += 0.05
    return min(span, max(hop, duration - t0))


def _along(rows, clock, rng, condition, target_fn, active, t0, hop, span, duration) -> None:
    """Travel along the real course from t0 to t0+span, packed into `hop` seconds."""

    def place(local: float) -> tuple[float, float, float, float]:
        unit = 0.0 if hop <= 0.0 else local / hop
        when = min(duration, t0 + span * _ease(unit))
        pair = _pair(target_fn, when, active)
        left = _shifted(condition, pair[0], when, "left", clock.t)
        right = _shifted(condition, pair[1], when, "right", clock.t)
        return (*left, *right)

    _emit(
        rows, clock, rng, condition, hop, "track", place,
        _moving_target(target_fn, t0, active, duration),
        None,
    )


def _hands_at(condition, target_fn, time_s, active) -> dict[str, tuple[float, float]]:
    pair = _pair(target_fn, time_s, active)
    return {
        "left": _place(condition, pair[0], time_s, "left"),
        "right": _place(condition, pair[1], time_s, "right"),
    }


def _moving_target(target_fn, t0, active, duration):
    def target_of(local: float):
        return _pair(target_fn, min(duration, max(0.0, t0 + local)), active)

    return target_of


def _pair(target_fn, time_s, active):
    point = target_fn(time_s)
    left = point if "left" in active else None
    right = _mirror(point) if "right" in active else None
    return left, right


def _place(condition, point, time_s, hand) -> tuple[float, float]:
    if point is None or condition.still_hand == hand:
        return 0.0, 0.0
    gain = condition.gain_left if hand == "left" else condition.gain_right
    return point[0] * gain, point[1] * gain


def _shifted(condition, point, time_s, hand, wobble_t: float) -> tuple[float, float]:
    x, y = _place(condition, point, time_s, hand)
    if point is None or condition.still_hand == hand:
        return x, y
    ox, oy = _wander_offset(condition, time_s, point)
    wobble = _wobble(wobble_t, hand)
    return x + ox + wobble[0], y + oy + wobble[1]


def _hand_point(hand, target, condition, shrink, elapsed, latency, move_s, time_s, miss):
    if condition.still_hand == hand:
        return 0.0, 0.0
    gain = condition.gain_left if hand == "left" else condition.gain_right
    if miss is None:
        scale = 0.0 if elapsed < latency else _ease((elapsed - latency) / move_s)
    else:
        scale = _diabetes_scale(elapsed, latency, move_s, miss)
    scale *= gain * shrink
    wobble = _wobble(time_s, hand)
    return target[0] * scale + wobble[0], target[1] * scale + wobble[1]


def _scaled(hand, target, condition, shrink, ease):
    if condition.still_hand == hand:
        return 0.0, 0.0
    gain = condition.gain_left if hand == "left" else condition.gain_right
    return target[0] * gain * shrink * ease, target[1] * gain * shrink * ease


def _diabetes_scale(elapsed: float, latency: float, move_s: float, miss: float) -> float:
    """Go out to the wrong gain, then ease back onto the apple. Speed stays ordinary."""
    if elapsed < latency:
        return 0.0
    outbound_end = latency + move_s
    correct_end = outbound_end + CORRECT_S
    if elapsed <= outbound_end:
        return miss * _ease((elapsed - latency) / move_s)
    if elapsed <= correct_end:
        mix = _ease((elapsed - outbound_end) / CORRECT_S)
        return miss + (1.0 - miss) * mix
    return 1.0


def _miss_gain(condition: Condition, index: int) -> float | None:
    if condition.aim == "strong":
        return 1.65 if index % 2 == 0 else 0.38
    if condition.aim == "mild":
        return 1.28 if index % 2 == 0 else 0.62
    return None


def _wander_offset(condition: Condition, time_s: float, point: tuple[float, float]) -> tuple[float, float]:
    """Slow curve off the path. Both frequencies stay under 1 Hz."""
    lateral_amp, ahead_amp = _wander_amps(condition)
    if lateral_amp == 0.0 and ahead_amp == 0.0:
        return 0.0, 0.0
    tx, ty = point
    radius = math.hypot(tx, ty) or 1.0
    ux, uy = tx / radius, ty / radius
    side = lateral_amp * math.sin(2.0 * math.pi * 0.30 * time_s)
    lead = ahead_amp * math.sin(2.0 * math.pi * 0.22 * time_s + 0.7)
    return ux * lead - uy * side, uy * lead + ux * side


def _wander_amps(condition: Condition) -> tuple[float, float]:
    if condition.wander == "strong":
        return 0.28, 0.20
    if condition.wander == "mild":
        return 0.16, 0.12
    return 0.0, 0.0


def _stick_shake(condition, hand, x, y, time_s, active: bool):
    if not active or condition.stick_shake <= 0.0 or not _hand_shakes(condition, hand):
        return x, y
    cycle = 2.0 * math.pi * condition.tremor_hz * time_s
    return x + condition.stick_shake * math.sin(cycle), y + condition.stick_shake * 0.6 * math.cos(cycle)


def _controller_shake(condition, time_s, active: bool) -> tuple[float, float, float]:
    if not active or condition.gyro_amp <= 0.0:
        return 0.0, 0.0, 0.0
    cycle = 2.0 * math.pi * condition.tremor_hz * time_s
    amp = condition.gyro_amp
    return amp * math.sin(cycle), amp * 0.65 * math.sin(cycle + 0.8), amp * 0.4 * math.sin(cycle + 1.4)


def _hand_shakes(condition: Condition, hand: str) -> bool:
    which = condition.shake_hand or condition.tremor_hand
    return which in (None, "both", hand)


def _jerk(elapsed: float, center: float) -> np.ndarray:
    return np.array([180.0, 90.0, 40.0]) * _jerk_envelope(elapsed, center)


def _jerk_envelope(elapsed: float, center: float) -> float:
    half = 0.04
    if abs(elapsed - center) > half:
        return 0.0
    return math.sin(math.pi * (elapsed - center + half) / (2 * half))


def _wobble(time_s: float, hand: str) -> tuple[float, float]:
    shift = 0.4 if hand == "right" else 0.0
    return (
        0.02 * math.sin(2 * math.pi * 0.7 * time_s + shift),
        0.02 * math.cos(2 * math.pi * 0.5 * time_s + shift),
    )


def _ease(unit: float) -> float:
    unit = min(max(unit, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * unit)


def _stick(normal: float) -> int:
    return int(round(min(255, max(0, CENTER + normal * SCALE))))


def _point(point) -> tuple[str, str]:
    if point is None:
        return "", ""
    return f"{point[0]:.4f}", f"{point[1]:.4f}"


def _polar(deg: float, dist: float) -> tuple[float, float]:
    angle = math.radians(deg)
    return dist * math.cos(angle), dist * math.sin(angle)


def _mirror(point: tuple[float, float]) -> tuple[float, float]:
    return -point[0], point[1]


def fly_at(time_s: float) -> tuple[float, float]:
    theta = 2 * math.pi * min(max(time_s, 0.0), FLY_LAP) / FLY_LAP
    radius = FLY_R0 + FLY_RA * math.sin(FLY_LOBES * theta)
    return radius * math.cos(theta), radius * math.sin(theta)


def water_at(time_s: float) -> tuple[float, float]:
    path = _WATER_PATH
    unit = min(max(time_s / WATER_SECS, 0.0), 1.0) * (WATER_N - 1)
    index = min(int(unit), WATER_N - 2)
    mix = unit - index
    start, end = path[index], path[index + 1]
    return start[0] + (end[0] - start[0]) * mix, start[1] + (end[1] - start[1]) * mix


def _build_water_path() -> list[tuple[float, float]]:
    controls = WATER_CTRL
    dense = []
    for index in range(len(controls) - 1):
        p0 = controls[max(index - 1, 0)]
        p1 = controls[index]
        p2 = controls[index + 1]
        p3 = controls[min(index + 2, len(controls) - 1)]
        dense.extend(_catmull(p0, p1, p2, p3, step / 50) for step in range(50))
    dense.append(controls[-1])
    lengths = [0.0]
    for start, end in zip(dense, dense[1:]):
        lengths.append(lengths[-1] + math.dist(start, end))
    spans = []
    cursor = 0
    for step in range(WATER_N):
        target = lengths[-1] * step / (WATER_N - 1)
        while cursor < len(lengths) - 2 and lengths[cursor + 1] < target:
            cursor += 1
        mix = (target - lengths[cursor]) / ((lengths[cursor + 1] - lengths[cursor]) or 1.0)
        start, end = dense[cursor], dense[cursor + 1]
        spans.append((start[0] + (end[0] - start[0]) * mix, start[1] + (end[1] - start[1]) * mix))
    return spans


def _catmull(p0, p1, p2, p3, unit: float) -> tuple[float, float]:
    def coord(a, b, c, d):
        return 0.5 * (
            2 * b
            + (-a + c) * unit
            + (2 * a - 5 * b + 4 * c - d) * unit ** 2
            + (-a + 3 * b - 3 * c + d) * unit ** 3
        )

    return coord(p0[0], p1[0], p2[0], p3[0]), coord(p0[1], p1[1], p2[1], p3[1])


_WATER_PATH = _build_water_path()


def _write(path: Path, rows: list[list], condition: Condition) -> None:
    label = (
        f"parkinson={condition.parkinson:g},stroke={condition.stroke:g},"
        f"tremor={condition.tremor:g},diabetes={condition.diabetes:g},ataxia={condition.ataxia:g}"
    )
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in rows:
            writer.writerow((*row, label))


class _Clock:
    def __init__(self):
        self.t = 0.0


def main() -> None:
    count = write_synthetic(Path("data/Synthetic"))
    print(f"Wrote {count} synthetic recordings to data/Synthetic")


if __name__ == "__main__":
    main()
