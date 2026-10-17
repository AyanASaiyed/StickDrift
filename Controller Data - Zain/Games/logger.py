"""
logger.py - shared helpers for the three screening games.

Contains:
  * DataWriter : writes {game}_{player}_{session}_{timestamp}_raw.csv / _events.csv / _meta.json
  * Session    : pygame window, fixed 60 Hz loop, controller reading, logging

Controller input comes from the existing script (dualsense_viewer.py, UNMODIFIED).
Its Reader thread keeps reading HID reports; every frame we simply grab the latest state.

Typical game structure:

    s = Session("trace", extra_args=add_args, params={...})
    s.meta["something"] = ...              # anything you want saved in meta.json
    def play(s):
        s.begin("Title", ["instructions"]) # waits for controller + button press, starts logging
        while ...:
            f = s.tick()                   # waits for next 60 Hz tick, reads controller
            ...update using f.mx, f.my, f.pressed...
            ...draw on s.screen...
            s.present((char_x, char_y))    # writes ONE raw row + flips display
    s.run(play)                            # handles quit / crash / Ctrl-C and always flushes files
"""
import argparse
import csv
import json
import math
import os
import re
import time

import pygame

from read_data import Reader

# ---------------------------------------------------------------- constants
W, H = 1280, 720
FPS = 60
DT = 1.0 / FPS            # fixed simulation step (seconds)
SLOW_FRAME_S = 0.025      # frames slower than this are counted + warned about
DEADZONE = 0.10           # applied ONLY to movement, never to logged raw values
BG = (20, 22, 28)
WHITE = (235, 235, 235)


class QuitGame(Exception):
    """Raised when the window is closed or Esc is pressed."""


class Frame:
    """Input snapshot for one frame."""

    def __init__(self, frame, t, raw_x, raw_y, raw_rx, raw_ry, button, pressed, mx, my):
        self.frame = frame      # frame index (0,1,2,...) since game start
        self.t = t              # seconds since game start
        self.raw_x = raw_x      # raw stick X (0..255 int as read, None if controller lost)
        self.raw_y = raw_y      # raw stick Y (0..255, 0 = up, 255 = down)
        self.raw_rx = raw_rx    # raw right-stick X (0..255, None if controller lost)
        self.raw_ry = raw_ry    # raw right-stick Y (0..255, 0 = up, 255 = down)
        self.button = button    # raw button level (0/1, None if lost)
        self.pressed = pressed  # True only on the frame the button goes 0 -> 1
        self.mx = mx            # movement X after deadzone/scaling, -1..1 (for gameplay only)
        self.my = my            # movement Y after deadzone/scaling, -1..1


def stick_to_move(raw_x, raw_y):
    """Convert raw 0..255 stick bytes to a deadzoned vector in -1..1. NOT used for logging."""
    if raw_x is None:
        return 0.0, 0.0
    x = (raw_x - 127.5) / 127.5
    y = (raw_y - 127.5) / 127.5
    m = math.hypot(x, y)
    if m < DEADZONE:
        return 0.0, 0.0
    scale = min(1.0, (m - DEADZONE) / (1.0 - DEADZONE)) / m
    return x * scale, y * scale


