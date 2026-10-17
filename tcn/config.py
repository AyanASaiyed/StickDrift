"""Shared constants for the per-hand pattern model.

Each hand is scored on what remains after its slow path is removed. Parkinson
is the part of that impairment shared by both hands. Stroke is the gap between
the hands. Essential tremor is the leftover shake. Scores are resemblance from
0 to 100, not disease probabilities, and more than one may be high.
"""

from dataclasses import dataclass

SAMPLE_HZ = 100
MIN_DURATION_S = 1.0

# Raw recording channels. Stick position, then the motion sensor.
CHANNELS = (
    "lx",
    "ly",
    "rx",
    "ry",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "acc_x",
    "acc_y",
    "acc_z",
)

# One shared network reads these, in this order, for whichever hand is moving.
HAND_CHANNELS = (
    "resid_x",
    "resid_y",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "speed_ratio",
    "amplitude",
    "latency_s",
    "has_cue",
    "shrink_ratio",
)

# Network outputs for a single hand. Recording scores are derived from these.
HAND_SCORES = ("tremor", "impairment")

# Recording-level scores returned to callers.
SCORES = ("parkinson", "stroke", "essential_tremor")

HIDDEN = 32
LEVELS = 6
KERNEL = 3
DROPOUT = 0.1

SCHEMA_VERSION = 2
SCORE_MEANING = "0-100 pattern resemblance, not a disease probability"


@dataclass(frozen=True)
class Segment:
    """How a recording is cut into moving stretches and how the slow path is removed."""

    smooth_s: float = 0.16
    move_window_s: float = 0.10
    move_counts: float = 3.0
    min_stretch_s: float = 0.25
    merge_gap_s: float = 0.15
    min_amplitude: float = 8.0
    stretch_steps: int = 80
    max_latency_s: float = 2.0
    shrink_clip: float = 3.0


DEFAULT_SEGMENT = Segment()

# Header aliases accepted from the HID recorder and from the pygame game logger.
COLUMN_ALIASES = {
    "t": ("t", "time"),
    "lx": ("lx", "raw_x"),
    "ly": ("ly", "raw_y"),
    "rx": ("rx", "raw_rx"),
    "ry": ("ry", "raw_ry"),
    "gyro_x": ("gyro_x",),
    "gyro_y": ("gyro_y",),
    "gyro_z": ("gyro_z",),
    "acc_x": ("acc_x",),
    "acc_y": ("acc_y",),
    "acc_z": ("acc_z",),
}

CUE_PHASES = frozenset({"cue", "track"})
