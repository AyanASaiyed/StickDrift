import { useCallback, useEffect, useState } from 'react'
import { listParticipants, listSessions, type Participant, type SessionRow } from './api'
import { ControllerCheck, type InputSource } from './components/ControllerCheck'
import { GardenAnalytics } from './components/GardenAnalytics'
import { ProfileHistory } from './components/ProfileHistory'
import { ProfilePicker } from './components/ProfilePicker'

export default function App() {
  const [participants, setParticipants] = useState<Participant[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<SessionRow[] | null>(null)
  const [sessionsError, setSessionsError] = useState<string | null>(null)
  const [useSimulator, setUseSimulator] = useState(false)
  const [source, setSource] = useState<InputSource>({ kind: 'none' })
  const [startNotice, setStartNotice] = useState(false)

  const loadParticipants = useCallback(() => {
    setLoadError(null)
    setParticipants(null)
    listParticipants()
      .then(setParticipants)
      .catch((e: Error) => setLoadError(e.message))
  }, [])

  useEffect(loadParticipants, [loadParticipants])

  useEffect(() => {
    if (!selectedId) return
    let cancelled = false
    setSessions(null)
    setSessionsError(null)
    listSessions(selectedId)
      .then((rows) => !cancelled && setSessions(rows))
      .catch((e: Error) => !cancelled && setSessionsError(e.message))
    return () => {
      cancelled = true
    }
  }, [selectedId])

  const selected = participants?.find((p) => p.participant_id === selectedId) ?? null
  const inputReady = source.kind !== 'none'
  const canStart = inputReady && selected !== null

  const missing = [!inputReady && 'connect the controller', !selected && 'choose a profile'].filter(Boolean)

  return (
    <>
      <header className="topbar">
        <div className="wrap topbar-inner">
          <span className="wordmark">
            <svg viewBox="0 0 32 32" aria-hidden className="mark">
              <circle cx="10" cy="16" r="7" />
              <circle cx="22" cy="16" r="7" />
              <circle cx="12" cy="13" r="2.5" className="mark-dot" />
              <circle cx="24" cy="18" r="2.5" className="mark-dot" />
            </svg>
            Stick Drift
          </span>
        </div>
      </header>

      <main className="wrap">
        <section className="hero">
          <h1>A short game for two thumbs.</h1>
          <p className="lede">
            Follow the arrows with the left stick, the right stick, or both. It takes about three minutes. Missing an
            arrow is fine, and you can pause or stop at any time.
          </p>
        </section>

        <div className="steps">
          <ControllerCheck
            useSimulator={useSimulator}
            onUseSimulatorChange={setUseSimulator}
            onSourceChange={setSource}
          />
          <ProfilePicker
            participants={participants}
            loadError={loadError}
            onRetry={loadParticipants}
            selectedId={selectedId}
            onSelect={(id) => {
              setSelectedId(id)
              setStartNotice(false)
            }}
            onCreated={(p) => {
              setParticipants((prev) => [...(prev ?? []), p].sort((a, b) => a.alias.localeCompare(b.alias)))
              setSelectedId(p.participant_id)
            }}
          />
        </div>

        <section className="start" aria-labelledby="start-heading">
          <div>
            <p className="step">Step 3</p>
            <h2 id="start-heading">{selected ? `Ready when ${selected.alias} is` : 'Start the session'}</h2>
            <p className="muted">
              {canStart
                ? 'A few practice arrows come first. They are not scored.'
                : `To start, ${missing.join(' and ')}.`}
            </p>
            {startNotice && (
              <p className="notice" role="status">
                The assessment screen isn't built yet. This button will open it.
              </p>
            )}
          </div>
          <button className="btn btn-start" disabled={!canStart} onClick={() => setStartNotice(true)}>
            Start
          </button>
        </section>

        {selected && <ProfileHistory participant={selected} sessions={sessions} error={sessionsError} />}

        <GardenAnalytics />

        <footer className="foot">
          Stick Drift shows care teams changes worth checking. It does not diagnose any condition. If someone has a
          sudden new symptom, follow your usual urgent-care procedure.
        </footer>
      </main>
    </>
  )
}
