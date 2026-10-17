import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import type { Hand } from '../api'
import { useAuth } from '../auth'

type Who = 'resident' | 'caregiver'
type Mode = 'login' | 'signup'

const COPY = {
  resident: {
    badge: 'Resident',
    login: { title: 'Resident log in', lede: 'Welcome back. Log in to visit Mabel’s garden.', cta: 'Log in' },
    signup: { title: 'Create a resident account', lede: 'Set up your own account to play the garden game.', cta: 'Create my account' },
    path: { login: '/login', signup: '/signup' },
  },
  caregiver: {
    badge: 'Care team',
    login: { title: 'Care team log in', lede: 'See residents’ results, trends and anything worth checking in on.', cta: 'Log in to the care dashboard' },
    signup: { title: 'Register as care team', lede: 'You’ll need the access code from your care team lead.', cta: 'Register' },
    path: { login: '/caregiver/login', signup: '/caregiver/signup' },
  },
} as const

function RoleIcon({ who }: { who: Who }) {
  return who === 'resident' ? (
    <svg viewBox="0 0 24 24" aria-hidden className="role-icon">
      <path d="M12 21v-7" />
      <path d="M12 14c-4 0-6-2.5-6-6 4 0 6 2 6 6Z" />
      <path d="M12 14c4 0 6-2.5 6-6-4 0-6 2-6 6Z" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" aria-hidden className="role-icon">
      <path d="M12 3 4 6v6c0 4.5 3.2 7.8 8 9 4.8-1.2 8-4.5 8-9V6l-8-3Z" />
      <path d="M12 8.5v5M9.5 11h5" />
    </svg>
  )
}

/** "Who are you?" switch shown on every login and signup page, so the two worlds are never confused. */
function RoleSwitch({ who, mode, from }: { who: Who; mode: Mode; from: string }) {
  return (
    <nav className="role-switch" aria-label="Who is signing in?">
      {(['resident', 'caregiver'] as Who[]).map((w) => (
        <Link
          key={w}
          to={COPY[w].path[mode]}
          state={w === 'resident' ? { from } : undefined}
          className={`role-tab role-tab-${w} ${who === w ? 'on' : ''}`}
          aria-current={who === w ? 'page' : undefined}
        >
          <RoleIcon who={w} />
          <span>
            <small>I’m a</small>
            {w === 'resident' ? 'Resident' : 'Care team member'}
          </span>
        </Link>
      ))}
    </nav>
  )
}

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && (
        <p id={`${id}-hint`} className="hint">
          {hint}
        </p>
      )}
    </div>
  )
}

export default function AuthPage({ who, mode }: { who: Who; mode: Mode }) {
  const { me, loginSenior, signupSenior, loginCaregiver, signupCaregiver } = useAuth()
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from ?? (who === 'caregiver' ? '/caregiver' : '/')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [hand, setHand] = useState<Hand>('unknown')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const isSignup = mode === 'signup'
  const text = COPY[who][mode]

  if (me) return <Navigate to={me.role === 'caregiver' ? '/caregiver' : '/'} replace />

  const ready = username.trim() && password && (who === 'resident' || !isSignup || inviteCode.trim())

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (who === 'resident') {
        if (isSignup) await signupSenior(username, password, hand)
        else await loginSenior(username, password)
      } else if (isSignup) await signupCaregiver(username, password, displayName, inviteCode)
      else await loginCaregiver(username, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const swapMode: Mode = isSignup ? 'login' : 'signup'
  const swapLabel =
    who === 'resident'
      ? isSignup
        ? 'I already have an account · Log in'
        : 'I’m new here · Create a resident account'
      : isSignup
        ? 'I already have an account · Log in'
        : 'I’m new to the care team · Register';

  return (
    <main className={`wrap page-pad auth-page auth-${who}`}>
      <RoleSwitch who={who} mode={mode} from={from} />

      <form className="panel auth" onSubmit={submit} noValidate>
        <p className="role-badge">
          <RoleIcon who={who} /> {COPY[who].badge}
        </p>
        <h1>{text.title}</h1>
        <p className="muted">{text.lede}</p>

        {who === 'caregiver' && isSignup && (
          <Field id="display" label="Your name (shown to your team)" hint="Optional. Leave blank to use your username.">
            <input
              id="display"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              autoComplete="name"
              maxLength={40}
              aria-describedby="display-hint"
            />
          </Field>
        )}

        <Field
          id="username"
          label="Username"
          hint={isSignup ? (who === 'resident' ? 'A nickname or code, 3–24 characters. Please don’t use your real name.' : '3–24 characters.') : undefined}
        >
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
        </Field>

        <Field id="password" label="Password" hint={isSignup ? 'At least 8 characters.' : undefined}>
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
        </Field>

        {who === 'caregiver' && isSignup && (
          <Field id="code" label="Care team access code" hint="Ask your care team lead. It keeps residents’ results private.">
            <input
              id="code"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value)}
              autoComplete="off"
              autoCapitalize="characters"
              maxLength={128}
              required
              aria-describedby="code-hint"
            />
          </Field>
        )}

        {who === 'resident' && isSignup && (
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

        <button type="submit" className="btn btn-big btn-role" disabled={busy || !ready}>
          {busy ? 'One moment…' : text.cta}
        </button>

        <div className="auth-swap">
          <Link className="btn btn-outline-role" to={COPY[who].path[swapMode]} state={who === 'resident' ? { from } : undefined}>
            {swapLabel}
          </Link>
        </div>
      </form>
    </main>
  )
}
