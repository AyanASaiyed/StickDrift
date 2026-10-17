"""
memory.py - Game 3 (replaces maze.py): "Remember the Order" - a block-tapping spatial memory test.

Run:  python memory.py --player P01 --session 1 [--seed N]

Nine big blocks sit on screen. Some of them light up one after another. The player then
moves a cursor with the left stick and presses A on the same blocks in the same order.
Sequence length starts at 2 and grows by one every two trials (max 7); the test stops when
both trials at a length are failed. No walls, no fog, no time pressure, no penalties.
A practice trial comes first (flagged practice=true in the logs, not scored).
"""
import math
import random

import pygame

from logger import Session, W, H, DT, BG

SPEED = 300.0                    # cursor speed px/s (slow and forgiving)
CURSOR_R = 16
BLOCK_R = 56                     # block radius = press radius (big and forgiving)
SHOW_ON, SHOW_OFF = 1.0, 0.5     # seconds each block is lit / dark between blocks
MIN_LEN, MAX_LEN, TRIALS_PER_LEN = 2, 7, 2
CENTER = (W / 2.0, H / 2.0)
# Fixed, irregular layout; none near the screen centre (cursor start). Block ids = list index.
BLOCKS = [(180, 160), (470, 120), (780, 170), (1100, 140), (260, 430),
          (560, 560), (900, 470), (1150, 540), (1000, 300)]
IDLE, LIT, OK, BAD = (80, 88, 110), (255, 215, 70), (80, 200, 120), (225, 70, 70)


def add_args(p):
    p.add_argument("--seed", type=int, default=None, help="random seed (default random, always logged)")


def main():
    s = Session("memory", extra_args=add_args)
    a = s.args
    if a.seed is None:
        a.seed = random.randrange(2 ** 31)
    rng = random.Random(a.seed)
    s.meta["params"] = {"seed": a.seed, "cursor_speed_px_s": SPEED, "block_radius": BLOCK_R,
                        "show_on_s": SHOW_ON, "show_off_s": SHOW_OFF, "min_len": MIN_LEN,
                        "max_len": MAX_LEN, "trials_per_len": TRIALS_PER_LEN}
    s.meta["block_positions"] = BLOCKS

    def play(s):
        cur = list(CENTER)

        def draw(colors, cursor=True, title=None):
            s.screen.fill(BG)
            for i, (bx, by) in enumerate(BLOCKS):
                pygame.draw.circle(s.screen, colors.get(i, IDLE), (bx, by), BLOCK_R)
            if cursor:
                pygame.draw.circle(s.screen, (255, 255, 255), (int(cur[0]), int(cur[1])), CURSOR_R, 4)
                pygame.draw.circle(s.screen, (255, 255, 255), (int(cur[0]), int(cur[1])), 3)
            if title:
                s.text([title], y=15, big_first=True)

        def wait(seconds, colors, title, cursor=False):
            """Idle frames (still logged). Cursor frozen."""
            s.hold([title], seconds=seconds, char=tuple(cur) if cursor else None,
                   draw=lambda f: draw(colors, cursor), y=15)

        def run_trial(k, length, practice):
            seq = rng.sample(range(len(BLOCKS)), length)
            s.event("trial_start", k, length=length, sequence=seq, practice=practice)

            # ---- WATCH: blocks light up one by one (cursor hidden)
            wait(1.2, {}, "Watch the blocks...")
            for n, b in enumerate(seq):
                s.event("block_show", k, index=n, block=b)
                wait(SHOW_ON, {b: LIT}, "Watch the blocks...")
                wait(SHOW_OFF, {}, "Watch the blocks...")

            # ---- RECALL: move cursor (left stick), press A on the blocks in the same order
            cur[0], cur[1] = CENTER
            s.event("recall_start", k, length=length)
            done = []                 # blocks correctly pressed so far
            t_prev = None
            success = None
            while success is None:
                f = s.tick()
                if t_prev is None:
                    t_prev = f.t
                cur[0] = min(max(cur[0] + f.mx * SPEED * DT, CURSOR_R), W - CURSOR_R)
                cur[1] = min(max(cur[1] + f.my * SPEED * DT, CURSOR_R), H - CURSOR_R)
                colors = {b: OK for b in done}
                if f.pressed:
                    hit = next((i for i, (bx, by) in enumerate(BLOCKS)
                                if math.dist(cur, (bx, by)) <= BLOCK_R), None)
                    if hit is None:                               # empty space: ignored, no penalty
                        s.event("press_empty", k, x=round(cur[0], 1), y=round(cur[1], 1))
                    elif done and hit == done[-1]:                # accidental double press: ignored
                        s.event("repeat_press", k, block=hit)
                    else:
                        expected = seq[len(done)]
                        ok = hit == expected
                        bx, by = BLOCKS[hit]
                        s.event("block_press", k, index=len(done), block=hit, expected=expected,
                                correct=ok, rt=round(f.t - t_prev, 3),
                                dist_to_center=round(math.dist(cur, (bx, by)), 1))
                        t_prev = f.t
                        if ok:
                            done.append(hit)
                            colors[hit] = OK
                            if len(done) == length:
                                success = True
                        else:
                            colors[hit] = BAD
                            success = False
                draw(colors, True, "Your turn! Same order, press A")
                s.present(tuple(cur))
            s.event("trial_end", k, success=success, length=length, n_correct=len(done), practice=practice)
            wait(1.5, colors, "Great!" if success else "Not quite - that's okay", cursor=True)
            return success

        s.begin("Remember the Order",
                ["Blocks will light up one at a time.", "Remember the order.",
                 "Then use the LEFT stick to move the circle", "and press A on the same blocks, in order."])

        # ---- practice (not scored; up to 2 tries)
        s.event("phase_change", "", to="practice")
        for k in (0, 0):
            if run_trial(k, MIN_LEN, True):
                break
        s.event("phase_change", "", to="test")
        s.hold(["Let's begin the test", "Press A"], until_button=True, char=None)

        # ---- scored test
        k = 0
        span = 0
        passed = 0
        for length in range(MIN_LEN, MAX_LEN + 1):
            ok_here = 0
            for _ in range(TRIALS_PER_LEN):
                k += 1
                if run_trial(k, length, False):
                    ok_here += 1
                    passed += 1
                    span = length
            if ok_here == 0:
                break

        s.hold(["Finished - thank you!", f"Longest sequence remembered: {span}",
                f"Sequences correct: {passed} of {k}", "", "Press A to exit"], until_button=True)

    s.run(play)


if __name__ == "__main__":
    main()