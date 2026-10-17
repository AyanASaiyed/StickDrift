"""Score a Recording with a trained checkpoint.

    from tcn import score
    score("runs/tcn/model.pt", recording)
"""

from pathlib import Path

import numpy as np
import torch

from tcn.checkpoint import load_checkpoint
from tcn.recording import Recording
from tcn.score import score_recording
from tcn.train import _device


def score(checkpoint: str | Path, recording: Recording, device: str = "auto") -> dict:
    """Return the three pattern scores for one recording."""
    torch_device = _device(device)
    model, blob = load_checkpoint(Path(checkpoint), torch_device)
    return score_recording(
        model,
        recording,
        np.asarray(blob["norm_mean"], dtype=np.float32),
        np.asarray(blob["norm_std"], dtype=np.float32),
        sample_hz=int(blob["sample_hz"]),
        window_s=float(blob["window_s"]),
        hop_s=float(blob["hop_s"]),
        score_names=list(blob["scores"]),
        device=torch_device,
    )
