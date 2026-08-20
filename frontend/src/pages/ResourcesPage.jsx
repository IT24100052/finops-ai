import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Server, ChevronRight, Filter } from 'lucide-react'
import { api } from '../api'

const PROVIDER_COLORS = { AWS: '#f59e0b', Azure: '#3b82f6', GCP: '#00d4aa', Generic: '#8b5cf6' }
const ENV_COLORS = { production: 'badge-ok', staging: 'badge-medium', development: 'badge-low' }

export default function ResourcesPage() {
  const [resources, setResources] = useState([])
  const [loading,   setLoading]   = useState(true)
  const [search,    setSearch]    = useState('')
  const [provFilt,  setProvFilt]  = useState('all')
  const [svcFilt,   setSvcFilt]   = useState('all')
  const nav = useNavigate()

  useEffect(() => {
    api.getResources()
      .then(r => setResources(r || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="loading-center"><div className="spinner" /><span>Loading resources…</span></div>
  )

  const providers = ['all', ...new Set(resources.map(r => r.provider).filter(Boolean))]
  const services  = ['all', ...new Set(resources.map(r => r.service).filter(Boolean))]

  const filtered = resources.filter(r => {
    const q = search.toLowerCase()
    const matchSearch = !q ||
      (r.resource_id || '').toLowerCase().includes(q) ||
      (r.resource_name || '').toLowerCase().includes(q) ||
      (r.service || '').toLowerCase().includes(q) ||
      (r.team || '').toLowerCase().includes(q)
    const matchProv = provFilt === 'all' || r.provider === provFilt
    const matchSvc  = svcFilt === 'all' || r.service === svcFilt
    return matchSearch && matchProv && matchSvc
  })

  return (
    <>
      <div className="page-header">
        <div className="page-title">Inventory</div>
        <div className="page-heading">Resources</div>
      </div>

      <div className="page-body">
        {resources.length === 0 ? (
          <div className="empty-state">
            <Server size={36} style={{ color: 'var(--text-muted)', margin: '0 auto 12px', display:'block' }} />
            <div style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: 6 }}>No resources found</div>
            <div>Upload billing data to see your resource inventory.</div>
          </div>
        ) : (
          <>
            {/* Filters */}
            <div className="filter-bar section">
              <input
                className="filter-search"
                placeholder="Search resource, service, team…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
              <span className="filter-label">Provider:</span>
              {providers.map(p => (
                <button key={p} className={`filter-chip ${provFilt === p ? 'active' : ''}`}
                  onClick={() => setProvFilt(p)}>{p}</button>
              ))}
              <span className="filter-label">Service:</span>
              <select className="filter-select" value={svcFilt} onChange={e => setSvcFilt(e.target.value)}>
                {services.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <table className="waste-table">
                <thead>
                  <tr>
                    <th>Resource</th>
                    <th>Provider / Service</th>
                    <th>Region</th>
                    <th>Environment</th>
                    <th>Team</th>
                    <th style={{ textAlign: 'right' }}>CPU Avg</th>
                    <th style={{ textAlign: 'right' }}>Total Cost</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r, i) => (
                    <tr key={i} style={{ cursor: 'pointer' }}
                      onClick={() => nav(`/resources/${encodeURIComponent(r.resource_id)}`)}>
                      <td>
                        <div className="resource-id">{r.resource_name || r.resource_id}</div>
                        <div className="resource-type">{r.resource_id}</div>
                        {r.instance_type && <div className="resource-type">{r.instance_type}</div>}
                      </td>
                      <td>
                        <span style={{
                          fontFamily: 'var(--font-mono)', fontSize: '0.72rem', fontWeight: 600,
                          color: PROVIDER_COLORS[r.provider] || 'var(--text-secondary)'
                        }}>
                          {r.provider || '—'}
                        </span>
                        <div className="resource-type">{r.service}</div>
                      </td>
                      <td><span style={{ fontSize: '0.8rem' }}>{r.region || '—'}</span></td>
                      <td>
                        {r.environment ? (
                          <span className={`badge ${ENV_COLORS[r.environment] || 'badge-low'}`}>
                            {r.environment}
                          </span>
                        ) : <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>—</span>}
                      </td>
                      <td><span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{r.team || '—'}</span></td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
                        {r.avg_cpu != null ? (
                          <span style={{
                            color: r.avg_cpu < 15 ? 'var(--danger)' : r.avg_cpu < 30 ? 'var(--warn)' : 'var(--accent)'
                          }}>{r.avg_cpu.toFixed(1)}%</span>
                        ) : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                      </td>
                      <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}>
                        <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                          ${Number(r.total_cost).toLocaleString(undefined,{maximumFractionDigits:2})}
                        </span>
                      </td>
                      <td><ChevronRight size={14} style={{ color: 'var(--text-muted)' }} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filtered.length === 0 && (
                <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  No resources match filters.
                </div>
              )}
            </div>
            <div style={{ marginTop: 10, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Showing {filtered.length} of {resources.length} resources
            </div>
          </>
        )}
      </div>
    </>
  )
}
