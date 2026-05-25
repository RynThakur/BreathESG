import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getDashboard } from '../api/client'

const CATEGORY_LABELS = {
  fuel_stationary: 'Stationary Combustion',
  fuel_mobile: 'Mobile Combustion',
  electricity: 'Purchased Electricity',
  travel_flight: 'Flights',
  travel_hotel: 'Hotels',
  travel_ground: 'Ground Transport',
  procurement: 'Procurement',
}

function ScopeBar({ by_scope }) {
  const total = Object.values(by_scope).reduce((s, v) => s + v.count, 0)
  if (!total) return null
  return (
    <div>
      <div className="scope-bar">
        {Object.entries(by_scope).map(([s, v]) => (
          <div key={s} className={`scope-bar-seg scope-${s}-bg`}
            style={{width: `${(v.count/total*100).toFixed(1)}%`, background: s==='1'?'#f97316':s==='2'?'#3b82f6':'#a855f7', opacity:0.8}} />
        ))}
      </div>
      <div style={{display:'flex', gap:16, marginTop:10}}>
        {Object.entries(by_scope).map(([s, v]) => (
          <div key={s} style={{display:'flex', alignItems:'center', gap:6}}>
            <span className={`scope-badge scope-${s}`}>S{s}</span>
            <span style={{fontSize:12, color:'var(--text-muted)'}}>{v.count} records</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getDashboard()
      .then(r => setStats(r.data))
      .catch(() => setError('Failed to load dashboard'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="page"><div className="spinner" style={{margin:'80px auto'}} /></div>
  if (error) return <div className="page"><div className="alert alert-error">{error}</div></div>

  const { total_records, pending, approved, flagged, rejected, by_scope, by_category, recent_jobs } = stats

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">Emission data status for current review cycle</p>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-number" style={{color:'var(--text)'}}>{total_records}</div>
          <div className="stat-label">Total Records</div>
        </div>
        <div className="stat-card">
          <div className="stat-number" style={{color:'var(--text-muted)'}}>{pending}</div>
          <div className="stat-label">Pending Review</div>
        </div>
        <div className="stat-card">
          <div className="stat-number" style={{color:'var(--accent)'}}>{approved}</div>
          <div className="stat-label">Approved</div>
        </div>
        <div className="stat-card">
          <div className="stat-number" style={{color:'var(--warn)'}}>{flagged}</div>
          <div className="stat-label">Flagged</div>
        </div>
        <div className="stat-card">
          <div className="stat-number" style={{color:'var(--danger)'}}>{rejected}</div>
          <div className="stat-label">Rejected</div>
        </div>
      </div>

      <div className="dash-grid">
        <div className="card">
          <div className="card-label">Scope Breakdown</div>
          <ScopeBar by_scope={by_scope} />
        </div>

        <div className="card">
          <div className="card-label">By Category</div>
          <div style={{display:'flex', flexDirection:'column', gap:6, marginTop:4}}>
            {Object.entries(by_category).map(([cat, v]) => (
              <div key={cat} style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                <span style={{fontSize:12, color:'var(--text-muted)'}}>{CATEGORY_LABELS[cat] || cat}</span>
                <span style={{fontFamily:'var(--mono)', fontSize:12, color:'var(--text)'}}>{v.count}</span>
              </div>
            ))}
            {Object.keys(by_category).length === 0 && (
              <span style={{fontSize:12, color:'var(--text-dim)'}}>No records yet</span>
            )}
          </div>
        </div>
      </div>

      <div style={{marginTop:16}} className="card">
        <div className="card-label" style={{marginBottom:12}}>Recent Ingest Jobs</div>
        {recent_jobs.length === 0 ? (
          <div className="empty-state" style={{padding:'24px 0'}}>
            <div className="empty-text">No jobs yet</div>
            <div className="empty-hint"><Link to="/upload" style={{color:'var(--accent)'}}>Upload a file</Link> to get started</div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>File</th>
                <th>Source Type</th>
                <th>Uploaded</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Flagged</th>
                <th>Failed</th>
              </tr>
            </thead>
            <tbody>
              {recent_jobs.map(job => (
                <tr key={job.id}>
                  <td style={{fontFamily:'var(--mono)', fontSize:12}}>{job.filename}</td>
                  <td><span style={{fontSize:11, color:'var(--text-muted)'}}>{job.source_type}</span></td>
                  <td className="td-mono">{new Date(job.uploaded_at).toLocaleDateString()}</td>
                  <td>
                    <span className={`badge badge-${job.status === 'done' ? 'approved' : job.status === 'failed' ? 'rejected' : 'pending'}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="td-mono">{job.rows_ok}</td>
                  <td className="td-mono" style={{color: job.rows_flagged > 0 ? 'var(--warn)' : ''}}>{job.rows_flagged}</td>
                  <td className="td-mono" style={{color: job.rows_failed > 0 ? 'var(--danger)' : ''}}>{job.rows_failed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {pending > 0 && (
        <div style={{marginTop:16}}>
          <Link to="/records?review_status=pending" className="btn btn-primary">
            Review {pending} Pending Records →
          </Link>
        </div>
      )}
    </div>
  )
}
