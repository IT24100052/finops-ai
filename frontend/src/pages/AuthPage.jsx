import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../AuthContext'

const DEMO_EMAIL = 'testuser@example.com'
const DEMO_PASS = 'Test@12345'

// Simple SVG eye icons inline — no extra dependency needed
function EyeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function EyeOffIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  )
}

export default function AuthPage() {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { login } = useAuth()
  const nav = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'register') {
        await api.register(email, password)
        setMode('login')
        setError('')
        return
      }
      const data = await api.login(email, password)
      login(data.access_token)
      nav('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function fillDemo() {
    setEmail(DEMO_EMAIL)
    setPassword(DEMO_PASS)
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">FINOPS AI</div>
        <div className="auth-tagline">Cloud cost intelligence platform</div>

        {/* ── Performance notice ── */}
        <div className="auth-notice">
          <span className="auth-notice-icon">⚡</span>
          <span>
            Load may be <strong>slow</strong> — the system processes a large dataset
            on a free-tier server. Please allow few seconds.
          </span>
        </div>

        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Email</label>
            <input
              className="form-input"
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <div className="input-wrapper">
              <input
                className="form-input"
                type={showPass ? 'text' : 'password'}
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="eye-toggle"
                onClick={() => setShowPass(p => !p)}
                aria-label={showPass ? 'Hide password' : 'Show password'}
                tabIndex={-1}
              >
                {showPass ? <EyeOffIcon /> : <EyeIcon />}
              </button>
            </div>
          </div>

          <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
            {loading ? <span className="spinner" /> : (mode === 'login' ? 'Sign in' : 'Create account')}
          </button>
        </form>

        {/* ── Demo credentials (only on login) ── */}
        {mode === 'login' && (
          <div className="demo-note">
            <div className="demo-note-header">
              <span>🔑 Demo credentials</span>
              <button className="demo-fill-btn" type="button" onClick={fillDemo}>
                Fill automatically
              </button>
            </div>
            <div className="demo-creds">
              <span className="demo-field">Email</span>
              <code>{DEMO_EMAIL}</code>
              <span className="demo-field">Password</span>
              <code>{DEMO_PASS}</code>
            </div>
          </div>
        )}

        <div className="auth-toggle">
          {mode === 'login' ? (
            <>Don't have an account?{' '}
              <button onClick={() => { setMode('register'); setError('') }}>Register</button>
            </>
          ) : (
            <>Already have an account?{' '}
              <button onClick={() => { setMode('login'); setError('') }}>Sign in</button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
