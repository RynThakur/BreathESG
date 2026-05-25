import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../App'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/dashboard')
    } catch (err) {
      setError('Invalid credentials. Try analyst / demo1234')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <h1>BREATHE ESG</h1>
          <p>Emissions Data Review Platform</p>
        </div>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              className="form-input"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="analyst"
              autoFocus
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              className="form-input"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="demo1234"
              required
            />
          </div>
          <button className="btn btn-primary" style={{width:'100%', marginTop:8}} disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
        <div style={{marginTop:20, padding:'12px', background:'var(--surface2)', borderRadius:'var(--radius)', fontSize:12, color:'var(--text-muted)'}}>
          <div style={{marginBottom:4, color:'var(--text-dim)', fontWeight:600, letterSpacing:'0.05em', textTransform:'uppercase', fontSize:10}}>Demo Credentials</div>
          <div style={{fontFamily:'var(--mono)'}}>analyst / demo1234</div>
        </div>
      </div>
    </div>
  )
}
