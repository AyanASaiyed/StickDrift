"""Per-hand DualSense pattern model.

The slow path of each stick is removed first. One shared network then scores
the leftover of whichever hand is moving: the shake, and how late, slow, or
shrinking the reach was. Parkinson is the impairment shared by both hands.
Stroke is the gap between them. Essential tremor is the shake.

Scores come back as parkinson, stroke, and essential_tremor, each from 0 to
100. They are pattern resemblance, not disease probabilities.
"""

from tcn.labels import load_examples
from tcn.predict import score
from tcn.recording import Example, Recording
from tcn.train import fit

__all__ = ["Example", "Recording", "fit", "load_examples", "score"]
