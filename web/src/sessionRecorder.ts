import {
  abandonSession,
  finishSession,
  saveTrial,
  startSession,
  uploadEvents,
  uploadSamples,
  type Activity,
  type FinishSessionInput,
  type JoystickSample,
  type SessionEvent,
  type StartSessionInput,
  type TrialResult,
} from './api'

export interface SampleContext {
  activity?: Activity | null
  trial_id?: number | null
  target_x?: number | null
  target_y?: number | null
  cursor_x?: number | null
  cursor_y?: number | null
}

export interface AxisReading {
  connected: boolean
  lx: number
  ly: number
  rx: number
  ry: number
}

/**
 * Collects one combined game's three activity types into a single session.
 * Call recordSample from the game's animation loop (not from React state updates).
 */
export class SessionRecorder {
  readonly sessionId: string
  private readonly clientStartMs: number
  private readonly onUploadError: (error: unknown) => void
  private sequence = 0
  private sampleQueue: JoystickSample[] = []
  private eventQueue: SessionEvent[] = []
  private context: SampleContext = {}
  private sampleFlush: Promise<void> | null = null
  private eventFlush: Promise<void> | null = null
  private closed = false

  private constructor(
    sessionId: string,
    clientStartMs: number,
    onUploadError: (error: unknown) => void,
  ) {
    this.sessionId = sessionId
    this.clientStartMs = clientStartMs
    this.onUploadError = onUploadError
  }

  static async open(
    participantId: string,
    input: StartSessionInput = {},
    onUploadError: (error: unknown) => void = (error) => console.error('Session data upload failed.', error),
  ) {
    // Start the local monotonic clock before the request so sample times align
    // with the server-created session timestamp, including request latency.
    const clientStartMs = performance.now()
    const session = await startSession(participantId, input)
    return new SessionRecorder(session.session_id, clientStartMs, onUploadError)
  }

  setContext(context: SampleContext) {
    this.context = { ...context }
  }

  recordSample(axes: AxisReading) {
    if (this.closed) return
    this.sampleQueue.push({
      seq: this.sequence++,
      t_ms: performance.now() - this.clientStartMs,
      lx: axes.connected ? axes.lx : 0,
      ly: axes.connected ? axes.ly : 0,
      rx: axes.connected ? axes.rx : 0,
      ry: axes.connected ? axes.ry : 0,
      connected: axes.connected,
      ...this.context,
    })
    if (this.sampleQueue.length >= 120) void this.flushSamples().catch(this.onUploadError)
  }

  recordEvent(eventType: string, payload: Record<string, unknown> = {}) {
    if (this.closed) return
    this.eventQueue.push({
      event_id: crypto.randomUUID(),
      t_ms: performance.now() - this.clientStartMs,
      event_type: eventType,
      payload,
    })
    if (this.eventQueue.length >= 50) void this.flushEvents().catch(this.onUploadError)
  }

  async recordTrial(trial: TrialResult) {
    if (this.closed) throw new Error('This session has already ended.')
    await saveTrial(this.sessionId, trial)
    this.recordEvent('trial_recorded', { trial_id: trial.trial_id, activity: trial.activity })
  }

  private async flushSamples() {
    if (this.sampleFlush) return this.sampleFlush
    this.sampleFlush = (async () => {
      while (this.sampleQueue.length) {
        const batch = this.sampleQueue.splice(0, 500)
        try {
          await uploadSamples(this.sessionId, batch)
        } catch (error) {
          this.sampleQueue = [...batch, ...this.sampleQueue]
          throw error
        }
      }
    })()
    try {
      await this.sampleFlush
    } finally {
      this.sampleFlush = null
    }
  }

  private async flushEvents() {
    if (this.eventFlush) return this.eventFlush
    this.eventFlush = (async () => {
      while (this.eventQueue.length) {
        const batch = this.eventQueue.splice(0, 200)
        try {
          await uploadEvents(this.sessionId, batch)
        } catch (error) {
          this.eventQueue = [...batch, ...this.eventQueue]
          throw error
        }
      }
    })()
    try {
      await this.eventFlush
    } finally {
      this.eventFlush = null
    }
  }

  async complete(input: FinishSessionInput) {
    if (this.closed) return
    this.closed = true
    try {
      await Promise.all([this.flushSamples(), this.flushEvents()])
      await finishSession(this.sessionId, input)
    } catch (error) {
      this.closed = false
      throw error
    }
  }

  async abandon() {
    if (this.closed) return
    this.closed = true
    try {
      await Promise.all([this.flushSamples(), this.flushEvents()])
      await abandonSession(this.sessionId)
    } catch (error) {
      this.closed = false
      throw error
    }
  }
}
