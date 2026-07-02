import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { musiciansApi } from '../api/client'
import { useAppStore } from '../store/appStore'
import type { Musician } from '../types'

export default function ProfileSelector() {
  const [musicians, setMusicians] = useState<Musician[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', instrument: '', role: 'musician' as 'admin' | 'musician' })
  const [saving, setSaving] = useState(false)
  const { setMode, setMusician } = useAppStore()
  const navigate = useNavigate()

  useEffect(() => {
    musiciansApi.list().then(setMusicians).finally(() => setLoading(false))
  }, [])

  const handleSelect = (m: Musician) => {
    setMusician({ id: m.id, name: m.name, role: m.role })
    setMode(m.role === 'admin' ? 'admin' : 'musician')
    navigate(m.role === 'admin' ? '/admin/calendar' : '/musician')
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) return
    setSaving(true)
    try {
      const m = await musiciansApi.create({
        name: form.name.trim(),
        instrument: form.instrument.trim() || undefined,
        role: form.role,
      })
      const created = m as Musician
      setMusicians((ms) => [...ms, created])
      setForm({ name: '', instrument: '', role: 'musician' })
      setShowForm(false)
      handleSelect(created)
    } catch {
      alert('Erro ao criar músico')
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen text-gray-500">
        Carregando…
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-8">
      <h1 className="text-4xl font-bold text-gray-900 mb-2">BandKit</h1>
      <p className="text-gray-500 mb-10">Quem é você?</p>

      {/* Lista de músicos existentes */}
      {musicians.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-2xl w-full mb-6">
          {musicians.map((m) => (
            <button
              key={m.id}
              onClick={() => handleSelect(m)}
              className="bg-white rounded-xl shadow p-6 text-left hover:shadow-md hover:ring-2 hover:ring-blue-400 transition"
            >
              <div className="text-lg font-semibold text-gray-900">{m.name}</div>
              {m.instrument && <div className="text-sm text-gray-500">{m.instrument}</div>}
              <div className="mt-3">
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                  m.role === 'admin'
                    ? 'bg-purple-100 text-purple-700'
                    : 'bg-green-100 text-green-700'
                }`}>
                  {m.role}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Formulário de criação */}
      {showForm ? (
        <form
          onSubmit={handleCreate}
          className="bg-white rounded-2xl shadow p-6 w-full max-w-sm space-y-3"
        >
          <h2 className="text-base font-semibold text-gray-800 mb-1">Novo músico</h2>

          <input
            autoFocus
            type="text"
            placeholder="Nome *"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />

          <input
            type="text"
            placeholder="Instrumento (opcional)"
            value={form.instrument}
            onChange={(e) => setForm((f) => ({ ...f, instrument: e.target.value }))}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />

          <select
            value={form.role}
            onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as 'admin' | 'musician' }))}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          >
            <option value="musician">Músico</option>
            <option value="admin">Admin</option>
          </select>

          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="flex-1 border border-gray-200 text-gray-600 text-sm px-4 py-2 rounded-lg hover:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving || !form.name.trim()}
              className="flex-1 bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Criando…' : 'Criar e entrar'}
            </button>
          </div>
        </form>
      ) : (
        <button
          onClick={() => setShowForm(true)}
          className={`text-sm ${musicians.length === 0 ? 'bg-blue-600 text-white px-6 py-3 rounded-xl hover:bg-blue-700 font-medium' : 'text-blue-600 hover:underline'}`}
        >
          {musicians.length === 0 ? 'Criar primeiro usuário' : '+ Adicionar músico'}
        </button>
      )}
    </div>
  )
}
