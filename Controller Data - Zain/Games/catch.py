"""
catch.py - Game 2: steer to a target and press A while inside it.

Run:  python catch.py --player P01 --session 1 [--kids] [--seed 42]
30 trials, then a 10 s button-mash round.
--kids : 25% of targets are red decoys that must NOT be pressed.
"""
import math
import random

import pygame

from logger import Session, W, H, DT, BG

SPEED = 420.0                                   # px/s at full stick
CHAR_R = 12
N_TRIALS = 30
DISTS = {"near": 150, "mid": 350, "far": 560}   # nominal spawn distance (px), +-10%
RADII = {"small": 20, "large": 42}              # target radius (px)
ITI = (0.8, 2.0)                                # blank inter-trial delay range (s)
DECOY_FRAC = 0.25
DECOY_WINDOW = 2.0                              # s a decoy stays before "correct_reject"
MASH_SECS = 10.0
TARGET_COL, DECOY_COL, CHAR_COL = (255, 215, 70), (225, 60, 60), (235, 235, 235)


def add_args(p):
    p.add_argument("--kids", action="store_true", help="25%% red decoy targets")
    p.add_argument("--seed", type=int, default=None, help="random seed (default random, always logged)")


def spawn_position(rng, px, py, dist_bin, radius):
    """Random point ~DISTS[dist_bin] from the player that fits on screen."""
    margin = radius + 20
    for attempt in range(200):
        d = DISTS[dist_bin] * rng.uniform(0.9, 1.1) * (0.97 ** (attempt // 20))  # shrink if it won't fit
        a = rng.uniform(0, 2 * math.pi)
        x, y = px + d * math.cos(a), py + d * math.sin(a)
        if margin <= x <= W - margin and margin <= y <= H - margin:
            return x, y
    return min(max(x, margin), W - margin), min(max(y, margin), H - margin)  # last resort: clamp


def main():
    s = Session("catch", extra_args=add_args)
    a = s.args
    if a.seed is None:
        a.seed = random.randrange(2 ** 31)
    rng = random.Random(a.seed)

    # Pre-plan the session: balanced distance x size combos, shuffled; delays; decoy flags
    combos = [(b, z) for b in DISTS for z in RADII] * (N_TRIALS // (len(DISTS) * len(RADII)))
    rng.shuffle(combos)
    decoys = [False] * N_TRIALS
    if a.kids:
        n_dec = round(DECOY_FRAC * N_TRIALS)
        decoys = [True] * n_dec + [False] * (N_TRIALS - n_dec)
        rng.shuffle(decoys)
    plan = [{"trial": i + 1, "dist_bin": b, "size": z, "decoy": dc,
             "delay": round(rng.uniform(*ITI), 3)}
            for i, ((b, z), dc) in enumerate(zip(combos, decoys))]
    s.meta["params"] = {"seed": a.seed, "kids_mode": a.kids, "speed_px_s": SPEED, "char_radius": CHAR_R,
                        "n_trials": N_TRIALS, "distances_px": DISTS, "radii_px": RADII,
                        "iti_range_s": ITI, "decoy_window_s": DECOY_WINDOW, "mash_seconds": MASH_SECS}
    s.meta["trial_plan"] = plan

    def play(s):
        pos = [W / 2.0, H / 2.0]
        hits = misses = commissions = rejects = 0
        collect_times = []

        def move(f):
            pos[0] = min(max(pos[0] + f.mx * SPEED * DT, CHAR_R), W - CHAR_R)
            pos[1] = min(max(pos[1] + f.my * SPEED * DT, CHAR_R), H - CHAR_R)

        def draw_char():
            pygame.draw.circle(s.screen, CHAR_COL, (int(pos[0]), int(pos[1])), CHAR_R)

        intro = ["Move onto the target and press A", "Be quick and accurate"]
        if a.kids:
            intro.append("RED targets: do NOT press!")
        s.begin("Catch", intro)

        for spec in plan:
            k = spec["trial"]
            r = RADII[spec["size"]]
            decoy = spec["decoy"]
            s.event("trial_start", k, delay=spec["delay"], dist_bin=spec["dist_bin"],
                    size=spec["size"], decoy=decoy)

            # --- blank inter-trial delay (no target; character still visible and movable)
            delay_end = None
            while True:
                f = s.tick()
                if delay_end is None:
                    delay_end = f.t + spec["delay"]
                move(f)
                if f.pressed:   # anticipatory press
                    s.event("button_press", k, phase="delay", target_visible=False,
                            char_x=round(pos[0], 1), char_y=round(pos[1], 1))
                s.screen.fill(BG)
                draw_char()
                s.present(pos)
                if f.t >= delay_end:
                    break

            # --- target on screen
            tx, ty = spawn_position(rng, pos[0], pos[1], spec["dist_bin"], r)
            spawn_t = None
            while True:
                f = s.tick()
                move(f)
                s.screen.fill(BG)
                pygame.draw.circle(s.screen, DECOY_COL if decoy else TARGET_COL, (int(tx), int(ty)), r)
                draw_char()
                if spawn_t is None:     # first frame the target is drawn
                    spawn_t = f.t
                    s.event("target_spawn", k, x=round(tx, 1), y=round(ty, 1), radius=r,
                            size=spec["size"], dist_bin=spec["dist_bin"], decoy=decoy,
                            player_x=round(pos[0], 1), player_y=round(pos[1], 1),
                            dist_from_player=round(math.dist(pos, (tx, ty)), 1))
                finished = False
                if f.pressed:
                    d = math.dist(pos, (tx, ty))
                    hit = d <= r
                    s.event("button_press", k, phase="target", dist=round(d, 1), inside=hit,
                            decoy=decoy, char_x=round(pos[0], 1), char_y=round(pos[1], 1))
                    if hit and decoy:
                        commissions += 1
                        s.event("commission_error", k, dist=round(d, 1), rt=round(f.t - spawn_t, 3))
                        finished = True
                    elif hit:
                        hits += 1
                        collect_times.append(f.t - spawn_t)
                        s.event("collect", k, time_to_collect=round(f.t - spawn_t, 3), dist=round(d, 1))
                        finished = True
                    else:
                        misses += 0 if decoy else 1   # hit rate counts real targets only
                        s.event("miss", k, dist=round(d, 1), decoy=decoy)  # target stays
                elif decoy and f.t - spawn_t >= DECOY_WINDOW:
                    rejects += 1
                    s.event("correct_reject", k, window=DECOY_WINDOW)
                    finished = True
                s.present(pos)
                if finished:
                    break

        # --- button-mash round (character frozen, still logged)
        s.event("phase_change", "", to="mash_ready")
        s.hold(["Button mash!", "Press A as fast as you can for 10 seconds", "Starting in 3..."],
               seconds=3, char=pos)
        s.event("phase_change", "", to="mash")
        presses = 0
        t_begin = None
        while True:
            f = s.tick()
            if t_begin is None:
                t_begin = f.t
            if f.pressed:
                presses += 1
                s.event("button_press", "", phase="mash", n=presses, since_start=round(f.t - t_begin, 4))
            s.screen.fill(BG)
            s.text(["GO!", f"Presses: {presses}", f"Time left: {max(0.0, MASH_SECS - (f.t - t_begin)):.1f}"])
            s.present(pos)
            if f.t - t_begin >= MASH_SECS:
                break

        mean_t = sum(collect_times) / len(collect_times) if collect_times else float("nan")
        attempts = hits + misses
        lines = ["Done!", f"Mean time to collect: {mean_t:.2f} s",
                 f"Hit rate: {100 * hits / attempts:.0f}%  ({hits} hits, {misses} misses)" if attempts
                 else "Hit rate: n/a",
                 f"Button mash: {presses} presses in {MASH_SECS:.0f} s"]
        if a.kids:
            lines.append(f"Decoys: {commissions} wrong presses, {rejects} correct rejects")
        lines += ["", "Press A to exit"]
        s.hold(lines, until_button=True, char=pos)

    s.run(play)


if __name__ == "__main__":
    main()
