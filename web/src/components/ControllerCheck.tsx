import { useEffect } from 'react'
import { useGamepad } from '../useGamepad'

export type InputSource = { kind: 'none' } | { kind: 'controller'; id: string } | { kind: 'simulated' }

interface Props {
  useSimulator: boolean
  onUseSimulatorChange: (value: boolean) => void
  onSourceChange: (source: InputSource) => void
}

// Movement counts once the stick passes ~40% of its range (see README).
const THRESHOLD = 0.4

function Stick({ label, x, y, active }: { label: string; x: number; y: number; active: boolean }) {
  const r = 44
  return (
    <figure className="stick">
      <svg viewBox="-60 -60 120 120" role="img" aria-label={`${label} stick position`}>
        <circle r={r + 6} className="stick-well" />
        <circle r={r * THRESHOLD} className="stick-threshold" />
        <line x1={-r} x2={r} className="stick-axis" />
        <line y1={-r} y2={r} className="stick-axis" />
        {active && <circle cx={x * r} cy={y * r} r={10} className="stick-dot" />}
      </svg>
      <figcaption>{label}</figcaption>
    </figure>
  )
}

export function ControllerCheck({ useSimulator, onUseSimulatorChange, onSourceChange }: Props) {
  const pad = useGamepad()

  const sourceKey = useSimulator ? 'simulated' : pad.connected ? `controller:${pad.id}` : 'none'
  useEffect(() => {
    if (useSimulator) onSourceChange({ kind: 'simulated' })
    else if (pad.connected) onSourceChange({ kind: 'controller', id: pad.id })
    else onSourceChange({ kind: 'none' })
    // sourceKey captures every input that changes the reported source.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceKey])

  let status: { tone: 'ok' | 'warn' | 'wait'; title: string; detail: string }
  if (useSimulator) {
    status = {
      tone: 'warn',
      title: 'Keyboard simulator',
      detail: 'Sessions played this way are labeled SIMULATED and never used for trends.',
    }
  } else if (!pad.connected) {
    status = {
      tone: 'wait',
      title: 'Press any button on the controller',
      detail: 'Plug the PS5 controller in with a USB-C data cable, then press a button so the browser can see it.',
    }
  } else if (!pad.standardMapping) {
    status = {
      tone: 'warn',
      title: 'Controller found, layout not recognized',
      detail: `“${pad.id}”. Stick directions may be wrong. Try Chrome, or reconnect over USB.`,
    }
  } else {
    status = {
      tone: 'ok',
      title: pad.isDualSense ? 'PS5 controller connected' : 'Controller connected',
      detail: 'Move each stick and check the dot follows it.',
    }
  }

  const sticksLive = pad.connected && !useSimulator

  return (
    <section className="panel" aria-labelledby="controller-heading">
      <p className="step">Step 1</p>
      <h2 id="controller-heading">Connect the controller</h2>

      <div className={`status status-${status.tone}`} role="status">
        <span className="status-light" aria-hidden />
        <div>
          <strong>{status.title}</strong>
          <p>{status.detail}</p>
        </div>
      </div>

      <div className={`sticks ${sticksLive ? '' : 'sticks-idle'}`}>
        <Stick label="Left" x={pad.lx} y={pad.ly} active={sticksLive} />
        <Stick label="Right" x={pad.rx} y={pad.ry} active={sticksLive} />
      </div>

      <label className="check">
        <input
          type="checkbox"
          checked={useSimulator}
          onChange={(e) => onUseSimulatorChange(e.target.checked)}
        />
        No controller? Use the keyboard instead (marked as simulated)
      </label>
    </section>
  )
}
