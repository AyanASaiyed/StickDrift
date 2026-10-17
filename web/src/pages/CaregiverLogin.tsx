import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'
import { useAuth } from '../auth'

export default function CaregiverLogin() {
  const { me, loginCaregiver } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (me) return <Navigate to={me.role === 'caregiver' ? '/caregiver' : '/'} replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await loginCaregiver(username, password)
      navigate('/caregiver', { replace: true })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="wrap page-pad">
      <form className="panel auth" onSubmit={submit} noValidate>
        <p className="step">Care team</p>
        <h1>Caregiver login</h1>
        <p className="muted">View residents’ sessions, history and changes worth checking.</p>

        <div className="field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            required
            autoFocus
          />
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <div className="password">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
            <button type="button" className="btn btn-quiet btn-small" onClick={() => setShowPassword((s) => !s)}>
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>
        </div>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="btn btn-big" disabled={busy || !username.trim() || !password}>
          {busy ? 'One moment…' : 'Log in'}
        </button>

        <p className="muted switch">
          Are you a resident? <Link to="/login">Resident login</Link>
        </p>
      </form>
    </main>
  )
}
