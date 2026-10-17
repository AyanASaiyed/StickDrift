# Stick Drift — project context and scope guardrails

> Living document for the Hack the Valley 11 team and any coding or research agents helping us. Last updated: 2026-10-16 (America/Toronto). Change decisions in the log at the bottom rather than silently changing the mission.

## 1. The project in one paragraph

Stick Drift is a **short, enjoyable, two-hand joystick activity** that can be repeated in a senior-living or long-term-care setting. A resident sees clear directional prompts, moves one or both thumbsticks, and gets immediate, respectful game feedback. An Arduino streams four analog axes to a laptop. The software measures how the resident responds, establishes an **individual baseline**, and surfaces meaningful changes—such as slower responses, more missed prompts, or a new left/right difference—to a **care-team dashboard** with the supporting data. Its promised output is **“a change worth checking,”** never a diagnosis, predicted disease, or emergency determination. A nurse or caregiver supplies the interpretation and decides what to do next.

## 2. Mission, user, and why it matters

**Mission:** Make a brief movement and attention check pleasant enough to repeat, and make changes visible early enough for a care team to follow up. We are testing whether an accessible game can collect useful, consistent observations without feeling like yet another clinical test.

**Primary user:** Older adult living in a senior-care setting. **Primary customer/workflow user:** Care team member (nurse, CNA, wellness director, therapist). **Secondary stakeholders:** Family and clinicians, if the care facility chooses to share information. **Possible future audience:** Children in pediatric rehabilitation; this is *not* the lead story for the PointClickCare sponsor challenge.

**The gap:** Staff have limited time to notice subtle changes between formal assessments. A one-off reaction score means little; a repeated, standardized activity may reveal a change relative to the resident's own pattern. Game design may help participation, but engagement is a hypothesis we should test, not a fact to assume.

**Value loop:** Resident plays → calibrated movement events are recorded → features are compared against a personal baseline → an explainable, appropriately cautious review prompt reaches the care team → a human records context and follows up.

**Why the physical interface matters:** A pair of inexpensive, identical controls gives standardized left- and right-hand input and a tangible live demo. We can record continuous joystick position, not just keypresses. The joystick is a prototype interaction device, **not a clinically validated neurologic instrument**. It cannot directly measure grip strength, applied pressure, true hand tremor, posture, or a specific illness.

## 3. Track fit and judging story

| Prize / track | Fit | What the demo must prove |
| --- | --- | --- |
| **PointClickCare: Catch It Early** | **Primary**. Its brief explicitly asks for an AI-powered solution that helps a nursing-home/senior-living **care team** notice a health risk before an emergency. Our narrower use case is a new change in hand movement or response pattern worth follow-up. | A caregiver receives a useful, evidence-linked review card, sees how today's measurements differ from the resident's own history, records an observation, and can dismiss or escalate the prompt. A game alone does not satisfy this track. |
| **Best Healthcare & Well-being Hack** | Strong secondary fit: accessible resident experience plus measurable caregiver workflow. | A working physical interface, a usable resident experience, trustworthy measurement and honest limits. |
| **Best AI for Social Impact Hack** | Possible if the AI adds a defensible capability to early review or usable summaries. | Compare the AI layer with a simple baseline, show actual measured numbers and failure handling; avoid a decorative chatbot. |
| **Best Use of Gemini API** | Optional only if we actually use Gemini meaningfully, such as a grounded narrative summary from structured measurements and care notes. | Demonstrate a faithful explanation with source values, and a deterministic fallback when the API is unavailable. Do not switch models just to claim a sponsor prize. |

Hack the Valley's judging also emphasizes technical quality, design, impact, presentation, inspiration, and authenticity. A polished, honest end-to-end story beats an unsupported disease classifier. The School of Cities challenge requires a Toronto civic problem grounded in urban data; **this product does not naturally fit that track**. Do not force that claim.

**Four-minute demo arc:** (1) Show a resident playing 30–60 seconds on two sticks. (2) Show raw axes and prompt events updating live. (3) Open a clearly labeled *simulated* later session with a repeatable change. (4) Show the care-team card: “Left-hand response median 0.82 s vs personal baseline 0.49 s; 4/12 incorrect vs 0–1/12 usual. Please check in.” (5) Record a caregiver note and show that the card says **review**, not “Parkinson's detected.” The numbers here are illustrative, not clinical cutoffs.

