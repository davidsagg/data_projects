import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { contactsApi } from '../api/client'
import { Card } from '../components/Card'

const EMPTY = {
  first_name: '',
  last_name: '',
  company: '',
  position: '',
  email: '',
  city: '',
  linkedin_url: '',
}

export function ContactNewPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)

  function set<K extends keyof typeof EMPTY>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function submit() {
    if (!form.first_name.trim() && !form.last_name.trim()) return
    setSaving(true)
    try {
      const contact = await contactsApi.create({
        ...form,
        company: form.company || undefined,
        position: form.position || undefined,
        email: form.email || undefined,
        city: form.city || undefined,
        linkedin_url: form.linkedin_url || undefined,
      })
      navigate(`/contacts/${contact.id}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-8">
      <Link to="/contacts" className="flex items-center gap-1 text-sm text-muted hover:text-text">
        <ArrowLeft size={14} /> Contatos
      </Link>
      <h1 className="text-2xl font-semibold text-text">Novo contato</h1>

      <Card className="grid grid-cols-2 gap-4">
        <Field label="Nome" value={form.first_name} onChange={(v) => set('first_name', v)} />
        <Field label="Sobrenome" value={form.last_name} onChange={(v) => set('last_name', v)} />
        <Field label="Empresa" value={form.company} onChange={(v) => set('company', v)} />
        <Field label="Cargo" value={form.position} onChange={(v) => set('position', v)} />
        <Field label="Email" value={form.email} onChange={(v) => set('email', v)} />
        <Field label="Cidade" value={form.city} onChange={(v) => set('city', v)} />
        <div className="col-span-2">
          <Field label="URL do LinkedIn" value={form.linkedin_url} onChange={(v) => set('linkedin_url', v)} />
        </div>
      </Card>

      <button
        onClick={submit}
        disabled={saving}
        className="rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
      >
        {saving ? 'Salvando...' : 'Salvar contato'}
      </button>
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted">{label}</label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
      />
    </div>
  )
}
