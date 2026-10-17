# Stick Drift — project context and scope guardrails

> Living document for the Hack the Valley 11 team and any coding or research agents helping us. Last updated: 2026-10-16 (America/Toronto). Change decisions in the log at the bottom rather than silently changing the mission.
>
> **Read §0 first** for what is actually built. Sections 1–13 are the plan and the guardrails.

## 0. Current build state (2026-10-16)

**Hardware changed:** we use one **Sony DualSense (PS5) controller** instead of an Arduino with two thumbstick modules. Its two sticks give the same four axes (LX, LY, RX, RY), so the measurement design below is unchanged. All Arduino wiring has been removed from §7.

**Database chosen:** **Tiger Data** (managed PostgreSQL + TimescaleDB) replaces local SQLite. Raw stick samples go in a hypertable.

| Area | State | Where |
| --- | --- | --- |
| Landing page | **Built, verified in browser.** Controller connect status with live stick preview, keyboard-simulator toggle (labeled SIMULATED), profile picker, create profile (nickname + dominant hand), Start button gated on input + profile, per-profile session history with results and synthetic labels. | `web/` (Vite + React + TS) |
| Browser controller input | **Built, not yet tested with a real controller.** Gamepad API, polled once per animation frame (~60 Hz), standard mapping, DualSense detected by vendor/product ID. | `web/src/useGamepad.ts` |
| Python controller reader | **Built and tested on hardware** (by Zain). Reads the DualSense directly over HID (USB or Bluetooth), live tkinter viewer, records CSV with sticks, triggers, buttons, gyro, accelerometer, touchpad, battery. Example recording: ~526 Hz, 3.1 s. | `Controller Data - Zain/` |
| API | **Built, tested on local Postgres, not yet on Tiger Data.** FastAPI: `GET /health`, `GET/POST /participants`, `GET /participants/{id}`, `GET /participants/{id}/sessions`. | `backend/app/main.py` |
| Database schema | **Written, tested on plain Postgres.** Tables: `participants`, `sessions`, `session_summaries`, `trials`, `responses`, `raw_samples` (hypertable). The TimescaleDB lines have not run yet. | `backend/schema.sql` |
| Synthetic demo data | **Built.** Two profiles × 7 sessions, all `is_synthetic = true`. "Demo Resident B" has slower left-hand results in the last two sessions to exercise the review card. | `backend/scripts/seed_synthetic.py` |
| Garden Rescue (`garden-v2`) | **Built, smoke-tested headless with a simulated reader; v1 was tried on hardware and was too hard, long and clinical.** Pygame garden story, ~60-90 s of play: apples (both sticks, mirrored, 6 pairs), butterfly left (12 s), butterfly right (12 s, mirrored), watering (both sticks, mirrored, 15 s). Calibrates stick centres at start. One folder per level with `controller_data.csv` (every HID report, Example PS5 Data columns + task context, recorded only while the level runs) and `level.json`. `--label` tags simulated-pattern demos; no scoring. | `Controller Data - Zain/Games/garden.py` |
| Calibration screen | Not started in the web app (Garden Rescue has its own). | — |
| Assessment game (practice + 3 blocks) | Not started. The Start button shows a "not built yet" notice. | — |
| Event detection / scoring | Not started. | — |
| Baseline + review rules | Not started. | — |
| Care-team dashboard + review card | Not started. | — |
| LLM summary, PyTorch experiment | Not started (P1). | — |

**Run it:** see `README.md` → *Running locally*. You need a `backend/.env` with the Tiger Data connection string (copy `backend/.env.example`). Never commit `.env`.

**Python environments (needs tidying):** the repo root has a `uv` project (`pyproject.toml`, Python ≥ 3.14, `hidapi`) for the HID reader. The backend uses `backend/requirements.txt` and was tested on Python 3.9. Pick one approach before the codebases meet (see §11).

## 1. The project in one paragraph

