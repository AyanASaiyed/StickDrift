"""Resample a Recording onto a uniform grid."""

from dataclasses import dataclass

import numpy as np

from tcn.config import MIN_DURATION_S, SAMPLE_HZ
from tcn.recording import Recording, RecordingError


@dataclass(frozen=True)
class Prepared:
    """One recording after resampling.

    `values` has shape (channels, time). Each channel has had its own median
    removed, which takes out stick-center offset, gyro bias, and gravity.
    `time_s` is the uniform grid those columns sit on.
    """

    values: np.ndarray
    time_s: np.ndarray
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
        values=np.ascontiguousarray(centered.T, dtype=np.float64),
        time_s=grid,
        duration_s=duration,
        sample_hz=sample_hz,
        name=recording.name,
    )


def _grid(start: float, end: float, sample_hz: int) -> np.ndarray:
    steps = int(round((end - start) * sample_hz)) + 1
    return np.linspace(start, end, steps)