## 4. Non-negotiable product boundaries

1. The product is an **observation and review tool**, not a diagnostic, treatment, or emergency-response device. No model output names stroke, Parkinson's, MS, dementia, or another disease from joystick performance.
2. A change may be caused by fatigue, sleep, medications, vision, instructions, unfamiliarity with games, device placement, or a faulty joystick. The interface shows context and confidence/quality rather than hiding uncertainty.
3. Preserve comparable **assessment rounds**: same prompt rules, input interpretation, order policy, trial counts, timing, and calibrated equipment for baseline and follow-ups. Optional themes, celebration, and a separate challenge mode can vary without changing the measured task. Do not automatically increase assessment speed and then compare raw scores.
4. Do not use childlike visuals or a competitive leaderboard for the older-adult pitch. Make the experience age-respectful: large arrows, high contrast, adjustable sound, clear instructions, no penalty or shame for missing a prompt, an easy pause and opt-out.
5. No hidden camera or biometric collection is required. Start with joystick data only. Use synthetic, clearly labeled data for any multi-day change we cannot actually observe during the hackathon.
6. A sudden new neurological symptom in real life warrants ordinary urgent clinical procedures; no one should wait for the game or an AI score.

## 5. Game and measurement protocol

### Resident flow

1. Care staff selects a pseudonymous resident profile; the resident agrees to play. Seat the person comfortably and put sticks at consistent positions, marked **LEFT** and **RIGHT**. Record dominant hand, but do not assume it performs identically to the other hand.
2. Calibrate each stick while untouched; ask for one gentle movement to each direction. Show an obvious hardware-check screen before starting.
3. Provide 4–8 unscored practice prompts, then a short pause. No performance history is created from practice.
4. **Fixed assessment mode:** three blocks of 12 prompts each: left-hand-only, right-hand-only, and both-hands. In the first two blocks, balance up/down/left/right; in the third, use a predefined balanced set of same-direction and opposite-direction pairs. Counterbalance the order of left and right blocks across sessions (or keep a fixed order and record it); never silently change the protocol. Each trial has a visible cue, a fixed response window (for example 2 seconds), and a neutral recenter period. ~2–4 minutes total including instructions and breaks. If the resident needs a shorter mode, define a separate protocol version and build its own baseline.
5. Optional free-play mode may add speed, stories, or personal high scores; it must be labeled **not used for health trends** unless separately validated.
6. At the end: resident sees a neutral, positive completion screen; staff sees data-quality status and, when sufficient history exists, the trend card.

### Trial timing and classification (engineering proposal; tune empirically)

- Sample all four axes at a nominal **50 Hz** and transmit `sequence`, `microcontroller_time_ms`, `LX`, `LY`, `RX`, `RY` over serial. Log dropped or malformed packets.
- Normalize each axis relative to its own measured center and travel in each direction. Mark a directional response when the intended axis exceeds a calibrated threshold, initially around **40% of that stick's observed range**, for at least **2–3 samples**. Require return to a neutral zone, perhaps 20%, before accepting the next response; the split thresholds create hysteresis. Validate with actual modules and user comfort.
- A trial starts when the cue is visibly presented, not when the random prompt is chosen. Log a monotonic host timestamp and align the microcontroller clock using repeated timestamp exchanges or host receive timestamps; report timing uncertainty in the demo. USB/serial, display refresh, and OS scheduling add latency, so do not claim millisecond clinical precision.
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
| Neutral instability | Variation in joystick readings when untouched and during recentering. | First treat as device jitter/noise; **do not market as tremor detection**. |
| Participation / usability | Completion rate, skipped sessions, retries, voluntary replay, simple enjoyment question (1–5), and opt-outs. | Product evidence; do not conflate intention to replay with actual longitudinal adherence. |

**Primary dashboard metrics for v1:** median response latency for each hand, first-response accuracy for each hand, matched-direction left/right gap, two-hand timing gap, participation, and data quality. Everything else is exploratory.

## 6. Establishing a controlled personal baseline

**A baseline is the person's own stable reference under a fixed protocol, not a population-wide “healthy” score.**

