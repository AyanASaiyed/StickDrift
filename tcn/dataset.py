"""Labeled windows for training. Input is Example objects, not files."""

from dataclasses import dataclass

import numpy as np
import torch
from torch.utils.data import Dataset

from tcn.config import HOP_S, SAMPLE_HZ, WINDOW_S
from tcn.prepare import RecordingError, prepare, windows
from tcn.recording import Example


@dataclass(frozen=True)
class WindowItem:
    recording: str
    values: np.ndarray
    mask: np.ndarray
    target: np.ndarray


class WindowDataset(Dataset):
    def __init__(self, items: list[WindowItem], mean: np.ndarray, std: np.ndarray):
        self.items = items
        self.mean = mean.astype(np.float32)
        self.std = std.astype(np.float32)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        item = self.items[index]
        values = (item.values - self.mean[:, None]) / self.std[:, None]
        return (
            torch.from_numpy(np.ascontiguousarray(values)),
            torch.from_numpy(item.mask.copy()),
            torch.from_numpy(item.target.copy()),
        )


def load_windows(
    examples: list[Example],
    sample_hz: int = SAMPLE_HZ,
    window_s: float = WINDOW_S,
    hop_s: float = HOP_S,
) -> list[WindowItem]:
    """Cut each labeled recording into fixed-length windows."""
    items: list[WindowItem] = []
    seen: dict[str, int] = {}
    for index, example in enumerate(examples):
        name = example.recording.name or f"recording-{index}"
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            name = f"{name}-{seen[name]}"
        prepared = prepare(example.recording, sample_hz=sample_hz)
        for values, mask in windows(prepared.values, sample_hz, window_s, hop_s):
            items.append(WindowItem(name, values, mask, example.target))
    if not items:
        raise RecordingError("No training windows.")
    return items


def split_items(
    items: list[WindowItem],
    val_ratio: float,
    seed: int,
) -> tuple[list[WindowItem], list[WindowItem]]:
    """Hold out whole recordings so overlapping windows do not leak into validation."""
    names = sorted({item.recording for item in items})
    if val_ratio <= 0 or len(names) < 2:
        return items, []
    rng = np.random.default_rng(seed)
    order = list(names)
    rng.shuffle(order)
    val_count = int(round(len(order) * val_ratio))
    val_count = min(max(val_count, 1), len(order) - 1)
    held = set(order[:val_count])
    train = [item for item in items if item.recording not in held]
    valid = [item for item in items if item.recording in held]
    return train, valid


def normalization(items: list[WindowItem]) -> tuple[np.ndarray, np.ndarray]:
    """Per-channel mean and standard deviation across training windows."""
    stacked = np.concatenate([item.values for item in items], axis=1)
    mean = stacked.mean(axis=1).astype(np.float32)
    std = stacked.std(axis=1).astype(np.float32)
    std = np.where(std < 1e-6, np.float32(1.0), std)
    return mean, std
