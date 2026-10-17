"""Write lobby demo recordings under data/new_game_data.

Each browser visit is one folder. Apple, fishing, and rat each get a level
folder with controller_data.csv and level.json, plus a session.json for the visit.
"""
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "new_game_data"

LEVELS = {"apple": 1, "fish": 2, "rat": 3}
FOLDER_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_lobby(_\d+)?$")
MAX_ROWS = 20000
MAX_TRIALS = 500

# Matches web/lobby/input.js AXIS_COUNT and BUTTON_NAMES, then record.js sampleRow.
LIVE_COLUMNS = (
    "live_id", "seq", "level", "t", "trial", "phase",
    "lx", "ly", "rx", "ry",
    "tgt_lx", "tgt_ly", "tgt_rx", "tgt_ry",
    "reached_l", "reached_r",
    "cur_lx", "cur_ly", "cur_rx", "cur_ry",
)
BUTTON_NAMES = (
    "cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2",
    "share", "options", "l3", "r3", "dpad_up", "dpad_down", "dpad_left", "dpad_right", "ps", "touchpad",
)
AXIS_COUNT = 8
HEADER = (
    LIVE_COLUMNS
    + ("source",)
    + tuple(f"axis_{i}" for i in range(AXIS_COUNT))
    + tuple(part for name in BUTTON_NAMES for part in (f"{name}_pressed", f"{name}_value"))
)

PARAMS = {
    "apple": {
        "hand": "both",
        "activity": "target_reach",
        "time_s": 15,
        "score": "100 per apple in the basket, minus 25 per wrong-colour touch",
    },
    "fish": {
        "hand": "one at a time",
        "activity": "target_tracking",
        "rounds": 2,
        "score": "6 x percent on the lane, plus 25 per second under 12 s",
    },
    "rat": {
        "hand": "either",
        "activity": "target_reach",
        "score": "300 per target caught, minus 100 for a wrong rat, minus 50 for an empty slam",
    },
}


class RecordingError(ValueError):
    pass


def _cell(value):
    if value is None:
        return ""
    return value


def _session_path(folder: str, live_id: str, root: Path) -> Path:
    if not FOLDER_RE.fullmatch(folder):
        raise RecordingError("Unknown recording folder")
    try:
        UUID(live_id)
    except ValueError as error:
        raise RecordingError("Unknown recording") from error
    path = (root / folder).resolve()
    if path.parent != root.resolve() or not path.is_dir():
        raise RecordingError("Unknown recording folder")
    meta_path = path / "session.json"
    if not meta_path.is_file():
        raise RecordingError("Unknown recording folder")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("live_id") != live_id:
        raise RecordingError("Recording id does not match this folder")
    return path


def start_session(source: str, root: Path = DATA) -> dict:
    if source not in ("gamepad", "keyboard", "none"):
        raise RecordingError("Unknown input source")
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder = f"{stamp}_lobby"
    path = root / folder
    suffix = 2
    while path.exists():
        folder = f"{stamp}_lobby_{suffix}"
        path = root / folder
        suffix += 1
        if suffix > 20:
            raise RecordingError("Could not create a recording folder")
    # The public folder name stays the timestamp form. A collision gets a suffix
    # that still cannot climb out of new_game_data.
    if not FOLDER_RE.fullmatch(folder):
        raise RecordingError("Could not create a recording folder")
    live_id = str(uuid4())
    path.mkdir(parents=True)
    meta = {
        "protocol": "lobby-v1",
        "game": "lobby",
        "live_id": live_id,
        "started": datetime.now().isoformat(timespec="seconds"),
        "ended": None,
        "source": source,
        "levels": [],
        "columns": list(HEADER),
        "coordinates": "lx/ly/rx/ry, tgt_* and cur_* match live_samples: -1..1, y grows downward. axis_* is the browser Gamepad axis, y grows downward.",
        "note": "Sampled at the lobby frame rate from the browser Gamepad API. Gyro, accelerometer, touch points, and battery are not available.",
    }
    (path / "session.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return {"live_id": live_id, "folder": folder}


def _check_rows(rows, live_id: str, level: str):
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise RecordingError("Too many samples")
    if not rows:
        raise RecordingError("Level has no samples")
    width = len(HEADER)
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, list) or len(row) != width:
            raise RecordingError("Sample row has the wrong columns")
        if row[0] != live_id or row[1] != index or row[2] != level:
            raise RecordingError("Sample row does not match this level")
        for cell_index, value in enumerate(row):
            if cell_index in (0, 2, 5, 20):
                if value is not None and (not isinstance(value, str) or len(value) > 80):
                    raise RecordingError("Bad sample text")
            elif isinstance(value, bool) or (value is not None and not isinstance(value, (int, float))):
                raise RecordingError("Bad sample number")


def write_level(live_id: str, folder: str, level: str, completed: bool, duration_s: float,
                score, stars, source: str, trials, rows, root: Path = DATA) -> dict:
    if level not in LEVELS:
        raise RecordingError("Unknown level")
    if source not in ("gamepad", "keyboard", "none"):
        raise RecordingError("Unknown input source")
    if not isinstance(duration_s, (int, float)) or not 0 <= float(duration_s) <= 3600:
        raise RecordingError("Bad level duration")
    if trials is None:
        trials = []
    if not isinstance(trials, list) or len(trials) > MAX_TRIALS:
        raise RecordingError("Too many trials")
    _check_rows(rows, live_id, level)
    path = _session_path(folder, live_id, root)
    number = LEVELS[level]
    level_dir = path / f"level_{number}_{level}"
    level_dir.mkdir(parents=True, exist_ok=True)
    with (level_dir / "controller_data.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(HEADER)
        for row in rows:
            writer.writerow([_cell(value) for value in row])
    level_meta = {
        "protocol": "lobby-v1",
        "live_id": live_id,
        "level": level,
        "number": number,
        "completed": bool(completed),
        "rows": len(rows),
        "duration_s": round(float(duration_s), 3),
        "score": score,
        "stars": stars,
        "source": source,
        "params": PARAMS[level],
        "results": {"trials": trials},
    }
    (level_dir / "level.json").write_text(json.dumps(level_meta, indent=1), encoding="utf-8")
    session_path = path / "session.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    entry = {
        "level": level,
        "folder": level_dir.name,
        "completed": bool(completed),
        "rows": len(rows),
        "duration_s": level_meta["duration_s"],
        "score": score,
        "stars": stars,
    }
    session["levels"] = [item for item in session.get("levels", []) if item.get("level") != level]
    session["levels"].append(entry)
    session["levels"].sort(key=lambda item: LEVELS[item["level"]])
    if source != "none":
        session["source"] = source
    session_path.write_text(json.dumps(session, indent=1), encoding="utf-8")
    return {"folder": str(level_dir), "rows": len(rows)}


def end_session(live_id: str, folder: str, root: Path = DATA) -> None:
    path = _session_path(folder, live_id, root)
    session_path = path / "session.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["ended"] = datetime.now().isoformat(timespec="seconds")
    session_path.write_text(json.dumps(session, indent=1), encoding="utf-8")
