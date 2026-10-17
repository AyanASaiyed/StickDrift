"""Lobby demo recordings land as one folder per visit and one folder per level."""
import json
import tempfile
import unittest
from pathlib import Path

from backend.app.lobby_record import HEADER, end_session, start_session, write_level


def sample_row(live_id, seq, level):
    row = [None] * len(HEADER)
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
    return row


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

    def test_rejects_a_folder_outside_the_recording_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = start_session("gamepad", root)
            with self.assertRaises(ValueError):
                write_level(started["live_id"], "../" + started["folder"], "apple", False, 1,
                            None, None, "gamepad", [], [sample_row(started["live_id"], 1, "apple")], root)


if __name__ == "__main__":
    unittest.main()
