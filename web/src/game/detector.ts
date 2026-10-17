import type { Direction } from '../api'

// Thresholds on the calibrated, normalized axis (stick range is about -1..1).
// The gap between them is hysteresis: after a move counts, the stick must
// come back near the middle before the next move can count.
export const THRESHOLD = 0.4
export const NEUTRAL = 0.2
export const CONFIRM_SAMPLES = 2

export interface MoveEvent {
  dir: Direction
  t: number // time of the first sample past the threshold
}

/** Direction of the dominant axis, or null inside the neutral zone. */
export function stickDirection(x: number, y: number, min = THRESHOLD): Direction | null {
  const ax = Math.abs(x)
  const ay = Math.abs(y)
  if (Math.max(ax, ay) < min) return null
  // Gamepad API: negative Y is up.
  return ax >= ay ? (x < 0 ? 'left' : 'right') : y < 0 ? 'up' : 'down'
}

export class StickDetector {
  armed = true
  private pending: MoveEvent | null = null
  private count = 0

  update(x: number, y: number, t: number): MoveEvent | null {
    const mag = Math.max(Math.abs(x), Math.abs(y))
    if (mag < NEUTRAL) {
      this.armed = true
      this.pending = null
      return null
    }
    if (!this.armed || mag < THRESHOLD) {
      this.pending = null
      return null
    }
    const dir = stickDirection(x, y)!
    if (this.pending?.dir === dir) {
      this.count++
    } else {
      this.pending = { dir, t }
      this.count = 1
    }
    if (this.count >= CONFIRM_SAMPLES) {
      const event = this.pending
      this.armed = false
      this.pending = null
      return event
    }
    return null
  }
}
