import { create } from 'zustand'

interface FiltersState {
  q: string
  groupId: number | null
  company: string | null
  position: string | null
  city: string | null
  sort: 'name' | 'company' | 'connected_on' | 'recent'
  page: number
  setQ: (q: string) => void
  setGroupId: (id: number | null) => void
  setCompany: (company: string | null) => void
  setPosition: (position: string | null) => void
  setCity: (city: string | null) => void
  setSort: (sort: FiltersState['sort']) => void
  setPage: (page: number) => void
  reset: () => void
}

const initial = {
  q: '',
  groupId: null,
  company: null,
  position: null,
  city: null,
  sort: 'name' as const,
  page: 1,
}

export const useFiltersStore = create<FiltersState>((set) => ({
  ...initial,
  setQ: (q) => set({ q, page: 1 }),
  setGroupId: (groupId) => set({ groupId, page: 1 }),
  setCompany: (company) => set({ company, page: 1 }),
  setPosition: (position) => set({ position, page: 1 }),
  setCity: (city) => set({ city, page: 1 }),
  setSort: (sort) => set({ sort, page: 1 }),
  setPage: (page) => set({ page }),
  reset: () => set(initial),
}))
