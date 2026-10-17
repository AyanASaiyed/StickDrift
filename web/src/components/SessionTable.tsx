import type { Review, SessionSummary } from '../api'
import { formatDateTime, formatScore, formatSeconds } from '../format'

export function ReviewCard({ review, name }: { review: Review; name: string }) {
  if (!review.flagged) {
    return (
      <div className="review review-ok" role="status">
        <strong>No change worth checking</strong>
        <p className="muted">{name}’s recent sessions are in line with their usual pattern.</p>
      </div>
    )
  }
  return (
    <div className="review review-flag" role="status">
      <strong>Change worth checking</strong>
      <ul>
        {review.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
      <p className="hint">
        This is a prompt to check in, not a diagnosis. A change can come from tiredness, medication, vision or an
        unfamiliar setup.
      </p>
    </div>
  )
}

function Quality({ s }: { s: SessionSummary }) {
  if (s.status === 'abandoned') return <span className="badge">Stopped early</span>
  if (s.quality === 'good') return <span className="badge badge-good">Good</span>
  if (s.quality === 'flagged') return <span className="badge badge-flagged">Check data</span>
  return <span className="badge">Not checked</span>
}

export function SessionTable({ sessions }: { sessions: SessionSummary[] }) {
  if (sessions.length === 0) return <p className="empty">No sessions yet.</p>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">When</th>
            <th scope="col">Left correct</th>
            <th scope="col">Right correct</th>
            <th scope="col">Both correct</th>
            <th scope="col">Left response</th>
            <th scope="col">Right response</th>
            <th scope="col">Enjoyment</th>
            <th scope="col">Data</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.session_id}>
              <td>{formatDateTime(s.started_at)}</td>
              <td className="num">{formatScore(s.left_correct, s.left_valid)}</td>
              <td className="num">{formatScore(s.right_correct, s.right_valid)}</td>
              <td className="num">{formatScore(s.both_correct, s.both_valid)}</td>
              <td className="num">{formatSeconds(s.left_median_latency_ms)}</td>
              <td className="num">{formatSeconds(s.right_median_latency_ms)}</td>
              <td className="num">{s.enjoyment ? `${s.enjoyment}/5` : '—'}</td>
              <td>
                <Quality s={s} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
