import { useId } from 'react'
import type { SessionSummary } from '../api'
import { formatDate } from '../format'

interface Series {
  label: string
  color: string
  /** One value per x point; null means no data that session. */
  points: (number | null)[]
}

interface LineChartProps {
  title: string
  caption: string
  xLabels: string[]
  series: Series[]
  /** Format a y value for the axis + tooltip. */
  format: (v: number) => string
  /** Force the y axis to start at zero (accuracy); otherwise it fits the data. */
  zeroBased?: boolean
  /** Optional fixed upper bound (e.g. 100 for percentages). */
  yMax?: number
}

const W = 720
const H = 300
const PAD = { top: 24, right: 20, bottom: 52, left: 56 }

function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) return [min]
  const span = max - min
  const step = span / count
  return Array.from({ length: count + 1 }, (_, i) => min + step * i)
}

function LineChart({ title, caption, xLabels, series, format, zeroBased, yMax }: LineChartProps) {
  const titleId = useId()
  const descId = useId()
  const values = series.flatMap((s) => s.points.filter((p): p is number => p != null))
  const hasData = values.length > 0
  const rawMin = hasData ? Math.min(...values) : 0
  const rawMax = yMax ?? (hasData ? Math.max(...values) : 1)
  const lo = zeroBased ? 0 : Math.min(rawMin, rawMax)
  const hi = Math.max(rawMax, lo + 1)
  // Pad the range a little so points don't sit on the frame.
  const pad = zeroBased ? 0 : (hi - lo) * 0.12
  const yLo = zeroBased ? 0 : lo - pad
  const yHi = yMax ?? hi + pad

  const plotW = W - PAD.left - PAD.right
  const plotH = H - PAD.top - PAD.bottom
  const n = xLabels.length

  const x = (i: number) => PAD.left + (n <= 1 ? plotW / 2 : (plotW * i) / (n - 1))
  const y = (v: number) => PAD.top + plotH * (1 - (v - yLo) / (yHi - yLo))

  const ticks = niceTicks(yLo, yHi)

  // Only label a handful of x points so dates stay readable.
  const labelEvery = Math.max(1, Math.ceil(n / 6))

  return (
    <figure className="chart">
      <figcaption>
        <strong>{title}</strong>
        <span className="muted">{caption}</span>
      </figcaption>
      <div className="chart-legend">
        {series.map((s) => (
          <span key={s.label} className="chart-key">
            <span className="chart-swatch" style={{ background: s.color }} aria-hidden />
            {s.label}
          </span>
        ))}
      </div>
      <svg
        className="chart-svg"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-labelledby={`${titleId} ${descId}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <title id={titleId}>{title}</title>
        <desc id={descId}>{caption}</desc>

        {ticks.map((t, i) => (
          <g key={i}>
            <line className="chart-grid" x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} />
            <text className="chart-axis" x={PAD.left - 10} y={y(t)} textAnchor="end" dominantBaseline="middle">
              {format(t)}
            </text>
          </g>
        ))}

        {xLabels.map((label, i) =>
          i % labelEvery === 0 || i === n - 1 ? (
            <text key={i} className="chart-axis" x={x(i)} y={H - PAD.bottom + 20} textAnchor="middle">
              {label}
            </text>
          ) : null,
        )}

        {series.map((s) => {
          const pts = s.points.map((v, i) => (v == null ? null : ([x(i), y(v)] as const)))
          // Build path segments, breaking on gaps.
          let d = ''
          let pen = false
          for (const p of pts) {
            if (p == null) {
              pen = false
              continue
            }
            d += `${pen ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)} `
            pen = true
          }
          return (
            <g key={s.label}>
              <path className="chart-line" d={d} style={{ stroke: s.color }} />
              {pts.map((p, i) =>
                p == null ? null : (
                  <circle key={i} className="chart-dot" cx={p[0]} cy={p[1]} r={4} style={{ fill: s.color }}>
                    <title>{`${s.label} · ${xLabels[i]}: ${format(s.points[i] as number)}`}</title>
                  </circle>
                ),
              )}
            </g>
          )
        })}
      </svg>
    </figure>
  )
}

/** Caregiver-facing trend charts built from a resident's session history (newest-first). */
export function TrendCharts({ sessions }: { sessions: SessionSummary[] }) {
  // Only completed sessions with usable data, oldest -> newest for the time axis.
  const usable = sessions
    .filter((s) => s.status === 'completed' && s.quality !== 'invalid')
    .slice()
    .reverse()

  if (usable.length < 2) {
    return (
      <p className="muted">
        Charts appear once there are at least two completed sessions to compare. {usable.length === 1 ? '1 so far.' : ''}
      </p>
    )
  }

  const xLabels = usable.map((s) => formatDate(s.started_at))
  const pct = (correct: number | null, valid: number | null) =>
    correct != null && valid ? Math.round((correct / valid) * 100) : null
  const secs = (ms: number | null) => (ms == null ? null : ms / 1000)

  return (
    <div className="chart-stack">
      <LineChart
        title="Response time"
        caption="How quickly each hand reacted when an arrow reached the top. Lower is quicker."
        xLabels={xLabels}
        format={(v) => `${v.toFixed(1)}s`}
        series={[
          { label: 'Left hand', color: 'var(--accent)', points: usable.map((s) => secs(s.left_median_latency_ms)) },
          { label: 'Right hand', color: 'var(--warn)', points: usable.map((s) => secs(s.right_median_latency_ms)) },
        ]}
      />
      <LineChart
        title="Accuracy"
        caption="Share of arrows matched correctly each session. Higher is better."
        xLabels={xLabels}
        zeroBased
        yMax={100}
        format={(v) => `${Math.round(v)}%`}
        series={[
          { label: 'Left hand', color: 'var(--accent)', points: usable.map((s) => pct(s.left_correct, s.left_valid)) },
          { label: 'Right hand', color: 'var(--warn)', points: usable.map((s) => pct(s.right_correct, s.right_valid)) },
          { label: 'Both hands', color: 'var(--synthetic)', points: usable.map((s) => pct(s.both_correct, s.both_valid)) },
        ]}
      />
    </div>
  )
}
