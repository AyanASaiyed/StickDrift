"""Synthetic apple and fishing recordings for the pattern model.

Each condition is one person. The apple file and the fishing file share the
same scores. Diabetes changes the apple reach only. Ataxia changes the fishing
path only. The fishing lane has no stored border: reached_l / reached_r is 1
while the cursor is inside the lane and 0 while it is outside. The cursor is
always written.

Folder names are the labels. Recorded folders such as "Diabetes Data" and
"Cerebellar ataxia" are different names, so they are not picked up here.
"""

import csv
import math
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HZ = 60
LANE_HALF = 0.10

APPLES_LEFT = (
    (0.42, -0.28),
    (-0.36, 0.18),
    (0.18, 0.40),
    (-0.48, -0.16),
    (0.52, 0.08),
    (0.02, -0.42),
)
APPLES_RIGHT = tuple((-x, y + 0.05) for x, y in APPLES_LEFT)

COLUMNS = (
    "t", "level", "phase",
    "lx", "ly", "rx", "ry",
    "tgt_lx", "tgt_ly", "tgt_rx", "tgt_ry",
    "reached_l", "reached_r",
    "cur_lx", "cur_ly", "cur_rx", "cur_ry",
)


@dataclass(frozen=True)
class Condition:
    folder: str
    parkinson: float
    stroke: float
    tremor: float
    diabetes: float = 0.0
    ataxia: float = 0.0
    weak_hand: str | None = None
    tremor_hand: str | None = None
    latency_s: float = 0.10
    move_s: float = 0.45
    gain_left: float = 1.0
    gain_right: float = 1.0
    stick_shake: float = 0.0
    tremor_hz: float = 6.5
    levels: tuple[str, ...] = ("apple", "fish")


def _person(
    folder: str,
    parkinson: float = 0.0,
    stroke: float = 0.0,
    tremor: float = 0.0,
    diabetes: float = 0.0,
    ataxia: float = 0.0,
    weak_hand: str | None = None,
) -> Condition:
    shared = _motion_strength(parkinson)
    sided = _motion_strength(stroke)
    shake = _motion_strength(tremor)
    gain_left = 1.0 - 0.22 * shared
    gain_right = 1.0 - 0.22 * shared
    if weak_hand == "left":
        gain_left *= 1.0 - 0.55 * sided
    elif weak_hand == "right":
        gain_right *= 1.0 - 0.55 * sided
    return Condition(
        folder,
        parkinson,
        stroke,
        tremor,
        diabetes=diabetes,
        ataxia=ataxia,
        weak_hand=weak_hand,
        latency_s=0.10 + 0.50 * shared + 0.12 * sided,
        move_s=0.40 + 0.80 * shared + 0.20 * sided,
        gain_left=gain_left,
        gain_right=gain_right,
        stick_shake=0.055 * shake,
        levels=_levels(parkinson, stroke, tremor, diabetes, ataxia),
    )


def _motion_strength(score: float) -> float:
    """How strongly a labeled score is acted. The label itself stays unchanged."""
    return (score / 100.0) * MOTION_SCALE


def _levels(parkinson: float, stroke: float, tremor: float, diabetes: float, ataxia: float) -> tuple[str, ...]:
    """Apple cannot show ataxia. Fishing cannot show diabetes. Rat is not generated."""
    normal = parkinson == stroke == tremor == diabetes == ataxia == 0
    levels = []
    if normal or parkinson or stroke or tremor or diabetes:
        levels.append("apple")
    if normal or parkinson or stroke or tremor or ataxia:
        levels.append("fish")
    return tuple(levels)


# A stored label of 100 is drawn with this fraction of the full cartoon.
# 0.5 makes today's half-strength movement the example for a score of 100,
# so a milder real play lands higher on the dashboard.
MOTION_SCALE = 0.5
_SEVERITIES = (25.0, 50.0, 75.0, 100.0)
_DISEASES = (
    ("Parkinson", "parkinson", None),
    ("Tremor", "tremor", None),
    ("Stroke Left", "stroke", "left"),
    ("Stroke Right", "stroke", "right"),
    ("Diabetes", "diabetes", None),
    ("Ataxia", "ataxia", None),
)


