import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
})

api.interceptors.response.use(
  res => res,
  err => {
    const msg = err.response?.data?.detail || err.message || 'Request failed'
    return Promise.reject(new Error(msg))
  }
)

export const getIncidents        = (limit = 100) =>
  api.get('/incidents', { params: { limit } }).then(r => r.data)

export const getIncidentDetail   = (id) =>
  api.get(`/incidents/${id}`).then(r => r.data)

export const transitionStatus    = (id, body) =>
  api.patch(`/incidents/${id}/status`, body).then(r => r.data)

export const ingestSignal        = (signal) =>
  api.post('/signals', signal).then(r => r.data)

export const ingestBatch         = (signals) =>
  api.post('/signals/batch', signals).then(r => r.data)

export const getSignals          = (wiId, limit = 200) =>
  api.get(`/signals/${wiId}`, { params: { limit } }).then(r => r.data)

export const getHealth           = () =>
  axios.get('/health').then(r => r.data)

export default api