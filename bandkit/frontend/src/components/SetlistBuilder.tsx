import { useEffect, useState } from 'react'
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor,
  useSensor, useSensors, DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates,
  useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { eventsApi, musiciansApi, songsApi } from '../api/client'
import type { Musician, SetlistItem, Song } from '../types'

// ── Item arrastável ───────────────────────────────────────────────

function SortableRow({
  item, song, musicians, allMusicians, eventId,
  onMusicianAdded, onMusicianRemoved,
}: {
  item: SetlistItem
  song: Song | undefined
  musicians: Musician[]
  allMusicians: Musician[]
  eventId: number
  onMusicianAdded: (itemId: number, m: { id: number; musician_id: number; instrument_override: string | null }) => void
  onMusicianRemoved: (itemId: number, musicianId: number) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.id })
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  const [showAdd, setShowAdd] = useState(false)
  const [addingId, setAddingId] = useState<number | null>(null)
  const [instrument, setInstrument] = useState('')

  const assigned = new Set(item.musicians.map((m) => m.musician_id))
  const available = allMusicians.filter((m) => !assigned.has(m.id))

  const handleAdd = async () => {
    if (!addingId) return
    const sm = await eventsApi.addMusicianToItem(eventId, item.id, addingId, instrument || undefined)
    onMusicianAdded(item.id, sm)
    setShowAdd(false)
    setAddingId(null)
    setInstrument('')
  }

  return (
    <div ref={setNodeRef} style={style} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      {/* Header da música */}
      <div className="flex items-center gap-3 px-3 py-2">
        <button {...attributes} {...listeners}
          className="text-gray-300 hover:text-gray-500 cursor-grab active:cursor-grabbing touch-none text-lg"
          aria-label="drag">⠿</button>
        <span className="text-xs text-gray-400 w-5 text-right shrink-0">{item.order_position}.</span>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-gray-900 truncate">{song?.title ?? `#${item.song_id}`}</div>
          {song?.artist && <div className="text-xs text-gray-400 truncate">{song.artist}</div>}
        </div>
        {item.key_override && (
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded shrink-0">
            {item.key_override}
          </span>
        )}
        {song?.key_original && !item.key_override && (
          <span className="text-xs text-gray-300 shrink-0">{song.key_original}</span>
        )}
      </div>

      {/* Músicos atribuídos */}
      <div className="px-3 pb-2 flex flex-wrap gap-1">
        {item.musicians.map((sm) => {
          const m = musicians.find((x) => x.id === sm.musician_id)
          return (
            <span key={sm.id} className="inline-flex items-center gap-1 bg-green-50 text-green-700 text-xs px-2 py-0.5 rounded-full">
              {m?.name ?? `#${sm.musician_id}`}
              {sm.instrument_override && <span className="opacity-60">· {sm.instrument_override}</span>}
              <button onClick={() => onMusicianRemoved(item.id, sm.musician_id)}
                className="ml-0.5 opacity-50 hover:opacity-100">×</button>
            </span>
          )
        })}

        {available.length > 0 && !showAdd && (
          <button onClick={() => setShowAdd(true)}
            className="text-xs text-gray-400 hover:text-blue-600 px-1">
            + músico
          </button>
        )}
      </div>

      {/* Formulário de adição de músico */}
      {showAdd && (
        <div className="px-3 pb-3 flex items-center gap-2 bg-gray-50 border-t border-gray-100">
          <select
            value={addingId ?? ''}
            onChange={(e) => setAddingId(Number(e.target.value) || null)}
            className="text-xs border border-gray-200 rounded px-2 py-1 flex-1"
          >
            <option value="">Selecionar músico…</option>
            {available.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}{m.instrument ? ` (${m.instrument})` : ''}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Instrumento"
            value={instrument}
            onChange={(e) => setInstrument(e.target.value)}
            className="text-xs border border-gray-200 rounded px-2 py-1 w-28"
          />
          <button onClick={handleAdd} disabled={!addingId}
            className="text-xs bg-blue-600 text-white px-2 py-1 rounded disabled:opacity-40">
            OK
          </button>
          <button onClick={() => setShowAdd(false)} className="text-xs text-gray-400 hover:text-gray-600">
            ×
          </button>
        </div>
      )}
    </div>
  )
}