Stick Drift is a **short, enjoyable, two-hand joystick activity** that can be repeated in a senior-living or long-term-care setting. A resident sees clear directional prompts, moves one or both thumbsticks on a PS5 controller, and gets immediate, respectful game feedback. The laptop reads the controller's four stick axes directly. The software measures how the resident responds, establishes an **individual baseline**, and surfaces meaningful changes—such as slower responses, more missed prompts, or a new left/right difference—to a **care-team dashboard** with the supporting data. Its promised output is **“a change worth checking,”** never a diagnosis, predicted disease, or emergency determination. A nurse or caregiver supplies the interpretation and decides what to do next.

## 2. Mission, user, and why it matters

**Mission:** Make a brief movement and attention check pleasant enough to repeat, and make changes visible early enough for a care team to follow up. We are testing whether an accessible game can collect useful, consistent observations without feeling like yet another clinical test.

**Primary user:** Older adult living in a senior-care setting. **Primary customer/workflow user:** Care team member (nurse, CNA, wellness director, therapist). **Secondary stakeholders:** Family and clinicians, if the care facility chooses to share information. **Possible future audience:** Children in pediatric rehabilitation; this is *not* the lead story for the PointClickCare sponsor challenge.

**The gap:** Staff have limited time to notice subtle changes between formal assessments. A one-off reaction score means little; a repeated, standardized activity may reveal a change relative to the resident's own pattern. Game design may help participation, but engagement is a hypothesis we should test, not a fact to assume.

**Value loop:** Resident plays → calibrated movement events are recorded → features are compared against a personal baseline → an explainable, appropriately cautious review prompt reaches the care team → a human records context and follows up.

**Why the physical interface matters:** A standard, inexpensive controller gives the same left- and right-thumb input every session and a tangible live demo. We record continuous stick position, not just button presses. The controller is a prototype interaction device, **not a clinically validated neurologic instrument**. It cannot directly measure grip strength, applied pressure, true hand tremor, posture, or a specific illness. Both hands are on one device, so the hands are not mechanically independent the way two separately mounted sticks would be; record how the controller was held or placed.

## 3. Track fit and judging story

| Prize / track | Fit | What the demo must prove |
| --- | --- | --- |
| **PointClickCare: Catch It Early** | **Primary**. Its brief explicitly asks for an AI-powered solution that helps a nursing-home/senior-living **care team** notice a health risk before an emergency. Our narrower use case is a new change in hand movement or response pattern worth follow-up. | A caregiver receives a useful, evidence-linked review card, sees how today's measurements differ from the resident's own history, records an observation, and can dismiss or escalate the prompt. A game alone does not satisfy this track. |
| **Best Healthcare & Well-being Hack** | Strong secondary fit: accessible resident experience plus measurable caregiver workflow. | A working physical interface, a usable resident experience, trustworthy measurement and honest limits. |
| **Best AI for Social Impact Hack** | Possible if the AI adds a defensible capability to early review or usable summaries. | Compare the AI layer with a simple baseline, show actual measured numbers and failure handling; avoid a decorative chatbot. |
| **Best Use of Gemini API** | Optional only if we actually use Gemini meaningfully, such as a grounded narrative summary from structured measurements and care notes. | Demonstrate a faithful explanation with source values, and a deterministic fallback when the API is unavailable. Do not switch models just to claim a sponsor prize. |

Hack the Valley's judging also emphasizes technical quality, design, impact, presentation, inspiration, and authenticity. A polished, honest end-to-end story beats an unsupported disease classifier. The School of Cities challenge requires a Toronto civic problem grounded in urban data; **this product does not naturally fit that track**. Do not force that claim.

**Four-minute demo arc:** (1) Show a resident playing 30–60 seconds on the controller's two sticks. (2) Show raw axes and prompt events updating live. (3) Open a clearly labeled *simulated* later session with a repeatable change. (4) Show the care-team card: “Left-hand response median 0.82 s vs personal baseline 0.49 s; 4/12 incorrect vs 0–1/12 usual. Please check in.” (5) Record a caregiver note and show that the card says **review**, not “Parkinson's detected.” The numbers here are illustrative, not clinical cutoffs.

## 4. Non-negotiable product boundaries

