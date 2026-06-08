import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const conversationsApi = {
  list: (params = {}) => api.get('/conversations', { params }),
  get: (id) => api.get(`/conversations/${id}`),
  messages: (id, params = {}) => api.get(`/conversations/${id}/messages`, { params }),
  markRead: (id) => api.post(`/conversations/${id}/read`),
  create: (data) => api.post(`/conversations`, data),
  delete: (id) => api.delete(`/conversations/${id}`),
};

export const messagesApi = {
  send: (conversationId, body, caseId, replyToId) =>
    api.post(`/messages/send/${conversationId}`, { body, reply_to_id: replyToId || null }, { params: caseId ? { case_id: caseId } : {} }),
};

export const mediaApi = {
  send: (conversationId, file, caption, caseId, replyToId) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('caption', caption || '');
    if (caseId) formData.append('case_id', caseId);
    if (replyToId) formData.append('reply_to_id', replyToId);
    return api.post(`/media/send/${conversationId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

export const casesApi = {
  list: (params = {}) => api.get('/cases', { params }),
  get: (id) => api.get(`/cases/${id}`),
  create: (data) => api.post('/cases', data),
  update: (id, data) => api.patch(`/cases/${id}`, data),
  changeStatus: (id, status) => api.patch(`/cases/${id}/status`, { status }),
  assign: (id, agentId) => api.post(`/cases/${id}/assign`, { agent_id: agentId }),
  linkMessages: (id, messageIds) => api.post(`/cases/${id}/link-messages`, { message_ids: messageIds }),
  unlinkMessages: (id, messageIds) => api.post(`/cases/${id}/unlink-messages`, { message_ids: messageIds }),
  notes: (id) => api.get(`/cases/${id}/notes`),
  createNote: (id, note) => api.post(`/cases/${id}/notes`, { note }),
  updateNote: (caseId, noteId, note) => api.put(`/cases/${caseId}/notes/${noteId}`, { note }),
  deleteNote: (caseId, noteId) => api.delete(`/cases/${caseId}/notes/${noteId}`),
  events: (id) => api.get(`/cases/${id}/events`),
  registerView: (id) => api.post(`/cases/${id}/view`),
  viewers: (id) => api.get(`/cases/${id}/viewers`),
};

export const dashboardApi = {
  getMetrics: () => api.get('/dashboard/metrics'),
};

export const agentsApi = {
  list: () => api.get('/agents'),
  create: (data) => api.post('/agents', data),
  update: (id, data) => api.put(`/agents/${id}`, data),
  remove: (id) => api.delete(`/agents/${id}`),
};

export const setupApi = {
  check: () => api.get('/setup/check'),
  seed: () => api.post('/setup/seed'),
};

export const contactsApi = {
  create: (data) => api.post(`/contacts`, data),
  update: (contactId, data) => api.put(`/contacts/${contactId}`, data),
};

export const windowApi = {
  getStatus: (conversationId) => api.get(`/window/status/${conversationId}`),
  getTemplates: () => api.get('/templates'),
  sendTemplate: (conversationId, data) => api.post(`/templates/send/${conversationId}`, data),
};

export const adminApi = {
  checkSetup: () => api.get('/admin/setup/check'),
  getMyTenant: () => api.get('/admin/my-tenant'),
  createMyTenant: (data) => api.post('/admin/my-tenant', data),
  getAccount: () => api.get('/admin/whatsapp-account'),
  updateAccount: (data) => api.put('/admin/whatsapp-account', data),
  validateConnection: () => api.post('/admin/whatsapp-account/validate'),
  disconnectAccount: () => api.post('/admin/whatsapp-account/disconnect'),
  getSecrets: () => api.get('/admin/whatsapp-secrets'),
  updateSecrets: (data) => api.put('/admin/whatsapp-secrets', data),
  testConnection: () => api.post('/admin/whatsapp-secrets/test-connection'),
  getWebhookInfo: () => api.get('/admin/webhook-info'),
  verifyWebhook: () => api.post('/admin/webhook-info/verify'),
  getAuditLogs: (limit = 50) => api.get(`/admin/audit-logs?limit=${limit}`),
  // Super admin: company management
  getTenants: () => api.get('/admin/tenants'),
  deleteTenant: (id) => api.delete(`/admin/tenants/${id}`),
  deleteUser: (id) => api.delete(`/admin/users/${id}`),
};

export default api;
