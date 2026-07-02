import { useEffect, useState } from 'react'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { setlistsApi, songsApi } from '../../api/client'
import type { Setlist, SetlistSong, Song } from '../../types'

// ── Item arrastável ────────────────────────────────────────────────

function SortableSongRow({
  entry, idx, song, onRemove,
}: {
  entry: SetlistSong
  idx: number
  song: Song | undefined
  onRemove: () => void
}) {
  const {
    attributes, listeners, setNodeRef,
    transform, transition, isDragging,
  } = useSortable({ id: entry.id })

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.45 : 1,
    zIndex: isDragging ? 10 : undefined,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="bg-white border border-gray-200 rounded-xl flex items-center gap-3 px-4 py-3 select-none"
    >
      {/* Alça de drag */}
      <button
        {...attributes}
        {...listeners}
        className="text-gray-300 hover:text-gray-500 cursor-grab active:cursor-grabbing touch-none text-base leading-none p-0.5"
        aria-label="Arrastar"
      >
        ⠿
      </button>

      <span className="text-gray-400 text-sm font-mono w-5 text-right shrink-0">{idx + 1}.</span>

      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-gray-900 truncate">
          {song?.title ?? `#${entry.song_id}`}
        </div>
        {song?.artist && (
          <div className="text-xs text-gray-400 truncate">{song.artist}</div>
        )}
      </div>

      {song?.key_original && (
        <span className="text-xs text-gray-400 shrink-0">{song.key_original}</span>
      )}

      <button
        onClick={onRemove}
        className="text-gray-300 hover:text-red-500 text-sm shrink-0 ml-1"
        title="Remover do setlist"
      >
        🗑
      </button>
    </div>
  )
}

// ── Página principal ───────────────────────────────────────────────

