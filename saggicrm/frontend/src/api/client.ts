import axios from 'axios'
import type {
  BulkGeocodeResult,
  Company,
  CompanyDetail,
  ContactDetail,
  ContactPage,
  FacetItem,
  GeocodeResult,
  Group,
  ImportSummary,
  Interaction,
  Reminder,
  StatsOut,
} from '../types'

const http = axios.create({ baseURL: '' })

export interface ContactFilters {
  q?: string
  group_id?: number
  company_id?: number
  sector?: string
  seniority?: string
  position?: string
  city?: string
  favorite_only?: boolean
  sort?: 'name' | 'company' | 'seniority' | 'connected_on' | 'recent'
  sort_dir?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

export const contactsApi = {
  list: (filters: ContactFilters = {}) =>
    http.get<ContactPage>('/api/contacts', { params: filters }).then((r) => r.data),
  get: (id: number) => http.get<ContactDetail>(`/api/contacts/${id}`).then((r) => r.data),
  create: (payload: Partial<ContactDetail>) =>
    http.post<ContactDetail>('/api/contacts', payload).then((r) => r.data),
  update: (id: number, payload: Partial<ContactDetail>) =>
    http.put<ContactDetail>(`/api/contacts/${id}`, payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/api/contacts/${id}`),
  toggleFavorite: (id: number) =>
    http.patch<ContactDetail>(`/api/contacts/${id}/favorite`).then((r) => r.data),
  locations: () => http.get<FacetItem[]>('/api/locations').then((r) => r.data),
  seniorityLevels: () => http.get<FacetItem[]>('/api/seniority-levels').then((r) => r.data),
}

export const companiesApi = {
  list: (
    filters: {
      sector?: string
      q?: string
      sort?: 'contacts' | 'name' | 'sector'
      sort_dir?: 'asc' | 'desc'
    } = {},
  ) => http.get<Company[]>('/api/companies', { params: filters }).then((r) => r.data),
  get: (id: number) => http.get<CompanyDetail>(`/api/companies/${id}`).then((r) => r.data),
  update: (id: number, payload: Partial<{ name: string; sector: string }>) =>
    http.patch<Company>(`/api/companies/${id}`, payload).then((r) => r.data),
  bulkSector: (companyIds: number[], sector: string) =>
    http.post('/api/companies/bulk-sector', { company_ids: companyIds, sector }),
}

export const groupsApi = {
  list: () => http.get<Group[]>('/api/groups').then((r) => r.data),
  create: (payload: { name: string; color: string }) =>
    http.post<Group>('/api/groups', payload).then((r) => r.data),
  update: (id: number, payload: Partial<{ name: string; color: string }>) =>
    http.put<Group>(`/api/groups/${id}`, payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/api/groups/${id}`),
  assign: (contactId: number, groupId: number) =>
    http.post(`/api/contacts/${contactId}/groups/${groupId}`),
  unassign: (contactId: number, groupId: number) =>
    http.delete(`/api/contacts/${contactId}/groups/${groupId}`),
}

export const interactionsApi = {
  list: (contactId: number) =>
    http.get<Interaction[]>(`/api/contacts/${contactId}/interactions`).then((r) => r.data),
  create: (contactId: number, payload: { type: string; content: string; occurred_at?: string }) =>
    http.post<Interaction>(`/api/contacts/${contactId}/interactions`, payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/api/interactions/${id}`),
}

export const remindersApi = {
  listGlobal: (status: 'pending' | 'overdue' | 'done' = 'pending') =>
    http.get<Reminder[]>('/api/reminders', { params: { status } }).then((r) => r.data),
  listForContact: (contactId: number) =>
    http.get<Reminder[]>(`/api/contacts/${contactId}/reminders`).then((r) => r.data),
  create: (contactId: number, payload: { due_date: string; note?: string }) =>
    http.post<Reminder>(`/api/contacts/${contactId}/reminders`, payload).then((r) => r.data),
  update: (id: number, payload: Partial<{ due_date: string; note: string; is_done: boolean }>) =>
    http.patch<Reminder>(`/api/reminders/${id}`, payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/api/reminders/${id}`),
}

export const geocodeApi = {
  company: (companyName: string, forceRetry = false) =>
    http
      .post<GeocodeResult>('/api/geocode/company', { company_name: companyName, force_retry: forceRetry })
      .then((r) => r.data),
  bulk: (chunkSize = 15) =>
    http.post<BulkGeocodeResult>('/api/geocode/bulk', null, { params: { chunk_size: chunkSize } }).then((r) => r.data),
}

export const importApi = {
  linkedin: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http.post<ImportSummary>('/api/import/linkedin', form).then((r) => r.data)
  },
}

export const statsApi = {
  get: () => http.get<StatsOut>('/api/stats').then((r) => r.data),
}
