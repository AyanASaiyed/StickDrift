"""Launch the garden game for a resident, stream it live, and judge it when it ends.

The API and the controller are on the same computer, so the API starts the game
as a local process. The game posts ~100 Hz samples and level events back to that
API with a one-time token. That API writes the live state and samples to
TigerData (`live_sessions`, `live_samples`), so a caregiver signed in on any
computer sharing the database can watch. When the game process exits, its
CSV/JSON folder is scored by the TCN pattern model (run in the project's Python
3.14 environment) and imported into TigerData for the resident.

Restarting the launching API mid-game drops that session's live stream and its
end-of-session import; the game still saves its files for a later import.
"""
import copy
import json
import logging
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from .auth import current_caregiver, current_senior
from .db import pool
from .live_metrics import SessionMetrics

log = logging.getLogger(__name__)
router = APIRouter(tags=["live"])

ROOT = Path(__file__).resolve().parents[2]
GAME_SCRIPT = ROOT / "Controller Data - Zain" / "Games" / "garden.py"
GAME_PYTHON = Path(os.environ.get("STICKDRIFT_GAME_PYTHON", ROOT / ".venv" / "bin" / "python"))
SCORER = ROOT / "backend" / "scripts" / "score_garden.py"
LOG_DIR = ROOT / "data" / ".live-logs"
API_URL = os.environ.get("STICKDRIFT_API_URL", "http://127.0.0.1:8000")
TIMEZONE = os.environ.get("GARDEN_RECORDING_TIMEZONE", "America/Toronto")
HOST = socket.gethostname()
CHANNEL = "stickdrift_live"  # NOTIFY channel; caregiver APIs LISTEN on it (see live_stream.py)
NOTIFY_MAX = 7000            # Postgres caps a payload at 8000 bytes; bigger batches send only a pointer

ACTIVE = {"starting", "waiting", "ready", "playing", "paused", "saving", "scoring"}
STATE_EVERY_S = 0.5      # how often the running state/metrics row is rewritten
HEARTBEAT_S = 5          # the launching API touches the row while the game runs
STALE_S = 20             # an active row older than this lost its launching API
RECENT_H = 6             # finished sessions listed under "Just finished"
LOBBY_GAMES = ("apple", "fish", "rat")
KEEP_EVENTS = {"trial", "wrong", "basket", "expired", "result", "trace", "slam", "miss"}
MAX_FRAMES = 24000       # a visit is a few minutes at 60 Hz; stop rather than grow without bound
_FRAME_KEYS = (
    "t", "trial", "phase", "lx", "ly", "rx", "ry",
    "target_lx", "target_ly", "target_rx", "target_ry",
    "on_l", "on_r",
    "cursor_lx", "cursor_ly", "cursor_rx", "cursor_ry",
)


def _now():
    return datetime.now(timezone.utc)


