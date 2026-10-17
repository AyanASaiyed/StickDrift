"""Save and load a trained pattern model."""

from pathlib import Path

import numpy as np
import torch

from tcn.config import SCHEMA_VERSION, SCORE_MEANING
from tcn.network import PatternTCN


def save_checkpoint(
    path: Path,
    model: PatternTCN,
    mean: np.ndarray,
    std: np.ndarray,
    sample_hz: int,
    window_s: float,
    hop_s: float,
    channels: tuple[str, ...],
    scores: tuple[str, ...],
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema_version": SCHEMA_VERSION,
            "model": model.state_dict(),
            "in_channels": model.in_channels,
            "hidden": model.hidden,
            "levels": model.levels,
            "kernel": model.kernel,
            "dropout": model.dropout,
            "sample_hz": sample_hz,
            "window_s": window_s,
            "hop_s": hop_s,
            "channels": list(channels),
            "scores": list(scores),
            "norm_mean": mean.astype(np.float32),
            "norm_std": std.astype(np.float32),
            "score_meaning": SCORE_MEANING,
        },
        path,
    )


def load_checkpoint(path: Path, device: torch.device) -> tuple[PatternTCN, dict]:
    blob = torch.load(Path(path), map_location=device, weights_only=False)
    version = blob.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"Checkpoint schema {version} does not match this code ({SCHEMA_VERSION}).")
    model = PatternTCN(
        in_channels=int(blob["in_channels"]),
        hidden=int(blob["hidden"]),
        levels=int(blob["levels"]),
        kernel=int(blob["kernel"]),
        dropout=float(blob["dropout"]),
        n_scores=len(blob["scores"]),
    )
    model.load_state_dict(blob["model"])
    model.to(device)
    model.eval()
    return model, blob
