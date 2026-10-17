"""Read the garden recordings whose folder is the pattern label.

Played recordings use these folders:

- Baseline Data: parkinson, stroke, and essential tremor 0
- Parkinsons Data: parkinson 100
- Tremor Data: essential tremor 100
- Stroke Data/Left Weak: stroke 100 on the left hand
- Stroke Data/Right Weak: stroke 100 on the right hand

Diabetes and ataxia are absent on played files. Absent is not 0: those terms
are masked out of the loss. Synthetic recordings use the folder names in
`tcn.synthetic.CONDITIONS`. A mix folder carries more than one score above zero.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from tcn.recording import Example, Recording, RecordingError
from tcn.synthetic import CONDITIONS

_BASELINE = "Baseline Data"
_PARKINSON = "Parkinsons Data"
_TREMOR = "Tremor Data"
_LEFT = "Left Weak"
_RIGHT = "Right Weak"


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
    if _LEFT in parts:
        return _FolderLabel(0.0, 100.0, 0.0, weak_hand="left")
    if _RIGHT in parts:
        return _FolderLabel(0.0, 100.0, 0.0, weak_hand="right")
    if _PARKINSON in parts:
        return _FolderLabel(100.0, 0.0, 0.0)
    if _TREMOR in parts:
        return _FolderLabel(0.0, 0.0, 100.0)
    if _BASELINE in parts:
        return _FolderLabel(0.0, 0.0, 0.0)
    raise RecordingError(
        f"{path} is not under Baseline Data, Parkinsons Data, Tremor Data, "
        "Stroke Data/Left Weak or Right Weak, or a Synthetic condition folder."
    )
