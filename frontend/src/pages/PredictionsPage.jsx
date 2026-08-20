import { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'
import { api } from '../api'

const HORIZON_OPTIONS = [7, 14, 30, 60, 90]

function TrendPill({ trend }) {
  if (trend === 'rising')  return <span className="trend-badge trend-rising"><TrendingUp size={11} /> Rising</span>
  if (trend === 'falling') return <span className="trend-badge trend-falling"><TrendingDown size={11} /> Falling</span>
  return <span className="trend-badge trend-flat"><Minus size={11} /> Flat</span>
}

function PredTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const vals = Object.fromEntries(payload.map(p => [p.name, p.value]))
  return (
    <div className="card" style={{ padding: '10px 14px', minWidth: 150 }}>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
      {vals.actual    != null && <div style={{ color: 'var(--accent)',    fontFamily:'var(--font-mono)', fontSize:'0.82rem' }}>Actual: ${vals.actual?.toFixed(2)}</div>}
      {vals.predicted != null && <div style={{ color: 'var(--warn)',     fontFamily:'var(--font-mono)', fontSize:'0.82rem' }}>Forecast: ${vals.predicted?.toFixed(2)}</div>}
    </div>
  )
}

export default function PredictionsPage() {
  const [prediction, setPrediction] = useState(null)
  const [daily,      setDaily]      = useState([])
  const [horizon,    setHorizon]    = useState(30)
  const [loading,    setLoading]    = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([api.getPrediction(horizon), api.getDailyCosts()])
      .then(([p, d]) => { setPrediction(p); setDaily(d) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [horizon])

  // Build unified chart: last 30 actual days + projected future days
  const chartData = (() => {
    if (!prediction || !daily.length) return []
    const actualDays = daily.slice(-30).map(d => ({
      label: new Date(d.date + 'T00:00:00').toLocaleDateString('en-US', { month:'short', day:'numeric' }),
      actual: d.cost,
      predicted: null,
      band_lo: null,
      band_hi: null,
    }))

    const lastDate  = new Date(daily[daily.length - 1].date + 'T00:00:00')
    const dailyPred = prediction.predicted_cost / horizon
    const dailyLo   = prediction.lower_bound    / horizon
    const dailyHi   = prediction.upper_bound    / horizon

    const futureDays = Array.from({ length: Math.min(horizon, 30) }, (_, i) => {
      const d = new Date(lastDate)
      d.setDate(d.getDate() + i + 1)
      return {
        label:     d.toLocaleDateString('en-US', { month:'short', day:'numeric' }),
        actual:    null,
        predicted: +dailyPred.toFixed(2),
        band_lo:   +dailyLo.toFixed(2),
        band_hi:   +dailyHi.toFixed(2),
      }
    })

    return [...actualDays, ...futureDays]
  })()

  const splitIdx = daily.slice(-30).length

  return (
    <>
      <div className="page-header">
        <div className="page-title">AI Module</div>
        <div className="page-heading">Cost Predictions</div>
      </div>

      <div className="page-body">

        {/* Horizon selector */}
        <div className="section" style={{ display:'flex', gap: 8, alignItems:'center' }}>
          <span style={{ fontSize:'0.78rem', color:'var(--text-muted)', marginRight:4 }}>Forecast horizon:</span>
          {HORIZON_OPTIONS.map(h => (
            <button
              key={h}
              onClick={() => setHorizon(h)}
              className="btn btn-ghost"
              style={{
                padding: '5px 12px', fontSize: '0.78rem',
                background: horizon === h ? 'var(--accent-dim)' : undefined,
                color:      horizon === h ? 'var(--accent)'     : undefined,
                borderColor:horizon === h ? 'var(--accent)'     : undefined,
              }}
            >
              {h}d
            </button>
          ))}
        </div>

        {loading ? (
          <div className="loading-center"><div className="spinner" /><span>Running prediction model…</span></div>
        ) : !prediction ? (
          <div className="empty-state">Upload billing data first to enable predictions.</div>
        ) : prediction.message ? (
          <div className="empty-state">{prediction.message}</div>
        ) : (
          <>
            {/* Summary cards */}
            <div className="grid-4" style={{ marginBottom: 14 }}>
              <div className="card">
                <div className="card-label">Predicted ({horizon}d)</div>
                <div className="card-value accent">${prediction.predicted_cost.toLocaleString()}</div>
                <div className="card-sub">total estimated spend</div>
              </div>
              <div className="card">
                <div className="card-label">Range</div>
                <div className="card-value" style={{ fontSize:'1.1rem' }}>
                  ${prediction.lower_bound.toLocaleString()} – ${prediction.upper_bound.toLocaleString()}
                </div>
                <div className="card-sub">confidence band</div>
              </div>
              <div className="card">
                <div className="card-label">Daily Avg (recent)</div>
                <div className="card-value">${prediction.daily_avg_recent}</div>
                <div className="card-sub">last 7-day window</div>
              </div>
              <div className="card">
                <div className="card-label">Trend</div>
                <div style={{ marginTop: 8 }}><TrendPill trend={prediction.trend} /></div>
                <div className="card-sub" style={{ marginTop: 6 }}>
                  {prediction.confidence && <span className={`badge badge-${prediction.confidence === 'high' ? 'ok' : prediction.confidence === 'medium' ? 'medium' : 'low'}`}>{prediction.confidence} confidence</span>}
                </div>
              </div>
            </div>
            {/* Extra row: historical avg + change + explanation */}
            <div className="grid-3" style={{ marginBottom: 24 }}>
              <div className="card">
                <div className="card-label">Historical Average</div>
                <div className="card-value" style={{ fontSize:'1.1rem' }}>
                  ${prediction.historical_average?.toLocaleString() || '—'}
                </div>
                <div className="card-sub">daily average over all history</div>
              </div>
              <div className="card">
                <div className="card-label">Forecast vs History</div>
                <div className="card-value" style={{
                  fontSize:'1.1rem',
                  color: prediction.forecast_change_percentage > 3 ? 'var(--danger)' : prediction.forecast_change_percentage < -3 ? 'var(--accent)' : 'var(--text-primary)'
                }}>
                  {prediction.forecast_change_percentage > 0 ? '+' : ''}{prediction.forecast_change_percentage?.toFixed(1) || 0}%
                </div>
                <div className="card-sub">vs historical daily average</div>
              </div>
              <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <div className="card-label">AI Explanation</div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {prediction.explanation || 'No explanation available.'}
                </div>
              </div>
            </div>

            {/* Forecast chart */}
            <div className="card" style={{ padding: '20px 20px 10px' }}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16 }}>
                <div className="section-title" style={{ marginBottom:0 }}>
                  Historical (30d) + {horizon}-day Forecast
                </div>
                <div style={{ display:'flex', gap:16, fontSize:'0.72rem', color:'var(--text-muted)' }}>
                  <span style={{ display:'flex', alignItems:'center', gap:5 }}>
                    <span style={{ display:'inline-block', width:16, height:2, background:'var(--accent)' }}/>
                    Actual
                  </span>
                  <span style={{ display:'flex', alignItems:'center', gap:5 }}>
                    <span style={{ display:'inline-block', width:16, height:2, background:'var(--warn)' }}/>
                    Forecast
                  </span>
                  <span style={{ display:'flex', alignItems:'center', gap:5 }}>
                    <span style={{ display:'inline-block', width:16, height:8, background:'rgba(245,158,11,0.15)', borderRadius:2 }}/>
                    Confidence band
                  </span>
                </div>
              </div>

              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={chartData} margin={{ top:4, right:4, left:-8, bottom:0 }}>
                  <defs>
                    <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#f59e0b" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}   />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize:10, fill:'var(--text-muted)', fontFamily:'Space Mono' }}
                    tickLine={false} axisLine={false}
                    interval={Math.floor(chartData.length / 8)}
                  />
                  <YAxis
                    tick={{ fontSize:10, fill:'var(--text-muted)', fontFamily:'Space Mono' }}
                    tickLine={false} axisLine={false}
                    tickFormatter={v => `$${v}`}
                  />
                  <Tooltip content={<PredTooltip />} />
                  <ReferenceLine
                    x={chartData[splitIdx - 1]?.label}
                    stroke="var(--border-bright)"
                    strokeDasharray="4 4"
                    label={{ value:'Today', fill:'var(--text-muted)', fontSize:10, position:'top' }}
                  />
                  {/* Confidence band */}
                  <Area
                    type="monotone" dataKey="band_hi" name="band_hi"
                    stroke="none" fill="url(#bandGrad)"
                    legendType="none" tooltipType="none"
                    connectNulls={false}
                  />
                  <Area
                    type="monotone" dataKey="band_lo" name="band_lo"
                    stroke="none" fill="var(--bg-base)"
                    legendType="none" tooltipType="none"
                    connectNulls={false}
                  />
                  <Line
                    type="monotone" dataKey="actual" name="actual"
                    stroke="var(--accent)" strokeWidth={2} dot={false}
                    connectNulls={false}
                    activeDot={{ r:4, fill:'var(--accent)', stroke:'var(--bg-base)', strokeWidth:2 }}
                  />
                  <Line
                    type="monotone" dataKey="predicted" name="predicted"
                    stroke="var(--warn)" strokeWidth={2} dot={false}
                    strokeDasharray="6 3"
                    connectNulls={false}
                    activeDot={{ r:4, fill:'var(--warn)', stroke:'var(--bg-base)', strokeWidth:2 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Model note */}
            <div style={{ marginTop:12, fontSize:'0.72rem', color:'var(--text-muted)', lineHeight:1.5 }}>
              <strong style={{ color:'var(--text-secondary)' }}>Model:</strong> Linear regression on daily totals (OLS, numpy polyfit).
              Confidence band = residual std × √horizon. Swap in LSTM for non-linear spend patterns.
            </div>
          </>
        )}
      </div>
    </>
  )
}
