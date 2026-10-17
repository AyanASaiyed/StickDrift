import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, type ResidentRow } from '../api'
import { formatDateTime } from '../format'

export default function CaregiverDashboard() {
  const [rows, setRows] = useState<ResidentRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .caregiverResidents()
      .then(setRows)
      .catch((e: Error) => setError(e.message))
  }, [])

  const flagged = rows?.filter((r) => r.review.flagged).length ?? 0

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
          <p className="muted dashboard-summary">
            {rows.length} {rows.length === 1 ? 'resident' : 'residents'}
            {flagged > 0 ? ` · ${flagged} with a change worth checking` : ' · none flagged right now'}.
          </p>
          <div className="resident-grid">
            {rows.map((r) => (
              <Link
                key={r.participant_id}
                to={`/caregiver/residents/${r.participant_id}`}
                className={`resident-card ${r.review.flagged ? 'resident-card-flag' : ''}`}
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
                </div>
                {r.review.flagged ? (
                  <div className="resident-flag">
                    <span className="flag-dot" aria-hidden /> Change worth checking
                    <ul>
                      {r.review.reasons.map((reason) => (
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
        </>
      )}
    </main>
  )
}
