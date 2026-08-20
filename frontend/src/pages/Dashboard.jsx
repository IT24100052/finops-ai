import { useEffect, useState, useCallback } from 'react'
import {
  TrendingDown, Calendar, AlertTriangle, DollarSign,
  Award, Server, Zap, BarChart2, RefreshCw
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar, Cell,
  PieChart, Pie, Legend
} from 'recharts'
import { api } from '../api'

const PALETTE = ['#00d4aa','#3b82f6','#f59e0b','#ff4d6d','#8b5cf6','#ec4899','#14b8a6','#f97316']

// ── Sub-components ──────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, accent, icon: Icon }) {
  return (
    <div className="card kpi-card">
      {Icon && (
        <div className={`kpi-icon ${accent || 'neutral'}`}>
          <Icon size={16} />
        </div>
      )}
      <div className="card-label">{label}</div>
      <div className={`card-value ${accent || ''}`}>{value}</div>
      {sub && <div className="card-sub">{sub}</div>}
    </div>
  )
}

function ChartCard({ title, children, style }) {
  return (
    <div className="card" style={{ padding: '18px 18px 10px', ...style }}>
      <div className="section-title" style={{ marginBottom: 14 }}>{title}</div>
      {children}
    </div>
  )
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="card" style={{ padding: '8px 12px', minWidth: 110, fontSize: '0.8rem' }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 2, fontSize: '0.7rem' }}>{label}</div>
      <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
        ${Number(payload[0].value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </div>
    </div>
  )
}

const ICON_MAP = {
  'trending-down': TrendingDown,
  'calendar':       Calendar,
  'alert-triangle': AlertTriangle,
  'award':          Award,
}
const ICON_COLOR = {
  'trending-down': 'teal',
  'calendar':       'blue',
  'alert-triangle': 'red',
  'award':          'amber',
}

// ── Filter bar ───────────────────────────────────────────────────────────────

