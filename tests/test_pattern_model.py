"""The per-hand model keeps the flaw and drops the route."""

import csv
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

from tcn import fit, fuse, load_examples, score
from tcn.checkpoint import load_checkpoint
from tcn.config import HAND_CHANNELS, HAND_SCORES, SCHEMA_VERSION
from tcn.dataset import _target
from tcn.prepare import prepare
from tcn.recording import Example, Recording, RecordingError
from tcn.score import _aggregate
from tcn.stretch import build_stretches, moving_average
from tcn.synthetic import CONDITIONS, write_synthetic
from tcn.train import masked_loss


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
        self.assertIsNone(both["diabetes"])
        self.assertIsNone(both["ataxia"])
        one = _aggregate({"left": [40.0], "right": []}, {"left": [55.0], "right": []})
        self.assertEqual(one["parkinson"], 55.0)
        self.assertIsNone(one["stroke"])
        self.assertEqual(one["essential_tremor"], 40.0)
        self.assertIsNone(one["diabetes"])
        self.assertIsNone(one["ataxia"])

    def test_folder_names_are_the_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_level(root / "Baseline Data" / "session" / "level_1_apples")
            _write_level(root / "Parkinsons Data" / "session" / "level_1_apples")
            _write_level(root / "Tremor Data" / "session" / "level_1_apples")
            _write_level(root / "Stroke Data" / "Left Weak" / "session" / "level_1_apples")
            _write_level(root / "Stroke Data" / "Right Weak" / "session" / "level_1_apples")
            by_name = {item.recording.name: item for item in load_examples(root)}
            baseline = by_name["Baseline Data/session/level_1_apples/controller_data.csv"]
            self.assertEqual(baseline.target.tolist(), [0, 0, 0])
            self.assertIsNone(baseline.diabetes)
            self.assertIsNone(baseline.ataxia)
            self.assertEqual(baseline.activity, "apples")
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
            plain_scores = score(path, plain, device="cpu")["scores"]
            shaky_score = score(path, shaking, device="cpu")["scores"]["essential_tremor"]
        self.assertEqual(
            set(plain_scores),
            {"parkinson", "stroke", "essential_tremor", "diabetes", "ataxia"},
        )
        self.assertIsNone(plain_scores["diabetes"])
        self.assertIsNone(plain_scores["ataxia"])
        self.assertIsNotNone(plain_scores["essential_tremor"])
        self.assertIsNotNone(shaky_score)
        self.assertGreater(shaky_score, plain_scores["essential_tremor"])


    def test_a_straight_reach_has_lower_target_error_than_an_overshoot(self):
        straight = _aimed_reach(0.60, 0.60)
        past = _aimed_reach(0.95, 0.60)
        self.assertLess(_end_error(straight), _end_error(past) * 0.35)
        turned = _aimed_reach(0.60, 0.60, axis="y")
        self.assertLess(np.max(np.abs(_error_pair(straight) - _error_pair(turned))), 0.05)

    def test_raw_stick_uses_the_game_scale_when_cursor_is_absent(self):
        on_target = _aimed_reach(0.60, 0.60, cursor=False)
        past = _aimed_reach(0.95, 0.60, cursor=False)
        self.assertLess(_end_error(on_target), _end_error(past) * 0.35)
        self.assertGreater(float(_channel(on_target, "has_target").mean()), 0.5)

    def test_a_shake_is_not_the_channel_that_sees_a_path_departure(self):
        wobble = _tracked(wobble=0.05, departure=0.0)
        departure = _tracked(wobble=0.0, departure=0.35)
        self.assertNotEqual(HAND_CHANNELS.index("resid_y"), HAND_CHANNELS.index("error_across"))
        self.assertGreater(_channel_std(wobble, "resid_y"), _channel_std(departure, "resid_y") * 4)
        self.assertGreater(_channel_std(departure, "error_across"), _channel_std(wobble, "error_across") * 3)

    def test_diabetes_loss_is_masked_off_apples_and_ataxia_off_the_path(self):
        quiet = _recording(_flat(1.2, 0), _flat(1.2, 0), _flat(1.2, 0), _flat(1.2, 0))
        apple = Example(quiet, 0, 0, 0, diabetes=80, ataxia=90, activity="apples")
        butterfly = Example(quiet, 0, 0, 0, diabetes=80, ataxia=90, activity="butterfly")
        water = Example(quiet, 0, 0, 0, diabetes=80, ataxia=90, activity="water")
        played = Example(
            _recording(
                _flat(1.2, 0), _flat(1.2, 0), _flat(1.2, 0), _flat(1.2, 0),
                name="level_1_apples/controller_data.csv",
            ),
            0, 0, 0,
        )
        hand = SimpleNamespace(hand="left")
        apple_y = _target(apple, hand)
        butterfly_y = _target(butterfly, hand)
        water_y = _target(water, hand)
        played_y = _target(played, hand)
        diabetes = HAND_SCORES.index("diabetes")
        ataxia = HAND_SCORES.index("ataxia")
        self.assertEqual(float(apple_y[diabetes]), 80.0)
        self.assertTrue(math.isnan(float(apple_y[ataxia])))
        self.assertTrue(math.isnan(float(butterfly_y[diabetes])))
        self.assertEqual(float(butterfly_y[ataxia]), 90.0)
        self.assertTrue(math.isnan(float(water_y[diabetes])))
        self.assertEqual(float(water_y[ataxia]), 90.0)
        self.assertTrue(math.isnan(float(played_y[diabetes])))
        self.assertTrue(math.isnan(float(played_y[ataxia])))

        labeled = torch.tensor(np.asarray(butterfly_y), dtype=torch.float32).unsqueeze(0)
        quiet_pred = torch.zeros_like(labeled)
        quiet_pred[0, ataxia] = float(butterfly_y[ataxia])
        loud_pred = quiet_pred.clone()
        loud_pred[0, diabetes] = 100.0
        self.assertEqual(float(masked_loss(quiet_pred, labeled)), float(masked_loss(loud_pred, labeled)))
        missed = quiet_pred.clone()
        missed[0, ataxia] = 0.0
        self.assertGreater(float(masked_loss(missed, labeled)), float(masked_loss(quiet_pred, labeled)))

    def test_a_file_without_targets_keeps_error_channels_at_zero(self):
        rest = _flat(2.2, 0.0)
        recording = _recording(_reach(rest, 0.3, 0.6, 80.0), rest, rest, rest, name="no-targets")
        self.assertFalse(recording.has_targets)
        self.assertEqual(float(_channel(recording, "error_along").std()), 0.0)
        self.assertEqual(float(_channel(recording, "has_target").max()), 0.0)

    def test_callers_average_shared_scores_and_skip_nulls(self):
        apple = {
            "parkinson": 80.0, "stroke": 40.0, "essential_tremor": 10.0,
            "diabetes": 70.0, "ataxia": None,
        }
        path = {
            "parkinson": 40.0, "stroke": None, "essential_tremor": None,
            "diabetes": None, "ataxia": 90.0,
        }
        fused = fuse(apple, path)
        self.assertEqual(fused["parkinson"], 60.0)
        self.assertEqual(fused["essential_tremor"], 10.0)
        self.assertEqual(fused["stroke"], 40.0)
        self.assertEqual(fused["diabetes"], 70.0)
        self.assertEqual(fused["ataxia"], 90.0)

    def test_schema_two_checkpoint_does_not_load(self):
        self.assertGreaterEqual(SCHEMA_VERSION, 3)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.pt"
            torch.save({"schema_version": 2}, path)
            with self.assertRaises(ValueError):
                load_checkpoint(path, torch.device("cpu"))

    def test_synthetic_folders_still_load_with_the_new_conditions(self):
        names = {condition.folder for condition in CONDITIONS}
        for folder in (
            "Baseline", "Parkinson Mild", "Parkinson and Tremor", "Stroke Right and Tremor",
            "Jerk", "Left Hand Slow", "Diabetes Mild", "Diabetes Strong",
            "Ataxia Mild", "Ataxia Strong", "Tremor and Diabetes", "Tremor and Ataxia",
        ):
            self.assertIn(folder, names)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_synthetic(root, apple_seeds=1)
            examples = load_examples(root)
            with (root / "Baseline" / "apples_s1" / "controller_data.csv").open() as handle:
                header = handle.readline()
        self.assertIn("target_lx", header)
        self.assertIn("cursor_ly", header)
        by_folder: dict[str, list] = {}
        for example in examples:
            folder = Path(example.recording.name).parts[0]
            by_folder.setdefault(folder, []).append(example)
        self.assertTrue(names <= set(by_folder))
        both = next(item for item in by_folder["Parkinson and Tremor"] if "apples" in item.recording.name)
        self.assertEqual(both.target.tolist(), [70.0, 0.0, 70.0])
        self.assertEqual(both.diabetes, 0.0)
        self.assertEqual(both.ataxia, 0.0)
        diabetes = next(item for item in by_folder["Diabetes Strong"] if item.activity == "apples")
        ataxia = next(item for item in by_folder["Ataxia Strong"] if item.activity == "butterfly")
        mixed = next(item for item in by_folder["Tremor and Diabetes"] if item.activity == "apples")
        path_mix = next(item for item in by_folder["Tremor and Ataxia"] if item.activity == "water")
        self.assertEqual(diabetes.diabetes, 85.0)
        self.assertEqual(ataxia.ataxia, 85.0)
        self.assertEqual(mixed.target.tolist()[2], 70.0)
        self.assertEqual(mixed.diabetes, 70.0)
        self.assertEqual(path_mix.ataxia, 70.0)
        self.assertTrue(diabetes.recording.has_targets)
        self.assertTrue(path_mix.recording.has_targets)
        hand = SimpleNamespace(hand="left")
        self.assertTrue(math.isnan(float(_target(diabetes, hand)[HAND_SCORES.index("ataxia")])))
        self.assertEqual(float(_target(diabetes, hand)[HAND_SCORES.index("diabetes")]), 85.0)
        self.assertTrue(math.isnan(float(_target(ataxia, hand)[HAND_SCORES.index("diabetes")])))
        self.assertEqual(float(_target(ataxia, hand)[HAND_SCORES.index("ataxia")]), 85.0)
        self.assertEqual(float(_target(both, hand)[HAND_SCORES.index("diabetes")]), 0.0)
        self.assertTrue(math.isnan(float(_target(both, hand)[HAND_SCORES.index("ataxia")])))


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


