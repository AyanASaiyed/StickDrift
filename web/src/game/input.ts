export interface RawSample {
  t: number // performance.now() clock
  lx: number
  ly: number
  rx: number
  ry: number
  connected: boolean
}

export interface Buttons {
  pause: boolean // Options / Esc, edge-triggered
  confirm: boolean // Cross / Enter / Space, edge-triggered
}

export interface InputReader {
  kind: 'gamepad_api' | 'keyboard'
  /** New samples since the last poll (0 or 1 per frame). */
  poll(): RawSample[]
  /** Latest values without consuming them. */
  peek(): RawSample
  buttons(): Buttons
  controllerId(): string | null
  dispose(): void
}

const firstPad = () => navigator.getGamepads?.().find((p): p is Gamepad => p !== null && p.connected) ?? null

// Standard mapping: buttons[0] = Cross, buttons[9] = Options.
const CROSS = 0
const OPTIONS = 9

export class GamepadReader implements InputReader {
  kind = 'gamepad_api' as const
  private lastTs = -1
  private lastConnected = true
  private prevPause = false
  private prevConfirm = false

  private read(pad: Gamepad | null): RawSample {
    if (!pad) return { t: performance.now(), lx: 0, ly: 0, rx: 0, ry: 0, connected: false }
    return {
      // Gamepad.timestamp is when the browser last received data from the device.
      t: pad.timestamp || performance.now(),
      lx: pad.axes[0] ?? 0,
      ly: pad.axes[1] ?? 0,
      rx: pad.axes[2] ?? 0,
      ry: pad.axes[3] ?? 0,
      connected: true,
    }
  }

  poll(): RawSample[] {
    const pad = firstPad()
    const s = this.read(pad)
    const changed = s.connected !== this.lastConnected || (s.connected && s.t !== this.lastTs)
    this.lastConnected = s.connected
    if (!changed) return []
    this.lastTs = s.t
    return [s]
  }

  peek(): RawSample {
    return this.read(firstPad())
  }

  buttons(): Buttons {
    const pad = firstPad()
    const pause = !!pad?.buttons[OPTIONS]?.pressed
    const confirm = !!pad?.buttons[CROSS]?.pressed
    const out = { pause: pause && !this.prevPause, confirm: confirm && !this.prevConfirm }
    this.prevPause = pause
    this.prevConfirm = confirm
    return out
  }

  controllerId() {
    return firstPad()?.id ?? null
  }

  dispose() {}
}

/**
 * Keyboard stand-in for the two sticks: WASD = left stick, arrow keys = right
 * stick. Sessions played this way are stored as simulated.
 */
export class KeyboardReader implements InputReader {
  kind = 'keyboard' as const
  private down = new Set<string>()
  private pauseQueued = false
  private confirmQueued = false

  private onDown = (e: KeyboardEvent) => {
    if (e.code.startsWith('Arrow') || e.code === 'Space') e.preventDefault()
    if (e.repeat) return
    this.down.add(e.code)
    if (e.code === 'Escape') this.pauseQueued = true
    if (e.code === 'Enter' || e.code === 'Space') this.confirmQueued = true
  }
  private onUp = (e: KeyboardEvent) => this.down.delete(e.code)
  private onBlur = () => this.down.clear()

  constructor() {
    window.addEventListener('keydown', this.onDown)
    window.addEventListener('keyup', this.onUp)
    window.addEventListener('blur', this.onBlur)
  }

  private axis(neg: string, pos: string) {
    return (this.down.has(pos) ? 1 : 0) - (this.down.has(neg) ? 1 : 0)
  }

  peek(): RawSample {
    return {
      t: performance.now(),
      lx: this.axis('KeyA', 'KeyD'),
      ly: this.axis('KeyW', 'KeyS'),
      rx: this.axis('ArrowLeft', 'ArrowRight'),
      ry: this.axis('ArrowUp', 'ArrowDown'),
      connected: true,
    }
  }

  poll(): RawSample[] {
    return [this.peek()]
  }

  buttons(): Buttons {
    const out = { pause: this.pauseQueued, confirm: this.confirmQueued }
    this.pauseQueued = this.confirmQueued = false
    return out
  }

  controllerId() {
    return 'keyboard'
  }

  dispose() {
    window.removeEventListener('keydown', this.onDown)
    window.removeEventListener('keyup', this.onUp)
    window.removeEventListener('blur', this.onBlur)
  }
}

export interface Calibration {
  ok: boolean
  center: { lx: number; ly: number; rx: number; ry: number }
  jitter: { lx: number; ly: number; rx: number; ry: number }
  samples: number
}

const MAX_CENTER_OFFSET = 0.25
const MAX_JITTER = 0.05

/** Resting center and noise of each axis, from samples taken while the sticks are untouched. */
export function calibrate(samples: RawSample[]): Calibration {
  const axes = ['lx', 'ly', 'rx', 'ry'] as const
  const live = samples.filter((s) => s.connected)
  const center = { lx: 0, ly: 0, rx: 0, ry: 0 }
  const jitter = { lx: 0, ly: 0, rx: 0, ry: 0 }
  for (const a of axes) {
    const v = live.map((s) => s[a])
    const mean = v.reduce((x, y) => x + y, 0) / (v.length || 1)
    center[a] = Math.round(mean * 1000) / 1000
    jitter[a] = Math.round(Math.sqrt(v.reduce((x, y) => x + (y - mean) ** 2, 0) / (v.length || 1)) * 1000) / 1000
  }
  const ok =
    live.length >= 10 &&
    axes.every((a) => Math.abs(center[a]) <= MAX_CENTER_OFFSET && jitter[a] <= MAX_JITTER)
  return { ok, center, jitter, samples: live.length }
}
