import { create } from 'zustand'

type SortField = 'name' | 'company' | 'seniority' | 'connected_on' | 'recent'
type SortDir = 'asc' | 'desc'

const DEFAULT_SORT_DIR: Record<SortField, SortDir> = {
  name: 'asc',
  company: 'asc',
  seniority: 'asc',
  connected_on: 'desc',
  recent: 'desc',
}

interface FiltersState {
  q: string
  groupId: number | null
  companyId: number | null
  sector: string | null
  seniority: string | null
  position: string | null
  city: string | null
  favoriteOnly: boolean
  sort: SortField
  sortDir: SortDir
  page: number
  setQ: (q: string) => void
  setGroupId: (id: number | null) => void
  setCompanyId: (companyId: number | null) => void
  setSector: (sector: string | null) => void
  setSeniority: (seniority: string | null) => void
  setPosition: (position: string | null) => void
  setCity: (city: string | null) => void
  setFavoriteOnly: (favoriteOnly: boolean) => void
  /** Clicking the active column again flips direction; a new column resets to its default. */
  toggleSort: (field: SortField) => void
  setPage: (page: number) => void
  reset: () => void
}

const initial = {
  q: '',
  groupId: null,
  companyId: null,
  sector: null,
  seniority: null,
  position: null,
  city: null,
  favoriteOnly: false,
  sort: 'name' as const,
  sortDir: 'asc' as const,
  page: 1,
}

export const useFiltersStore = create<FiltersState>((set, get) => ({
  ...initial,
  setQ: (q) => set({ q, page: 1 }),
  setGroupId: (groupId) => set({ groupId, page: 1 }),
  setCompanyId: (companyId) => set({ companyId, page: 1 }),
  setSector: (sector) => set({ sector, page: 1 }),
  setSeniority: (seniority) => set({ seniority, page: 1 }),
  setPosition: (position) => set({ position, page: 1 }),
  setCity: (city) => set({ city, page: 1 }),
  setFavoriteOnly: (favoriteOnly) => set({ favoriteOnly, page: 1 }),
  toggleSort: (field) => {
    const { sort, sortDir } = get()
    if (field === sort) {
      set({ sortDir: sortDir === 'asc' ? 'desc' : 'asc', page: 1 })
    } else {
      set({ sort: field, sortDir: DEFAULT_SORT_DIR[field], page: 1 })
    }
  },
  setPage: (page) => set({ page }),
  reset: () => set(initial),
}))