def _game_stick(normal: float) -> float:
    center = 127.5
    if normal >= 0.0:
        return center + normal * (255.0 - center)
    return center + normal * center


def _aimed_reach(end: float, target: float, axis: str = "x", cursor: bool = True) -> Recording:
    rest_s, move_s, hold_s = 0.45, 0.7, 0.35
    count = int(round((rest_s + move_s + hold_s) * HZ)) + 1
    rows = []
    for index in range(count):
        time_s = index / HZ
        if time_s < rest_s:
            place, phase = 0.0, "wait"
        elif time_s < rest_s + move_s:
            unit = (time_s - rest_s) / move_s
            place = end * (0.5 - 0.5 * math.cos(math.pi * unit))
            phase = "cue"
        else:
            place, phase = end, "cue"
        along_x = place if axis == "x" else 0.0
        along_y = place if axis == "y" else 0.0
        target_x = target if axis == "x" and phase == "cue" else 0.0
        target_y = target if axis == "y" and phase == "cue" else 0.0
        row = {
            "t": f"{time_s:.4f}",
            "lx": f"{_game_stick(along_x):.4f}",
            "ly": f"{_game_stick(along_y):.4f}",
            "rx": "128",
            "ry": "128",
            "gyro_x": "0",
            "gyro_y": "0",
            "gyro_z": "0",
            "acc_x": "0",
            "acc_y": "0",
            "acc_z": "0",
            "phase": phase,
            "target_lx": f"{target_x:.4f}",
            "target_ly": f"{target_y:.4f}",
            "target_rx": "0.0000",
            "target_ry": "0.0000",
        }
        if cursor:
            row["cursor_lx"] = f"{along_x:.4f}"
            row["cursor_ly"] = f"{along_y:.4f}"
            row["cursor_rx"] = "0.0000"
            row["cursor_ry"] = "0.0000"
        rows.append(row)
    return Recording.from_rows(rows, "level_1_apples/aimed")


