"""Read endpoints for seniors (own data) and caregivers (all residents).

The review flag is a deterministic, non-diagnostic "change worth checking":
it compares a resident's latest completed session with the median of their
earlier ones. It never names a condition.
"""
from statistics import median
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import current_caregiver, current_senior
from .db import pool

router = APIRouter(tags=["views"])

# How much a metric must move from the personal baseline to be worth a note.
LATENCY_RISE_MS = 150.0
ACCURACY_DROP = 2  # out of 12


class SessionSummary(BaseModel):
    session_id: UUID
    started_at: Any
    completed_at: Optional[Any]
    status: str
    quality: Optional[str]
    mode: str
    protocol_version: str
    left_median_latency_ms: Optional[float]
    right_median_latency_ms: Optional[float]
    left_correct: Optional[int]
    left_valid: Optional[int]
    right_correct: Optional[int]
    right_valid: Optional[int]
    both_correct: Optional[int]
    both_valid: Optional[int]
    enjoyment: Optional[int]


class Review(BaseModel):
    flagged: bool
    reasons: List[str]


class ResidentRow(BaseModel):
    participant_id: UUID
    username: Optional[str]
    display_name: str
    dominant_hand: str
    session_count: int
    last_played_at: Optional[Any]
    review: Review


class ResidentDetail(BaseModel):
    participant_id: UUID
    username: Optional[str]
    display_name: str
    dominant_hand: str
    review: Review
    sessions: List[SessionSummary]


def _fetch_sessions(conn, participant_id: UUID) -> List[dict]:
    return conn.execute(
        """SELECT s.session_id, s.started_at, s.completed_at, s.status, s.quality,
                  s.mode, s.protocol_version,
                  ss.left_median_latency_ms, ss.right_median_latency_ms,
                  ss.left_correct, ss.left_valid, ss.right_correct, ss.right_valid,
                  ss.both_correct, ss.both_valid, ss.enjoyment
           FROM sessions s
           LEFT JOIN session_summaries ss ON ss.session_id = s.session_id
           WHERE s.participant_id = %s
           ORDER BY s.started_at DESC""",
        (participant_id,),
    ).fetchall()


def _review(sessions: List[dict]) -> Review:
    """Compare the latest completed session with the median of earlier ones."""
    usable = [
        s for s in sessions
        if s["status"] == "completed" and s["quality"] in ("good", "flagged")
    ]
    # sessions come newest-first; baseline needs history before the latest.
    if len(usable) < 4:
        return Review(flagged=False, reasons=[])
    latest, prior = usable[0], usable[1:]
    reasons: List[str] = []

    def prior_median(key):
        vals = [s[key] for s in prior if s[key] is not None]
        return median(vals) if vals else None

    for hand, key in (("Left", "left_median_latency_ms"), ("Right", "right_median_latency_ms")):
        base, now = prior_median(key), latest[key]
        if base is not None and now is not None and now - base >= LATENCY_RISE_MS:
            reasons.append(
                f"{hand}-hand response slower: {now/1000:.2f} s vs usual {base/1000:.2f} s."
            )

    for hand, ckey, vkey in (("left", "left_correct", "left_valid"), ("right", "right_correct", "right_valid")):
        base, now, valid = prior_median(ckey), latest[ckey], latest[vkey]
        if base is not None and now is not None and base - now >= ACCURACY_DROP:
            reasons.append(
                f"{hand.capitalize()}-hand accuracy lower: {now}/{valid} vs usual {int(base)}/{valid}."
            )

    return Review(flagged=bool(reasons), reasons=reasons)


# ---- senior (own data) ---------------------------------------------------

@router.get("/me/sessions", response_model=List[SessionSummary])
def my_sessions(me: dict = Depends(current_senior)):
    with pool.connection() as conn:
        return _fetch_sessions(conn, me["account_id"])


# ---- caregiver (all residents) -------------------------------------------

@router.get("/caregiver/residents", response_model=List[ResidentRow])
def residents(_: dict = Depends(current_caregiver)):
    with pool.connection() as conn:
        people = conn.execute(
            """SELECT p.participant_id, p.username, p.alias, p.dominant_hand,
                      count(s.session_id)::int AS session_count,
                      max(s.started_at) AS last_played_at
               FROM participants p
               LEFT JOIN sessions s ON s.participant_id = p.participant_id
               GROUP BY p.participant_id
               ORDER BY p.alias""",
        ).fetchall()
        out = []
        for p in people:
            review = _review(_fetch_sessions(conn, p["participant_id"]))
            out.append({
                "participant_id": p["participant_id"], "username": p["username"],
                "display_name": p["alias"], "dominant_hand": p["dominant_hand"],
                "session_count": p["session_count"], "last_played_at": p["last_played_at"],
                "review": review,
            })
    # Flagged residents first, then by name.
    out.sort(key=lambda r: (not r["review"].flagged, r["display_name"].lower()))
    return out


@router.get("/caregiver/residents/{participant_id}", response_model=ResidentDetail)
def resident_detail(participant_id: UUID, _: dict = Depends(current_caregiver)):
    with pool.connection() as conn:
        p = conn.execute(
            "SELECT participant_id, username, alias, dominant_hand FROM participants WHERE participant_id = %s",
            (participant_id,),
        ).fetchone()
        if p is None:
            raise HTTPException(404, "Resident not found.")
        sessions = _fetch_sessions(conn, participant_id)
    return {
        "participant_id": p["participant_id"], "username": p["username"],
        "display_name": p["alias"], "dominant_hand": p["dominant_hand"],
        "review": _review(sessions), "sessions": sessions,
    }
