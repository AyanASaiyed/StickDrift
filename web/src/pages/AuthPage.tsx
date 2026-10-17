import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import type { Hand } from '../api'
import { useAuth } from '../auth'

export default function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const { me, loginSenior, signupSenior } = useAuth()
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from ?? '/'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [hand, setHand] = useState<Hand>('unknown')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const isSignup = mode === 'signup'

  if (me) return <Navigate to={me.role === 'caregiver' ? '/caregiver' : from} replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (isSignup) await signupSenior(username, password, hand)
      else await loginSenior(username, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="wrap page-pad">
      <form className="panel auth" onSubmit={submit} noValidate>
        <h1>{isSignup ? 'Create your account' : 'Welcome back'}</h1>

        <div className="field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            maxLength={24}
            required
            autoFocus
            aria-describedby={isSignup ? 'username-hint' : undefined}
          />
          {isSignup && (
            <p id="username-hint" className="hint">
              A nickname or code, 3–24 characters. Please don’t use your real name.
            </p>
          )}
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <div className="password">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isSignup ? 'new-password' : 'current-password'}
              maxLength={128}
              required
              aria-describedby={isSignup ? 'password-hint' : undefined}
            />
            <button type="button" className="btn btn-quiet btn-small" onClick={() => setShowPassword((s) => !s)}>
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>
          {isSignup && (
            <p id="password-hint" className="hint">
              At least 8 characters.
            </p>
          )}
        </div>

        {isSignup && (
          <fieldset className="field">
            <legend>Which hand do you usually write with?</legend>
            <div className="segmented">
              {(['left', 'right', 'unknown'] as Hand[]).map((h) => (
                <label key={h} className={hand === h ? 'on' : ''}>
                  <input type="radio" name="hand" value={h} checked={hand === h} onChange={() => setHand(h)} />
                  {h === 'unknown' ? 'Not sure' : h[0].toUpperCase() + h.slice(1)}
                </label>
              ))}
            </div>
          </fieldset>
        )}

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="btn btn-big" disabled={busy || !username.trim() || !password}>
          {busy ? 'One moment…' : isSignup ? 'Create account' : 'Log in'}
        </button>

        <p className="muted switch">
          {isSignup ? (
            <>
              Already have an account? <Link to="/login" state={{ from }}>Log in</Link>
            </>
          ) : (
            <>
              New here? <Link to="/signup" state={{ from }}>Create an account</Link>
            </>
          )}
        </p>
        <p className="muted switch">
          Are you a care team member? <Link to="/caregiver/login">Caregiver login</Link>
        </p>
      </form>
    </main>
  )
}
