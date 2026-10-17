import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, type ResidentDetail as Detail } from '../api'
import { ReviewCard, SessionTable } from '../components/SessionTable'
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

  return (
    <main className="wrap page-pad">
      <p className="crumb">
        <Link to="/caregiver">← All residents</Link>
      </p>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : data === null ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          <div className="page-head">
            <div>
              <p className="step">Resident</p>
              <h1>{data.display_name}</h1>
              <p className="muted">
                {data.dominant_hand === 'unknown' ? 'Dominant hand not set' : `${data.dominant_hand}-handed`}
                {data.username && <> · username {data.username}</>}
              </p>
            </div>
          </div>

          <section className="panel">
            <ReviewCard review={data.review} name={data.display_name} />
          </section>

          <section className="panel">
            <h2>Trends over time</h2>
            <p className="muted">Each point is one session, oldest on the left. Compared only with this resident’s own history.</p>
            <TrendCharts sessions={data.sessions} />
          </section>

          <section className="panel">
            <h2>Session history</h2>
            <p className="muted">
              {data.sessions.length} {data.sessions.length === 1 ? 'session' : 'sessions'}, newest first. Compared only
              with this resident’s own earlier sessions.
            </p>
            <SessionTable sessions={data.sessions} />
          </section>
        </>
      )}
    </main>
  )
}
