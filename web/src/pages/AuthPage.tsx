import { useEffect, useRef, useState, type CSSProperties, type FormEvent, type InputHTMLAttributes, type ReactNode } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import {
  ArrowRight,
  ArrowUpRight,
  CircleNotch,
  Eye,
  EyeSlash,
  IdentificationBadge,
  Key,
  Lock,
  Plant,
  ShieldCheck,
  User,
  WarningCircle,
} from '@phosphor-icons/react'
import type { Hand } from '../api'
import { useAuth } from '../auth'
import './Auth.css'

type Who = 'resident' | 'caregiver'
type Mode = 'login' | 'signup'

const COPY = {
  resident: {
    login: {
      title: 'Back to the *garden.*',
      stage: 'Log in and pick up where you left off. Three games are waiting.',
      card: 'Resident log in',
      lede: 'Welcome back. Log in to visit Mabel’s garden.',
      cta: 'Log in',
    },
    signup: {
      title: 'Your own corner of the *garden.*',
      stage: 'A nickname is all you need. Please don’t use your real name.',
      card: 'Create a resident account',
      lede: 'Set up your own account to play the games.',
      cta: 'Create my account',
    },
    path: { login: '/login', signup: '/signup' },
  },
  caregiver: {
    login: {
      title: 'See how everyone is *doing.*',
      stage: 'Results, trends and live sessions for the residents you look after, in one place.',
      card: 'Care team log in',
      lede: 'See residents’ results, trends and anything worth checking in on.',
      cta: 'Log in to the care dashboard',
    },
    signup: {
      title: 'Join your care *team.*',
      stage: 'You’ll need the access code from your care team lead.',
      card: 'Register as care team',
      lede: 'The code keeps residents’ results private.',
      cta: 'Register',
    },
    path: { login: '/caregiver/login', signup: '/caregiver/signup' },
  },
} as const

const GAMES = ['Apple Picking', 'Harbour Fishing', 'Rat Catching']
const WHO: Who[] = ['resident', 'caregiver']

/** Headline with the *starred* words in the accent colour; every word rises in on its own beat. */
function Headline({ text }: { text: string }) {
  let n = 0
  return (
    <h1>
      {text.split(/(\*[^*]+\*)/).map((part, i) => {
        const em = part.startsWith('*')
        return part
          .replace(/\*/g, '')
          .split(' ')
          .filter(Boolean)
          .map((w) => {
            const node = (
              <span key={`${i}-${n}`} className="w" style={{ '--w': n } as CSSProperties}>
                {em ? <em>{w}</em> : w}
                {' '}
              </span>
            )
            n += 1
            return node
          })
      })}
    </h1>
  )
}

/** "Who are you?" tabs. The pill slides between the two even though each is its own page, by remembering where it was. */
function RoleToggle({ who, mode, from }: { who: Who; mode: Mode; from: string }) {
  const idx = WHO.indexOf(who)
  const [i, setI] = useState(() => {
    try {
      return Number(sessionStorage.getItem('stickdrift.auth.who') ?? idx)
    } catch {
      return idx
    }
  })
  useEffect(() => {
    const id = requestAnimationFrame(() => setI(idx))
    try {
      sessionStorage.setItem('stickdrift.auth.who', String(idx))
    } catch {
      /* private mode: no slide, no problem */
    }
    return () => cancelAnimationFrame(id)
  }, [idx])
  return (
    <nav className="au-toggle" aria-label="Who is signing in?" data-in style={{ '--i': i, '--d': 1 } as CSSProperties}>
      <span className="au-pill" aria-hidden />
      {WHO.map((w) => (
        <Link
          key={w}
          to={COPY[w].path[mode]}
          state={w === 'resident' ? { from } : undefined}
          className="au-tab"
          aria-current={who === w ? 'page' : undefined}
        >
          {w === 'resident' ? <Plant size={20} weight="light" aria-hidden /> : <ShieldCheck size={20} weight="light" aria-hidden />}
          {w === 'resident' ? 'Resident' : 'Care team'}
        </Link>
      ))}
    </nav>
  )
}

function TextField({
  id,
  label,
  icon,
  hint,
  right,
  ...input
}: {
  id: string
  label: string
  icon: ReactNode
  hint?: string
  right?: ReactNode
} & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="au-field">
      <div className="au-input">
        <input id={id} placeholder=" " aria-describedby={hint ? `${id}-hint` : undefined} {...input} />
        <label htmlFor={id}>{label}</label>
        <span className="ico" aria-hidden>
          {icon}
        </span>
        {right}
      </div>
      {hint && (
        <p id={`${id}-hint`} className="au-hint">
          {hint}
        </p>
      )}
    </div>
  )
}

/** 0-4 from length and variety. A nudge, not a rule: the server only needs 8 characters. */
function strength(pw: string): number {
  if (!pw) return 0
  let s = pw.length >= 8 ? 1 : 0
  if (pw.length >= 12) s += 1
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s += 1
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) s += 1
  return Math.min(4, Math.max(pw.length >= 3 ? 1 : 0, s))
}
const LEVELS = ['', 'Short', 'Okay', 'Good', 'Strong']

