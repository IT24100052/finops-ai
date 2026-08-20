import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './AuthContext'
import Sidebar from './components/Sidebar'
import AuthPage from './pages/AuthPage'
import Dashboard from './pages/Dashboard'
import PredictionsPage from './pages/PredictionsPage'
import WastePage from './pages/WastePage'
import AlertsPage from './pages/AlertsPage'
import UploadPage from './pages/UploadPage'
import ResourcesPage from './pages/ResourcesPage'
import ResourceDetailPage from './pages/ResourceDetailPage'
import DataQualityPage from './pages/DataQualityPage'

function ProtectedLayout() {
  const { isAuthed } = useAuth()

  if (!isAuthed) return <Navigate to="/login" replace />

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/predictions" element={<PredictionsPage />} />
          <Route path="/waste" element={<WastePage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/resources" element={<ResourcesPage />} />
          <Route
            path="/resources/:resourceId"
            element={<ResourceDetailPage />}
          />
          <Route path="/data-quality" element={<DataQualityPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}

function AuthRoute() {
  const { isAuthed } = useAuth()

  if (isAuthed) return <Navigate to="/" replace />

  return <AuthPage />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <Routes>
          <Route path="/login" element={<AuthRoute />} />
          <Route path="/*" element={<ProtectedLayout />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}