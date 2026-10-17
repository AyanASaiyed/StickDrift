"""Per-hand DualSense pattern model.

The slow path of each stick is removed first. One shared network then scores
the leftover of whichever hand is moving: the shake, how late, slow, or
shrinking the reach was, and how far the stick missed its target. Parkinson
is the impairment shared by both hands. Stroke is the gap between them.
Essential tremor is the shake. Diabetes is a mistimed apple reach. Ataxia is
leaving the butterfly or watering path.

Scores come back as parkinson, stroke, essential_tremor, diabetes, and ataxia,
each from 0 to 100. They are pattern resemblance, not disease probabilities,
and they do not sum to 100.
"""

from tcn.labels import load_examples
from tcn.predict import score
from tcn.recording import Example, Recording
from tcn.score import fuse
from tcn.train import fit

__all__ = ["Example", "Recording", "fit", "fuse", "load_examples", "score"]
