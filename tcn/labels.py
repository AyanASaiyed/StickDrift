"""Read the garden recordings whose folder is the pattern label.

Played recordings use these folders:

- Baseline Data: all three scores 0
- Parkinsons Data: parkinson 100
- Tremor Data: essential tremor 100
- Stroke Data/Left Weak: stroke 100 on the left hand
- Stroke Data/Right Weak: stroke 100 on the right hand

Synthetic recordings use the folder names in `tcn.synthetic.CONDITIONS`.
A mix folder carries more than one score above zero.
"""

import csv
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
    parkinson, stroke, tremor, weak_hand, tremor_hand = _targets(path)
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    name = str(path.relative_to(root))
    return Example(
        Recording.from_rows(rows, name),
        parkinson,
        stroke,
        tremor,
        weak_hand=weak_hand,
        tremor_hand=tremor_hand,
    )


def _targets(path: Path) -> tuple[float, float, float, str | None, str | None]:
    parts = set(path.parts)
    for condition in CONDITIONS:
        if condition.folder in parts:
            return (
                condition.parkinson,
                condition.stroke,
                condition.tremor,
                condition.weak_hand,
                condition.tremor_hand,
            )
    if _LEFT in parts:
        return 0.0, 100.0, 0.0, "left", None
    if _RIGHT in parts:
        return 0.0, 100.0, 0.0, "right", None
    if _PARKINSON in parts:
        return 100.0, 0.0, 0.0, None, None
    if _TREMOR in parts:
        return 0.0, 0.0, 100.0, None, None
    if _BASELINE in parts:
        return 0.0, 0.0, 0.0, None, None
    raise RecordingError(
        f"{path} is not under Baseline Data, Parkinsons Data, Tremor Data, "
        "Stroke Data/Left Weak or Right Weak, or a Synthetic condition folder."
    )
