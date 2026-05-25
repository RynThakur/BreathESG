import React, { createContext, useContext, useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { getMe, login as apiLogin, logout as apiLogout } from './api/client'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Records from './pages/Records'
import Upload from './pages/Upload'
import Jobs from './pages/Jobs'
import Layout from './components/Layout'
import './styles.css'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getMe().then(r => setUser(r.data)).catch(() => setUser(null)).finally(() => setLoading(false))
  }, [])

  const login = async (username, password) => {
    await apiLogin(username, password)
    const r = await getMe()
    setUser(r.data)
    return r.data
  }

  const logout = async () => {
    await apiLogout().catch(() => {})
    setUser(null)
  }

  if (loading) return <div className="loading-screen"><div className="spinner" /></div>

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

function PrivateRoute({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="records" element={<Records />} />
            <Route path="upload" element={<Upload />} />
            <Route path="jobs" element={<Jobs />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
