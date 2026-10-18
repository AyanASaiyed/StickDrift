"""Read recordings whose folder is the pattern label.

Played recordings under data/new_game_data:

- Baseline Data: every score 0
- Parkinsons Data: parkinson 100, everything else 0
- Tremor Data: essential tremor 100, everything else 0
- Stroke Data/Left Weak or Right Weak: stroke 100 on that hand, everything else 0
- Diabetes Data: diabetes 100, everything else 0
- Cerebellar ataxia: ataxia 100, everything else 0

Played recordings under data/ultimate_data use the names Baseline, Parkinsons,
Tremor, Stroke/Left Hand Weak or Right Hand Weak, and Cerebral Ataxia, and
carry gyro and accelerometer columns from the DualSense.

Diabetes is trained only on apple files. Ataxia is trained only on fishing
files. A 0 on the other game is masked, not treated as a real negative.
Synthetic mixes use the folder names in `tcn.synthetic.CONDITIONS`.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from tcn.config import CHANNELS
from tcn.recording import Example, Recording, RecordingError
from tcn.synthetic import CONDITIONS

# new_game_data names, then the ultimate_data names (recorded with gyro and accelerometer)
_BASELINE = frozenset({"Baseline Data", "Baseline"})
_PARKINSON = frozenset({"Parkinsons Data", "Parkinsons"})
_TREMOR = frozenset({"Tremor Data", "Tremor"})
_DIABETES = frozenset({"Diabetes Data"})
_ATAXIA = frozenset({"Cerebellar ataxia", "Cerebral Ataxia"})
_LEFT = frozenset({"Left Weak", "Left Hand Weak"})
_RIGHT = frozenset({"Right Weak", "Right Hand Weak"})


def load_examples(root: str | Path) -> list[Example]:
    """Load every `controller_data.csv` under `root` and label it from its folder."""
    folder = Path(root)
    paths = sorted(folder.rglob("controller_data.csv"))
    if not paths:
        raise RecordingError(f"{folder} has no controller_data.csv recordings.")
    return [_example(folder, path) for path in paths]


def _example(root: Path, path: Path) -> Example:
    label = _targets(path)
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    name = str(path.relative_to(root))
    return Example(
        Recording.from_rows(rows, name),
        label.parkinson,
        label.stroke,
        label.tremor,
        weak_hand=label.weak_hand,
        tremor_hand=label.tremor_hand,
        diabetes=label.diabetes,
        ataxia=label.ataxia,
    )


@dataclass(frozen=True)
class _FolderLabel:
    parkinson: float
    stroke: float
    tremor: float
    diabetes: float | None = None
    ataxia: float | None = None
    weak_hand: str | None = None
    tremor_hand: str | None = None


def _targets(path: Path) -> _FolderLabel:
    parts = set(path.parts)
    for condition in CONDITIONS:
        if condition.folder in parts:
            return _FolderLabel(
                condition.parkinson,
                condition.stroke,
                condition.tremor,
                diabetes=condition.diabetes,
                ataxia=condition.ataxia,
                weak_hand=condition.weak_hand,
                tremor_hand=condition.tremor_hand,
            )
    if parts & _LEFT:
        return _played(0.0, 100.0, 0.0, weak_hand="left")
    if parts & _RIGHT:
        return _played(0.0, 100.0, 0.0, weak_hand="right")
    if parts & _PARKINSON:
        return _played(100.0, 0.0, 0.0)
    if parts & _TREMOR:
        return _played(0.0, 0.0, 100.0)
    if parts & _DIABETES:
        return _played(0.0, 0.0, 0.0, diabetes=100.0)
    if parts & _ATAXIA:
        return _played(0.0, 0.0, 0.0, ataxia=100.0)
    if parts & _BASELINE:
        return _played(0.0, 0.0, 0.0)
    raise RecordingError(
        f"{path} is not under Baseline Data, Parkinsons Data, Tremor Data, "
        "Stroke Data/Left Weak or Right Weak, Diabetes Data, Cerebellar ataxia, "
        "or a Synthetic condition folder."
    )


def _played(
    parkinson: float,
    stroke: float,
    tremor: float,
    diabetes: float = 0.0,
    ataxia: float = 0.0,
    weak_hand: str | None = None,
) -> _FolderLabel:
    """One recorded condition at full strength, and none of the others."""
    return _FolderLabel(
        parkinson,
        stroke,
        tremor,
        diabetes=diabetes,
        ataxia=ataxia,
        weak_hand=weak_hand,
    )


def _labelled_examples(folder: Path) -> list[Example]:
    """Like load_examples, but skip visits saved outside a label folder (a trial lobby run)."""
    examples = []
    for path in sorted(folder.rglob("controller_data.csv")):
        try:
            examples.append(_example(folder, path))
        except RecordingError as error:
            if "is not under" not in str(error):
                raise
            print(f"Skipping unlabelled recording {path.relative_to(folder)}")
    return examples


# Gyro shake (residual RMS, raw DualSense units) of the played recordings: healthy and
# Parkinson's play is about 20-55, real tremor is 410-1040. With only those two
# groups the model called anything above healthy a full tremor, so a hand that shakes
# a little scored like one that shakes hard. These copies fill in the middle.
SHAKE_NONE = 60.0  # at or below this, no tremor
SHAKE_FULL = 450.0  # at or above this, full tremor
SHAKE_LADDER = (70.0, 110.0, 160.0, 230.0, 330.0)
_GYRO = [CHANNELS.index(name) for name in ("gyro_x", "gyro_y", "gyro_z")]


def _shake(values: np.ndarray, hz: float) -> float:
    window = max(3, int(round(0.16 * hz)))
    kernel = np.ones(window) / window
    parts = [values[:, c] - np.convolve(values[:, c], kernel, mode="same") for c in _GYRO]
    return float(np.sqrt(np.mean([part.std() ** 2 for part in parts])))


def shake_label(shake: float) -> float:
    """How much tremor a gyro shake of this size is, from 0 to 100."""
    return float(np.clip((shake - SHAKE_NONE) / (SHAKE_FULL - SHAKE_NONE), 0.0, 1.0) * 100.0)


def weaker_tremors(example: Example) -> list[Example]:
    """Copies of a full-tremor recording with the shake scaled down, each labelled by its size."""
    old = example.recording
    if float(example.target[2]) < 100.0 or not np.abs(old.values[:, _GYRO]).max() > 0.0:
        return []
    hz = len(old.time_s) / max(float(old.time_s[-1] - old.time_s[0]), 1e-6)
    window = max(3, int(round(0.16 * hz)))
    kernel = np.ones(window) / window
    current = _shake(old.values, hz)
    copies = []
    for target in SHAKE_LADDER:
        if target >= current:
            continue
        scale = target / current
        values = old.values.copy()
        for c in _GYRO:
            slow = np.convolve(values[:, c], kernel, mode="same")
            values[:, c] = slow + scale * (values[:, c] - slow)
        twin = Recording(
            old.time_s, values, old.name, cues=old.cue_s, task_spans=old.task_spans,
            targets=old.targets, cursors=old.cursors, bounds=old.bounds, activity=old.activity,
        )
        copies.append(Example(
            twin, example.target[0], example.target[1], shake_label(target),
            weak_hand=example.weak_hand, tremor_hand=example.tremor_hand,
            diabetes=example.diabetes, ataxia=example.ataxia, activity=example.activity,
        ))
    return copies


def load_training_examples(root: str | Path = "data") -> list[Example]:
    """Apple and fishing recordings, played (new_game_data, ultimate_data) and synthetic. Rat files are left out."""
    base = Path(root)
    folders = [base / "new_game_data", base / "ultimate_data", base / "Synthetic"]
    examples: list[Example] = []
    for folder in folders:
        if not folder.is_dir() or not any(folder.rglob("controller_data.csv")):
            continue
        examples.extend(
            example for example in _labelled_examples(folder) if example.activity != "rat"
        )
    for example in list(examples):
        examples.extend(weaker_tremors(example))
    if not examples:
        raise RecordingError(f"{base} has no new-game or synthetic recordings.")
    return examples