class LiveSession:
    """State kept by the API that launched the game. Everyone else reads TigerData."""

    def __init__(self, participant_id: UUID, name: str, keyboard: bool):
        self.id = uuid4()
        self.token = secrets.token_urlsafe(32)
        self.participant_id = participant_id
        self.name = name
        self.keyboard = keyboard
        self.lock = threading.Lock()
        self.created_at = _now()
        self.ended_at: Optional[datetime] = None
        self.status = "starting"
        self.level: Optional[str] = None
        self.levels: List[str] = []
        self.levels_done: List[str] = []
        self.trial: Optional[int] = None
        self.phase: Optional[str] = None
        self.synthetic = keyboard
        self.folder: Optional[str] = None
        self.seq = 0
        self.metrics = SessionMetrics()
        self.result: Optional[dict] = None
        self.db_session_id: Optional[UUID] = None
        self.error: Optional[str] = None
        self.proc: Optional[subprocess.Popen] = None
        self.last_state_write = 0.0
        self.reporting = False
        # Lobby frames live here until the visit ends. They are never written to the database.
        self.capture = {name: {"frames": [], "events": []} for name in LOBBY_GAMES}

    def ingest(self, items: List[Any]) -> Tuple[List[tuple], bool]:
        """Apply events and samples; returns (sample rows to store, whether status changed)."""
        rows: List[tuple] = []
        changed = False
        with self.lock:
            for item in items:
                if isinstance(item, dict):
                    changed |= self._event(item)
                elif isinstance(item, list) and len(item) in (13, 17) and self.level:
                    # garden: 13 values; web lobby: 17, adding the in-game hand position
                    self.seq += 1
                    self.metrics.add(item)
                    self.trial, self.phase = item[1], item[2]
                    rows.append((self.id, self.seq, self.level, *item, *[None] * (17 - len(item))))
                    self._keep_frame(item)
        return rows, changed

    def _keep_frame(self, item):
        if self.level not in LOBBY_GAMES or len(item) < 17:
            return
        bucket = self.capture[self.level]
        if len(bucket["frames"]) >= MAX_FRAMES:
            bucket["truncated"] = True
            return
        bucket["frames"].append(dict(zip(_FRAME_KEYS, item[:17])))

    def _keep_event(self, event: dict):
        if event.get("type") not in KEEP_EVENTS or self.level not in LOBBY_GAMES:
            return
        self.capture[self.level]["events"].append(dict(event))

    def _event(self, e: dict) -> bool:
        self._keep_event(e)
        kind = e.get("type")
        if kind == "session_start":
            self.folder = e.get("folder")
            self.synthetic = bool(e.get("synthetic")) or self.keyboard
            self.levels = [str(x) for x in e.get("levels", [])][:8]
            self.status = "waiting"
        elif kind == "calibrated":
            self.status = "ready"
        elif kind == "level_start":
            self.level = str(e.get("level"))
            self.metrics.start_level(self.level)
            self.status = "playing"
        elif kind == "paused":
            self.status = "paused"
        elif kind == "resumed":
            self.status = "playing"
        elif kind == "level_end":
            self.metrics.close_trial()
            if e.get("level") and e.get("completed"):
                self.levels_done.append(str(e["level"]))
            self.status, self.level, self.trial, self.phase = "ready", None, None, None
        elif kind == "trial" and self.level:
            self.metrics.add_trial(e)
        elif kind == "session_end":
            self.folder = e.get("folder") or self.folder
            self.status = "saving"
        else:
            return False
        return True


# Only sessions launched by this API process. Used for tokens and "one game per computer".
SESSIONS: Dict[UUID, LiveSession] = {}
BY_TOKEN: Dict[str, LiveSession] = {}
REGISTRY_LOCK = threading.Lock()


def _active_here(participant_id: Optional[UUID] = None) -> Optional[LiveSession]:
    for s in SESSIONS.values():
        if s.status in ACTIVE and (participant_id is None or s.participant_id == participant_id):
            return s
    return None


# ---- TigerData persistence ----------------------------------------------------

def _persist(s: LiveSession, with_metrics: bool = True):
    with s.lock:
        metrics = s.metrics.summary() if with_metrics else None
        values = (s.id, s.participant_id, s.name, s.status, s.level, Jsonb(s.levels), Jsonb(s.levels_done),
                  s.trial, s.phase, s.synthetic, s.seq, None if metrics is None else Jsonb(metrics),
                  None if s.result is None else Jsonb(s.result), s.db_session_id, s.error, HOST,
                  s.created_at, s.ended_at)
    try:
        with pool.connection() as conn:
            conn.execute(
                """INSERT INTO live_sessions
                   (live_id, participant_id, name, status, level, levels, levels_done, trial, phase,
                    synthetic, seq, metrics, result, db_session_id, error, host, started_at, ended_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                   ON CONFLICT (live_id) DO UPDATE SET
                     status = EXCLUDED.status, level = EXCLUDED.level, levels = EXCLUDED.levels,
                     levels_done = EXCLUDED.levels_done, trial = EXCLUDED.trial, phase = EXCLUDED.phase,
                     synthetic = EXCLUDED.synthetic, seq = EXCLUDED.seq,
                     metrics = COALESCE(EXCLUDED.metrics, live_sessions.metrics),
                     result = EXCLUDED.result, db_session_id = EXCLUDED.db_session_id,
                     error = EXCLUDED.error, ended_at = EXCLUDED.ended_at, updated_at = now()""",
                values,
            )
            # Same transaction, so watchers are only told once the row is committed.
            conn.execute("SELECT pg_notify(%s, %s)", (CHANNEL, json.dumps({"i": str(s.id), "st": 1})))
        s.last_state_write = time.monotonic()
    except Exception:
        log.exception("Could not write live session %s to TigerData", s.id)


