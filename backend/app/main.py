import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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
)


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
                      ss.both_correct, ss.both_valid, ss.enjoyment
               FROM sessions s
               LEFT JOIN session_summaries ss ON ss.session_id = s.session_id
               WHERE s.participant_id = %s
               ORDER BY s.started_at DESC
               LIMIT %s""",
            (participant_id, min(limit, 200)),
        ).fetchall()
