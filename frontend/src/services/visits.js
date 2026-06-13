import { api } from './api'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

function buildQuery(params) {
  const search = new URLSearchParams()
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v) search.append(k, v)
  })
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export const visitsApi = {
  list: () => api.get('/visits/'),
  create: (payload) => api.post('/visits/', payload),
  update: (id, payload) => api.put(`/visits/${id}/`, payload),
  remove: (id) => api.delete(`/visits/${id}/`),
  summary: (params) => api.get(`/visits/summary/${buildQuery(params)}`),
  exportUrl: (params) => `${API_BASE}/visits/export/${buildQuery(params)}`
}
