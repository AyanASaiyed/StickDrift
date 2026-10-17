import { Link, Navigate, Route, Routes } from 'react-router'
import { AuthProvider, RequireRole, useAuth } from './auth'
import { TopBar } from './components/TopBar'
import AuthPage from './pages/AuthPage'
import CaregiverDashboard from './pages/CaregiverDashboard'
import CaregiverLogin from './pages/CaregiverLogin'
import History from './pages/History'
import Home from './pages/Home'
import Play from './pages/Play'
import ResidentDetail from './pages/ResidentDetail'

function Welcome() {
  return (
    <main className="wrap">
      <section className="hero">
        <h1>A short game for two thumbs.</h1>
        <p className="lede">
          Arrows float up the screen. When one reaches the top, nudge the matching stick on your PS5 controller. It takes
          about three minutes, missing an arrow is fine, and you can pause any time.
        </p>
        <div className="row">
          <Link className="btn btn-big" to="/signup">
            Create an account
          </Link>
          <Link className="btn btn-quiet btn-big" to="/login">
            Log in
          </Link>
        </div>
        <p className="muted">
          Care team member? <Link to="/caregiver/login">Caregiver login</Link>
        </p>
      </section>
      <section className="features" aria-label="How it works">
        <div className="panel">
          <h2>Follow the arrows</h2>
          <p className="muted">Left-side arrows are for the left stick, right-side arrows for the right stick.</p>
        </div>
        <div className="panel">
          <h2>Same game every time</h2>
          <p className="muted">The arrows never speed up, so each session can be compared fairly with your last.</p>
        </div>
        <div className="panel">
          <h2>Your care team can help</h2>
          <p className="muted">Caregivers see your history and anything worth checking in on.</p>
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
        <Route path="/login" element={<AuthPage mode="login" key="login" />} />
        <Route path="/signup" element={<AuthPage mode="signup" key="signup" />} />
        <Route path="/caregiver/login" element={<CaregiverLogin />} />
        <Route
          path="/play"
          element={
            <RequireRole role="senior">
              <Play />
            </RequireRole>
          }
        />
        <Route
          path="/history"
          element={
            <RequireRole role="senior">
              <History />
            </RequireRole>
          }
        />
        <Route
          path="/caregiver"
          element={
            <RequireRole role="caregiver">
              <CaregiverDashboard />
            </RequireRole>
          }
        />
        <Route
          path="/caregiver/residents/:id"
          element={
            <RequireRole role="caregiver">
              <ResidentDetail />
            </RequireRole>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
