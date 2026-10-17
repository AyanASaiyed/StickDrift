"""Push live sessions to caregivers over a WebSocket instead of polling.

The resident's game posts to the API on the resident's own computer, and that
API writes to TigerData (live.py). It also sends a Postgres NOTIFY on the
`stickdrift_live` channel in the same transaction: small sample batches ride
in the notification itself; big ones and state changes send only a pointer.

Every API that has a caregiver watching keeps one LISTEN connection (here, on
a background thread) and fans each notification out to its WebSocket viewers.
So TigerData is read only to fill a gap or to fetch session state (at most
every STATE_DEBOUNCE_S, and every REFRESH_S so a vanished game shows as lost),
no matter how many caregivers are watching.

Messages sent to the browser, all JSON:
  {"type": "snapshot", ...state, "samples": [...]}   once, on connect
  {"type": "samples", "samples": [...]}              new samples, in order
  {"type": "state", ...state}                        status, level, metrics, result
  {"type": "resync"}                                 this viewer fell behind; reconnect
"""
import asyncio
import json
import logging
import os
import threading
import time
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse
from uuid import UUID

import psycopg
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import auth, live
from .db import DATABASE_URL

log = logging.getLogger(__name__)
router = APIRouter(tags=["live"])

SNAPSHOT_LIMIT = 2000   # samples sent on connect (~20 s at 100 Hz)
GAP_LIMIT = 4000        # most samples fetched to fill one gap
STATE_DEBOUNCE_S = 0.25
REFRESH_S = 5
QUEUE_MAX = 400         # messages a slow viewer may fall behind before it is told to resync
ALLOWED_ORIGINS = {o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()}


def _dump(msg: dict) -> str:
    return json.dumps(msg, default=str, separators=(",", ":"))


class Watch:
    """One live session that at least one caregiver on this API is viewing."""

    def __init__(self, live_id: str):
        self.live_id = live_id
        self.clients: Set[asyncio.Queue] = set()
        self.seq: Optional[int] = None    # newest sample sent to viewers; None until the first snapshot
        self.early: List[list] = []       # samples that arrived before that snapshot
        self.fetch_lock = asyncio.Lock()
        self.state_due = False
        self.refresher: Optional[asyncio.Task] = None


