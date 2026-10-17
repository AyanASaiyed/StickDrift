const dateFmt = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })
const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

export const formatDate = (iso: string) => dateFmt.format(new Date(iso))
export const formatDateTime = (iso: string) => dateTimeFmt.format(new Date(iso))

export const formatSeconds = (ms: number | null) => (ms === null ? '—' : `${(ms / 1000).toFixed(2)} s`)

export const formatScore = (correct: number | null, valid: number | null) =>
  correct === null || valid === null ? '—' : `${correct}/${valid}`
