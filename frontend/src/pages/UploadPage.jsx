import { useState, useRef } from 'react'
import { Upload, FileText, CheckCircle, XCircle, Trash2, Download } from 'lucide-react'
import { api } from '../api'

const SAMPLE_HEADER = 'date,service,resource_id,instance_type,usage_hours,avg_cpu_utilization,storage_gb,cost'
const SAMPLE_ROWS = [
  '2026-06-01,EC2,i-web-01,m5.large,24.0,72.3,,2.18',
  '2026-06-01,EC2,i-idle-01,m5.xlarge,24.0,1.4,,4.21',
  '2026-06-01,S3,s3-logs,,0,,,0.43,1800',
  '2026-06-01,RDS,db-prod,db.r5.large,24.0,55.0,,3.90',
]

function downloadSampleCSV() {
  const content = [SAMPLE_HEADER, ...SAMPLE_ROWS].join('\n')
  const blob = new Blob([content], { type: 'text/csv' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = 'sample_billing_data.csv'
  a.click()
  URL.revokeObjectURL(url)
}

export default function UploadPage() {
  const [dragOver,  setDragOver]  = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result,    setResult]    = useState(null)
  const [clearing,  setClearing]  = useState(false)
  const inputRef = useRef()

  async function handleFile(file) {
    if (!file) return
    setResult(null)
    setUploading(true)
    try {
      const res = await api.uploadCSV(file)
      setResult({ ok: true, ...res })
    } catch (e) {
      setResult({ ok: false, error: e.message })
    } finally {
      setUploading(false)
    }
  }

  async function handleClear() {
    if (!window.confirm('Delete all your billing data? This cannot be undone.')) return
    setClearing(true)
    try {
      const res = await api.clearBilling()
      setResult({ ok: true, cleared: true, deleted_rows: res.deleted_rows })
    } catch (e) {
      setResult({ ok: false, error: e.message })
    } finally {
      setClearing(false)
    }
  }

  return (
    <>
      <div className="page-header">
        <div className="page-title">Data</div>
        <div className="page-heading">Upload Billing Data</div>
      </div>

      <div className="page-body" style={{ maxWidth: 640 }}>

        {/* Format info */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
            <div className="section-title" style={{ marginBottom:0 }}>Required CSV format</div>
            <button className="btn btn-ghost" style={{ fontSize:'0.75rem', padding:'5px 12px' }} onClick={downloadSampleCSV}>
              <Download size={13} /> Download sample
            </button>
          </div>
          <div style={{ fontFamily:'var(--font-mono)', fontSize:'0.72rem', color:'var(--text-secondary)', lineHeight:1.8 }}>
            <div style={{ color:'var(--accent)', marginBottom:4 }}>{SAMPLE_HEADER}</div>
            {SAMPLE_ROWS.map((r,i) => <div key={i} style={{ color:'var(--text-muted)' }}>{r}</div>)}
          </div>
          <div className="divider" />
          <div style={{ fontSize:'0.78rem', color:'var(--text-secondary)', lineHeight:1.6 }}>
            <strong style={{ color:'var(--text-primary)' }}>Required:</strong> date, service, resource_id, cost.<br />
            <strong style={{ color:'var(--text-primary)' }}>Optional:</strong> instance_type, usage_hours, avg_cpu_utilization, storage_gb.<br />
            For accurate waste detection, include <code style={{ fontFamily:'var(--font-mono)', color:'var(--accent)' }}>avg_cpu_utilization</code> (0–100) and <code style={{ fontFamily:'var(--font-mono)', color:'var(--accent)' }}>usage_hours</code>.
          </div>
        </div>

        {/* Upload zone */}
        <div
          className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
          style={{ marginBottom: 16 }}
          onClick={() => inputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => {
            e.preventDefault()
            setDragOver(false)
            handleFile(e.dataTransfer.files[0])
          }}
        >
          {uploading ? (
            <>
              <div className="spinner" style={{ margin:'0 auto 12px' }} />
              <div style={{ color:'var(--text-secondary)', fontSize:'0.9rem' }}>Uploading and processing…</div>
            </>
          ) : (
            <>
              <Upload size={32} className="upload-icon" />
              <div style={{ fontSize:'0.92rem', color:'var(--text-primary)' }}>
                Drop your CSV here, or <span style={{ color:'var(--accent)' }}>click to browse</span>
              </div>
              <div className="upload-hint">AWS CUR, Azure Cost Export, or the sample format above</div>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            style={{ display:'none' }}
            onChange={e => handleFile(e.target.files[0])}
          />
        </div>

        {/* Result banner */}
        {result && (
          <div style={{
            padding: '14px 18px',
            borderRadius: 'var(--radius-md)',
            marginBottom: 16,
            background: result.ok ? 'var(--accent-dim)' : 'var(--danger-dim)',
            border: `1px solid ${result.ok ? 'rgba(0,212,170,0.25)' : 'rgba(255,77,109,0.25)'}`,
            display: 'flex', alignItems: 'flex-start', gap: 12,
          }}>
            {result.ok
              ? <CheckCircle size={18} style={{ color:'var(--accent)', flexShrink:0, marginTop:1 }} />
              : <XCircle    size={18} style={{ color:'var(--danger)', flexShrink:0, marginTop:1 }} />
            }
            <div style={{ fontSize:'0.82rem', color:'var(--text-primary)', lineHeight:1.5 }}>
              {result.cleared
                ? `Cleared ${result.deleted_rows} billing records successfully.`
                : result.ok
                  ? <>
                      <strong>{result.rows_inserted.toLocaleString()} rows imported</strong> from {result.filename}.
                      {result.rows_failed > 0 && <> {result.rows_failed} rows skipped.</>}
                      {' '}<a href="/" style={{ color:'var(--accent)' }}>Go to dashboard →</a>
                    </>
                  : `Upload failed: ${result.error}`
              }
              {result.ok && result.errors?.length > 0 && (
                <div style={{ marginTop:6, color:'var(--text-muted)', fontFamily:'var(--font-mono)', fontSize:'0.7rem' }}>
                  Sample errors: {result.errors.slice(0,3).join(' | ')}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Clear data */}
        <div className="divider" />
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          <div>
            <div style={{ fontSize:'0.85rem', fontWeight:500, color:'var(--text-primary)', marginBottom:2 }}>Clear all data</div>
            <div style={{ fontSize:'0.78rem', color:'var(--text-muted)' }}>Remove all uploaded billing records for your account.</div>
          </div>
          <button className="btn btn-danger" onClick={handleClear} disabled={clearing}>
            <Trash2 size={14} /> {clearing ? 'Clearing…' : 'Clear data'}
          </button>
        </div>

      </div>
    </>
  )
}
