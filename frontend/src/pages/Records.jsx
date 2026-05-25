import React, { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getRecords, reviewRecord, getAuditTrail } from '../api/client'

const CATEGORY_LABELS = {
  fuel_stationary: 'Stationary Combustion',
  fuel_mobile: 'Mobile Combustion',
  electricity: 'Purchased Electricity',
  travel_flight: 'Flight',
  travel_hotel: 'Hotel',
  travel_ground: 'Ground Transport',
  procurement: 'Procurement',
}

function ReviewModal({ record, onClose, onDone }) {
  const [action, setAction] = useState('')
  const [notes, setNotes] = useState('')
  const [editQty, setEditQty] = useState('')
  const [editReason, setEditReason] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [auditTrail, setAuditTrail] = useState([])

  useEffect(() => {
    getAuditTrail(record.id).then(r => setAuditTrail(r.data)).catch(() => {})
  }, [record.id])

  const handleSubmit = async () => {
    if (!action) { setError('Select an action'); return }
    setLoading(true); setError('')
    try {
      await reviewRecord(record.id, {
        action,
        notes,
        ...(editQty ? { edit_quantity: parseFloat(editQty), edit_reason: editReason } : {}),
      })
      onDone()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to submit review')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-header">
          <span className="modal-title">Review Record</span>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {/* Record details */}
          <div style={{marginBottom:16}}>
            <div className="detail-row">
              <span className="detail-key">Scope</span>
              <span className={`scope-badge scope-${record.scope}`}>Scope {record.scope}</span>
            </div>
            <div className="detail-row">
              <span className="detail-key">Category</span>
              <span className="detail-val">{CATEGORY_LABELS[record.category] || record.category}</span>
            </div>
            <div className="detail-row">
              <span className="detail-key">Quantity</span>
              <span className="detail-val">{parseFloat(record.quantity).toLocaleString()} {record.unit}</span>
            </div>
            <div className="detail-row">
              <span className="detail-key">Raw Value</span>
              <span className="detail-val">{record.raw_quantity} {record.raw_unit}</span>
            </div>
            <div className="detail-row">
              <span className="detail-key">Period</span>
              <span className="detail-val">{record.period_start} → {record.period_end}</span>
            </div>
            {record.facility_name && (
              <div className="detail-row">
                <span className="detail-key">Facility</span>
                <span className="detail-val">{record.facility_name} {record.facility_country && `(${record.facility_country})`}</span>
              </div>
            )}
            {record.origin && (
              <div className="detail-row">
                <span className="detail-key">Route</span>
                <span className="detail-val">{record.origin} → {record.destination} {record.distance_km ? `(${parseFloat(record.distance_km).toLocaleString()} km)` : ''}</span>
              </div>
            )}
            {record.vendor_name && (
              <div className="detail-row">
                <span className="detail-key">Vendor</span>
                <span className="detail-val">{record.vendor_name}</span>
              </div>
            )}
            {record.meter_id && (
              <div className="detail-row">
                <span className="detail-key">Meter</span>
                <span className="detail-val">{record.meter_id} {record.tariff_code && `/ ${record.tariff_code}`}</span>
              </div>
            )}
            {record.is_estimated_read && (
              <div className="detail-row">
                <span className="detail-key">Read Type</span>
                <span style={{fontSize:12, color:'var(--warn)'}}>⚠ Estimated</span>
              </div>
            )}
            {record.anomaly_flags?.length > 0 && (
              <div className="detail-row">
                <span className="detail-key">Flags</span>
                <div className="flag-list">
                  {record.anomaly_flags.map(f => <span key={f} className="flag-tag">{f}</span>)}
                </div>
              </div>
            )}
            {record.ingest_job_filename && (
              <div className="detail-row">
                <span className="detail-key">Source File</span>
                <span className="detail-val" style={{fontFamily:'var(--mono)', fontSize:11}}>{record.ingest_job_filename}</span>
              </div>
            )}
          </div>

          {/* Quantity edit */}
          <div style={{background:'var(--surface2)', borderRadius:'var(--radius)', padding:12, marginBottom:14}}>
            <div className="form-label" style={{marginBottom:8}}>Override Quantity (optional)</div>
            <div style={{display:'flex', gap:8, alignItems:'center'}}>
              <input className="form-input" type="number" placeholder={record.quantity}
                value={editQty} onChange={e => setEditQty(e.target.value)} style={{flex:1}} />
              <span style={{fontSize:12, color:'var(--text-muted)', whiteSpace:'nowrap'}}>{record.unit}</span>
            </div>
            {editQty && (
              <input className="form-input" style={{marginTop:8}} placeholder="Reason for edit..."
                value={editReason} onChange={e => setEditReason(e.target.value)} />
            )}
          </div>

          {/* Action */}
          <div className="form-group">
            <div className="form-label">Action</div>
            <div style={{display:'flex', gap:8}}>
              {['approve','flag','reject'].map(a => (
                <button key={a} onClick={() => setAction(a)}
                  className={`btn btn-sm btn-${a === 'approve' ? 'approve' : a === 'flag' ? 'flag' : 'reject'}`}
                  style={{flex:1, opacity: action && action !== a ? 0.4 : 1}}>
                  {a === 'approve' ? '✓ Approve' : a === 'flag' ? '⚑ Flag' : '✕ Reject'}
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Notes</label>
            <textarea className="form-textarea" placeholder="Add review notes..."
              value={notes} onChange={e => setNotes(e.target.value)} />
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          {/* Audit trail */}
          {auditTrail.length > 0 && (
            <div>
              <div className="form-label" style={{marginBottom:10}}>History</div>
              <div className="audit-timeline">
                {auditTrail.map(ev => (
                  <div key={ev.id} className={`audit-event ${ev.event_type}`}>
                    <div className="audit-type">{ev.event_type}</div>
                    <div className="audit-meta">
                      {ev.actor_name} · {new Date(ev.timestamp).toLocaleString()}
                    </div>
                    {ev.payload?.notes && (
                      <div style={{fontSize:11, color:'var(--text-muted)', marginTop:2}}>"{ev.payload.notes}"</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={loading || !action}>
            {loading ? 'Submitting...' : 'Submit Review'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Records() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [page, setPage] = useState(1)
  const [count, setCount] = useState(0)

  const filters = {
    scope: searchParams.get('scope') || '',
    category: searchParams.get('category') || '',
    review_status: searchParams.get('review_status') || '',
    has_flags: searchParams.get('has_flags') || '',
  }

  const fetchRecords = useCallback(() => {
    setLoading(true)
    const params = { page, ...Object.fromEntries(Object.entries(filters).filter(([,v]) => v)) }
    getRecords(params)
      .then(r => { setRecords(r.data.results || r.data); setCount(r.data.count || r.data.length) })
      .catch(() => setError('Failed to load records'))
      .finally(() => setLoading(false))
  }, [page, searchParams])

  useEffect(() => { fetchRecords() }, [fetchRecords])

  const setFilter = (key, val) => {
    const next = new URLSearchParams(searchParams)
    if (val) next.set(key, val); else next.delete(key)
    next.delete('page')
    setPage(1)
    setSearchParams(next)
  }

  const totalPages = Math.ceil(count / 50)

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Emission Records</h1>
        <p className="page-subtitle">{count} records · select any row to review</p>
      </div>

      <div className="table-wrap">
        <div className="table-toolbar">
          <span className="filter-label">Filter:</span>
          <select className="filter-select" value={filters.review_status} onChange={e => setFilter('review_status', e.target.value)}>
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="flagged">Flagged</option>
            <option value="rejected">Rejected</option>
          </select>
          <select className="filter-select" value={filters.scope} onChange={e => setFilter('scope', e.target.value)}>
            <option value="">All Scopes</option>
            <option value="1">Scope 1</option>
            <option value="2">Scope 2</option>
            <option value="3">Scope 3</option>
          </select>
          <select className="filter-select" value={filters.category} onChange={e => setFilter('category', e.target.value)}>
            <option value="">All Categories</option>
            <option value="fuel_stationary">Stationary Combustion</option>
            <option value="fuel_mobile">Mobile Combustion</option>
            <option value="electricity">Electricity</option>
            <option value="travel_flight">Flights</option>
            <option value="travel_hotel">Hotels</option>
            <option value="travel_ground">Ground Transport</option>
            <option value="procurement">Procurement</option>
          </select>
          <select className="filter-select" value={filters.has_flags} onChange={e => setFilter('has_flags', e.target.value)}>
            <option value="">All Records</option>
            <option value="true">Flagged Only</option>
          </select>
          {Object.values(filters).some(Boolean) && (
            <button className="btn btn-ghost btn-sm" onClick={() => { setSearchParams({}); setPage(1) }}>
              Clear filters
            </button>
          )}
        </div>

        {loading ? (
          <div style={{padding:'48px', textAlign:'center'}}><div className="spinner" style={{margin:'0 auto'}} /></div>
        ) : error ? (
          <div style={{padding:20}}><div className="alert alert-error">{error}</div></div>
        ) : records.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">○</div>
            <div className="empty-text">No records match these filters</div>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Scope</th>
                <th>Category</th>
                <th>Quantity</th>
                <th>Period</th>
                <th>Facility / Route</th>
                <th>Source</th>
                <th>Flags</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {records.map(r => (
                <tr key={r.id} onClick={() => setSelected(r)} style={{cursor:'pointer'}}>
                  <td><span className={`scope-badge scope-${r.scope}`}>S{r.scope}</span></td>
                  <td style={{fontSize:12, color:'var(--text-muted)'}}>{CATEGORY_LABELS[r.category] || r.category}</td>
                  <td className="td-mono">
                    {parseFloat(r.quantity).toLocaleString(undefined, {maximumFractionDigits:2})} {r.unit}
                    {r.is_edited && <span style={{marginLeft:4, fontSize:10, color:'var(--scope3)'}}>edited</span>}
                  </td>
                  <td className="td-mono">{r.period_start}</td>
                  <td style={{fontSize:12}}>
                    {r.origin ? `${r.origin}→${r.destination}` : r.facility_name || '—'}
                  </td>
                  <td style={{fontSize:11, color:'var(--text-dim)', fontFamily:'var(--mono)', maxWidth:140, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>
                    {r.ingest_job_filename}
                  </td>
                  <td>
                    {r.anomaly_flags?.length > 0 && (
                      <span title={r.anomaly_flags.join(', ')}>
                        <span className="flag-dot" />
                        <span style={{fontSize:11, color:'var(--warn)'}}>{r.anomaly_flags.length}</span>
                      </span>
                    )}
                  </td>
                  <td><span className={`badge badge-${r.review_status}`}>{r.review_status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {totalPages > 1 && (
          <div className="pagination">
            <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => p-1)}>← Prev</button>
            <span style={{fontSize:12, color:'var(--text-muted)'}}>Page {page} / {totalPages}</span>
            <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage(p => p+1)}>Next →</button>
          </div>
        )}
      </div>

      {selected && (
        <ReviewModal
          record={selected}
          onClose={() => setSelected(null)}
          onDone={() => { setSelected(null); fetchRecords() }}
        />
      )}
    </div>
  )
}
