"""Synthetic apple and fishing recordings for the pattern model.

Each condition is one simulated player. The level layouts (where each apple
appears, where the basket is, how the fishing lane moves) are replayed from
the played Baseline recordings, so the games look like the real ones.

The stick sets the hand's speed, as in the real games: the cursor moves by
GAIN * stick per second. A player pushes the stick toward where they are
aiming, mostly at full tilt, and lets go near the target. The conditions
change how they push, using what the played recordings show:

- Parkinson: late starts, short broken pushes with pauses, more jitter, both hands.
- Stroke: the same broken, late pushes, on the weak hand only.
- Essential tremor: a 6-7.5 Hz shake added to the stick while pushing.
- Diabetes (apple only): the reach passes the apple or stops short, pauses, then corrects.
- Ataxia (fishing only): the aim wanders slowly off the lane, with choppier pushes.

The fishing lane has no stored border: reached_l / reached_r is 1 while the
cursor is inside the lane and 0 while it is outside. On apple, reached is 1
while that hand carries an apple. Folder names are the labels. Recorded
folders such as "Diabetes Data" and "Cerebellar ataxia" are different names,
so they are not picked up here.
"""

import csv
import math
import shutil
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np

HZ = 100
LANE_HALF = 0.10
REACH = 0.08
GAIN = {"apple": 0.87, "fish": 0.60}
TEMPLATES = Path("data/new_game_data/Baseline Data")

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
    return Condition(
        folder, parkinson, stroke, tremor, diabetes=diabetes, ataxia=ataxia, weak_hand=weak_hand,
        levels=_levels(parkinson, stroke, tremor, diabetes, ataxia),
    )


def _levels(parkinson: float, stroke: float, tremor: float, diabetes: float, ataxia: float) -> tuple[str, ...]:
    """Apple cannot show ataxia. Fishing cannot show diabetes. Rat is not generated."""
    normal = parkinson == stroke == tremor == diabetes == ataxia == 0
    levels = []
    if normal or parkinson or stroke or tremor or diabetes:
        levels.append("apple")
    if normal or parkinson or stroke or tremor or ataxia:
        levels.append("fish")
    return tuple(levels)


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


# ---------------------------------------------------------------- level layouts

@dataclass(frozen=True)
class _Apple:
    duration: float
    first_cue: dict[str, float]
    apples: dict[str, list[tuple[float, float]]]
    basket: tuple[float, float]


@dataclass(frozen=True)
class _Fish:
    time_s: np.ndarray
    targets: dict[str, np.ndarray]  # hand -> (n, 2), NaN while that hand has no lane


