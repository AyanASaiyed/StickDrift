"""Run with: python -m unittest discover -s tests -p test_garden_story.py

Headless, synthetic only. Exercises actual chapter loops and exported records.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Controller Data - Zain" / "Games"))
import pygame
import garden as core
from garden_story import HoldGesture
from garden_diorama import DioramaGame


class GestureTests(unittest.TestCase):
    def test_neutral_required_hold_cancels_and_rearms(self):
        g = HoldGesture(0.8)
        self.assertFalse(g.update(False, True, 0))
        self.assertFalse(g.update(False, True, 2))
        g.update(True, False, 3)
        self.assertFalse(g.update(False, True, 4))
        g.update(False, False, 4.3)
        self.assertFalse(g.update(False, True, 5))
        self.assertTrue(g.update(False, True, 5.9))
        self.assertFalse(g.update(False, True, 7))
        g.update(True, False, 8)
        g.update(False, True, 9)
        self.assertTrue(g.update(False, True, 10))


class StoryTests(unittest.TestCase):
    def setUp(self):
        self.previous = os.getcwd()
        self.temp = tempfile.TemporaryDirectory(prefix="stickdrift-story-test-")
        os.chdir(self.temp.name)
        args = argparse.Namespace(player="synthetic_test", session=1, label="synthetic",
                                  level="all", mute=True, fullscreen=False, demo=True,
                                  preview=None, reduced_motion=True)
        self.game = DioramaGame(args)
        self.game.centers = dict.fromkeys(("lx", "ly", "rx", "ry"), 128)
        self.game.rec.centers = self.game.centers

    def tearDown(self):
        self.game.rec.close()
        pygame.quit()
        os.chdir(self.previous)
        self.temp.cleanup()

    def scripted_events(self, down=False, disconnect=False):
        calls = 0
        original = self.game.reader.state.copy()

        def events():
            nonlocal calls
            calls += 1
            if disconnect and calls < 4:
                self.game.reader.state = None
                return None, False, False
            state = original.copy()
            state["ly"] = (238 if down else 18) if calls > 7 else 128
            self.game.reader.state = state
            return state, False, False
        return events

    def test_card_and_reconnect_use_sticks_without_buttons(self):
        self.game._events = self.scripted_events()
        self.game.card(["A picnic awaits", "Welcome to the garden."], min_s=0)
        self.assertEqual(self.game.rec.depth, 0)
        self.game._events = self.scripted_events(disconnect=True)
        before = self.game.now()
        self.game.pause_screen(lost=True)
        self.assertEqual(self.game.rec.depth, 0)
        self.assertLess(self.game.now() - before, 0.1)
        self.assertEqual(self.game.meta["disconnects"], 1)

    def test_pause_can_finish_with_stick_and_resumes_recorder_depth(self):
        self.game._events = self.scripted_events(down=True)
        with self.assertRaises(core.QuitGame):
            self.game.pause_screen(lost=False)
        self.assertEqual(self.game.rec.depth, 0)

    def test_calibration_waits_for_released_stick(self):
        self.game.centers = None
        self.game.card = lambda *a, **kw: None
        state = self.game.reader.state.copy()
        calls = 0

        def events():
            nonlocal calls
            calls += 1
            state["ly"] = 18 if calls < 15 else 128
            self.game.reader.state = state
            return state, False, False

        self.game._events = events
        self.game.calibrate()
        self.assertEqual(self.game.centers["ly"], 128)
        self.assertGreater(self.game.meta["calibration"]["samples_60hz"], 30)

    def test_all_chapters_write_consistent_raw_data(self):
        game = self.game
        game.card = lambda *a, **kw: None

        def autopilot():
            ctx = game.rec.ctx
            dt = game.now() - ctx.trial_t0 if ctx.trial_t0 is not None else None
            lt, rt = ctx.target(dt)
            game.cur = tuple(lt or (0, 0)) + tuple(rt or (0, 0))
            game.disp = {"left": game.cur[:2], "right": game.cur[2:]}
            state = game.reader.state.copy()
            for key, value in zip(("lx", "ly", "rx", "ry"), game.cur):
                state[key] = round(128 + value * (127 if value > 0 else 128))
            game.rec.sample(time.perf_counter(), state)
            time.sleep(0.002)

        game.tick = autopilot
        with patch.multiple(core, APPLE_ITI=0.02, REST_HOLD=0.01, START_HOLD=0.01,
                            FLY_LAP=0.15, WATER_SECS=0.15):
            for chapter in core.LEVELS:
                game.run_level(chapter)
        self.assertEqual(len(game.meta["levels"]), 4)
        self.assertTrue(game.meta["is_synthetic"])
        for level in game.meta["levels"]:
            folder = Path(game.folder) / level["folder"]
            info = json.loads((folder / "level.json").read_text())
            self.assertEqual(info["protocol"], "garden-v3")
            self.assertTrue(info["completed"])
            with (folder / "controller_data.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertGreater(len(rows), 0)
            self.assertEqual(len(rows), info["rows"])
            self.assertTrue(all(None not in row for row in rows))
            self.assertTrue(all(row["level"] == level["level"] for row in rows))
            times = [float(row["t"]) for row in rows]
            self.assertEqual(times, sorted(times))
            self.assertTrue(all(-1 <= float(row["cursor_lx"]) <= 1 for row in rows))
            if level["level"] == "apples":
                self.assertEqual(len(info["results"]), 6)
                self.assertTrue(all(r["reached_l"] and r["reached_r"] for r in info["results"]))


if __name__ == "__main__":
    unittest.main()
