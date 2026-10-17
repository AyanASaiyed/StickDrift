# Stick Drift

A short two-thumbstick activity for senior-living and long-term-care settings that helps care teams notice when a resident's response pattern changes.

A resident plays a 2–4 minute game on a PS5 controller, following large on-screen arrows with one or both thumbsticks. Stick Drift records how they respond, builds a baseline from that resident's own sessions, and shows the care team a review card when something shifts, such as slower responses, more missed prompts, or a new left/right difference.

The output is **a change worth checking**. Stick Drift does not diagnose, predict disease, or decide whether something is an emergency. A nurse or caregiver reads the card, adds context, and decides what happens next.

> Built for Hack the Valley 11 (PointClickCare: Catch It Early).

## How it works

```
DualSense (USB-C) → browser game (Gamepad API) → FastAPI + Tiger Data → baseline + review rules → care-team dashboard
```

1. **Connect and calibrate.** Staff pick a pseudonymous resident profile. The resident presses a button to connect the controller, then the app measures each stick's resting center, jitter and range. If calibration fails, the hardware-check screen says so before the session starts.
2. **Practice.** 4–8 unscored prompts so the resident can get used to the controls. Practice is never stored as performance history.
3. **Assessment.** Three fixed blocks of 12 prompts each: left hand only, right hand only, and both hands. Every prompt has a visible cue, a fixed 2-second response window, and a pause to recenter. The protocol is identical in every session so the results can be compared.
4. **Finish.** The resident sees a neutral, positive completion screen and can rate the session 1–5. Staff see the data-quality status and, once there is enough history, the trend card.

A separate free-play mode may add speed or themes. It is labeled **not used for health trends** and never feeds the baseline.

## What it measures

| Metric | Definition |
| --- | --- |
| Response latency | Time from cue onset to the first valid stick movement, per hand and direction (median and spread) |
| Direction accuracy | Correct first responses out of valid prompts, plus wrong-direction, missed and early-movement counts |
| Left/right gap | Difference between the two hands' latencies on matched directions, compared with that resident's usual gap |
| Two-hand timing gap | Time between the left and right threshold crossings on both-hand prompts |
| Participation | Completion, skipped sessions, retries, enjoyment rating |
| Data quality | Controller disconnects, calibration drift, unreadable trials |

A movement counts once the intended axis passes about 40% of that stick's calibrated range for 2–3 samples. The stick must return below about 20% before the next response is accepted. Timeouts and false starts are recorded as their own outcomes and never counted as slow responses.

Latency includes seeing the cue, deciding and moving, plus browser and display delay. It is not a pure motor-speed measure, and the app doesn't claim millisecond precision.

## Personal baseline and review cards

Each resident is compared only with themselves, never with a population "normal."

- A baseline needs at least 3 valid sessions over 2–3 different days, run under the same protocol version, on the same controller and in the same setup.
- For each metric, the baseline center is the median of session results, and the spread is a robust MAD-based estimate with a floor set by instrument noise.
- Sessions that fail quality checks are flagged and kept out of comparisons. A missed session is never read as decline.
- A review card is raised when two separate reliable metrics move noticeably in the same direction, or when a large change repeats on the next valid session.
- Flagged sessions are never automatically folded into the baseline. A reset happens only after documented caregiver review, and earlier history is kept.

A card shows the actual numbers, for example:

> Left-hand response median 0.82 s vs personal baseline 0.49 s; 4/12 incorrect vs 0–1/12 usual. Session quality: good. Please check in.

Staff mark each card **acknowledged**, **needs assessment**, or **dismissed with reason**, and can add a note. The app never contacts family, writes to a medical record, or names a condition.

The numbers above are illustrative. All thresholds in this project are untested design choices, not clinical cutoffs.

## AI components

- **Rule-based comparison (core).** Medians, robust spread, quality gates and explicit review rules. Every other component is measured against this.
- **Written summary (optional).** An LLM turns the computed metrics into a short note for staff. It only receives structured values, every number in its output is checked against the source, and disease names are rejected. If the API is unavailable, the app falls back to a fixed template.
- **Anomaly experiment (optional).** A small PyTorch autoencoder trained on session-level features. A high reconstruction error means "unusual compared with the training sessions," not illness. It ships only if it beats the rules on held-out data.

## Data