1. **Hardware/calibration baseline:** With both sticks untouched, gather 1–2 seconds of readings per axis for centers and neutral jitter. Move each axis slowly in both directions to find comfortable, observed ranges; store module-specific calibration. Recheck each session. If the center or range shifts substantially, re-calibrate and mark the session as potentially noncomparable.
2. **Practice effect:** Run unscored practice first. If the person is still learning the controls, record “baseline pending.” Avoid treating the first game ever as a stable reference.
3. **Controlled sessions:** As a proposed starting protocol, collect at least **3 separate sessions over 2–3 different days**, with the same block definitions, prompt windows, display, seat/placement, and assistance policy. These numbers are design choices to be tested, **not published clinical thresholds**. Record time of day, dominant hand, assistive needs, interruptions, tiredness/pain or other context if voluntarily supplied. Repeat the exact protocol on follow-up days.
4. **Quality gates:** Reject or flag a session with disconnects, high serial packet loss, bad neutral calibration, too many unreadable trials, changed hardware, or interrupted instructions. Do not interpret missed sessions as declining health.
5. **Compute reference:** For each feature, take the median of session summaries as center; compute a robust spread (for example `1.4826 × median(|x - median(x)|)`), with a floor informed by instrument noise to avoid dividing by zero. Retain the actual session range and count. Separate baseline by protocol version; store device ID, calibration, and assistance status.
6. **Review logic:** Compare later sessions to the personal reference; show raw values, absolute change, baseline range, and context. A prototype rule might request review when **two distinct reliable metrics move materially in the same direction**, or when a large within-person change repeats on the next valid session. Exact cutoffs require validation and false-alert measurement; do not represent illustrative thresholds as medical cutoffs. Allow a human to review a sudden large shift immediately even if there is no second session.
7. **Updating:** Do not automatically absorb flagged values into the baseline. After caregiver review, a clinician-approved or explicitly documented reset may establish a new reference; retain the earlier history.

**Hackathon reality:** We cannot gather a real multi-day resident baseline during 36 hours. We can demonstrate a short **engineering baseline** from three standardized rounds with consenting adult teammates, explicitly labeled nonclinical, and use a **clearly labeled synthetic multi-day timeline** to show the intended dashboard. Never present fabricated patient measurements as collected evidence.

**More meaningful controlled comparison for the demo:** Have a few consenting teammates complete the identical task under two conditions—normal and, for example, a deliberate alternate-hand or distracted **demo condition**. Show that the signal pipeline reflects the condition, while acknowledging that this does not simulate disease and is not clinical validation. If testing enjoyment, compare a plain prompt screen with the gamified one on the same fixed motor protocol; record participant preference and completion, while controlling for order.

## 7. Hardware: confirmed inventory and proposed wiring

**Confirmed from our conversation:** one Arduino board (exact model unknown), two analog thumbstick joystick modules (exact model and voltage rating unknown), and a laptop for the game/dashboard. **Needed or to confirm:** a USB data cable matching the board, 10–12 jumper wires (or a breadboard and jumpers), a way to mount the sticks securely (cardboard/foam board/box/tape), and power from laptop USB. No camera, Bluetooth, ESP32, pressure sensor, accelerometer, or NFC reader is needed for v1. We have **not verified the live MLH hardware inventory** for these items; do not list a loaner as confirmed.

### Conditional pin map for an Arduino Uno R3 + common `GND / VCC / VRx / VRy / SW` modules

| Joystick pin | Arduino pin | Purpose |
| --- | --- | --- |
| Left GND, Right GND | GND (common ground) | Both modules share board ground. |
| Left VCC, Right VCC | 5V **only if both modules and the board are rated for 5V** | Uno R3 example; verify the printed board/module labels before powering. |
| Left VRx | A0 | Left horizontal analog position. |
| Left VRy | A1 | Left vertical analog position. |
| Right VRx | A2 | Right horizontal analog position. |
| Right VRy | A3 | Right vertical analog position. |
| Left SW / Right SW | D2 / D3, optional | Center push buttons; if wired, use `INPUT_PULLUP` on common active-low modules and verify actual behavior. |
| Arduino USB | Laptop USB data port | Power, upload, and serial stream. No wireless relay is necessary. |

