"""One DualSense recording, independent of how it was stored.

A recording is a sequence of samples. Each sample has a timestamp in seconds,
both stick positions, and the motion sensor inside the controller body:

    t, lx, ly, rx, ry, gyro_x, gyro_y, gyro_z, acc_x, acc_y, acc_z

Stick columns may also be named raw_x, raw_y, raw_rx, raw_ry. Any other fields
in a sample are ignored. CSV, JSON, or a database row can all become a
Recording once those fields are in memory.
"""

from collections.abc import Mapping, Sequence

import numpy as np

from tcn.config import CHANNELS, COLUMN_ALIASES, SCORES


class RecordingError(ValueError):
    """A recording does not contain the expected sample pattern."""


class Recording:
    """Raw samples before resampling.

    `time_s` has shape (samples,). `values` has shape (samples, channels) in
    `CHANNELS` order.
    """

    def __init__(self, time_s: np.ndarray, values: np.ndarray, name: str = ""):
        time_s = np.asarray(time_s, dtype=np.float64).reshape(-1)
        values = np.asarray(values, dtype=np.float64)
        if values.ndim != 2 or values.shape[1] != len(CHANNELS):
            raise RecordingError(
                f"{_label(name)} values must have shape (samples, {len(CHANNELS)}), "
                f"in this order: {', '.join(CHANNELS)}."
            )
        if len(time_s) != len(values):
            raise RecordingError(
                f"{_label(name)} has {len(time_s)} timestamps and {len(values)} samples."
            )
        if len(time_s) < 2:
            raise RecordingError(f"{_label(name)} needs at least 2 samples.")
        if not np.isfinite(time_s).all() or not np.isfinite(values).all():
            raise RecordingError(f"{_label(name)} contains a blank or non-numeric sample.")
        self.time_s = time_s
        self.values = values
        self.name = name

    @classmethod
    def from_columns(cls, time_s: Sequence[float], name: str = "", **columns: Sequence[float]) -> "Recording":
        """Build a recording from one array per channel."""
        resolved = _resolve_columns(columns, name)
        width = len(np.asarray(time_s).reshape(-1))
        rows = np.column_stack([_match_length(resolved[channel], width, channel, name) for channel in CHANNELS])
        return cls(time_s, rows, name)

    @classmethod
    def from_rows(cls, rows: Sequence[Mapping[str, object]], name: str = "") -> "Recording":
        """Build a recording from an ordered sequence of sample mappings."""
        samples = list(rows)
        if not samples:
            raise RecordingError(f"{_label(name)} has no samples.")
        header: set[str] = set()
        for sample in samples:
            header.update(str(key) for key in sample.keys())
        chosen = _choose(header, ("t", *CHANNELS), name)
        times: list[float] = []
        values: list[list[float]] = []
        for sample in samples:
            parsed = _parse_sample(sample, chosen)
            if parsed is None:
                continue
            stamp, row = parsed
            times.append(stamp)
            values.append(row)
        if not values:
            raise RecordingError(f"{_label(name)} has no complete samples.")
        return cls(times, values, name)


class Example:
    """A recording plus the three pattern scores it should match, each 0–100."""

    def __init__(self, recording: Recording, parkinson: float, stroke: float, essential_tremor: float):
        target = np.asarray([parkinson, stroke, essential_tremor], dtype=np.float32)
        for score_name, value in zip(SCORES, target, strict=True):
            if not 0.0 <= float(value) <= 100.0:
                raise RecordingError(f"{score_name} must be from 0 to 100.")
        self.recording = recording
        self.target = target


def _resolve_columns(columns: Mapping[str, Sequence[float]], name: str) -> dict[str, np.ndarray]:
    chosen = _choose(set(columns), CHANNELS, name)
    resolved = {}
    for channel in CHANNELS:
        resolved[channel] = np.asarray(columns[chosen[channel]], dtype=np.float64).reshape(-1)
    return resolved


def _choose(header: set[str], fields: tuple[str, ...], name: str) -> dict[str, str]:
    chosen = {}
    missing = []
    for logical in fields:
        alias = next((item for item in COLUMN_ALIASES[logical] if item in header), None)
        if alias is None:
            missing.append(logical)
        else:
            chosen[logical] = alias
    if missing:
        raise RecordingError(
            f"{_label(name)} is missing {', '.join(missing)}. "
            "Each sample needs t, lx, ly, rx, ry, gyro_x, gyro_y, gyro_z, acc_x, acc_y, acc_z. "
            "Stick fields may also be named raw_x, raw_y, raw_rx, raw_ry."
        )
    return chosen


def _parse_sample(sample: Mapping[str, object], chosen: dict[str, str]) -> tuple[float, list[float]] | None:
    cells: list[float] = []
    for logical in ("t", *CHANNELS):
        text = sample.get(chosen[logical])
        if text is None or text == "":
            return None
        try:
            cells.append(float(text))
        except (TypeError, ValueError):
            return None
    return cells[0], cells[1:]


def _match_length(values: np.ndarray, width: int, channel: str, name: str) -> np.ndarray:
    if len(values) != width:
        raise RecordingError(
            f"{_label(name)} channel {channel} has {len(values)} samples, expected {width}."
        )
    return values


def _label(name: str) -> str:
    return name or "recording"
