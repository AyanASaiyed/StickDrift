// Live stream of the lobby to the Stick Drift API, so a caregiver can watch on the dashboard.
// Uses the resident's login cookie to open a session, then posts stick samples and game
// changes to /live/ingest about ten times a second. It never blocks or breaks the game:
// with no login or no API it stays silent.
const API = '/api'
const SAMPLE_HZ = 60
const POST_EVERY_MS = 100
const MAX_QUEUE = SAMPLE_HZ * 20

export class LiveStream {
  constructor() {
    this.token = null
    this.queue = []
    this.level = null
    this.t0 = performance.now()
    this.lastSample = -Infinity
    this.sending = false
    this.ended = false
  }

  async start(keyboard, levels) {
    try {
      const res = await fetch(`${API}/me/lobby/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyboard }),
      })
      if (!res.ok) return false // not logged in as a resident: play without streaming
      this.token = (await res.json()).token
    } catch {
      return false
    }
    this.event('session_start', { levels, synthetic: keyboard })
    this.enter('lobby')
    this.timer = setInterval(() => this.flush(), POST_EVERY_MS)
    window.addEventListener('pagehide', () => this.end())
    return true
  }

  event(type, data = {}) {
    if (this.token) this.queue.push({ type, ...data })
  }

  /** Switch the stream to a game (or back to 'lobby'), closing the previous one. */
  enter(level) {
    if (this.level) this.event('level_end', { level: this.level, completed: this.level !== 'lobby' })
    this.level = level
    this.event('level_start', { level })
  }

  /** Seconds since the stream opened; the clock the samples use. */
  now() {
    return (performance.now() - this.t0) / 1000
  }

  /** One 17-value sample from measure.js: t, trial, phase, sticks, targets, on-target flags, in-game hands. */
  sample(item) {
    if (!this.token) return
    if (item[0] - this.lastSample < 1 / SAMPLE_HZ) return
    this.lastSample = item[0]
    this.queue.push(item)
    if (this.queue.length > MAX_QUEUE) this.queue.splice(0, this.queue.length - MAX_QUEUE)
  }

  async flush() {
    if (!this.token || this.sending || this.queue.length === 0) return
    const items = this.queue.splice(0, 2000)
    this.sending = true
    try {
      const res = await fetch(`${API}/live/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Live-Token': this.token },
        body: JSON.stringify({ items }),
      })
      if (res.status === 410) this.stop() // the API forgot this session (restart or timeout)
    } catch {
      this.queue.unshift(...items.slice(-MAX_QUEUE)) // best effort: keep recent samples for a retry
    } finally {
      this.sending = false
    }
  }

  stop() {
    clearInterval(this.timer)
    this.token = null
  }

  end() {
    if (!this.token || this.ended) return
    this.ended = true
    const token = this.token
    const items = this.queue.splice(0)
    const headers = { 'Content-Type': 'application/json', 'X-Live-Token': token }
    // keepalive lets these finish while the tab is closing
    if (items.length) fetch(`${API}/live/ingest`, { method: 'POST', headers, body: JSON.stringify({ items }), keepalive: true }).catch(() => {})
    fetch(`${API}/live/end`, { method: 'POST', headers, keepalive: true }).catch(() => {})
    this.stop()
  }
}
