import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: `${BASE}/api`,
  withCredentials: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
})

export const getCSRF = () => api.get('/csrf/')

api.interceptors.request.use(config => {
  if (['post', 'put', 'patch', 'delete'].includes(config.method?.toLowerCase())) {
    const cookie = document.cookie
      .split('; ')
      .find(c => c.startsWith('csrftoken='))

    if (cookie) {
      config.headers['X-CSRFToken'] = cookie.split('=')[1]
    }
  }

  return config
})

export const login = async (username, password) => {
  await getCSRF()

  return api.post(
    '/auth/login/',
    new URLSearchParams({ username, password }),
    {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    }
  )
}

export const logout = () => api.post('/auth/logout/')

export const getMe = () => api.get('/me/')

export const getDashboard = () => api.get('/dashboard/')

export const getJobs = () => api.get('/jobs/')

export const getRecords = (params = {}) =>
  api.get('/records/', { params })

export const reviewRecord = (id, data) =>
  api.post(`/records/${id}/review/`, data)

export const getAuditTrail = (id) =>
  api.get(`/records/${id}/audit_trail/`)

export const uploadFile = (sourceType, file) => {
  const form = new FormData()
  form.append('source_type', sourceType)
  form.append('file', file)

  return api.post('/ingest/', form)
}

export const getPlantCodes = () => api.get('/plant-codes/')

export default api