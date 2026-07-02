import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AppState {
  mode: 'admin' | 'musician' | null
  currentMusician: { id: number; name: string; role: string } | null
  setMode: (mode: 'admin' | 'musician') => void
  setMusician: (m: AppState['currentMusician']) => void
  logout: () => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      mode: null,
      currentMusician: null,
      setMode: (mode) => set({ mode }),
      setMusician: (m) => set({ currentMusician: m }),
      logout: () => set({ mode: null, currentMusician: null }),
    }),
    { name: 'bandkit-session' }
  )
)

interface MusicianStore {
  semitones: number
  currentSongId: number | null
  increment: () => void
  decrement: () => void
  reset: () => void
  setSemitones: (n: number) => void
  setCurrentSong: (id: number) => void
}

export const useMusicianStore = create<MusicianStore>()((set) => ({
  semitones: 0,
  currentSongId: null,
  increment: () => set((s) => ({ semitones: s.semitones + 1 })),
  decrement: () => set((s) => ({ semitones: s.semitones - 1 })),
  reset: () => set({ semitones: 0 }),
  setSemitones: (n) => set({ semitones: n }),
  setCurrentSong: (id) => set({ currentSongId: id, semitones: 0 }),
}))
