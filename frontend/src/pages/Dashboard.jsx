import { useEffect, useState } from 'react'
import { TrendingDown, Calendar, AlertTriangle, DollarSign } from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar, Cell
} from 'recharts'
import { api } from '../api'

const ICON_MAP = {
  'trending-down': TrendingDown,
  'calendar':       Calendar,
  'alert-triangle': AlertTriangle,
}

const ICON_COLOR = { 'trending-down': 'teal', 'calendar': 'blue', 'alert-triangle': 'red' }

function StatCard({ label, value, sub, accent }) {
  return (
    <div className="card">
      <div className="card-label">{label}</div>
      <div className={`card-value ${accent || ''}`}>{value}</div>
      {sub && <div className="card-sub">{sub}</div>}
    </div>
  )
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="card" style={{ padding: '10px 14px', minWidth: 120 }}>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 3 }}>{label}</div>
      <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)', fontSize: '0.9rem' }}>
        ${payload[0].value?.toFixed(2)}
      </div>
    </div>
  )
}

const SERVICE_COLORS = ['#00d4aa','#3b82f6','#f59e0b','#ff4d6d','#8b5cf6']

export default function Dashboard() {
  const [summary,  setSummary]  = useState(null)
  const [daily,    setDaily]    = useState([])
  const [insights, setInsights] = useState(null)
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    Promise.all([api.getSummary(), api.getDailyCosts(), api.getInsights()])
      .then(([s, d, i]) => { setSummary(s); setDaily(d); setInsights(i) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="loading-center"><div className="spinner" /><span>Loading dashboard…</span></div>
  )

  const hasData = summary && summary.record_count > 0

  if (!hasData) return (
    <div className="empty-state">
      <DollarSign size={40} style={{ color: 'var(--text-muted)', margin: '0 auto 12px', display:'block' }} />
      <div style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: 6 }}>No billing data yet</div>
      <div>Go to <strong>Data Upload</strong> to load a CSV and see AI insights here.</div>
    </div>
  )

  // Format daily data for chart (show last 60 days, label as Mmm dd)
  const chartData = daily.slice(-60).map(d => ({
    ...d,
    label: new Date(d.date + 'T00:00:00').toLocaleDateString('en-US', { month:'short', day:'numeric' })
  }))

  return (
    <>
      <div className="page-header">
        <div className="page-title">Overview</div>
        <div className="page-heading">Cost Dashboard</div>
      </div>

      <div className="page-body">

        {/* STAT CARDS */}
        <div className="section">
          <div className="grid-4">
            <StatCard
              label="Total Spend"
              value={`$${summary.total_cost.toLocaleString()}`}
              sub={`${summary.date_range.start} → ${summary.date_range.end}`}
            />
            <StatCard
              label="Potential Waste"
              value={insights?.waste_percentage ? `${insights.waste_percentage}%` : '—'}
              sub={`~$${insights?.total_potential_savings?.toLocaleString() ?? 0}/mo potential savings`}
              accent="danger"
            />
            <StatCard
              label="30-Day Forecast"
              value={insights?.prediction ? `$${insights.prediction.predicted_cost.toLocaleString()}` : '—'}
              sub={insights?.prediction ? `Trend: ${insights.prediction.trend}` : ''}
              accent={insights?.prediction?.trend === 'rising' ? 'danger' : 'accent'}
            />
            <StatCard
              label="Resources Tracked"
              value={summary.record_count.toLocaleString()}
              sub={`${summary.service_breakdown.length} services`}
            />
          </div>
        </div>

        {/* AI INSIGHT CARDS */}
        {insights?.headline_cards?.length > 0 && (
          <div className="section">
            <div className="section-title">AI Insights</div>
            <div className="grid-3">
              {insights.headline_cards.map((card, i) => {
                const Icon = ICON_MAP[card.icon] || DollarSign
                const colorCls = ICON_COLOR[card.icon] || 'blue'
                return (
                  <div key={i} className="insight-card">
                    <div className={`insight-icon ${colorCls}`}>
                      <Icon size={16} />
                    </div>
                    <div>
                      <div className="insight-title">{card.title}</div>
                      <div className="insight-msg">{card.message}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* CHARTS ROW */}
        <div className="grid-2-1" style={{ marginBottom: 28 }}>
          {/* Daily cost trend */}
          <div className="card" style={{ padding: '20px 20px 10px' }}>
            <div className="section-title" style={{ marginBottom: 16 }}>Daily Cost (last 60 days)</div>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#00d4aa" stopOpacity={0.18} />
                    <stop offset="95%" stopColor="#00d4aa" stopOpacity={0}    />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Space Mono' }}
                  tickLine={false} axisLine={false}
                  interval={Math.floor(chartData.length / 6)}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Space Mono' }}
                  tickLine={false} axisLine={false}
                  tickFormatter={v => `$${v}`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone" dataKey="cost"
                  stroke="#00d4aa" strokeWidth={2}
                  fill="url(#costGrad)" dot={false}
                  activeDot={{ r: 4, fill: '#00d4aa', stroke: '#0a0c0f', strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Service breakdown */}
          <div className="card" style={{ padding: '20px 20px 10px' }}>
            <div className="section-title" style={{ marginBottom: 16 }}>By Service</div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={summary.service_breakdown}
                layout="vertical"
                margin={{ top: 0, right: 8, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Space Mono' }}
                  tickLine={false} axisLine={false}
                  tickFormatter={v => `$${v}`}
                />
                <YAxis
                  type="category" dataKey="service"
                  tick={{ fontSize: 11, fill: 'var(--text-secondary)' }}
                  tickLine={false} axisLine={false}
                  width={55}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                  {summary.service_breakdown.map((_, i) => (
                    <Cell key={i} fill={SERVICE_COLORS[i % SERVICE_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>
    </>
  )
}