def _store_samples(rows: List[tuple]):
    if not rows:
        return
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO live_samples
                   (live_id, seq, level, t, trial, phase, lx, ly, rx, ry,
                    tgt_lx, tgt_ly, tgt_rx, tgt_ry, reached_l, reached_r, cur_lx, cur_ly, cur_rx, cur_ry)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                rows,
            )
            # Small batches ride in the notification itself, so watchers don't need to read the table.
            live_id = str(rows[0][0])
            payload = json.dumps({"i": live_id, "s": [list(r[1:]) for r in rows]}, separators=(",", ":"))
            if len(payload) > NOTIFY_MAX:
                payload = json.dumps({"i": live_id, "q": rows[-1][1]})
            cur.execute("SELECT pg_notify(%s, %s)", (CHANNEL, payload))
    except Exception:
        log.exception("Could not write live samples to TigerData")


def _heartbeat(s: LiveSession):
    try:
        with pool.connection() as conn:
            conn.execute("UPDATE live_sessions SET updated_at = now() WHERE live_id = %s", (s.id,))
    except Exception:
        log.exception("Live heartbeat failed")


def _prune_db():
    try:
        with pool.connection() as conn:
            conn.execute("DELETE FROM live_sessions WHERE updated_at < now() - interval '1 day'")
    except Exception:
        log.exception("Pruning old live sessions failed")


# ---- end of session -------------------------------------------------------

MODEL = ROOT / "runs" / "tcn" / "model.pt"


def _score(folder: str) -> dict:
    if not MODEL.is_file():
        raise RuntimeError("the pattern model has not been trained yet; train it to create runs/tcn/model.pt")
    out = subprocess.run([str(GAME_PYTHON), str(SCORER), folder], cwd=ROOT, capture_output=True,
                         text=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip().splitlines()[-1] if out.stderr.strip() else "scorer failed")
    return json.loads(out.stdout)


def _store(s: LiveSession, tcn: Optional[dict]) -> Optional[UUID]:
    from scripts.import_garden import import_one  # backend/scripts, imported lazily

    with pool.connection() as conn:
        _, _, _, _, session_id = import_one(conn, Path(s.folder), "site-live", TIMEZONE,
                                            participant_id=s.participant_id)
        if session_id is None:
            return None
        conn.execute(
            """UPDATE session_summaries
               SET metrics = metrics || %s, code_version = 'garden-live-v1', computed_at = now()
               WHERE session_id = %s""",
            (Jsonb({"live": s.metrics.summary(), "tcn": tcn}), session_id),
        )
        conn.execute("UPDATE sessions SET quality = 'good' WHERE session_id = %s AND quality IS NULL "
                     "AND status = 'completed'", (session_id,))
        return session_id


def _finalize(s: LiveSession):
    with s.lock:
        s.metrics.close_trial()
        folder = s.folder
    session_json = Path(folder) / "session.json" if folder else None
    levels = []
    if session_json and session_json.is_file():
        try:
            levels = json.loads(session_json.read_text(encoding="utf-8")).get("levels", [])
        except (OSError, ValueError):
            levels = []
    if not levels:
        with s.lock:
            s.status, s.ended_at = "stopped", _now()
            s.error = "The game closed before the first chapter, so there is nothing to judge."
        _persist(s)
        return

    with s.lock:
        s.status = "scoring"
    _persist(s)
    tcn, error = None, None
    try:
        tcn = _score(folder)
    except Exception as e:  # scorer problems must not lose the recording
        log.exception("TCN scoring failed for %s", folder)
        error = f"The pattern model could not score this session ({e})."
    session_id = None
    try:
        session_id = _store(s, tcn)
    except Exception as e:
        log.exception("Saving garden session failed for %s", folder)
        error = (error + " " if error else "") + f"Saving to TigerData failed ({e}); the files are kept in {folder}."
    with s.lock:
        s.result, s.db_session_id, s.error = tcn, session_id, error
        s.status = "finished" if tcn is not None else "failed"
        s.ended_at = _now()
    _persist(s)


