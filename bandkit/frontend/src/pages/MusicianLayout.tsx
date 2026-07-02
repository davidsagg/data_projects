import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Calendar, momentLocalizer, Views } from 'react-big-calendar'
import moment from 'moment'
import 'moment/locale/pt-br'
import 'react-big-calendar/lib/css/react-big-calendar.css'
import { eventsApi, executionsApi, songsApi } from '../api/client'
import { useAppStore, useMusicianStore } from '../store/appStore'
import { ChordViewer } from '../components/ChordViewer'
import { getKeyName, semitonesBetween } from '../utils/transpose'
import type { BandEvent, MusicalExecution, Song } from '../types'

moment.locale('pt-br')
const localizer = momentLocalizer(moment)

const EVENT_COLORS: Record<string, string> = {
  show: '#3b82f6', rehearsal: '#22c55e', recording: '#f97316', other: '#8b5cf6',
}
const TYPE_LABELS: Record<string, string> = {
  show: 'Show', rehearsal: 'Ensaio', recording: 'Gravação', other: 'Outro',
}

type MainView = 'events' | 'setlist' | 'song'
type EventsView = 'calendar' | 'list'
interface CalEvent { id: number; title: string; start: Date; end: Date; resource: BandEvent }

const SECTION_LINE = /^\[([^\]]+)\]$/
const CHORD_ROOT   = /^[A-G]/
function countSections(bkcp: string) {
  return bkcp.split('\n').filter(l => { const m = SECTION_LINE.exec(l); return m && !CHORD_ROOT.test(m[1] ?? '') }).length
}

