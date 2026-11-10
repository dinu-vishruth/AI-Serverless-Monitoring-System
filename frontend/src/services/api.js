/**
 * API service for communicating with FastAPI backend.
 */

const API_BASE = `${import.meta.env.VITE_API_ORIGIN || ''}/api/v1`;

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(sessionStorage.getItem('isms-token') ? { Authorization: `Bearer ${sessionStorage.getItem('isms-token')}` } : {}),
    ...options.headers,
  };

  try {
    const response = await fetch(url, { ...options, headers, signal: AbortSignal.timeout(28000) });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail || response.status));
    }
    return await response.json();
  } catch (err) {
    console.error(`API Error on ${endpoint}:`, err);
    throw err;
  }
}

export const api = {
  getReliability: (id) => request(`/monitoring/${id}/reliability`),
  getDependencies: () => request('/dependencies'),
  getNotifications: () => request('/notifications/status'),
  getModel: (id) => request(`/ai/models/${id}`),
  setDemoMode: (mode) => request('/demo/mode', { method: 'PUT', body: JSON.stringify({ mode }) }),
  getCorrelation: (id) => request(`/incidents/${id}/correlation`),
  remediate: (id, action, comments) => request(`/incidents/${id}/remediate`, { method: 'POST', body: JSON.stringify({ action, comments, authorized: true }) }),
  // Metrics & Overview
  getOverview: () => request('/metrics/overview'),

  // Services
  getServices: (activeOnly = false) => request(`/services?active_only=${activeOnly}`),
  getService: (id) => request(`/services/${id}`),
  createService: (data) => request('/services', { method: 'POST', body: JSON.stringify(data) }),
  updateService: (id, data) => request(`/services/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteService: (id) => request(`/services/${id}`, { method: 'DELETE' }),

  // Monitoring
  getServiceRecords: (id, hours = 24) => request(`/monitoring/${id}/records?hours=${hours}&limit=3000`),
  getLatestRecord: (id) => request(`/monitoring/${id}/latest`),
  triggerCheck: (id) => request(`/monitoring/${id}/check-now`, { method: 'POST' }),

  // Incidents
  getIncidents: (statusFilter, severity) => {
    const params = new URLSearchParams();
    if (statusFilter) params.append('status_filter', statusFilter);
    if (severity) params.append('severity', severity);
    return request(`/incidents?${params.toString()}`);
  },
  getIncident: (id) => request(`/incidents/${id}`),
  updateIncident: (id, data) => request(`/incidents/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  // AI & Assistant
  chatAI: (query, serviceId, incidentId) =>
    request('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ query, service_id: serviceId, incident_id: incidentId }),
    }),
  analyzeIncident: (incidentId) =>
    request('/ai/analyze-incident', {
      method: 'POST',
      body: JSON.stringify({ incident_id: incidentId }),
    }),
  retrainModel: (serviceId) => request(`/ai/retrain/${serviceId}`, { method: 'POST' }),
  getAIAnalyses: (serviceId) => request(`/ai/analyses${serviceId ? `?service_id=${serviceId}` : ''}`),
};