def _watch(s: LiveSession, log_file):
    try:
        while True:
            try:
                s.proc.wait(timeout=HEARTBEAT_S)
                break
            except subprocess.TimeoutExpired:
                _heartbeat(s)
    finally:
        log_file.close()
    try:
        _finalize(s)
    except Exception:
        log.exception("Finalizing live session failed")
        with s.lock:
            s.status, s.ended_at = "failed", _now()
            s.error = s.error or "Something went wrong while finishing this session."
        _persist(s)
    with REGISTRY_LOCK:
        BY_TOKEN.pop(s.token, None)
        SESSIONS.pop(s.id, None)


# ---- resident ---------------------------------------------------------------

class LaunchIn(BaseModel):
    keyboard: bool = False


class GardenStatus(BaseModel):
    """What a resident sees: whether the game is open. No scores or history."""
    active: bool
    status: Optional[str] = None
    level: Optional[str] = None


@router.post("/me/garden/launch", response_model=GardenStatus, status_code=201)
def launch(body: LaunchIn, me: dict = Depends(current_senior)):
    if not GAME_PYTHON.is_file():
        raise HTTPException(503, "The game isn't installed on this computer yet. Ask a staff member to run "
                                 "`uv sync` in the project folder.")
    with REGISTRY_LOCK:
        mine = _active_here(me["account_id"])
        if mine is not None:
            return {"active": True, "status": mine.status, "level": mine.level}
        if _active_here() is not None:
            raise HTTPException(409, "Someone else is already playing on this computer. Try again in a few minutes.")
        s = LiveSession(me["account_id"], me["display_name"], body.keyboard)
        SESSIONS[s.id] = s
        BY_TOKEN[s.token] = s

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = open(LOG_DIR / f"{s.id}.log", "w")
    player = "".join(c if c.isalnum() or c in "-_" else "_" for c in (me.get("username") or "resident"))[:24]
    cmd = [str(GAME_PYTHON), str(GAME_SCRIPT), "--player", player, "--label", "site", "--no-tiger-sync"]
    if body.keyboard:
        cmd.append("--demo")
    env = {**os.environ, "STICKDRIFT_LIVE_URL": f"{API_URL}/live/ingest", "STICKDRIFT_LIVE_TOKEN": s.token}
    env.pop("DATABASE_URL", None)
    try:
        s.proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT,
                                  start_new_session=True)
    except OSError as e:
        log_file.close()
        with REGISTRY_LOCK:
            SESSIONS.pop(s.id, None)
            BY_TOKEN.pop(s.token, None)
        raise HTTPException(500, f"The game could not start ({e}).")
    _persist(s)
    _prune_db()
    threading.Thread(target=_watch, args=(s, log_file), name=f"garden-{s.id}", daemon=True).start()
    return {"active": True, "status": s.status, "level": None}


@router.get("/me/garden", response_model=GardenStatus)
def my_garden(me: dict = Depends(current_senior)):
    s = _active_here(me["account_id"])
    return {"active": s is not None, "status": s.status if s else None, "level": s.level if s else None}


# ---- browser lobby ------------------------------------------------------------
# The 3D lobby (web/lobby.html) runs in the resident's own browser tab. It opens a
# live session here with their login cookie and streams its stick samples to
# /live/ingest like the garden game does. The samples also stay in memory. When
# the tab closes, visit.report scores Apple Picking and Harbour Fishing, counts
# Rat Catching, stores that document, and drops the frames.

LOBBY_IDLE_S = 60        # a lobby tab that stopped posting this long ago is forgotten


def _forget(s: LiveSession):
    with REGISTRY_LOCK:
        BY_TOKEN.pop(s.token, None)
        SESSIONS.pop(s.id, None)


def _played(capture: dict) -> bool:
    return any(bucket.get("frames") or bucket.get("events") for bucket in capture.values())