1. The product is an **observation and review tool**, not a diagnostic, treatment, or emergency-response device. No model output names stroke, Parkinson's, MS, dementia, or another disease from joystick performance.
2. A change may be caused by fatigue, sleep, medications, vision, instructions, unfamiliarity with games, device placement, or a faulty controller. The interface shows context and confidence/quality rather than hiding uncertainty.
3. Preserve comparable **assessment rounds**: same prompt rules, input interpretation, order policy, trial counts, timing, and calibrated equipment for baseline and follow-ups. Optional themes, celebration, and a separate challenge mode can vary without changing the measured task. Do not automatically increase assessment speed and then compare raw scores.
4. Do not use childlike visuals or a competitive leaderboard for the older-adult pitch. Make the experience age-respectful: large arrows, high contrast, adjustable sound, clear instructions, no penalty or shame for missing a prompt, an easy pause and opt-out.
5. No hidden camera or biometric collection is required. Start with stick data only. The DualSense also reports gyro, accelerometer and touchpad data: **do not use them in v1 metrics, and never present motion data as tremor detection.** Use synthetic, clearly labeled data for any multi-day change we cannot actually observe during the hackathon.
6. A sudden new neurological symptom in real life warrants ordinary urgent clinical procedures; no one should wait for the game or an AI score.

## 5. Game and measurement protocol

### Resident flow

1. Care staff selects a pseudonymous resident profile; the resident agrees to play. Seat the person comfortably. The controller is held in both hands or rested on a table or lap; use the same placement every session and record it. Record dominant hand, but do not assume it performs identically to the other hand.
2. Calibrate each stick while untouched; ask for one gentle movement to each direction. Show an obvious hardware-check screen before starting.
3. Provide 4–8 unscored practice prompts, then a short pause. No performance history is created from practice.
4. **Fixed assessment mode (`assess-v1`):** three blocks of 12 prompts each: left-hand-only, right-hand-only, and both-hands. In the first two blocks, balance up/down/left/right; in the third, use a predefined balanced set of same-direction and opposite-direction pairs. Counterbalance the order of left and right blocks across sessions (or keep a fixed order and record it); never silently change the protocol. Each trial has a visible cue, a fixed response window (for example 2 seconds), and a neutral recenter period. ~2–4 minutes total including instructions and breaks. If the resident needs a shorter mode, define a separate protocol version and build its own baseline.
5. Optional free-play mode may add speed, stories, or personal high scores; it must be labeled **not used for health trends** unless separately validated.
6. At the end: resident sees a neutral, positive completion screen; staff sees data-quality status and, when sufficient history exists, the trend card.

### Trial timing and classification (engineering proposal; tune empirically)

- **Input path is an open decision (§11).** Two working readers exist:
  - *Browser Gamepad API* (`web/src/useGamepad.ts`): axes normalized to −1…1, read once per display frame (~60 Hz, ~16 ms resolution). Samples and cue onsets share one clock (`performance.now()`), which keeps timing simple and honest.
  - *Python HID* (`Controller Data - Zain/read_data.py`): raw 0–255 axes at ~500 Hz over USB, plus buttons, triggers and IMU. Finer resolution, but samples must be streamed to the browser (e.g. WebSocket), and the Python clock must be aligned with the browser's cue-onset clock.
- Log each sample with `seq`, a monotonic timestamp, `LX`, `LY`, `RX`, `RY`, and a connected flag. Log dropped reports and disconnects.
- Normalize each axis relative to its own measured center and travel in each direction. The untouched DualSense is not perfectly centered: in Zain's recording the right stick rested at 129–130 / 131–132 on a 0–255 scale (center 127.5), so always calibrate the center rather than assuming it. Mark a directional response when the intended axis exceeds a calibrated threshold, initially around **40% of that stick's observed range**, for at least **2–3 samples**. Require return to a neutral zone, perhaps 20%, before accepting the next response; the split thresholds create hysteresis. Validate with real users and comfort.
- Gamepad API Y axes are negative for up; HID Y bytes are low for up. Fix orientation in one stored mapping, not ad hoc.
- A trial starts when the cue is visibly presented, not when the random prompt is chosen. USB/Bluetooth, polling, display refresh, and OS scheduling add latency, so do not claim millisecond clinical precision. Use a USB-C data cable for assessment sessions; Bluetooth adds latency and jitter.
- Only score a prompt if hardware quality is good and the hand was centered at trial start. Record timeouts and false starts explicitly; do not turn invalid trials into slow responses.
- Keep **raw signals**, **derived events**, **prompt schedule**, and **protocol version** so trends can be recomputed if the scoring logic changes.

