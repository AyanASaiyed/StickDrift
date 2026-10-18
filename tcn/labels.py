"""Read recordings whose folder is the pattern label.

Played recordings under data/new_game_data:

- Baseline Data: every score 0
- Parkinsons Data: parkinson 100, everything else 0
- Tremor Data: essential tremor 100, everything else 0
- Stroke Data/Left Weak or Right Weak: stroke 100 on that hand, everything else 0
- Diabetes Data: diabetes 100, everything else 0
- Cerebellar ataxia: ataxia 100, everything else 0

Diabetes is trained only on apple files. Ataxia is trained only on fishing
files. A 0 on the other game is masked, not treated as a real negative.
Synthetic mixes use the folder names in `tcn.synthetic.CONDITIONS`.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from tcn.recording import Example, Recording, RecordingError
from tcn.synthetic import CONDITIONS

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
        f"{path} is not under Baseline, Parkinsons, Tremor, "
        "Stroke/Left Hand Weak or Right Hand Weak, Diabetes Data, Cerebral Ataxia, "
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


def load_training_examples(root: str | Path = "data") -> list[Example]:
    """Apple and fishing recordings in data/ultimate_data.

    Rat files and cerebral-ataxia visits are left out. Diabetes stays in the
    network but these recordings label it 0.
    """
    folder = Path(root) / "ultimate_data"
    if not folder.is_dir() or not any(folder.rglob("controller_data.csv")):
        raise RecordingError(f"{folder} has no recorded controller files.")
    examples = [
        example
        for example in load_examples(folder)
        if example.activity != "rat" and not set(Path(example.recording.name).parts) & _ATAXIA
    ]
    if not examples:
        raise RecordingError(f"{folder} has no apple or fishing recordings.")
    return examples