def _holds_frames(value) -> bool:
    if isinstance(value, dict):
        if "frames" in value or "cursor_lx" in value:
            return True
        return any(_holds_frames(item) for item in value.values())
    if isinstance(value, list):
        return any(_holds_frames(item) for item in value)
    return False


def _run_report(capture: dict) -> dict:
    python = str(GAME_PYTHON) if GAME_PYTHON.is_file() else sys.executable
    out = subprocess.run(
        [python, "-m", "visit.report"],
        input=json.dumps(capture),
        text=True,
        capture_output=True,
        cwd=ROOT,
        timeout=180,
    )
    if out.returncode != 0:
        detail = out.stderr.strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "visit report failed")
    report = json.loads(out.stdout)
    if _holds_frames(report):
        raise RuntimeError("visit report still held the raw frames")
    return report


def _store_visit(s: LiveSession, report: dict) -> UUID:
    session_id = uuid4()
    finished = int(report.get("levels_completed") or 0)
    metrics = {
        "levels_completed": finished,
        "tcn": {
            "scores": report["model"]["scores"],
            "by_game": report["model"]["by_game"],
            "meaning": report["model"]["meaning"],
            "schema_version": report["schema_version"],
        },
        "live": report["live"],
        "visit": report,
    }
    with s.lock:
        synthetic = s.synthetic
        participant_id = s.participant_id
        started = s.created_at
    with pool.connection() as conn:
        conn.execute(
            """INSERT INTO sessions
               (session_id, participant_id, mode, protocol_version, connection, placement,
                status, quality, is_synthetic, started_at, completed_at)
               VALUES (%s, %s, 'free_play', 'lobby-v1', %s, 'other', %s, 'good', %s, %s, now())""",
            (session_id, participant_id, "simulated" if synthetic else "unknown",
             "completed" if finished else "abandoned", synthetic, started),
        )
        conn.execute(
            """INSERT INTO session_summaries (session_id, metrics, code_version)
               VALUES (%s, %s, 'lobby-report-v1')""",
            (session_id, Jsonb(metrics)),
        )
    return session_id


def _finish_visit(s: LiveSession, capture: dict):
    try:
        report = _run_report(capture)
        session_id = _store_visit(s, report)
        scores = (report.get("model") or {}).get("scores")
        with s.lock:
            s.result = {"scores": scores} if scores else None
            s.db_session_id = session_id
            s.status = "finished"
            s.ended_at = _now()
            s.error = None
    except Exception as error:
        log.exception("Lobby visit report failed")
        with s.lock:
            s.status = "failed"
            s.ended_at = _now()
            s.error = str(error)
    finally:
        capture.clear()
        _persist(s)


def _end_lobby(s: LiveSession, status: str = "ended"):
    with s.lock:
        if s.reporting:
            return
        s.reporting = True
        capture = copy.deepcopy(s.capture)
        for bucket in s.capture.values():
            bucket["frames"].clear()
            bucket["events"].clear()
            bucket.pop("truncated", None)
        s.metrics.close_trial()
        s.level = None
        played = _played(capture)
        if played:
            s.status = "scoring"
        else:
            s.status, s.ended_at = status, _now()
    _persist(s)
    _forget(s)
    if played:
        threading.Thread(target=_finish_visit, args=(s, capture), daemon=True).start()


def _prune_lobby():
    cutoff = time.monotonic() - LOBBY_IDLE_S
    for s in [s for s in SESSIONS.values() if s.proc is None and s.last_state_write < cutoff]:
        _end_lobby(s, "lost")


class LobbyStart(BaseModel):
    keyboard: bool = False


@router.post("/me/lobby/start", status_code=201)
def lobby_start(body: LobbyStart, me: dict = Depends(current_senior)):
    _prune_lobby()
    for old in [s for s in SESSIONS.values() if s.proc is None and s.participant_id == me["account_id"]]:
        _end_lobby(old)  # one open lobby per resident; a reload replaces the old tab
    s = LiveSession(me["account_id"], me["display_name"], body.keyboard)
    s.status = "ready"
    s.last_state_write = time.monotonic()
    with REGISTRY_LOCK:
        SESSIONS[s.id] = s
        BY_TOKEN[s.token] = s
    _persist(s)
    _prune_db()
    return {"live_id": s.id, "token": s.token}


