import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2, Users } from 'lucide-react'
import { contactsApi, groupsApi } from '../api/client'
import type { Group } from '../types'
import { Card } from '../components/Card'
import { useFiltersStore } from '../store/filters'

const COLOR_OPTIONS = [
  '#6d4aff',
  '#0ea5a4',
  '#e2622b',
  '#2563eb',
  '#c026d3',
  '#16a34a',
  '#d946ef',
  '#ea580c',
]

export function GroupsPage() {
  const navigate = useNavigate()
  const setGroupId = useFiltersStore((s) => s.setGroupId)
  const [groups, setGroups] = useState<Group[]>([])
  const [counts, setCounts] = useState<Record<number, number>>({})
  const [name, setName] = useState('')
  const [color, setColor] = useState(COLOR_OPTIONS[0])

  function load() {
    groupsApi.list().then(async (list) => {
      setGroups(list)
      const entries = await Promise.all(
        list.map(async (g) => [g.id, (await contactsApi.list({ group_id: g.id, page_size: 1 })).total] as const),
      )
      setCounts(Object.fromEntries(entries))
    })
  }

  useEffect(load, [])

  async function createGroup() {
    if (!name.trim()) return
    await groupsApi.create({ name: name.trim(), color })
    setName('')
    load()
  }

  async function removeGroup(id: number) {
    if (!confirm('Remover este grupo? Os contatos não serão apagados.')) return
    await groupsApi.remove(id)
    load()
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold text-text">Grupos</h1>
        <p className="text-sm text-muted">Organize seus contatos em listas, como "Board Advisors" ou "Prospects".</p>
      </div>

      <Card className="flex items-center gap-3">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && createGroup()}
          placeholder="Nome do novo grupo"
          className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm"
        />
        <div className="flex gap-1">
          {COLOR_OPTIONS.map((c) => (
            <button
              key={c}
              onClick={() => setColor(c)}
              className="h-6 w-6 rounded-full ring-offset-2"
              style={{ background: c, boxShadow: color === c ? `0 0 0 2px ${c}` : 'none' }}
              aria-label={`Cor ${c}`}
            />
          ))}
        </div>
        <button onClick={createGroup} className="flex items-center gap-1 rounded-lg bg-accent px-3 py-2 text-sm text-white">
          <Plus size={16} /> Criar
        </button>
      </Card>

      <div className="grid grid-cols-2 gap-4">
        {groups.map((g) => (
          <Card key={g.id} className="flex items-center justify-between">
            <button
              onClick={() => {
                setGroupId(g.id)
                navigate('/contacts')
              }}
              className="flex items-center gap-3 text-left"
            >
              <span className="h-3 w-3 rounded-full" style={{ background: g.color }} />
              <div>
                <div className="font-medium text-text">{g.name}</div>
                <div className="flex items-center gap-1 text-xs text-muted">
                  <Users size={12} /> {counts[g.id] ?? '...'} contatos
                </div>
              </div>
            </button>
            <button onClick={() => removeGroup(g.id)} className="text-muted hover:text-red-500">
              <Trash2 size={16} />
            </button>
          </Card>
        ))}
        {groups.length === 0 && <p className="text-sm text-muted">Nenhum grupo criado ainda.</p>}
      </div>
    </div>
  )
}
