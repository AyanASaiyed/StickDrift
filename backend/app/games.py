"""Save a finished game for the logged-in senior.

The arrow game reports hit/accuracy counts per hand. These map onto the shared
`session_summaries` columns so a resident's whole history (older demo sessions
and new games) reads the same way. Timing offsets go in the metrics JSONB.
"""
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, conint

from .auth import current_senior
from .db import pool

router = APIRouter(tags=["games"])

CODE_VERSION = "web-arrows-v1"


class GameResult(BaseModel):
    protocol_version: str = Field(default="assess-v1", max_length=40)
    input_reader: Literal["gamepad_api", "keyboard"] = "gamepad_api"
    connection: Literal["usb", "bluetooth", "simulated", "unknown"] = "unknown"
    placement: Literal["hands", "table", "lap", "other"] = "other"
    status: Literal["completed", "abandoned"] = "completed"
    quality: Literal["good", "flagged", "invalid"] = "good"
    left_hits: conint(ge=0, le=99) = 0
    left_notes: conint(ge=0, le=99) = 0
    right_hits: conint(ge=0, le=99) = 0
    right_notes: conint(ge=0, le=99) = 0
    both_hits: conint(ge=0, le=99) = 0
    both_trials: conint(ge=0, le=99) = 0
    left_median_offset_ms: Optional[float] = None
    right_median_offset_ms: Optional[float] = None
    stray_moves: conint(ge=0, le=9999) = 0
    enjoyment: Optional[conint(ge=1, le=5)] = None


@router.post("/me/games", status_code=201)
def save_game(body: GameResult, me: dict = Depends(current_senior)):
    with pool.connection() as conn:
        session = conn.execute(
            """INSERT INTO sessions (participant_id, mode, protocol_version, connection,
                                     placement, status, quality, completed_at)
               VALUES (%s, 'assessment', %s, %s, %s, %s, %s, now())
               RETURNING session_id""",
            (me["account_id"], body.protocol_version,
             "simulated" if body.input_reader == "keyboard" else body.connection,
             body.placement, body.status, body.quality),
        ).fetchone()
        if body.status == "completed":
            metrics = {
                "input_reader": body.input_reader,
                "left_median_offset_ms": body.left_median_offset_ms,
                "right_median_offset_ms": body.right_median_offset_ms,
                "stray_moves": body.stray_moves,
            }
            conn.execute(
                """INSERT INTO session_summaries
                   (session_id, left_correct, left_valid, right_correct, right_valid,
                    both_correct, both_valid, enjoyment, metrics, code_version)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (session["session_id"], body.left_hits, body.left_notes, body.right_hits,
                 body.right_notes, body.both_hits, body.both_trials, body.enjoyment,
                 Jsonb(metrics), CODE_VERSION),
            )
    return {"session_id": session["session_id"], "status": body.status}


class Rating(BaseModel):
    enjoyment: conint(ge=1, le=5)


@router.patch("/me/games/{session_id}/rating", status_code=204)
def rate_game(session_id: UUID, body: Rating, me: dict = Depends(current_senior)):
    with pool.connection() as conn:
        updated = conn.execute(
            """UPDATE session_summaries ss SET enjoyment = %s
               FROM sessions s
               WHERE ss.session_id = s.session_id AND s.session_id = %s
                 AND s.participant_id = %s""",
            (body.enjoyment, session_id, me["account_id"]),
        ).rowcount
    if not updated:
        raise HTTPException(404, "Session not found.")
