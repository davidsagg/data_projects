import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001/api';

// Create axios instance
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),

  register: (email: string, password: string, name?: string) =>
    api.post('/auth/register', { email, password, name }),

  getMe: () => api.get('/auth/me'),
};

// Projects API
export const projectsAPI = {
  getAll: (params?: { category?: string; status?: string }) =>
    api.get('/projects', { params }),

  getById: (id: string) =>
    api.get(`/projects/${id}`),

  create: (data: any) =>
    api.post('/projects', data),

  update: (id: string, data: any) =>
    api.put(`/projects/${id}`, data),

  delete: (id: string) =>
    api.delete(`/projects/${id}`),

  addMilestone: (projectId: string, data: any) =>
    api.post(`/projects/${projectId}/milestones`, data),

  toggleMilestone: (projectId: string, milestoneId: string) =>
    api.patch(`/projects/${projectId}/milestones/${milestoneId}/toggle`),

  addRedFlag: (projectId: string, data: any) =>
    api.post(`/projects/${projectId}/red-flags`, data),

  resolveRedFlag: (projectId: string, flagId: string) =>
    api.patch(`/projects/${projectId}/red-flags/${flagId}/resolve`),
};

// Objectives API
export const objectivesAPI = {
  getAll: (params?: { category?: string; status?: string }) =>
    api.get('/objectives', { params }),

  getById: (id: string) =>
    api.get(`/objectives/${id}`),

  create: (data: any) =>
    api.post('/objectives', data),

  update: (id: string, data: any) =>
    api.put(`/objectives/${id}`, data),

  delete: (id: string) =>
    api.delete(`/objectives/${id}`),

  updateKeyResult: (objectiveId: string, krId: string, data: any) =>
    api.put(`/objectives/${objectiveId}/key-results/${krId}`, data),
};

// Initiatives API
export const initiativesAPI = {
  getAll: (params?: { category?: string; status?: string }) =>
    api.get('/initiatives', { params }),

  getById: (id: string) =>
    api.get(`/initiatives/${id}`),

  create: (data: any) =>
    api.post('/initiatives', data),

  update: (id: string, data: any) =>
    api.put(`/initiatives/${id}`, data),

  delete: (id: string) =>
    api.delete(`/initiatives/${id}`),
};

// Dashboard API
export const dashboardAPI = {
  getStats: () =>
    api.get('/dashboard/stats'),

  getSummary: () =>
    api.get('/dashboard/summary'),
};

export default api;
