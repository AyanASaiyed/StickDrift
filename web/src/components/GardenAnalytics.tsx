import { useCallback, useEffect, useState } from 'react'
import {
  api,
  type GardenRecording,
  type GardenSecond,
} from '../api'
import { formatDateTime } from '../format'

function points(rows: GardenSecond[], side: 'left' | 'right') {
  if (!rows.length) return ''
  const first = new Date(rows[0].bucket).getTime()
  const last = new Date(rows[rows.length - 1].bucket).getTime()
  const span = Math.max(1000, last - first)
  return rows.map((row) => {
    const x = 12 + (new Date(row.bucket).getTime() - first) / span * 776
    const magnitude = side === 'left' ? row.left_magnitude : row.right_magnitude
    const y = 148 - Math.min(1.5, magnitude ?? 0) / 1.5 * 132
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

export function GardenAnalytics() {
  const [recordings, setRecordings] = useState<GardenRecording[] | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [timeline, setTimeline] = useState<GardenSecond[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    setError(null)
    api.gardenRecordings()
      .then((rows) => {
        setRecordings(rows)
        setSelectedId((current) => current && rows.some((row) => row.session_id === current)
          ? current : rows[0]?.session_id ?? '')
      })
      .catch((cause: Error) => setError(cause.message))
  }, [])

  useEffect(refresh, [refresh])

  useEffect(() => {
    if (!selectedId) {
      setTimeline(null)
      return
    }
    let cancelled = false
    setTimeline(null)
    api.gardenTimeline(selectedId)
      .then((rows) => { if (!cancelled) setTimeline(rows) })
      .catch((cause: Error) => { if (!cancelled) setError(cause.message) })
    return () => { cancelled = true }
  }, [selectedId])

  const selected = recordings?.find((row) => row.session_id === selectedId)
  const total = timeline?.reduce((sum, row) => sum + row.sample_count, 0) ?? 0

  return (
    <section className="panel garden-analytics" aria-labelledby="garden-analytics-heading">
      <div className="analytics-head">
        <div>
          <p className="step">TigerData</p>
          <h2 id="garden-analytics-heading">Garden recordings</h2>
        </div>
        <button className="btn btn-secondary" type="button" onClick={refresh}>Refresh</button>
      </div>
      <p className="muted">Recorded controller samples are stored in a TigerData hypertable. This chart reads one-second continuous aggregates. Folder groups are test scenarios, not diagnoses.</p>
      {error && <p className="error" role="alert">{error}</p>}
      {recordings === null ? <p className="muted">Loading recordings…</p>
        : recordings.length === 0 ? <p className="muted">No garden CSV recordings have been imported yet.</p>
          : <>
            <label htmlFor="garden-recording">Recording</label>
            <select id="garden-recording" value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
              {recordings.map((row) => <option key={row.session_id} value={row.session_id}>
                {formatDateTime(row.started_at)} · {row.source_group || 'New recording'}
                {row.is_synthetic ? ' · Synthetic' : ''}
              </option>)}
            </select>
            {selected && <p className="hint">
              {selected.sample_count.toLocaleString()} stored samples · {selected.level_count} levels · {selected.status}
              {selected.is_synthetic ? ' · Synthetic' : ''}
            </p>}
            {timeline === null ? <p className="muted">Loading timeline…</p>
              : timeline.length === 0 ? <p className="muted">The aggregate is refreshing; try again shortly.</p>
                : <>
                  <svg className="garden-chart" viewBox="0 0 800 160" role="img"
                    aria-label="Average left and right stick movement magnitude per second">
                    <line x1="12" y1="148" x2="788" y2="148" className="chart-axis" />
                    <polyline points={points(timeline, 'left')} className="chart-left" />
                    <polyline points={points(timeline, 'right')} className="chart-right" />
                  </svg>
                  <p className="hint"><span className="chart-key chart-key-left" /> Left stick · <span className="chart-key chart-key-right" /> Right stick · {total.toLocaleString()} samples in timeline</p>
                </>}
          </>}
    </section>
  )
}