function FilterBar({ filters, onChange, providers, regions, environments }) {
  return (
    <div className="filter-bar">
      <span className="filter-label">Filter:</span>
      <select className="filter-select" value={filters.provider || ''} onChange={e => onChange('provider', e.target.value)}>
        <option value="">All Providers</option>
        {providers.map(p => <option key={p} value={p}>{p}</option>)}
      </select>
      <select className="filter-select" value={filters.region || ''} onChange={e => onChange('region', e.target.value)}>
        <option value="">All Regions</option>
        {regions.map(r => <option key={r} value={r}>{r}</option>)}
      </select>
      <select className="filter-select" value={filters.environment || ''} onChange={e => onChange('environment', e.target.value)}>
        <option value="">All Environments</option>
        {environments.map(e => <option key={e} value={e}>{e}</option>)}
      </select>
      {(filters.provider || filters.region || filters.environment) && (
        <button className="btn btn-ghost" style={{ padding: '5px 10px', fontSize: '0.78rem' }}
          onClick={() => onChange('__clear')}>
          <RefreshCw size={12} /> Clear
        </button>
      )}
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────

export default function Dashboard() {
  const [summary,   setSummary]   = useState(null)
  const [daily,     setDaily]     = useState([])
  const [insights,  setInsights]  = useState(null)
  const [byProvider, setByProvider] = useState([])
  const [byEnv,     setByEnv]     = useState([])
  const [byTeam,    setByTeam]    = useState([])
  const [loading,   setLoading]   = useState(true)
  const [filters,   setFilters]   = useState({})
  const [providers, setProviders] = useState([])
  const [regions,   setRegions]   = useState([])
  const [environments, setEnvironments] = useState([])

  const loadData = useCallback(async (activeFilters = {}) => {
    setLoading(true)
    try {
      const [s, d, ins, prov, env, team] = await Promise.all([
        api.getSummary(activeFilters),
        api.getDailyCosts(activeFilters),
        api.getInsights(),
        api.getByProvider(activeFilters),
        api.getByEnvironment(activeFilters),
        api.getByTeam(activeFilters),
      ])
      setSummary(s)
      setDaily(d)
      setInsights(ins)
      setByProvider(prov || [])
      setByEnv(env || [])
      setByTeam(team || [])

      // Populate filter options from unfiltered summary
      if (s.providers) setProviders(s.providers)
      if (s.regions) setRegions(s.regions)
      // Derive environments from by-env data
      setEnvironments(['production','staging','development'])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData({}) }, [loadData])

  const handleFilter = (key, value) => {
    if (key === '__clear') {
      setFilters({})
      loadData({})
    } else {
      const next = { ...filters, [key]: value || undefined }
      setFilters(next)
      loadData(next)
    }
  }

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

  const chartData = daily.slice(-60).map(d => ({
    ...d,
    label: new Date(d.date + 'T00:00:00').toLocaleDateString('en-US', { month:'short', day:'numeric' })
  }))

  const pred = insights?.prediction
  const waste = insights?.waste_percentage
  const savings = insights?.total_potential_savings
  const finopsScore = insights?.finops_score
  const finopsGrade = insights?.finops_grade
  const dailyAvg = summary?.daily_average
  const resourceCount = summary?.resource_count || 0

  // Grade color
  const gradeColor = finopsScore >= 80 ? 'accent' : finopsScore >= 60 ? 'warn' : 'danger'

  return (
    <>
      <div className="page-header">
        <div className="page-title">Overview</div>
        <div className="page-heading">Cost Dashboard</div>
      </div>

      <div className="page-body">

        {/* FILTER BAR */}
        <FilterBar
          filters={filters}
          onChange={handleFilter}
          providers={providers}
          regions={regions}
          environments={environments}
        />

        {/* KPI CARDS — 4 columns × 2 rows */}
        <div className="section">
          <div className="grid-4">
            <KpiCard
              label="Total Spend"
              value={`$${summary.total_cost.toLocaleString()}`}
              sub={summary.date_range ? `${summary.date_range.start} → ${summary.date_range.end}` : ''}
              icon={DollarSign}
            />
            <KpiCard
              label="Daily Average"
              value={dailyAvg ? `$${dailyAvg.toLocaleString()}` : '—'}
              sub={`across ${summary.record_count.toLocaleString()} records`}
              icon={BarChart2}
              accent="accent"
            />
            <KpiCard
              label="30-Day Forecast"
              value={pred ? `$${pred.predicted_cost.toLocaleString()}` : '—'}
              sub={pred ? `Trend: ${pred.trend} · ${pred.confidence} confidence` : ''}
              accent={pred?.trend === 'rising' ? 'danger' : 'accent'}
              icon={TrendingDown}
            />
            <KpiCard
              label="Potential Savings"
              value={savings != null ? `$${savings.toLocaleString()}` : '—'}
              sub={waste != null ? `${waste}% of total spend` : ''}
              accent="danger"
              icon={Zap}
            />
          </div>
          <div className="grid-4" style={{ marginTop: 14 }}>
            <KpiCard
              label="Resources Tracked"
              value={resourceCount.toLocaleString()}
              sub={`${summary.service_breakdown.length} services`}
              icon={Server}
            />
            <KpiCard
              label="Cloud Providers"
              value={summary.providers?.length || 1}
              sub={summary.providers?.join(' · ') || 'Generic'}
              icon={BarChart2}
              accent="accent"
            />
            <KpiCard
              label="Waste Ratio"
              value={waste != null ? `${waste}%` : '—'}
              sub="of budget potentially wasted"
              accent={waste > 30 ? 'danger' : waste > 15 ? 'warn' : 'accent'}
              icon={AlertTriangle}
            />
            <KpiCard
              label="FinOps Score"
              value={finopsScore != null ? `${finopsScore}/100` : '—'}
              sub={finopsGrade ? `Grade: ${finopsGrade}` : ''}
              accent={gradeColor}
              icon={Award}
            />
          </div>
        </div>

        {/* AI INSIGHT CARDS */}
        {insights?.headline_cards?.length > 0 && (
          <div className="section">
            <div className="section-title">AI Insights</div>
            <div className="grid-2" style={{ gridTemplateColumns: 'repeat(2,1fr)' }}>
              {insights.headline_cards.map((card, i) => {
                const Icon = ICON_MAP[card.icon] || DollarSign
                const colorCls = ICON_COLOR[card.icon] || 'blue'
                return (
                  <div key={i} className="insight-card">
                    <div className={`insight-icon ${colorCls}`}><Icon size={16} /></div>
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

        {/* CHARTS ROW 1: Daily + Service */}
        <div className="grid-2-1" style={{ marginBottom: 16 }}>
          <ChartCard title="Daily Cost Trend (last 60 days)">
            <ResponsiveContainer width="100%" height={210}>
              <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#00d4aa" stopOpacity={0.18} />
                    <stop offset="95%" stopColor="#00d4aa" stopOpacity={0}    />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Space Mono' }}
                  tickLine={false} axisLine={false} interval={Math.floor(chartData.length / 6)} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Space Mono' }}
                  tickLine={false} axisLine={false} tickFormatter={v => `$${v}`} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="cost" stroke="#00d4aa" strokeWidth={2}
                  fill="url(#costGrad)" dot={false}
                  activeDot={{ r: 4, fill: '#00d4aa', stroke: '#0a0c0f', strokeWidth: 2 }} />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="By Service">
            <ResponsiveContainer width="100%" height={210}>
              <BarChart data={summary.service_breakdown} layout="vertical"
                margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Space Mono' }}
                  tickLine={false} axisLine={false} tickFormatter={v => `$${v}`} />
                <YAxis type="category" dataKey="service"
                  tick={{ fontSize: 11, fill: 'var(--text-secondary)' }}
                  tickLine={false} axisLine={false} width={80} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                  {summary.service_breakdown.map((_, i) => (
                    <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>

        {/* CHARTS ROW 2: Provider + Environment + Team */}
        <div className="grid-3" style={{ marginBottom: 16 }}>
          <ChartCard title="By Provider">
            {byProvider.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '40px 0', textAlign: 'center' }}>
                No provider data — add a 'provider' column to your CSV.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={byProvider} dataKey="cost" nameKey="provider" cx="50%" cy="50%"
                    outerRadius={65} innerRadius={30} paddingAngle={3}>
                    {byProvider.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                  </Pie>
                  <Tooltip formatter={(v) => `$${Number(v).toLocaleString(undefined,{maximumFractionDigits:2})}`} />
                  <Legend iconSize={8} wrapperStyle={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard title="By Environment">
            {byEnv.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '40px 0', textAlign: 'center' }}>
                No environment data.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={byEnv} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                  <XAxis type="number" tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                    tickLine={false} axisLine={false} tickFormatter={v => `$${v}`} />
                  <YAxis type="category" dataKey="environment" width={85}
                    tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} tickLine={false} axisLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                    {byEnv.map((d, i) => {
                      const c = d.environment?.toLowerCase()
                      const fill = c === 'production' ? '#00d4aa' : c === 'staging' ? '#f59e0b' : '#3b82f6'
                      return <Cell key={i} fill={fill} />
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard title="By Team">
            {byTeam.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '40px 0', textAlign: 'center' }}>
                No team data — add a 'team' column to your CSV.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={byTeam.slice(0, 6)} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                  <XAxis type="number" tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                    tickLine={false} axisLine={false} tickFormatter={v => `$${v}`} />
                  <YAxis type="category" dataKey="team" width={75}
                    tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} tickLine={false} axisLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                    {byTeam.slice(0, 6).map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </div>

      </div>
    </>
  )
}
