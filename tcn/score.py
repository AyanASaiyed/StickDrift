"""Score one Recording with a loaded checkpoint."""

import numpy as np
import torch

from tcn.prepare import prepare, windows
from tcn.recording import Recording


def score_recording(
    model: torch.nn.Module,
    recording: Recording,
    mean: np.ndarray,
    std: np.ndarray,
    sample_hz: int,
    window_s: float,
    hop_s: float,
    score_names: list[str],
    device: torch.device,
) -> dict:
    prepared = prepare(recording, sample_hz=sample_hz)
    pieces = windows(prepared.values, sample_hz, window_s, hop_s)
    values = np.stack([(item - mean[:, None]) / std[:, None] for item, _mask in pieces])
    masks = np.stack([mask for _item, mask in pieces])
    inputs = torch.from_numpy(np.ascontiguousarray(values)).to(device)
    mask = torch.from_numpy(np.ascontiguousarray(masks)).to(device)
    with torch.no_grad():
        predicted = model(inputs, mask).mean(dim=0).detach().cpu()
    scores = {
        name: round(float(predicted[index]), 1)
        for index, name in enumerate(score_names)
    }
    return {
        "recording": recording.name,
        "duration_s": round(prepared.duration_s, 3),
        "windows": len(pieces),
        "scores": scores,
    }
