import api from '../lib/api';

export const calendarApi = {
  getAuthUrl: () => api.get('/calendar/auth-url'),
  exchangeCode: (data) => api.post('/calendar/exchange-code', data),
  getStatus: () => api.get('/calendar/status'),
  disconnect: () => api.delete('/calendar/disconnect'),
  getSettings: () => api.get('/calendar/reminder-settings'),
  updateSettings: (data) => api.put('/calendar/reminder-settings', data),
  testReminder: (data) => api.post('/calendar/test-reminder', data),
  getLogs: (params) => api.get('/calendar/reminder-logs', { params }),
};
