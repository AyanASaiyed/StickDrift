import { useState, type FormEvent } from 'react'
import { createParticipant, type Hand, type Participant } from '../api'
import { formatDate } from '../format'

interface Props {
  participants: Participant[] | null
  loadError: string | null
  onRetry: () => void
  selectedId: string | null
  onSelect: (id: string) => void
  onCreated: (p: Participant) => void
}

const HAND_LABEL: Record<Hand, string> = { left: 'Left-handed', right: 'Right-handed', unknown: 'Hand not set' }

function NewProfileForm({ onCreated, onCancel }: { onCreated: Props['onCreated']; onCancel: () => void }) {
  const [alias, setAlias] = useState('')
  const [hand, setHand] = useState<Hand>('unknown')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      onCreated(await createParticipant(alias.trim(), hand))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="new-profile" onSubmit={submit}>
      <label htmlFor="alias">Nickname or code</label>
      <input
        id="alias"
        value={alias}
        onChange={(e) => setAlias(e.target.value)}
        maxLength={40}
        required
        autoFocus
        placeholder="e.g. Maple 3"
        aria-describedby="alias-hint"
      />
      <p id="alias-hint" className="hint">
        Don't use a real name.
      </p>

      <fieldset>
        <legend>Usual writing hand</legend>
        <div className="segmented">
          {(['left', 'right', 'unknown'] as Hand[]).map((h) => (
            <label key={h} className={hand === h ? 'on' : ''}>
              <input type="radio" name="hand" value={h} checked={hand === h} onChange={() => setHand(h)} />
              {h === 'unknown' ? 'Not sure' : h[0].toUpperCase() + h.slice(1)}
            </label>
          ))}
        </div>
      </fieldset>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button type="submit" className="btn" disabled={saving || !alias.trim()}>
          {saving ? 'Saving…' : 'Create profile'}
        </button>
        <button type="button" className="btn btn-quiet" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  )
}

export function ProfilePicker({ participants, loadError, onRetry, selectedId, onSelect, onCreated }: Props) {
  const [creating, setCreating] = useState(false)

  return (
    <section className="panel" aria-labelledby="profile-heading">
      <p className="step">Step 2</p>
      <h2 id="profile-heading">Choose who is playing</h2>

      {loadError ? (
        <div className="status status-warn" role="alert">
          <span className="status-light" aria-hidden />
          <div>
            <strong>Profiles couldn't load</strong>
            <p>{loadError}</p>
            <button className="btn btn-quiet" onClick={onRetry}>
              Try again
            </button>
          </div>
        </div>
      ) : participants === null ? (
        <p className="muted">Loading profiles…</p>
      ) : (
        <>
          {participants.length === 0 && !creating && <p className="muted">No profiles yet. Create the first one.</p>}
          <ul className="profiles" role="radiogroup" aria-label="Profiles">
            {participants.map((p) => (
              <li key={p.participant_id}>
                <button
                  role="radio"
                  aria-checked={p.participant_id === selectedId}
                  className="profile"
                  onClick={() => onSelect(p.participant_id)}
                >
                  <span className="profile-name">{p.alias}</span>
                  <span className="profile-meta">
                    {HAND_LABEL[p.dominant_hand]} · {p.session_count}{' '}
                    {p.session_count === 1 ? 'session' : 'sessions'}
                    {p.last_played_at && <> · last played {formatDate(p.last_played_at)}</>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {creating ? (
            <NewProfileForm
              onCreated={(p) => {
                setCreating(false)
                onCreated(p)
              }}
              onCancel={() => setCreating(false)}
            />
          ) : (
            <button className="btn btn-quiet" onClick={() => setCreating(true)}>
              + New profile
            </button>
          )}
        </>
      )}
    </section>
  )
}
