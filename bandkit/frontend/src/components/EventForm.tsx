import { useEffect, useState } from 'react'
import { eventsApi, setlistsApi } from '../api/client'
import type { BandEvent, SetlistBrief } from '../types'

interface Props {
  onClose: () => void
  onCreated: (event: BandEvent) => void
  initialDate?: Date
}

export default function EventForm({ onClose, onCreated, initialDate }: Props) {
  const toLocal = (d?: Date) =>
    d ? new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16) : ''

  const [form, setForm] = useState({
    title: '', date: toLocal(initialDate), event_type: 'show', status: 'tentative', venue: '', notes: '',
    setlist_id: '' as string | number,
  })
  const [setlists, setSetlists] = useState<SetlistBrief[]>([])
  const [newSetlistName, setNewSetlistName] = useState('')
  const [createSetlist, setCreateSetlist] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { setlistsApi.list().then(setSetlists) }, [])

  const set = (field: string, value: string) => setForm(f => ({ ...f, [field]: value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.title.trim() || !form.date) { setError('Título e data são obrigatórios'); return }
    setSaving(true)
    try {
      let setlist_id: number | null = null

      if (createSetlist && newSetlistName.trim()) {
        const sl = await setlistsApi.create({ name: newSetlistName.trim() }) as SetlistBrief
        setlist_id = sl.id
      } else if (form.setlist_id) {
        setlist_id = Number(form.setlist_id)
      }

      const event = await eventsApi.create({
        title: form.title.trim(),
        date: new Date(form.date).toISOString(),
        event_type: form.event_type,
        status: form.status,
        venue: form.venue || null,
        notes: form.notes || null,
        setlist_id,
      })
      onCreated(event as BandEvent)
    } catch {
      setError('Erro ao criar evento')
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Novo Evento</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-3">
          {error && <p className="text-red-500 text-sm">{error}</p>}

          <input type="text" placeholder="Título *" value={form.title}
            onChange={e => set('title', e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />

          <input type="datetime-local" value={form.date}
            onChange={e => set('date', e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />

          <div className="grid grid-cols-2 gap-3">
            <select value={form.event_type} onChange={e => set('event_type', e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
              <option value="show">Show</option>
              <option value="rehearsal">Ensaio</option>
              <option value="recording">Gravação</option>
              <option value="other">Outro</option>
            </select>
            <select value={form.status} onChange={e => set('status', e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
              <option value="confirmed">Confirmado</option>
              <option value="tentative">Provável</option>
              <option value="cancelled">Cancelado</option>
            </select>
          </div>

          <input type="text" placeholder="Local" value={form.venue}
            onChange={e => set('venue', e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />

          {/* Setlist */}
          <div className="border border-gray-200 rounded-lg p-3 space-y-2">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Setlist</div>
            <div className="flex gap-2">
              <button type="button" onClick={() => setCreateSetlist(false)}
                className={`text-xs px-3 py-1 rounded-full border transition ${!createSetlist ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-200 text-gray-500 hover:border-blue-400'}`}>
                Existente
              </button>
              <button type="button" onClick={() => setCreateSetlist(true)}
                className={`text-xs px-3 py-1 rounded-full border transition ${createSetlist ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-200 text-gray-500 hover:border-blue-400'}`}>
                Criar novo
              </button>
            </div>
            {!createSetlist ? (
              <select value={form.setlist_id} onChange={e => set('setlist_id', e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                <option value="">— Nenhum —</option>
                {setlists.map(sl => <option key={sl.id} value={sl.id}>{sl.name}</option>)}
              </select>
            ) : (
              <input type="text" placeholder="Nome do novo setlist"
                value={newSetlistName} onChange={e => setNewSetlistName(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
            )}
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancelar</button>
            <button type="submit" disabled={saving}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
              {saving ? 'Criando…' : 'Criar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
