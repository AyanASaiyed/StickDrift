"""Score a Recording with a trained checkpoint.

    from tcn import score
    score("runs/tcn/model.pt", recording)
"""

from pathlib import Path

import numpy as np
import torch

from tcn.checkpoint import load_checkpoint
from tcn.config import Segment
from tcn.recording import Recording
from tcn.score import score_recording
from tcn.train import _device


def score(checkpoint: str | Path, recording: Recording, device: str = "auto") -> dict:
    """Return the three pattern scores (parkinson, stroke, essential_tremor) for one recording.

    Stroke is null when only one hand moves, because the gap between hands
    cannot be read. Parkinson and tremor are null when neither hand moves.
    """
    torch_device = _device(device)
    model, blob = load_checkpoint(Path(checkpoint), torch_device)
    return score_recording(
        model,
        recording,
        np.asarray(blob["norm_mean"], dtype=np.float32),
        np.asarray(blob["norm_std"], dtype=np.float32),
        sample_hz=int(blob["sample_hz"]),
        segment=Segment(**blob["segment"]),
        hand_scores=list(blob["hand_scores"]),
        device=torch_device,
    )
