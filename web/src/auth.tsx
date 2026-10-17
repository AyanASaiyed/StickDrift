import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { api, ApiError, type Hand, type Me } from './api'

interface AuthState {
  me: Me | null
  loading: boolean
  error: string | null
  login: (username: string, password: string) => Promise<void>
  signup: (username: string, password: string, hand: Hand) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch((e: ApiError) => {
        if (e.status !== 401) setError(e.message)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    setMe(await api.login(username, password))
    setError(null)
  }, [])

  const signup = useCallback(async (username: string, password: string, hand: Hand) => {
    setMe(await api.signup(username, password, hand))
    setError(null)
  }, [])

  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined)
    setMe(null)
  }, [])

  return (
    <AuthContext.Provider value={{ me, loading, error, login, signup, logout }}>{children}</AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

/** Renders children only when logged in; otherwise sends the user to /login. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth()
  const location = useLocation()
  if (loading) return <p className="wrap muted page-pad">Loading…</p>
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return children
}
