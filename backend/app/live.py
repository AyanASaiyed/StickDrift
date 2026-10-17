"""Launch the garden game for a resident, stream it live, and judge it when it ends.

The API and the controller are on the same computer, so the API starts the game
as a local process. The game posts ~100 Hz samples and level events back here
with a one-time token. Caregivers poll a live snapshot. When the game process
exits, its CSV/JSON folder is scored by the TCN pattern model (run in the
project's Python 3.14 environment) and imported into TigerData for the resident.

Live sessions are kept in memory: restarting the API mid-game drops the live view,
but the game still saves its files, which can be imported later.
"""
import json
import logging
import os
import secrets
import subprocess
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
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

BUFFER_S = 120
SAMPLE_HZ = 100
ACTIVE = {"starting", "waiting", "ready", "playing", "paused", "saving"}
KEEP_FINISHED_S = 6 * 3600


def _now():
    return datetime.now(timezone.utc)


class LiveSession:
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
        self.samples: deque = deque(maxlen=BUFFER_S * SAMPLE_HZ)
        self.metrics = SessionMetrics()
        self.result: Optional[dict] = None
        self.db_session_id: Optional[UUID] = None
        self.error: Optional[str] = None
        self.proc: Optional[subprocess.Popen] = None

    # ---- ingest --------------------------------------------------------------

    def ingest(self, items: List[Any]):
        with self.lock:
            for item in items:
                if isinstance(item, dict):
                    self._event(item)
                elif isinstance(item, list) and len(item) == 13 and self.level:
                    self.seq += 1
                    self.samples.append((self.seq, self.level, item))
                    self.metrics.add(item)
                    self.trial, self.phase = item[1], item[2]

    def _event(self, e: dict):
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
        elif kind == "session_end":
            self.folder = e.get("folder") or self.folder
            self.status = "saving"

    # ---- views ---------------------------------------------------------------

    def brief(self) -> dict:
        end = self.ended_at or _now()
        tcn = (self.result or {}).get("scores")
        return {
            "live_id": self.id, "participant_id": self.participant_id, "name": self.name,
            "status": self.status, "level": self.level, "levels": self.levels,
            "levels_done": self.levels_done, "synthetic": self.synthetic,
            "started_at": self.created_at, "elapsed_s": round((end - self.created_at).total_seconds(), 1),
            "tcn_scores": tcn, "db_session_id": self.db_session_id, "error": self.error,
        }

    def snapshot(self, since: int, limit: int) -> dict:
        with self.lock:
            if since <= 0 or not self.samples or since < self.samples[0][0]:
                rows = list(self.samples)[-limit:]
            else:
                rows = [r for r in self.samples if r[0] > since][-limit:]
            return {**self.brief(), "trial": self.trial, "phase": self.phase, "seq": self.seq,
                    "samples": [[seq, level, *s] for seq, level, s in rows],
                    "metrics": self.metrics.summary(), "result": self.result}


SESSIONS: Dict[UUID, LiveSession] = {}
BY_TOKEN: Dict[str, LiveSession] = {}
REGISTRY_LOCK = threading.Lock()


def _prune():
    cutoff = time.time() - KEEP_FINISHED_S
    for sid, s in list(SESSIONS.items()):
        if s.status not in ACTIVE and s.ended_at and s.ended_at.timestamp() < cutoff:
            SESSIONS.pop(sid, None)
            BY_TOKEN.pop(s.token, None)


def _active_for(participant_id: Optional[UUID] = None) -> Optional[LiveSession]:
    for s in SESSIONS.values():
        if s.status in ACTIVE and (participant_id is None or s.participant_id == participant_id):
            return s
    return None


# ---- end of session -------------------------------------------------------

def _score(folder: str) -> dict:
    out = subprocess.run([str(GAME_PYTHON), str(SCORER), folder], cwd=ROOT, capture_output=True,
                         text=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip().splitlines()[-1] if out.stderr.strip() else "scorer failed")
    return json.loads(out.stdout)


def _store(s: LiveSession, tcn: Optional[dict]) -> Optional[UUID]:
    from scripts.import_garden import import_one  # backend/scripts, imported lazily

    with pool.connection() as conn:
        status, _, _, _, session_id = import_one(conn, Path(s.folder), "site-live", TIMEZONE,
                                                 participant_id=s.participant_id)
        if session_id is None:
            return None
        live_summary = s.metrics.summary()
        conn.execute(
            """UPDATE session_summaries
               SET metrics = metrics || %s, code_version = 'garden-live-v1', computed_at = now()
               WHERE session_id = %s""",
            (Jsonb({"live": live_summary, "tcn": tcn}), session_id),
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
        return

    with s.lock:
        s.status = "scoring"
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


def _watch(s: LiveSession, log_file):
    try:
        s.proc.wait()
    finally:
        log_file.close()
    try:
        _finalize(s)
    except Exception:
        log.exception("Finalizing live session failed")
        with s.lock:
            s.status, s.ended_at = "failed", _now()
            s.error = s.error or "Something went wrong while finishing this session."
    with REGISTRY_LOCK:
        BY_TOKEN.pop(s.token, None)


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
        _prune()
        mine = _active_for(me["account_id"])
        if mine is not None:
            return {"active": True, "status": mine.status, "level": mine.level}
        if _active_for() is not None:
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
    threading.Thread(target=_watch, args=(s, log_file), name=f"garden-{s.id}", daemon=True).start()
    return {"active": True, "status": s.status, "level": None}


@router.get("/me/garden", response_model=GardenStatus)
def my_garden(me: dict = Depends(current_senior)):
    s = _active_for(me["account_id"])
    return {"active": s is not None, "status": s.status if s else None, "level": s.level if s else None}


# ---- game -------------------------------------------------------------------

class IngestIn(BaseModel):
    items: List[Union[List[Any], Dict[str, Any]]] = Field(max_length=5000)


@router.post("/live/ingest")
def ingest(body: IngestIn, x_live_token: str = Header(...)):
    s = BY_TOKEN.get(x_live_token)
    if s is None:
        raise HTTPException(410, "This live session is no longer open.")
    s.ingest(body.items)
    return {"ok": True}


# ---- caregiver --------------------------------------------------------------

@router.get("/caregiver/live")
def live_list(_: dict = Depends(current_caregiver)):
    with REGISTRY_LOCK:
        _prune()
        items = sorted(SESSIONS.values(), key=lambda s: s.created_at, reverse=True)
    return [s.brief() for s in items]


@router.get("/caregiver/live/{live_id}")
def live_snapshot(live_id: UUID, since: int = 0, limit: int = 2000, _: dict = Depends(current_caregiver)):
    s = SESSIONS.get(live_id)
    if s is None:
        raise HTTPException(404, "That live session has ended or the server was restarted.")
    return s.snapshot(since, max(1, min(limit, 4000)))