### What we can measure

| Signal | Operational definition | Interpretation / caveat |
| --- | --- | --- |
| Prompt response latency | Cue appearance to first valid threshold crossing, per hand and direction; report median and spread over valid trials. | Mixed visual attention, decision, motor movement, and timing-system latency; not a pure motor-speed measure. |
| Direction accuracy | Correct first response / valid prompts; also wrong first direction, omission, and premature movement counts. | Affected by understanding, vision, and practice as well as movement. |
| Correction latency | Time from first incorrect movement to first valid intended movement, if within the window. | Exploratory; useful for describing behavior, not a diagnostic sign. |
| Time to full excursion | Threshold crossing to calibrated target amplitude; optional endpoint stability/overshoot. | Only if the stick has enough usable range and sampling quality. |
| Left/right asymmetry | Compare **matched** unimanual directions, e.g. `median_L - median_R` and normalized difference `abs(L-R)/((L+R)/2)`. Track changes in *that person's* asymmetry. | Dominance and mechanical differences matter; asymmetry by itself is not disease evidence. |
| Two-hand coordination | In both-hand trials, absolute difference between the two threshold-crossing times; dual-task miss rate. | Also influenced by task comprehension and prompt complexity. |
| Within-session change | Slope/early-versus-late latency and errors in the fixed block. | Possible fatigue or learning; descriptive only with so few trials. |
| Neutral instability | Variation in stick readings when untouched and during recentering. | First treat as device jitter/noise; **do not market as tremor detection**. |
| Participation / usability | Completion rate, skipped sessions, retries, voluntary replay, simple enjoyment question (1–5), and opt-outs. | Product evidence; do not conflate intention to replay with actual longitudinal adherence. |

**Primary dashboard metrics for v1:** median response latency for each hand, first-response accuracy for each hand, matched-direction left/right gap, two-hand timing gap, participation, and data quality. Everything else is exploratory. These map to `session_summaries` in `backend/schema.sql`.

## 6. Establishing a controlled personal baseline

**A baseline is the person's own stable reference under a fixed protocol, not a population-wide “healthy” score.**

1. **Hardware/calibration baseline:** With both sticks untouched, gather 1–2 seconds of readings per axis for centers and neutral jitter. Move each axis slowly in both directions to find comfortable, observed ranges; store controller-specific calibration. Recheck each session. If the center or range shifts substantially, re-calibrate and mark the session as potentially noncomparable.
2. **Practice effect:** Run unscored practice first. If the person is still learning the controls, record “baseline pending.” Avoid treating the first game ever as a stable reference.
3. **Controlled sessions:** As a proposed starting protocol, collect at least **3 separate sessions over 2–3 different days**, with the same block definitions, prompt windows, display, controller, placement, connection type, and assistance policy. These numbers are design choices to be tested, **not published clinical thresholds**. Record time of day, dominant hand, assistive needs, interruptions, tiredness/pain or other context if voluntarily supplied. Repeat the exact protocol on follow-up days.
4. **Quality gates:** Reject or flag a session with disconnects, dropped reports, bad neutral calibration, too many unreadable trials, a changed controller, or interrupted instructions. Do not interpret missed sessions as declining health.
5. **Compute reference:** For each feature, take the median of session summaries as center; compute a robust spread (for example `1.4826 × median(|x - median(x)|)`), with a floor informed by instrument noise to avoid dividing by zero. Retain the actual session range and count. Separate baseline by protocol version; store controller ID, connection type, calibration, and assistance status.
6. **Review logic:** Compare later sessions to the personal reference; show raw values, absolute change, baseline range, and context. A prototype rule might request review when **two distinct reliable metrics move materially in the same direction**, or when a large within-person change repeats on the next valid session. Exact cutoffs require validation and false-alert measurement; do not represent illustrative thresholds as medical cutoffs. Allow a human to review a sudden large shift immediately even if there is no second session.
7. **Updating:** Do not automatically absorb flagged values into the baseline. After caregiver review, a clinician-approved or explicitly documented reset may establish a new reference; retain the earlier history.

