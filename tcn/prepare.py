"""Resample a Recording onto a uniform grid and cut it into windows."""

from dataclasses import dataclass

import numpy as np

from tcn.config import MIN_DURATION_S, SAMPLE_HZ
from tcn.recording import Recording, RecordingError


@dataclass(frozen=True)
class Prepared:
    """One recording after resampling.

    `values` has shape (channels, time). Each channel has had its own median
    removed, which takes out stick-center offset, gyro bias, and gravity.
    Dataset-level standardization happens later, using statistics from training.
    """

    values: np.ndarray
    duration_s: float
    sample_hz: int
    name: str


def prepare(recording: Recording, sample_hz: int = SAMPLE_HZ) -> Prepared:
    """Resample one recording onto a uniform `sample_hz` grid."""
    timestamps = recording.time_s
    samples = recording.values
    order = np.argsort(timestamps, kind="stable")
    timestamps = timestamps[order]
    samples = samples[order]
    keep = np.ones(len(timestamps), dtype=bool)
    keep[:-1] = np.diff(timestamps) > 0
    timestamps = timestamps[keep]
    samples = samples[keep]
    if len(timestamps) < 2:
        raise RecordingError(f"{recording.name or 'recording'} has no increasing timestamps.")

    duration = float(timestamps[-1] - timestamps[0])
    if duration < MIN_DURATION_S:
        raise RecordingError(
            f"{recording.name or 'recording'} is {duration:.2f}s. "
            f"Recordings need at least {MIN_DURATION_S:.0f}s."
        )

    grid = _grid(float(timestamps[0]), float(timestamps[-1]), sample_hz)
    resampled = np.empty((len(grid), samples.shape[1]), dtype=np.float64)
    for index in range(samples.shape[1]):
        resampled[:, index] = np.interp(grid, timestamps, samples[:, index])
    centered = resampled - np.median(resampled, axis=0, keepdims=True)
    return Prepared(
        values=np.ascontiguousarray(centered.T, dtype=np.float32),
        duration_s=duration,
        sample_hz=sample_hz,
        name=recording.name,
    )


def windows(values: np.ndarray, sample_hz: int, window_s: float, hop_s: float) -> list[tuple[np.ndarray, np.ndarray]]:
    """Cut (channels, time) into fixed windows and a validity mask for each.

    A recording shorter than one window is replicate-padded. The mask is 0 on
    padded steps so the pooled score ignores them. Longer recordings use a
    sliding window and always include the final window.
    """
    count = values.shape[1]
    width = int(round(window_s * sample_hz))
    hop = int(round(hop_s * sample_hz))
    if width < 2 or hop < 1:
        raise RecordingError("Window and hop must cover at least one sample.")
    if count <= width:
        padded = np.repeat(values[:, -1:], width, axis=1)
        padded[:, :count] = values
        mask = np.zeros(width, dtype=np.float32)
        mask[:count] = 1.0
        return [(padded, mask)]

    starts = list(range(0, count - width + 1, hop))
    if starts[-1] != count - width:
        starts.append(count - width)
    full = np.ones(width, dtype=np.float32)
    return [(values[:, start:start + width], full.copy()) for start in starts]


def _grid(start: float, end: float, sample_hz: int) -> np.ndarray:
    steps = int(round((end - start) * sample_hz)) + 1
    return np.linspace(start, end, steps)
