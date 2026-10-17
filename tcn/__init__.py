"""DualSense pattern matcher.

Feed `fit` a list of recordings. Each recording is the sample pattern — time,
both stick positions, and the in-body gyro and accelerometer — plus three
target scores. The file format used to store that pattern is outside the model.

Scores come back as parkinson, stroke, and essential_tremor, each from 0 to
100. They are pattern resemblance, not disease probabilities.
"""

from tcn.predict import score
from tcn.recording import Example, Recording
from tcn.train import fit

__all__ = ["Example", "Recording", "fit", "score"]