**Hackathon reality:** We cannot gather a real multi-day resident baseline during 36 hours. We can demonstrate a short **engineering baseline** from three standardized rounds with consenting adult teammates, explicitly labeled nonclinical, and use a **clearly labeled synthetic multi-day timeline** to show the intended dashboard (`backend/scripts/seed_synthetic.py`; every row has `is_synthetic = true` and the UI labels it). Never present fabricated patient measurements as collected evidence.

**More meaningful controlled comparison for the demo:** Have a few consenting teammates complete the identical task under two conditions—normal and, for example, a deliberate alternate-hand or distracted **demo condition**. Show that the signal pipeline reflects the condition, while acknowledging that this does not simulate disease and is not clinical validation. If testing enjoyment, compare a plain prompt screen with the gamified one on the same fixed motor protocol; record participant preference and completion, while controlling for order.

## 7. Hardware and software architecture

### Hardware

**Confirmed:** one Sony DualSense (PS5) controller, a laptop (macOS), and Chrome. **Needed:** a USB-C cable that carries **data** (not charge-only). No Arduino, wiring, camera, or extra sensors are needed for v1.

- **Connect over USB-C for assessments.** Bluetooth works with both readers but adds latency and jitter. Record the connection type on every session (`sessions.connection`).
- **Same controller for baseline and follow-ups.** Record a controller ID on every session (`sessions.controller_id`).
- **Placement:** in hands, on a table, or on a lap. Test what is comfortable for someone with reduced dexterity, use it consistently, and record it (`sessions.placement`).
- **Browser reader:** Chrome only exposes a gamepad after a button on it is pressed. The landing page shows "Press any button on the controller" until then. The standard mapping puts the left stick on axes 0/1 and the right stick on 2/3. DualSense is vendor `054c`, product `0ce6` (Edge: `0df2`).
- **Python HID reader:** `uv run "Controller Data - Zain/read_data.py"` (or `pip install hidapi`). Shows a live viewer; press **R** to record a CSV, **Esc** to quit. Only one program may hold the HID device; close it before another reader opens the controller.
- **Do not use haptics, adaptive triggers or the light bar in assessment mode** unless they are identical in every session.
- **Fallback:** a keyboard simulator using the same event schema, visibly labeled SIMULATED, keeps the demo alive if the controller fails. The landing page has the toggle; the simulator itself is not built yet.

### Software

```
DualSense ──USB-C──► browser (Gamepad API)  ─┐
          └─HID────► Python reader (optional)─┤─► FastAPI ─► Tiger Data (Postgres + TimescaleDB)
                                             │                 ▲
React app: /  landing + profiles             │                 │
           /play assessment game  ◄──────────┘   baseline + review rules (Python)
           /care care-team dashboard ◄───────────────────────── review cards
```

- **Web:** Vite + React + TypeScript, one app with routes for the landing page, `/play` and `/care`.
- **API:** Python, FastAPI, psycopg 3 with a connection pool. Connection string comes from `DATABASE_URL` in `backend/.env`.
- **Database:** Tiger Data. Raw samples in a hypertable partitioned on `time`; everything else in ordinary tables. Apply `backend/schema.sql` (safe to re-run).
- **Analysis:** pandas/NumPy for features and baseline; PyTorch optional.
- Never make the live game wait on the database or a model API call. Batch raw-sample uploads.

## 8. AI/ML strategy: useful, bounded, and honest

### Layer A — deterministic, shippable v1

Calibrate → extract per-trial features → aggregate valid session summaries → compare against the resident's own baseline. Use medians, robust spread, quality gates, explicit review rules, and a deterministic care-card template. This is the **control** against which any trained model must add value. A rich dashboard with precise reasons and good UX is already a strong technical project.

