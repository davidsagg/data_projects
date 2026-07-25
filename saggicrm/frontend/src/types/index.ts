export type InteractionType = 'note' | 'call' | 'meeting' | 'email' | 'coffee' | 'other'
export type ContactSource = 'linkedin_import' | 'manual'

export interface Group {
  id: number
  name: string
  color: string
  created_at: string
}

export interface Interaction {
  id: number
  contact_id: number
  type: InteractionType
  content: string
  occurred_at: string
  created_at: string
}

export interface Reminder {
  id: number
  contact_id: number
  due_date: string
  note: string | null
  is_done: boolean
  created_at: string
  completed_at: string | null
}

export interface ContactListItem {
  id: number
  first_name: string
  last_name: string
  linkedin_url: string | null
  email: string | null
  company: string | null
  position: string | null
  connected_on: string | null
  city: string | null
  country: string | null
  latitude: number | null
  longitude: number | null
  source: ContactSource
  groups: Group[]
  last_contacted_at: string | null
}

export interface ContactDetail extends ContactListItem {
  interactions: Interaction[]
  reminders: Reminder[]
}

export interface ContactPage {
  items: ContactListItem[]
  total: number
  page: number
  page_size: number
}

export interface ImportSummary {
  created: number
  updated: number
  skipped_blank: number
  total_rows: number
}

export interface FacetItem {
  value: string
  count: number
}

export interface StatsOut {
  total_contacts: number
  total_groups: number
  contacts_missing_city: number
  top_companies: FacetItem[]
  contacts_by_group: FacetItem[]
  connections_by_year: FacetItem[]
  upcoming_reminders: Reminder[]
  recent_contacts: ContactListItem[]
}

export interface GeocodeResult {
  company_name: string
  found: boolean
  city: string | null
  country: string | null
  latitude: number | null
  longitude: number | null
}

export interface BulkGeocodeResult {
  processed: number
  remaining: number
  results: GeocodeResult[]
}
