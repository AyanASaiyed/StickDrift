"""Synthetic garden recordings for the pattern model.

The apple, butterfly, and watering targets match the game. What changes is
how the hand travels: late, slow, smaller, steadily shaky, one-sided, or a
single jerk. Folder names are the labels.
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

# Same course as Controller Data - Zain/Games/garden.py.
APPLES = ((270, 0.60), (180, 0.40), (135, 0.60), (315, 0.40), (90, 0.40), (225, 0.60))
FLY_R0, FLY_RA, FLY_LOBES, FLY_LAP = 0.40, 0.06, 2, 12.0
WATER_CTRL = ((-0.55, 0.25), (-0.30, -0.10), (0.0, 0.20), (0.30, -0.10), (0.55, 0.20))
WATER_SECS = 15.0

COLUMNS = (
    "t", "lx", "ly", "rx", "ry",
    "gyro_x", "gyro_y", "gyro_z",
    "acc_x", "acc_y", "acc_z",
    "phase", "label",
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


def _recording(condition: Condition, level: str, seed: int) -> list[tuple]:
    rng = np.random.default_rng(seed + sum(ord(char) for char in condition.folder))
    rows: list[tuple] = []
    clock = _Clock()
    if level == "apples":
        _rest(rows, clock, rng, condition, 0.45)
        for index, (deg, dist) in enumerate(APPLES):
            target = _polar(deg, dist)
            shrink = condition.shrink ** index
            _reach_pair(rows, clock, rng, condition, target, shrink, jerk=condition.jerk and index == 0)
            _return_pair(rows, clock, rng, condition, target, shrink)
            _rest(rows, clock, rng, condition, 0.35)
        return rows
    target_fn = _fly if level.startswith("butterfly") else _water
    hand = "left" if level.endswith("left") else "right" if level.endswith("right") else "both"
    duration = FLY_LAP if level.startswith("butterfly") else WATER_SECS
    _rest(rows, clock, rng, condition, 0.40)
    _track(rows, clock, rng, condition, target_fn, hand, duration)
    return rows


def _reach_pair(rows, clock, rng, condition, target, shrink, jerk: bool) -> None:
    duration = condition.latency_s + condition.move_s + 0.28
    jerk_at = condition.latency_s + condition.move_s * 0.55

    def place(elapsed: float) -> tuple[float, float, float, float]:
        left = _hand_point("left", target, condition, shrink, elapsed, condition.latency_s, condition.move_s, clock.t)
        right = _hand_point("right", (-target[0], target[1]), condition, shrink, elapsed, condition.latency_s, condition.move_s, clock.t)
        return (*left, *right)

    _emit(rows, clock, rng, condition, duration, "cue", place, jerk_at if jerk else None)


def _return_pair(rows, clock, rng, condition, target, shrink) -> None:
    duration = 0.35

    def place(elapsed: float) -> tuple[float, float, float, float]:
        ease = 1.0 - _ease(elapsed / duration)
        left = _scaled("left", target, condition, shrink, ease)
        right = _scaled("right", (-target[0], target[1]), condition, shrink, ease)
        return (*left, *right)

    _emit(rows, clock, rng, condition, duration, "return", place, None)


def _track(rows, clock, rng, condition, target_fn, hand: str, duration: float) -> None:
    elapsed = 0.0
    while elapsed < duration - 0.05:
        step = min(condition.move_s, duration - elapsed)
        goals = {
            "left": target_fn(elapsed + step),
            "right": _mirror(target_fn(elapsed + step)),
        }
        if hand == "left":
            goals["right"] = (0.0, 0.0)
        elif hand == "right":
            goals["left"] = (0.0, 0.0)

        def place(local: float, goals=goals, step=step) -> tuple[float, float, float, float]:
            ease = _ease(local / step)
            left = _scaled("left", goals["left"], condition, 1.0, ease, clock.t)
            right = _scaled("right", goals["right"], condition, 1.0, ease, clock.t)
            return (*left, *right)

        _emit(rows, clock, rng, condition, step, "track", place, None)
        elapsed += step
        rest = min(0.22, duration - elapsed)
        if rest > 0.05:
            hold = (
                *_scaled("left", goals["left"], condition, 1.0, 1.0),
                *_scaled("right", goals["right"], condition, 1.0, 1.0),
            )
            _emit(rows, clock, rng, condition, rest, "track", lambda _local, hold=hold: hold, None)
            elapsed += rest


def _rest(rows, clock, rng, condition, duration: float) -> None:
    _emit(rows, clock, rng, condition, duration, "wait", lambda _elapsed: (0.0, 0.0, 0.0, 0.0), None)


def _emit(rows, clock, rng, condition, duration: float, phase: str, place, jerk_at) -> None:
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
        rows.append((
            round(clock.t, 4),
            _stick(lx), _stick(ly), _stick(rx), _stick(ry),
            int(round(gyro[0])), int(round(gyro[1])), int(round(gyro[2])),
            int(round(rng.normal(0, 30))),
            int(round(7800 + rng.normal(0, 40))),
            int(round(1340 + rng.normal(0, 30))),
            phase,
        ))
        clock.t += 1.0 / HZ


def _hand_point(hand, target, condition, shrink, elapsed, latency, move_s, time_s):
    if condition.still_hand == hand:
        return 0.0, 0.0
    if elapsed < latency:
        base = (0.0, 0.0)
    else:
        base = _scaled(hand, target, condition, shrink, _ease((elapsed - latency) / move_s))
    return base[0] + _wobble(time_s, hand)[0], base[1] + _wobble(time_s, hand)[1]


def _scaled(hand, target, condition, shrink, ease, time_s=None):
    if condition.still_hand == hand:
        return 0.0, 0.0
    gain = condition.gain_left if hand == "left" else condition.gain_right
    point = (target[0] * gain * shrink * ease, target[1] * gain * shrink * ease)
    if time_s is None:
        return point
    wobble = _wobble(time_s, hand)
    return point[0] + wobble[0], point[1] + wobble[1]


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
    envelope = _jerk_envelope(elapsed, center)
    return np.array([180.0, 90.0, 40.0]) * envelope


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


def _polar(deg: float, dist: float) -> tuple[float, float]:
    angle = math.radians(deg)
    return dist * math.cos(angle), dist * math.sin(angle)


def _mirror(point: tuple[float, float]) -> tuple[float, float]:
    return -point[0], point[1]


def _fly(time_s: float) -> tuple[float, float]:
    theta = 2 * math.pi * min(max(time_s, 0.0), FLY_LAP) / FLY_LAP
    radius = FLY_R0 + FLY_RA * math.sin(FLY_LOBES * theta)
    return radius * math.cos(theta), radius * math.sin(theta)


def _water(time_s: float) -> tuple[float, float]:
    spans = _water_spans()
    unit = min(max(time_s / WATER_SECS, 0.0), 1.0) * (len(spans) - 1)
    index = min(int(unit), len(spans) - 2)
    mix = unit - index
    start, end = spans[index], spans[index + 1]
    return start[0] + (end[0] - start[0]) * mix, start[1] + (end[1] - start[1]) * mix


def _water_spans() -> list[tuple[float, float]]:
    controls = WATER_CTRL
    dense = []
    for index in range(len(controls) - 1):
        p0 = controls[max(index - 1, 0)]
        p1 = controls[index]
        p2 = controls[index + 1]
        p3 = controls[min(index + 2, len(controls) - 1)]
        dense.extend(_catmull(p0, p1, p2, p3, step / 20) for step in range(20))
    dense.append(controls[-1])
    lengths = [0.0]
    for start, end in zip(dense, dense[1:]):
        lengths.append(lengths[-1] + math.dist(start, end))
    spans = []
    cursor = 0
    for step in range(80):
        target = lengths[-1] * step / 79
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


def _write(path: Path, rows: list[tuple], condition: Condition) -> None:
    label = f"parkinson={condition.parkinson:g},stroke={condition.stroke:g},tremor={condition.tremor:g}"
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