Stick Drift keeps raw stick samples, the prompt schedule, detected responses and the protocol version separately, so trends can be recomputed if the scoring logic changes. Data lives in [Tiger Data](https://www.tigerdata.com/) (managed PostgreSQL with TimescaleDB). Raw stick samples go in a hypertable partitioned by time. Each resident has a profile with their session history and per-session results.

Because Tiger Data is a cloud service, data leaves the laptop. Profiles hold only a nickname or code and a dominant hand: never a real name or other health information. The connection string stays in `backend/.env`, which is not committed. There is no camera, microphone or other biometric capture.

The multi-day trends in the demo are **synthetic and labeled as such**. The short baseline in the demo comes from consenting adult teammates and is not clinical data.

## Hardware

- Sony DualSense (PS5) controller, connected by a USB-C **data** cable. Use wired for assessments: Bluetooth adds latency and jitter.
- A laptop running Chrome.

Each session records the controller ID, connection type and how the controller was placed (in hand, on a table, on a lap). If the controller is unavailable, a keyboard simulator uses the same event format and is clearly labeled **SIMULATED** on screen.

## Tech stack

- **Web app:** Vite, React, TypeScript, Gamepad API (resident game at `/play`, care dashboard at `/care`)
- **Backend:** Python, FastAPI, psycopg
- **Database:** Tiger Data (PostgreSQL + TimescaleDB)
- **Analysis:** pandas, NumPy, PyTorch (optional)

## Running locally

The Python game scripts live in `Controller Data - Zain`. From the repository
root, install the locked dependencies with [uv](https://docs.astral.sh/uv/):

```powershell
uv sync
```

Connect a DualSense controller over USB, then start a game:

```powershell
uv run python "Controller Data - Zain\trace.py" --player P01 --session 1
uv run python "Controller Data - Zain\catch.py" --player P01 --session 1
uv run python "Controller Data - Zain\maze.py" --player P01 --session 1
```

Optional game flags include `--seed 42` (repeatable randomized layouts) and
`--kids` for red decoys in Catch. Each game writes its CSV and JSON session
files to a `data/` directory under the current working directory. To test
controller input separately, run:

```powershell
uv run python "Controller Data - Zain\read_data.py"
```
You need Node 20+, Python 3.9+, Chrome, and a Tiger Data service.

**1. Database.** Create a service in Tiger Console and copy its connection string. Then:

```bash
cd backend
cp .env.example .env          # paste the connection string into DATABASE_URL
psql "$(grep ^DATABASE_URL .env | cut -d= -f2-)" -f schema.sql
```

**2. Backend.**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.seed_synthetic   # optional: two demo profiles with SYNTHETIC history
uvicorn app.main:app --reload      # http://localhost:8000
```

**3. Web app.**

```bash
cd web
npm install
npm run dev                        # http://localhost:5173
```

If the API runs somewhere other than `http://localhost:8000`, set `VITE_API_URL` in `web/.env`.

## Project layout

For design decisions, guardrails and what's built so far, read [Context.MD](Context.MD).

```
Context.MD                   Project context, guardrails, current build state, decision log
Controller Data - Zain/
  read_data.py               DualSense reader over HID (~500 Hz): live viewer + CSV recording
  Example PS5 Data.csv       Sample recording
backend/
  schema.sql                 Tiger Data tables (participants, sessions, results, trials, raw samples)
  app/main.py                API: profiles and session history
  scripts/seed_synthetic.py  Labeled synthetic demo data
web/
  src/App.tsx                Landing page: controller check, profile picker, start, history
  src/useGamepad.ts          DualSense input via the Gamepad API
```

### API

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/health` | Database reachable |
| GET | `/participants` | Profiles with session count and last played |
| POST | `/participants` | Create a profile `{alias, dominant_hand}` |
| GET | `/participants/{id}` | One profile |
| GET | `/participants/{id}/sessions` | Session history with results, newest first |

## Limitations

- This is a hackathon prototype, not a medical device, and it has not been clinically validated.
- A change in results can come from fatigue, sleep, medication, vision, unfamiliarity with game controllers, controller placement, or a faulty device. The dashboard shows data quality and context for this reason.
- The joystick task is loosely inspired by clinical movement comparisons. It does not implement a validated exam and cannot measure grip strength, tremor or posture.
- Usability findings are preliminary unless they come from older adults and care staff.
- Anyone with a sudden new neurological symptom needs normal urgent care. Nobody should wait on a game score.
