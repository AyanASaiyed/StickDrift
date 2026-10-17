import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, type ResidentDetail as Detail } from '../api'
import { Assistant } from '../components/Assistant'
import { ConcernCard, RiskAlert, RiskBadge } from '../components/Insights'
import { SessionTable } from '../components/SessionTable'
import { TrendCharts } from '../components/TrendCharts'

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
