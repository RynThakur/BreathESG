import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: `${BASE}/api`,

  withCredentials: true,

  xsrfCookieName: 'csrftoken',

  xsrfHeaderName: 'X-CSRFToken',
})


// -------------------
// CSRF
// -------------------

export const getCSRF = () => {
  return api.get('/csrf/')
}


// -------------------
// Automatically attach CSRF token
// -------------------

api.interceptors.request.use((config) => {

  const method = config.method?.toLowerCase()

  if (
    ['post', 'put', 'patch', 'delete']
      .includes(method)
  ) {

    const cookie = document.cookie
      .split('; ')
      .find(c => c.startsWith('csrftoken='))

    if (cookie) {

      const token = cookie.split('=')[1]

      config.headers['X-CSRFToken'] = token
    }
  }

  return config
})


// -------------------
// AUTH
// -------------------

export const login = async (
  username,
  password
) => {

  // Get csrf cookie first

  await getCSRF()

  // Login request

  return api.post(
    '/auth/login/',
    {
      username,
      password
    },
    {
      headers: {
        'Content-Type': 'application/json'
      }
    }
  )
}


export const logout = () =>
  api.post('/auth/logout/')


export const getMe = () =>
  api.get('/me/')


export const getDashboard = () =>
  api.get('/dashboard/')


export const getJobs = () =>
  api.get('/jobs/')


export const getRecords = (
  params = {}
) =>
  api.get(
    '/records/',
    { params }
  )


export const reviewRecord = (
  id,
  data
) =>
  api.post(
    `/records/${id}/review/`,
    data
  )


export const getAuditTrail = (
  id
) =>
  api.get(
    `/records/${id}/audit_trail/`
  )


// -------------------
// Upload
// -------------------

export const uploadFile = (
  sourceType,
  file
) => {

  const form = new FormData()

  form.append(
    'source_type',
    sourceType
  )

  form.append(
    'file',
    file
  )

  return api.post(
    '/ingest/',
    form
  )
}


export const getPlantCodes = () =>
  api.get('/plant-codes/')


export default api