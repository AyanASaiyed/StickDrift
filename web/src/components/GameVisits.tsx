import type { GameResult, GameSession, HandLive, LobbyGame, RatReport } from '../api'
import { formatDateTime } from '../format'
import { PatternBars, RatPoints, hasPatternScores } from './LiveCharts'
import { pct, secs } from './liveData'

const GAME_NAMES: Record<LobbyGame, string> = {
  apple: 'Apple Picking',
  fish: 'Harbour Fishing',
  rat: 'Rat Catching',
}
const ORDER: LobbyGame[] = ['apple', 'fish', 'rat']

type Row = { label: string; value: (h: HandLive) => string; hint?: string }

const caught = (h: HandLive) => (h.apples_total ? `${h.apples_reached}/${h.apples_total}` : '—')

const ROWS: Record<LobbyGame, Row[]> = {
  apple: [
    { label: 'Apples picked', value: caught },
    { label: 'Time to pick', value: (h) => secs(h.reach_s), hint: 'From the apple being free to the glove grabbing it' },
    { label: 'Reaction time', value: (h) => secs(h.reaction_s), hint: 'Apple appears → stick pushed toward it' },
    { label: 'Peak speed', value: (h) => (h.peak_speed == null ? '—' : `${h.peak_speed.toFixed(1)} tilts/s`) },
  ],
  fish: [
    { label: 'Distance from lane', value: (h) => pct(h.tracking_error), hint: 'Share of the water; lower is closer' },
    { label: 'Time on lane', value: (h) => pct(h.on_target) },
    { label: 'Shake', value: (h) => (h.shake == null ? '—' : `${(h.shake * 100).toFixed(1)}%`), hint: 'Leftover wobble after the smooth path' },
    { label: 'Shake rhythm', value: (h) => (h.shake_hz ? `${h.shake_hz} Hz` : '—'), hint: 'How many times a second the wobble repeats' },
  ],
  rat: [
    { label: 'Target rats caught', value: caught },
    { label: 'Time to slam', value: (h) => secs(h.reach_s), hint: 'Target rat appears → stick flicked up' },
    { label: 'Reaction time', value: (h) => secs(h.reaction_s) },
  ],
}

function GameCard({ game, result, rat }: { game: LobbyGame; result: GameResult; rat?: RatReport | null }) {
  return (
    <article className="game-card">
      <header>
        <h3>{GAME_NAMES[game]}</h3>
        {result.finished ? (
          <span className="badge badge-good">Played through</span>
        ) : (
          <span className="badge">Left early</span>
        )}
      </header>
      {game === 'rat' && rat && <RatPoints rat={rat} labeled={false} />}
      <table className="game-table">
        <thead>
          <tr>
            <th scope="col">
              <span className="sr-only">Measurement</span>
            </th>
            <th scope="col">
              <i style={{ background: 'var(--hand-left)' }} aria-hidden /> Left
            </th>
            <th scope="col">
              <i style={{ background: 'var(--hand-right)' }} aria-hidden /> Right
            </th>
          </tr>
        </thead>
        <tbody>
          {ROWS[game].map((r) => (
            <tr key={r.label}>
              <th scope="row" title={r.hint}>
                {r.label}
              </th>
              <td className="num">{r.value(result.hands.left)}</td>
              <td className="num">{r.value(result.hands.right)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rat && rat.target_rats ? (
        <p className="game-note">
          {rat.correctness_pct != null && <>Caught {Math.round(rat.correctness_pct)}% of {rat.target_rats} target rats. </>}
          {rat.median_reaction_s != null && <>Median {secs(rat.median_reaction_s)} from the rat’s nose reaching the hand to the slam.</>}
        </p>
      ) : null}
      <p className="hint">{Math.round(result.play_s)} s of play recorded</p>
    </article>
  )
}

/** Short per-visit numbers for the history table: what was played and the headline result of each game. */
function headline(v: GameSession, game: LobbyGame): string {
  const r = v.games[game]
  if (!r) return '—'
  if (game === 'rat' && v.visit?.games?.rat?.score != null) return `${v.visit.games.rat.score} pts`
  const { left: l, right: rt } = r.hands
  if (game === 'fish') {
    const on = [l.on_target, rt.on_target].filter((x): x is number => x != null)
    return on.length ? `${pct(on.reduce((a, b) => a + b, 0) / on.length)} on lane` : 'played'
  }
  const got = (l.apples_reached ?? 0) + (rt.apples_reached ?? 0)
  const total = (l.apples_total ?? 0) + (rt.apples_total ?? 0)
  return total ? `${got}/${total} ${game === 'apple' ? 'picked' : 'caught'}` : 'played'
}

export function GameVisits({ visits }: { visits: GameSession[] }) {
  if (visits.length === 0) {
    return (
      <section className="panel calm">
        <h2>No game visits yet</h2>
        <p className="muted">They appear here when the resident plays in the game lobby and closes it.</p>
      </section>
    )
  }
  const latest = visits[0]
  return (
    <>
      <section className="panel">
        <h2>
          Latest visit <span className="muted section-sub">{formatDateTime(latest.started_at)}</span>
          {latest.is_synthetic && <span className="badge badge-synthetic">Keyboard input</span>}
        </h2>
        <div className="game-grid">
          {ORDER.filter((g) => latest.games[g]).map((g) => (
            <GameCard key={g} game={g} result={latest.games[g]!} rat={g === 'rat' ? latest.visit?.games?.rat : null} />
          ))}
        </div>
        {hasPatternScores(latest.tcn?.scores) && latest.tcn?.scores && (
          <div className="game-patterns">
            <h3>Pattern model</h3>
            <p className="muted">Apple Picking and Harbour Fishing, scored when the resident left the garden.</p>
            <PatternBars scores={latest.tcn.scores} levels={latest.tcn.levels} />
          </div>
        )}
        {!hasPatternScores(latest.tcn?.scores) && latest.tcn?.levels?.some((level) => level.error) && (
          <p className="error">The pattern model could not score Apple Picking and Harbour Fishing for this visit.</p>
        )}
        <p className="hint">
          Lobby games are free play: each visit is shown on its own and does not set a baseline. Hover a measurement
          name for what it means.
        </p>
      </section>

      <section className="panel">
        <h2>All visits</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">When</th>
                {ORDER.map((g) => (
                  <th scope="col" key={g}>
                    {GAME_NAMES[g]}
                  </th>
                ))}
                <th scope="col">Input</th>
              </tr>
            </thead>
            <tbody>
              {visits.map((v) => (
                <tr key={v.session_id}>
                  <td>{formatDateTime(v.started_at)}</td>
                  {ORDER.map((g) => (
                    <td key={g} className={v.games[g] ? '' : 'muted'}>
                      {headline(v, g)}
                    </td>
                  ))}
                  <td>
                    {v.is_synthetic ? (
                      <span className="badge badge-synthetic">Keyboard</span>
                    ) : (
                      <span className="muted">Controller</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
