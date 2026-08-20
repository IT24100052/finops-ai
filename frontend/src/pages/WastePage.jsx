import { useEffect, useState } from 'react'
import { AlertTriangle, Cpu, Database, HardDrive, TrendingDown, Filter } from 'lucide-react'
import { api } from '../api'

const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 }
const ISSUE_ICON = {
  'Idle resource':          Cpu,
  'Oversized instance':     TrendingDown,
  'Inefficient storage tier': HardDrive,
  'Anomalous cost pattern': AlertTriangle,
}

function SeverityBadge({ s }) {
  return <span className={`badge badge-${s}`}>{s}</span>
}

function WasteRow({ f }) {
  const Icon = ISSUE_ICON[f.issue] || Database
  return (
    <tr>
      <td>
        <div className="resource-id">{f.resource_id}</div>
        <div className="resource-type">
          {f.service}{f.instance_type ? ` · ${f.instance_type}` : ''}
        </div>
      </td>
      <td>
        <div className="issue-title">{f.issue}</div>
        <div className="issue-detail">{f.detail}</div>
      </td>
      <td><SeverityBadge s={f.severity} /></td>
      <td className="cost-cell">
        <div className="cost-val">${f.monthly_cost.toLocaleString()}</div>
        <div style={{ fontSize:'0.68rem', color:'var(--text-muted)', marginTop:1 }}>monthly cost</div>
      </td>
      <td className="cost-cell">
        <div className="savings-val">-${f.estimated_monthly_savings.toLocaleString()}/mo</div>
      </td>
      <td>
        <div style={{ fontSize:'0.78rem', color:'var(--text-secondary)', maxWidth: 260, lineHeight:1.4 }}>
          {f.recommendation}
        </div>
      </td>
    </tr>
  )
}

export default function WastePage() {
  const [findings, setFindings] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [filter,   setFilter]   = useState('all') // all | high | medium | low

  useEffect(() => {
    api.getWaste()
      .then(data => setFindings(data.sort((a,b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const filtered = filter === 'all' ? findings : findings.filter(f => f.severity === filter)

  const totalSavings   = findings.reduce((s, f) => s + f.estimated_monthly_savings, 0)
  const highCount      = findings.filter(f => f.severity === 'high').length
  const mediumCount    = findings.filter(f => f.severity === 'medium').length
  const lowCount       = findings.filter(f => f.severity === 'low').length

  return (
    <>
      <div className="page-header">
        <div className="page-title">AI Module</div>
        <div className="page-heading">Waste Detection</div>
      </div>

      <div className="page-body">
        {loading ? (
          <div className="loading-center"><div className="spinner" /><span>Analyzing resource fleet…</span></div>
        ) : findings.length === 0 ? (
          <div className="empty-state">
            <AlertTriangle size={36} style={{ color:'var(--text-muted)', margin:'0 auto 12px', display:'block' }} />
            <div style={{ fontSize:'1rem', color:'var(--text-primary)', marginBottom:6 }}>No findings</div>
            <div>Upload billing data to run the waste detection engine.</div>
          </div>
        ) : (
          <>
            {/* Summary bar */}
            <div className="grid-4" style={{ marginBottom: 24 }}>
              <div className="card">
                <div className="card-label">Est. Monthly Savings</div>
                <div className="card-value accent">${totalSavings.toLocaleString(undefined, { maximumFractionDigits:0 })}</div>
                <div className="card-sub">{findings.length} issues detected</div>
              </div>
              <div className="card">
                <div className="card-label">High Severity</div>
                <div className="card-value danger">{highCount}</div>
                <div className="card-sub">idle resources wasting money</div>
              </div>
              <div className="card">
                <div className="card-label">Medium Severity</div>
                <div className="card-value warn">{mediumCount}</div>
                <div className="card-sub">oversized or anomalous</div>
              </div>
              <div className="card">
                <div className="card-label">Low Severity</div>
                <div className="card-value">{lowCount}</div>
                <div className="card-sub">storage optimisations</div>
              </div>
            </div>

            {/* Filter chips */}
            <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:16 }}>
              <Filter size={13} style={{ color:'var(--text-muted)' }} />
              {['all','high','medium','low'].map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className="btn btn-ghost"
                  style={{
                    padding:'4px 12px', fontSize:'0.75rem', textTransform:'capitalize',
                    background:   filter === f ? (f === 'high' ? 'var(--danger-dim)' : f === 'medium' ? 'var(--warn-dim)' : f === 'low' ? 'var(--info-dim)' : 'var(--accent-dim)') : undefined,
                    color:        filter === f ? (f === 'high' ? 'var(--danger)'     : f === 'medium' ? 'var(--warn)'     : f === 'low' ? 'var(--info)'     : 'var(--accent)')     : undefined,
                    borderColor:  filter === f ? 'transparent' : undefined,
                  }}
                >
                  {f === 'all' ? `All (${findings.length})` : `${f} (${findings.filter(x => x.severity === f).length})`}
                </button>
              ))}
            </div>

            {/* Findings table */}
            <div className="card" style={{ padding:0, overflow:'hidden' }}>
              <table className="waste-table">
                <thead>
                  <tr>
                    <th>Resource</th>
                    <th>Issue</th>
                    <th>Severity</th>
                    <th style={{ textAlign:'right' }}>Cost</th>
                    <th style={{ textAlign:'right' }}>Savings</th>
                    <th>Recommendation</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((f, i) => <WasteRow key={i} f={f} />)}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop:12, fontSize:'0.72rem', color:'var(--text-muted)', lineHeight:1.5 }}>
              <strong style={{ color:'var(--text-secondary)' }}>Engine:</strong> Two layers —
              rule-based heuristics (idle CPU, oversized instance families, storage cost-per-GB)
              + Isolation Forest anomaly detection on cost-per-usage-hour.
              Savings estimates are conservative (90% for idle, 40% for oversized, 20% for anomalies).
            </div>
          </>
        )}
      </div>
    </>
  )
}