export default function MusicianLayout() {
  const navigate = useNavigate()
  const { currentMusician, logout } = useAppStore()
  const { semitones, setSemitones, reset, currentSongId, setCurrentSong } = useMusicianStore()

  const [mainView,    setMainView]    = useState<MainView>('events')
  const [eventsView,  setEventsView]  = useState<EventsView>('list')
  const [myEvents,    setMyEvents]    = useState<BandEvent[]>([])
  const [selectedEvent, setSelectedEvent] = useState<BandEvent | null>(null)
  const [executions,  setExecutions]  = useState<MusicalExecution[]>([])
  const [songs,       setSongs]       = useState<Song[]>([])
  const [darkMode,    setDarkMode]    = useState(true)
  const [sectionIdx,  setSectionIdx]  = useState(0)
  const [syncing,     setSyncing]     = useState(false)
  const [showAll,     setShowAll]     = useState(false)
  const viewerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
    return () => { document.documentElement.classList.remove('dark') }
  }, [darkMode])

  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let wl: any = null
    const req = async () => {
      if ('wakeLock' in navigator)
        try { wl = await (navigator as any).wakeLock.request('screen') } catch {}
    }
    req()
    return () => { wl?.release() }
  }, [])

  useEffect(() => {
    eventsApi.list(currentMusician?.id).then(d => setMyEvents(d as BandEvent[]))
    songsApi.list().then(d => setSongs(d as Song[]))
  }, [currentMusician])

  const songMap = useMemo(() => Object.fromEntries(songs.map(s => [s.id, s])), [songs])
  const currentSong = currentSongId != null ? songMap[currentSongId] : undefined
  const currentExec = executions.find(e => e.song_id === currentSongId)
  const sectionCount = useMemo(() => currentSong?.bkcp_content ? countSections(currentSong.bkcp_content) : 0, [currentSong])

  const myExecutionIds = useMemo(
    () => new Set(executions.filter(e => e.musicians.some(m => m.musician_id === currentMusician?.id)).map(e => e.id)),
    [executions, currentMusician],
  )
  const displayedExecutions = useMemo(
    () => showAll ? executions : executions.filter(e => myExecutionIds.has(e.id)),
    [executions, showAll, myExecutionIds],
  )

  const openEvent = useCallback(async (ev: BandEvent) => {
    setSelectedEvent(ev)
    setShowAll(false)
    const execs = await executionsApi.list(ev.id)
    setExecutions(execs as MusicalExecution[])
    setMainView('setlist')
  }, [])

  const reimportSetlist = useCallback(async () => {
    if (!selectedEvent?.setlist_id) return
    setSyncing(true)
    try {
      const execs = await executionsApi.reimportSetlist(selectedEvent.id)
      setExecutions(execs as MusicalExecution[])
    } catch {
      alert('Erro ao sincronizar com o setlist')
    } finally {
      setSyncing(false)
    }
  }, [selectedEvent])

  const openSong = useCallback((exec: MusicalExecution) => {
    const song = songMap[exec.song_id]
    setCurrentSong(exec.song_id)
    setSectionIdx(0)
    if (exec.key_override && song?.key_original) {
      setSemitones(semitonesBetween(song.key_original, exec.key_override))
    } else {
      reset()
    }
    setMainView('song')
  }, [songMap, setCurrentSong, setSemitones, reset])

  const handleTranspose = useCallback(async (delta: number) => {
    const next = semitones + delta
    setSemitones(next)
    if (currentExec && currentSong?.key_original && selectedEvent) {
      const newKey = getKeyName(currentSong.key_original, next)
      await executionsApi.patch(selectedEvent.id, currentExec.id, { key_override: newKey || null }).catch(() => {})
      setExecutions(es => es.map(e => e.id === currentExec.id ? { ...e, key_override: newKey || null } : e))
    }
  }, [semitones, setSemitones, currentExec, currentSong, selectedEvent])

  const navigateSection = useCallback((dir: 1 | -1) => {
    if (!viewerRef.current) return
    const headers = Array.from(viewerRef.current.querySelectorAll('[data-section-header]'))
    if (!headers.length) return
    setSectionIdx(idx => {
      const next = Math.max(0, Math.min(headers.length - 1, idx + dir))
      headers[next]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      return next
    })
  }, [])

  useEffect(() => {
    if (mainView !== 'song') return
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'ArrowRight') navigateSection(1)
      if (e.key === 'ArrowLeft')  navigateSection(-1)
      if (e.key === '+')          handleTranspose(1)
      if (e.key === '-')          handleTranspose(-1)
      if (e.key === 'r' || e.key === 'R') { reset(); setSemitones(0); setSectionIdx(0) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [mainView, navigateSection, handleTranspose, reset, setSemitones])

  const keyName = getKeyName(currentSong?.key_original ?? '', semitones)
  const bg   = darkMode ? 'bg-gray-900 text-gray-100' : 'bg-gray-50 text-gray-900'
  const side = darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'
  const sorted = [...myEvents].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  const calEvents: CalEvent[] = myEvents.map(e => ({
    id: e.id, title: e.title,
    start: new Date(e.date),
    end: new Date(new Date(e.date).getTime() + (e.duration_min ?? 60) * 60_000),
    resource: e,
  }))

  return (
    <div className={`flex min-h-screen ${bg} transition-colors duration-200`}>

      {/* ── Sidebar ─────────────────────────────── */}
      <aside className={`w-56 border-r flex flex-col shrink-0 ${side}`}>
        <div className="p-4 border-b border-inherit">
          <div className="text-xs font-bold text-blue-400 mb-1">BandKit</div>
          <div className="text-sm font-semibold truncate">{currentMusician?.name}</div>
          <div className="text-xs opacity-50 truncate capitalize">{currentMusician?.role}</div>
        </div>

        <div className="p-2 border-b border-inherit">
          <button onClick={() => setMainView('events')}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${
              mainView === 'events' ? 'bg-blue-600 text-white' : darkMode ? 'hover:bg-gray-700 text-gray-300' : 'hover:bg-gray-100 text-gray-700'
            }`}>
            📅 Meus Eventos
          </button>
        </div>

        {selectedEvent && mainView !== 'events' && (
          <>
            <div className="px-3 py-2 text-xs font-semibold opacity-60 uppercase tracking-wide border-b border-inherit truncate">
              {selectedEvent.title}
            </div>
            <nav className="flex-1 overflow-auto p-2 space-y-0.5">
              {displayedExecutions.length === 0 && (
                <p className="text-xs opacity-40 p-3 text-center">
                  {showAll ? 'Sem músicas' : 'Você não está escalado'}
                </p>
              )}
              {displayedExecutions.map(exec => {
                const song = songMap[exec.song_id]
                const active = currentSongId === exec.song_id && mainView === 'song'
                const key = exec.key_override ?? song?.key_original ?? ''
                const isAssigned = myExecutionIds.has(exec.id)
                return (
                  <button key={exec.id} onClick={() => openSong(exec)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${
                      active ? 'bg-blue-600 text-white' : darkMode ? 'hover:bg-gray-700 text-gray-300' : 'hover:bg-gray-100 text-gray-700'
                    }`}>
                    <div className="flex items-center gap-1">
                      <span className="font-medium truncate">{song?.title ?? `#${exec.song_id}`}</span>
                      {isAssigned && showAll && <span className={`text-xs shrink-0 ${active ? 'text-yellow-300' : 'text-yellow-400'}`}>★</span>}
                    </div>
                    {key && <span className={`text-xs ${active ? 'opacity-80' : 'text-blue-400'}`}>{key}</span>}
                  </button>
                )
              })}
            </nav>
          </>
        )}

        {mainView === 'events' && <div className="flex-1" />}

        <div className="p-3 border-t border-inherit space-y-1">
          <button onClick={() => setDarkMode(d => !d)}
            className="w-full text-left text-xs px-3 py-2 rounded-lg opacity-60 hover:opacity-100 transition">
            {darkMode ? '☀️  Modo Claro' : '🌙  Modo Escuro'}
          </button>
          <button onClick={() => navigate('/admin/calendar')}
            className="w-full text-left text-xs px-3 py-2 rounded-lg opacity-60 hover:opacity-100 transition">← Admin</button>
          <button onClick={() => { logout(); navigate('/') }}
            className="w-full text-left text-xs px-3 py-2 rounded-lg opacity-40 hover:opacity-80 transition">Sair</button>
        </div>
      </aside>

      {/* ── Main ─────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* EVENTS VIEW */}
        {mainView === 'events' && (
          <>
            <div className={`flex items-center justify-between px-6 py-4 border-b shrink-0 ${side}`}>
              <div className="flex items-center gap-3">
                <h1 className="text-lg font-semibold">Meus Eventos</h1>
                <div className="flex bg-gray-100 rounded-lg p-0.5">
                  {(['list', 'calendar'] as EventsView[]).map(v => (
                    <button key={v} onClick={() => setEventsView(v)}
                      className={`px-3 py-1 text-xs rounded-md font-medium transition ${eventsView === v ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}>
                      {v === 'calendar' ? 'Calendário' : 'Lista'}
                    </button>
                  ))}
                </div>
              </div>
              <span className="text-xs opacity-40">{myEvents.length} evento{myEvents.length !== 1 ? 's' : ''}</span>
            </div>

            {eventsView === 'list' && (
              <div className="flex-1 overflow-auto p-6">
                {sorted.length === 0 ? (
                  <div className="flex items-center justify-center h-full opacity-30 flex-col gap-3">
                    <div className="text-4xl">📅</div>
                    <p className="text-sm">Você ainda não está escalado em nenhum evento</p>
                  </div>
                ) : (
                  <div className="max-w-xl space-y-2">
                    {sorted.map(ev => (
                      <div key={ev.id} onClick={() => openEvent(ev)}
                        className={`rounded-xl border flex items-center gap-4 px-5 py-4 cursor-pointer transition hover:shadow-sm ${darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
                        <div className="shrink-0 w-12 text-center">
                          <div className="text-xs opacity-50 uppercase">{new Date(ev.date).toLocaleDateString('pt-BR', { month: 'short' })}</div>
                          <div className="text-2xl font-bold leading-none">{new Date(ev.date).getDate()}</div>
                        </div>
                        <div className="w-1 self-stretch rounded-full shrink-0" style={{ backgroundColor: EVENT_COLORS[ev.event_type] ?? '#6b7280' }} />
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold truncate">{ev.title}</div>
                          <div className="text-xs opacity-50 mt-0.5">
                            {new Date(ev.date).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                            {ev.venue && ` · ${ev.venue}`}
                          </div>
                          {ev.setlist && <div className="text-xs text-blue-400 mt-0.5">📋 {ev.setlist.name}</div>}
                        </div>
                        <span className="text-xs opacity-60 shrink-0">{TYPE_LABELS[ev.event_type]}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {eventsView === 'calendar' && (
              <div className="flex-1 p-4 overflow-hidden">
                {myEvents.length === 0 ? (
                  <div className="flex items-center justify-center h-full opacity-30 flex-col gap-3">
                    <div className="text-4xl">📅</div>
                    <p className="text-sm">Você ainda não está escalado em nenhum evento</p>
                  </div>
                ) : (
                  <Calendar localizer={localizer} events={calEvents}
                    defaultView={Views.MONTH} views={[Views.MONTH, Views.WEEK]}
                    onSelectEvent={(e: CalEvent) => openEvent(e.resource)}
                    eventPropGetter={(e: CalEvent) => ({ style: { backgroundColor: EVENT_COLORS[e.resource.event_type] ?? '#6b7280', border: 'none' } })}
                    style={{ height: '100%' }}
                    messages={{ month: 'Mês', week: 'Semana', today: 'Hoje', next: '›', previous: '‹', noEventsInRange: 'Nenhum evento.' }} />
                )}
              </div>
            )}
          </>
        )}

        {/* SETLIST VIEW */}
        {mainView === 'setlist' && (
          <>
            <div className={`border-b shrink-0 ${side}`}>
              {/* Linha 1: voltar + título + sincronizar */}
              <div className="flex items-center gap-3 px-6 pt-4 pb-3">
                <button onClick={() => setMainView('events')} className="text-sm opacity-60 hover:opacity-100">←</button>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold truncate">{selectedEvent?.title}</div>
                  <div className="text-xs opacity-50">
                    {selectedEvent && new Date(selectedEvent.date).toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' })}
                    {selectedEvent?.setlist && ` · 📋 ${selectedEvent.setlist.name}`}
                  </div>
                </div>
                {selectedEvent?.setlist_id && (
                  <button
                    onClick={reimportSetlist}
                    disabled={syncing}
                    title="Reimportar setlist do admin"
                    className={`shrink-0 text-xs px-3 py-1.5 rounded-lg border transition disabled:opacity-40 ${
                      darkMode
                        ? 'border-gray-600 text-gray-400 hover:text-blue-400 hover:border-blue-500'
                        : 'border-gray-300 text-gray-500 hover:text-blue-600 hover:border-blue-400'
                    }`}
                  >
                    {syncing ? '…' : '↻ Sincronizar'}
                  </button>
                )}
              </div>
              {/* Linha 2: toggle de visão */}
              <div className="px-6 pb-3">
                <div className={`inline-flex rounded-lg p-0.5 text-xs ${darkMode ? 'bg-gray-700' : 'bg-gray-100'}`}>
                  <button
                    onClick={() => setShowAll(false)}
                    className={`px-3 py-1 rounded-md transition font-medium ${
                      !showAll
                        ? 'bg-blue-600 text-white shadow'
                        : darkMode ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    Minhas músicas
                  </button>
                  <button
                    onClick={() => setShowAll(true)}
                    className={`px-3 py-1 rounded-md transition font-medium ${
                      showAll
                        ? 'bg-blue-600 text-white shadow'
                        : darkMode ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    Setlist completo
                  </button>
                </div>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-6">
              {displayedExecutions.length === 0 ? (
                <div className="flex items-center justify-center h-full opacity-30 flex-col gap-3">
                  <div className="text-4xl">🎵</div>
                  <p className="text-sm">
                    {showAll
                      ? 'Nenhuma música neste evento'
                      : 'Você não está escalado em nenhuma música deste evento'}
                  </p>
                </div>
              ) : (
                <div className="max-w-xl space-y-2">
                  {displayedExecutions.map(exec => {
                    const song = songMap[exec.song_id]
                    const key = exec.key_override ?? song?.key_original ?? ''
                    const isAssigned = myExecutionIds.has(exec.id)
                    return (
                      <div key={exec.id} onClick={() => openSong(exec)}
                        className={`rounded-xl border flex items-center gap-4 px-5 py-4 cursor-pointer transition hover:shadow-sm ${
                          darkMode
                            ? `bg-gray-800 border-gray-700 ${isAssigned && showAll ? 'border-l-2 border-l-blue-500' : ''}`
                            : `bg-white border-gray-200 ${isAssigned && showAll ? 'border-l-2 border-l-blue-500' : ''}`
                        }`}>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold truncate">{song?.title ?? `#${exec.song_id}`}</span>
                            {isAssigned && showAll && (
                              <span className="text-yellow-400 text-xs shrink-0">★</span>
                            )}
                          </div>
                          {song?.artist && <div className="text-xs opacity-50 truncate">{song.artist}</div>}
                          {isAssigned && exec.musicians.length > 0 && (
                            <div className="text-xs text-green-400 mt-0.5 truncate">
                              {exec.musicians.map(m => m.instrument_override ?? '').filter(Boolean).join(', ')}
                            </div>
                          )}
                        </div>
                        <div className="shrink-0 text-right">
                          <div className={`text-lg font-bold ${darkMode ? 'text-blue-400' : 'text-blue-600'}`}>{key}</div>
                          {exec.key_override && song?.key_original && exec.key_override !== song.key_original && (
                            <div className="text-xs opacity-40">orig. {song.key_original}</div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </>
        )}

        {/* SONG VIEW */}
        {mainView === 'song' && (
          <>
            <div className={`flex items-center justify-between px-5 py-3 border-b shrink-0 ${side}`}>
              <div className="flex items-center gap-2">
                <button onClick={() => setMainView('setlist')} className="text-sm opacity-60 hover:opacity-100 mr-1">←</button>
                <button onClick={() => navigateSection(-1)} disabled={sectionIdx === 0} className="px-2 py-1 text-sm rounded hover:opacity-70 disabled:opacity-20" aria-label="←">◀</button>
                <button onClick={() => navigateSection(1)}  disabled={sectionCount === 0} className="px-2 py-1 text-sm rounded hover:opacity-70 disabled:opacity-20" aria-label="→">▶</button>
                {currentSong && <span className="text-sm font-semibold truncate opacity-80 ml-1 hidden sm:block">{currentSong.title}</span>}
              </div>
              <div className="text-xs opacity-30 hidden sm:block">← → + − R</div>
            </div>

            <div ref={viewerRef} className="flex-1 overflow-auto px-8 py-6">
              {currentSong?.bkcp_content
                ? <ChordViewer bkcp={currentSong.bkcp_content} semitones={semitones} darkMode={darkMode} />
                : <div className="flex items-center justify-center h-full opacity-30 text-sm">Cifra não disponível</div>
              }
            </div>

            {currentSong && (
              <div className={`shrink-0 border-t ${side} px-6 py-3 flex items-center gap-4`}>
                <div className="flex items-center gap-2">
                  <button onClick={() => handleTranspose(-1)} aria-label="−"
                    className={`w-10 h-10 rounded-full text-xl font-bold flex items-center justify-center transition ${darkMode ? 'bg-gray-700 hover:bg-gray-600 text-white' : 'bg-gray-200 hover:bg-gray-300'}`}>−</button>
                  <div className="text-center min-w-[5rem]">
                    {/* Tom atual em destaque */}
                    <div className={`text-xl font-bold ${darkMode ? 'text-blue-400' : 'text-blue-600'}`}>
                      {keyName || '—'}
                    </div>
                    {/* Info secundária: original quando sem transposição, offset quando transposto */}
                    <div className="text-xs opacity-50">
                      {semitones === 0
                        ? (currentSong?.key_original || 'sem tom')
                        : `${semitones > 0 ? '+' : ''}${semitones} st`}
                    </div>
                  </div>
                  <button onClick={() => handleTranspose(1)} aria-label="+"
                    className={`w-10 h-10 rounded-full text-xl font-bold flex items-center justify-center transition ${darkMode ? 'bg-gray-700 hover:bg-gray-600 text-white' : 'bg-gray-200 hover:bg-gray-300'}`}>+</button>
                  {semitones !== 0 && (
                    <button onClick={() => { reset(); setSemitones(0) }} className="text-xs opacity-50 hover:opacity-100 underline ml-1">reset</button>
                  )}
                </div>
                {sectionCount > 0 && (
                  <div className="flex-1 flex items-center gap-3">
                    <span className="text-xs opacity-50 shrink-0">{Math.min(sectionIdx + 1, sectionCount)}/{sectionCount}</span>
                    <div className={`flex-1 h-1.5 rounded-full ${darkMode ? 'bg-gray-700' : 'bg-gray-200'}`}>
                      <div className="h-1.5 rounded-full bg-blue-500 transition-all duration-300"
                        style={{ width: `${((sectionIdx + 1) / sectionCount) * 100}%` }} />
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