def _conditions() -> tuple[Condition, ...]:
    """Baseline, each disease at 25/50/75/100, and every pair at every strength pair."""
    found: list[Condition] = [_person("Baseline")]
    for name, kind, side in _DISEASES:
        for amount in _SEVERITIES:
            found.append(_person(f"{name} {int(amount)}", weak_hand=side, **{kind: amount}))
    for index, left in enumerate(_DISEASES):
        for right in _DISEASES[index + 1:]:
            if left[1] == "stroke" and right[1] == "stroke":
                continue
            side = left[2] or right[2]
            for left_amount in _SEVERITIES:
                for right_amount in _SEVERITIES:
                    folder = f"{left[0]} {int(left_amount)} + {right[0]} {int(right_amount)}"
                    scores = {left[1]: left_amount, right[1]: right_amount}
                    found.append(_person(folder, weak_hand=side, **scores))
    return tuple(found)


CONDITIONS = _conditions()


def write_synthetic(root: str | Path, apple_seeds: int = 1) -> int:
    """Write one apple file and one fishing file per condition. Returns the file count."""
    destination = Path(root)
    if destination.exists():
        shutil.rmtree(destination)
    count = 0
    for condition in CONDITIONS:
        for level in condition.levels:
            seeds = range(1, apple_seeds + 1) if level == "apple" else range(1, 2)
            for seed in seeds:
                folder = destination / condition.folder / f"{level}_s{seed}"
                folder.mkdir(parents=True)
                rows = _apple(condition, seed) if level == "apple" else _fish(condition, seed)
                _write(folder / "controller_data.csv", rows)
                count += 1
    return count


def _apple(condition: Condition, seed: int) -> list[list]:
    rng = np.random.default_rng(_seed(condition, seed))
    rows: list[list] = []
    clock = 0.0
    clock = _hold(rows, clock, 0.45, "apple", "", (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0))
    for index, (left_goal, right_goal) in enumerate(zip(APPLES_LEFT, APPLES_RIGHT, strict=True)):
        clock = _reach(rows, clock, rng, condition, index, "apple", "cue", left_goal, right_goal, diabetes=True)
        clock = _reach(
            rows, clock, rng, condition, index, "apple", "carry",
            (0.0, 0.15), (0.0, 0.15), diabetes=False, origin=(left_goal, right_goal),
        )
        clock = _hold(rows, clock, 0.30, "apple", "", (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0))
    return rows


def _fish(condition: Condition, seed: int) -> list[list]:
    rows: list[list] = []
    clock = 0.0
    for hand, sign in (("left", 1.0), ("right", -1.0)):
        clock = _hold(rows, clock, 0.40, "fish", "", (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0))
        duration = 8.0
        count = int(round(duration * HZ))
        for step in range(count):
            time_s = clock + step / HZ
            along = -0.75 + 1.50 * (step / max(count - 1, 1))
            center = (sign * along, 0.22 * math.sin(2.0 * math.pi * (0.55 + 0.15 * seed) * time_s))
            cursor = _fish_cursor(condition, hand, center, time_s)
            other = (0.0, 0.0)
            left_cur, right_cur = (cursor, other) if hand == "left" else (other, cursor)
            left_tgt, right_tgt = (center, None) if hand == "left" else (None, center)
            reached_l = _inside(left_cur, left_tgt)
            reached_r = _inside(right_cur, right_tgt)
            stick_l = _stick_command(condition, "left", left_cur, time_s, moving=hand == "left")
            stick_r = _stick_command(condition, "right", right_cur, time_s, moving=hand == "right")
            rows.append(_row(time_s, "fish", "track", stick_l, stick_r, left_tgt, right_tgt, left_cur, right_cur, reached_l, reached_r))
        clock += duration
    return rows


def _reach(rows, clock, rng, condition, index, level, phase, left_goal, right_goal, diabetes: bool, origin=None):
    start_left, start_right = ((0.0, 0.0), (0.0, 0.0)) if origin is None else origin
    duration = condition.latency_s + condition.move_s + (0.55 if diabetes and condition.diabetes else 0.20)
    count = max(2, int(round(duration * HZ)))
    for step in range(count):
        elapsed = step / HZ
        time_s = clock + elapsed
        left = _aimed(condition, "left", start_left, left_goal, elapsed, index, diabetes)
        right = _aimed(condition, "right", start_right, right_goal, elapsed, index, diabetes)
        left = _wobble(condition, "left", left, time_s)
        right = _wobble(condition, "right", right, time_s)
        stick_l = _stick_command(condition, "left", left, time_s, moving=elapsed > condition.latency_s)
        stick_r = _stick_command(condition, "right", right, time_s, moving=elapsed > condition.latency_s)
        rows.append(_row(
            time_s, level, phase, stick_l, stick_r, left_goal, right_goal, left, right, 0, 0, rng=rng,
        ))
    return clock + duration


