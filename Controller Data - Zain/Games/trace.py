"""
trace.py - Game 1: steer an orb along a winding lane, left to right (velocity control).

Run:  python trace.py --player P01 --session 1 [--seed 123]
3 trials, 3 different seeded tracks (seeds = base, base+1, base+2).
Each track: gentle curves -> long almost-straight section -> 2 sharper turns -> finish.
"""
import math
import random

import pygame

from logger import Session, W, H, DT, BG

LANE_W = 50            # lane width in px
HALF = LANE_W / 2
ORB_R = 10
SPEED = 260.0          # px/s at full stick deflection
N_TRIALS = 3
STEP = 5.0             # centerline point spacing (px)
LANE_COL, ON_COL, OFF_COL = (60, 64, 82), (80, 200, 120), (230, 70, 70)


def catmull(p0, p1, p2, p3, t):
    """Uniform Catmull-Rom spline point between p1 and p2."""
    return tuple(0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t
                        + (-a + 3 * b - 3 * c + d) * t ** 3)
                 for a, b, c, d in zip(p0, p1, p2, p3))


def build_track(seed):
    """Return list of (x, y) centerline points, ~STEP px apart, from left to right."""
    rng = random.Random(seed)
    flip = rng.choice((-1, 1))          # mirror vertically for variety
    cy = H / 2
    j = lambda a: rng.uniform(-a, a)
    # (x, y-offset-from-middle) control points
    offs = [
        (90, 0),
        (220, 90 + j(20)), (360, -(70 + j(20))), (460, -15 + j(8)),   # gentle curves
        (560, j(3)), (680, j(3)), (800, j(3)), (880, j(3)),            # long ~straight section
        (945 + j(8), -20 + j(8)), (985 + j(8), -85 + j(8)),            # sharp turn 1 (east -> north)
        (992, -160 + j(10)), (1020, -215 + j(8)),                      # sharp turn 2 (north -> east)
        (1085, -230 + j(8)), (1140, -190 + j(10)), (1190, -150 + j(15)),
    ]
    ctrl = [(x, cy + flip * dy) for x, dy in offs]
    n = len(ctrl)
    dense = []
    for i in range(n - 1):
        p0, p1, p2, p3 = ctrl[max(i - 1, 0)], ctrl[i], ctrl[i + 1], ctrl[min(i + 2, n - 1)]
        dense += [catmull(p0, p1, p2, p3, k / 40) for k in range(40)]
    dense.append(ctrl[-1])
    pts, acc = [dense[0]], 0.0           # resample to roughly even spacing
    for a, b in zip(dense, dense[1:]):
        acc += math.dist(a, b)
        if acc >= STEP:
            pts.append(b)
            acc = 0.0
    if pts[-1] != dense[-1]:
        pts.append(dense[-1])
    return [(round(x, 1), round(y, 1)) for x, y in pts]


def nearest_dist(pts, x, y):
    """Distance from (x,y) to the closest centerline point."""
    best = 1e18
    for px, py in pts:
        d = (px - x) ** 2 + (py - y) ** 2
        if d < best:
            best = d
    return math.sqrt(best)


def render_track(pts):
    surf = pygame.Surface((W, H))
    surf.fill(BG)
    for p in pts:
        pygame.draw.circle(surf, LANE_COL, (int(p[0]), int(p[1])), int(HALF))
    pygame.draw.lines(surf, (200, 200, 210), False, pts, 2)       # centerline
    pygame.draw.circle(surf, (120, 160, 255), (int(pts[0][0]), int(pts[0][1])), int(HALF), 3)
    pygame.draw.circle(surf, (255, 220, 80), (int(pts[-1][0]), int(pts[-1][1])), int(HALF), 3)
    return surf


def add_args(p):
    p.add_argument("--seed", type=int, default=None, help="base seed for the 3 tracks (default random)")


def main():
    s = Session("trace", extra_args=add_args)
    base = s.args.seed if s.args.seed is not None else random.randrange(2 ** 30)
    seeds = [base + i for i in range(N_TRIALS)]
    tracks = [build_track(sd) for sd in seeds]
    s.meta["params"] = {"lane_width": LANE_W, "orb_radius": ORB_R, "speed_px_s": SPEED,
                        "n_trials": N_TRIALS, "base_seed": base, "seeds": seeds}
    # full centerlines saved once so deviation can be computed offline
    s.meta["tracks"] = [{"trial": i + 1, "seed": sd, "centerline": pts}
                        for i, (sd, pts) in enumerate(zip(seeds, tracks))]

    def play(s):
        results = []
        s.begin("Trace", ["Steer the orb along the lane from left to right",
                          "Stay inside the lane (orb turns red when outside)"])
        for k in range(1, N_TRIALS + 1):
            pts = tracks[k - 1]
            surf = render_track(pts)
            pos = [float(pts[0][0]), float(pts[0][1])]
            end = pts[-1]

            def scene(f, color=ON_COL):
                s.screen.blit(surf, (0, 0))
                pygame.draw.circle(s.screen, color, (int(pos[0]), int(pos[1])), ORB_R)

            s.hold([f"Trial {k}/{N_TRIALS}", "Press A to begin"], until_button=True,
                   char=pos, draw=scene, y=20)

            s.event("trial_start", k, seed=seeds[k - 1], start=pts[0])
            t_begin = None
            frames = on_frames = off_count = 0
            off = False
            off_since = 0.0
            while True:
                f = s.tick()
                if t_begin is None:
                    t_begin = f.t
                # velocity control: position += stick * speed * dt
                pos[0] = min(max(pos[0] + f.mx * SPEED * DT, 0), W)
                pos[1] = min(max(pos[1] + f.my * SPEED * DT, 0), H)

                dist = nearest_dist(pts, pos[0], pos[1])
                now_off = dist > HALF
                if now_off and not off:
                    off_count += 1
                    off_since = f.t
                    s.event("off_path", k, x=round(pos[0], 1), y=round(pos[1], 1), dist=round(dist, 1))
                elif off and not now_off:
                    s.event("back_on_path", k, x=round(pos[0], 1), y=round(pos[1], 1),
                            off_duration=round(f.t - off_since, 3))
                off = now_off
                frames += 1
                on_frames += 0 if off else 1

                scene(f, OFF_COL if off else ON_COL)
                done = math.dist(pos, end) < HALF
                if done:
                    pct = 100.0 * on_frames / frames
                    s.event("finish", k, time=round(f.t - t_begin, 3), pct_on_path=round(pct, 1),
                            off_path_count=off_count)
                    results.append((f.t - t_begin, pct))
                s.present(pos)
                if done:
                    break

        lines = ["Done!"] + [f"Trial {i}: {t:.1f} s   {p:.0f}% on path"
                             for i, (t, p) in enumerate(results, 1)] + ["", "Press A to exit"]
        s.hold(lines, until_button=True, char=pos)

    s.run(play)


if __name__ == "__main__":
    main()