// ── SetlistBuilder principal ──────────────────────────────────────

interface Props {
  eventId: number
  items: SetlistItem[]
  onUpdate: (items: SetlistItem[]) => void
}

export default function SetlistBuilder({ eventId, items, onUpdate }: Props) {
  const [songs, setSongs] = useState<Song[]>([])
  const [allMusicians, setAllMusicians] = useState<Musician[]>([])
  const [search, setSearch] = useState('')
  const [showSearch, setShowSearch] = useState(false)
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    songsApi.list().then(setSongs)
    musiciansApi.list().then(setAllMusicians)
  }, [])

  const songMap = Object.fromEntries(songs.map((s) => [s.id, s]))
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIdx = items.findIndex((i) => i.id === active.id)
    const newIdx = items.findIndex((i) => i.id === over.id)
    const reordered = arrayMove(items, oldIdx, newIdx).map((item, idx) => ({
      ...item, order_position: idx + 1,
    }))
    onUpdate(reordered)
    await eventsApi.reorderSetlist(eventId, reordered.map((i) => ({ id: i.id, order_position: i.order_position }))).catch(() => {})
  }

  const addSong = async (song: Song) => {
    setAdding(true)
    try {
      const item = await eventsApi.addToSetlist(eventId, { song_id: song.id, order_position: items.length + 1 })
      onUpdate([...items, item as SetlistItem])
      setSearch('')
      setShowSearch(false)
    } catch (err: unknown) {
      if ((err as { response?: { status: number } })?.response?.status === 409) alert('Posição já ocupada')
    } finally {
      setAdding(false)
    }
  }

  const handleMusicianAdded = (
    itemId: number,
    sm: { id: number; musician_id: number; instrument_override: string | null },
  ) => {
    onUpdate(items.map((it) =>
      it.id === itemId ? { ...it, musicians: [...it.musicians, sm] } : it
    ))
  }

  const handleMusicianRemoved = async (itemId: number, musicianId: number) => {
    await eventsApi.removeMusicianFromItem(eventId, itemId, musicianId).catch(() => {})
    onUpdate(items.map((it) =>
      it.id === itemId
        ? { ...it, musicians: it.musicians.filter((m) => m.musician_id !== musicianId) }
        : it
    ))
  }

  const filtered = songs.filter(
    (s) => !items.some((i) => i.song_id === s.id) &&
      (s.title.toLowerCase().includes(search.toLowerCase()) ||
        (s.artist ?? '').toLowerCase().includes(search.toLowerCase()))
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Setlist</h3>
        <span className="text-xs text-gray-400">{items.length} músicas</span>
      </div>

      {items.length === 0 ? (
        <p className="text-sm text-gray-400 italic">Setlist vazio.</p>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
            <div className="space-y-2">
              {items.map((item) => (
                <SortableRow
                  key={item.id}
                  item={item}
                  song={songMap[item.song_id]}
                  musicians={allMusicians}
                  allMusicians={allMusicians}
                  eventId={eventId}
                  onMusicianAdded={handleMusicianAdded}
                  onMusicianRemoved={handleMusicianRemoved}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      {/* Adicionar música */}
      <div className="border-t border-gray-100 pt-3">
        {!showSearch ? (
          <button onClick={() => setShowSearch(true)}
            className="text-sm text-blue-600 hover:text-blue-700 font-medium">
            + Adicionar música
          </button>
        ) : (
          <div className="space-y-2">
            <input autoFocus type="text" placeholder="Buscar música…" value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
            <div className="max-h-48 overflow-auto space-y-1">
              {filtered.length === 0 && <p className="text-xs text-gray-400 px-2">Nenhuma música</p>}
              {filtered.map((song) => (
                <button key={song.id} onClick={() => addSong(song)} disabled={adding}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 rounded-lg flex justify-between gap-2">
                  <span className="font-medium truncate">{song.title}</span>
                  <span className="text-gray-400 shrink-0">{song.artist}</span>
                </button>
              ))}
            </div>
            <button onClick={() => { setShowSearch(false); setSearch('') }}
              className="text-xs text-gray-400 hover:text-gray-600">Fechar</button>
          </div>
        )}
      </div>
    </div>
  )
}
