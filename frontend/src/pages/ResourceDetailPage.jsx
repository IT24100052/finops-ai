import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Server, DollarSign } from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from 'recharts'
import { api } from '../api'

function MetaRow({ label, value }) {
  if (!value) return null
  return (
    <div style={{ display: 'flex', gap: 12, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ width: 160, flexShrink: 0, fontSize: '0.75rem', color: 'var(--text-muted)',
        fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em', paddingTop: 1 }}>
        {label}
      </div>
      <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{value}</div>
    </div>
  )
}

function StatBox({ label, value, sub, color }) {
  return (
    <div className="card" style={{ padding: '14px 16px' }}>
      <div className="card-label">{label}</div>
      <div className="card-value" style={{ fontSize: '1.4rem', color: color || 'var(--text-primary)' }}>{value}</div>
      {sub && <div className="card-sub">{sub}</div>}
    </div>
  )
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="card" style={{ padding: '8px 12px', fontSize: '0.78rem' }}>
      <div style={{ color: 'var(--text-muted)' }}>{label}</div>
      <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
        ${Number(payload[0].value).toFixed(2)}
      </div>
    </div>
  )
}

export default function ResourceDetailPage() {
  const { resourceId } = useParams()
  const nav = useNavigate()
  const [data,    setData]    = useState(null)
  const [waste,   setWaste]   = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.getResource(decodeURIComponent(resourceId)),
      api.getWaste(),
    ])
      .then(([d, w]) => {
        setData(d)
        setWaste((w || []).filter(f => f.resource_id === decodeURIComponent(resourceId)))
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [resourceId])

  if (loading) return (
    <div className="loading-center"><div className="spinner" /><span>Loading resource…</span></div>
  )

  if (!data || data.error) return (
    <div className="empty-state">
      <Server size={36} style={{ color: 'var(--text-muted)', margin: '0 auto 12px', display:'block' }} />
      <div>{data?.error || 'Resource not found'}</div>
      <button className="btn btn-ghost" style={{ marginTop: 12 }} onClick={() => nav(-1)}>
        <ArrowLeft size={13} /> Back
      </button>
    </div>
  )

  const chartData = (data.cost_history || []).map(d => ({
    ...d,
    label: new Date(d.date + 'T00:00:00').toLocaleDateString('en-US', { month:'short', day:'numeric' })
  }))

  const cpuColor = data.avg_cpu == null ? 'var(--text-muted)'
    : data.avg_cpu < 15 ? 'var(--danger)' : data.avg_cpu < 30 ? 'var(--warn)' : 'var(--accent)'

  return (
    <>
      <div className="page-header">
        <div className="page-title">Resource Detail</div>
        <div className="page-heading" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: '0.78rem' }}
            onClick={() => nav(-1)}>
            <ArrowLeft size={13} /> Back
          </button>
          {data.resource_name || data.resource_id}
        </div>
      </div>

      <div className="page-body">

        {/* Stats row */}
        <div className="grid-4 section">
          <StatBox label="Total Cost" value={`$${Number(data.total_cost).toLocaleString(undefined,{maximumFractionDigits:2})}`}
            color="var(--text-primary)" sub={`${data.days_active} active days`} />
          <StatBox label="Avg CPU" value={data.avg_cpu != null ? `${data.avg_cpu}%` : '—'}
            color={cpuColor} sub="avg utilization" />
          <StatBox label="Usage Hours" value={data.total_hours != null ? data.total_hours.toLocaleString() : '—'}
            sub="total hours tracked" />
          <StatBox label="Issues Detected" value={waste.length}
            color={waste.length > 0 ? 'var(--danger)' : 'var(--accent)'}
            sub={waste.length ? 'click below to review' : 'no issues found'} />
        </div>

        {/* Metadata + Cost history */}
        <div className="grid-2" style={{ marginBottom: 24, alignItems: 'start' }}>
          <div className="card">
            <div className="section-title" style={{ marginBottom: 12 }}>Metadata</div>
            <MetaRow label="Resource ID"   value={data.resource_id} />
            <MetaRow label="Resource Name" value={data.resource_name} />
            <MetaRow label="Provider"      value={data.provider} />
            <MetaRow label="Account"       value={data.account_id} />
            <MetaRow label="Service"       value={data.service} />
            <MetaRow label="Region"        value={data.region} />
            <MetaRow label="Instance Type" value={data.instance_type} />
            <MetaRow label="Resource Type" value={data.resource_type} />
            <MetaRow label="Environment"   value={data.environment} />
            <MetaRow label="Team"          value={data.team} />
            <MetaRow label="Project"       value={data.project} />
            <MetaRow label="Tags"          value={data.tags} />
          </div>

          <div className="card" style={{ padding: '18px 18px 10px' }}>
            <div className="section-title" style={{ marginBottom: 14 }}>Cost History</div>
            {chartData.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', textAlign: 'center', padding: '40px 0' }}>
                No cost history available
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="resGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#00d4aa" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#00d4aa" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                    tickLine={false} axisLine={false}
                    interval={Math.max(0, Math.floor(chartData.length / 5) - 1)} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                    tickLine={false} axisLine={false} tickFormatter={v => `$${v}`} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="cost" stroke="#00d4aa" strokeWidth={2}
                    fill="url(#resGrad)" dot={false}
                    activeDot={{ r: 4, fill: '#00d4aa', stroke: '#0a0c0f', strokeWidth: 2 }} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Waste findings for this resource */}
        {waste.length > 0 && (
          <div className="section">
            <div className="section-title">Detected Issues & Recommendations</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {waste.map((f, i) => (
                <div key={i} className="card" style={{ borderColor: f.severity === 'high' || f.severity === 'critical' ? 'rgba(255,77,109,0.3)' : 'var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span className="issue-title">{f.issue}</span>
                    <span className={`badge badge-${f.severity}`}>{f.severity}</span>
                  </div>
                  <div className="issue-detail" style={{ marginBottom: 8 }}>{f.detail}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--accent)' }}>
                    <strong>Recommendation:</strong> {f.recommendation}
                  </div>
                  <div style={{ marginTop: 8, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    Estimated savings: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>
                      ${f.estimated_monthly_savings.toLocaleString(undefined,{maximumFractionDigits:2})}/mo
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </>
  )
}