class DataWriter:
    """Owns the three output files. Rows are buffered; close() flushes everything."""

    def __init__(self, game, player, session, meta):
        os.makedirs("data", exist_ok=True)
        player = re.sub(r"[^A-Za-z0-9_-]", "_", str(player))
        stamp = time.strftime("%Y%m%d_%H%M%S")
        base = os.path.join("data", f"{game}_{player}_{session}_{stamp}")
        self.meta_path = base + "_meta.json"
        self._raw_f = open(base + "_raw.csv", "w", newline="", buffering=1 << 16)
        self._ev_f = open(base + "_events.csv", "w", newline="", buffering=1 << 16)
        self._raw = csv.writer(self._raw_f, lineterminator="\n")
        self._ev = csv.writer(self._ev_f, lineterminator="\n")
        self._raw.writerow(["t", "raw_x", "raw_y", "raw_rx", "raw_ry", "button",
                            "char_x", "char_y", "frame"])
        self._ev.writerow(["t", "event", "trial", "data"])
        self.write_meta(meta)  # written early so a crash still leaves a meta file
        self.paths = (base + "_raw.csv", base + "_events.csv", self.meta_path)

    def raw(self, t, raw_x, raw_y, raw_rx, raw_ry, button, cx, cy, frame):
        blank = lambda v: "" if v is None else v
        self._raw.writerow([f"{t:.6f}", blank(raw_x), blank(raw_y), blank(raw_rx), blank(raw_ry),
                            blank(button),
                            "" if cx is None else round(cx, 3),
                            "" if cy is None else round(cy, 3), frame])

    def event(self, t, name, trial, data):
        self._ev.writerow([f"{t:.6f}", name, trial, json.dumps(data, separators=(",", ":"))])

    def write_meta(self, meta):
        with open(self.meta_path, "w") as f:  # single line of JSON
            f.write(json.dumps(meta, separators=(",", ":")) + "\n")

    def close(self, meta):
        for f in (self._raw_f, self._ev_f):
            try:
                f.flush()
                f.close()
            except Exception:
                pass
        self.write_meta(meta)


