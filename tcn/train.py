"""Train the pattern TCN on Recording objects.

    from tcn import Example, Recording, fit

    fit([
        Example(recording, parkinson=90, stroke=5, essential_tremor=10),
    ])
"""

from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from tcn.checkpoint import save_checkpoint
from tcn.config import (
    CHANNELS,
    DROPOUT,
    HIDDEN,
    HOP_S,
    KERNEL,
    LEVELS,
    SAMPLE_HZ,
    SCORE_MEANING,
    SCORES,
    WINDOW_S,
)
from tcn.dataset import WindowDataset, load_windows, normalization, split_items
from tcn.network import PatternTCN
from tcn.prepare import RecordingError
from tcn.recording import Example


def fit(
    examples: list[Example],
    out: str | Path = "runs/tcn/model.pt",
    epochs: int = 30,
    batch_size: int = 16,
    lr: float = 1e-3,
    val_ratio: float = 0.2,
    seed: int = 7,
    device: str = "auto",
    sample_hz: int = SAMPLE_HZ,
    window_s: float = WINDOW_S,
    hop_s: float = HOP_S,
    hidden: int = HIDDEN,
    levels: int = LEVELS,
    kernel: int = KERNEL,
    dropout: float = DROPOUT,
) -> Path:
    """Train on labeled recordings and save a checkpoint. Returns its path."""
    if not examples:
        raise RecordingError("fit needs at least one labeled recording.")
    seed_everything(seed)
    torch_device = _device(device)
    items = load_windows(examples, sample_hz=sample_hz, window_s=window_s, hop_s=hop_s)
    train_items, val_items = split_items(items, val_ratio, seed)
    mean, std = normalization(train_items)
    train_loader = _loader(train_items, mean, std, batch_size, shuffle=True)
    val_loader = _loader(val_items, mean, std, batch_size, shuffle=False) if val_items else None

    model = PatternTCN(
        in_channels=len(CHANNELS),
        hidden=hidden,
        levels=levels,
        kernel=kernel,
        dropout=dropout,
        n_scores=len(SCORES),
    ).to(torch_device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    recordings = len({item.recording for item in items})
    print(
        f"Pattern TCN  recordings={recordings}  train_windows={len(train_items)}  "
        f"val_windows={len(val_items)}  device={torch_device}"
    )
    print(SCORE_MEANING)
    if not val_items and val_ratio > 0:
        print("No validation split. Add at least two recordings to hold one out.")

    best_mae = None
    best_state = None
    for epoch in range(1, epochs + 1):
        train_mae = _epoch(model, train_loader, optimizer, torch_device)
        if val_loader is None:
            print(f"epoch {epoch:03d}  train_mae={train_mae:.2f}")
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            continue
        val_mae = _epoch(model, val_loader, None, torch_device)
        print(f"epoch {epoch:03d}  train_mae={train_mae:.2f}  val_mae={val_mae:.2f}")
        if best_mae is None or val_mae < best_mae:
            best_mae = val_mae
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}

    if best_state is None:
        raise RecordingError("Training produced no checkpoint.")
    model.load_state_dict(best_state)
    destination = Path(out)
    save_checkpoint(
        destination,
        model,
        mean,
        std,
        sample_hz=sample_hz,
        window_s=window_s,
        hop_s=hop_s,
        channels=CHANNELS,
        scores=SCORES,
    )
    held = f"  best_val_mae={best_mae:.2f}" if best_mae is not None else ""
    print(f"Saved {destination}{held}")
    return destination


def _epoch(
    model: PatternTCN,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer | None,
    device: torch.device,
) -> float:
    training = optimizer is not None
    model.train(training)
    absolute = 0.0
    count = 0
    for inputs, mask, target in loader:
        inputs = inputs.to(device)
        mask = mask.to(device)
        target = target.to(device)
        if training:
            optimizer.zero_grad(set_to_none=True)
        predicted = model(inputs, mask)
        loss = nn.functional.mse_loss(predicted / 100.0, target / 100.0)
        if training:
            loss.backward()
            optimizer.step()
        absolute += (predicted - target).abs().sum().item()
        count += predicted.numel()
    return absolute / max(count, 1)


def _loader(items, mean, std, batch_size: int, shuffle: bool) -> DataLoader:
    return DataLoader(
        WindowDataset(items, mean, std),
        batch_size=min(batch_size, len(items)),
        shuffle=shuffle,
    )


def _device(name: str) -> torch.device:
    if name != "auto":
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def seed_everything(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
