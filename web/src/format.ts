const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

export const formatDateTime = (iso: string) => dateTimeFmt.format(new Date(iso))

const dateFmt = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })

/** Short "Oct 17" style label for chart axes. */
export const formatDate = (iso: string) => dateFmt.format(new Date(iso))

export const formatScore = (hits: number | null, total: number | null) =>
  hits === null || total === null ? '—' : `${hits}/${total}`

export const formatSeconds = (ms: number | null) => (ms === null ? '—' : `${(ms / 1000).toFixed(2)} s`)

/** Signed timing offset in plain words: "0.12 s late", "0.05 s early", "On time". */
export function formatOffset(ms: number | null): string {
  if (ms === null) return '—'
  if (Math.abs(ms) < 20) return 'On time'
  return `${(Math.abs(ms) / 1000).toFixed(2)} s ${ms > 0 ? 'late' : 'early'}`
}

const shortFmt = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })

/** Axis labels for visits: the date, or date and time when several fall on the same day. */
export function visitLabels(isoTimes: string[]): string[] {
  const dates = isoTimes.map(formatDate)
  return new Set(dates).size === dates.length ? dates : isoTimes.map((t) => shortFmt.format(new Date(t)))
}
