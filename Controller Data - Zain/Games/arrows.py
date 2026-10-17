"""
sticks.py - Game 4: Two Sticks (independent left/right stick reaction + direction test).

Run:  python sticks.py --player P01 --session 1 [--seed N]

An arrow appears over each stick label (LEFT / RIGHT). The player pushes each stick in the
direction its arrow points, as fast as possible, then lets go of both sticks.
Trial kinds: "both" (two arrows at once, same or different directions), "left" only, "right" only.
4 practice trials (flagged practice=true), then 20 scored trials.

Detection uses thresholds on the RAW stick values (normalised to -1..1, no deadzone):
  onset    : stick deflection >= ONSET_T  (reaction time)
  response : stick deflection >= COMPLETE_T -> direction decided by dominant axis
The full raw trace of BOTH sticks is in the raw CSV (raw_x/raw_y = left, raw_rx/raw_ry = right),
so better onset detection can be redone offline.
"""
import math
import random

import pygame

from logger import Session, W, H, BG

ONSET_T = 0.20        # deflection that counts as "started moving"
COMPLETE_T = 0.70     # deflection that counts as a completed push
CENTER_T = 0.25       # both sticks below this = "let go"
EARLY_T = 0.50        # deflection during the wait = anticipatory move
TIMEOUT = 5.0         # seconds to respond before the cue counts as missed
FEEDBACK_S = 1.0
DELAY_RANGE = (1.0, 2.5)
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
PANEL_X = {"left": 320, "right": 960}
COL = {"left": (90, 160, 255), "right": (255, 170, 60)}
GOOD, WRONG, GREY, DIM, WHITE = (80, 200, 120), (225, 70, 70), (130, 130, 140), (70, 74, 90), (235, 235, 235)


def add_args(p):
    p.add_argument("--seed", type=int, default=None, help="random seed (default random, always logged)")


def norm(rx, ry):
    """Raw 0..255 bytes -> -1..1 (UNfiltered). Used for detection only, never written to the log."""
    if rx is None:
        return 0.0, 0.0
    return (rx - 127.5) / 127.5, (ry - 127.5) / 127.5


def direction_of(dx, dy):
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"      # screen coords: y grows downward


def arrow_points(cx, cy, direction):
    """Polygon for a big arrow centred at (cx, cy) pointing in `direction`."""
    base = [(-90, -28), (0, -28), (0, -70), (95, 0), (0, 70), (0, 28), (-90, 28)]   # points right
    ux, uy = DIRS[direction]
    out = []
    for x, y in base:                          # rotate so +x maps onto (ux, uy)
        out.append((cx + x * ux - y * uy, cy + x * uy + y * ux))
    return out


def make_plans(rng):
    dirs = list(DIRS)

    def pair(same):
        l = rng.choice(dirs)
        return l, (l if same else rng.choice([d for d in dirs if d != l]))

    def spec(kind, l=None, r=None, practice=False):
        return {"kind": kind, "left_dir": l, "right_dir": r,
                "delay": round(rng.uniform(*DELAY_RANGE), 3), "practice": practice}

    practice = [spec("both", *pair(True), True), spec("left", rng.choice(dirs), None, True),
                spec("right", None, rng.choice(dirs), True), spec("both", *pair(False), True)]
    main = ([spec("both", *pair(True)) for _ in range(6)] +
            [spec("both", *pair(False)) for _ in range(6)] +
            [spec("left", d, None) for d in rng.sample(dirs, 4)] +
            [spec("right", None, d) for d in rng.sample(dirs, 4)])
    rng.shuffle(main)
    return practice, main


