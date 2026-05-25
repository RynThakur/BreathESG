import React, { useState, useEffect } from 'react'
import { getJobs, getRecords } from '../api/client'
import { Link } from 'react-router-dom'

const SOURCE_LABELS = {
  sap_flat: 'SAP Flat File',
  utility_csv: 'Utility CSV',
  travel_json: 'Travel JSON',
}

export default function Jobs() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    getJobs()
      .then(r => setJobs(r.data.results || r.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="page"><div className="spinner" style={{margin:'80px auto'}} /></div>

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Ingest Jobs</h1>
        <p className="page-subtitle">History of all file ingestion runs</p>
      </div>

      {jobs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">○</div>
          <div className="empty-text">No ingest jobs yet</div>
          <div className="empty-hint"><Link to="/upload" style={{color:'var(--accent)'}}>Upload a file</Link> to create your first job</div>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Filename</th>
                <th>Source</th>
                <th>Uploaded</th>
                <th>Uploaded By</th>
                <th>Status</th>
                <th>OK</th>
                <th>Flagged</th>
                <th>Failed</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map(job => (
                <React.Fragment key={job.id}>
                  <tr
                    onClick={() => setExpanded(expanded === job.id ? null : job.id)}
                    style={{cursor:'pointer'}}
                  >
                    <td style={{fontFamily:'var(--mono)', fontSize:12}}>{job.filename}</td>
                    <td><span style={{fontSize:11, color:'var(--text-muted)'}}>{SOURCE_LABELS[job.source_type]}</span></td>
                    <td className="td-mono">{new Date(job.uploaded_at).toLocaleString()}</td>
                    <td style={{fontSize:12, color:'var(--text-muted)'}}>{job.uploaded_by_name || '—'}</td>
                    <td>
                      <span className={`badge badge-${job.status === 'done' ? 'approved' : job.status === 'failed' ? 'rejected' : 'pending'}`}>
                        {job.status}
                      </span>
                    </td>
                    <td className="td-mono" style={{color:'var(--accent)'}}>{job.rows_ok}</td>
                    <td className="td-mono" style={{color: job.rows_flagged > 0 ? 'var(--warn)' : 'var(--text-dim)'}}>{job.rows_flagged}</td>
                    <td className="td-mono" style={{color: job.rows_failed > 0 ? 'var(--danger)' : 'var(--text-dim)'}}>{job.rows_failed}</td>
                    <td>
                      <Link
                        to={`/records?job=${job.id}`}
                        onClick={e => e.stopPropagation()}
                        className="btn btn-ghost btn-sm"
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                  {expanded === job.id && job.error_log?.length > 0 && (
                    <tr>
                      <td colSpan={9} style={{background:'var(--surface2)', padding:'12px 16px'}}>
                        <div style={{fontSize:11, color:'var(--text-dim)', marginBottom:6, fontWeight:600, textTransform:'uppercase', letterSpacing:'0.05em'}}>
                          Parse errors ({job.error_log.length})
                        </div>
                        {job.error_log.map((e, i) => (
                          <div key={i} style={{fontFamily:'var(--mono)', fontSize:11, color:'var(--danger)', marginBottom:3}}>
                            {e}
                          </div>
                        ))}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
