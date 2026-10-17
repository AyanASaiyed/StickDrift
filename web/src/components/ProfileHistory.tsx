import type { Participant, SessionRow } from '../api'
import { formatDateTime, formatScore, formatSeconds } from '../format'

interface Props {
  participant: Participant
  sessions: SessionRow[] | null
  error: string | null
}

const STATUS_LABEL: Record<SessionRow['status'], string> = {
  completed: 'Completed',
  in_progress: 'In progress',
  abandoned: 'Stopped early',
}

function QualityBadge({ quality }: { quality: SessionRow['quality'] }) {
  if (!quality) return <span className="badge">Not checked</span>
  const label = { good: 'Good', flagged: 'Flagged', invalid: 'Not usable' }[quality]
  return <span className={`badge badge-${quality}`}>{label}</span>
}

export function ProfileHistory({ participant, sessions, error }: Props) {
  const synthetic = sessions?.some((s) => s.is_synthetic)

  return (
    <section className="panel history" aria-labelledby="history-heading">
      <div className="history-head">
        <div>
          <p className="step">Profile</p>
          <h2 id="history-heading">{participant.alias}: session history</h2>
        </div>
        {synthetic && <span className="badge badge-synthetic">Includes synthetic demo data</span>}
      </div>
      <p className="muted">
        Results are compared only with this person's own earlier sessions. Free play is shown but never counted.
      </p>

      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : sessions === null ? (
        <p className="muted">Loading history…</p>
      ) : sessions.length === 0 ? (
        <p className="empty">No sessions yet. The first few completed sessions set this person's baseline.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Mode</th>
                <th scope="col">Left response</th>
                <th scope="col">Right response</th>
                <th scope="col">Left correct</th>
                <th scope="col">Right correct</th>
                <th scope="col">Both correct</th>
                <th scope="col">Data quality</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.session_id}>
                  <td>
                    {formatDateTime(s.started_at)}
                    {s.status !== 'completed' && <span className="sub">{STATUS_LABEL[s.status]}</span>}
                    {s.is_synthetic && <span className="sub synthetic">Synthetic</span>}
                  </td>
                  <td>{s.mode === 'assessment' ? 'Assessment' : 'Free play'}</td>
                  <td className="num">{formatSeconds(s.left_median_latency_ms)}</td>
                  <td className="num">{formatSeconds(s.right_median_latency_ms)}</td>
                  <td className="num">{formatScore(s.left_correct, s.left_valid)}</td>
                  <td className="num">{formatScore(s.right_correct, s.right_valid)}</td>
                  <td className="num">{formatScore(s.both_correct, s.both_valid)}</td>
                  <td>
                    <QualityBadge quality={s.quality} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint">Response times are medians from cue to movement.</p>
        </div>
      )}
    </section>
  )
}
