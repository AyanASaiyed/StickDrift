# Stick Drift

Controller games for senior-living and long-term-care residents that help care teams notice when someone's movement changes.

A resident logs in, opens a small 3D game lobby, and plays short games with a PS5 controller: picking apples, tracing a fish through a harbour, catching rats. While they play, Stick Drift measures how each hand moves: how quickly it reacts, how fast and far it reaches, how closely it follows a path, and how much it shakes. A caregiver on any computer can watch the session live, then review every visit, see trends over time, and ask an AI assistant about the results.

The output is **a change worth checking**, never a diagnosis. Stick Drift does not name conditions, predict disease, or decide whether something is an emergency. A nurse or caregiver reads the numbers, adds context, and decides what happens next.

> Built for Hack the Valley 11 (PointClickCare: Catch It Early).

## How it works

```
Resident's laptop                                         Caregiver's laptop (any computer)
─────────────────                                         ─────────────────────────────────
Browser: 3D lobby + games ──samples──► FastAPI ──┐   ┌──► FastAPI ──WebSocket──► Dashboard, live view,
(PS5 pad via Gamepad API)                        ▼   │                             history, trends, assistant
                                          Tiger Data (PostgreSQL + TimescaleDB)
                                          live buffer · NOTIFY · history · samples
```

1. **Play.** The resident logs in and clicks **Open the lobby**. They walk Grandma around a 3D lobby with the left stick and step onto a pad to start a game.
2. **Stream.** The lobby sends stick samples, in-game hand and target positions, and one result per attempt to the resident's API, about ten times a second. That API writes them to Tiger Data and sends a Postgres `NOTIFY`.
3. **Watch live.** Any caregiver's API `LISTEN`s and pushes updates to their browser over a WebSocket. The live view shows the sticks, distance from target and measurements as they happen, about 0.1 s behind the resident.
4. **Save.** When the visit ends, it becomes a permanent session in the resident's history with per-game, per-hand results. Only in-game samples are kept for analysis and training. Walking around the lobby, menus and countdowns are dropped.
5. **Review.** Caregivers see each resident's visits, trends across visits, any potential concerns with recommended checks, and can ask the assistant questions grounded in the recorded numbers.

The two laptops share nothing but the Tiger Data database. If the resident's API runs older code and sends no notifications, the caregiver's API reads new samples directly every 0.15 s, so the view stays live either way.

## The games

### Web lobby (main experience)

A three.js lobby that runs in the browser at `/lobby.html`. Residents open it from their home page in a new tab.

| Game | What the resident does | What it measures, per hand |
| --- | --- | --- |
| **Apple Picking** | Steer a red glove (left stick) and a blue glove (right stick) to matching apples, then carry them to the basket | Apples picked, time to pick, reaction time, peak speed, how far the stick was pushed |
| **Harbour Fishing** | Trace a glowing lane with the fishing lure, one hand at a time | Distance from the lane, share of time on the lane, shake and its rhythm |
| **Rat Catching** | Flick a stick up to slam the hand when the target rat runs underneath | Target rats caught, time to slam, reaction time |

Controls: left stick walks, right stick moves the camera, Cross enters a game, Circle leaves it. A keyboard fallback exists (WASD, IJKL, Space, O); visits played that way are labelled **keyboard input** everywhere. Each game shows a score and 0–3 stars to the resident. Those are for fun and are separate from the caregiver measurements.

The games move an in-game hand with the stick (velocity control), so distance from target compares that hand with its target, while speed and shake are read from the stick itself. The game logic lives in `web/lobby/*.js`. `web/lobby/measure.js` reads each game's state without changing it.

### Mabel's Moonflower Garden (desktop game)

The original pygame game (`garden-v3`): four chapters of apple picking with both sticks, a left-stick and a right-stick butterfly flight, and watering with both sticks. It records every controller report (~500 Hz) to CSV, imports the recording into Tiger Data, and appears on the resident's page as **Garden visits**. The site no longer opens it, but it can still be run directly (see [Running the garden game](#running-the-garden-game)).

### Blender lobby

`blender_hub/hub_world.py` is the same lobby and games built inside Blender 5 (Windows only). It is a design reference and does not send data to Stick Drift. See [blender_hub/README.md](blender_hub/README.md).

## What caregivers see

