import { useAuth } from '../auth'

export default function Home() {
  const { me } = useAuth()

  return (
    <main className="wrap">
      <section className="hero hero-small">
        <h1>Hi, {me?.display_name}.</h1>
        <p className="lede">Ready for a game today?</p>
      </section>

      <section className="garden-launch" aria-labelledby="garden-heading">
        <div className="garden-art" aria-hidden>
          <svg viewBox="0 0 320 180">
            <rect width="320" height="180" rx="20" className="ga-sky" />
            <circle cx="262" cy="42" r="20" className="ga-sun" />
            <path d="M0 128 Q80 92 160 120 T320 112 V180 H0Z" className="ga-hill" />
            <path d="M0 150 Q100 130 200 148 T320 140 V180 H0Z" className="ga-grass" />
            <rect x="52" y="78" width="14" height="52" rx="4" className="ga-trunk" />
            <circle cx="59" cy="70" r="30" className="ga-tree" />
            <circle cx="48" cy="64" r="5" className="ga-apple" />
            <circle cx="70" cy="76" r="5" className="ga-apple" />
            <g className="ga-bird ga-bird-l">
              <ellipse cx="138" cy="70" rx="14" ry="10" />
              <circle cx="148" cy="64" r="7" />
            </g>
            <g className="ga-bird ga-bird-r">
              <ellipse cx="196" cy="84" rx="14" ry="10" />
              <circle cx="186" cy="78" r="7" />
            </g>
            <circle cx="248" cy="138" r="7" className="ga-flower" />
            <circle cx="270" cy="146" r="6" className="ga-flower" />
          </svg>
        </div>
        <div className="garden-copy">
          <p className="step">Game lobby</p>
          <h2 id="garden-heading">Pick a game</h2>

          <p className="muted">
            Step into the lobby and pick a game: apple picking, harbour fishing or rat catching. It opens in a new tab.
          </p>
          <a className="btn btn-start" href="/lobby.html" target="_blank" rel="noopener noreferrer">
            Open the lobby
          </a>
        </div>
      </section>

      <footer className="foot">
        Stick Drift helps care teams notice changes worth checking. It does not diagnose any condition. If someone has
        a sudden new symptom, follow your usual urgent-care procedure.
      </footer>
    </main>
  )
}
