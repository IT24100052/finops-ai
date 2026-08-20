const BASE = ''  // Vite proxy handles /auth, /costs, /ai, /billing

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

  return res.json()
}

export const api = {
  // Auth
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

  // Billing
  uploadCSV: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request('/billing/upload', { method: 'POST', body: fd, headers: {} })
  },

  clearBilling: () => request('/billing/clear', { method: 'DELETE' }),

  // Costs
  getSummary:    () => request('/costs/summary'),
  getDailyCosts: () => request('/costs/daily'),
  getByResource: () => request('/costs/by-resource'),

  // AI
  getPrediction: (days = 30) => request(`/ai/prediction?horizon_days=${days}`),
  getWaste:      () => request('/ai/waste'),
  getInsights:   () => request('/ai/insights'),
}
