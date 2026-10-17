"""Shared constants for the DualSense pattern model.

Scores are resemblance to a motor pattern, from 0 to 100. They are not
disease probabilities, and a high score on more than one pattern is allowed.
"""

SAMPLE_HZ = 100
WINDOW_S = 4.0
HOP_S = 2.0
MIN_DURATION_S = 1.0

# Stick position, then the motion sensor that carries trembling.
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

SCORES = ("parkinson", "stroke", "essential_tremor")

HIDDEN = 32
LEVELS = 8
KERNEL = 3
DROPOUT = 0.1

SCHEMA_VERSION = 1
SCORE_MEANING = "0-100 pattern resemblance, not a disease probability"

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
