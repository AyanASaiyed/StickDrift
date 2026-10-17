import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, type ResidentRow } from '../api'
import { Assistant } from '../components/Assistant'
import { RiskBadge } from '../components/Insights'
import { formatDateTime } from '../format'

function Sparkline({ left, right }: { left: (number | null)[]; right: (number | null)[] }) {
  const vals = [...left, ...right].filter((v): v is number => v != null)
  if (vals.length < 2) return null
  const W = 220
  const H = 48
  const lo = Math.min(...vals)
  const hi = Math.max(...vals)
  const span = Math.max(hi - lo, 1)
  const n = Math.max(left.length, right.length)
  const x = (i: number) => (n <= 1 ? W / 2 : 4 + ((W - 8) * i) / (n - 1))
  const y = (v: number) => 4 + (H - 8) * (1 - (v - lo) / span)
  const path = (pts: (number | null)[]) =>
    pts.reduce((d, v, i) => (v == null ? d : `${d}${d ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)} `), '')
  return (
    <figure className="spark">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="Response time trend, left and right hand"
      >
        <path d={path(left)} className="spark-line" style={{ stroke: 'var(--accent)' }} />
        <path d={path(right)} className="spark-line" style={{ stroke: 'var(--warn)' }} />
      </svg>
      <figcaption>
        <span className="spark-key" style={{ background: 'var(--accent)' }} aria-hidden /> Left
        <span className="spark-key" style={{ background: 'var(--warn)' }} aria-hidden /> Right · response time
      </figcaption>
    </figure>
  )
}

export default function CaregiverDashboard() {
  const [rows, setRows] = useState<ResidentRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .caregiverResidents()
      .then(setRows)
      .catch((e: Error) => setError(e.message))
  }, [])

  const atRisk = rows?.filter((r) => r.risk !== 'none') ?? []

  return (
    <main className="wrap page-pad">
      <div className="page-head">
        <div>
          <p className="step">Care team</p>
          <h1>Residents</h1>
        </div>
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : rows === null ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          {atRisk.length > 0 ? (
            <div className="risk-alert risk-alert-check" role="alert">
              <strong>
                {atRisk.length} {atRisk.length === 1 ? 'resident has' : 'residents have'} a potential health concern
              </strong>
              <p>
                {atRisk.map((r) => `${r.display_name} (${r.concerns.map((c) => c.title).join(', ')})`).join(' · ')}
              </p>
            </div>
          ) : (
            <p className="muted dashboard-summary">
              {rows.length} {rows.length === 1 ? 'resident' : 'residents'} · none with a potential concern right now.
            </p>
          )}

          <div className="resident-grid">
            {rows.map((r) => (
              <Link
                key={r.participant_id}
                to={`/caregiver/residents/${r.participant_id}`}
                className={`resident-card ${r.risk !== 'none' ? `resident-card-flag resident-card-${r.risk}` : ''}`}
              >
                <div className="resident-card-head">
                  <span className="avatar" aria-hidden>
                    {r.display_name[0].toUpperCase()}
                  </span>
                  <div>
                    <span className="resident-name">{r.display_name}</span>
                    <span className="resident-meta">
                      {r.dominant_hand === 'unknown' ? 'hand not set' : `${r.dominant_hand}-handed`} · {r.session_count}{' '}
                      {r.session_count === 1 ? 'session' : 'sessions'}
                    </span>
                  </div>
                  <RiskBadge risk={r.risk} />
                </div>
                <Sparkline left={r.trend_left_ms} right={r.trend_right_ms} />
                {r.risk !== 'none' ? (
                  <div className="resident-flag">
                    <span className="flag-dot" aria-hidden /> {r.concerns.map((c) => c.title).join(' · ')}
                    <ul>
                      {r.review.reasons.slice(0, 2).map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <div className="resident-ok">In line with usual pattern</div>
                )}
                <div className="resident-foot muted">
                  {r.last_played_at ? `Last played ${formatDateTime(r.last_played_at)}` : 'Not played yet'}
                </div>
              </Link>
            ))}
          </div>

          <Assistant
            suggestions={[
              'Who needs a check today?',
              'Summarize everyone’s recent trends.',
              'Which residents are stable?',
            ]}
          />
        </>
      )}
    </main>
  )
}
