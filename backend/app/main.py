import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, List, Literal, Optional
from uuid import UUID, uuid4

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb

from . import assistant, auth, games, views
from .db import pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(title="Stick Drift API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,  # the login cookie needs this on cross-origin calls
)
app.include_router(auth.router)
app.include_router(views.router)
app.include_router(games.router)
app.include_router(assistant.router)


class ParticipantIn(BaseModel):
    alias: str = Field(min_length=1, max_length=40)
    dominant_hand: Literal["left", "right", "unknown"]


class Participant(BaseModel):
    participant_id: UUID
    alias: str
    dominant_hand: str
    created_at: datetime
    session_count: int
    last_played_at: Optional[datetime]


class SessionRow(BaseModel):
    session_id: UUID
    mode: str
    protocol_version: str
    status: str
    quality: Optional[str]
    is_synthetic: bool
    connection: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    left_median_latency_ms: Optional[float]
    right_median_latency_ms: Optional[float]
    left_correct: Optional[int]
    left_valid: Optional[int]
    right_correct: Optional[int]
    right_valid: Optional[int]
    both_correct: Optional[int]
    both_valid: Optional[int]
    enjoyment: Optional[int]
    metrics: Optional[dict[str, Any]] = None


Activity = Literal['target_reach', 'target_tracking', 'bilateral_control']


class SessionCreate(BaseModel):
    mode: Literal['assessment', 'free_play'] = 'assessment'
    protocol_version: str = Field(default='garden-v1', min_length=1, max_length=40)
    controller_id: Optional[str] = Field(default=None, max_length=200)
    connection: Literal['usb', 'bluetooth', 'simulated', 'unknown'] = 'unknown'
    placement: Literal['hands', 'table', 'lap', 'other'] = 'other'
    is_synthetic: bool = False


class SessionCreated(BaseModel):
    session_id: UUID
    started_at: datetime


class RawSample(BaseModel):
    seq: int = Field(ge=0)
    # Monotonic milliseconds relative to the session start, not wall-clock time.
    t_ms: float = Field(ge=0, allow_inf_nan=False)
    lx: float = Field(ge=-1, le=1, allow_inf_nan=False)
    ly: float = Field(ge=-1, le=1, allow_inf_nan=False)
    rx: float = Field(ge=-1, le=1, allow_inf_nan=False)
    ry: float = Field(ge=-1, le=1, allow_inf_nan=False)
    connected: bool = True
    activity: Optional[Activity] = None
    trial_id: Optional[int] = Field(default=None, ge=1, le=32767)
    target_x: Optional[float] = Field(default=None, allow_inf_nan=False)
    target_y: Optional[float] = Field(default=None, allow_inf_nan=False)
    cursor_x: Optional[float] = Field(default=None, allow_inf_nan=False)
    cursor_y: Optional[float] = Field(default=None, allow_inf_nan=False)


class SampleBatch(BaseModel):
    samples: List[RawSample] = Field(min_length=1, max_length=500)


class TrialRecord(BaseModel):
    trial_id: int = Field(ge=1, le=32767)
    activity: Activity
    block: Literal['practice', 'left', 'right', 'both']
    hand: Literal['left', 'right', 'both']
    direction_l: Optional[Literal['up', 'down', 'left', 'right']] = None
    direction_r: Optional[Literal['up', 'down', 'left', 'right']] = None
    cue_onset_ms: float = Field(ge=0, allow_inf_nan=False)
    deadline_ms: float = Field(gt=0, allow_inf_nan=False)
    details: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal['correct', 'wrong_direction', 'omission', 'false_start', 'invalid']
    detected_l: Optional[str] = None
    detected_r: Optional[str] = None
    cross_l_ms: Optional[float] = None
    cross_r_ms: Optional[float] = None
    latency_ms: Optional[float] = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    code_version: str = Field(default='web-garden-v1', min_length=1, max_length=80)


