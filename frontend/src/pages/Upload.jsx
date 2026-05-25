import React, { useState, useRef } from 'react'
import { uploadFile } from '../api/client'
import { Link } from 'react-router-dom'

const SOURCES = [
  {
    key: 'sap_flat',
    label: 'SAP Flat File',
    desc: 'IDoc-derived CSV export from SAP MM or FI module. Handles German column headers (MENGE, MEINS, WERKS), YYYYMMDD dates, and SAP unit codes (L, GAL, MMBTU, TO).',
    accept: '.csv,.txt,.tsv',
    scope: 'Scope 1 (fuel) + Scope 3 (procurement)',
    example: 'SAP_MM_FuelProcurement_Q1_2024.csv',
    fields: 'BELNR, BUDAT, WERKS, MATNR, MAKTX, MATKL, MENGE, MEINS, NAME1, WRBTR, WAERS',
  },
  {
    key: 'utility_csv',
    label: 'Utility Portal CSV',
    desc: 'Green Button / EnergyCAP format CSV from utility portals (Con Edison, PG&E, National Grid, etc.). Handles billing periods that don\'t align with calendar months, estimated vs actual reads.',
    accept: '.csv',
    scope: 'Scope 2 (electricity) + Scope 1 (gas)',
    example: 'ConEdison_HQ_Jan_Mar_2024.csv',
    fields: 'account_number, meter_id, commodity, unit, bill_start_date, bill_end_date, consumption, read_type, rate_schedule',
  },
  {
    key: 'travel_json',
    label: 'Corporate Travel JSON',
    desc: 'SAP Concur expense report JSON export. Handles flights (IATA codes → distance estimation), hotels (nights), ground transport, and multi-currency amounts.',
    accept: '.json',
    scope: 'Scope 3 (business travel)',
    example: 'Concur_Q1_2024_ExpenseExport.json',
    fields: 'expenseTypeCode, transactionDate, transactionAmount, transactionCurrencyCode, vendorDescription, custom1/2 (airport codes)',
  },
]

function SampleDownload({ sourceType }) {
  const samples = {
    sap_flat: `BELNR,BUDAT,BLDAT,WERKS,MATNR,MAKTX,MATKL,MENGE,MEINS,LIFNR,NAME1,WRBTR,WAERS
5100012345,20240115,20240114,1000,000000000000100001,Diesel Kraftstoff,001,45200,L,VEND001,Shell Deutschland GmbH,38420.00,EUR
5100012346,20240122,20240121,1100,000000000000100002,Diesel Fleet,002,12800,L,VEND002,BP Europa SE,10880.00,EUR
5100012350,20240131,20240130,1000,000000000000200001,Natural Gas,001,2000,MMBTU,VEND003,E.ON SE,62000.00,EUR
5100012360,20240215,20240214,1000,000000000000300001,Packaging Materials,011,41666.67,EUR,VEND004,Smurfit Kappa GmbH,41666.67,EUR
5100012399,20240210,20240209,2000,000000000000100001,Diesel Fuel,001,1500000,L,VEND005,BP America Inc,1200000.00,USD`,

    utility_csv: `account_number,meter_id,commodity,unit,bill_start_date,bill_end_date,consumption,demand_kw,cost,rate_schedule,read_type,facility_name,country
43406,1424,electric,KWH,2024-01-03,2024-02-02,347000,890,41640,SC-9,actual,Chicago HQ - North Tower,US
43407,1425,electric,KWH,2024-02-03,2024-03-05,298000,780,35760,SC-9,estimated,Chicago HQ - North Tower,US
43410,2001,electric,KWH,2024-01-08,2024-02-07,512000,1200,61440,SC-9-Large,actual,Hamburg Plant - Grid Connection,DE
43411,2002,gas,MMBTU,2024-01-01,2024-01-31,1800,0,54000,GS-2,actual,Hamburg Plant - Gas,DE`,

    travel_json: JSON.stringify({
      reports: [
        {
          reportId: "RPT-2024-001",
          reportName: "Q1 Business Travel",
          submittedDate: "2024-03-31",
          entries: [
            { entryId: "E001", expenseTypeCode: "AIRFR", transactionDate: "2024-01-15", transactionAmount: 890.00, transactionCurrencyCode: "USD", vendorDescription: "United Airlines", locationCity: "New York", locationCountry: "US", custom1: "JFK", custom2: "LHR", custom3: "1" },
            { entryId: "E002", expenseTypeCode: "HOTEL", transactionDate: "2024-01-15", transactionAmount: 680.00, transactionCurrencyCode: "USD", vendorDescription: "Marriott London", locationCity: "London", locationCountry: "GB", quantity: 3 },
            { entryId: "E003", expenseTypeCode: "TAXI", transactionDate: "2024-01-15", transactionAmount: 45.00, transactionCurrencyCode: "USD", vendorDescription: "Uber", locationCity: "New York", locationCountry: "US" },
            { entryId: "E004", expenseTypeCode: "AIRFR", transactionDate: "2024-02-05", transactionAmount: 2100.00, transactionCurrencyCode: "USD", vendorDescription: "Singapore Airlines", locationCity: "Los Angeles", locationCountry: "US", custom1: "LAX", custom2: "SYD", custom3: "1" }
          ]
        }
      ]
    }, null, 2)
  }

  const content = samples[sourceType]
  const ext = sourceType === 'travel_json' ? 'json' : 'csv'
  const filename = `sample_${sourceType}.${ext}`

  const download = () => {
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = filename; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <button className="btn btn-ghost btn-sm" onClick={download} style={{marginTop:8}}>
      ↓ Download sample {ext.toUpperCase()}
    </button>
  )
}