def _tracked(wobble: float, departure: float) -> Recording:
    rest_s, track_s = 0.4, 1.6
    count = int(round((rest_s + track_s) * HZ)) + 1
    rows = []
    for index in range(count):
        time_s = index / HZ
        if time_s < rest_s:
            x = y = 0.0
            phase = "wait"
        else:
            unit = (time_s - rest_s) / track_s
            x = 0.15 + 0.70 * unit
            y = wobble * math.sin(2 * math.pi * 6 * time_s) + departure * math.sin(math.pi * unit)
            phase = "track"
        row = {
            "t": f"{time_s:.4f}",
            "lx": f"{_game_stick(x):.4f}",
            "ly": f"{_game_stick(y):.4f}",
            "rx": "128",
            "ry": "128",
            "gyro_x": "0",
            "gyro_y": "0",
            "gyro_z": "0",
            "acc_x": "0",
            "acc_y": "0",
            "acc_z": "0",
            "phase": phase,
            "target_lx": f"{x if phase == 'track' else 0.0:.4f}",
            "target_ly": "0.0000",
            "target_rx": "",
            "target_ry": "",
            "cursor_lx": f"{x:.4f}",
            "cursor_ly": f"{y:.4f}",
            "cursor_rx": "0.0000",
            "cursor_ry": "0.0000",
        }
        rows.append(row)
    return Recording.from_rows(rows, "level_2_butterfly_left/tracked")


def _left_stretch(recording: Recording):
    stretches = [item for item in build_stretches(prepare(recording), recording.cue_s, task_spans=recording.task_spans) if item.hand == "left"]
    if not stretches:
        raise AssertionError(f"{recording.name} produced no left-hand stretch")
    return max(stretches, key=lambda item: item.end_s - item.start_s)


def _channel(recording: Recording, name: str) -> np.ndarray:
    return _left_stretch(recording).values[HAND_CHANNELS.index(name)]


def _channel_std(recording: Recording, name: str) -> float:
    return float(np.std(_channel(recording, name)))


def _error_pair(recording: Recording) -> np.ndarray:
    return np.vstack([_channel(recording, "error_along"), _channel(recording, "error_across")])


def _end_error(recording: Recording) -> float:
    pair = _error_pair(recording)
    tail = np.hypot(pair[0, -8:], pair[1, -8:])
    return float(np.mean(tail))


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
