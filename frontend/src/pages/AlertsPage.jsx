import { useEffect, useState } from 'react'
import { AlertTriangle, TrendingUp, Zap, CheckCircle, Bell } from 'lucide-react'
import { api } from '../api'

function generateAlerts(summary, prediction, waste) {
  const alerts = []

  if (!summary || !summary.record_count) return alerts

  const dailySpend = summary.total_cost / 90 // rough daily avg from ~90 days data

  // Alert: rapidly rising costs
  if (prediction?.trend === 'rising') {
    alerts.push({
      severity: 'high',
      icon: TrendingUp,
      title: 'Rising Cost Trend Detected',
      message: `Your cloud spend shows an upward trend. The AI forecasts $${prediction.predicted_cost.toLocaleString()} over the next 30 days. Investigate resource growth before costs compound.`,
    })
  }

  // Alert: waste > 25%
  if (waste?.length > 0) {
    const totalWaste  = waste.reduce((s, f) => s + f.estimated_monthly_savings, 0)
    const wasteRatio  = totalWaste / (summary.total_cost / 3) // 3 months → monthly
    if (wasteRatio > 0.25) {
      alerts.push({
        severity: 'high',
        icon: AlertTriangle,
        title: `High Waste Ratio — ${(wasteRatio * 100).toFixed(0)}% of Budget`,
        message: `${waste.filter(f => f.severity === 'high').length} idle or critically oversized resources are costing ~$${totalWaste.toLocaleString(undefined,{maximumFractionDigits:0})}/month unnecessarily.`,
      })
    }
  }

  // Alert: idle high-cost resources
  const idleResources = waste?.filter(f => f.issue === 'Idle resource' && f.monthly_cost > 50) ?? []
  if (idleResources.length > 0) {
    alerts.push({
      severity: 'high',
      icon: Zap,
      title: `${idleResources.length} Idle High-Cost Resource${idleResources.length > 1 ? 's' : ''}`,
      message: `Resources running at <5% CPU: ${idleResources.map(r => r.resource_id).join(', ')}. These can likely be stopped or scheduled.`,
    })
  }

  // Alert: single service dominates (>60%)
  if (summary.service_breakdown?.length > 1) {
    const top     = summary.service_breakdown[0]
    const topRatio = top.cost / summary.total_cost
    if (topRatio > 0.6) {
      alerts.push({
        severity: 'medium',
        icon: AlertTriangle,
        title: `${top.service} is ${(topRatio * 100).toFixed(0)}% of Total Spend`,
        message: `Heavy concentration in one service can indicate over-provisioning. Consider reviewing ${top.service} resource tiers and reserved-instance pricing.`,
      })
    }
  }

  // Alert: anomalous cost spikes from waste engine
  const anomalies = waste?.filter(f => f.issue === 'Anomalous cost pattern') ?? []
  if (anomalies.length > 0) {
    alerts.push({
      severity: 'medium',
      icon: Zap,
      title: `${anomalies.length} Anomalous Cost Pattern${anomalies.length > 1 ? 's' : ''} (ML Detected)`,
      message: `Isolation Forest flagged ${anomalies.map(a => a.resource_id).join(', ')} as having abnormal cost relative to actual usage. May indicate a billing leak or misconfiguration.`,
    })
  }

  // Info: forecast within budget (only if no high alerts)
  if (prediction && prediction.trend === 'flat' && alerts.filter(a => a.severity === 'high').length === 0) {
    alerts.push({
      severity: 'low',
      icon: CheckCircle,
      title: 'Spend Stable — No Critical Issues',
      message: `Cost trend is flat. Forecast for next 30 days: $${prediction.predicted_cost.toLocaleString()}. Continue monitoring for drift.`,
    })
  }

  return alerts
}

export default function AlertsPage() {
  const [alerts,  setAlerts]  = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.getSummary(), api.getPrediction(30), api.getWaste()])
      .then(([s, p, w]) => setAlerts(generateAlerts(s, p, w)))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const colorMap = { high: 'var(--danger)', medium: 'var(--warn)', low: 'var(--accent)' }
  const bgMap    = { high: 'var(--danger-dim)', medium: 'var(--warn-dim)', low: 'var(--accent-dim)' }
  const borderMap= { high: 'rgba(255,77,109,0.18)', medium: 'rgba(245,158,11,0.18)', low: 'rgba(0,212,170,0.18)' }

  return (
    <>
      <div className="page-header">
        <div className="page-title">Monitoring</div>
        <div className="page-heading">Alerts & Warnings</div>
      </div>

      <div className="page-body">
        {loading ? (
          <div className="loading-center"><div className="spinner" /><span>Evaluating alert conditions…</span></div>
        ) : alerts.length === 0 ? (
          <div className="empty-state">
            <Bell size={36} style={{ color:'var(--text-muted)', margin:'0 auto 12px', display:'block' }} />
            <div>No data yet — upload a billing CSV to generate alerts.</div>
          </div>
        ) : (
          <>
            {/* Summary counts */}
            <div className="grid-3" style={{ marginBottom: 24 }}>
              {['high','medium','low'].map(sev => {
                const count = alerts.filter(a => a.severity === sev).length
                return (
                  <div className="card" key={sev}>
                    <div className="card-label">{sev.charAt(0).toUpperCase() + sev.slice(1)} Priority</div>
                    <div className="card-value" style={{ color: colorMap[sev] }}>{count}</div>
                    <div className="card-sub">active alert{count !== 1 ? 's' : ''}</div>
                  </div>
                )
              })}
            </div>

            {/* Alert cards */}
            <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
              {alerts.map((alert, i) => {
                const Icon = alert.icon
                return (
                  <div
                    key={i}
                    style={{
                      background: bgMap[alert.severity],
                      border: `1px solid ${borderMap[alert.severity]}`,
                      borderRadius: 'var(--radius-md)',
                      padding: '16px 18px',
                      display: 'flex',
                      gap: 14,
                      alignItems: 'flex-start',
                    }}
                  >
                    <div style={{
                      width: 36, height: 36, borderRadius: 'var(--radius-sm)',
                      background: 'rgba(0,0,0,0.2)',
                      display:'flex', alignItems:'center', justifyContent:'center',
                      flexShrink: 0, color: colorMap[alert.severity],
                    }}>
                      <Icon size={16} />
                    </div>
                    <div style={{ flex:1 }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:8, marginBottom:4 }}>
                        <div style={{ fontSize:'0.88rem', fontWeight:600, color:'var(--text-primary)' }}>
                          {alert.title}
                        </div>
                        <span className={`badge badge-${alert.severity}`} style={{ flexShrink:0 }}>
                          {alert.severity}
                        </span>
                      </div>
                      <div style={{ fontSize:'0.82rem', color:'var(--text-secondary)', lineHeight:1.5 }}>
                        {alert.message}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </>
        )}
      </div>
    </>
  )
}
