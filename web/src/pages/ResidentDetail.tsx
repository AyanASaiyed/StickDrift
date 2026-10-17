import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, type GardenSession, type ResidentDetail as Detail } from '../api'
import { Assistant } from '../components/Assistant'
import { ConcernCard, RiskAlert, RiskBadge } from '../components/Insights'
import { PatternBars } from '../components/LiveCharts'
import { PATTERN_LABELS, pct, secs } from '../components/liveData'
import { LiveNow } from '../components/LiveNow'
import { SessionTable } from '../components/SessionTable'
import { TrendCharts } from '../components/TrendCharts'
import { formatDateTime } from '../format'

export default function ResidentDetail() {
  const { id = '' } = useParams()
  const [data, setData] = useState<Detail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setData(null)
    setError(null)
    api
      .caregiverResident(id)
      .then(setData)
      .catch((e: Error) => setError(e.message))
  }, [id])

  if (error) {
    return (
      <main className="wrap page-pad">
        <p className="crumb">
          <Link to="/caregiver">← All residents</Link>
        </p>
        <p className="error" role="alert">
          {error}
        </p>
      </main>
    )
  }
  if (data === null) {
    return (
      <main className="wrap page-pad">
        <p className="muted">Loading…</p>
      </main>
    )
  }

  const { insights } = data

  return (
    <main className="wrap page-pad">
      <p className="crumb">
        <Link to="/caregiver">← All residents</Link>
      </p>

      <div className="page-head">
        <div>
          <p className="step">Resident</p>
          <h1>
            {data.display_name} <RiskBadge risk={insights.risk} />
          </h1>
          <p className="muted">
            {data.dominant_hand === 'unknown' ? 'Dominant hand not set' : `${data.dominant_hand}-handed`}
            {data.username && <> · username {data.username}</>} · {data.sessions.length} sessions
            {insights.synthetic && <span className="badge badge-synthetic">Includes simulated data</span>}
          </p>
        </div>
      </div>

      <LiveNow participantId={data.participant_id} compact />

      <RiskAlert name={data.display_name} insights={insights} />

      {insights.concerns.length > 0 && (
        <section className="panel" id="concerns">
          <h2>Potential health concerns</h2>
          <p className="muted">{insights.disclaimer}</p>
          <div className="concern-list">
            {insights.concerns.map((c) => (
              <ConcernCard key={c.id} concern={c} />
            ))}
          </div>
        </section>
      )}

      <GardenVisits visits={data.garden_sessions} />

      <section className="panel">
        <h2>Trends over time</h2>
        <p className="muted">
          Each point is one session, oldest on the left. The dashed line is their usual level (median of{' '}
          {insights.baseline_sessions || 'their earlier'} sessions); ringed points moved enough to count as a change.
        </p>
        <TrendCharts sessions={data.sessions} insights={insights} />
      </section>

      <Assistant
        participantId={data.participant_id}
        name={data.display_name}
        suggestions={[
          `Why was ${data.display_name} flagged?`,
          'How has the left hand changed over time?',
          'What should I check first?',
          'Is this resident improving or getting worse?',
        ]}
      />

      <section className="panel">
        <h2>Session history</h2>
        <p className="muted">
          {data.sessions.length} {data.sessions.length === 1 ? 'session' : 'sessions'}, newest first.
        </p>
        <SessionTable sessions={data.sessions} />
      </section>
    </main>
  )
}

function GardenVisits({ visits }: { visits: GardenSession[] }) {
  const judged = visits.filter((v) => v.tcn?.scores)
  const latest = judged[0]
  return (
    <section className="panel">
      <h2>Garden visits</h2>
      {visits.length === 0 ? (
        <p className="muted">No garden visits yet. They appear here when the resident opens the garden from the site.</p>
      ) : (
        <>
          {latest?.tcn && (
            <>
              <h3 className="group-title">
                Latest judgement · {formatDateTime(latest.started_at)}
                {latest.is_synthetic && <span className="badge badge-synthetic">Simulated input</span>}
              </h3>
              <PatternBars scores={latest.tcn.scores} levels={latest.tcn.levels} />
              {latest.live && (
                <div className="tile-grid tile-grid-compact">
                  {(
                    [
                      ['Reaction time', (h: 'left' | 'right') => secs(latest.live!.hands[h].reaction_s)],
                      ['Time to reach', (h: 'left' | 'right') => secs(latest.live!.hands[h].reach_s)],
                      ['Distance from target', (h: 'left' | 'right') => pct(latest.live!.hands[h].tracking_error)],
                      ['Time on target', (h: 'left' | 'right') => pct(latest.live!.hands[h].on_target)],
                    ] as const
                  ).map(([label, f]) => (
                    <div className="tile" key={label}>
                      <span className="tile-label">{label}</span>
                      <span className="tile-vals">
                        <span>
                          <i style={{ background: 'var(--hand-left)' }} aria-hidden /> {f('left')}
                        </span>
                        <span>
                          <i style={{ background: 'var(--hand-right)' }} aria-hidden /> {f('right')}
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Chapters</th>
                  {Object.values(PATTERN_LABELS).map((l) => (
                    <th scope="col" key={l}>
                      {l}
                    </th>
                  ))}
                  <th scope="col">Data</th>
                </tr>
              </thead>
              <tbody>
                {visits.map((v) => (
                  <tr key={v.session_id}>
                    <td>{formatDateTime(v.started_at)}</td>
                    <td className="num">{v.levels_completed ?? '—'}/4</td>
                    {(['parkinson', 'stroke', 'essential_tremor'] as const).map((k) => {
                      const val = v.tcn?.scores?.[k]
                      return (
                        <td key={k} className={`num ${val != null && val >= 70 ? 'delta-bad' : ''}`}>
                          {val == null ? '—' : Math.round(val)}
                        </td>
                      )
                    })}
                    <td>
                      {v.status === 'completed' ? (
                        <span className="badge badge-good">Finished</span>
                      ) : (
                        <span className="badge">Stopped early</span>
                      )}
                      {v.is_synthetic && <span className="badge badge-synthetic">Simulated</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="hint">Pattern scores are 0–100 resemblance from the TCN model, not a diagnosis.</p>
        </>
      )}
    </section>
  )
}
