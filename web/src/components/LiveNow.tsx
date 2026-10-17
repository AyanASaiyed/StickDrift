import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, type LiveBrief, type LiveStatus, type PatternKey } from '../api'
import { levelName, PATTERN_LABELS } from './liveData'

const ACTIVE: LiveStatus[] = ['starting', 'waiting', 'ready', 'playing', 'paused', 'saving', 'scoring']

const SHORT: Record<LiveStatus, string> = {
  starting: 'Opening the game',
  waiting: 'Waiting for controller',
  ready: 'Between chapters',
  playing: 'Playing',
  paused: 'On a break',
  saving: 'Saving',
  scoring: 'Being judged',
  finished: 'Judged',
  failed: 'Could not judge',
  stopped: 'Closed early',
  lost: 'Connection lost',
}

function topPattern(b: LiveBrief) {
  if (!b.tcn_scores) return null
  const entries = Object.entries(b.tcn_scores).filter(([, v]) => v != null) as [PatternKey, number][]
  if (!entries.length) return null
  const [key, value] = entries.sort((a, z) => z[1] - a[1])[0]
  return { label: PATTERN_LABELS[key], value }
}

/** Live and recently finished garden sessions. With participantId, only that resident's. */
export function LiveNow({ participantId, compact }: { participantId?: string; compact?: boolean }) {
  const [items, setItems] = useState<LiveBrief[] | null>(null)

  useEffect(() => {
    let stop = false
    const poll = () =>
      api
        .caregiverLive()
        .then((rows) => !stop && setItems(rows))
        .catch(() => undefined)
    void poll()
    const id = window.setInterval(poll, 3000)
    return () => {
      stop = true
      window.clearInterval(id)
    }
  }, [])

  if (items === null) return null
  const mine = participantId ? items.filter((b) => b.participant_id === participantId) : items
  const active = mine.filter((b) => ACTIVE.includes(b.status))
  const recent = mine.filter((b) => !ACTIVE.includes(b.status)).slice(0, 3)

  if (compact) {
    if (!active.length) return null
    const b = active[0]
    return (
      <Link className="live-banner" to={`/caregiver/live/${b.live_id}`}>
        <span className="pulse" aria-hidden /> <strong>{b.name} is in the garden right now</strong> ·{' '}
        {SHORT[b.status]}
        {b.level ? ` · ${levelName(b.level)}` : ''} — watch live
      </Link>
    )
  }

  return (
    <section className="panel live-now" aria-label="Live garden sessions">
      <div className="live-now-head">
        <h2>Live now</h2>
        <span className="muted">{active.length ? `${active.length} playing` : 'No one is playing right now'}</span>
      </div>
      {active.length > 0 && (
        <ul className="live-cards">
          {active.map((b) => (
            <li key={b.live_id}>
              <Link className="live-card" to={`/caregiver/live/${b.live_id}`}>
                <span className="pulse" aria-hidden />
                <span>
                  <strong>{b.name}</strong>
                  <span className="muted">
                    {SHORT[b.status]}
                    {b.level ? ` · ${levelName(b.level)}` : ''} · {b.levels_done.length}/4 chapters
                  </span>
                </span>
                <span className="live-card-cta">Watch live →</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {recent.length > 0 && (
        <>
          <h3 className="group-title">Just finished</h3>
          <ul className="live-cards">
            {recent.map((b) => {
              const top = topPattern(b)
              return (
                <li key={b.live_id}>
                  <Link className="live-card live-card-done" to={`/caregiver/live/${b.live_id}`}>
                    <span>
                      <strong>{b.name}</strong>
                      <span className="muted">
                        {SHORT[b.status]}
                        {top ? ` · highest pattern: ${top.label.toLowerCase()} ${Math.round(top.value)}/100` : ''}
                        {b.error && !top ? ` · ${b.error}` : ''}
                      </span>
                    </span>
                    <span className="live-card-cta">Open →</span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </section>
  )
}
