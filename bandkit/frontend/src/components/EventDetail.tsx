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
import { executionsApi, musiciansApi, songsApi } from '../api/client'
import type { BandEvent, Musician, MusicalExecution, Song } from '../types'
import DuplicateEventModal from './DuplicateEventModal'

const TYPE_LABELS: Record<string, string> = { show: 'Show', rehearsal: 'Ensaio', recording: 'Gravação', other: 'Outro' }
const STATUS_STYLE: Record<string, string> = {
  confirmed: 'bg-green-100 text-green-700',
  tentative: 'bg-yellow-100 text-yellow-700',
  cancelled: 'bg-red-100 text-red-500',
}

interface Props { event: BandEvent; onClose: () => void; onUpdated: () => void }

export default function EventDetail({ event, onClose, onUpdated }: Props) {
  const [executions, setExecutions] = useState<MusicalExecution[]>([])
  const [songs,      setSongs]      = useState<Song[]>([])
  const [musicians,  setMusicians]  = useState<Musician[]>([])
  const [addingSong, setAddingSong] = useState(false)
  const [songSearch, setSongSearch] = useState('')
  const [syncing,    setSyncing]    = useState(false)
  const [showDuplicate, setShowDuplicate] = useState(false)

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  useEffect(() => {
    executionsApi.list(event.id).then(d => setExecutions(d as MusicalExecution[]))
    songsApi.list().then(d => setSongs(d as Song[]))
    musiciansApi.list().then(d => setMusicians(d as Musician[]))
  }, [event.id])

  const songMap     = Object.fromEntries(songs.map(s => [s.id, s]))
  const musicianMap = Object.fromEntries(musicians.map(m => [m.id, m]))
  const executionSongIds = new Set(executions.map(e => e.song_id))

  // ── Drag & drop de execuções ───────────────────────────────────

  const handleDragEnd = async (dndEvent: DragEndEvent) => {
    const { active, over } = dndEvent
    if (!over || active.id === over.id) return

    const oldIdx = executions.findIndex(e => e.id === active.id)
    const newIdx = executions.findIndex(e => e.id === over.id)
    if (oldIdx === -1 || newIdx === -1) return

    const reordered = arrayMove(executions, oldIdx, newIdx).map(
      (ex, i) => ({ ...ex, order_position: i + 1 }),
    )
    setExecutions(reordered)   // optimistic

    await executionsApi.reorderExecutions(
      event.id,
      reordered.map(ex => ({ id: ex.id, order_position: ex.order_position ?? 0 })),
    ).catch(() => {
      executionsApi.list(event.id).then(d => setExecutions(d as MusicalExecution[]))
    })
  }

  // ── Setlist sync ────────────────────────────────────────────────

  const syncSetlist = async () => {
    setSyncing(true)
    const execs = await executionsApi.syncSetlist(event.id).catch(() => null)
    if (execs) setExecutions(execs as MusicalExecution[])
    setSyncing(false)
    onUpdated()
  }

  // ── Músicas ─────────────────────────────────────────────────────

  const addExecution = async (song: Song) => {
    const ex = await executionsApi.create(event.id, { song_id: song.id })
    setExecutions(es => [...es, ex as MusicalExecution])
    setAddingSong(false); setSongSearch('')
    onUpdated()
  }

  const removeExecution = async (execId: number) => {
    if (!confirm('Remover esta música do evento?')) return
    await executionsApi.delete(event.id, execId)
    setExecutions(es => es.filter(e => e.id !== execId))
    onUpdated()
  }

  const patchKey = async (exec: MusicalExecution, key: string) => {
    const updated = await executionsApi.patch(event.id, exec.id, { key_override: key || null })
    setExecutions(es => es.map(e => e.id === exec.id ? updated as MusicalExecution : e))
  }

  const addMusician = async (execId: number, musicianId: number, instrument: string) => {
    const em = await executionsApi.addMusician(event.id, execId, { musician_id: musicianId, instrument_override: instrument || null })
    setExecutions(es => es.map(e => e.id === execId ? { ...e, musicians: [...e.musicians, em] } : e))
  }

  const removeMusician = async (execId: number, musicianId: number) => {
    await executionsApi.removeMusician(event.id, execId, musicianId)
    setExecutions(es => es.map(e => e.id === execId
      ? { ...e, musicians: e.musicians.filter(m => m.musician_id !== musicianId) }
      : e))
  }

  const filteredSongs = songs.filter(s =>
    !executionSongIds.has(s.id) &&
    (s.title.toLowerCase().includes(songSearch.toLowerCase()) ||
      (s.artist ?? '').toLowerCase().includes(songSearch.toLowerCase()))
  )

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">

        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-gray-100 shrink-0">
          <div>
            <h2 className="text-base font-semibold text-gray-900">{event.title}</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {new Date(event.date).toLocaleString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
              {event.venue && ` · ${event.venue}`}
            </p>
            <div className="flex gap-2 mt-2">
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{TYPE_LABELS[event.event_type] ?? event.event_type}</span>
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_STYLE[event.status] ?? 'bg-gray-100'}`}>
                {event.status === 'confirmed' ? 'Confirmado' : event.status === 'cancelled' ? 'Cancelado' : 'Provável'}
              </span>
              {event.setlist && <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded">📋 {event.setlist.name}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2 ml-4 shrink-0">
            <button
              onClick={() => setShowDuplicate(true)}
              className="text-xs text-gray-500 hover:text-blue-600 border border-gray-200 px-2 py-1 rounded-lg hover:border-blue-400 transition"
              title="Duplicar evento"
            >
              ⊕ Duplicar
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
          </div>
        </div>

        {/* Execuções */}
        <div className="flex-1 overflow-auto p-6 space-y-3">
          <div className="flex items-center justify-between mb-1">
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
              Execuções · {executions.length}
            </h3>
            <div className="flex items-center gap-3">
              {executions.length > 1 && (
                <span className="text-xs text-gray-400">Arraste ⠿ para reordenar</span>
              )}
              {event.setlist_id && (
                <button onClick={syncSetlist} disabled={syncing}
                  className="text-xs text-blue-600 hover:underline disabled:opacity-50">
                  {syncing ? 'Sincronizando…' : '↻ Sincronizar setlist'}
                </button>
              )}
            </div>
          </div>

          {executions.length === 0 && (
            <p className="text-sm text-gray-400 italic">Nenhuma música neste evento ainda.</p>
          )}

          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={executions.map(e => e.id)} strategy={verticalListSortingStrategy}>
              <div className="space-y-2">
                {executions.map(exec => (
                  <SortableExecutionRow
                    key={exec.id}
                    exec={exec}
                    song={songMap[exec.song_id]}
                    musicianMap={musicianMap}
                    available={musicians.filter(m => !exec.musicians.some(em => em.musician_id === m.id))}
                    onPatchKey={(k) => patchKey(exec, k)}
                    onAddMusician={(mid, inst) => addMusician(exec.id, mid, inst)}
                    onRemoveMusician={(mid) => removeMusician(exec.id, mid)}
                    onRemove={() => removeExecution(exec.id)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>

          {/* Adicionar música */}
          {!addingSong ? (
            <button onClick={() => setAddingSong(true)}
              className="text-sm text-blue-600 hover:text-blue-700 font-medium">
              + Adicionar música
            </button>
          ) : (
            <div className="space-y-2 border border-gray-200 rounded-xl p-3">
              <input autoFocus type="text" placeholder="Buscar música…"
                value={songSearch} onChange={e => setSongSearch(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
              <div className="max-h-40 overflow-auto space-y-1">
                {filteredSongs.map(s => (
                  <button key={s.id} onClick={() => addExecution(s)}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 rounded-lg flex justify-between">
                    <span className="font-medium truncate">{s.title}</span>
                    <span className="text-gray-400 shrink-0 ml-2">{s.artist}</span>
                  </button>
                ))}
              </div>
              <button onClick={() => { setAddingSong(false); setSongSearch('') }}
                className="text-xs text-gray-400 hover:text-gray-600">Fechar</button>
            </div>
          )}
        </div>

        {showDuplicate && (
          <DuplicateEventModal
            event={event}
            onClose={() => setShowDuplicate(false)}
            onDuplicated={(newEvent) => {
              setShowDuplicate(false)
              onUpdated()
              onClose()
              alert(`Evento "${newEvent.title}" duplicado com sucesso!`)
            }}
          />
        )}
      </div>
    </div>
  )
}

// ── Linha de execução arrastável ──────────────────────────────────

function SortableExecutionRow({
  exec, song, musicianMap, available,
  onPatchKey, onAddMusician, onRemoveMusician, onRemove,
}: {
  exec: MusicalExecution
  song: Song | undefined
  musicianMap: Record<number, Musician>
  available: Musician[]
  onPatchKey: (k: string) => void
  onAddMusician: (mid: number, inst: string) => void
  onRemoveMusician: (mid: number) => void
  onRemove: () => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: exec.id })

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.45 : 1,
    zIndex: isDragging ? 10 : undefined,
  }

  const [editKey,  setEditKey]  = useState(false)
  const [keyVal,   setKeyVal]   = useState(exec.key_override ?? '')
  const [showAdd,  setShowAdd]  = useState(false)
  const [addingId, setAddingId] = useState<number | ''>('')
  const [instrument, setInstrument] = useState('')

  const saveKey = () => { onPatchKey(keyVal); setEditKey(false) }

  const handleAdd = () => {
    if (!addingId) return
    onAddMusician(Number(addingId), instrument)
    setShowAdd(false); setAddingId(''); setInstrument('')
  }

  return (
    <div ref={setNodeRef} style={style} className="border border-gray-200 rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-3">
        {/* Alça drag */}
        <button
          {...attributes} {...listeners}
          className="text-gray-300 hover:text-gray-500 cursor-grab active:cursor-grabbing touch-none text-base leading-none shrink-0"
          aria-label="Arrastar"
        >⠿</button>

        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-gray-900 truncate">{song?.title ?? `#${exec.song_id}`}</div>
          {song?.artist && <div className="text-xs text-gray-400 truncate">{song.artist}</div>}
        </div>

        {/* Tom */}
        <div className="flex items-center gap-1 shrink-0">
          {editKey ? (
            <>
              <input autoFocus value={keyVal} onChange={e => setKeyVal(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') saveKey() }}
                className="w-14 text-sm border border-blue-400 rounded px-2 py-0.5 text-center" />
              <button onClick={saveKey} className="text-xs text-blue-600 hover:underline">OK</button>
            </>
          ) : (
            <button onClick={() => { setKeyVal(exec.key_override ?? ''); setEditKey(true) }}
              className="text-sm font-bold text-blue-600 hover:underline min-w-[2rem] text-center">
              {exec.key_override ?? song?.key_original ?? '—'}
            </button>
          )}
        </div>

        <button onClick={onRemove} className="text-gray-300 hover:text-red-500 text-sm ml-1 shrink-0">🗑</button>
      </div>

      {/* Músicos */}
      <div className="px-4 pb-3 flex flex-wrap gap-1">
        {exec.musicians.map(em => {
          const m = musicianMap[em.musician_id]
          return (
            <span key={em.id} className="inline-flex items-center gap-1 bg-green-50 text-green-700 text-xs px-2 py-0.5 rounded-full">
              {m?.name ?? `#${em.musician_id}`}
              {em.instrument_override && <span className="opacity-60">· {em.instrument_override}</span>}
              <button onClick={() => onRemoveMusician(em.musician_id)} className="opacity-50 hover:opacity-100 ml-0.5">×</button>
            </span>
          )
        })}

        {available.length > 0 && !showAdd && (
          <button onClick={() => setShowAdd(true)} className="text-xs text-gray-400 hover:text-blue-600 px-1">+ músico</button>
        )}
      </div>

      {showAdd && (
        <div className="px-4 pb-3 flex items-center gap-2 bg-gray-50 border-t border-gray-100">
          <select value={addingId} onChange={e => setAddingId(e.target.value as unknown as number | '')}
            className="text-xs border border-gray-200 rounded px-2 py-1 flex-1">
            <option value="">Selecionar…</option>
            {available.map(m => <option key={m.id} value={m.id}>{m.name}{m.instrument ? ` (${m.instrument})` : ''}</option>)}
          </select>
          <input type="text" placeholder="Instrumento" value={instrument}
            onChange={e => setInstrument(e.target.value)}
            className="text-xs border border-gray-200 rounded px-2 py-1 w-24" />
          <button onClick={handleAdd} disabled={!addingId}
            className="text-xs bg-blue-600 text-white px-2 py-1 rounded disabled:opacity-40">OK</button>
          <button onClick={() => setShowAdd(false)} className="text-xs text-gray-400">×</button>
        </div>
      )}
    </div>
  )
}
