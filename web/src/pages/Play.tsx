import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { api, summarizeGame, type Placement } from '../api'
import { assessmentChart, practiceChart, PROTOCOL_VERSION } from '../game/chart'
import { Game, type GameResult } from '../game/Game'
import { calibrate, GamepadReader, KeyboardReader, type Calibration, type InputReader, type RawSample } from '../game/input'

export interface PlayState {
  input: 'gamepad' | 'keyboard'
  placement: Placement
}

type Phase =
  | { name: 'calibrate' }
  | { name: 'howto' }
  | { name: 'practice' }
  | { name: 'ready' }
  | { name: 'main' }
  | { name: 'saving'; result: GameResult; status: 'completed' | 'abandoned' }
  | { name: 'done'; sessionId: string }
  | { name: 'stopped' }

const KEYBOARD_CALIBRATION: Calibration = {
  ok: true,
  center: { lx: 0, ly: 0, rx: 0, ry: 0 },
  jitter: { lx: 0, ly: 0, rx: 0, ry: 0 },
  samples: 0,
}

const CALIBRATE_MS = 1500

/** Calls `onConfirm` when ✕ / Enter / Space is pressed, while `active`. */
function useConfirm(reader: InputReader | null, active: boolean, onConfirm: () => void) {
  const cb = useRef(onConfirm)
  cb.current = onConfirm
  useEffect(() => {
    if (!reader || !active) return
    reader.buttons() // clear presses that happened before this screen
    let frame = 0
    const loop = () => {
      if (reader.buttons().confirm) cb.current()
      frame = requestAnimationFrame(loop)
    }
    frame = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(frame)
  }, [reader, active])
}

