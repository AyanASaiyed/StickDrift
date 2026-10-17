import { useEffect, useState } from 'react'

export interface GamepadState {
  connected: boolean
  id: string
  isDualSense: boolean
  standardMapping: boolean
  // Standard mapping: axes 0/1 = left stick, 2/3 = right stick. Up on Y is negative.
  lx: number
  ly: number
  rx: number
  ry: number
}

const DISCONNECTED: GamepadState = {
  connected: false,
  id: '',
  isDualSense: false,
  standardMapping: false,
  lx: 0,
  ly: 0,
  rx: 0,
  ry: 0,
}

// Sony vendor 054c, DualSense product 0ce6 (DualSense Edge is 0df2).
const isDualSense = (id: string) => /dualsense|054c.*(0ce6|0df2)/i.test(id)

const axis = (v: number | undefined) => (Number.isFinite(v) ? v! : 0)

/**
 * Polls the first connected gamepad once per animation frame.
 * Browsers only expose a gamepad after a button on it has been pressed.
 */
export function useGamepad(): GamepadState {
  const [state, setState] = useState<GamepadState>(DISCONNECTED)

  useEffect(() => {
    let frame = 0
    const poll = () => {
      const pad = navigator.getGamepads?.().find((p): p is Gamepad => p !== null && p.connected)
      setState((prev) => {
        if (!pad) return prev.connected ? DISCONNECTED : prev
        const next: GamepadState = {
          connected: true,
          id: pad.id,
          isDualSense: isDualSense(pad.id),
          standardMapping: pad.mapping === 'standard',
          // Preserve the browser's full axis precision for the assessment log.
          lx: axis(pad.axes[0]),
          ly: axis(pad.axes[1]),
          rx: axis(pad.axes[2]),
          ry: axis(pad.axes[3]),
        }
        const same = (Object.keys(next) as (keyof GamepadState)[]).every((k) => next[k] === prev[k])
        return same ? prev : next
      })
      frame = requestAnimationFrame(poll)
    }
    frame = requestAnimationFrame(poll)
    return () => cancelAnimationFrame(frame)
  }, [])

  return state
}
