import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { ArrowLeft, ExternalLink, MapPinned, Plus, Trash2, Check } from 'lucide-react'
import { contactsApi, geocodeApi, groupsApi, interactionsApi, remindersApi } from '../api/client'
import type { ContactDetail, Group, InteractionType } from '../types'
import { Avatar } from '../components/Avatar'
import { Card } from '../components/Card'
import { EditableField } from '../components/EditableField'
import { GroupChip } from '../components/GroupChip'
import { formatDateOnly } from '../lib/date'

const INTERACTION_LABELS: Record<InteractionType, string> = {
  note: 'Nota',
  call: 'Ligação',
  meeting: 'Reunião',
  email: 'Email',
  coffee: 'Café',
  other: 'Outro',
}

export function ContactDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const contactId = Number(id)
  const [contact, setContact] = useState<ContactDetail | null>(null)
  const [allGroups, setAllGroups] = useState<Group[]>([])
  const [addGroupId, setAddGroupId] = useState('')
  const [noteType, setNoteType] = useState<InteractionType>('note')
  const [noteContent, setNoteContent] = useState('')
  const [reminderDate, setReminderDate] = useState('')
  const [reminderNote, setReminderNote] = useState('')
  const [geocoding, setGeocoding] = useState(false)

  const load = useCallback(() => {
    contactsApi.get(contactId).then(setContact)
  }, [contactId])

  useEffect(() => {
    load()
    groupsApi.list().then(setAllGroups)
  }, [load])

  if (!contact) {
    return <div className="p-8 text-muted">Carregando...</div>
  }

  async function updateField(field: string, value: string) {
    await contactsApi.update(contactId, { [field]: value || null })
    load()
  }

  async function addGroup() {
    if (!addGroupId) return
    await groupsApi.assign(contactId, Number(addGroupId))
    setAddGroupId('')
    load()
  }

  async function removeGroup(groupId: number) {
    await groupsApi.unassign(contactId, groupId)
    load()
  }

  async function suggestCity() {
    if (!contact?.company) return
    setGeocoding(true)
    try {
      const result = await geocodeApi.company(contact.company)
      if (result.found) {
        await contactsApi.update(contactId, {
          city: result.city ?? undefined,
          country: result.country ?? undefined,
          latitude: result.latitude ?? undefined,
          longitude: result.longitude ?? undefined,
        })
        load()
      }
    } finally {
      setGeocoding(false)
    }
  }

  async function addInteraction() {
    if (!noteContent.trim()) return
    await interactionsApi.create(contactId, { type: noteType, content: noteContent })
    setNoteContent('')
    load()
  }

  async function removeInteraction(interactionId: number) {
    await interactionsApi.remove(interactionId)
    load()
  }

  async function addReminder() {
    if (!reminderDate) return
    await remindersApi.create(contactId, { due_date: reminderDate, note: reminderNote || undefined })
    setReminderDate('')
    setReminderNote('')
    load()
  }

  async function toggleReminder(reminderId: number, isDone: boolean) {
    await remindersApi.update(reminderId, { is_done: !isDone })
    load()
  }

  async function removeReminder(reminderId: number) {
    await remindersApi.remove(reminderId)
    load()
  }

  async function deleteContact() {
    if (!contact) return
    if (!confirm(`Remover ${contact.first_name} ${contact.last_name} do CRM?`)) return
    await contactsApi.remove(contactId)
    navigate('/contacts')
  }

  const availableGroups = allGroups.filter((g) => !contact.groups.some((cg) => cg.id === g.id))

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-8">
      <Link to="/contacts" className="flex items-center gap-1 text-sm text-muted hover:text-text">
        <ArrowLeft size={14} /> Contatos
      </Link>

      <div className="flex items-center gap-4">
        <Avatar firstName={contact.first_name} lastName={contact.last_name} size={64} />
        <div className="flex-1">
          <h1 className="text-2xl font-semibold text-text">
            {contact.first_name} {contact.last_name}
          </h1>
          <p className="text-sm text-muted">
            {contact.position || 'Sem cargo'} {contact.company && `· ${contact.company}`}
          </p>
        </div>
        {contact.linkedin_url && (
          <a
            href={contact.linkedin_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 rounded-lg border border-border px-3 py-2 text-sm text-text hover:bg-accent-soft/50"
          >
            LinkedIn <ExternalLink size={14} />
          </a>
        )}
        <button
          onClick={deleteContact}
          className="rounded-lg border border-border p-2 text-muted hover:border-red-300 hover:text-red-500"
          aria-label="Remover contato"
        >
          <Trash2 size={16} />
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {contact.groups.map((g) => (
          <GroupChip key={g.id} group={g} onRemove={() => removeGroup(g.id)} />
        ))}
        {availableGroups.length > 0 && (
          <select
            value={addGroupId}
            onChange={(e) => {
              setAddGroupId(e.target.value)
              if (e.target.value) addGroup()
            }}
            className="rounded-full border border-dashed border-border bg-transparent px-2 py-1 text-xs text-muted"
          >
            <option value="">+ grupo</option>
            {availableGroups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        )}
      </div>

      <Card className="grid grid-cols-2 gap-4">
        <EditableField label="Nome" value={contact.first_name} onSave={(v) => updateField('first_name', v)} />
        <EditableField label="Sobrenome" value={contact.last_name} onSave={(v) => updateField('last_name', v)} />
        <EditableField label="Empresa" value={contact.company || ''} onSave={(v) => updateField('company', v)} />
        <EditableField label="Cargo" value={contact.position || ''} onSave={(v) => updateField('position', v)} />
        <EditableField label="Email" value={contact.email || ''} onSave={(v) => updateField('email', v)} />
        <div>
          <div className="mb-1 flex items-center justify-between">
            <label className="block text-xs font-medium uppercase tracking-wide text-muted">Cidade</label>
            {contact.company && !contact.city && (
              <button
                onClick={suggestCity}
                disabled={geocoding}
                className="flex items-center gap-1 text-xs font-medium text-accent hover:underline disabled:opacity-50"
              >
                <MapPinned size={12} /> {geocoding ? 'Buscando...' : 'Sugerir'}
              </button>
            )}
          </div>
          <EditableField label="" value={contact.city || ''} placeholder="Não informado" onSave={(v) => updateField('city', v)} />
        </div>
      </Card>

      <Card>
        <h2 className="mb-4 text-sm font-semibold text-text">Lembretes</h2>
        <div className="mb-4 flex gap-2">
          <input
            type="date"
            value={reminderDate}
            onChange={(e) => setReminderDate(e.target.value)}
            className="rounded-lg border border-border bg-surface px-3 py-2 text-sm"
          />
          <input
            value={reminderNote}
            onChange={(e) => setReminderNote(e.target.value)}
            placeholder="Sobre o que é o follow-up?"
            className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm"
          />
          <button onClick={addReminder} className="rounded-lg bg-accent px-3 py-2 text-white">
            <Plus size={16} />
          </button>
        </div>
        <ul className="space-y-2">
          {contact.reminders.map((r) => (
            <li key={r.id} className="flex items-center gap-3 rounded-lg border border-border px-3 py-2">
              <button
                onClick={() => toggleReminder(r.id, r.is_done)}
                className={`flex h-5 w-5 items-center justify-center rounded-full border ${r.is_done ? 'border-accent bg-accent text-white' : 'border-border'}`}
              >
                {r.is_done && <Check size={12} />}
              </button>
              <div className={`flex-1 text-sm ${r.is_done ? 'text-muted line-through' : 'text-text'}`}>
                {r.note || 'Follow-up'}
              </div>
              <div className="text-xs text-muted">{formatDateOnly(r.due_date)}</div>
              <button onClick={() => removeReminder(r.id)} className="text-muted hover:text-red-500">
                <Trash2 size={14} />
              </button>
            </li>
          ))}
          {contact.reminders.length === 0 && <p className="text-sm text-muted">Nenhum lembrete ainda.</p>}
        </ul>
      </Card>

      <Card>
        <h2 className="mb-4 text-sm font-semibold text-text">Histórico de interações</h2>
        <div className="mb-4 flex gap-2">
          <select
            value={noteType}
            onChange={(e) => setNoteType(e.target.value as InteractionType)}
            className="rounded-lg border border-border bg-surface px-2 py-2 text-sm"
          >
            {Object.entries(INTERACTION_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <input
            value={noteContent}
            onChange={(e) => setNoteContent(e.target.value)}
            placeholder="O que aconteceu?"
            className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm"
          />
          <button onClick={addInteraction} className="rounded-lg bg-accent px-3 py-2 text-white">
            <Plus size={16} />
          </button>
        </div>
        <ul className="space-y-3">
          {contact.interactions.map((i) => (
            <li key={i.id} className="flex items-start gap-3 rounded-lg border border-border px-3 py-2">
              <span className="mt-0.5 rounded-full bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent">
                {INTERACTION_LABELS[i.type]}
              </span>
              <div className="flex-1">
                <p className="text-sm text-text">{i.content}</p>
                <p className="text-xs text-muted">{new Date(i.occurred_at).toLocaleString('pt-BR')}</p>
              </div>
              <button onClick={() => removeInteraction(i.id)} className="text-muted hover:text-red-500">
                <Trash2 size={14} />
              </button>
            </li>
          ))}
          {contact.interactions.length === 0 && <p className="text-sm text-muted">Nenhuma interação registrada.</p>}
        </ul>
      </Card>
    </div>
  )
}
