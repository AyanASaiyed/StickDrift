import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, type Finding, type GardenSession, type Insights, type ResidentDetail as Detail } from '../api'
import { Assistant } from '../components/Assistant'
import { GameVisits } from '../components/GameVisits'
import { ConcernCard, RiskAlert, RiskBadge } from '../components/Insights'
import { PatternBars } from '../components/LiveCharts'
import { PATTERN_LABELS, PATTERN_ORDER, pct, secs } from '../components/liveData'
import { LiveNow } from '../components/LiveNow'
import { SessionTable } from '../components/SessionTable'
import { TabPanel, Tabs } from '../components/Tabs'
import { GameTrendCharts, GardenTrendCharts, TrendCharts } from '../components/TrendCharts'
import { formatDateTime } from '../format'

type TabKey = 'overview' | 'trends' | 'games' | 'garden' | 'ask' | 'history'

export default function ResidentDetail() {
  const { id = '' } = useParams()
  const [data, setData] = useState<Detail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<TabKey>('overview')

  useEffect(() => {
    setData(null)
    setError(null)
    setTab('overview')
    api
      .caregiverResident(id)
      .then(setData)
      .catch((e: Error) => setError(e.message))
  }, [id])

  if (error) {
    return (
      <main className="wrap page-pad">
        <p className="crumb">
          <Link to="/caregiver">← All residents</Link>
        </p>
        <p className="error" role="alert">
          {error}
        </p>
      </main>
    )
  }
  if (data === null) {
    return (
      <main className="wrap page-pad">
        <p className="muted">Loading…</p>
      </main>
    )
  }

  const { insights } = data

  return (
    <main className="wrap page-pad">
      <p className="crumb">
        <Link to="/caregiver">← All residents</Link>
      </p>

      <header className="resident-head">
        <span className="avatar avatar-lg" aria-hidden>
          {data.display_name[0].toUpperCase()}
        </span>
        <div>
          <h1>
            {data.display_name} <RiskBadge risk={insights.risk} />
          </h1>
          <p className="muted">
            {data.dominant_hand === 'unknown' ? 'Dominant hand not set' : `${data.dominant_hand}-handed`} ·{' '}
            {data.sessions.length + data.garden_sessions.length + data.game_sessions.length} sessions
            {insights.synthetic && <span className="badge badge-synthetic">Includes simulated data</span>}
          </p>
        </div>
      </header>

      <LiveNow participantId={data.participant_id} compact />
      <RiskAlert name={data.display_name} insights={insights} onSeeDetails={() => setTab('overview')} />

      <Tabs<TabKey>
        label="Resident sections"
        value={tab}
        onChange={setTab}
        items={[
          { key: 'overview', label: 'Overview' },
          { key: 'trends', label: 'Trends' },
          { key: 'games', label: 'Game visits', badge: data.game_sessions.length || null },
          ...(data.garden_sessions.length > 0
            ? [{ key: 'garden' as const, label: 'Garden visits', badge: data.garden_sessions.length }]
            : []),
          { key: 'ask', label: 'Ask the assistant' },
          ...(data.sessions.length > 0
            ? [{ key: 'history' as const, label: 'Earlier sessions', badge: data.sessions.length }]
            : []),
        ]}
      />

      <TabPanel>
        {tab === 'overview' && <Overview data={data} insights={insights} />}
        {tab === 'trends' && <Trends data={data} insights={insights} />}
        {tab === 'games' && <GameVisits visits={data.game_sessions} />}
        {tab === 'garden' && <GardenVisits visits={data.garden_sessions} />}
        {tab === 'ask' && (
          <Assistant
            participantId={data.participant_id}
            name={data.display_name}
            suggestions={[
              `Why was ${data.display_name} flagged?`,
              'How has the left hand changed over time?',
              'What should I check first?',
              'Is this resident improving or getting worse?',
            ]}
          />
        )}
        {tab === 'history' && (
          <section className="panel">
            <h2>Earlier sessions</h2>
            <p className="muted panel-lede">Sessions recorded before the garden game, kept for comparison.</p>
            <SessionTable sessions={data.sessions} />
          </section>
        )}
      </TabPanel>
    </main>
  )
}

function glance(f: Finding | undefined) {
  if (!f) return { value: '—', delta: '', bad: false }
  return { value: f.latest_text, delta: `usual ${f.baseline_text}`, bad: f.flagged }
}