/** The card: a nested bezel whose border lights up under the cursor and has a beam running round it. */
function SpotlightCard({ children, onSubmit }: { children: ReactNode; onSubmit: (e: FormEvent) => void }) {
  const ref = useRef<HTMLFormElement>(null)
  return (
    <form
      ref={ref}
      className="au-card"
      onSubmit={onSubmit}
      noValidate
      data-in
      style={{ '--d': 2 } as CSSProperties}
      onPointerMove={(e) => {
        const r = ref.current!.getBoundingClientRect()
        ref.current!.style.setProperty('--mx', `${e.clientX - r.left}px`)
        ref.current!.style.setProperty('--my', `${e.clientY - r.top}px`)
      }}
    >
      <div className="au-core">{children}</div>
    </form>
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
  const frame = useRef<HTMLDivElement>(null)
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
        ? 'I already have an account'
        : 'I’m new here'
      : isSignup
        ? 'I already have an account'
        : 'I’m new to the care team';
  const swapAction = isSignup ? 'Log in' : who === 'resident' ? 'Create a resident account' : 'Register'
  const level = strength(password)

  return (
    <main className={`au ${who === 'caregiver' ? 'au-care' : ''}`}>
      <div className="au-orbs" aria-hidden>
        <i />
        <i />
      </div>

      <div className="au-grid">
        <section
          className="au-stage"
          aria-label="About this page"
          onPointerMove={(e) => {
            const f = frame.current
            if (!f) return
            const r = f.getBoundingClientRect()
            const x = (e.clientX - (r.left + r.width / 2)) / window.innerWidth
            const y = (e.clientY - (r.top + r.height / 2)) / window.innerHeight
            f.style.setProperty('--ry', `${x * 9}deg`)
            f.style.setProperty('--rx', `${-y * 7}deg`)
          }}
          onPointerLeave={() => {
            frame.current?.style.setProperty('--rx', '0deg')
            frame.current?.style.setProperty('--ry', '0deg')
          }}
        >
          <Headline text={text.title} />
          <p className="au-lede" data-in style={{ '--d': 4 } as CSSProperties}>
            {text.stage}
          </p>
          <div ref={frame} className="au-frame" data-in style={{ '--d': 6 } as CSSProperties}>
            <div>
              <img src="/lobby/lobby.jpg" alt="The game lobby: a garden with three glowing game pads and a grandmother walking between them" width={1280} height={720} />
              {(who === 'resident' ? GAMES : ['Live sessions', 'Left and right hand', 'Trends over time']).map((g) => (
                <span key={g} className="tag">
                  <i /> {g}
                </span>
              ))}
            </div>
          </div>
        </section>

        <SpotlightCard onSubmit={submit}>
          <RoleToggle who={who} mode={mode} from={from} />
          <h2 data-in style={{ '--d': 3 } as CSSProperties}>
            {text.card}
          </h2>
          <p className="au-sub">{text.lede}</p>

          {who === 'caregiver' && isSignup && (
            <TextField
              id="display"
              label="Your name (shown to your team)"
              hint="Optional. Leave blank to use your username."
              icon={<IdentificationBadge size={22} weight="light" />}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              autoComplete="name"
              maxLength={40}
            />
          )}

          <TextField
            id="username"
            label="Username"
            hint={isSignup ? (who === 'resident' ? 'A nickname or code, 3–24 characters. Please don’t use your real name.' : '3–24 characters.') : undefined}
            icon={<User size={22} weight="light" />}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            maxLength={24}
            required
            autoFocus
          />

          <div>
            <TextField
              id="password"
              label="Password"
              hint={isSignup ? 'At least 8 characters.' : undefined}
              icon={<Lock size={22} weight="light" />}
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isSignup ? 'new-password' : 'current-password'}
              maxLength={128}
              required
              right={
                <button
                  type="button"
                  className="au-eye"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                >
                  {showPassword ? <EyeSlash size={22} weight="light" /> : <Eye size={22} weight="light" />}
                </button>
              }
            />
            {isSignup && (
              <div className="au-meter" aria-live="polite">
                {[1, 2, 3, 4].map((n) => (
                  <i key={n} className={level >= n ? 'on' : ''} />
                ))}
                <span>{LEVELS[level]}</span>
              </div>
            )}
          </div>

          {who === 'caregiver' && isSignup && (
            <TextField
              id="code"
              label="Care team access code"
              hint="Ask your care team lead. It keeps residents’ results private."
              icon={<Key size={22} weight="light" />}
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value)}
              autoComplete="off"
              autoCapitalize="characters"
              maxLength={128}
              required
            />
          )}

          {who === 'resident' && isSignup && (
            <fieldset className="au-field">
              <legend className="au-legend">Which hand do you usually write with?</legend>
              <div className="au-seg">
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
            <p className="au-error" role="alert" key={error}>
              <WarningCircle size={22} weight="light" aria-hidden />
              {error}
            </p>
          )}

          <button type="submit" className="au-btn" disabled={busy || !ready}>
            {busy ? 'One moment…' : text.cta}
            <span className="arrow" aria-hidden>
              {busy ? <CircleNotch size={22} weight="light" className="spin" /> : <ArrowUpRight size={22} weight="light" />}
            </span>
          </button>

          <Link className="au-swap" to={COPY[who].path[swapMode]} state={who === 'resident' ? { from } : undefined}>
            {swapLabel} · {swapAction}
            <span aria-hidden>
              <ArrowRight size={18} weight="light" />
            </span>
          </Link>
        </SpotlightCard>
      </div>
    </main>
  )
}