### Layer B — PyTorch experiment if data supports it

**Do not train a disease classifier.** With a few teammate sessions and no clinical labels, such a classifier would be meaningless. A feasible PyTorch experiment is a small **feature reconstruction autoencoder** trained only on routine/demo sessions, using standardized session-level features such as left/right latency, accuracy, asymmetry, two-hand timing gap, and completion. Suggested architecture for an experiment: `torch.nn.Sequential(Linear(d, 16), ReLU(), Linear(16, 4), ReLU(), Linear(4, 16), ReLU(), Linear(16, d))`. Train using MSE/Huber reconstruction loss on *training-participant* sessions only. A larger reconstruction error suggests “unusual relative to training examples,” **not illness**. Exclude participant-specific leakage from train/test and show a held-out comparison with the rule-based baseline.

**Data gate:** If we have only a handful of sessions, keep PyTorch as a documented experiment and do not present its output as reliable. Pooled volunteer data may demonstrate the code path but cannot establish a clinical threshold; per-person fine-tuning requires much more genuine longitudinal data. If the model has no measurable advantage on held-out clean vs deliberately altered *demo conditions*, ship the rule-based card alone.

**Other defensible model options later:** An interpretable logistic or tree model for *care-team-reviewed change* once real labels and sufficient participants exist; a temporal model (1-D CNN/GRU in PyTorch) for raw axis traces only after enough standardized sessions exist to justify sequence learning. No need for YOLO, pose estimation, or a camera to solve v1. Do not use a pretrained model merely because it sounds impressive.

### Layer C — language assistance for the care team

Optional LLM takes structured, already-computed facts and produces a concise note with the explicit numbers and caveats: “Compared with this resident's last 3 valid sessions, left-hand median latency rose from 0.49 s to 0.82 s; today's session had a stable connection. Please check for fatigue, pain, recent medication changes, or other context.” Require a JSON input containing only allowed features, bounded output, no unsupported diagnosis, and a visible human-review status. Template-based wording is the fallback. Staff notes are human-authored; never hallucinate a caregiver action or chart history.

**Evaluation:** For signal pipeline, compare detected events against manually observed prompts on a few recordings. For ML, report sample count, split by participant/session, baseline rule comparison, false-review prompts in routine demo data, and whether a known *demo-only perturbation* is surfaced. For summaries, check that every number exactly matches the structured source and that no disease name or invented patient fact appears. None of these evaluations establishes clinical safety or effectiveness.

## 9. Data contracts and review workflow

The schema in `backend/schema.sql` implements these contracts. Change the schema and this section together.

**Minimum identifiers:** `participant_id` (UUID; the profile holds only an `alias` nickname/code and `dominant_hand`), `session_id`, `protocol_version`, `controller_id`, `connection`, `placement`, timestamps. Avoid real names and other health information.

**Prompt** (`trials`): `trial_id`, block (`practice`/`left`/`right`/`both`), requested hand(s), requested direction(s), cue-onset time, response deadline. **Raw sample** (`raw_samples`, hypertable): `time`, `session_id`, `seq`, client monotonic `t_ms`, four axis values, `connected` flag. Record which reader produced the samples, since Gamepad API values are −1…1 and HID values are 0–255. **Derived response** (`responses`): outcome (`correct`/`wrong_direction`/`omission`/`false_start`/`invalid`), detected direction(s), threshold-crossing times, latency, code version. **Session summary** (`session_summaries`): metrics with their denominators, enjoyment rating, code version. **Session** (`sessions`): mode (`assessment`/`free_play`), status, quality (`good`/`flagged`/`invalid`), `is_synthetic`. **Review card** (not yet in schema): exact compared values, time span, reason, confidence/quality label, acknowledgement status, caregiver notes, and follow-up outcome.

**Human workflow:** New card → staff reviews underlying sessions and possible context → staff chooses `acknowledged`, `needs assessment`, or `dismissed with reason` → outcome is retained for learning and error analysis. The app never autonomously notifies family, writes a medical record, or issues a diagnosis. A future care-system integration would require permissions, privacy review, clinical validation, and a defined workflow; do not imply that we integrated PointClickCare's EHR during this hackathon.

