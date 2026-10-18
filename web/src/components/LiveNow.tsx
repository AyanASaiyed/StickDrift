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
  ended: 'Finished',
}

/** Garden sessions have 4 chapters; the lobby lists 'lobby' plus its games. */
const chapterCount = (levels: string[]) => levels.filter((l) => l !== 'lobby').length || 4

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
        <span className="pulse" aria-hidden /> <strong>{b.name} is playing right now</strong> ·{' '}
        {SHORT[b.status]}
        {b.level ? ` · ${levelName(b.level)}` : ''} — watch live
      </Link>
    )
  }

  if (!active.length && !recent.length) {
    return (
      <p className="live-idle">
        <span className="live-idle-dot" aria-hidden /> No one is playing right now.
      </p>
    )
  }

  return (
    <section className="live-now" aria-label="Live garden sessions">
      {active.map((b) => (
        <Link key={b.live_id} className="live-card" to={`/caregiver/live/${b.live_id}`}>
          <span className="pulse" aria-hidden />
          <span className="live-card-text">
            <strong>{b.name} is playing</strong>
            <span className="muted">
              {SHORT[b.status]}
              {b.level ? ` · ${levelName(b.level)}` : ''} · {b.levels_done.length} of {chapterCount(b.levels)} {b.levels.includes('lobby') ? 'games' : 'chapters'}
            </span>
          </span>
          <span className="live-card-cta">Watch live →</span>
        </Link>
      ))}
      {recent.length > 0 && (
        <ul className="live-recent" aria-label="Just finished">
          {recent.slice(0, 2).map((b) => {
            const top = topPattern(b)
            return (
              <li key={b.live_id}>
                <Link to={`/caregiver/live/${b.live_id}`}>
                  <strong>{b.name}</strong> · {SHORT[b.status].toLowerCase()}
                  {b.rat?.score != null ? ` · Rat Catching ${b.rat.score} pts` : ''}
                  {top ? ` · ${top.label.toLowerCase()} ${Math.round(top.value)}/100` : ''}
                  <span className="live-card-cta"> Open →</span>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
