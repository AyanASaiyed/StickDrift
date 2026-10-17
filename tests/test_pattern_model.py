"""The per-hand model keeps the flaw and drops the route."""

import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from tcn import fit, load_examples, score
from tcn.config import HAND_CHANNELS
from tcn.dataset import _target
from tcn.prepare import prepare
from tcn.recording import Example, Recording, RecordingError
from tcn.score import _aggregate
from tcn.stretch import build_stretches, moving_average


HZ = 100


class PatternModelTest(unittest.TestCase):
    def test_slow_path_keeps_the_reach_and_drops_the_shake(self):
        sample_count = 4 * HZ
        time_s = np.arange(sample_count) / HZ
        reach = np.linspace(0.0, 80.0, sample_count)
        shake = 8.0 * np.sin(2 * np.pi * 6 * time_s)
        signal = np.vstack([reach + shake])
        slow = moving_average(signal, 41)
        leftover = signal - slow
        reach_corr = np.corrcoef(slow[0], reach)[0, 1]
        shake_corr = np.corrcoef(leftover[0], shake)[0, 1]
        self.assertGreater(reach_corr, 0.98)
        self.assertGreater(shake_corr, 0.9)

    def test_rest_is_skipped_and_each_hand_is_separate(self):
        rest = _flat(3.0, 128.0)
        noise = np.random.default_rng(0).uniform(-1.0, 1.0, rest.shape)
        quiet = _recording(rest + noise, rest, rest + noise, rest)
        self.assertEqual(build_stretches(prepare(quiet), quiet.cue_s), [])

        left = _reach(rest, start=1.0, duration=0.6, height=80.0)
        moving = _recording(left, rest, rest, rest, name="left-only")
        stretches = build_stretches(prepare(moving), moving.cue_s)
        self.assertTrue(stretches)
        self.assertTrue(all(item.hand == "left" for item in stretches))

    def test_a_slow_reach_scores_a_lower_speed_ratio_than_a_fast_one(self):
        rest = _flat(2.4, 0.0)
        fast = _recording(_reach(rest, 0.4, 0.4, 70.0), rest, rest, rest, name="fast")
        slow = _recording(_reach(rest, 0.4, 1.4, 70.0), rest, rest, rest, name="slow")
        fast_ratio = build_stretches(prepare(fast), fast.cue_s)[0].speed_ratio
        slow_ratio = build_stretches(prepare(slow), slow.cue_s)[0].speed_ratio
        self.assertGreater(fast_ratio, slow_ratio * 1.5)

    def test_shake_remains_in_the_leftover(self):
        rest = _flat(2.2, 0.0)
        smooth = _reach(rest, 0.3, 1.5, 80.0)
        time_s = np.arange(len(smooth)) / HZ
        shaky = smooth + 10.0 * np.sin(2 * np.pi * 6 * time_s)
        smooth_left = _residual_scale(_recording(smooth, rest, rest, rest, name="smooth"))
        shaky_left = _residual_scale(_recording(shaky, rest, rest, rest, name="shaky"))
        self.assertGreater(shaky_left, smooth_left * 3)

    def test_a_cue_keeps_the_reach_and_leaves_the_return(self):
        rest = _flat(3.4, 0.0)
        values = rest.copy()
        begin = int(1.0 * HZ)
        width = int(0.5 * HZ)
        values[begin:begin + width] = np.linspace(0.0, 80.0, width)
        hold_end = int(2.2 * HZ)
        values[begin + width:hold_end] = 80.0
        back = int(0.5 * HZ)
        values[hold_end:hold_end + back] = np.linspace(80.0, 0.0, back)
        quiet = _recording(values, rest, rest, rest, name="return")
        self.assertGreaterEqual(len(build_stretches(prepare(quiet), quiet.cue_s)), 2)
        cued = _recording(values, rest, rest, rest, cues=[1.0], name="cued-return")
        stretches = build_stretches(prepare(cued), cued.cue_s)
        self.assertEqual(len(stretches), 1)
        self.assertLess(stretches[0].start_s, 1.4)

    def test_a_late_start_is_measured_from_the_cue(self):
        rest = _flat(2.5, 0.0)
        moved = _reach(rest, start=1.4, duration=0.5, height=80.0)
        recording = _recording(moved, rest, rest, rest, cues=[1.0], name="late")
        stretch = build_stretches(prepare(recording), recording.cue_s)[0]
        latency = float(stretch.values[HAND_CHANNELS.index("latency_s"), 0])
        has_cue = float(stretch.values[HAND_CHANNELS.index("has_cue"), 0])
        self.assertEqual(has_cue, 1.0)
        self.assertGreater(latency, 0.2)
        self.assertLess(latency, 0.8)

    def test_phase_column_becomes_a_cue(self):
        rows = [_row(0.0, 128, "wait"), _row(0.5, 128, "cue"), _row(0.6, 160, "cue")]
        recording = Recording.from_rows(rows, "garden")
        self.assertEqual(recording.cue_s.tolist(), [0.5])

    def test_stroke_is_the_gap_and_stays_empty_for_one_hand(self):
        both = _aggregate(
            {"left": [10.0], "right": [80.0]},
            {"left": [20.0], "right": [90.0]},
        )
        self.assertEqual(both["parkinson"], 20.0)
        self.assertEqual(both["stroke"], 70.0)
        self.assertEqual(both["essential_tremor"], 80.0)
        one = _aggregate({"left": [40.0], "right": []}, {"left": [55.0], "right": []})
        self.assertEqual(one["parkinson"], 55.0)
        self.assertIsNone(one["stroke"])
        self.assertEqual(one["essential_tremor"], 40.0)

    def test_folder_names_are_the_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_level(root / "Baseline Data" / "session" / "level_1_apples")
            _write_level(root / "Parkinsons Data" / "session" / "level_1_apples")
            _write_level(root / "Tremor Data" / "session" / "level_1_apples")
            _write_level(root / "Stroke Data" / "Left Weak" / "session" / "level_1_apples")
            _write_level(root / "Stroke Data" / "Right Weak" / "session" / "level_1_apples")
            by_name = {item.recording.name: item for item in load_examples(root)}
            self.assertEqual(by_name["Baseline Data/session/level_1_apples/controller_data.csv"].target.tolist(), [0, 0, 0])
            self.assertEqual(by_name["Parkinsons Data/session/level_1_apples/controller_data.csv"].target.tolist(), [100, 0, 0])
            self.assertEqual(by_name["Tremor Data/session/level_1_apples/controller_data.csv"].target.tolist(), [0, 0, 100])
            left = by_name["Stroke Data/Left Weak/session/level_1_apples/controller_data.csv"]
            right = by_name["Stroke Data/Right Weak/session/level_1_apples/controller_data.csv"]
            self.assertEqual(left.weak_hand, "left")
            self.assertEqual(float(left.target[1]), 100.0)
            self.assertEqual(right.weak_hand, "right")
            self.assertIsNone(by_name["Baseline Data/session/level_1_apples/controller_data.csv"].weak_hand)

    def test_a_mix_splits_shared_slowness_and_the_gap(self):
        recording = _recording(_flat(1.2, 0), _flat(1.2, 0), _flat(1.2, 0), _flat(1.2, 0))
        mixed = Example(recording, 50, 35, 70, weak_hand="left", tremor_hand="left")
        left = _target(mixed, SimpleNamespace(hand="left"))
        right = _target(mixed, SimpleNamespace(hand="right"))
        self.assertEqual(float(left[0]), 70.0)
        self.assertEqual(float(right[0]), 0.0)
        self.assertEqual(float(left[1]), 85.0)
        self.assertEqual(float(right[1]), 50.0)

    def test_synthetic_folder_names_are_the_mix_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_level(root / "Synthetic" / "Parkinson and Tremor" / "apples_s1")
            _write_level(root / "Synthetic" / "Stroke Right and Tremor" / "apples_s1")
            by_name = {item.recording.name: item for item in load_examples(root)}
            both = by_name["Synthetic/Parkinson and Tremor/apples_s1/controller_data.csv"]
            sided = by_name["Synthetic/Stroke Right and Tremor/apples_s1/controller_data.csv"]
            self.assertEqual(both.target.tolist(), [70.0, 0.0, 70.0])
            self.assertEqual(sided.weak_hand, "right")
            self.assertEqual(sided.tremor_hand, "both")
            self.assertEqual(sided.target.tolist(), [0.0, 70.0, 70.0])

    def test_a_stroke_target_needs_the_weak_hand(self):
        recording = _recording(_flat(1.2, 0), _flat(1.2, 0), _flat(1.2, 0), _flat(1.2, 0))
        with self.assertRaises(RecordingError):
            Example(recording, 0, 100, 0)

    def test_old_window_setup_is_gone(self):
        # Imported here on purpose: the assertion is that this name no longer exists.
        with self.assertRaises(ImportError):
            from tcn.prepare import windows  # noqa: F401

    def test_fit_and_score_use_the_shared_hand_model(self):
        rest = _flat(1.5, 0.0)
        smooth = _reach(rest, 0.2, 0.8, 80.0)
        time_s = np.arange(len(smooth)) / HZ
        shaky = smooth + 12.0 * np.sin(2 * np.pi * 7 * time_s)
        plain = _both_hands(smooth, rest, "plain")
        shaking = _both_hands(shaky, rest, "shaking")
        with tempfile.TemporaryDirectory() as tmp:
            path = fit(
                [
                    Example(plain, parkinson=0, stroke=0, essential_tremor=0),
                    Example(shaking, parkinson=0, stroke=0, essential_tremor=100),
                ],
                out=Path(tmp) / "model.pt",
                epochs=12,
                batch_size=8,
                lr=5e-3,
                val_ratio=0,
                device="cpu",
                hidden=16,
                levels=3,
                dropout=0.0,
            )
            plain_score = score(path, plain, device="cpu")["scores"]["essential_tremor"]
            shaky_score = score(path, shaking, device="cpu")["scores"]["essential_tremor"]
        self.assertIsNotNone(plain_score)
        self.assertIsNotNone(shaky_score)
        self.assertGreater(shaky_score, plain_score)