function Overview({ data, insights }: { data: Detail; insights: Insights }) {
  const by = new Map(insights.findings.map((f) => [f.key, f]))
  const rows: { label: string; l?: Finding; r?: Finding }[] = [
    { label: 'Response time', l: by.get('left_latency'), r: by.get('right_latency') },
    { label: 'Accuracy', l: by.get('left_accuracy'), r: by.get('right_accuracy') },
  ]
  const latestGarden = data.garden_sessions[0]

  return (
    <>
      {insights.status === 'ok' && (
        <section className="glance" aria-label="Latest session compared with usual">
          {rows.map((row) => (
            <div className="glance-card" key={row.label}>
              <h3>{row.label}</h3>
              {(['l', 'r'] as const).map((k) => {
                const g = glance(row[k])
                return (
                  <p key={k} className={g.bad ? 'is-flagged' : ''}>
                    <i style={{ background: `var(--hand-${k === 'l' ? 'left' : 'right'})` }} aria-hidden />
                    <span className="sr-only">{k === 'l' ? 'Left' : 'Right'}</span>
                    <strong>{g.value}</strong>
                    <span className="muted">{g.delta}</span>
                  </p>
                )
              })}
            </div>
          ))}
          <div className="glance-card">
            <h3>Last garden visit</h3>
            {latestGarden ? (
              <>
                <p>
                  <strong>{formatDateTime(latestGarden.started_at)}</strong>
                </p>
                <p className="muted">{latestGarden.levels_completed ?? 0}/4 chapters finished</p>
              </>
            ) : (
              <p className="muted">None yet</p>
            )}
          </div>
        </section>
      )}

      {insights.concerns.length > 0 ? (
        <section id="concerns" aria-label="Potential health concerns">
          <p className="muted section-note">{insights.disclaimer}</p>
          <div className="concern-list">
            {insights.concerns.map((c) => (
              <ConcernCard key={c.id} concern={c} />
            ))}
          </div>
        </section>
      ) : (
        <section className="panel calm">
          <h2>All in line</h2>
          <p className="muted">
            Nothing has moved enough from {data.display_name}’s usual pattern to flag. Look at Trends to see how each
            measurement has moved over time.
          </p>
        </section>
      )}
    </>
  )
}

function GardenVisits({ visits }: { visits: GardenSession[] }) {
  const latest = visits.find((v) => v.tcn?.scores)
  if (visits.length === 0) {
    return (
      <section className="panel calm">
        <h2>No garden visits yet</h2>
        <p className="muted">They appear here when the resident opens the garden from the site.</p>
      </section>
    )
  }
  return (
    <>
      {latest?.tcn && (
        <section className="panel">
          <h2>
            Latest judgement <span className="muted section-sub">{formatDateTime(latest.started_at)}</span>
            {latest.is_synthetic && <span className="badge badge-synthetic">Simulated input</span>}
          </h2>
          <PatternBars scores={latest.tcn.scores} levels={latest.tcn.levels} />
          {latest.live && (
            <div className="tile-grid tile-grid-compact">
              {(
                [
                  ['Reaction time', (h: 'left' | 'right') => secs(latest.live!.hands[h].reaction_s)],
                  ['Time to reach', (h: 'left' | 'right') => secs(latest.live!.hands[h].reach_s)],
                  ['Distance from target', (h: 'left' | 'right') => pct(latest.live!.hands[h].tracking_error)],
                  ['Time on target', (h: 'left' | 'right') => pct(latest.live!.hands[h].on_target)],
                ] as const
              ).map(([label, f]) => (
                <div className="tile" key={label}>
                  <span className="tile-label">{label}</span>
                  <span className="tile-vals">
                    <span>
                      <i style={{ background: 'var(--hand-left)' }} aria-hidden /> {f('left')}
                    </span>
                    <span>
                      <i style={{ background: 'var(--hand-right)' }} aria-hidden /> {f('right')}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
      <section className="panel">
        <h2>All visits</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Chapters</th>
                {Object.values(PATTERN_LABELS).map((l) => (
                  <th scope="col" key={l}>
                    {l}
                  </th>
                ))}
                <th scope="col">Data</th>
              </tr>
            </thead>
            <tbody>
              {visits.map((v) => (
                <tr key={v.session_id}>
                  <td>{formatDateTime(v.started_at)}</td>
                  <td className="num">{v.levels_completed ?? '—'}/4</td>
                  {PATTERN_ORDER.map((k) => {
                    const val = v.tcn?.scores?.[k]
                    return (
                      <td key={k} className={`num ${val != null && val >= 70 ? 'delta-bad' : ''}`}>
                        {val == null ? '—' : Math.round(val)}
                      </td>
                    )
                  })}
                  <td>
                    {v.status === 'completed' ? (
                      <span className="badge badge-good">Finished</span>
                    ) : (
                      <span className="badge">Stopped early</span>
                    )}
                    {v.is_synthetic && <span className="badge badge-synthetic">Simulated</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="hint">Pattern scores are 0–100 resemblance from the TCN model, not a diagnosis.</p>
      </section>
    </>
  )
}

type TrendMode = 'games' | 'garden' | 'earlier'

function Trends({ data, insights }: { data: Detail; insights: Insights }) {
  const modes = [
    { key: 'games' as const, label: 'Game visits', badge: data.game_sessions.length },
    { key: 'garden' as const, label: 'Garden visits', badge: data.garden_sessions.length },
    { key: 'earlier' as const, label: 'Earlier sessions', badge: data.sessions.length },
  ].filter((m) => m.badge > 0)
  const [mode, setMode] = useState<TrendMode>(modes[0]?.key ?? 'earlier')

  return (
    <section className="panel">
      {modes.length > 1 && <Tabs variant="pills" label="Which game" value={mode} onChange={setMode} items={modes} />}
      {mode === 'games' ? (
        <>
          <p className="muted panel-lede">Each point is one visit to the game lobby, oldest on the left.</p>
          <GameTrendCharts visits={data.game_sessions} />
        </>
      ) : mode === 'garden' ? (
        <>
          <p className="muted panel-lede">Each point is one garden visit, oldest on the left.</p>
          <GardenTrendCharts visits={data.garden_sessions} />
        </>
      ) : (
        <>
          <p className="muted panel-lede">
            Each point is one session. The dashed line is their usual level; a red ring marks a reading that moved
            enough to count as a change.
          </p>
          <TrendCharts sessions={data.sessions} insights={insights} />
        </>
      )}
    </section>
  )
}
