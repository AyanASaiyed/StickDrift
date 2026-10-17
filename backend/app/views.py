"""Caregiver read endpoints for residents' history and performance.

Residents do not get a history view; only caregivers see results. Insights come
from `insights.analyze` (earlier session summaries compared with the resident's own
baseline) plus the TCN pattern judgement of their latest garden session.
"""
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import current_caregiver
from .db import pool
from .insights import add_model_concerns, analyze, review_from

router = APIRouter(tags=["views"])


class SessionSummary(BaseModel):
    session_id: UUID
    started_at: Any
    completed_at: Optional[Any]
    status: str
    quality: Optional[str]
    mode: str
    protocol_version: str
    is_synthetic: bool = False
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


class ConcernBrief(BaseModel):
    id: str
    title: str
    level: str


class ResidentRow(BaseModel):
    participant_id: UUID
    username: Optional[str]
    display_name: str
    dominant_hand: str
    session_count: int
    last_played_at: Optional[Any]
    review: Review
    risk: str
    concerns: List[ConcernBrief]
    # Oldest -> newest, completed sessions only, for a sparkline.
    trend_left_ms: List[Optional[float]]
    trend_right_ms: List[Optional[float]]


class GardenSession(BaseModel):
    session_id: UUID
    started_at: Any
    status: str
    is_synthetic: bool
    levels_completed: Optional[int]
    levels_total: int = 4
    tcn: Optional[dict]
    live: Optional[dict]


class ResidentDetail(BaseModel):
    participant_id: UUID
    username: Optional[str]
    display_name: str
    dominant_hand: str
    review: Review
    insights: dict
    sessions: List[SessionSummary]
    garden_sessions: List[GardenSession]


def _fetch_sessions(conn, participant_id: UUID) -> List[dict]:
    return conn.execute(
        """SELECT s.session_id, s.started_at, s.completed_at, s.status, s.quality,
                  s.mode, s.protocol_version, s.is_synthetic,
                  ss.left_median_latency_ms, ss.right_median_latency_ms,
                  ss.left_correct, ss.left_valid, ss.right_correct, ss.right_valid,
                  ss.both_correct, ss.both_valid, ss.enjoyment
           FROM sessions s
           LEFT JOIN session_summaries ss ON ss.session_id = s.session_id
           WHERE s.participant_id = %s AND s.protocol_version NOT LIKE 'garden-%%'
             AND s.protocol_version <> 'lobby-v1'
           ORDER BY s.started_at DESC""",
        (participant_id,),
    ).fetchall()


def _fetch_garden(conn, participant_id: UUID) -> List[dict]:
    return conn.execute(
        """SELECT s.session_id, s.started_at, s.status, s.is_synthetic,
                  (ss.metrics->>'levels_completed')::int AS levels_completed,
                  CASE WHEN s.protocol_version = 'lobby-v1' THEN 3 ELSE 4 END AS levels_total,
                  ss.metrics->'tcn' AS tcn, ss.metrics->'live' AS live
           FROM sessions s
           LEFT JOIN session_summaries ss ON ss.session_id = s.session_id
           WHERE s.participant_id = %s
             AND (s.protocol_version LIKE 'garden-%%' OR s.protocol_version = 'lobby-v1')
           ORDER BY s.started_at DESC LIMIT 50""",
        (participant_id,),
    ).fetchall()


def resident_profile(conn, participant_id: UUID) -> Optional[dict]:
    p = conn.execute(
        "SELECT participant_id, username, alias, dominant_hand FROM participants WHERE participant_id = %s",
        (participant_id,),
    ).fetchone()
    if p is None:
        return None
    sessions = _fetch_sessions(conn, participant_id)
    garden = _fetch_garden(conn, participant_id)
    insights = add_model_concerns(analyze(sessions), garden)
    return {
        "participant_id": p["participant_id"], "username": p["username"],
        "display_name": p["alias"], "dominant_hand": p["dominant_hand"],
        "review": review_from(insights), "insights": insights, "sessions": sessions,
        "garden_sessions": garden,
    }


def all_profiles(conn) -> List[dict]:
    ids = conn.execute(
        """SELECT p.participant_id FROM participants p
           WHERE p.username IS NOT NULL
           ORDER BY p.alias"""
    ).fetchall()
    return [resident_profile(conn, r["participant_id"]) for r in ids]


# ---- caregiver (all residents) -------------------------------------------

RISK_ORDER = {"check": 0, "watch": 1, "none": 2}


@router.get("/caregiver/residents", response_model=List[ResidentRow])
def residents(_: dict = Depends(current_caregiver)):
    with pool.connection() as conn:
        profiles = all_profiles(conn)
    out = []
    for p in profiles:
        sessions = p["sessions"]
        done = [s for s in reversed(sessions) if s["status"] == "completed"][-12:]
        played = [x["started_at"] for x in sessions[:1] + p["garden_sessions"][:1]]
        out.append({
            "participant_id": p["participant_id"], "username": p["username"],
            "display_name": p["display_name"], "dominant_hand": p["dominant_hand"],
            "session_count": len(sessions) + len(p["garden_sessions"]),
            "last_played_at": max(played) if played else None,
            "review": p["review"], "risk": p["insights"]["risk"],
            "concerns": p["insights"]["concerns"],
            "trend_left_ms": [s["left_median_latency_ms"] for s in done],
            "trend_right_ms": [s["right_median_latency_ms"] for s in done],
        })
    out.sort(key=lambda r: (RISK_ORDER[r["risk"]], r["display_name"].lower()))
    return out


@router.get("/caregiver/residents/{participant_id}", response_model=ResidentDetail)
def resident_detail(participant_id: UUID, _: dict = Depends(current_caregiver)):
    with pool.connection() as conn:
        profile = resident_profile(conn, participant_id)
    if profile is None:
        raise HTTPException(404, "Resident not found.")
    return profile