**Privacy defaults:** Opt-in participant testing; pseudonyms only; no raw camera/audio; role-specific dashboard mock in the demo. **Data now leaves the laptop** because Tiger Data is a cloud service, so profiles must never hold real names or health details. Keep the connection string in `backend/.env` (git-ignored). Do not commit personal data, API secrets, or a resident's information to GitHub. CSV recordings in the repo must come from consenting teammates only.

## 10. Build priorities for the 36-hour hackathon

| Priority | Deliverable | Definition of done | Status |
| --- | --- | --- | --- |
| P0 | Controller + stable data stream | Both sticks map to four live normalized axes; disconnects visible; hardware check passes. | Two readers exist; input path not yet chosen; calibration not built. |
| P0 | Fixed assessment game | Accessible instructions, practice, balanced prompt blocks, response event log, and paused/invalid-state handling. | Landing page done; game not started. |
| P0 | Baseline and trends | Controlled demo baseline, transparent personal comparison, session quality gate, clearly marked simulated longitudinal data. | Schema + synthetic seed done; baseline logic not started. |
| P0 | Care-team view | One clear review card with raw evidence, context, and human acknowledgement. | Not started. |
| P1 | Useful AI | A grounded written summary and/or trained PyTorch anomaly experiment **with** rule-based comparison and stated limits. | Not started. |
| P1 | Evaluation + pitch | Record real gameplay, inspect event timing, show data provenance, include enjoyment comparison if time permits, rehearse four-minute demo. | Not started. |
| P2 | Extra themes, haptics, future integration | Only after P0 works. No camera/YOLO, disease classifier, IMU "tremor" metrics, multi-sensor sprawl, or rushed EHR integration. | — |

**Milestone order:** Controller input + calibration → prompt-to-event timing → raw data persistence → controlled baseline → review card → trained-model experiment → polish. When the controller fails, switch to the same event schema with a prominently labeled simulator and preserve the care-team loop.

**Scope-drift test for agents:** Before adding a feature, ask: (1) Does it improve resident engagement **without corrupting comparability**? (2) Does it improve a **measured change** or its quality? (3) Does it help a **care team** act on a reviewable observation? (4) Can it be shown working during the 36-hour demo? If none apply, defer it. If it makes a disease claim, changes the assessment protocol silently, uses IMU data as a health signal, or targets children as the main PointClickCare story, stop and return to this document.

## 11. Open decisions for the team

- **Which input path scores the assessment?** Browser Gamepad API (simple, one clock with the cue display, ~60 Hz) or Python HID (~500 Hz, needs a WebSocket bridge and clock alignment). Whichever we pick, the other stays as a debugging tool. Decide before building event detection.
- **One Python environment.** Root `pyproject.toml` (uv, Python ≥ 3.14) vs `backend/requirements.txt` (tested on 3.9). Fold the backend dependencies into the uv project or keep them separate on purpose.
- **Tiger Data service:** who creates it and shares the connection string privately? Run `backend/schema.sql` against it and confirm the hypertable is created.
- Is holding the controller comfortable for a person with reduced dexterity, or should it rest on a table? Test placement and allow a participant to decline without interpreting inability to play as a score.
- Do we want a minimal abstract arrow theme, a mature puzzle theme, or both with identical underlying prompts? Ask intended users, not just teammates, when possible.
- Can we recruit any **consenting older adults and care staff** for feedback? Without them, clearly label usability conclusions preliminary.
- Integrate early: run the full landing → game → API → card flow every few hours; do not leave dashboard wiring until the end.

## 12. Evidence and references

These sources inform the direction; none validate *this joystick protocol*.

