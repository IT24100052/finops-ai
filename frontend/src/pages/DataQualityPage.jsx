import { useEffect, useState } from 'react'
import { Activity, CheckCircle, AlertTriangle } from 'lucide-react'
import { api } from '../api'

function ScoreGauge({ score }) {
  const color = score >= 80 ? 'var(--accent)' : score >= 60 ? 'var(--warn)' : 'var(--danger)'
  const grade = score >= 90 ? 'A+' : score >= 80 ? 'A' : score >= 70 ? 'B' : score >= 60 ? 'C' : score >= 50 ? 'D' : 'F'
  return (
    <div style={{ textAlign: 'center', padding: '20px 0' }}>
      <div style={{
        width: 120, height: 120, borderRadius: '50%', margin: '0 auto 16px',
        border: `6px solid ${color}`,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        boxShadow: `0 0 24px ${color}33`,
      }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.8rem', fontWeight: 700, color, lineHeight: 1 }}>
          {score.toFixed(0)}
        </div>
        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: 2 }}>/ 100</div>
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.4rem', fontWeight: 700, color }}>
        Grade: {grade}
      </div>
    </div>
  )
}

function DimensionBar({ dim }) {
  const color = dim.score >= 80 ? 'var(--accent)' : dim.score >= 60 ? 'var(--warn)' : 'var(--danger)'
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: '0.82rem', fontWeight: 500, color: 'var(--text-primary)' }}>{dim.name}</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color }}>
          {dim.score.toFixed(0)}/100 · weight {dim.weight}%
        </span>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${dim.score}%`, background: color }} />
      </div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>{dim.detail}</div>
    </div>
  )
}

export default function DataQualityPage() {
  const [quality, setQuality] = useState(null)
  const [score,   setScore]   = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.getDataQuality(), api.getFinopsScore()])
      .then(([q, s]) => { setQuality(q); setScore(s) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="loading-center"><div className="spinner" /><span>Analysing data quality…</span></div>
  )

  if (!quality || quality.total_records === 0) return (
    <div className="empty-state">
      <Activity size={36} style={{ color: 'var(--text-muted)', margin: '0 auto 12px', display:'block' }} />
      <div style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: 6 }}>No data to analyse</div>
      <div>Upload billing data to see data quality metrics.</div>
    </div>
  )

  const q = quality
  const qColor = q.score >= 80 ? 'var(--accent)' : q.score >= 60 ? 'var(--warn)' : 'var(--danger)'

  const issues = [
    { label: 'Total Records',       val: q.total_records.toLocaleString(),    ok: true },
    { label: 'Valid Records',        val: q.valid_records.toLocaleString(),     ok: true },
    { label: 'Invalid Records',      val: q.invalid_records,                    ok: q.invalid_records === 0 },
    { label: 'Duplicate Records',    val: q.duplicate_records,                  ok: q.duplicate_records === 0 },
    { label: 'Invalid Costs',        val: q.invalid_costs,                      ok: q.invalid_costs === 0 },
    { label: 'Invalid CPU Values',   val: q.invalid_cpu_values,                 ok: q.invalid_cpu_values === 0 },
    { label: 'Missing Provider',     val: `${q.missing_provider} rows`,         ok: q.missing_provider === 0 },
    { label: 'Missing Region',       val: `${q.missing_region} rows`,           ok: q.missing_region === 0 },
    { label: 'Missing Environment',  val: `${q.missing_environment} rows`,      ok: q.missing_environment === 0 },
    { label: 'Missing Team Tag',     val: `${q.missing_team} rows`,             ok: q.missing_team === 0 },
    { label: 'Untagged Resources',   val: `${q.missing_tags} resources`,        ok: q.missing_tags === 0 },
    { label: 'Tagging Coverage',     val: `${q.tagging_coverage_pct}%`,         ok: q.tagging_coverage_pct >= 80 },
  ]

  return (
    <>
      <div className="page-header">
        <div className="page-title">Governance</div>
        <div className="page-heading">Data Quality</div>
      </div>

      <div className="page-body">

        {/* Score + FinOps side by side */}
        <div className="grid-2 section">
          <div className="card">
            <div className="section-title" style={{ marginBottom: 8 }}>Data Quality Score</div>
            <ScoreGauge score={q.score} />
            <div style={{ textAlign: 'center', fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 8 }}>
              {q.score >= 90 ? 'Excellent data quality.' :
               q.score >= 70 ? 'Good quality with minor issues.' :
               'Data issues detected — review recommendations.'}
            </div>
          </div>

          {score && (
            <div className="card">
              <div className="section-title" style={{ marginBottom: 8 }}>FinOps Health Score</div>
              <ScoreGauge score={score.score} />
              <div style={{ textAlign: 'center', fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 8 }}>
                {score.explanation}
              </div>
            </div>
          )}
        </div>

        {/* FinOps score dimensions */}
        {score?.dimensions?.length > 0 && (
          <div className="card section">
            <div className="section-title" style={{ marginBottom: 16 }}>FinOps Score Breakdown</div>
            {score.dimensions.map((d, i) => <DimensionBar key={i} dim={d} />)}
          </div>
        )}

        {/* Data quality issue table */}
        <div className="grid-2 section" style={{ alignItems: 'start' }}>
          <div className="card">
            <div className="section-title" style={{ marginBottom: 12 }}>Quality Metrics</div>
            {issues.map((item, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '8px 0', borderBottom: i < issues.length - 1 ? '1px solid var(--border)' : 'none'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.82rem' }}>
                  {item.ok
                    ? <CheckCircle size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                    : <AlertTriangle size={13} style={{ color: 'var(--warn)', flexShrink: 0 }} />
                  }
                  <span style={{ color: 'var(--text-secondary)' }}>{item.label}</span>
                </div>
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: '0.78rem',
                  color: item.ok ? 'var(--text-primary)' : 'var(--warn)'
                }}>{item.val}</span>
              </div>
            ))}
          </div>

          <div className="card">
            <div className="section-title" style={{ marginBottom: 12 }}>Recommendations</div>
            {q.recommendations.length === 0 ? (
              <div style={{ fontSize: '0.82rem', color: 'var(--accent)' }}>
                <CheckCircle size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                All data quality checks passed.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {q.recommendations.map((r, i) => (
                  <div key={i} style={{
                    background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)',
                    padding: '10px 14px', fontSize: '0.82rem', color: 'var(--text-secondary)',
                    borderLeft: '3px solid var(--warn)', lineHeight: 1.5
                  }}>
                    {r}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

      </div>
    </>
  )
}