class EventRecord(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    t_ms: float = Field(ge=0, allow_inf_nan=False)
    event_type: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    events: List[EventRecord] = Field(min_length=1, max_length=200)


class SessionFinish(BaseModel):
    quality: Literal['good', 'flagged', 'invalid']
    enjoyment: Optional[int] = Field(default=None, ge=1, le=5)
    metrics: dict[str, Any] = Field(default_factory=dict)
    code_version: str = Field(default='web-garden-v1', min_length=1, max_length=80)


class SessionCounts(BaseModel):
    session_id: UUID
    status: str
    sample_count: int
    trial_count: int
    response_count: int
    event_count: int


class GardenRecording(BaseModel):
    session_id: UUID
    source_group: Optional[str]
    sample_count: int
    level_count: int
    started_at: datetime
    status: str
    is_synthetic: bool


class GardenSecond(BaseModel):
    bucket: datetime
    activity: Optional[str]
    sample_count: int
    left_magnitude: Optional[float]
    right_magnitude: Optional[float]
    disconnected_count: int


PARTICIPANT_SELECT = """
    SELECT p.participant_id, p.alias, p.dominant_hand, p.created_at,
           count(s.session_id)::int AS session_count,
           max(s.started_at) AS last_played_at
    FROM participants p
    LEFT JOIN sessions s ON s.participant_id = p.participant_id
"""


@app.get("/health")
def health():
    with pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"ok": True}


@app.get("/participants", response_model=List[Participant])
def list_participants():
    with pool.connection() as conn:
        return conn.execute(
            PARTICIPANT_SELECT + " GROUP BY p.participant_id ORDER BY p.alias"
        ).fetchall()


@app.post("/participants", response_model=Participant, status_code=201)
def create_participant(body: ParticipantIn):
    alias = body.alias.strip()
    if not alias:
        raise HTTPException(422, "Alias can't be blank.")
    try:
        with pool.connection() as conn:
            row = conn.execute(
                """INSERT INTO participants (alias, dominant_hand) VALUES (%s, %s)
                   RETURNING participant_id, alias, dominant_hand, created_at""",
                (alias, body.dominant_hand),
            ).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "A profile with that alias already exists.")
    return {**row, "session_count": 0, "last_played_at": None}