- **Dashboard** (`/caregiver`). Every resident with a risk badge ("No concerns", "Keep an eye on", "Check soon"), who is playing right now, and visits that just finished.
- **Live view** (`/caregiver/live/:id`). Each in-game hand against its target, a rolling 20-second chart (distance from target or stick tilt), and measurements updating as the resident plays.
- **Resident page** (`/caregiver/residents/:id`):
  - **Overview.** Status banner and any potential concerns. Each concern shows what changed, what to check first, possible everyday reasons, and its research basis.
  - **Trends.** One line per hand across visits: time to pick an apple, time on the fishing lane, time to slam a rat (and garden or earlier sessions when the resident has them).
  - **Game visits.** The latest visit as one card per game, plus a table of every visit.
  - **Ask the assistant.** Questions about this resident, answered from their recorded measurements.

### AI assistant and guardrails

The assistant (Google Gemini, `backend/app/assistant.py`) receives only structured facts built from the database: measurements, changes from usual, concerns, recommended checks, and recent visits. Its answers are filtered before they are shown:

- Any number not present in the facts is flagged as unverified.
- Answers that name a disease or condition are replaced with a referral to a clinician.
- If the API key is missing or Gemini is unavailable, a rule-based answer built directly from the records is returned instead.

Potential concerns come from fixed rules (latest result vs that resident's own usual level) and, for garden visits, the pattern model below. They always use neutral movement wording, such as "One-sided difference between hands", never a diagnosis.

### Pattern model (`tcn/`)

A temporal convolutional network that scores garden recordings 0–100 for resemblance to five movement patterns. The labels caregivers see are:

- slowed, smaller movements in both hands;
- a one-sided difference between hands;
- shake during movement;
- reaches that land past or short, then correct;
- a hand that weaves off a moving path.

These are pattern resemblance, not disease probabilities. The model is trained on teammate-recorded and synthetic data only. **No trained checkpoint is committed.** Until `runs/tcn/model.pt` exists, garden visits are saved without a judgement. See [Training the pattern model](#training-the-pattern-model).

## Running locally

You need Node 20+, Python 3.9+ for the backend, Python 3.14 with [uv](https://docs.astral.sh/uv/) for the games and model, Chrome or Edge, and a [Tiger Data](https://www.tigerdata.com/) service.

**1. Database.** Create a service in Tiger Console and copy its connection string. Apply both schemas (they are safe to re-run):

```bash
cd backend
cp .env.example .env               # set DATABASE_URL (and the other variables below)
psql "$DATABASE_URL" -f schema.sql
psql "$DATABASE_URL" -f auth_schema.sql
```

**2. Backend.**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.seed_synthetic   # optional: two demo residents with SYNTHETIC history
python seed_accounts.py            # optional: logins for existing residents + a caregiver account
uvicorn app.main:app --port 8000
```

**3. Web app.**

```bash
cd web
npm install
npm run dev                        # http://localhost:5173 (the lobby is http://localhost:5173/lobby.html)
```

The Vite dev server proxies `/api` (including the live WebSocket) to `http://localhost:8000`, so the browser sees one origin and the login cookie just works. After pulling changes, restart both the API and the dev server.

**4. Use it.**

- Residents sign up at `/signup` and open the lobby from their home page.
- Caregivers register at `/caregiver/signup` with the access code from `CAREGIVER_INVITE_CODE`, or use the account from `seed_accounts.py`.

For the cross-laptop setup, each laptop runs its own API and web app against the same `DATABASE_URL`.

### Environment variables (`backend/.env`)

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Tiger Data connection string (never commit it) |
| `CAREGIVER_INVITE_CODE` | Access code required to register a caregiver; empty turns registration off |
| `GEMINI_API_KEY` | Enables the AI assistant; without it the rule-based answers are used |
| `GEMINI_MODEL` | Optional model override (default `gemini-3.8-flash`, with fallbacks) |
| `CORS_ORIGINS` | Allowed web origins, comma separated (default `http://localhost:5173`) |
| `GARDEN_RECORDING_TIMEZONE` | Timezone of garden CSV timestamps (default `America/Toronto`) |
| `STICKDRIFT_GAME_PYTHON`, `STICKDRIFT_API_URL` | Where the API finds Python for the garden game and model, and its own URL |

### Running the garden game

From the repository root:

```bash
uv sync
uv run python "Controller Data - Zain/Games/garden.py" --player P01 --session 1 --fullscreen
uv run python "Controller Data - Zain/Games/garden.py" --demo --mute     # keyboard, labelled synthetic
```

Each run writes `data/<timestamp>_garden_<player>_all-levels/` with one CSV and `level.json` per chapter, then imports it into Tiger Data when `backend/.env` is configured. Use `--no-tiger-sync` to skip the import, and `--reduced-motion` to still decorative motion. To import recordings later:

```bash
cd backend
python -m scripts.import_garden ../data --dry-run
python -m scripts.import_garden ../data
```

### Training the pattern model

The model trains in the root Python 3.14 environment on recordings whose folder names are the labels (see `tcn/labels.py`):

```bash
uv run python -m tcn.synthetic                                   # writes data/Synthetic
uv run python -c "from tcn import fit, load_examples; fit(load_examples('data'))"
```

This writes `runs/tcn/model.pt`. Once that file exists, the API scores each garden visit with `backend/scripts/score_garden.py` when the game closes.

## Data and privacy

Data lives in Tiger Data (managed PostgreSQL with TimescaleDB), so it leaves the laptop:

- **Profiles** hold only a nickname or code and a dominant hand, never a real name or health information.
- **Passwords** are hashed with argon2id, and logins use an HttpOnly session cookie.
- **No camera, microphone or other biometric capture.**

| Table | What it holds |
| --- | --- |
| `participants`, `caregivers`, `auth_sessions` | Accounts and logins |
| `sessions`, `session_summaries` | One row per visit (`lobby-v1` or `garden-v3`) and its per-game, per-hand results |
| `raw_samples` | Hypertable of in-game stick samples with target and in-game hand positions, tagged by game; the training data |
| `garden_level_results`, `garden_imports` | Imported garden recordings |
| `live_sessions`, `live_samples` | Short-term buffer for the live view, cleared after a day; finished visits are copied to `sessions` and `raw_samples` first |

Lobby visits are stored as free play: each visit is shown on its own and does not feed a statistical baseline yet. The multi-day histories of the demo residents are **synthetic and labelled as such**.

## Project layout

```
web/
  index.html, src/           React app: login and signup, resident home, caregiver dashboard, live view, resident pages
  src/components/            Charts, live feed (WebSocket + playback buffer), game visits, assistant, insights
  lobby.html, lobby/         Browser 3D lobby and games (three.js); live.js streams, measure.js measures
backend/
  schema.sql, auth_schema.sql   Tiger Data tables
  app/main.py                FastAPI app, health, and the low-level session API
  app/auth.py                Resident and caregiver accounts, sessions, access code
  app/live.py                Live sessions, lobby streaming, saving lobby visits, garden launch and scoring
  app/live_stream.py         LISTEN/NOTIFY hub and the caregiver WebSocket
  app/live_metrics.py        Per-hand movement measurements (reach, tracking, shake, left-right difference)
  app/views.py, insights.py  Caregiver resident data, concerns and recommended checks
  app/assistant.py           Gemini assistant with grounding and wording checks
  scripts/                   Synthetic demo data, garden import, garden scoring
  seed_accounts.py           Demo logins
tcn/                         Pattern model: data preparation, network, training, scoring
Controller Data - Zain/      DualSense reader and the pygame garden game
blender_hub/                 Blender version of the lobby
Context.MD                   Project context, guardrails and decision log
```

### API

All caregiver routes need a caregiver login; `/me/*` routes need a resident login.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/senior/signup`, `/auth/senior/login` | Resident accounts |
| POST | `/auth/caregiver/signup`, `/auth/caregiver/login` | Caregiver accounts (signup needs the access code) |
| GET / POST | `/auth/me`, `/auth/logout` | Current account, log out |
| POST | `/me/lobby/start` | Open a live session for the lobby; returns a one-time stream token |
| POST | `/live/ingest`, `/live/end` | Stream samples and events with the token; end the visit (saves it to history) |
| POST / GET | `/me/garden/launch`, `/me/garden` | Launch the desktop garden game on this computer and check its state |
| GET | `/caregiver/residents`, `/caregiver/residents/{id}` | Residents with risk; one resident's visits, insights and concerns |
| GET | `/caregiver/live`, `/caregiver/live/{id}` | Live and recently finished sessions; one session's state and samples |
| WS | `/caregiver/live/{id}/ws` | Push stream of one live session |
| POST | `/caregiver/assistant` | Ask the assistant about all residents or one |
| GET | `/health` | Database reachable |

`main.py` also keeps a lower-level `/participants` and `/sessions/{id}/…` API for recording sessions sample by sample, and `/garden/recordings` and `/sessions/{id}/garden-timeline` for imported garden data.

## Limitations

- This is a hackathon prototype, not a medical device, and it has not been clinically validated. All thresholds are untested design choices, not clinical cutoffs.
- A change in results can come from fatigue, sleep, medication, vision, unfamiliarity with game controllers, how the controller is held, or a faulty device.
- Lobby measurements are sampled at about 60 Hz in the browser, including display and network delay. They are not precise to the millisecond and are not a pure motor-speed measure.
- The pattern model is trained on teammate-simulated and synthetic recordings only, and no trained model is committed.
- Anyone with a sudden new neurological symptom needs normal urgent care. Nobody should wait on a game score.
