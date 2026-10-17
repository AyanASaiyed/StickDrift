import { Link, Navigate, Route, Routes } from 'react-router'
import { AuthProvider, RequireRole, useAuth } from './auth'
import { TopBar } from './components/TopBar'
import AuthPage from './pages/AuthPage'
import CaregiverDashboard from './pages/CaregiverDashboard'
import CaregiverLogin from './pages/CaregiverLogin'
import ArrowSetup from './pages/ArrowSetup'
import Home from './pages/Home'
import LiveSession from './pages/LiveSession'
import Play from './pages/Play'
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
        <div className="row">
          <Link className="btn btn-big" to="/signup">Create an account</Link>
          <Link className="btn btn-quiet btn-big" to="/login">Log in</Link>
        </div>
        <p className="muted">Care team member? <Link to="/caregiver/login">Caregiver login</Link></p>
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
        <Route path="/login" element={<AuthPage mode="login" key="login" />} />
        <Route path="/signup" element={<AuthPage mode="signup" key="signup" />} />
        <Route path="/caregiver/login" element={<CaregiverLogin />} />
        <Route path="/play" element={<RequireRole role="senior"><Play /></RequireRole>} />
        <Route path="/arrows" element={<RequireRole role="senior"><ArrowSetup /></RequireRole>} />
        <Route path="/caregiver" element={<RequireRole role="caregiver"><CaregiverDashboard /></RequireRole>} />
        <Route path="/caregiver/residents/:id" element={<RequireRole role="caregiver"><ResidentDetail /></RequireRole>} />
        <Route path="/caregiver/live/:id" element={<RequireRole role="caregiver"><LiveSession /></RequireRole>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
