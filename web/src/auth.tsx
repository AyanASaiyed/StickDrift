import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { api, ApiError, type Hand, type Me, type Role } from './api'

interface AuthState {
  me: Me | null
  loading: boolean
  loginSenior: (username: string, password: string) => Promise<void>
  signupSenior: (username: string, password: string, hand: Hand) => Promise<void>
  loginCaregiver: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch((e: ApiError) => {
        if (e.status !== 401) console.error(e)
      })
      .finally(() => setLoading(false))
  }, [])

  const loginSenior = useCallback(async (u: string, p: string) => setMe(await api.loginSenior(u, p)), [])
  const signupSenior = useCallback(
    async (u: string, p: string, h: Hand) => setMe(await api.signupSenior(u, p, h)),
    [],
  )
  const loginCaregiver = useCallback(async (u: string, p: string) => setMe(await api.loginCaregiver(u, p)), [])
  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined)
    setMe(null)
  }, [])

  return (
    <AuthContext.Provider value={{ me, loading, loginSenior, signupSenior, loginCaregiver, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}

/** Gate a route on being logged in with the required role. */
export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { me, loading } = useAuth()
  const location = useLocation()
  if (loading) return <p className="wrap page-pad muted">Loading…</p>
  if (!me) {
    const to = role === 'caregiver' ? '/caregiver/login' : '/login'
    return <Navigate to={to} replace state={{ from: location.pathname }} />
  }
  if (me.role !== role) {
    // Logged in as the other role: send them to their own home.
    return <Navigate to={me.role === 'caregiver' ? '/caregiver' : '/'} replace />
  }
  return children
}