**Before connecting:** Read the model printed on the Arduino, identify 5V vs 3.3V logic and the joystick pin labels, and confirm your USB cable carries data. Do not apply 5V analog output to a 3.3V-only board. The Uno R3 has six analog inputs and reads A0–A5 at default 10-bit resolution, so four axes fit; other Arduino variants differ. If X/Y appears inverted after wiring, fix orientation in a stored calibration map, not by guessing across sessions.

**Bring-up checklist:**

1. Mount both modules with enough distance for relaxed hand placement; mark left/right and forward direction. Strain-relieve the wires.
2. Connect *one* module first, flash a tiny sketch reading A0/A1, and observe its center and four excursions in Arduino Serial Monitor.
3. Attach the second module to A2/A3; verify each stick independently and at the same time. Check all power/ground connections while USB is disconnected.
4. Stream a single machine-readable line, such as `v1,seq,mcu_ms,lx,ly,rx,ry`, at 50 Hz with `Serial.begin(115200)`. If sampling or printing cannot maintain the rate, lower it and record the actual achieved rate. The Arduino does not run PyTorch; it only samples and sends data.
5. In Python, use `pyserial` to select the port, discard incomplete lines, detect sequence gaps, save raw samples, and update the game via WebSocket or a local process. Close Arduino Serial Monitor before the app opens the same port.
6. Run per-axis center/range checks. Pause game scoring if serial disconnects or calibration fails. A plain keyboard simulator using the same event schema is the emergency demo fallback; it must be visibly identified as simulated input.

**Likely software shape:** Arduino sketch → USB serial → Python ingest/event engine (`pyserial`, `numpy`, `pandas`) → local SQLite → FastAPI/WebSocket → React/TypeScript or a simple browser game and care dashboard. PyTorch is optional in the Python analysis service. Keep raw samples and prompt events in separate SQLite tables; never force the live UI to wait for a model API call.

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

**Minimum identifiers:** `participant_id` (pseudonym), `session_id`, `protocol_version`, `device_id`, `calibration_id`, timestamps. Avoid real names and other health information in the hackathon demo.

**Prompt:** `trial_id`, block type, requested hand(s), requested direction(s), cue-onset monotonic time, response deadline. **Raw sample:** sample sequence, Arduino uptime, host receipt monotonic time, four raw ADC values, packet-quality flag. **Derived response:** validity, detected direction(s), threshold-crossing times, latency, wrong direction, omission, correction, and code version. **Session summary:** metrics with denominators, quality gates, reference version, and optional self-report context. **Review card:** exact compared values, time span, reason, confidence/quality label, acknowledgement status, caregiver notes, and follow-up outcome.

**Human workflow:** New card → staff reviews underlying sessions and possible context → staff chooses `acknowledged`, `needs assessment`, or `dismissed with reason` → outcome is retained for learning and error analysis. The app never autonomously notifies family, writes a medical record, or issues a diagnosis. A future care-system integration would require permissions, privacy review, clinical validation, and a defined workflow; do not imply that we integrated PointClickCare's EHR during this hackathon.

**Privacy defaults:** Opt-in participant testing; pseudonyms; local storage by default; no raw camera/audio; role-specific dashboard mock in the demo; do not commit personal data, API secrets, or a resident's information to GitHub.

## 10. Build priorities for the 36-hour hackathon

| Priority | Deliverable | Definition of done |
| --- | --- | --- |
| P0 | Hardware + stable data stream | Two thumbsticks map to four live normalized axes; reconnect/errors visible; simple hardware test passes. |
| P0 | Fixed assessment game | Accessible instructions, practice, balanced prompt blocks, response event log, and paused/invalid-state handling. |
| P0 | Baseline and trends | Controlled demo baseline, transparent personal comparison, session quality gate, clearly marked simulated longitudinal data. |
| P0 | Care-team view | One clear review card with raw evidence, context, and human acknowledgement. |
| P1 | Useful AI | A grounded written summary and/or trained PyTorch anomaly experiment **with** rule-based comparison and stated limits. |
| P1 | Evaluation + pitch | Record real gameplay, inspect event timing, show data provenance, include enjoyment comparison if time permits, rehearse four-minute demo. |
| P2 | Extra themes, hardware enclosure polish, future integration | Only after P0 works. No camera/YOLO, disease classifier, multi-sensor sprawl, or rushed EHR integration. |