@router.post("/live/end", status_code=204)
def lobby_end(x_live_token: str = Header(...)):
    s = BY_TOKEN.get(x_live_token)
    if s is not None and s.proc is None:
        _end_lobby(s)


# ---- game -------------------------------------------------------------------

class IngestIn(BaseModel):
    items: List[Union[List[Any], Dict[str, Any]]] = Field(max_length=5000)


@router.post("/live/ingest")
def ingest(body: IngestIn, x_live_token: str = Header(...)):
    s = BY_TOKEN.get(x_live_token)
    if s is None:
        raise HTTPException(410, "This live session is no longer open.")
    rows, changed = s.ingest(body.items)
    _store_samples(rows)
    if changed or time.monotonic() - s.last_state_write >= STATE_EVERY_S:
        _persist(s)
    return {"ok": True}


# ---- caregiver (reads TigerData, so any computer can watch) ----------------------

BRIEF_COLUMNS = """live_id, participant_id, name, status, level, levels, levels_done, synthetic,
                   started_at, ended_at, updated_at, db_session_id, error, host,
                   result->'scores' AS tcn_scores,
                   EXTRACT(EPOCH FROM (COALESCE(ended_at, now()) - started_at)) AS elapsed_s,
                   updated_at < now() - make_interval(secs => %s) AS stale"""


def _brief(row: dict) -> dict:
    status = row["status"]
    error = row["error"]
    if status in ACTIVE and row["stale"]:
        status = "lost"
        error = error or ("The computer running this game stopped sending updates. Its recording is saved "
                          "there and can be imported later.")
    return {
        "live_id": row["live_id"], "participant_id": row["participant_id"], "name": row["name"],
        "status": status, "level": row["level"], "levels": row["levels"], "levels_done": row["levels_done"],
        "synthetic": row["synthetic"], "started_at": row["started_at"],
        "elapsed_s": round(float(row["elapsed_s"]), 1), "tcn_scores": row["tcn_scores"],
        "db_session_id": row["db_session_id"], "error": error,
    }


@router.get("/caregiver/live")
def live_list(_: dict = Depends(current_caregiver)):
    with pool.connection() as conn:
        rows = conn.execute(
            f"""SELECT {BRIEF_COLUMNS} FROM live_sessions
                WHERE updated_at > now() - make_interval(hours => %s)
                ORDER BY started_at DESC LIMIT 20""",
            (STALE_S, RECENT_H),
        ).fetchall()
    return [_brief(r) for r in rows]


def state(live_id: UUID) -> Optional[dict]:
    """Everything about a live session except its samples, or None if it doesn't exist."""
    with pool.connection() as conn:
        row = conn.execute(
            f"SELECT {BRIEF_COLUMNS}, trial, phase, seq, metrics, result FROM live_sessions WHERE live_id = %s",
            (STALE_S, live_id),
        ).fetchone()
    if row is None:
        return None
    return {**_brief(row), "trial": row["trial"], "phase": row["phase"], "seq": row["seq"],
            "metrics": row["metrics"] or SessionMetrics().summary(), "result": row["result"]}


def samples_since(live_id: UUID, since: int, limit: int) -> List[list]:
    """The newest `limit` samples after `since`, oldest first."""
    with pool.connection() as conn:
        rows = conn.execute(
            """SELECT seq, level, t, trial, phase, lx, ly, rx, ry, tgt_lx, tgt_ly, tgt_rx, tgt_ry,
                      reached_l, reached_r, cur_lx, cur_ly, cur_rx, cur_ry
               FROM live_samples WHERE live_id = %s AND seq > %s
               ORDER BY seq DESC LIMIT %s""",
            (live_id, max(since, 0), limit),
        ).fetchall()
    return [list(r.values()) for r in reversed(rows)]


@router.get("/caregiver/live/{live_id}")
def live_snapshot(live_id: UUID, since: int = 0, limit: int = 2000, _: dict = Depends(current_caregiver)):
    limit = max(1, min(limit, 4000))
    st = state(live_id)
    if st is None:
        raise HTTPException(404, "That live session was not found.")
    return {**st, "samples": samples_since(live_id, since, limit)}