export default function Play() {
  const state = useLocation().state as PlayState | null
  const navigate = useNavigate()
  const [reader, setReader] = useState<InputReader | null>(null)
  const [phase, setPhase] = useState<Phase>({ name: 'calibrate' })
  const [calibration, setCalibration] = useState<Calibration | null>(null)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rating, setRating] = useState<number | null>(null)
  const practice = useMemo(practiceChart, [])
  const main = useMemo(assessmentChart, [])
  const inputKind = state?.input

  useEffect(() => {
    if (!inputKind) return
    const r = inputKind === 'keyboard' ? new KeyboardReader() : new GamepadReader()
    setReader(r)
    if (inputKind === 'keyboard') setCalibration(KEYBOARD_CALIBRATION)
    return () => r.dispose()
  }, [inputKind])

  // Keyboard has nothing to calibrate.
  useEffect(() => {
    if (inputKind === 'keyboard' && phase.name === 'calibrate') setPhase({ name: 'howto' })
  }, [inputKind, phase.name])

  const runCalibration = useCallback(() => {
    if (!reader || checking) return
    setChecking(true)
    setCalibration(null)
    const samples: RawSample[] = []
    const startedAt = performance.now()
    const tick = () => {
      samples.push(...reader.poll())
      if (performance.now() - startedAt < CALIBRATE_MS) {
        requestAnimationFrame(tick)
      } else {
        setCalibration(calibrate(samples))
        setChecking(false)
      }
    }
    requestAnimationFrame(tick)
  }, [reader, checking])

  const startMain = useCallback(() => {
    if (!reader || !calibration || !state) return
    setError(null)
    setPhase({ name: 'main' })
  }, [reader, calibration, state])

  const save = useCallback(
    async (result: GameResult, status: 'completed' | 'abandoned') => {
      if (!reader || !state) return
      setPhase({ name: 'saving', result, status })
      setError(null)
      try {
        const { session_id } = await api.saveGame({
          ...summarizeGame({ status, ...result }),
          protocol_version: PROTOCOL_VERSION,
          input_reader: reader.kind,
          connection: reader.kind === 'keyboard' ? 'simulated' : 'unknown',
          placement: state.placement,
          quality: 'good',
        })
        setPhase(status === 'completed' ? { name: 'done', sessionId: session_id } : { name: 'stopped' })
      } catch (e) {
        setError((e as Error).message)
      }
    },
    [reader, state],
  )

  const confirmAction: Record<string, (() => void) | undefined> = {
    calibrate: calibration?.ok ? () => setPhase({ name: 'howto' }) : runCalibration,
    howto: () => setPhase({ name: 'practice' }),
    ready: startMain,
  }
  useConfirm(reader, phase.name in confirmAction && !checking, () => confirmAction[phase.name]?.())

  if (!state) return <Navigate to="/" replace />
  if (!reader || !calibration && phase.name !== 'calibrate') return <p className="wrap muted page-pad">Loading…</p>

  const simulated = reader.kind === 'keyboard'
  const confirmHint = simulated ? 'or press Enter' : 'or press ✕ on the controller'

  switch (phase.name) {
    case 'calibrate':
      return (
        <Screen title="Quick stick check">
          <p>Let go of both sticks so they rest in the middle. This takes about two seconds.</p>
          {calibration && !calibration.ok && (
            <p className="notice" role="status">
              {calibration.samples === 0
                ? 'Can’t see the controller. Press any button on it, then check again.'
                : 'The sticks didn’t settle in the middle. Make sure nothing is touching them and check again.'}
            </p>
          )}
          {calibration?.ok && (
            <p className="ok" role="status">
              Sticks look good.
            </p>
          )}
          <div className="row">
            {calibration?.ok ? (
              <button className="btn btn-big" onClick={() => setPhase({ name: 'howto' })}>
                Continue
              </button>
            ) : (
              <button className="btn btn-big" onClick={runCalibration} disabled={checking}>
                {checking ? 'Checking…' : calibration ? 'Check again' : 'Check sticks'}
              </button>
            )}
            {calibration && !calibration.ok && (
              <button className="btn btn-quiet" onClick={() => setPhase({ name: 'howto' })}>
                Continue anyway
              </button>
            )}
          </div>
          <p className="hint">{confirmHint}</p>
        </Screen>
      )

    case 'howto':
      return (
        <Screen title="How to play">
          <ol className="howto">
            <li>Arrows rise up the screen. Left-side arrows are for the left stick, right-side arrows for the right stick.</li>
            <li>When an arrow reaches the outlined row at the top, push that stick the way the arrow points.</li>
            <li>Then let the stick go back to the middle, ready for the next one.</li>
          </ol>
          {simulated && (
            <p className="notice">
              Keyboard: <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> is the left stick, the arrow keys are the right
              stick. <kbd>Esc</kbd> pauses.
            </p>
          )}
          <p className="muted">First, six practice arrows. They aren’t scored.</p>
          <div className="row">
            <button className="btn btn-big" onClick={() => setPhase({ name: 'practice' })}>
              Start practice
            </button>
          </div>
          <p className="hint">{confirmHint}</p>
        </Screen>
      )

    case 'practice':
      return (
        <Game
          chart={practice}
          reader={reader}
          calibration={calibration!}
          practice
          onFinish={() => setPhase({ name: 'ready' })}
          onStop={() => navigate('/')}
        />
      )

    case 'ready':
      return (
        <Screen title="Ready for the real round?">
          <p>
            Three parts: left stick, right stick, then both together. It takes about a minute and a half, and you can pause at
            any time.
          </p>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <div className="row">
            <button className="btn btn-big" onClick={startMain}>
              Start
            </button>
            <button className="btn btn-quiet" onClick={() => setPhase({ name: 'practice' })}>
              Practice again
            </button>
          </div>
          <p className="hint">{confirmHint}</p>
        </Screen>
      )

    case 'main':
      return (
        <Game
          chart={main}
          reader={reader}
          calibration={calibration!}
          practice={false}
          onFinish={(r) => save(r, 'completed')}
          onStop={(r) => save(r, 'abandoned')}
        />
      )

    case 'saving':
      return (
        <Screen title={error ? 'Couldn’t save the session' : 'Saving…'}>
          {error ? (
            <>
              <p className="error" role="alert">
                {error}
              </p>
              <div className="row">
                <button className="btn btn-big" onClick={() => save(phase.result, phase.status)}>
                  Try again
                </button>
              </div>
            </>
          ) : (
            <p className="muted">One moment.</p>
          )}
        </Screen>
      )

    case 'done':
      return (
        <Screen title="That’s it for today. Thank you!">
          <p>Your session is saved.</p>
          <fieldset className="rating">
            <legend>How did you find it?</legend>
            <div className="rating-options">
              {['Not for me', 'It was OK', 'Fine', 'Liked it', 'Really enjoyed it'].map((label, i) => (
                <button
                  key={label}
                  className={`rating-option ${rating === i + 1 ? 'on' : ''}`}
                  aria-pressed={rating === i + 1}
                  onClick={() => {
                    setRating(i + 1)
                    api.rateGame(phase.sessionId, i + 1).catch(() => setRating(null))
                  }}
                >
                  <span className="rating-num">{i + 1}</span>
                  {label}
                </button>
              ))}
            </div>
            {rating && <p className="hint">Thanks for telling us.</p>}
          </fieldset>
          <div className="row">
            <Link className="btn btn-big" to="/history">
              See my history
            </Link>
            <Link className="btn btn-quiet" to="/">
              Back to home
            </Link>
          </div>
        </Screen>
      )

    case 'stopped':
      return (
        <Screen title="Session stopped">
          <p>That’s completely fine. What you played is saved and marked as stopped early.</p>
          <div className="row">
            <Link className="btn btn-big" to="/">
              Back to home
            </Link>
            <Link className="btn btn-quiet" to="/history">
              See my history
            </Link>
          </div>
        </Screen>
      )
  }
}

function Screen({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="wrap page-pad">
      <section className="panel screen">
        <h1>{title}</h1>
        {children}
      </section>
    </main>
  )
}
