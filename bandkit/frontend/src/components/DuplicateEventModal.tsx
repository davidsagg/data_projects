import { useEffect, useState } from 'react'
import { eventsApi, setlistsApi } from '../api/client'
import type { BandEvent, SetlistBrief } from '../types'

interface Props {
  event: BandEvent
  onClose: () => void
  onDuplicated: (newEvent: BandEvent) => void
}

export default function DuplicateEventModal({ event, onClose, onDuplicated }: Props) {
  const toLocal = (d: string) => {
    const dt = new Date(d)
    return new Date(dt.getTime() - dt.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
  }

  const nextWeek = () => {
    const d = new Date(event.date)
    d.setDate(d.getDate() + 7)
    return toLocal(d.toISOString())
  }

  const [title, setTitle] = useState(event.title + ' (cópia)')
  const [date, setDate] = useState(nextWeek())
  const [setlistOption, setSetlistOption] = useState<'same' | 'none' | 'other'>('same')
  const [otherSetlistId, setOtherSetlistId] = useState<string>('')
  const [copyMusicians, setCopyMusicians] = useState(true)
  const [setlists, setSetlists] = useState<SetlistBrief[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => { setlistsApi.list().then(setSetlists) }, [])

  const resolvedSetlistId = (): number | null => {
    if (setlistOption === 'none') return null
    if (setlistOption === 'same') return event.setlist_id
    return otherSetlistId ? Number(otherSetlistId) : null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !date) return
    setSaving(true)
    try {
      const newEvent = await eventsApi.duplicate(event.id, {
        title: title.trim(),
        date: new Date(date).toISOString(),
        setlist_id: resolvedSetlistId(),
        copy_musicians: copyMusicians,
      })
      onDuplicated(newEvent as BandEvent)
    } catch {
      alert('Erro ao duplicar evento')
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Duplicar Evento</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Título */}
          <div>
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-1">Título</label>
            <input type="text" value={title} onChange={e => setTitle(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
          </div>

          {/* Data */}
          <div>
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-1">Nova data *</label>
            <input type="datetime-local" value={date} onChange={e => setDate(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
            <p className="text-xs text-gray-400 mt-1">Original: {new Date(event.date).toLocaleString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</p>
          </div>

          {/* Setlist */}
          <div>
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-1">Setlist</label>
            <div className="flex flex-col gap-1.5">
              {event.setlist_id && (
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="radio" name="sl" checked={setlistOption === 'same'} onChange={() => setSetlistOption('same')} />
                  <span>Mesmo setlist <span className="text-gray-400">({event.setlist?.name})</span></span>
                </label>
              )}
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="radio" name="sl" checked={setlistOption === 'other'} onChange={() => setSetlistOption('other')} />
                <span>Setlist diferente</span>
              </label>
              {setlistOption === 'other' && (
                <select value={otherSetlistId} onChange={e => setOtherSetlistId(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm ml-5">
                  <option value="">— Selecionar —</option>
                  {setlists.map(sl => <option key={sl.id} value={sl.id}>{sl.name}</option>)}
                </select>
              )}
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="radio" name="sl" checked={setlistOption === 'none'} onChange={() => setSetlistOption('none')} />
                <span>Sem setlist</span>
              </label>
            </div>
          </div>

          {/* Copiar músicos */}
          <label className="flex items-center gap-3 cursor-pointer p-3 border border-gray-200 rounded-lg hover:bg-gray-50">
            <input type="checkbox" checked={copyMusicians} onChange={e => setCopyMusicians(e.target.checked)}
              className="w-4 h-4 text-blue-600" />
            <div>
              <div className="text-sm font-medium text-gray-900">Copiar músicos e tonalidades</div>
              <div className="text-xs text-gray-400">Reaplica os músicos e os tons de cada execução do evento original</div>
            </div>
          </label>

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancelar</button>
            <button type="submit" disabled={saving || !title.trim() || !date}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
              {saving ? 'Duplicando…' : '⊕ Duplicar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
