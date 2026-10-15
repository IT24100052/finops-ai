import { useEffect, useState } from 'react'
import { AlertTriangle, TrendingDown, DollarSign, Filter } from 'lucide-react'
import { api } from '../api'

const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 }
const SEVERITY_LABELS = ['all', 'critical', 'high', 'medium', 'low']

function SeverityBadge({ s }) {
  const cls = s === 'critical' ? 'badge-critical' : `badge-${s}`
  return <span className={`badge ${cls}`}>{s}</span>
}

function ConfidenceDot({ c }) {
  const color = c === 'high' ? 'var(--accent)' : c === 'medium' ? 'var(--warn)' : 'var(--text-muted)'
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.72rem', color }}>
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: color, display: 'inline-block' }} />
      {c}
    </span>
  )
}

export default function WastePage() {
  const [findings, setFindings] = useState([])
  const [loading, setLoading]   = useState(true)
  const [filter, setFilter]     = useState('all')
  const [provFilter, setProvFilter] = useState('all')

  useEffect(() => {
    api.getWaste()
      .then(setFindings)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="loading-center"><div className="spinner" /><span>Analysing waste…</span></div>
  )

  // Provider options
  const providers = ['all', ...new Set(findings.map(f => f.provider).filter(Boolean))]

  const allVerifiedMonthly = findings.length > 0 && findings.every(f => Boolean(f.is_verified_monthly))

  const filtered = findings
    .filter(f => filter === 'all' || f.severity === filter)
    .filter(f => provFilter === 'all' || f.provider === provFilter)

  const filteredPeriods = [...new Set(filtered.map(f => f.savings_period).filter(Boolean))]
  const filteredAllMonthly = filtered.length > 0 && filtered.every(f => Boolean(f.is_verified_monthly))
  const filteredMixed = filteredPeriods.length > 1 && !filteredAllMonthly

  // Do not sum findings with incompatible periods or describe an observed-period total as monthly
  const canSumFiltered = !filteredMixed
  const totalSavings = canSumFiltered
    ? filtered.reduce((s, f) => s + ((typeof f.estimated_savings === 'number' ? f.estimated_savings : f.estimated_monthly_savings) || 0), 0)
    : null

  const critical = findings.filter(f => f.severity === 'critical').length
  const high     = findings.filter(f => f.severity === 'high').length
  const medium   = findings.filter(f => f.severity === 'medium').length
  const low      = findings.filter(f => f.severity === 'low').length

  return (
    <>
      <div className="page-header">
        <div className="page-title">AI Analysis</div>
        <div className="page-heading">Waste Detection</div>
      </div>

      <div className="page-body">
        {findings.length === 0 ? (
          <div className="empty-state">
            <TrendingDown size={40} style={{ color: 'var(--text-muted)', margin: '0 auto 12px', display:'block' }} />
            <div style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: 6 }}>No waste detected</div>
            <div>Upload billing data to run AI waste analysis.</div>
          </div>
        ) : (
          <>
            {/* Summary cards */}
            <div className="grid-4 section">
              <div className="card">
                <div className="card-label">
                  {filteredAllMonthly ? 'Potential Monthly Savings' : 'Potential Savings'}
                </div>
                <div className="card-value accent">
                  {canSumFiltered
                    ? `$${totalSavings.toLocaleString(undefined,{maximumFractionDigits:0})}`
                    : 'Mixed Periods'}
                </div>
                <div className="card-sub">
                  {canSumFiltered
                    ? (filteredAllMonthly
                        ? `from ${filtered.length} issue(s) (/month)`
                        : `from ${filtered.length} issue(s) across ${filteredPeriods[0] || 'observed period'}`)
                    : 'Multiple observation windows; see individual items'}
                </div>
              </div>
              <div className="card">
                <div className="card-label">Critical / High</div>
                <div className="card-value danger">{critical + high}</div>
                <div className="card-sub">{critical} critical, {high} high</div>
              </div>
              <div className="card">
                <div className="card-label">Medium / Low</div>
                <div className="card-value warn">{medium + low}</div>
                <div className="card-sub">{medium} medium, {low} low</div>
              </div>
              <div className="card">
                <div className="card-label">Total Issues</div>
                <div className="card-value">{findings.length}</div>
                <div className="card-sub">{filtered.length} shown after filter</div>
              </div>
            </div>

            {/* Filter bar */}
            <div className="filter-bar section">
              <Filter size={13} style={{ color: 'var(--text-muted)' }} />
              <span className="filter-label">Severity:</span>
              {SEVERITY_LABELS.map(s => (
                <button key={s} onClick={() => setFilter(s)}
                  className={`filter-chip ${filter === s ? 'active' : ''}`}>
                  {s}
                </button>
              ))}
              {providers.length > 1 && (
                <>
                  <span className="filter-label" style={{ marginLeft: 12 }}>Provider:</span>
                  {providers.map(p => (
                    <button key={p} onClick={() => setProvFilter(p)}
                      className={`filter-chip ${provFilter === p ? 'active' : ''}`}>
                      {p}
                    </button>
                  ))}
                </>
              )}
            </div>

            {/* Findings table */}
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <table className="waste-table">
                <thead>
                  <tr>
                    <th>Resource</th>
                    <th>Provider / Region</th>
                    <th>Issue</th>
                    <th>Severity</th>
                    <th>Confidence</th>
                    <th style={{ textAlign: 'right' }}>{allVerifiedMonthly ? 'Monthly Cost' : 'Period Cost'}</th>
                    <th style={{ textAlign: 'right' }}>{allVerifiedMonthly ? 'Savings (/mo)' : 'Estimated Savings'}</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((f, i) => {
                    const costVal = typeof f.period_cost === 'number' ? f.period_cost : f.monthly_cost
                    const savingsVal = typeof f.estimated_savings === 'number' ? f.estimated_savings : f.estimated_monthly_savings
                    const isMonthlyFinding = Boolean(f.is_verified_monthly)
                    const periodTag = isMonthlyFinding ? '/mo' : (f.savings_period || 'observed period')

                    return (
                      <tr key={i}>
                        <td>
                          <div className="resource-id">{f.resource_name || f.resource_id}</div>
                          <div className="resource-type">{f.resource_id}</div>
                          {f.instance_type && <div className="resource-type">{f.instance_type}</div>}
                          {f.team && <div className="resource-type" style={{ color: 'var(--info)' }}>{f.team}</div>}
                        </td>
                        <td>
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)' }}>
                            {f.provider || '—'}
                          </div>
                          <div className="resource-type">{f.region || '—'}</div>
                          {f.environment && (
                            <div style={{ fontSize: '0.68rem', marginTop: 2 }}>
                              <span className={`badge badge-${
                                f.environment === 'production' ? 'ok' :
                                f.environment === 'staging' ? 'medium' : 'low'
                              }`}>{f.environment}</span>
                            </div>
                          )}
                        </td>
                        <td style={{ maxWidth: 280 }}>
                          <div className="issue-title">{f.issue}</div>
                          <div className="issue-detail">{f.detail}</div>
                          <div className="issue-detail" style={{ color: 'var(--accent)', marginTop: 4 }}>
                            {f.recommendation}
                          </div>
                        </td>
                        <td><SeverityBadge s={f.severity} /></td>
                        <td><ConfidenceDot c={f.confidence} /></td>
                        <td className="cost-cell">
                          <span className="cost-val">${costVal.toLocaleString(undefined,{maximumFractionDigits:2})}</span>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{periodTag}</div>
                        </td>
                        <td className="cost-cell">
                          <span className="savings-val">${savingsVal.toLocaleString(undefined,{maximumFractionDigits:2})}</span>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                            {isMonthlyFinding ? `${f.savings_percentage}% (/mo)` : `${f.savings_percentage}% (observed)`}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  )
}
