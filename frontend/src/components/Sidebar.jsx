import { useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, TrendingUp, AlertTriangle, Upload,
  Bell, LogOut, Server, Database, Shield, Activity
} from 'lucide-react'
import { useAuth } from '../AuthContext'

const NAV = [
  { icon: LayoutDashboard, label: 'Dashboard',    path: '/' },
  { icon: TrendingUp,      label: 'Predictions',  path: '/predictions' },
  { icon: AlertTriangle,   label: 'Waste',        path: '/waste' },
  { icon: Bell,            label: 'Alerts',       path: '/alerts' },
  { icon: Database,        label: 'Resources',    path: '/resources' },
  { icon: Upload,          label: 'Data Upload',  path: '/upload' },
  { icon: Activity,        label: 'Data Quality', path: '/data-quality' },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const { pathname } = useLocation()

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="logo-mark">FinOps AI</span>
        <span className="logo-sub">Cloud Cost Intelligence</span>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section">Workspace</div>
        {NAV.map(({ icon: Icon, label, path }) => (
          <button
            key={path}
            className={`nav-item ${pathname === path ? 'active' : ''}`}
            onClick={() => nav(path)}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <Server size={13} />
          <span style={{ fontSize: '0.72rem' }}>{user?.email ?? 'Guest'}</span>
        </div>
        <button className="nav-item" style={{ padding: '7px 0' }} onClick={logout}>
          <LogOut size={13} />
          <span style={{ fontSize: '0.78rem' }}>Sign out</span>
        </button>
      </div>
    </aside>
  )
}
