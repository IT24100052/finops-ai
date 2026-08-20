const BASE = ''  // Vite proxy handles /auth, /costs, /ai, /billing, /budgets

function getToken() {
  return localStorage.getItem('finops_token')
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  }

  // Don't set Content-Type for FormData (browser sets boundary automatically)
  if (options.body instanceof FormData) {
    delete headers['Content-Type']
  }

  const res = await fetch(BASE + path, { ...options, headers })

  if (res.status === 401) {
    localStorage.removeItem('finops_token')
    window.location.href = '/login'
    return
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }

  // Handle 204 No Content (DELETE)
  if (res.status === 204) return null

  return res.json()
}

function buildQuery(params = {}) {
  const q = Object.entries(params)
    .filter(([, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&')
  return q ? `?${q}` : ''
}

export const api = {
  // ── Auth ────────────────────────────────────────────────────────────────
  register: (email, password) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }),

  login: async (email, password) => {
    const form = new URLSearchParams({ username: email, password })
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }))
      throw new Error(err.detail || 'Login failed')
    }
    return res.json()
  },

  // ── Billing ──────────────────────────────────────────────────────────────
  uploadCSV: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request('/billing/upload', { method: 'POST', body: fd, headers: {} })
  },

  clearBilling: () => request('/billing/clear', { method: 'DELETE' }),

  // ── Costs ────────────────────────────────────────────────────────────────
  getSummary:        (filters = {}) => request(`/costs/summary${buildQuery(filters)}`),
  getDailyCosts:     (filters = {}) => request(`/costs/daily${buildQuery(filters)}`),
  getByResource:     ()             => request('/costs/by-resource'),
  getByProvider:     (filters = {}) => request(`/costs/by-provider${buildQuery(filters)}`),
  getByRegion:       (filters = {}) => request(`/costs/by-region${buildQuery(filters)}`),
  getByService:      (filters = {}) => request(`/costs/by-service${buildQuery(filters)}`),
  getByTeam:         (filters = {}) => request(`/costs/by-team${buildQuery(filters)}`),
  getByProject:      (filters = {}) => request(`/costs/by-project${buildQuery(filters)}`),
  getByEnvironment:  (filters = {}) => request(`/costs/by-environment${buildQuery(filters)}`),

  // ── Resources ────────────────────────────────────────────────────────────
  getResources:      (filters = {}) => request(`/costs/resources${buildQuery(filters)}`),
  getResource:       (id)           => request(`/costs/resources/${encodeURIComponent(id)}`),

  // ── AI ───────────────────────────────────────────────────────────────────
  getPrediction:     (days = 30)    => request(`/ai/prediction?horizon_days=${days}`),
  getWaste:          ()             => request('/ai/waste'),
  getInsights:       ()             => request('/ai/insights'),
  getFinopsScore:    ()             => request('/ai/finops-score'),
  getDataQuality:    ()             => request('/ai/data-quality'),

  // ── Budgets ──────────────────────────────────────────────────────────────
  getBudgets:    ()         => request('/budgets'),
  createBudget:  (data)     => request('/budgets', { method: 'POST', body: JSON.stringify(data) }),
  updateBudget:  (id, data) => request(`/budgets/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteBudget:  (id)       => request(`/budgets/${id}`, { method: 'DELETE' }),
}
