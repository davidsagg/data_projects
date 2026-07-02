import axios from 'axios'

export const api = axios.create({ baseURL: '' })

export const musiciansApi = {
  list: () => api.get('/api/musicians').then(r => r.data),
  create: (data: unknown) => api.post('/api/musicians', data).then(r => r.data),
  update: (id: number, data: unknown) => api.put(`/api/musicians/${id}`, data).then(r => r.data),
  delete: (id: number) => api.delete(`/api/musicians/${id}`),
}

export const songsApi = {
  list: () => api.get('/api/songs').then(r => r.data),
  upload: (file: File) => {
    const f = new FormData(); f.append('file', file)
    return api.post('/api/songs/upload', f).then(r => r.data)
  },
  patch: (id: number, data: { bkcp_content?: string; key_original?: string | null; title?: string; artist?: string }) =>
    api.patch(`/api/songs/${id}`, data).then(r => r.data),
  transpose: (id: number, semitones: number) =>
    api.post(`/api/songs/${id}/transpose?semitones=${semitones}`).then(r => r.data),
  delete: (id: number) => api.delete(`/api/songs/${id}`),
}

export const setlistsApi = {
  list: () => api.get('/api/setlists').then(r => r.data),
  create: (data: { name: string; notes?: string }) => api.post('/api/setlists', data).then(r => r.data),
  get: (id: number) => api.get(`/api/setlists/${id}`).then(r => r.data),
  update: (id: number, data: unknown) => api.put(`/api/setlists/${id}`, data).then(r => r.data),
  delete: (id: number) => api.delete(`/api/setlists/${id}`),
  duplicate: (id: number, name?: string) =>
    api.post(`/api/setlists/${id}/duplicate`, { name: name ?? null }).then(r => r.data),
  addSong: (setlistId: number, data: { song_id: number; order_position: number }) =>
    api.post(`/api/setlists/${setlistId}/songs`, data).then(r => r.data),
  removeSong: (setlistId: number, entryId: number) =>
    api.delete(`/api/setlists/${setlistId}/songs/${entryId}`),
  reorder: (setlistId: number, items: { id: number; order_position: number }[]) =>
    api.put(`/api/setlists/${setlistId}/reorder`, items).then(r => r.data),
}

export const eventsApi = {
  list: (musicianId?: number) =>
    api.get(`/api/events${musicianId != null ? `?musician_id=${musicianId}` : ''}`).then(r => r.data),
  create: (data: unknown) => api.post('/api/events', data).then(r => r.data),
  get: (id: number) => api.get(`/api/events/${id}`).then(r => r.data),
  update: (id: number, data: unknown) => api.put(`/api/events/${id}`, data).then(r => r.data),
  delete: (id: number) => api.delete(`/api/events/${id}`),
  duplicate: (id: number, data: {
    title: string; date: string; setlist_id: number | null; copy_musicians: boolean
  }) => api.post(`/api/events/${id}/duplicate`, data).then(r => r.data),
}

export const executionsApi = {
  list: (eventId: number, musicianId?: number) =>
    api.get(`/api/events/${eventId}/executions${musicianId != null ? `?musician_id=${musicianId}` : ''}`).then(r => r.data),
  create: (eventId: number, data: { song_id: number; key_override?: string }) =>
    api.post(`/api/events/${eventId}/executions`, data).then(r => r.data),
  patch: (eventId: number, execId: number, data: { key_override?: string | null; notes?: string | null }) =>
    api.patch(`/api/events/${eventId}/executions/${execId}`, data).then(r => r.data),
  delete: (eventId: number, execId: number) =>
    api.delete(`/api/events/${eventId}/executions/${execId}`),
  syncSetlist: (eventId: number) =>
    api.post(`/api/events/${eventId}/sync-setlist`).then(r => r.data),
  reimportSetlist: (eventId: number) =>
    api.post(`/api/events/${eventId}/reimport-setlist`).then(r => r.data),
  reorderExecutions: (eventId: number, items: { id: number; order_position: number }[]) =>
    api.put(`/api/events/${eventId}/executions/reorder`, items).then(r => r.data),
  addMusician: (eventId: number, execId: number, data: { musician_id: number; instrument_override?: string | null }) =>
    api.post(`/api/events/${eventId}/executions/${execId}/musicians`, data).then(r => r.data),
  removeMusician: (eventId: number, execId: number, musicianId: number) =>
    api.delete(`/api/events/${eventId}/executions/${execId}/musicians/${musicianId}`),
}
