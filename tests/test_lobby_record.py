"""Lobby demo recordings land as one folder per visit and one folder per level."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from backend.app.lobby_record import (
    HEADER, MOTION_COLUMNS, MOTION_NOTE, NO_MOTION_NOTE, PAD_HEADER, end_session, start_session, write_level,
)


def sample_row(live_id, seq, level, width=len(HEADER)):
    row = [None] * width
    row[0] = live_id
    row[1] = seq
    row[2] = level
    row[3] = 0.016 * seq
    row[5] = "cue"
    row[6] = 0.1
    row[7] = -0.2
    row[14] = 0
    row[15] = 1
    row[20] = "keyboard"
    if width == len(HEADER):
        row[-1] = row[3]
    return row


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.reader(stream))


class LobbyRecordTests(unittest.TestCase):
    def test_three_levels_keep_live_sample_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = start_session("keyboard", root)
            self.assertTrue(started["folder"].endswith("_lobby"))
            for level in ("apple", "fish", "rat"):
                write_level(
                    started["live_id"], started["folder"], level, True, 1.5,
                    100, 1, "keyboard",
                    [{"type": "trial", "trial": 1, "hand": "left", "reached": True}],
                    [sample_row(started["live_id"], 1, level)],
                    root,
                )
            end_session(started["live_id"], started["folder"], root)
            folder = root / started["folder"]
            session = json.loads((folder / "session.json").read_text(encoding="utf-8"))
            self.assertEqual(session["ended"][:10], session["started"][:10])
            self.assertEqual([item["level"] for item in session["levels"]], ["apple", "fish", "rat"])
            header = (folder / "level_1_apple" / "controller_data.csv").read_text(encoding="utf-8").splitlines()[0]
            for column in ("live_id", "seq", "level", "t", "trial", "phase", "lx", "ly", "rx", "ry",
                           "tgt_lx", "tgt_ly", "tgt_rx", "tgt_ry", "reached_l", "reached_r",
                           "cur_lx", "cur_ly", "cur_rx", "cur_ry", "source", "axis_0", "cross_pressed"):
                self.assertIn(column, header.split(","))
            level = json.loads((folder / "level_2_fish" / "level.json").read_text(encoding="utf-8"))
            self.assertEqual(level["results"]["trials"][0]["hand"], "left")
            self.assertTrue((folder / "level_3_rat" / "controller_data.csv").is_file())

    def test_motion_cells_are_written_and_blank_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = start_session("gamepad", root)
            live_id = started["live_id"]
            measured = sample_row(live_id, 1, "apple")
            measured[len(PAD_HEADER):len(PAD_HEADER) + 14] = [-164, 39, -54, 1106, 7063, -3059, 1, 15, 341, 0, 0, 0, 80, 0]
            missing = sample_row(live_id, 2, "apple")
            write_level(live_id, started["folder"], "apple", True, 1.0, 100, 1, "gamepad", [],
                        [measured, missing], root, motion="webhid")
            folder = root / started["folder"]
            header, first, second = read_rows(folder / "level_1_apple" / "controller_data.csv")
            self.assertEqual(tuple(header[-len(MOTION_COLUMNS):]), MOTION_COLUMNS)
            motion = dict(zip(header, first))
            self.assertEqual(motion["gyro_x"], "-164")
            self.assertEqual(motion["acc_y"], "7063")
            self.assertEqual(motion["battery"], "80")
            self.assertEqual(motion["Mute"], "0")
            self.assertEqual(motion["t_wall"], motion["t"])
            blank = dict(zip(header, second))
            for column in MOTION_COLUMNS[:-1]:
                self.assertEqual(blank[column], "")
            self.assertEqual(blank["t_wall"], blank["t"])
            session = json.loads((folder / "session.json").read_text(encoding="utf-8"))
            self.assertEqual(session["columns"], list(HEADER))
            self.assertEqual(session["note"], MOTION_NOTE)
            level = json.loads((folder / "level_1_apple" / "level.json").read_text(encoding="utf-8"))
            self.assertEqual(level["motion"], "webhid")

    def test_old_width_rows_get_blank_motion_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = start_session("keyboard", root)
            row = sample_row(started["live_id"], 1, "fish", width=len(PAD_HEADER))
            write_level(started["live_id"], started["folder"], "fish", False, 1.0, None, None,
                        "keyboard", [], [row], root)
            folder = root / started["folder"]
            header, first = read_rows(folder / "level_2_fish" / "controller_data.csv")
            self.assertEqual(len(first), len(HEADER))
            cells = dict(zip(header, first))
            self.assertTrue(all(cells[column] == "" for column in MOTION_COLUMNS[:-1]))
            self.assertEqual(cells["t_wall"], cells["t"])
            session = json.loads((folder / "session.json").read_text(encoding="utf-8"))
            self.assertEqual(session["note"], NO_MOTION_NOTE)

    def test_rejects_a_folder_outside_the_recording_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = start_session("gamepad", root)
            with self.assertRaises(ValueError):
                write_level(started["live_id"], "../" + started["folder"], "apple", False, 1,
                            None, None, "gamepad", [], [sample_row(started["live_id"], 1, "apple")], root)


if __name__ == "__main__":
    unittest.main()