def _aimed(condition, hand, start, goal, elapsed, index, diabetes: bool):
    gain = condition.gain_left if hand == "left" else condition.gain_right
    if elapsed < condition.latency_s:
        scale = 0.0
    else:
        unit = (elapsed - condition.latency_s) / condition.move_s
        scale = _ease(unit)
        if diabetes and condition.diabetes > 0.0:
            scale = _diabetes_scale(unit, _motion_strength(condition.diabetes), index)
    aimed = (
        start[0] + (goal[0] - start[0]) * gain * scale,
        start[1] + (goal[1] - start[1]) * gain * scale,
    )
    return aimed


def _diabetes_scale(unit: float, strength: float, index: int) -> float:
    """Go past the apple or stop short, then come back. The outbound speed stays ordinary."""
    miss = (1.15 + 0.55 * strength) if index % 2 == 0 else (0.45 - 0.25 * strength)
    if unit < 1.0:
        return miss * _ease(unit)
    correct = _ease(min(unit - 1.0, 1.0))
    return miss + (1.0 - miss) * correct


def _fish_cursor(condition, hand, center, time_s):
    gain = condition.gain_left if hand == "left" else condition.gain_right
    point = (center[0] * gain, center[1] * gain)
    if condition.ataxia <= 0.0:
        return _wobble(condition, hand, point, time_s)
    amount = 0.06 + 0.28 * _motion_strength(condition.ataxia)
    side = amount * math.sin(2.0 * math.pi * 0.28 * time_s)
    lead = amount * 0.7 * math.sin(2.0 * math.pi * 0.18 * time_s + 0.6)
    tx, ty = center
    radius = math.hypot(tx, ty) or 1.0
    ux, uy = tx / radius, ty / radius
    offset = (ux * lead - uy * side, uy * lead + ux * side)
    return _wobble(condition, hand, (point[0] + offset[0], point[1] + offset[1]), time_s)


def _wobble(condition, hand, point, time_s):
    if condition.stick_shake <= 0.0:
        return point
    cycle = 2.0 * math.pi * condition.tremor_hz * time_s
    shift = 0.4 if hand == "right" else 0.0
    return (
        point[0] + condition.stick_shake * 0.35 * math.sin(cycle + shift),
        point[1] + condition.stick_shake * 0.22 * math.cos(cycle + shift),
    )


def _stick_command(condition, hand, cursor, time_s, moving: bool):
    if not moving:
        base = (0.0, 0.0)
    else:
        base = (max(-1.0, min(1.0, cursor[0])), max(-1.0, min(1.0, cursor[1] * 0.5)))
    if condition.stick_shake <= 0.0:
        return base
    cycle = 2.0 * math.pi * condition.tremor_hz * time_s
    return (
        max(-1.0, min(1.0, base[0] + condition.stick_shake * math.sin(cycle))),
        max(-1.0, min(1.0, base[1] + condition.stick_shake * 0.7 * math.cos(cycle))),
    )


def _inside(cursor, target) -> int:
    if target is None:
        return 0
    return 1 if math.dist(cursor, target) <= LANE_HALF else 0


def _hold(rows, clock, duration, level, phase, left_tgt, right_tgt, left_cur, right_cur) -> float:
    count = max(2, int(round(duration * HZ)))
    for step in range(count):
        time_s = clock + step / HZ
        rows.append(_row(time_s, level, phase, (0.0, 0.0), (0.0, 0.0), left_tgt, right_tgt, left_cur, right_cur, 0, 0))
    return clock + duration


def _row(time_s, level, phase, stick_l, stick_r, left_tgt, right_tgt, left_cur, right_cur, reached_l, reached_r, rng=None):
    del rng
    return [
        round(time_s, 4),
        level,
        phase,
        _num(stick_l[0]), _num(stick_l[1]), _num(stick_r[0]), _num(stick_r[1]),
        *_point(left_tgt),
        *_point(right_tgt),
        reached_l,
        reached_r,
        _num(left_cur[0]), _num(left_cur[1]), _num(right_cur[0]), _num(right_cur[1]),
    ]


def _point(point) -> tuple[str, str]:
    if point is None:
        return "", ""
    return _num(point[0]), _num(point[1])


def _num(value: float) -> str:
    return f"{value:.4f}"


def _ease(unit: float) -> float:
    unit = min(max(unit, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * unit)


def _seed(condition: Condition, seed: int) -> int:
    return seed + sum(ord(char) for char in condition.folder)


def _write(path: Path, rows: list[list]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        writer.writerows(rows)


def main() -> None:
    count = write_synthetic(Path("data/Synthetic"))
    print(f"Wrote {count} synthetic recordings to data/Synthetic")


if __name__ == "__main__":
    main()
