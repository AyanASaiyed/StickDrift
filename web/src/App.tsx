import { Link, Navigate, Route, Routes } from 'react-router'
import { AuthProvider, RequireRole, useAuth } from './auth'
import { TopBar } from './components/TopBar'
import AuthPage from './pages/AuthPage'
import CaregiverDashboard from './pages/CaregiverDashboard'
import Home from './pages/Home'
import LiveSession from './pages/LiveSession'
import ResidentDetail from './pages/ResidentDetail'

function Welcome() {
  return (
    <main className="wrap">
      <section className="hero">
        <h1>A visit to Mabel’s garden.</h1>
        <p className="lede">
          Help Mabel get ready for a picnic with your PS5 controller: guide two little birds to apples, follow a
          butterfly, and water the moonflowers. It takes a few minutes, and you can rest any time.
        </p>
      </section>

      <section className="who" aria-label="Choose how to continue">
        <div className="who-card who-resident">
          <p className="role-badge">
            <svg viewBox="0 0 24 24" aria-hidden className="role-icon">
              <path d="M12 21v-7" />
              <path d="M12 14c-4 0-6-2.5-6-6 4 0 6 2 6 6Z" />
              <path d="M12 14c4 0 6-2.5 6-6-4 0-6 2-6 6Z" />
            </svg>
            Resident
          </p>
          <h2>I’m here to play</h2>
          <p className="muted">Open the garden game and take a short visit.</p>
          <div className="who-actions">
            <Link className="btn btn-big btn-role" to="/login">
              Resident log in
            </Link>
            <Link className="btn btn-outline-role" to="/signup">
              New here? Create an account
            </Link>
          </div>
        </div>
        <div className="who-card who-caregiver">
          <p className="role-badge">
            <svg viewBox="0 0 24 24" aria-hidden className="role-icon">
              <path d="M12 3 4 6v6c0 4.5 3.2 7.8 8 9 4.8-1.2 8-4.5 8-9V6l-8-3Z" />
              <path d="M12 8.5v5M9.5 11h5" />
            </svg>
            Care team
          </p>
          <h2>I’m on the care team</h2>
          <p className="muted">See residents’ results, trends and anything worth checking in on.</p>
          <div className="who-actions">
            <Link className="btn btn-big btn-role" to="/caregiver/login">
              Care team log in
            </Link>
            <Link className="btn btn-outline-role" to="/caregiver/signup">
              New to the team? Register
            </Link>
          </div>
        </div>
      </section>

      <section className="features" aria-label="How it works">
        <div className="panel">
          <h2>Two sticks, two birds</h2>
          <p className="muted">The left stick flies Pip, the right stick flies Poppy.</p>
        </div>
        <div className="panel">
          <h2>The same garden every visit</h2>
          <p className="muted">Nothing speeds up or changes, so each visit can be compared fairly with the last.</p>
        </div>
        <div className="panel">
          <h2>Your care team can help</h2>
          <p className="muted">Your care team sees how each visit went and anything worth checking in on.</p>
        </div>
      </section>
    </main>
  )
}

function Root() {
  const { me, loading } = useAuth()
  if (loading) return <p className="wrap page-pad muted">Loading…</p>
  if (me?.role === 'caregiver') return <Navigate to="/caregiver" replace />
  if (me?.role === 'senior') return <Home />
  return <Welcome />
}

export default function App() {
  return (
    <AuthProvider>
      <TopBar />
      <Routes>
        <Route path="/" element={<Root />} />
        <Route path="/login" element={<AuthPage who="resident" mode="login" key="r-login" />} />
        <Route path="/signup" element={<AuthPage who="resident" mode="signup" key="r-signup" />} />
        <Route path="/caregiver/login" element={<AuthPage who="caregiver" mode="login" key="c-login" />} />
        <Route path="/caregiver/signup" element={<AuthPage who="caregiver" mode="signup" key="c-signup" />} />
        <Route path="/caregiver" element={<RequireRole role="caregiver"><CaregiverDashboard /></RequireRole>} />
        <Route path="/caregiver/residents/:id" element={<RequireRole role="caregiver"><ResidentDetail /></RequireRole>} />
        <Route path="/caregiver/live/:id" element={<RequireRole role="caregiver"><LiveSession /></RequireRole>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
