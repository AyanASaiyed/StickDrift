"""Read the garden recordings whose folder is the pattern label.

The CSV files say `unlabeled`. The folder is the label:

- Baseline Data: all three scores 0
- Parkinsons Data: parkinson 100
- Tremor Data: essential tremor 100
- Stroke Data/Left Weak: stroke 100 on the left hand
- Stroke Data/Right Weak: stroke 100 on the right hand
"""

import csv
from pathlib import Path

from tcn.recording import Example, Recording, RecordingError

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
    parkinson, stroke, tremor, weak_hand = _targets(path)
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    name = str(path.relative_to(root))
    return Example(Recording.from_rows(rows, name), parkinson, stroke, tremor, weak_hand=weak_hand)


def _targets(path: Path) -> tuple[float, float, float, str | None]:
    parts = set(path.parts)
    if _LEFT in parts:
        return 0.0, 100.0, 0.0, "left"
    if _RIGHT in parts:
        return 0.0, 100.0, 0.0, "right"
    if _PARKINSON in parts:
        return 100.0, 0.0, 0.0, None
    if _TREMOR in parts:
        return 0.0, 0.0, 100.0, None
    if _BASELINE in parts:
        return 0.0, 0.0, 0.0, None
    raise RecordingError(
        f"{path} is not under Baseline Data, Parkinsons Data, Tremor Data, "
        "or Stroke Data/Left Weak or Right Weak."
    )
