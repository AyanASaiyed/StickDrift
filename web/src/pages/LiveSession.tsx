import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, type HandLive, type LiveSample, type LiveSnapshot, type LiveStatus } from '../api'
import { DiffBars, PatternBars, ReachTrialsChart, RollingChart, StickFields } from '../components/LiveCharts'
import { handPos, handTarget, levelName, pct, secs } from '../components/liveData'
import { TabPanel, Tabs } from '../components/Tabs'

const KEEP = 100 * 40
const DONE: LiveStatus[] = ['finished', 'failed', 'stopped', 'lost']

const STATUS_TEXT: Record<LiveStatus, string> = {
  starting: 'Opening the game',
  waiting: 'Waiting for the controller',
  ready: 'Between chapters',
  playing: 'Playing',
  paused: 'On a break',
  saving: 'Saving the session',
  scoring: 'Judging with the pattern model',
  finished: 'Session judged',
  failed: 'Could not judge',
  stopped: 'Closed early',
  lost: 'Connection lost',
}

const CHAPTERS = ['apples', 'butterfly_left', 'butterfly_right', 'water']

function elapsed(s: number) {
  const m = Math.floor(s / 60)
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

function Tile({ label, left, right, hint }: { label: string; left: string; right: string; hint?: string }) {
  return (
    <div className="tile">
      <span className="tile-label">{label}</span>
      <span className="tile-vals">
        <span>
          <i style={{ background: 'var(--hand-left)' }} aria-hidden /> <span className="sr-only">Left</span>
          {left}
        </span>
        <span>
          <i style={{ background: 'var(--hand-right)' }} aria-hidden /> <span className="sr-only">Right</span>
          {right}
        </span>
      </span>
      {hint && <span className="tile-hint">{hint}</span>}
    </div>
  )
}

function tiles(h: { left: HandLive; right: HandLive }) {
  const both = (f: (x: HandLive) => string) => [f(h.left), f(h.right)] as const
  const shake = (x: HandLive) => (x.shake == null ? '—' : `${(x.shake * 100).toFixed(1)}%${x.shake_hz ? ` · ${x.shake_hz} Hz` : ''}`)
  const change = (x: HandLive) =>
    x.speed_change_pct == null ? '—' : `${x.speed_change_pct > 0 ? '+' : ''}${x.speed_change_pct.toFixed(0)}%`
  return {
    speed: [
      { label: 'Reaction time', vals: both((x) => secs(x.reaction_s)), hint: 'Apple appears → stick starts moving' },
      { label: 'Time to reach', vals: both((x) => secs(x.reach_s)) },
      { label: 'Peak speed', vals: both((x) => (x.peak_speed == null ? '—' : `${x.peak_speed.toFixed(1)} tilts/s`)) },
      { label: 'Reach size', vals: both((x) => pct(x.reach_size)), hint: 'Furthest point ÷ distance to the apple' },
      { label: 'Speed, first → last apples', vals: both(change), hint: 'Negative = slowing down as it went on' },
      {
        label: 'Apples picked',
        vals: both((x) => (x.apples_total ? `${x.apples_reached}/${x.apples_total}` : '—')),
      },
    ],
    steady: [
      { label: 'Distance from target', vals: both((x) => pct(x.tracking_error)), hint: 'Share of full stick range' },
      { label: 'Time on target', vals: both((x) => pct(x.on_target)) },
      { label: 'Shake', vals: both(shake), hint: 'Leftover wobble after the smooth path · rhythm' },
    ],
  }
}

export default function LiveSession() {
  const { id = '' } = useParams()
  const [snap, setSnap] = useState<LiveSnapshot | null>(null)
  const [samples, setSamples] = useState<LiveSample[]>([])
  const [error, setError] = useState<string | null>(null)
  const since = useRef(0)
  const [chart, setChart] = useState<'distance' | 'tilt'>('distance')
  const [mTab, setMTab] = useState<'speed' | 'steady' | 'diff'>('speed')

  useEffect(() => {
    let stop = false
    let timer = 0
    since.current = 0
    setSamples([])
    const tick = async () => {
      try {
        const s = await api.caregiverLiveSnapshot(id, since.current)
        if (stop) return
        setError(null)
        setSnap(s)
        if (s.samples.length) {
          const fresh = s.samples.filter((x) => x[0] > since.current)
          since.current = s.seq
          setSamples((prev) => [...prev, ...fresh].slice(-KEEP))
        }
        const done = DONE.includes(s.status)
        if (!done || !s.result) timer = window.setTimeout(tick, done ? 3000 : 250)
      } catch (e) {
        if (stop) return
        setError((e as Error).message)
        timer = window.setTimeout(tick, 2000)
      }
    }
    void tick()
    return () => {
      stop = true
      window.clearTimeout(timer)
    }
  }, [id])

  if (!snap) {
    return (
      <main className="wrap page-pad">
        <p className="crumb">
          <Link to="/caregiver">← All residents</Link>
        </p>
        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : (
          <p className="muted">Connecting to the live session…</p>
        )}
      </main>
    )
  }

  const live = !DONE.includes(snap.status) && snap.status !== 'scoring'
  const t = tiles(snap.metrics.hands)
  const reachTrials = snap.metrics.reach_trials

  return (
    <main className="wrap page-pad">
      <p className="crumb">
        <Link to="/caregiver">← All residents</Link> ·{' '}
        <Link to={`/caregiver/residents/${snap.participant_id}`}>{snap.name}’s profile</Link>
      </p>

      <div className="page-head">
        <div>
          <p className="step">{live ? 'Live session' : 'Garden session'}</p>
          <h1>
            {snap.name}{' '}
            <span className={`live-pill live-${snap.status}`}>
              {live && <span className="pulse" aria-hidden />}
              {STATUS_TEXT[snap.status]}
              {snap.status === 'playing' && snap.level ? ` · ${levelName(snap.level)}` : ''}
            </span>
          </h1>
          <p className="muted">
            {elapsed(snap.elapsed_s)} since opening
            {snap.trial != null && snap.level === 'apples' ? ` · apple ${snap.trial}` : ''}
            {snap.synthetic && <span className="badge badge-synthetic">Keyboard / simulated input</span>}
          </p>
        </div>
      </div>

      <ol className="chapter-track" aria-label="Chapters">
        {CHAPTERS.map((c) => {
          const state = snap.levels_done.includes(c) ? 'done' : snap.level === c ? 'now' : 'todo'
          return (
            <li key={c} className={`chapter chapter-${state}`}>
              <span className="chapter-dot" aria-hidden />
              {levelName(c)}
              <span className="sr-only"> ({state === 'done' ? 'finished' : state === 'now' ? 'in progress' : 'not started'})</span>
            </li>
          )
        })}
      </ol>

      {error && (
        <p className="error" role="alert">
          Connection hiccup: {error}
        </p>
      )}

      {(snap.status === 'scoring' || snap.status === 'saving' || snap.result || snap.status === 'failed' || snap.status === 'stopped' || snap.status === 'lost') && (
        <section className={`panel judge ${snap.result ? 'judge-done' : ''}`} aria-live="polite">
          <h2>End-of-session judgement</h2>
          {snap.result ? (
            <>
              <PatternBars scores={snap.result.scores} levels={snap.result.levels} />
              {snap.db_session_id && (
                <p className="muted">
                  Saved to {snap.name}’s record.{' '}
                  <Link to={`/caregiver/residents/${snap.participant_id}`}>Open profile</Link>
                </p>
              )}
            </>
          ) : snap.status === 'scoring' || snap.status === 'saving' ? (
            <p className="muted">
              <span className="pulse" aria-hidden /> The TCN movement pattern model is reviewing the whole session…
            </p>
          ) : null}
          {snap.error && <p className="error">{snap.error}</p>}
        </section>
      )}

      <section className="panel">
        <div className="panel-head">
          <h2>{live ? 'Right now' : 'Last moments'}</h2>
          <Tabs
            variant="pills"
            label="Live chart"
            value={chart}
            onChange={setChart}
            items={[
              { key: 'distance', label: 'Distance from target' },
              { key: 'tilt', label: 'Stick tilt' },
            ]}
          />
        </div>
        <div className="live-grid">
          <StickFields samples={samples} />
          {chart === 'distance' ? (
            <RollingChart
              title="Distance from target"
              caption="How far each stick is from where the game wants it. Lower is closer."
              samples={samples}
              windowS={20}
              max={1}
              format={(v) => `${Math.round(v * 100)}%`}
              value={(s, h) => {
                const tg = handTarget(s, h)
                if (!tg) return null
                const [x, y] = handPos(s, h)
                return Math.hypot(x - tg[0], y - tg[1])
              }}
            />
          ) : (
            <RollingChart
              title="Stick tilt"
              caption="How far each stick is pushed from the middle."
              samples={samples}
              windowS={20}
              max={1}
              format={(v) => `${Math.round(v * 100)}%`}
              value={(s, h) => Math.min(1, Math.hypot(...handPos(s, h)))}
            />
          )}
        </div>
        {samples.length === 0 && (
          <p className="muted">Movement appears here once a chapter starts. Story screens and breaks are not recorded.</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Measurements</h2>
          <Tabs
            variant="pills"
            label="Measurement group"
            value={mTab}
            onChange={setMTab}
            items={[
              { key: 'speed', label: 'Speed and size' },
              { key: 'steady', label: 'Steadiness' },
              { key: 'diff', label: 'Left vs right' },
            ]}
          />
        </div>
        <p className="muted key-line">
          <span className="key-inline"><i style={{ background: 'var(--hand-left)' }} /> Left</span>{' '}
          <span className="key-inline"><i style={{ background: 'var(--hand-right)' }} /> Right</span> · updates as they play
        </p>
        <TabPanel>
          {mTab === 'speed' && (
            <>
              <div className="tile-grid">
                {t.speed.map((x) => (
                  <Tile key={x.label} label={x.label} left={x.vals[0]} right={x.vals[1]} hint={x.hint} />
                ))}
              </div>
              <ReachTrialsChart trials={reachTrials} />
            </>
          )}
          {mTab === 'steady' && (
            <div className="tile-grid">
              {t.steady.map((x) => (
                <Tile key={x.label} label={x.label} left={x.vals[0]} right={x.vals[1]} hint={x.hint} />
              ))}
            </div>
          )}
          {mTab === 'diff' && <DiffBars diff={snap.metrics.left_right_difference_pct} />}
        </TabPanel>
        <p className="hint">
          These describe movement during this session only. Comparing with earlier visits is what shows a real change.
        </p>
      </section>
    </main>
  )
}