def main():
    s = Session("sticks", extra_args=add_args)
    a = s.args
    if a.seed is None:
        a.seed = random.randrange(2 ** 31)
    rng = random.Random(a.seed)
    practice_plan, main_plan = make_plans(rng)
    s.meta["params"] = {"seed": a.seed, "onset_thr": ONSET_T, "complete_thr": COMPLETE_T,
                        "center_thr": CENTER_T, "early_thr": EARLY_T, "timeout_s": TIMEOUT,
                        "delay_range_s": DELAY_RANGE, "n_practice": len(practice_plan),
                        "n_trials": len(main_plan)}
    s.meta["practice_plan"] = practice_plan
    s.meta["trial_plan"] = main_plan

    def play(s):
        scr = s.screen

        def say(txt, x, y, font=None, color=WHITE):
            img = (font or s.font).render(txt, True, color)
            scr.blit(img, img.get_rect(center=(int(x), int(y))))

        def draw_panels(vec, directions=None, status=None, title=None, notes=None):
            """directions/status/notes: dicts keyed by 'left'/'right'."""
            scr.fill(BG)
            if title:
                say(title, W / 2, 50, s.big)
            for side in ("left", "right"):
                cx = PANEL_X[side]
                say(side.upper() + " STICK", cx, 130, s.big, COL[side])
                d = (directions or {}).get(side)
                if d:
                    stat = (status or {}).get(side)
                    color = {"correct": GOOD, "wrong": WRONG, "timeout": GREY}.get(stat, COL[side])
                    pygame.draw.polygon(scr, color, arrow_points(cx, 330, d))
                else:
                    pygame.draw.circle(scr, DIM, (cx, 330), 20)
                if notes and notes.get(side):
                    say(notes[side], cx, 460, s.font)
                # live stick indicator (helps first-time users see what the stick is doing)
                pygame.draw.circle(scr, DIM, (cx, 590), 70, 3)
                vx, vy = vec[side]
                m = math.hypot(vx, vy)
                k = 1.0 / m if m > 1 else 1.0
                pygame.draw.circle(scr, COL[side], (int(cx + vx * k * 70), int(590 + vy * k * 70)), 14)

        def vecs(f):
            return {"left": norm(f.raw_x, f.raw_y), "right": norm(f.raw_rx, f.raw_ry)}

        def neutral_wait(k, delay):
            """Wait until both sticks are released, then a random delay with no early movement."""
            centered_since = None
            delay_end = None
            while True:
                f = s.tick()
                v = vecs(f)
                mags = [math.hypot(*v["left"]), math.hypot(*v["right"])]
                if delay_end is None:
                    title = "Let go of both sticks"
                    if max(mags) < CENTER_T:
                        centered_since = f.t if centered_since is None else centered_since
                        if f.t - centered_since >= 0.4:
                            delay_end = f.t + delay
                    else:
                        centered_since = None
                else:
                    title = "Get ready..."
                    if max(mags) >= EARLY_T:            # moved before the cue
                        s.event("early_move", k, left=round(mags[0], 2), right=round(mags[1], 2))
                        delay_end = None
                        centered_since = None
                draw_panels(v, title=title)
                s.present()
                if delay_end is not None and f.t >= delay_end:
                    return

        def run_trial(k, spec):
            s.event("trial_start", k, **spec)
            neutral_wait(k, spec["delay"])
            need = {side: spec[side + "_dir"] for side in ("left", "right") if spec[side + "_dir"]}
            res = {side: {"status": None} for side in need}
            cue_t = None
            crosstalk = False
            while True:
                f = s.tick()
                v = vecs(f)
                if cue_t is None:
                    cue_t = f.t
                    s.event("cue_on", k, left=spec["left_dir"], right=spec["right_dir"])
                for side, target in need.items():
                    r = res[side]
                    if r["status"] is not None:
                        continue
                    dx, dy = v[side]
                    mag = math.hypot(dx, dy)
                    if "onset" not in r and mag >= ONSET_T:
                        r["onset"] = f.t - cue_t
                        s.event("stick_onset", k, stick=side, rt=round(r["onset"], 3))
                    if mag >= COMPLETE_T:
                        r["onset"] = r.get("onset", f.t - cue_t)
                        r["rt_complete"] = f.t - cue_t
                        r["response"] = direction_of(dx, dy)
                        r["status"] = "correct" if r["response"] == target else "wrong"
                        s.event("stick_response", k, stick=side, target=target, response=r["response"],
                                correct=r["status"] == "correct", rt_onset=round(r["onset"], 3),
                                rt_complete=round(r["rt_complete"], 3),
                                movement_time=round(r["rt_complete"] - r["onset"], 3))
                    elif f.t - cue_t >= TIMEOUT:
                        r["status"] = "timeout"
                        s.event("stick_timeout", k, stick=side, target=target)
                if spec["kind"] != "both" and not crosstalk:     # other stick should stay still
                    other = "right" if spec["kind"] == "left" else "left"
                    if math.hypot(*v[other]) >= EARLY_T:
                        crosstalk = True
                        s.event("non_target_stick_move", k, stick=other)
                status = {sd: r["status"] for sd, r in res.items()}
                draw_panels(v, {"left": spec["left_dir"], "right": spec["right_dir"]}, status,
                            title="Push the sticks!")
                s.present()
                if all(r["status"] is not None for r in res.values()):
                    break

            # brief feedback (frames still logged)
            notes = {sd: {"correct": "Good!", "wrong": "Wrong way", "timeout": "Too slow"}[r["status"]]
                     for sd, r in res.items()}
            fb_end = None
            while True:
                f = s.tick()
                fb_end = f.t + FEEDBACK_S if fb_end is None else fb_end
                draw_panels(vecs(f), {"left": spec["left_dir"], "right": spec["right_dir"]}, status,
                            title="Push the sticks!", notes=notes)
                s.present()
                if f.t >= fb_end:
                    break

            lag = None
            if len(res) == 2 and all("onset" in r for r in res.values()):
                lag = round(abs(res["left"]["onset"] - res["right"]["onset"]), 3)
            s.event("trial_end", k, kind=spec["kind"], practice=spec["practice"], status=status,
                    onset_lag=lag)
            return res

        s.begin("Two Sticks",
                ["An arrow will appear above each stick.",
                 "Push the LEFT stick the way the left arrow points,",
                 "and the RIGHT stick the way the right arrow points.",
                 "Go as fast as you can, then let go of both sticks.",
                 "Sometimes only one arrow will show."])

        k = 0
        s.event("phase_change", "", to="practice")
        for spec in practice_plan:
            k += 1
            run_trial(k, spec)
        s.event("phase_change", "", to="test")
        s.hold(["Practice finished", "Now the real test", "Press A when ready"], until_button=True)

        results = []
        for spec in main_plan:
            k += 1
            results.append(run_trial(k, spec))

        lines = ["Finished - thank you!"]
        for side in ("left", "right"):
            rs = [r[side] for r in results if side in r]
            ok = [r for r in rs if r["status"] == "correct"]
            mean = sum(r["onset"] for r in ok) / len(ok) if ok else float("nan")
            lines.append(f"{side.capitalize()} stick: {len(ok)}/{len(rs)} correct, "
                         f"average reaction {mean:.2f} s")
        s.hold(lines + ["", "Press A to exit"], until_button=True)

    s.run(play)


if __name__ == "__main__":
    main()