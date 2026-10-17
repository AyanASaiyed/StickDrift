import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api, type SessionSummary } from '../api'
import { useAuth } from '../auth'
import { SessionTable } from '../components/SessionTable'

export default function History() {
  const { me } = useAuth()
  const [rows, setRows] = useState<SessionSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .mySessions()
      .then(setRows)
      .catch((e: Error) => setError(e.message))
  }, [])

  const completed = rows?.filter((r) => r.status === 'completed').length ?? 0

  return (
    <main className="wrap page-pad">
      <div className="page-head">
        <div>
          <p className="step">History</p>
          <h1>{me?.display_name}’s sessions</h1>
        </div>
        <Link className="btn" to="/">
          Play again
        </Link>
      </div>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : rows === null ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <section className="panel empty-state">
          <h2>No sessions yet</h2>
          <p className="muted">Your results will show up here after your first game.</p>
          <Link className="btn btn-big" to="/">
            Play your first game
          </Link>
        </section>
      ) : (
        <section className="panel">
          <p className="muted">
            {completed} completed {completed === 1 ? 'session' : 'sessions'}. Results are compared only with your own
            earlier sessions.
          </p>
          <SessionTable sessions={rows} />
          <p className="hint">
            “Correct” is how many arrows you matched in each part. “Response” is your usual timing, where it was measured.
          </p>
        </section>
      )}
    </main>
  )
}