class Session:
    def __init__(self, game, extra_args=None, params=None):
        p = argparse.ArgumentParser(description=game)
        p.add_argument("--player", default="anon", help="player ID (default anon)")
        p.add_argument("--session", type=int, default=1, help="session number (default 1)")
        if extra_args:
            extra_args(p)
        self.args = p.parse_args()
        self.game = game

        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption(game)
        self.font = pygame.font.SysFont(None, 34)
        self.big = pygame.font.SysFont(None, 60)

        self.reader = Reader()   # background thread reading the DualSense
        self.reader.start()

        self.meta = {
            "game": game, "player": self.args.player, "session": self.args.session,
            "controller": "Sony DualSense / DualSense Edge (HID via dualsense_viewer.Reader)",
            "screen": [W, H], "fps_target": FPS, "movement_deadzone": DEADZONE,
            "raw_note": ("raw_x/raw_y are left-stick bytes and raw_rx/raw_ry are right-stick bytes; "
                         "all are unmodified 0-255 values, centre ~128, y grows downward"),
            "params": dict(params or {}),
        }
        self.writer = None
        self.t0 = None
        self.cur = None            # most recent Frame
        self.frame_no = 0
        self._next_tick = None
        self._last_stamp = None
        self._prev_button = 0
        self.slow_frames = 0
        self.max_frame_s = 0.0

    # ------------------------------------------------------------ timing
    def now(self):
        """Seconds since game start."""
        return time.perf_counter() - self.t0

    def tick(self):
        """Wait for the next 60 Hz tick, pump window events, read the controller."""
        if self._next_tick is None:
            self._next_tick = time.perf_counter()
        while True:                                  # sleep, then spin for the last 2 ms
            remaining = self._next_tick - time.perf_counter()
            if remaining <= 0:
                break
            if remaining > 0.002:
                time.sleep(remaining - 0.002)
        stamp = time.perf_counter()
        self._next_tick += DT
        if self._next_tick < stamp:                  # we fell behind: resync instead of bursting
            self._next_tick = stamp + DT

        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                raise QuitGame()

        st = self.reader.state                       # latest controller report (or None)
        if st is None:
            raw_x = raw_y = raw_rx = raw_ry = button = None
        else:
            raw_x, raw_y, button = st["lx"], st["ly"], st["Cross"]  # Cross = "A" / button 0
            raw_rx, raw_ry = st["rx"], st["ry"]

        pressed = bool(button) and not self._prev_button
        self._prev_button = button or 0
        mx, my = stick_to_move(raw_x, raw_y)

        t = 0.0
        if self.t0 is not None:
            t = stamp - self.t0
            if self._last_stamp is not None:
                dt = stamp - self._last_stamp
                self.max_frame_s = max(self.max_frame_s, dt)
                if dt > SLOW_FRAME_S:
                    self.slow_frames += 1
            self._last_stamp = stamp
        self.cur = Frame(self.frame_no if self.t0 is not None else -1,
                         t, raw_x, raw_y, raw_rx, raw_ry, button, pressed, mx, my)
        return self.cur

    def present(self, char=None):
        """Log ONE raw row for this frame and flip the display. Call exactly once per tick()."""
        f = self.cur
        if self.writer is not None:
            cx, cy = char if char else (None, None)
            self.writer.raw(f.t, f.raw_x, f.raw_y, f.raw_rx, f.raw_ry,
                            f.button, cx, cy, f.frame)
            self.frame_no += 1
        if f.raw_x is None and self.t0 is not None:
            self.text(["CONTROLLER LOST"], y=10, big_first=False)
        pygame.display.flip()

    # ------------------------------------------------------------ logging
    def event(self, name, trial="", t=None, **data):
        """Write one event row. Time defaults to the current frame's time."""
        if self.writer is None:
            return
        if t is None:
            t = self.cur.t if self.cur is not None else self.now()
        self.writer.event(t, name, trial, data)

    def start(self):
        """Create the output files and start the game clock (t = 0)."""
        self.writer = DataWriter(self.game, self.args.player, self.args.session, self.meta)
        self.t0 = time.perf_counter()
        self.cur = None
        self.frame_no = 0
        self._last_stamp = None
        self.event("game_start", player=self.args.player, session=self.args.session)

    def close(self, completed):
        if self.writer is not None:
            self.event("game_end", t=self.now(), completed=completed,
                       frames=self.frame_no, slow_frames=self.slow_frames)
            self.meta["frames"] = self.frame_no
            self.meta["slow_frames_over_25ms"] = self.slow_frames
            self.meta["max_frame_ms"] = round(self.max_frame_s * 1000, 2)
            self.meta["completed"] = completed
            self.writer.close(self.meta)
            print("Saved:", *self.writer.paths, sep="\n  ")
            if self.slow_frames:
                print(f"WARNING: {self.slow_frames} frame(s) took >25 ms "
                      f"(max {self.max_frame_s * 1000:.1f} ms). Raw data has timing gaps.")
            else:
                print("Timing OK: no frame took longer than 25 ms.")
        pygame.quit()

    def run(self, play):
        """Run play(session); ALWAYS flush files, even on crash or Ctrl-C."""
        completed = False
        try:
            play(self)
            completed = True
        except (QuitGame, KeyboardInterrupt):
            print("Stopped early.")
        finally:
            self.close(completed)

    # ------------------------------------------------------------ simple screens
    def text(self, lines, y=None, big_first=True):
        y0 = y if y is not None else H / 2 - len(lines) * 22
        for i, line in enumerate(lines):
            font = self.big if (i == 0 and big_first) else self.font
            img = font.render(line, True, WHITE)
            self.screen.blit(img, img.get_rect(center=(W // 2, int(y0 + i * 44 + 20))))

    def hold(self, lines, seconds=None, until_button=False, char=None, draw=None, y=None):
        """Show text; return after `seconds` and/or a button press (whichever comes first).
        Frames (and raw rows) keep being logged. Needs seconds or until_button."""
        begin = time.perf_counter()
        while True:
            f = self.tick()
            if draw:
                draw(f)
            else:
                self.screen.fill(BG)
            self.text(lines, y)
            self.present(char)
            if until_button and f.pressed:
                return
            if seconds is not None and time.perf_counter() - begin >= seconds:
                return

    def begin(self, title, instructions):
        """Wait for the controller, show instructions, wait for A, then start logging."""
        while self.reader.state is None:
            self.tick()
            self.screen.fill(BG)
            self.text(["Waiting for controller...", "Plug in the DualSense via USB"])
            pygame.display.flip()
        self.hold([title] + list(instructions) + ["", "Press A to start"], until_button=True)
        self.start()