def _flat(duration_s: float, value: float) -> np.ndarray:
    return np.full(int(round(duration_s * HZ)) + 1, value, dtype=np.float64)


def _reach(base: np.ndarray, start: float, duration: float, height: float) -> np.ndarray:
    values = base.copy()
    begin = int(start * HZ)
    width = int(duration * HZ)
    values[begin:begin + width] = np.linspace(base[0], base[0] + height, width)
    values[begin + width:] = base[0] + height
    return values


def _recording(lx, ly, rx, ry, cues=None, name="rec") -> Recording:
    count = len(lx)
    time_s = np.arange(count) / HZ
    zeros = np.zeros(count)
    return Recording.from_columns(
        time_s,
        name=name,
        cues=cues,
        lx=lx,
        ly=ly,
        rx=rx,
        ry=ry,
        gyro_x=zeros,
        gyro_y=zeros,
        gyro_z=zeros,
        acc_x=zeros,
        acc_y=zeros,
        acc_z=zeros,
    )


def _both_hands(lx: np.ndarray, rest: np.ndarray, name: str) -> Recording:
    return _recording(lx, rest, lx, rest, name=name)


def _residual_scale(recording: Recording) -> float:
    stretches = build_stretches(prepare(recording), recording.cue_s)
    column = HAND_CHANNELS.index("resid_x")
    return float(np.mean([np.std(item.values[column]) for item in stretches]))


def _row(time_s: float, stick: float, phase: str) -> dict[str, str]:
    return {
        "t": str(time_s),
        "lx": str(stick),
        "ly": "128",
        "rx": "128",
        "ry": "128",
        "gyro_x": "0",
        "gyro_y": "0",
        "gyro_z": "0",
        "acc_x": "0",
        "acc_y": "0",
        "acc_z": "0",
        "phase": phase,
    }


def _write_level(folder: Path) -> None:
    folder.mkdir(parents=True)
    path = folder / "controller_data.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_row(0, 128, "wait")))
        writer.writeheader()
        writer.writerow(_row(0, 128, "wait"))
        writer.writerow(_row(0.2, 128, "wait"))


if __name__ == "__main__":
    unittest.main()
