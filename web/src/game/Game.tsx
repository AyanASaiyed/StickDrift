import { useEffect, useRef, useState } from 'react'
import type { SampleRecord, SessionComplete } from '../api'
import type { Chart, Hand } from './chart'
import { StickDetector } from './detector'
import type { Calibration, InputReader } from './input'
import { Judge } from './judge'
import { drawFrame, type Flash } from './render'

export type GameResult = Omit<SessionComplete, 'status'>

type PauseReason = 'user' | 'disconnect' | 'hidden'

interface Props {
  chart: Chart
  reader: InputReader
  calibration: Calibration
  practice: boolean
  onFinish: (result: GameResult) => void
  onStop: (result: GameResult) => void
}

const GREAT_MS = 150

export function Game({ chart, reader, calibration, practice, onFinish, onStop }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [pause, setPause] = useState<PauseReason | null>(null)
  const [connected, setConnected] = useState(true)
  const [confirmStop, setConfirmStop] = useState(false)
  // The loop reads these through refs so it never restarts mid-game.
  const pauseRef = useRef<PauseReason | null>(null)
  const actions = useRef({ pause: () => {}, resume: () => {}, stop: () => {} })
  const callbacks = useRef({ onFinish, onStop })
  callbacks.current = { onFinish, onStop }

  useEffect(() => {
    const canvas = canvasRef.current!
    const ctx = canvas.getContext('2d')!
    const judge = new Judge(chart)
    const det: Record<Hand, StickDetector> = { left: new StickDetector(), right: new StickDetector() }
    const c = calibration.center
    const samples: SampleRecord[] = []
    let flashes: Flash[] = []
    let disconnects = 0
    let lastConnected = true
    let ended = false
    let sticks = { lx: 0, ly: 0, rx: 0, ry: 0 }

    const start = performance.now()
    let pausedTotal = 0
    let pausedAt = 0
    const gameTime = (perf: number) => perf - start - pausedTotal

    const result = (): GameResult => ({
      trials: judge.trialRecords(),
      responses: judge.responseRecords(),
      samples,
      stray_moves: judge.strayMoves,
      disconnects,
    })

    const setPaused = (reason: PauseReason | null) => {
      if (reason && !pauseRef.current) pausedAt = performance.now()
      if (!reason && pauseRef.current) pausedTotal += performance.now() - pausedAt
      pauseRef.current = reason
      setPause(reason)
    }
    actions.current.pause = () => {
      if (!pauseRef.current && !ended) setPaused('user')
    }
    actions.current.resume = () => {
      if (pauseRef.current === 'disconnect' && !reader.peek().connected) return
      reader.poll() // drop samples taken while paused
      setPaused(null)
      setConfirmStop(false)
    }
    actions.current.stop = () => {
      if (ended) return
      ended = true
      callbacks.current.onStop(result())
    }

    const resize = () => {
      const dpr = window.devicePixelRatio || 1
      canvas.width = Math.round(canvas.clientWidth * dpr)
      canvas.height = Math.round(canvas.clientHeight * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)

    const onVisibility = () => {
      if (document.hidden && !pauseRef.current) setPaused('hidden')
    }
    document.addEventListener('visibilitychange', onVisibility)

    let frame = 0
    const loop = () => {
      frame = requestAnimationFrame(loop)
      const perf = performance.now()
      const btn = reader.buttons()

      if (pauseRef.current) {
        const live = reader.peek().connected
        setConnected(live)
        if (btn.confirm) actions.current.resume()
      } else {
        if (btn.pause) setPaused('user')
      }

      const now = pauseRef.current ? pausedAt - start - pausedTotal : gameTime(perf)
      if (!pauseRef.current) {
        judge.openWindows(now, { left: det.left.armed, right: det.right.armed })
        for (const s of reader.poll()) {
          if (!s.connected) {
            if (lastConnected) {
              disconnects++
              setConnected(false)
              setPaused('disconnect')
            }
            lastConnected = false
            continue
          }
          lastConnected = true
          const t = gameTime(s.t)
          sticks = { lx: s.lx - c.lx, ly: s.ly - c.ly, rx: s.rx - c.rx, ry: s.ry - c.ry }
          if (!practice) samples.push([performance.timeOrigin + s.t, t, s.lx, s.ly, s.rx, s.ry, true])
          for (const [hand, x, y] of [
            ['left', sticks.lx, sticks.ly],
            ['right', sticks.rx, sticks.ry],
          ] as [Hand, number, number][]) {
            const move = det[hand].update(x, y, t)
            if (!move) continue
            const j = judge.onMove(hand, move.dir, move.t)
            if (j?.outcome === 'hit') {
              flashes.push({ hand, dir: j.dir, at: now, text: Math.abs(j.offset_ms) <= GREAT_MS ? 'Great!' : 'Good' })
            }
          }
        }
        judge.closeWindows(now)
        flashes = flashes.filter((f) => now - f.at < 800)
      }

      drawFrame(ctx, canvas.clientWidth, canvas.clientHeight, {
        now,
        chart,
        notes: judge.notes,
        sticks,
        flashes,
        practice,
      })

      if (!ended && !pauseRef.current && now >= chart.end_ms && judge.done) {
        ended = true
        cancelAnimationFrame(frame)
        callbacks.current.onFinish(result())
      }
    }
    frame = requestAnimationFrame(loop)

    return () => {
      cancelAnimationFrame(frame)
      ro.disconnect()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [chart, reader, calibration, practice])

  return (
    <div className="stage">
      <canvas ref={canvasRef} className="stage-canvas" aria-label="Game: move the matching stick when each arrow reaches the outlined row" />
      <div className="stage-hud">
        {practice && <span className="badge badge-quiet">Practice: not scored</span>}
        {reader.kind === 'keyboard' && <span className="badge badge-sim">SIMULATED INPUT</span>}
        <button className="btn btn-ghost" onClick={() => actions.current.pause()}>
          Pause
        </button>
      </div>

      {pause && (
        <div className="overlay" role="dialog" aria-modal="true" aria-labelledby="pause-title">
          <div className="overlay-card">
            {pause === 'disconnect' ? (
              <>
                <h2 id="pause-title">Controller disconnected</h2>
                <p className="muted">
                  {connected
                    ? 'It’s back. Resume when you’re ready.'
                    : 'Plug the controller back in and press any button on it.'}
                </p>
              </>
            ) : (
              <>
                <h2 id="pause-title">Paused</h2>
                <p className="muted">Take as long as you need.</p>
              </>
            )}
            {confirmStop ? (
              <div className="stack">
                <p>
                  Stop this session? {practice ? 'Practice isn’t saved.' : 'What you’ve played so far is kept and marked as stopped early.'}
                </p>
                <div className="row">
                  <button className="btn" onClick={() => actions.current.stop()}>
                    Yes, stop
                  </button>
                  <button className="btn btn-quiet" onClick={() => setConfirmStop(false)}>
                    Keep playing
                  </button>
                </div>
              </div>
            ) : (
              <div className="row">
                <button
                  className="btn btn-big"
                  autoFocus
                  disabled={pause === 'disconnect' && !connected}
                  onClick={() => actions.current.resume()}
                >
                  Resume
                </button>
                <button className="btn btn-quiet" onClick={() => setConfirmStop(true)}>
                  Stop session
                </button>
              </div>
            )}
            {!confirmStop && reader.kind === 'gamepad_api' && (
              <p className="hint">Or press ✕ on the controller to resume.</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