export default function SetlistsPage() {
  const [setlists,  setSetlists]  = useState<Setlist[]>([])
  const [songs,     setSongs]     = useState<Song[]>([])
  const [selected,  setSelected]  = useState<Setlist | null>(null)
  const [newName,   setNewName]   = useState('')
  const [search,    setSearch]    = useState('')
  const [showNew,   setShowNew]   = useState(false)
  const [creating,  setCreating]  = useState(false)
  const [addingId,  setAddingId]  = useState<number | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  useEffect(() => {
    setlistsApi.list().then(d => setSetlists(d as Setlist[]))
    songsApi.list().then(d => setSongs(d as Song[]))
  }, [])

  const songMap = Object.fromEntries(songs.map(s => [s.id, s]))

  const reload = async () => {
    const sls = await setlistsApi.list() as Setlist[]
    setSetlists(sls)
    if (selected) {
      const fresh = sls.find(s => s.id === selected.id)
      setSelected(fresh ?? null)
    }
  }

  // ── Drag & drop ──────────────────────────────────────────────────

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id || !selected) return

    const oldIdx = selected.songs.findIndex(e => e.id === active.id)
    const newIdx = selected.songs.findIndex(e => e.id === over.id)
    if (oldIdx === -1 || newIdx === -1) return

    // Atualização otimista: reordena localmente imediatamente
    const reordered = arrayMove(selected.songs, oldIdx, newIdx).map(
      (entry, i) => ({ ...entry, order_position: i + 1 }),
    )
    setSelected({ ...selected, songs: reordered })
    setSetlists(ss =>
      ss.map(sl => sl.id === selected.id ? { ...sl, songs: reordered } : sl),
    )

    // Persiste no servidor
    await setlistsApi.reorder(
      selected.id,
      reordered.map(e => ({ id: e.id, order_position: e.order_position })),
    ).catch(() => reload()) // reverte se falhar
  }

  // ── CRUD setlist ─────────────────────────────────────────────────

  const createSetlist = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newName.trim()) return
    setCreating(true)
    const sl = await setlistsApi.create({ name: newName.trim() }) as Setlist
    setSetlists(ss => [...ss, sl])
    setSelected(sl)
    setNewName(''); setShowNew(false); setCreating(false)
  }

  const deleteSetlist = async (sl: Setlist) => {
    if (!confirm(`Apagar setlist "${sl.name}"?`)) return
    await setlistsApi.delete(sl.id)
    setSetlists(ss => ss.filter(s => s.id !== sl.id))
    if (selected?.id === sl.id) setSelected(null)
  }

  const duplicateSetlist = async (sl: Setlist) => {
    const name = prompt('Nome do novo setlist:', sl.name + ' (cópia)')
    if (name === null) return
    const copy = await setlistsApi.duplicate(sl.id, name.trim() || undefined) as Setlist
    setSetlists(ss => [...ss, copy])
    setSelected(copy)
  }

  // ── Músicas ───────────────────────────────────────────────────────

  const addSong = async (song: Song) => {
    if (!selected || addingId !== null) return
    setAddingId(song.id)
    try {
      const nextPos = selected.songs.length > 0
        ? Math.max(...selected.songs.map(s => s.order_position)) + 1
        : 1
      await setlistsApi.addSong(selected.id, { song_id: song.id, order_position: nextPos })
      await reload()
    } catch {
      alert('Erro ao adicionar música. Tente novamente.')
    } finally {
      setAddingId(null)
    }
  }

  const removeSong = async (entryId: number) => {
    if (!selected) return
    await setlistsApi.removeSong(selected.id, entryId)
    await reload()
  }

  const availableSongs = songs.filter(s =>
    !selected?.songs.some(e => e.song_id === s.id) &&
    (s.title.toLowerCase().includes(search.toLowerCase()) ||
      (s.artist ?? '').toLowerCase().includes(search.toLowerCase()))
  )

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="flex h-screen bg-gray-50">

      {/* Sidebar: lista de setlists */}
      <div className="w-72 bg-white border-r border-gray-200 flex flex-col shrink-0">
        <div className="p-4 border-b border-gray-100">
          <h1 className="text-lg font-semibold text-gray-900 mb-3">Setlists</h1>
          {showNew ? (
            <form onSubmit={createSetlist} className="flex gap-2">
              <input
                autoFocus type="text" placeholder="Nome…" value={newName}
                onChange={e => setNewName(e.target.value)}
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
              />
              <button
                type="submit" disabled={creating}
                className="bg-blue-600 text-white text-sm px-3 py-1 rounded-lg disabled:opacity-50"
              >OK</button>
            </form>
          ) : (
            <button
              onClick={() => setShowNew(true)}
              className="w-full bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700"
            >
              + Novo setlist
            </button>
          )}
        </div>

        <div className="flex-1 overflow-auto divide-y divide-gray-50">
          {setlists.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">Nenhum setlist criado ainda.</p>
          )}
          {setlists.map(sl => (
            <div
              key={sl.id}
              onClick={() => setSelected(sl)}
              className={`group flex items-center px-4 py-3 cursor-pointer hover:bg-gray-50 transition ${
                selected?.id === sl.id ? 'bg-blue-50 border-l-2 border-blue-500' : ''
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-900 truncate">{sl.name}</div>
                <div className="text-xs text-gray-400">{sl.songs.length} músicas</div>
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition ml-2">
                <button
                  onClick={e => { e.stopPropagation(); duplicateSetlist(sl) }}
                  className="text-gray-400 hover:text-blue-600 text-sm p-0.5"
                  title="Duplicar"
                >⊕</button>
                <button
                  onClick={e => { e.stopPropagation(); deleteSetlist(sl) }}
                  className="text-gray-300 hover:text-red-500 text-sm p-0.5"
                  title="Apagar"
                >🗑</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Editor do setlist selecionado */}
      {selected ? (
        <div className="flex-1 flex overflow-hidden">

          {/* Lista de músicas com drag & drop */}
          <div className="flex-1 overflow-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900">{selected.name}</h2>
              {selected.songs.length > 0 && (
                <span className="text-xs text-gray-400">Arraste ⠿ para reordenar</span>
              )}
            </div>

            {selected.songs.length === 0 ? (
              <p className="text-sm text-gray-400 italic">
                Setlist vazio. Adicione músicas da biblioteca →
              </p>
            ) : (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
              >
                <SortableContext
                  items={selected.songs.map(e => e.id)}
                  strategy={verticalListSortingStrategy}
                >
                  <div className="space-y-2 max-w-xl">
                    {selected.songs.map((entry, idx) => (
                      <SortableSongRow
                        key={entry.id}
                        entry={entry}
                        idx={idx}
                        song={songMap[entry.song_id]}
                        onRemove={() => removeSong(entry.id)}
                      />
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
            )}
          </div>

          {/* Biblioteca de músicas */}
          <div className="w-72 bg-white border-l border-gray-200 flex flex-col shrink-0">
            <div className="p-4 border-b border-gray-100">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Adicionar música
              </div>
              <input
                type="text" placeholder="Buscar…" value={search}
                onChange={e => setSearch(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div className="flex-1 overflow-auto divide-y divide-gray-50">
              {availableSongs.map(song => (
                <button
                  key={song.id}
                  onClick={() => addSong(song)}
                  disabled={addingId !== null}
                  className="w-full text-left px-4 py-3 hover:bg-blue-50 transition disabled:opacity-50 disabled:cursor-wait"
                >
                  <div className="text-sm font-medium text-gray-900 truncate">
                    {addingId === song.id ? '…' : song.title}
                  </div>
                  {song.artist && (
                    <div className="text-xs text-gray-400 truncate">{song.artist}</div>
                  )}
                  {song.key_original && (
                    <div className="text-xs text-gray-300">{song.key_original}</div>
                  )}
                </button>
              ))}
              {availableSongs.length === 0 && (
                <p className="text-xs text-gray-400 text-center py-6">Nenhuma música disponível</p>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-400">
          <div className="text-center">
            <div className="text-4xl mb-3">📋</div>
            <p className="text-sm">Selecione um setlist ou crie um novo</p>
          </div>
        </div>
      )}
    </div>
  )
}
