import { useEffect, useState } from 'react'
import { Bell, Plus, Trash2, AlertTriangle, CheckCircle, TrendingUp } from 'lucide-react'
import { api } from '../api'

const STATUS_STYLES = {
  ok:       { cls: 'badge-ok',     icon: CheckCircle,    color: 'var(--accent)' },
  warning:  { cls: 'badge-medium', icon: AlertTriangle,  color: 'var(--warn)' },
  critical: { cls: 'badge-high',   icon: AlertTriangle,  color: 'var(--danger)' },
  exceeded: { cls: 'badge-critical',icon: AlertTriangle,  color: 'var(--danger)' },
}

function BudgetProgressBar({ pct }) {
  const clamped = Math.min(pct, 110)
  const color = pct >= 100 ? 'var(--danger)' : pct >= 80 ? 'var(--warn)' : 'var(--accent)'
  return (
    <div className="progress-track">
      <div className="progress-fill" style={{ width: `${Math.min(clamped, 100)}%`, background: color }} />
    </div>
  )
}

function BudgetCard({ budget, onDelete }) {
  const st = STATUS_STYLES[budget.status] || STATUS_STYLES.ok
  const Icon = st.icon
  return (
    <div className="card budget-card">
      <div className="budget-header">
        <div>
          <div className="budget-name">{budget.name}</div>
          <div className="budget-scope">
            {budget.scope}{budget.scope_value ? `: ${budget.scope_value}` : ''}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className={`badge ${st.cls}`}>
            <Icon size={10} style={{ marginRight: 3, verticalAlign: 'middle' }} />
            {budget.status}
          </span>
          <button className="btn btn-danger" style={{ padding: '4px 8px', fontSize: '0.75rem' }}
            onClick={() => onDelete(budget.id)}>
            <Trash2 size={12} />
          </button>
        </div>
      </div>

      <BudgetProgressBar pct={budget.utilization_pct} />

      <div className="budget-stats">
        <div>
          <div className="budget-stat-label">Spent</div>
          <div className="budget-stat-val">${budget.current_spend.toLocaleString(undefined,{maximumFractionDigits:0})}</div>
        </div>
        <div>
          <div className="budget-stat-label">Limit</div>
          <div className="budget-stat-val">${budget.monthly_limit.toLocaleString(undefined,{maximumFractionDigits:0})}</div>
        </div>
        <div>
          <div className="budget-stat-label">Remaining</div>
          <div className="budget-stat-val" style={{ color: budget.remaining === 0 ? 'var(--danger)' : 'var(--accent)' }}>
            ${budget.remaining.toLocaleString(undefined,{maximumFractionDigits:0})}
          </div>
        </div>
        <div>
          <div className="budget-stat-label">Utilization</div>
          <div className="budget-stat-val" style={{
            color: budget.utilization_pct >= 100 ? 'var(--danger)' : budget.utilization_pct >= 80 ? 'var(--warn)' : 'var(--accent)'
          }}>
            {budget.utilization_pct}%
          </div>
        </div>
        <div>
          <div className="budget-stat-label">Forecast</div>
          <div className="budget-stat-val">${budget.forecasted_spend.toLocaleString(undefined,{maximumFractionDigits:0})}</div>
        </div>
        {budget.projected_overrun > 0 && (
          <div>
            <div className="budget-stat-label" style={{ color: 'var(--danger)' }}>Overrun</div>
            <div className="budget-stat-val danger">${budget.projected_overrun.toLocaleString(undefined,{maximumFractionDigits:0})}</div>
          </div>
        )}
      </div>

      {budget.triggered_thresholds.length > 0 && (
        <div style={{ marginTop: 8, fontSize: '0.72rem', color: 'var(--warn)' }}>
          Thresholds triggered: {budget.triggered_thresholds.map(t => `${t}%`).join(', ')}
        </div>
      )}
    </div>
  )
}

const SCOPE_OPTIONS = ['overall', 'provider', 'service', 'team', 'project', 'environment']