@app.get("/participants/{participant_id}", response_model=Participant)
def get_participant(participant_id: UUID):
    with pool.connection() as conn:
        row = conn.execute(
            PARTICIPANT_SELECT + " WHERE p.participant_id = %s GROUP BY p.participant_id",
            (participant_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Profile not found.")
    return row


@app.get("/participants/{participant_id}/sessions", response_model=List[SessionRow])
def list_sessions(participant_id: UUID, limit: int = 50):
    with pool.connection() as conn:
        return conn.execute(
            """SELECT s.session_id, s.mode, s.protocol_version, s.status, s.quality,
                      s.is_synthetic, s.connection, s.started_at, s.completed_at,
                      ss.left_median_latency_ms, ss.right_median_latency_ms,
                      ss.left_correct, ss.left_valid, ss.right_correct, ss.right_valid,
                      ss.both_correct, ss.both_valid, ss.enjoyment, ss.metrics
               FROM sessions s
               LEFT JOIN session_summaries ss ON ss.session_id = s.session_id
               WHERE s.participant_id = %s
               ORDER BY s.started_at DESC
               LIMIT %s""",
            (participant_id, min(limit, 200)),
        ).fetchall()


@app.post('/participants/{participant_id}/sessions', response_model=SessionCreated, status_code=201)
def create_session(participant_id: UUID, body: SessionCreate):
    with pool.connection() as conn:
        exists = conn.execute(
            'SELECT 1 FROM participants WHERE participant_id = %s', (participant_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(404, 'Profile not found.')
        row = conn.execute(
            """INSERT INTO sessions (participant_id, mode, protocol_version, controller_id,
                                      connection, placement, is_synthetic)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING session_id, started_at""",
            (participant_id, body.mode, body.protocol_version, body.controller_id,
             body.connection, body.placement, body.is_synthetic),
        ).fetchone()
    return row


@app.post('/sessions/{session_id}/samples')
def append_samples(session_id: UUID, body: SampleBatch):
    with pool.connection() as conn:
        session = conn.execute(
            'SELECT started_at, status FROM sessions WHERE session_id = %s', (session_id,)
        ).fetchone()
        if session is None:
            raise HTTPException(404, 'Session not found.')
        if session['status'] != 'in_progress':
            raise HTTPException(409, 'Samples can only be added to an in-progress session.')
        rows = [
            (session['started_at'] + timedelta(milliseconds=s.t_ms), session_id, s.seq, s.t_ms,
             s.lx, s.ly, s.rx, s.ry, s.connected, s.activity, s.trial_id,
             s.target_x, s.target_y, s.cursor_x, s.cursor_y)
            for s in body.samples
        ]
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO raw_samples
                   (time, session_id, seq, t_ms, lx, ly, rx, ry, connected, activity,
                    trial_id, target_x, target_y, cursor_x, cursor_y)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (time, session_id, seq) DO NOTHING""",
                rows,
            )
    return {'received': len(rows), 'session_id': session_id}


@app.post('/sessions/{session_id}/trials', status_code=201)
def save_trial(session_id: UUID, body: TrialRecord):
    with pool.connection() as conn:
        session = conn.execute(
            'SELECT status FROM sessions WHERE session_id = %s', (session_id,)
        ).fetchone()
        if session is None:
            raise HTTPException(404, 'Session not found.')
        if session['status'] != 'in_progress':
            raise HTTPException(409, 'Trials can only be added to an in-progress session.')
        conn.execute(
            """INSERT INTO trials
               (session_id, trial_id, block, hand, direction_l, direction_r, cue_onset_ms,
                deadline_ms, activity, details)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (session_id, trial_id) DO UPDATE SET
                 block = EXCLUDED.block, hand = EXCLUDED.hand,
                 direction_l = EXCLUDED.direction_l, direction_r = EXCLUDED.direction_r,
                 cue_onset_ms = EXCLUDED.cue_onset_ms, deadline_ms = EXCLUDED.deadline_ms,
                 activity = EXCLUDED.activity, details = EXCLUDED.details""",
            (session_id, body.trial_id, body.block, body.hand, body.direction_l,
             body.direction_r, body.cue_onset_ms, body.deadline_ms, body.activity,
             Jsonb(body.details)),
        )
        conn.execute(
            """INSERT INTO responses
               (session_id, trial_id, outcome, detected_l, detected_r, cross_l_ms,
                cross_r_ms, latency_ms, metrics, code_version)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (session_id, trial_id) DO UPDATE SET
                 outcome = EXCLUDED.outcome, detected_l = EXCLUDED.detected_l,
                 detected_r = EXCLUDED.detected_r, cross_l_ms = EXCLUDED.cross_l_ms,
                 cross_r_ms = EXCLUDED.cross_r_ms, latency_ms = EXCLUDED.latency_ms,
                 metrics = EXCLUDED.metrics, code_version = EXCLUDED.code_version""",
            (session_id, body.trial_id, body.outcome, body.detected_l, body.detected_r,
             body.cross_l_ms, body.cross_r_ms, body.latency_ms, Jsonb(body.metrics),
             body.code_version),
        )
    return {'session_id': session_id, 'trial_id': body.trial_id, 'saved': True}


@app.post('/sessions/{session_id}/events')
def append_events(session_id: UUID, body: EventBatch):
    with pool.connection() as conn:
        session = conn.execute(
            'SELECT status FROM sessions WHERE session_id = %s', (session_id,)
        ).fetchone()
        if session is None:
            raise HTTPException(404, 'Session not found.')
        if session['status'] != 'in_progress':
            raise HTTPException(409, 'Events can only be added to an in-progress session.')
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO session_events (event_id, session_id, t_ms, event_type, payload)
                   VALUES (%s, %s, %s, %s, %s) ON CONFLICT (event_id) DO NOTHING""",
                [(e.event_id, session_id, e.t_ms, e.event_type, Jsonb(e.payload)) for e in body.events],
            )
    return {'received': len(body.events), 'session_id': session_id}


@app.post('/sessions/{session_id}/complete')
def complete_session(session_id: UUID, body: SessionFinish):
    with pool.connection() as conn:
        row = conn.execute(
            """UPDATE sessions SET status = 'completed', quality = %s, completed_at = now()
               WHERE session_id = %s AND status = 'in_progress'
               RETURNING session_id""",
            (body.quality, session_id),
        ).fetchone()
        if row is None:
            exists = conn.execute(
                'SELECT status FROM sessions WHERE session_id = %s', (session_id,)
            ).fetchone()
            if exists is None:
                raise HTTPException(404, 'Session not found.')
            if exists['status'] != 'completed':
                raise HTTPException(409, 'Session is not in progress.')
        conn.execute(
            """INSERT INTO session_summaries (session_id, enjoyment, metrics, code_version)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (session_id) DO UPDATE SET
                 enjoyment = EXCLUDED.enjoyment, metrics = EXCLUDED.metrics,
                 code_version = EXCLUDED.code_version, computed_at = now()""",
            (session_id, body.enjoyment, Jsonb(body.metrics), body.code_version),
        )
    return {'session_id': session_id, 'status': 'completed', 'quality': body.quality}


@app.post('/sessions/{session_id}/abandon')
def abandon_session(session_id: UUID):
    with pool.connection() as conn:
        row = conn.execute(
            """UPDATE sessions SET status = 'abandoned', completed_at = now()
               WHERE session_id = %s AND status = 'in_progress' RETURNING session_id""",
            (session_id,),
        ).fetchone()
        if row is None:
            exists = conn.execute('SELECT 1 FROM sessions WHERE session_id = %s', (session_id,)).fetchone()
            if exists is None:
                raise HTTPException(404, 'Session not found.')
            raise HTTPException(409, 'Session is not in progress.')
    return {'session_id': session_id, 'status': 'abandoned'}


@app.get('/sessions/{session_id}/data-status', response_model=SessionCounts)
def session_data_status(session_id: UUID):
    with pool.connection() as conn:
        row = conn.execute(
            """SELECT s.session_id, s.status,
                      (SELECT count(*) FROM raw_samples r WHERE r.session_id = s.session_id)::int AS sample_count,
                      (SELECT count(*) FROM trials t WHERE t.session_id = s.session_id)::int AS trial_count,
                      (SELECT count(*) FROM responses r WHERE r.session_id = s.session_id)::int AS response_count,
                      (SELECT count(*) FROM session_events e WHERE e.session_id = s.session_id)::int AS event_count
               FROM sessions s WHERE s.session_id = %s""",
            (session_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, 'Session not found.')
    return row


@app.get('/garden/recordings', response_model=List[GardenRecording])
def garden_recordings(limit: int = 100, _: dict = Depends(auth.current_caregiver)):
    with pool.connection() as conn:
        return conn.execute(
            """SELECT s.session_id, i.source_group, i.sample_count, s.started_at,
                      s.status, s.is_synthetic,
                      (SELECT count(*) FROM garden_level_results l
                       WHERE l.session_id = s.session_id)::int AS level_count
               FROM garden_imports i
               JOIN sessions s ON s.session_id = i.session_id
               ORDER BY s.started_at DESC LIMIT %s""",
            (max(1, min(limit, 500)),),
        ).fetchall()


@app.get('/sessions/{session_id}/garden-timeline', response_model=List[GardenSecond])
def garden_timeline(session_id: UUID, _: dict = Depends(auth.current_caregiver)):
    with pool.connection() as conn:
        exists = conn.execute(
            'SELECT 1 FROM garden_imports WHERE session_id = %s', (session_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(404, 'Garden recording not found.')
        return conn.execute(
            """SELECT bucket, activity, sample_count, left_magnitude,
                      right_magnitude, disconnected_count
               FROM garden_sample_seconds
               WHERE session_id = %s
               ORDER BY bucket, activity""",
            (session_id,),
        ).fetchall()
