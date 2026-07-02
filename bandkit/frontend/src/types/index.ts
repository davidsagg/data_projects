export interface Musician {
  id: number; name: string; instrument: string | null; role: string; email: string | null; photo_url: string | null
}

export interface Song {
  id: number; title: string; artist: string | null; key_original: string | null
  bkcp_content: string | null; genre_tags: string | null; tempo_bpm: number | null
  duration_sec: number | null; parse_status: string
}

export interface SongBrief {
  id: number; title: string; artist: string | null; key_original: string | null; parse_status: string
}

export interface SetlistSong {
  id: number; song_id: number; order_position: number; notes: string | null; song: SongBrief | null
}

export interface Setlist {
  id: number; name: string; notes: string | null; created_at: string; songs: SetlistSong[]
}

export interface SetlistBrief {
  id: number; name: string; notes: string | null
}

export interface BandEvent {
  id: number; title: string; date: string; event_type: string; status: string
  venue: string | null; venue_address: string | null; notes: string | null
  duration_min: number | null; setlist_id: number | null; setlist: SetlistBrief | null
}

export interface ExecutionMusician {
  id: number; musician_id: number; instrument_override: string | null
}

export interface MusicalExecution {
  id: number; song_id: number; order_position: number | null
  key_override: string | null; notes: string | null
  musicians: ExecutionMusician[]
}
