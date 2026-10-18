// Buffers one lobby game at a time and asks the API to write
// data/new_game_data/{stamp}_lobby/level_N_{name}/.
// Rows keep the live_samples columns, then the full browser pad state, then the DualSense
// motion cells from motion.js (blank when not measured) and t_wall.
import { AXIS_COUNT, BUTTON_NAMES } from './input.js'
import { MOTION_CELLS } from './motion.js'

const API = '/api'
const r4 = (v) => (typeof v === 'number' && Number.isFinite(v) ? Math.round(v * 1e4) / 1e4 : 0)

export function controllerCells(controller) {
  const cells = []
  for (let i = 0; i < AXIS_COUNT; i++) cells.push(r4(controller?.axes?.[i]))
  for (let i = 0; i < BUTTON_NAMES.length; i++) {
    const b = controller?.buttons?.[i]
    cells.push(b?.pressed ? 1 : 0, r4(b?.value))
  }
  return cells
}

/** motion is motion.latest(): 14 raw cells, or null, which writes blanks rather than zeros. */
export function motionCells(motion) {
  if (!motion) return Array(MOTION_CELLS).fill(null)
  return motion.slice(0, MOTION_CELLS)
}

/** sample is the 17-value array from measure.js. t is replaced with seconds since this level started. */
export function sampleRow(liveId, seq, level, t, sample, source, controller, motion = null) {
  const blank = (v) => (v == null ? null : v)
  return [
    liveId, seq, level, t,
    blank(sample[1]), blank(sample[2]),
    blank(sample[3]), blank(sample[4]), blank(sample[5]), blank(sample[6]),
    blank(sample[7]), blank(sample[8]), blank(sample[9]), blank(sample[10]),
    sample[11] ?? 0, sample[12] ?? 0,
    blank(sample[13]), blank(sample[14]), blank(sample[15]), blank(sample[16]),
    source,
    ...controllerCells(controller),
    ...motionCells(motion),
    t,
  ]
}

export class Recorder {
  constructor() {
    this.liveId = null
    this.folder = null
    this.opening = null
    this.level = null
    this.t0 = 0
    this.seq = 0
    this.rows = []
    this.trials = []
    this.source = 'none'
    this.motion = false
    this.sending = Promise.resolve()
  }

  /** Seconds since the current level started. */
  now() {
    return this.level ? (performance.now() - this.t0) / 1000 : 0
  }

  begin(level) {
    this.level = level
    this.t0 = performance.now()
    this.seq = 0
    this.rows = []
    this.trials = []
    this.source = 'none'
    this.motion = false
  }

  trial(event) {
    if (!this.level || !event) return
    this.trials.push(event)
  }

  /** sample is measure.frame's array; its clock is the whole visit, so the row uses this level's clock. */
  sample(sample, pad, motion = null) {
    if (!this.level) return
    this.seq += 1
    if (pad.source && pad.source !== 'none') this.source = pad.source
    if (motion) this.motion = true
    const t = Math.round(this.now() * 1000) / 1000
    this.rows.push(sampleRow(this.liveId, this.seq, this.level, t, sample, pad.source || 'none', pad.controller, motion))
  }

  async ensureSession() {
    if (this.liveId) return
    if (!this.opening) {
      this.opening = fetch(`${API}/lobby/record/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: this.source === 'none' ? 'keyboard' : this.source }),
      }).then(async (res) => {
        if (!res.ok) throw new Error(`record start ${res.status}`)
        const body = await res.json()
        this.liveId = body.live_id
        this.folder = body.folder
      }).catch((error) => {
        this.opening = null
        throw error
      })
    }
    await this.opening
  }

  /** Close the open level and write it. Empty visits are skipped. */
  end(meta, keepalive = false) {
    if (!this.level || this.rows.length === 0) {
      this.level = null
      return Promise.resolve()
    }
    const payload = {
      level: this.level,
      completed: !!meta.completed,
      duration_s: Math.round(this.now() * 1000) / 1000,
      score: meta.score ?? null,
      stars: meta.stars ?? null,
      source: this.source,
      motion: this.motion ? 'webhid' : 'none',
      trials: this.trials.splice(0),
      rows: this.rows.splice(0),
    }
    this.level = null
    const send = this.sending.then(() => this.postLevel(payload, keepalive))
    this.sending = send.catch(() => {})
    return send
  }

  async postLevel(payload, keepalive) {
    try {
      await this.ensureSession()
    } catch (error) {
      console.warn('Lobby recording did not start', error)
      return
    }
    for (const row of payload.rows) row[0] = this.liveId
    try {
      const res = await fetch(`${API}/lobby/record/level`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ live_id: this.liveId, folder: this.folder, ...payload }),
        keepalive,
      })
      if (!res.ok) console.warn('Lobby recording was not saved', res.status)
    } catch (error) {
      console.warn('Lobby recording was not saved', error)
    }
  }

  /** Mark the visit finished once any open level has been posted. */
  finish(keepalive = false) {
    return this.sending.then(() => {
      if (!this.liveId || !this.folder) return
      return fetch(`${API}/lobby/record/end`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ live_id: this.liveId, folder: this.folder }),
        keepalive,
      }).catch(() => {})
    })
  }
}
