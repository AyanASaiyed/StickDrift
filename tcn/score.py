"""Turn per-hand stretch scores into the three recording scores."""

import numpy as np
import torch

from tcn.config import HAND_SCORES, SCORES, Segment
from tcn.prepare import prepare
from tcn.recording import Recording
from tcn.stretch import build_stretches


def score_recording(
    model: torch.nn.Module,
    recording: Recording,
    mean: np.ndarray,
    std: np.ndarray,
    sample_hz: int,
    segment: Segment,
    hand_scores: list[str],
    device: torch.device,
) -> dict:
    prepared = prepare(recording, sample_hz=sample_hz)
    stretches = build_stretches(prepared, recording.cue_s, segment, recording.task_spans)
    counts = {"left": 0, "right": 0}
    if not stretches:
        return _result(recording.name, prepared.duration_s, counts, {name: None for name in SCORES})

    values = np.stack([(item.values - mean[:, None]) / std[:, None] for item in stretches])
    inputs = torch.from_numpy(np.ascontiguousarray(values)).to(device)
    with torch.no_grad():
        predicted = model(inputs).detach().cpu().numpy()

    tremor_index = hand_scores.index(HAND_SCORES[0])
    impairment_index = hand_scores.index(HAND_SCORES[1])
    tremor: dict[str, list[float]] = {"left": [], "right": []}
    impairment: dict[str, list[float]] = {"left": [], "right": []}
    for stretch, row in zip(stretches, predicted, strict=True):
        counts[stretch.hand] += 1
        tremor[stretch.hand].append(float(row[tremor_index]))
        impairment[stretch.hand].append(float(row[impairment_index]))
    return _result(recording.name, prepared.duration_s, counts, _aggregate(tremor, impairment))


def _aggregate(
    tremor: dict[str, list[float]],
    impairment: dict[str, list[float]],
) -> dict[str, float | None]:
    """Parkinson is the impairment shared by both hands. Stroke is the gap."""
    tremor_means = {hand: float(np.mean(values)) for hand, values in tremor.items() if values}
    impairment_means = {hand: float(np.mean(values)) for hand, values in impairment.items() if values}
    if not tremor_means:
        return {name: None for name in SCORES}
    scores: dict[str, float | None] = {"essential_tremor": max(tremor_means.values())}
    if "left" in impairment_means and "right" in impairment_means:
        scores["parkinson"] = min(impairment_means["left"], impairment_means["right"])
        scores["stroke"] = abs(impairment_means["left"] - impairment_means["right"])
    else:
        scores["parkinson"] = next(iter(impairment_means.values()))
        scores["stroke"] = None
    return scores


def _result(name: str, duration_s: float, counts: dict[str, int], scores: dict[str, float | None]) -> dict:
    return {
        "recording": name,
        "duration_s": round(duration_s, 3),
        "stretches": counts,
        "scores": {name: None if value is None else round(float(value), 1) for name, value in scores.items()},
    }
