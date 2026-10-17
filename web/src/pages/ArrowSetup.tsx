import { useState } from 'react'
import { useNavigate } from 'react-router'
import type { Placement } from '../api'
import { useAuth } from '../auth'
import { ControllerCheck, type InputSource } from '../components/ControllerCheck'
import type { PlayState } from './Play'

const PLACEMENTS: { value: Placement; label: string }[] = [
  { value: 'hands', label: 'In my hands' },
  { value: 'table', label: 'On a table' },
  { value: 'lap', label: 'On my lap' },
]

export default function ArrowSetup() {
  const { me } = useAuth()
  const navigate = useNavigate()
  const [useSimulator, setUseSimulator] = useState(false)
  const [source, setSource] = useState<InputSource>({ kind: 'none' })
  const [placement, setPlacement] = useState<Placement>('hands')

  const ready = source.kind !== 'none'
  const start = () => {
    const state: PlayState = { input: source.kind === 'simulated' ? 'keyboard' : 'gamepad', placement }
    navigate('/play', { state })
  }

  return (
    <main className="wrap">
      <section className="hero hero-small">
        <h1>Hi, {me?.display_name}.</h1>
        <p className="lede">Ready for today’s game? It takes about three minutes.</p>
      </section>

      <div className="steps">
        <ControllerCheck useSimulator={useSimulator} onUseSimulatorChange={setUseSimulator} onSourceChange={setSource} />

        <section className="panel" aria-labelledby="placement-heading">
          <p className="step">Step 2</p>
          <h2 id="placement-heading">Where is the controller?</h2>
          <p className="muted">Use the same spot each time so sessions compare fairly.</p>
          <div className="segmented segmented-stack" role="radiogroup" aria-labelledby="placement-heading">
            {PLACEMENTS.map((p) => (
              <label key={p.value} className={placement === p.value ? 'on' : ''}>
                <input
                  type="radio"
                  name="placement"
                  value={p.value}
                  checked={placement === p.value}
                  onChange={() => setPlacement(p.value)}
                />
                {p.label}
              </label>
            ))}
          </div>
        </section>
      </div>

      <section className="start" aria-labelledby="start-heading">
        <div>
          <p className="step">Step 3</p>
          <h2 id="start-heading">Start the game</h2>
          <p className="muted">
            {ready ? 'A quick stick check and six practice arrows come first.' : 'To start, connect the controller.'}
          </p>
        </div>
        <button className="btn btn-start" disabled={!ready} onClick={start}>
          Start
        </button>
      </section>

      <footer className="foot">
        Stick Drift shows care teams changes worth checking. It does not diagnose any condition. If someone has a sudden
        new symptom, follow your usual urgent-care procedure.
      </footer>
    </main>
  )
}
