import { useEffect, useState } from 'react'
import { musiciansApi } from '../../api/client'
import type { Musician } from '../../types'

const ROLE_STYLE: Record<string, string> = {
  admin: 'bg-purple-100 text-purple-700',
  musician: 'bg-green-100 text-green-700',
}

const INSTRUMENTS = [
  'Guitarra', 'Violão', 'Baixo', 'Bateria', 'Teclado', 'Piano',
  'Violino', 'Saxofone', 'Trompete', 'Percussão', 'Vocal', 'Outro',
]

interface FormState {
  name: string
  instrument: string
  role: 'admin' | 'musician'
  email: string
}

const emptyForm = (): FormState => ({ name: '', instrument: '', role: 'musician', email: '' })

export default function MusiciansPage() {
  const [musicians, setMusicians] = useState<Musician[]>([])
  const [form, setForm] = useState<FormState>(emptyForm())
  const [editingId, setEditingId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    musiciansApi.list().then((data) => setMusicians(data as Musician[]))
  }, [])

  const set = (field: keyof FormState, value: string) =>
    setForm((f) => ({ ...f, [field]: value }))

  const openCreate = () => {
    setForm(emptyForm())
    setEditingId(null)
    setShowForm(true)
  }

  const openEdit = (m: Musician) => {
    setForm({
      name: m.name,
      instrument: m.instrument ?? '',
      role: m.role as 'admin' | 'musician',
      email: m.email ?? '',
    })
    setEditingId(m.id)
    setShowForm(true)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) return
    setSaving(true)
    const payload = {
      name: form.name.trim(),
      instrument: form.instrument.trim() || null,
      role: form.role,
      email: form.email.trim() || null,
    }
    try {
      if (editingId) {
        const updated = await musiciansApi.update(editingId, payload)
        setMusicians((ms) => ms.map((m) => (m.id === editingId ? (updated as Musician) : m)))
      } else {
        const created = await musiciansApi.create(payload)
        setMusicians((ms) => [...ms, created as Musician])
      }
      setShowForm(false)
      setForm(emptyForm())
      setEditingId(null)
    } catch {
      alert('Erro ao salvar músico')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (m: Musician) => {
    if (!confirm(`Remover "${m.name}"?`)) return
    try {
      await musiciansApi.delete(m.id)
      setMusicians((ms) => ms.filter((x) => x.id !== m.id))
    } catch {
      alert('Erro ao remover músico')
    }
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200 shrink-0">
        <h1 className="text-xl font-semibold text-gray-900">Músicos</h1>
        <button
          onClick={openCreate}
          className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700"
        >
          + Novo músico
        </button>
      </div>

      {/* Lista */}
      <div className="flex-1 overflow-auto p-6">
        {musicians.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <div className="text-4xl mb-3">👥</div>
            <p className="text-sm">Nenhum músico cadastrado ainda.</p>
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm overflow-hidden max-w-3xl">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Nome</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Instrumento</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Perfil</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Email</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {musicians.map((m) => (
                  <tr key={m.id} className="hover:bg-gray-50 transition">
                    <td className="px-4 py-3 font-medium text-gray-900">{m.name}</td>
                    <td className="px-4 py-3 text-gray-500">{m.instrument ?? '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_STYLE[m.role] ?? 'bg-gray-100 text-gray-600'}`}>
                        {m.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{m.email ?? '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => openEdit(m)} className="text-xs text-blue-600 hover:underline mr-3">Editar</button>
                      <button onClick={() => handleDelete(m)} className="text-xs text-red-500 hover:underline">Remover</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal de criação/edição */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h2 className="text-base font-semibold text-gray-900">
                {editingId ? 'Editar músico' : 'Novo músico'}
              </h2>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-gray-600 text-xl">×</button>
            </div>
            <form onSubmit={handleSave} className="p-6 space-y-3">
              <input
                autoFocus type="text" placeholder="Nome *" value={form.name}
                onChange={(e) => set('name', e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
              <div className="flex gap-2">
                <select
                  value={form.instrument}
                  onChange={(e) => set('instrument', e.target.value)}
                  className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  <option value="">Instrumento…</option>
                  {INSTRUMENTS.map((i) => <option key={i} value={i}>{i}</option>)}
                </select>
                <select
                  value={form.role}
                  onChange={(e) => set('role', e.target.value as 'admin' | 'musician')}
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  <option value="musician">Músico</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <input
                type="email" placeholder="Email (opcional)" value={form.email}
                onChange={(e) => set('email', e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
              <div className="flex justify-end gap-2 pt-1">
                <button type="button" onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">
                  Cancelar
                </button>
                <button type="submit" disabled={saving || !form.name.trim()}
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                  {saving ? 'Salvando…' : 'Salvar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
