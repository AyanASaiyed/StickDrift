"""Insert SYNTHETIC demo profiles and sessions. Not real measurements.

Every session written here has is_synthetic = true, and the UI labels it.
Usage (from backend/):  python -m scripts.seed_synthetic
"""
import random
from datetime import datetime, timedelta, timezone

from app.db import pool

PROTOCOL = "assess-v1"
CODE_VERSION = "seed-synthetic"

# alias, dominant hand, whether later sessions drift (to show a review card later)
PROFILES = [
    ("Demo Resident A", "right", False),
    ("Demo Resident B", "left", True),
]


def summary(rng, drift):
    left = rng.gauss(820 if drift else 490, 30)
    right = rng.gauss(470, 30)
    return {
        "left_median_latency_ms": round(left),
        "right_median_latency_ms": round(right),
        "left_correct": 8 if drift else rng.choice([11, 12]),
        "left_valid": 12,
        "right_correct": rng.choice([11, 12]),
        "right_valid": 12,
        "both_correct": rng.choice([10, 11, 12]),
        "both_valid": 12,
        "lr_gap_ms": round(left - right),
        "bimanual_gap_ms": round(rng.gauss(90, 15)),
        "enjoyment": rng.choice([4, 5]),
    }


def main():
    rng = random.Random(11)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    pool.open()
    with pool.connection() as conn:
        for alias, hand, drifts in PROFILES:
            row = conn.execute(
                """INSERT INTO participants (alias, dominant_hand) VALUES (%s, %s)
                   ON CONFLICT (alias) DO NOTHING RETURNING participant_id""",
                (alias, hand),
            ).fetchone()
            if row is None:
                print(f"{alias}: already exists, skipped")
                continue
            for day in range(6, -1, -1):
                started = now - timedelta(days=day, hours=rng.randint(0, 3))
                drift = drifts and day <= 1
                session = conn.execute(
                    """INSERT INTO sessions (participant_id, mode, protocol_version, controller_id,
                                             connection, placement, status, quality, is_synthetic,
                                             started_at, completed_at)
                       VALUES (%s, 'assessment', %s, 'synthetic', 'simulated', 'table',
                               'completed', 'good', true, %s, %s)
                       RETURNING session_id""",
                    (row["participant_id"], PROTOCOL, started, started + timedelta(minutes=3)),
                ).fetchone()
                values = summary(rng, drift)
                cols = ", ".join(values)
                params = ", ".join(["%s"] * len(values))
                conn.execute(
                    f"INSERT INTO session_summaries (session_id, {cols}, code_version) "
                    f"VALUES (%s, {params}, %s)",
                    (session["session_id"], *values.values(), CODE_VERSION),
                )
            print(f"{alias}: 7 synthetic sessions")
    pool.close()


if __name__ == "__main__":
    main()