class Hub:
    def __init__(self):
        self.watches: Dict[str, Watch] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.stopping = threading.Event()

    # ---- the LISTEN connection (background thread) ------------------------

    def _ensure_listener(self):
        if self.thread and self.thread.is_alive():
            return
        self.loop = asyncio.get_running_loop()
        self.stopping.clear()
        self.thread = threading.Thread(target=self._listen, name="live-listen", daemon=True)
        self.thread.start()

    def _listen(self):
        backoff = 1.0
        while not self.stopping.is_set():
            try:
                with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
                    conn.execute(f"LISTEN {live.CHANNEL}")
                    backoff = 1.0
                    self.loop.call_soon_threadsafe(self._resync_all)  # anything missed while reconnecting
                    while not self.stopping.is_set():
                        for n in conn.notifies(timeout=2):
                            self.loop.call_soon_threadsafe(self._on_notify, n.payload)
            except Exception:
                if self.stopping.is_set():
                    break
                log.exception("Live LISTEN connection dropped; retrying in %.0f s", backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)

    def close(self):
        self.stopping.set()

    # ---- notifications (event loop) ----------------------------------------

    def _on_notify(self, payload: str):
        try:
            msg = json.loads(payload)
        except ValueError:
            return
        w = self.watches.get(msg.get("i"))
        if w is None:
            return
        if "s" in msg:
            self._take(w, msg["s"])
        elif "q" in msg:
            asyncio.create_task(self._fill(w))
        elif "st" in msg:
            self._state_soon(w)

    def _take(self, w: Watch, rows: List[list]):
        if not rows:
            return
        if w.seq is None:
            w.early.extend(rows)
            return
        if rows[0][0] > w.seq + 1:  # a batch went missing (too big to inline, or a reconnect)
            asyncio.create_task(self._fill(w))
            return
        fresh = [r for r in rows if r[0] > w.seq]
        if fresh:
            w.seq = fresh[-1][0]
            self._send(w, {"type": "samples", "samples": fresh})

    async def _fill(self, w: Watch):
        async with w.fetch_lock:
            if w.seq is None:
                return
            rows = await asyncio.to_thread(live.samples_since, UUID(w.live_id), w.seq, GAP_LIMIT)
            fresh = [r for r in rows if r[0] > w.seq]
            if fresh:
                w.seq = fresh[-1][0]
                self._send(w, {"type": "samples", "samples": fresh})

    def _state_soon(self, w: Watch):
        if w.state_due:
            return
        w.state_due = True
        self.loop.call_later(STATE_DEBOUNCE_S, lambda: asyncio.create_task(self._push_state(w)))

    async def _push_state(self, w: Watch):
        w.state_due = False
        try:
            st = await asyncio.to_thread(live.state, UUID(w.live_id))
        except Exception:
            log.exception("Reading live state failed")
            return
        if st is not None:
            self._send(w, {"type": "state", **st})

    async def _refresh(self, w: Watch):
        while True:
            await asyncio.sleep(REFRESH_S)
            await self._push_state(w)

    def _resync_all(self):
        for w in self.watches.values():
            asyncio.create_task(self._fill(w))
            self._state_soon(w)

    def _send(self, w: Watch, msg: dict):
        text = _dump(msg)  # serialised once for every viewer
        for q in list(w.clients):
            try:
                q.put_nowait(text)
            except asyncio.QueueFull:
                while not q.empty():
                    q.get_nowait()
                q.put_nowait(_dump({"type": "resync"}))

    # ---- viewers ------------------------------------------------------------

    def subscribe(self, live_id: str, q: asyncio.Queue) -> Watch:
        self._ensure_listener()
        w = self.watches.get(live_id)
        if w is None:
            w = self.watches[live_id] = Watch(live_id)
            w.refresher = asyncio.create_task(self._refresh(w))
        w.clients.add(q)
        return w

    def started(self, w: Watch, seq: int):
        """A viewer has its snapshot up to `seq`; begin streaming after it."""
        if w.seq is None:
            w.seq = seq
            early, w.early = w.early, []
            self._take(w, [r for r in early if r[0] > seq])

    def unsubscribe(self, w: Watch, q: asyncio.Queue):
        w.clients.discard(q)
        if not w.clients and self.watches.get(w.live_id) is w:
            del self.watches[w.live_id]
            if w.refresher:
                w.refresher.cancel()


hub = Hub()


def _origin_ok(ws: WebSocket) -> bool:
    """Browsers send cookies with cross-site WebSocket handshakes, so only accept our own pages."""
    origin = ws.headers.get("origin")
    if not origin or origin in ALLOWED_ORIGINS:
        return True
    return urlparse(origin).netloc == ws.headers.get("host")


@router.websocket("/caregiver/live/{live_id}/ws")
async def live_socket(ws: WebSocket, live_id: UUID):
    if not _origin_ok(ws):
        await ws.close(code=4403)
        return
    account = await asyncio.to_thread(auth.lookup, ws)
    if account is None or account["role"] != "caregiver":
        await ws.close(code=4401)
        return
    await ws.accept()

    q: asyncio.Queue = asyncio.Queue(QUEUE_MAX)
    w = hub.subscribe(str(live_id), q)
    try:
        # Subscribe first, then read: anything newer than the snapshot is already queued (duplicates are dropped
        # by seq in the browser).
        st = await asyncio.to_thread(live.state, live_id)
        if st is None:
            await ws.close(code=4404)
            return
        samples = await asyncio.to_thread(live.samples_since, live_id, 0, SNAPSHOT_LIMIT)
        await ws.send_text(_dump({"type": "snapshot", **st, "samples": samples}))
        hub.started(w, samples[-1][0] if samples else st["seq"])

        async def pump():
            while True:
                await ws.send_text(await q.get())

        async def drain():  # the browser sends nothing; this notices when it goes away
            while True:
                await ws.receive_text()

        tasks = [asyncio.create_task(pump()), asyncio.create_task(drain())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        for t in done:
            if t.exception() and not isinstance(t.exception(), WebSocketDisconnect):
                log.warning("Live socket ended: %r", t.exception())
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(w, q)