export default function Upload() {
  const [sourceType, setSourceType] = useState('sap_flat')
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const fileRef = useRef()

  const source = SOURCES.find(s => s.key === sourceType)

  const handleFile = (f) => {
    setFile(f)
    setResult(null)
    setError('')
  }

  const handleSubmit = async () => {
    if (!file) { setError('Please select a file'); return }
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await uploadFile(sourceType, file)
      setResult(r.data)
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
    } catch (e) {
      setError(e.response?.data?.error || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Upload Data</h1>
        <p className="page-subtitle">Ingest emissions data from SAP, utility portals, or corporate travel platforms</p>
      </div>

      <div className="source-tabs">
        {SOURCES.map(s => (
          <button key={s.key} className={`source-tab ${sourceType === s.key ? 'active' : ''}`}
            onClick={() => { setSourceType(s.key); setFile(null); setResult(null); setError('') }}>
            {s.label}
          </button>
        ))}
      </div>

      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:16}}>
        <div>
          <div className="card" style={{marginBottom:12}}>
            <div className="card-label">{source.label}</div>
            <p style={{fontSize:13, color:'var(--text-muted)', lineHeight:1.6, marginBottom:12}}>{source.desc}</p>
            <div className="detail-row">
              <span className="detail-key">Scope</span>
              <span style={{fontSize:12, color:'var(--text-muted)'}}>{source.scope}</span>
            </div>
            <div className="detail-row">
              <span className="detail-key">Expected fields</span>
              <span style={{fontSize:11, fontFamily:'var(--mono)', color:'var(--text-dim)', textAlign:'right'}}>{source.fields}</span>
            </div>
            <SampleDownload sourceType={sourceType} />
          </div>
        </div>

        <div>
          <div
            className={`upload-zone ${dragging ? 'drag-over' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }}
          >
            <input ref={fileRef} type="file" accept={source.accept}
              onChange={e => handleFile(e.target.files[0])} />
            <div className="upload-icon">⬆</div>
            {file ? (
              <>
                <div className="upload-text" style={{color:'var(--accent)'}}>{file.name}</div>
                <div className="upload-hint">{(file.size/1024).toFixed(1)} KB</div>
              </>
            ) : (
              <>
                <div className="upload-text">Drop file here or click to browse</div>
                <div className="upload-hint">Accepts {source.accept} · max 10MB</div>
              </>
            )}
          </div>

          <div style={{marginTop:12, display:'flex', gap:8}}>
            <button className="btn btn-primary" style={{flex:1}} onClick={handleSubmit} disabled={loading || !file}>
              {loading ? 'Processing...' : 'Ingest File'}
            </button>
          </div>

          {error && <div className="alert alert-error" style={{marginTop:12}}>{error}</div>}

          {result && (
            <div className="card" style={{marginTop:12}}>
              <div className="alert alert-success" style={{marginBottom:12}}>
                ✓ Ingestion complete
              </div>
              <div className="detail-row">
                <span className="detail-key">Status</span>
                <span className={`badge badge-${result.status === 'done' ? 'approved' : 'rejected'}`}>{result.status}</span>
              </div>
              <div className="detail-row">
                <span className="detail-key">Rows ingested</span>
                <span className="detail-val">{result.rows_ok}</span>
              </div>
              <div className="detail-row">
                <span className="detail-key">Flagged</span>
                <span className="detail-val" style={{color: result.rows_flagged > 0 ? 'var(--warn)' : ''}}>{result.rows_flagged}</span>
              </div>
              <div className="detail-row">
                <span className="detail-key">Failed rows</span>
                <span className="detail-val" style={{color: result.rows_failed > 0 ? 'var(--danger)' : ''}}>{result.rows_failed}</span>
              </div>
              {result.error_log?.length > 0 && (
                <div style={{marginTop:10}}>
                  <div className="card-label" style={{marginBottom:6}}>Parse Errors</div>
                  {result.error_log.slice(0, 5).map((e, i) => (
                    <div key={i} style={{fontSize:11, color:'var(--danger)', fontFamily:'var(--mono)', marginBottom:4}}>{e}</div>
                  ))}
                </div>
              )}
              <Link to="/records" className="btn btn-ghost btn-sm" style={{marginTop:10, display:'inline-flex'}}>
                Review Records →
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
