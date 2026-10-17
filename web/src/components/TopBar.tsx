import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useAuth } from '../auth'

function ProfileMenu({ username }: { username: string }) {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
        button.current?.focus()
      }
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="menu" ref={root}>
      <button
        ref={button}
        className="menu-button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="avatar" aria-hidden>
          {username[0].toUpperCase()}
        </span>
        <span className="menu-name">{username}</span>
        <svg viewBox="0 0 12 12" className="caret" aria-hidden>
          <path d="M2 4l4 4 4-4" />
        </svg>
      </button>
      {open && (
        <div className="menu-list" role="menu">
          <Link role="menuitem" className="menu-item" to="/history" onClick={() => setOpen(false)} autoFocus>
            History
          </Link>
          <button
            role="menuitem"
            className="menu-item"
            onClick={async () => {
              setOpen(false)
              // Leave protected pages first, or their login guard redirects to /login.
              navigate('/', { replace: true })
              await logout()
            }}
          >
            Log out
          </button>
        </div>
      )}
    </div>
  )
}

export function TopBar() {
  const { me, loading } = useAuth()
  return (
    <header className="topbar">
      <div className="wrap topbar-inner">
        <Link to="/" className="wordmark">
          <svg viewBox="0 0 32 32" aria-hidden className="mark">
            <circle cx="10" cy="16" r="7" />
            <circle cx="22" cy="16" r="7" />
            <circle cx="12" cy="13" r="2.5" className="mark-dot" />
            <circle cx="24" cy="18" r="2.5" className="mark-dot" />
          </svg>
          Stick Drift
        </Link>
        {!loading &&
          (me ? (
            <ProfileMenu username={me.username} />
          ) : (
            <nav className="row">
              <Link className="btn btn-quiet btn-small" to="/login">
                Log in
              </Link>
              <Link className="btn btn-small" to="/signup">
                Create account
              </Link>
            </nav>
          ))}
      </div>
    </header>
  )
}