**Milestone order:** Hardware streaming → prompt-to-event timing → raw data persistence → controlled baseline → review card → trained-model experiment → polish. When hardware fails, switch to the same event schema with a prominently labeled simulator and preserve the care-team loop.

**Scope-drift test for agents:** Before adding a feature, ask: (1) Does it improve resident engagement **without corrupting comparability**? (2) Does it improve a **measured change** or its quality? (3) Does it help a **care team** act on a reviewable observation? (4) Can it be shown working during the 36-hour demo? If none apply, defer it. If it makes a disease claim, changes the assessment protocol silently, or targets children as the main PointClickCare story, stop and return to this document.

## 11. Open decisions for the team

- What **exact Arduino model** and exact joystick module labels/voltage do we have? Photograph or transcribe them before finalizing VCC and pinout.
- Which computer/OS and available USB cable? This determines serial-port setup and whether a browser app can use the Web Serial API or Python should own serial.
- Is the tabletop controller comfortable for a person with reduced dexterity? We should test placement and allow a participant to decline without interpreting inability to play as a score.
- Do we want a minimal abstract arrow theme, a mature puzzle theme, or both with identical underlying prompts? Ask intended users, not just teammates, when possible.
- Can we recruit any **consenting older adults and care staff** for feedback? Without them, clearly label usability conclusions preliminary.
- Who owns hardware/game, analytics, care-team workflow, and demo integration? Integrate early; do not leave dashboard wiring until the end.

## 12. Evidence and references

These sources inform the direction; none validate *this joystick protocol*.

1. Hack the Valley 11 [PointClickCare: Catch It Early brief and prize categories](https://hack-the-valley-11.devpost.com/) and [event rules and deadlines](https://hack-the-valley-11.devpost.com/rules). The rules say submitted code is created during the hackathon window; this document is planning context, not prebuilt submission code.
2. Arduino [Uno R3 specifications](https://docs.arduino.cc/hardware/uno-rev3) and [analogRead reference](https://github.com/arduino/reference-en/blob/master/Language/Functions/Analog%20IO/analogRead.adoc). Conditional wiring above assumes an Uno R3 and common analog thumbsticks, pending physical inspection.
3. [Balance Assessment Using Gamified Digital Technology in Community-Dwelling Older Adults](https://games.jmir.org/2026/1/e80747/): 30 older adults, gamified versus plain digital assessment, higher reported enjoyment and intention to continue; single-session and balance-task findings do **not** prove long-term joystick adherence.
4. [Evaluating the User Experience and Usability of Game-Based Cognitive Assessments for Older People](https://aging.jmir.org/2025/1/e65252/): review of eight studies; accessibility, appropriate difficulty, and user-centered design matter; game elements do not universally improve experience or measurement.
5. [Exergames versus self-regulated exercises during geriatric rehabilitation](https://pubmed.ncbi.nlm.nih.gov/28330455/): a counterexample in which conventional exercises had better adherence, enjoyment, and motivation than the exergame.
6. [Neurological assessment overview](https://www.ncbi.nlm.nih.gov/books/NBK596731/): clinical examinations may include rapid alternating movements, but this joystick task is **inspired by the general idea of comparing movements** and is not an implementation of a validated examination.
7. PyTorch [building models with `torch.nn`](https://docs.pytorch.org/tutorials/beginner/basics/buildmodel_tutorial) for an optional, honestly evaluated ML experiment.

## 13. Decision log

| Date | Decision | Reason / revisit condition |
| --- | --- | --- |
| 2026-10-16 | Lead with older adult and care-team experience for PointClickCare. | Matches the sponsor's stated senior-care workflow. Revisit for a separate pediatric product after the hackathon. |
| 2026-10-16 | Use two existing thumbsticks and Arduino over USB serial. | Hardware already owned; measurable live interaction with no wireless dependency. Verify exact models. |
| 2026-10-16 | Establish a personal controlled baseline and flag **change worth checking**. | Honest with available data; human review is the product outcome. |
| 2026-10-16 | Rules first; PyTorch anomaly prototype only if data and validation permit. | Avoid impressive-sounding but unsupported disease labels. |

**Editing rule:** When changing this document, update the protocol version/assumptions, this decision log, and the demo claims together. Preserve the mission and evidence boundaries unless the team explicitly decides to pivot.