def _read(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _value(row: dict, key: str) -> float:
    text = row.get(key)
    return float(text) if text not in (None, "") else math.nan


def _apple_layout(path: Path) -> _Apple:
    rows = _read(path)
    apples: dict[str, list[tuple[float, float]]] = {"left": [], "right": []}
    first: dict[str, float] = {}
    basket = (0.0, 0.351)
    for hand, side in (("left", "l"), ("right", "r")):
        last = None
        for row in rows:
            point = (_value(row, f"tgt_{side}x"), _value(row, f"tgt_{side}y"))
            if math.isnan(point[0]) or point == last:
                last = point if not math.isnan(point[0]) else last
                continue
            last = point
            if row["phase"] == "carry" or abs(point[0]) < 1e-6 and point[1] > 0.3:
                basket = point
                continue
            apples[hand].append(point)
            first.setdefault(hand, float(row["t"]))
    return _Apple(float(rows[-1]["t"]), first, apples, basket)


def _fish_layout(path: Path) -> _Fish:
    rows = _read(path)
    time_s = np.array([float(row["t"]) for row in rows])
    targets = {
        hand: np.array([[_value(row, f"tgt_{side}x"), _value(row, f"tgt_{side}y")] for row in rows])
        for hand, side in (("left", "l"), ("right", "r"))
    }
    return _Fish(time_s, targets)


@cache
def _layouts(level: str) -> list:
    name = "level_1_apple" if level == "apple" else "level_2_fish"
    paths = sorted(TEMPLATES.rglob(f"{name}/controller_data.csv"))
    if not paths:
        raise FileNotFoundError(f"No {name} recordings under {TEMPLATES} to take the layout from.")
    return [_apple_layout(path) if level == "apple" else _fish_layout(path) for path in paths]


# ---------------------------------------------------------------- the player

@dataclass
class _Hand:
    """How one hand pushes the stick. Built from the condition and a little per-player spread."""

    latency_s: float
    push_s: float  # math.inf for one smooth push
    gap_s: float
    jitter: float
    tremor_amp: float
    tremor_hz: float
    tremor_phase: float
    overshoot: float  # diabetes strength, 0..1
    wander: float  # ataxia lane departure, in cursor units
    wander_hz: tuple[float, float]
    stiffness: float  # how close to the target the push starts to ease off


def _hands(condition: Condition, rng: np.random.Generator, level: str) -> dict[str, _Hand]:
    def spread(value: float, amount: float = 0.15) -> float:
        return value * float(rng.uniform(1.0 - amount, 1.0 + amount))

    pd = condition.parkinson / 100.0
    tr = condition.tremor / 100.0
    db = condition.diabetes / 100.0
    ax = condition.ataxia / 100.0
    hands = {}
    for hand in ("left", "right"):
        weak = condition.stroke / 100.0 if condition.weak_hand == hand else 0.0
        broken = max(pd, weak, 0.6 * ax)
        if level == "fish":
            broken *= 0.2  # played recordings still follow the lane; only apple pushes break up
        hands[hand] = _Hand(
            latency_s=spread(0.15 + 0.35 * pd + 0.30 * weak),
            push_s=math.inf if broken == 0 else spread(1.3 - 0.95 * broken),
            gap_s=spread(0.06 + 0.18 * broken),
            jitter=spread(0.012 + 0.045 * pd + 0.03 * weak),
            tremor_amp=spread(0.17 * tr),
            tremor_hz=float(rng.uniform(6.0, 7.5)),
            tremor_phase=float(rng.uniform(0.0, 2.0 * math.pi)),
            overshoot=db,
            wander=spread(0.008 + 0.022 * ax) if ax else 0.0,
            wander_hz=(float(rng.uniform(0.18, 0.3)), float(rng.uniform(0.32, 0.45))),
            stiffness=spread(2.2, 0.25),
        )
    return hands


class _Player:
    def __init__(self, hand: _Hand, gain: float, rng: np.random.Generator, start: tuple[float, float]):
        self.p = hand
        self.gain = gain
        self.rng = rng
        self.cursor = np.array(start, dtype=float)
        self.goal_since = 0.0
        self.cycle = 0.0
        self.aim_override: np.ndarray | None = None
        self.paused_until = -1.0

    def new_goal(self, time_s: float) -> None:
        self.goal_since = time_s
        self.cycle = 0.0
        self.aim_override = None

    def step(self, time_s: float, dt: float, aim: np.ndarray | None, lead: np.ndarray | None = None) -> np.ndarray:
        stick = np.zeros(2)
        if aim is not None and time_s - self.goal_since >= self.p.latency_s and time_s >= self.paused_until:
            error = aim - self.cursor
            distance = float(np.hypot(*error))
            pushing = True
            if math.isfinite(self.p.push_s):
                self.cycle += dt
                period = self.p.push_s + self.p.gap_s
                pushing = (self.cycle % period) < self.p.push_s
            if pushing and distance > 1e-4:
                # ease off near the target but keep a firm push, and let go once on it
                size = 0.0 if distance < 0.04 else min(1.0, max(0.3, self.p.stiffness * distance))
                stick = error / distance * size
                if lead is not None:
                    stick = stick + lead / self.gain
                stick = stick + self.rng.normal(0.0, self.p.jitter, 2)
                if self.p.tremor_amp:
                    phase = 2.0 * math.pi * self.p.tremor_hz * time_s + self.p.tremor_phase
                    stick = stick + self.p.tremor_amp * np.array([math.sin(phase), 0.7 * math.cos(phase)])
        size = float(np.hypot(*stick))
        if size > 1.05:  # the stick moves inside a circle, not a square
            stick = stick / size * 1.05
        stick = np.clip(stick, -1.0, 1.0)
        self.cursor = np.clip(self.cursor + self.gain * stick * dt, -1.0, 1.0)
        return stick


# ---------------------------------------------------------------- the levels

def _apple(condition: Condition, seed: int) -> list[list]:
    rng = np.random.default_rng(_seed(condition, seed))
    layouts = _layouts("apple")
    layout = layouts[seed % len(layouts)]
    hands = _hands(condition, rng, "apple")
    players = {hand: _Player(hands[hand], GAIN["apple"], rng, layout.basket) for hand in hands}
    # each hand: waiting for its first apple, reaching an apple, or carrying one to the basket
    state = {hand: {"stage": "wait", "index": 0, "goal": None, "start": None} for hand in hands}
    rows = []
    dt = 1.0 / HZ
    for step in range(int(layout.duration * HZ)):
        time_s = step * dt
        sticks, targets, reached = {}, {}, {}
        for hand, player in players.items():
            s = state[hand]
            apples = layout.apples[hand]
            if s["stage"] == "wait" and apples and time_s >= layout.first_cue.get(hand, math.inf):
                s.update(stage="cue", goal=np.array(apples[0]), start=player.cursor.copy())
                player.new_goal(time_s)
                _plan_miss(player, s, hands[hand], rng)
            aim = None
            if s["stage"] in ("cue", "carry"):
                aim = s["goal"] if player.aim_override is None else player.aim_override
                if player.aim_override is not None and np.hypot(*(player.cursor - player.aim_override)) < REACH:
                    # passed the apple or stopped short: pause, then correct
                    player.aim_override = None
                    player.paused_until = time_s + 0.08 + 0.15 * hands[hand].overshoot
                    aim = s["goal"]
            sticks[hand] = player.step(time_s, dt, aim)
            targets[hand] = None if s["goal"] is None else tuple(s["goal"])
            if s["stage"] == "cue" and player.aim_override is None and np.hypot(*(player.cursor - s["goal"])) < REACH:
                s.update(stage="carry", goal=np.array(layout.basket))
                player.new_goal(time_s)
            elif s["stage"] == "carry" and np.hypot(*(player.cursor - s["goal"])) < REACH:
                s["index"] += 1
                next_apple = apples[s["index"] % len(apples)]
                s.update(stage="cue", goal=np.array(next_apple), start=player.cursor.copy())
                player.new_goal(time_s)
                _plan_miss(player, s, hands[hand], rng)
            reached[hand] = 1 if s["stage"] == "carry" else 0
        stages = {state[hand]["stage"] for hand in hands}
        phase = "cue" if "cue" in stages else "carry" if "carry" in stages else ""
        rows.append(_row(time_s, "apple", phase, sticks, targets, players, reached))
    return rows


def _plan_miss(player: _Player, s: dict, hand: _Hand, rng: np.random.Generator) -> None:
    """Diabetes: aim past the apple or short of it first."""
    if not hand.overshoot:
        return
    long_way = bool(rng.random() < 0.5)
    miss = 1.25 + 0.45 * hand.overshoot if long_way else 0.6 - 0.3 * hand.overshoot
    player.aim_override = np.clip(s["start"] + (s["goal"] - s["start"]) * miss, -1.0, 1.0)


def _fish(condition: Condition, seed: int) -> list[list]:
    rng = np.random.default_rng(_seed(condition, seed))
    layouts = _layouts("fish")
    layout = layouts[seed % len(layouts)]
    hands = _hands(condition, rng, "fish")
    players = {hand: _Player(hands[hand], GAIN["fish"], rng, (0.0, 0.0)) for hand in hands}
    active = {hand: False for hand in hands}
    rows = []
    previous_time = layout.time_s[0]
    for index, time_s in enumerate(layout.time_s):
        dt = max(float(time_s - previous_time), 1e-3) if index else 1.0 / HZ
        previous_time = time_s
        sticks, targets, reached = {}, {}, {}
        for hand, player in players.items():
            target = layout.targets[hand][index]
            has = bool(np.isfinite(target).all())
            if has and not active[hand]:
                player.cursor = target + rng.normal(0.0, 0.02, 2)
                player.new_goal(float(time_s))
            active[hand] = has
            aim, lead = None, None
            if has:
                aim = target.copy()
                lead = _lane_speed(layout, hand, index)
                p = hands[hand]
                if p.wander:
                    aim = aim + p.wander * np.array([
                        math.sin(2 * math.pi * p.wander_hz[0] * time_s),
                        0.8 * math.sin(2 * math.pi * p.wander_hz[1] * time_s + 0.6),
                    ])
            sticks[hand] = player.step(float(time_s), dt, aim, lead)
            targets[hand] = tuple(target) if has else None
            reached[hand] = 1 if has and np.hypot(*(player.cursor - target)) <= LANE_HALF else 0
        phase = "track" if any(active.values()) else ""
        rows.append(_row(float(time_s), "fish", phase, sticks, targets, players, reached))
    return rows


def _lane_speed(layout: _Fish, hand: str, index: int, window_s: float = 0.25) -> np.ndarray | None:
    """The lane's speed over the next quarter second. The log repeats a position, then jumps."""
    ahead = int(np.searchsorted(layout.time_s, layout.time_s[index] + window_s))
    ahead = min(ahead, len(layout.time_s) - 1)
    later, now = layout.targets[hand][ahead], layout.targets[hand][index]
    span = float(layout.time_s[ahead] - layout.time_s[index])
    if span <= 0 or not (np.isfinite(later).all() and np.isfinite(now).all()):
        return None
    return (later - now) / span


# ---------------------------------------------------------------- files

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


def _row(time_s, level, phase, sticks, targets, players, reached) -> list:
    left, right = sticks["left"], sticks["right"]
    return [
        round(time_s, 4), level, phase,
        _num(left[0]), _num(left[1]), _num(right[0]), _num(right[1]),
        *_point(targets["left"]), *_point(targets["right"]),
        reached["left"], reached["right"],
        _num(players["left"].cursor[0]), _num(players["left"].cursor[1]),
        _num(players["right"].cursor[0]), _num(players["right"].cursor[1]),
    ]


def _point(point) -> tuple[str, str]:
    if point is None:
        return "", ""
    return _num(point[0]), _num(point[1])


def _num(value: float) -> str:
    return f"{value:.4f}"


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