1. Hack the Valley 11 [PointClickCare: Catch It Early brief and prize categories](https://hack-the-valley-11.devpost.com/) and [event rules and deadlines](https://hack-the-valley-11.devpost.com/rules). The rules say submitted code is created during the hackathon window; this document is planning context, not prebuilt submission code.
2. MDN [Gamepad API](https://developer.mozilla.org/en-US/docs/Web/API/Gamepad_API) and the W3C [standard gamepad mapping](https://w3c.github.io/gamepad/#remapping), used by the browser reader.
3. [Tiger Data documentation](https://docs.tigerdata.com/) for service setup, connection strings and hypertables.
4. [Balance Assessment Using Gamified Digital Technology in Community-Dwelling Older Adults](https://games.jmir.org/2026/1/e80747/): 30 older adults, gamified versus plain digital assessment, higher reported enjoyment and intention to continue; single-session and balance-task findings do **not** prove long-term joystick adherence.
5. [Evaluating the User Experience and Usability of Game-Based Cognitive Assessments for Older People](https://aging.jmir.org/2025/1/e65252/): review of eight studies; accessibility, appropriate difficulty, and user-centered design matter; game elements do not universally improve experience or measurement.
6. [Exergames versus self-regulated exercises during geriatric rehabilitation](https://pubmed.ncbi.nlm.nih.gov/28330455/): a counterexample in which conventional exercises had better adherence, enjoyment, and motivation than the exergame.
7. [Neurological assessment overview](https://www.ncbi.nlm.nih.gov/books/NBK596731/): clinical examinations may include rapid alternating movements, but this joystick task is **inspired by the general idea of comparing movements** and is not an implementation of a validated examination.
8. PyTorch [building models with `torch.nn`](https://docs.pytorch.org/tutorials/beginner/basics/buildmodel_tutorial) for an optional, honestly evaluated ML experiment.

## 13. Decision log

| Date | Decision | Reason / revisit condition |
| --- | --- | --- |
| 2026-10-16 | Lead with older adult and care-team experience for PointClickCare. | Matches the sponsor's stated senior-care workflow. Revisit for a separate pediatric product after the hackathon. |
| 2026-10-16 | ~~Use two existing thumbsticks and Arduino over USB serial.~~ Superseded below. | — |
| 2026-10-16 | Establish a personal controlled baseline and flag **change worth checking**. | Honest with available data; human review is the product outcome. |
| 2026-10-16 | Rules first; PyTorch anomaly prototype only if data and validation permit. | Avoid impressive-sounding but unsupported disease labels. |
| 2026-10-16 | **Use a PS5 DualSense controller instead of Arduino + thumbstick modules.** | No wiring or serial parsing; same four axes; familiar, sturdy device. Revisit if holding it is too hard for target users. |
| 2026-10-16 | **Use Tiger Data (Postgres + TimescaleDB) instead of local SQLite.** | Shared database for the team; hypertable for raw samples. Consequence: data leaves the laptop, so pseudonyms only. |
| 2026-10-16 | Name the fixed assessment protocol `assess-v1`. | Every session stores its protocol version; any change to blocks, timing or thresholds needs a new version and its own baseline. |
| 2026-10-16 | DualSense IMU (gyro/accelerometer) is recorded by the HID tool but excluded from v1 metrics. | Too easy to oversell as tremor detection; not part of the validated-by-us task. |
| 2026-10-17 | Add Garden Rescue (`garden-v1`) as a fixed-course data-collection game for teammate-simulated movement patterns, separate from `assess-v1`. | Position-mapped sticks (not velocity) so reduced range shows up; no random layouts so recordings are comparable. The game only records; a teammate builds the model. Labels are demo tags, never diagnoses. |
| 2026-10-17 | Garden Rescue `garden-v2`: shorter (4 levels, ~60-90 s), easier (bigger tolerances, slower near-round butterfly), friendlier garden visuals and wording, both sticks at once with mirrored targets for apples and watering, butterfly one stick per level; one data folder per level. | v1 felt too hard, too long and like a clinical test. Butterfly stays one-handed because two-stick tracking was the hardest part. v1 and v2 recordings are not comparable. |

**Editing rule:** When changing this document, update §0, the protocol version/assumptions, this decision log, and the demo claims together. Preserve the mission and evidence boundaries unless the team explicitly decides to pivot.