function CreateBudgetForm({ onCreated, onCancel }) {
  const [name, setName]       = useState('')
  const [limit, setLimit]     = useState('')
  const [scope, setScope]     = useState('overall')
  const [scopeVal, setScopeVal] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr]         = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setErr('')
    if (!name.trim()) return setErr('Name is required')
    if (!limit || isNaN(Number(limit)) || Number(limit) <= 0) return setErr('Enter a valid monthly limit')
    setLoading(true)
    try {
      const b = await api.createBudget({
        name: name.trim(),
        monthly_limit: Number(limit),
        scope,
        scope_value: scopeVal || null,
      })
      onCreated(b)
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <div className="section-title" style={{ marginBottom: 16 }}>Create New Budget</div>
      <form onSubmit={submit}>
        {err && <div className="error-msg">{err}</div>}
        <div className="grid-2" style={{ gap: 14, marginBottom: 14 }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Budget Name</label>
            <input className="form-input" value={name} onChange={e => setName(e.target.value)}
              placeholder="e.g. Monthly AWS Budget" />
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Monthly Limit ($)</label>
            <input className="form-input" type="number" min="1" step="100" value={limit}
              onChange={e => setLimit(e.target.value)} placeholder="5000" />
          </div>
        </div>
        <div className="grid-2" style={{ gap: 14, marginBottom: 16 }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Scope</label>
            <select className="form-input" value={scope} onChange={e => { setScope(e.target.value); setScopeVal('') }}>
              {SCOPE_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          {scope !== 'overall' && (
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Scope Value</label>
              <input className="form-input" value={scopeVal} onChange={e => setScopeVal(e.target.value)}
                placeholder={`e.g. ${scope === 'provider' ? 'AWS' : scope === 'service' ? 'EC2' : 'Analytics'}`} />
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            <Plus size={14} /> {loading ? 'Creating…' : 'Create Budget'}
          </button>
          <button type="button" className="btn btn-ghost" onClick={onCancel}>Cancel</button>
        </div>
      </form>
    </div>
  )
}

export default function AlertsPage() {
  const [budgets,  setBudgets]  = useState([])
  const [insights, setInsights] = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [showForm, setShowForm] = useState(false)

  useEffect(() => {
    Promise.all([api.getBudgets(), api.getInsights()])
      .then(([b, i]) => { setBudgets(b || []); setInsights(i) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const handleCreated = (b) => {
    setBudgets(prev => [...prev, b])
    setShowForm(false)
  }

  const handleDelete = async (id) => {
    await api.deleteBudget(id)
    setBudgets(prev => prev.filter(b => b.id !== id))
  }

  if (loading) return (
    <div className="loading-center"><div className="spinner" /><span>Loading…</span></div>
  )

  // AI-generated monitoring alerts (from insights)
  const topIssues = insights?.top_issues || []
  const wastePct  = insights?.waste_percentage || 0
  const savings   = insights?.total_potential_savings || 0

  const aiAlerts = []
  if (wastePct > 30) aiAlerts.push({ sev: 'high',   msg: `High waste ratio: ${wastePct}% of budget potentially wasted (~$${savings.toLocaleString(undefined,{maximumFractionDigits:0})}/mo).` })
  topIssues.filter(i => i.severity === 'critical' || i.severity === 'high').slice(0, 3).forEach(i => {
    aiAlerts.push({ sev: 'high', msg: `${i.issue}: ${i.resource_name || i.resource_id} — save $${i.estimated_monthly_savings.toLocaleString(undefined,{maximumFractionDigits:0})}/mo.` })
  })
  topIssues.filter(i => i.severity === 'medium').slice(0, 2).forEach(i => {
    aiAlerts.push({ sev: 'medium', msg: `${i.issue}: ${i.resource_name || i.resource_id} — ${i.detail}` })
  })
  if (aiAlerts.length === 0 && insights) {
    aiAlerts.push({ sev: 'low', msg: 'No critical alerts. Cost governance looks healthy.' })
  }

  return (
    <>
      <div className="page-header">
        <div className="page-title">Monitoring</div>
        <div className="page-heading">Alerts & Budgets</div>
      </div>

      <div className="page-body">

        {/* AI Monitoring Alerts */}
        <div className="section">
          <div className="section-title">AI Monitoring Alerts</div>
          <div className="alert-list">
            {aiAlerts.map((a, i) => (
              <div key={i} className={`alert-item ${a.sev}`}>
                <AlertTriangle size={14} />
                <span>{a.msg}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="divider" />

        {/* Budget Management */}
        <div className="section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div className="section-title" style={{ margin: 0 }}>Budget Management</div>
            {!showForm && (
              <button className="btn btn-primary" style={{ padding: '7px 14px', fontSize: '0.82rem' }}
                onClick={() => setShowForm(true)}>
                <Plus size={14} /> New Budget
              </button>
            )}
          </div>

          {showForm && (
            <CreateBudgetForm onCreated={handleCreated} onCancel={() => setShowForm(false)} />
          )}

          {budgets.length === 0 && !showForm ? (
            <div className="empty-state" style={{ padding: '30px 0' }}>
              <Bell size={32} style={{ color: 'var(--text-muted)', margin: '0 auto 10px', display: 'block' }} />
              <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)', marginBottom: 4 }}>No budgets yet</div>
              <div style={{ fontSize: '0.82rem' }}>Create a budget to track spend against limits.</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {budgets.map(b => <BudgetCard key={b.id} budget={b} onDelete={handleDelete} />)}
            </div>
          )}
        </div>

      </div>
    </>
  )
}
