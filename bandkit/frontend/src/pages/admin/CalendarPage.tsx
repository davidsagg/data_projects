import { useCallback, useEffect, useState } from 'react'
import { Calendar, momentLocalizer, Views } from 'react-big-calendar'
import moment from 'moment'
import 'moment/locale/pt-br'
import 'react-big-calendar/lib/css/react-big-calendar.css'
import { eventsApi } from '../../api/client'
import type { BandEvent } from '../../types'
import EventForm from '../../components/EventForm'
import EventDetail from '../../components/EventDetail'
import DuplicateEventModal from '../../components/DuplicateEventModal'

moment.locale('pt-br')
const localizer = momentLocalizer(moment)

const EVENT_COLORS: Record<string, string> = {
  show: '#3b82f6',
  rehearsal: '#22c55e',
  recording: '#f97316',
  other: '#8b5cf6',
}

const TYPE_LABELS: Record<string, string> = {
  show: 'Show', rehearsal: 'Ensaio', recording: 'Gravação', other: 'Outro',
}

const STATUS_STYLE: Record<string, string> = {
  confirmed: 'bg-green-100 text-green-700',
  tentative: 'bg-yellow-100 text-yellow-700',
  cancelled: 'bg-red-100 text-red-500 line-through',
}

interface CalEvent {
  id: number; title: string; start: Date; end: Date; resource: BandEvent
}

type ViewMode = 'calendar' | 'list'

export default function CalendarPage() {
  const [events, setEvents]     = useState<BandEvent[]>([])
  const [showForm, setShowForm] = useState(false)
  const [slotDate, setSlotDate] = useState<Date | undefined>()
  const [detail, setDetail]     = useState<BandEvent | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('calendar')
  const [duplicating, setDuplicating] = useState<BandEvent | null>(null)

  const load = useCallback(() => {
    eventsApi.list().then((data) => setEvents(data as BandEvent[]))
  }, [])
  useEffect(() => { load() }, [load])

  const sorted = [...events].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

  const calEvents: CalEvent[] = events.map((e) => ({
    id: e.id, title: e.title,
    start: new Date(e.date),
    end: new Date(new Date(e.date).getTime() + (e.duration_min ?? 60) * 60_000),
    resource: e,
  }))

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900">Calendário</h1>
          {/* Toggle */}
          <div className="flex bg-gray-100 rounded-lg p-0.5">
            {(['calendar', 'list'] as ViewMode[]).map((v) => (
              <button key={v} onClick={() => setViewMode(v)}
                className={`px-3 py-1 text-xs rounded-md font-medium transition ${
                  viewMode === v ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'
                }`}>
                {v === 'calendar' ? 'Calendário' : 'Lista'}
              </button>
            ))}
          </div>
        </div>
        <button onClick={() => { setSlotDate(undefined); setShowForm(true) }}
          className="bg-blue-600 text-white px-4 py-2 text-sm rounded-lg hover:bg-blue-700">
          + Novo Evento
        </button>
      </div>

      {/* Calendar view */}
      {viewMode === 'calendar' && (
        <div className="flex-1 p-4 overflow-hidden">
          <Calendar
            localizer={localizer} events={calEvents}
            defaultView={Views.MONTH} views={[Views.MONTH, Views.WEEK]}
            selectable
            onSelectSlot={({ start }) => { setSlotDate(start instanceof Date ? start : new Date(start)); setShowForm(true) }}
            onSelectEvent={(e: CalEvent) => setDetail(e.resource)}
            eventPropGetter={(e: CalEvent) => ({ style: { backgroundColor: EVENT_COLORS[e.resource.event_type] ?? '#6b7280', border: 'none' } })}
            style={{ height: '100%' }}
            messages={{ month: 'Mês', week: 'Semana', day: 'Dia', today: 'Hoje', next: '›', previous: '‹', noEventsInRange: 'Nenhum evento.' }}
          />
        </div>
      )}

      {/* List view */}
      {viewMode === 'list' && (
        <div className="flex-1 overflow-auto p-6">
          {sorted.length === 0 ? (
            <p className="text-center text-gray-400 py-12">Nenhum evento criado ainda.</p>
          ) : (
            <div className="max-w-3xl space-y-2">
              {sorted.map((ev) => (
                <div key={ev.id} onClick={() => setDetail(ev)}
                  className="bg-white rounded-xl border border-gray-200 px-5 py-4 flex items-center gap-4 hover:shadow-sm cursor-pointer transition">
                  {/* Data */}
                  <div className="shrink-0 w-14 text-center">
                    <div className="text-xs text-gray-400 uppercase">
                      {new Date(ev.date).toLocaleDateString('pt-BR', { month: 'short' })}
                    </div>
                    <div className="text-2xl font-bold text-gray-800 leading-none">
                      {new Date(ev.date).getDate()}
                    </div>
                  </div>
                  {/* Barra colorida */}
                  <div className="w-1 self-stretch rounded-full shrink-0"
                    style={{ backgroundColor: EVENT_COLORS[ev.event_type] ?? '#6b7280' }} />
                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-gray-900 truncate">{ev.title}</div>
                    <div className="text-xs text-gray-500 mt-0.5 flex items-center gap-2">
                      <span>{new Date(ev.date).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span>
                      {ev.venue && <span>· {ev.venue}</span>}
                    </div>
                  </div>
                  {/* Badges + ações */}
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                      {TYPE_LABELS[ev.event_type] ?? ev.event_type}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_STYLE[ev.status] ?? 'bg-gray-100 text-gray-600'}`}>
                      {ev.status === 'confirmed' ? 'Confirmado' : ev.status === 'cancelled' ? 'Cancelado' : 'Provável'}
                    </span>
                    <button
                      onClick={e => { e.stopPropagation(); setDuplicating(ev) }}
                      className="text-xs text-gray-400 hover:text-blue-600 border border-gray-200 hover:border-blue-400 px-2 py-0.5 rounded transition"
                      title="Duplicar evento"
                    >
                      ⊕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {showForm && (
        <EventForm initialDate={slotDate}
          onClose={() => { setShowForm(false); setSlotDate(undefined) }}
          onCreated={(ev) => { setEvents((es) => [...es, ev]); setShowForm(false) }} />
      )}

      {detail && <EventDetail event={detail} onClose={() => setDetail(null)} onUpdated={load} />}

      {duplicating && (
        <DuplicateEventModal
          event={duplicating}
          onClose={() => setDuplicating(null)}
          onDuplicated={(newEv) => {
            setEvents(es => [...es, newEv])
            setDuplicating(null)
          }}
        />
      )}
    </div>
  )
}
