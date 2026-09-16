import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { NavRail } from './components/NavRail'
import { AuthProvider } from './contexts/AuthProvider'
import { useAuth } from './hooks/useAuth'
import Chat from './pages/Chat'
import Context from './pages/Context'
import Dashboard from './pages/Dashboard'
import Graph from './pages/Graph'
import Journal from './pages/Journal'
import Login from './pages/Login'
import Objectives from './pages/Objectives'
import Onboarding from './pages/Onboarding'
import Projects from './pages/Projects'
import Reflections from './pages/Reflections'
import Register from './pages/Register'
import Settings from './pages/Settings'
import Styleguide from './pages/Styleguide'
import Usage from './pages/Usage'

function Shell() {
  return (
    <div className="flex min-h-screen bg-bg text-text">
      <NavRail />
      <main className="min-w-0 flex-1">
        <Outlet />
      </main>
    </div>
  )
}

function Loading() {
  return <div className="min-h-screen bg-bg p-8 text-sm text-muted-fg">Loading…</div>
}

/** Feature routes: authed AND onboarded. */
function RequireAuth() {
  const { user, loading, onboarded } = useAuth()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  if (!onboarded) return <Navigate to="/onboarding" replace />
  return <Shell />
}

/** Onboarding route: authed only (re-runnable even once complete — REQ-5). */
function RequireAuthOnly({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  return children
}

function RedirectIfAuthed({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  if (user) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route
          path="/login"
          element={
            <RedirectIfAuthed>
              <Login />
            </RedirectIfAuthed>
          }
        />
        <Route
          path="/register"
          element={
            <RedirectIfAuthed>
              <Register />
            </RedirectIfAuthed>
          }
        />
        <Route
          path="/onboarding"
          element={
            <RequireAuthOnly>
              <Onboarding />
            </RequireAuthOnly>
          }
        />
        <Route element={<RequireAuth />}>
          <Route path="/" element={<Chat />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/journal" element={<Journal />} />
          <Route path="/objectives" element={<Objectives />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/context" element={<Context />} />
          <Route path="/graph" element={<Graph />} />
          <Route path="/usage" element={<Usage />} />
          <Route path="/reflections" element={<Reflections />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="/styleguide" element={<Styleguide />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
