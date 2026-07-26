import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Search, Plus, ChevronLeft, ChevronRight, X, Star } from 'lucide-react'
import clsx from 'clsx'
import { companiesApi, contactsApi, groupsApi } from '../api/client'
import type { Company, ContactListItem, FacetItem, Group } from '../types'
import { useFiltersStore } from '../store/filters'
import { Avatar } from '../components/Avatar'
import { GroupChip } from '../components/GroupChip'
import { FavoriteStar } from '../components/FavoriteStar'
import { SortableTh } from '../components/SortableTh'
import { SECTORS } from '../lib/sectors'
import { SENIORITY_LEVELS } from '../lib/seniority'

const PAGE_SIZE = 50

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('pt-BR')
}

export function ContactsListPage() {
  const filters = useFiltersStore()
  const [contacts, setContacts] = useState<ContactListItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [companies, setCompanies] = useState<Company[]>([])
  const [cities, setCities] = useState<FacetItem[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [assignGroupId, setAssignGroupId] = useState('')

  useEffect(() => {
    companiesApi.list().then(setCompanies)
    contactsApi.locations().then(setCities)
    groupsApi.list().then(setGroups)
  }, [])

  const load = useCallback(() => {
    setLoading(true)
    contactsApi
      .list({
        q: filters.q || undefined,
        group_id: filters.groupId || undefined,
        company_id: filters.companyId || undefined,
        sector: filters.sector || undefined,
        seniority: filters.seniority || undefined,
        city: filters.city || undefined,
        favorite_only: filters.favoriteOnly || undefined,
        sort: filters.sort,
        sort_dir: filters.sortDir,
        page: filters.page,
        page_size: PAGE_SIZE,
      })
      .then((res) => {
        setContacts(res.items)
        setTotal(res.total)
        setLoading(false)
      })
  }, [
    filters.q,
    filters.groupId,
    filters.companyId,
    filters.sector,
    filters.seniority,
    filters.city,
    filters.favoriteOnly,
    filters.sort,
    filters.sortDir,
    filters.page,
  ])

  useEffect(() => {
    load()
  }, [load])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const allSelected = contacts.length > 0 && contacts.every((c) => selected.has(c.id))

  function toggleAll() {
    if (allSelected) {
      setSelected(new Set())
    } else {
      setSelected(new Set(contacts.map((c) => c.id)))
    }
  }

  function toggleOne(id: number) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  async function applyBulkGroup() {
    if (!assignGroupId) return
    await Promise.all([...selected].map((id) => groupsApi.assign(id, Number(assignGroupId))))
    setSelected(new Set())
    setAssignGroupId('')
    load()
  }

  async function toggleFavorite(id: number) {
    setContacts((prev) => prev.map((c) => (c.id === id ? { ...c, is_favorite: !c.is_favorite } : c)))
    await contactsApi.toggleFavorite(id)
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Contatos</h1>
          <p className="text-sm text-muted">{total.toLocaleString('pt-BR')} contatos</p>
        </div>
        <Link
          to="/contacts/new"
          className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          <Plus size={16} />
          Novo contato
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-64">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={filters.q}
            onChange={(e) => filters.setQ(e.target.value)}
            placeholder="Buscar por nome, empresa ou cargo..."
            className="w-full rounded-lg border border-border bg-surface py-2 pl-9 pr-3 text-sm outline-none focus:border-accent"
          />
        </div>
        <select
          value={filters.companyId ?? ''}
          onChange={(e) => filters.setCompanyId(e.target.value ? Number(e.target.value) : null)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text"
        >
          <option value="">Todas as empresas</option>
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.contact_count})
            </option>
          ))}
        </select>
        <select
          value={filters.sector ?? ''}
          onChange={(e) => filters.setSector(e.target.value || null)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text"
        >
          <option value="">Todos os setores</option>
          {SECTORS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={filters.seniority ?? ''}
          onChange={(e) => filters.setSeniority(e.target.value || null)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text"
        >
          <option value="">Toda senioridade</option>
          {SENIORITY_LEVELS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={filters.city || ''}
          onChange={(e) => filters.setCity(e.target.value || null)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text"
        >
          <option value="">Todas as cidades</option>
          {cities.map((c) => (
            <option key={c.value} value={c.value}>
              {c.value} ({c.count})
            </option>
          ))}
        </select>
        <button
          onClick={() => filters.setFavoriteOnly(!filters.favoriteOnly)}
          className={clsx(
            'flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium',
            filters.favoriteOnly
              ? 'border-amber-300 bg-amber-50 text-amber-600'
              : 'border-border bg-surface text-muted hover:text-text',
          )}
        >
          <Star size={14} fill={filters.favoriteOnly ? 'currentColor' : 'none'} />
          Favoritos
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => filters.setGroupId(null)}
          className={clsx(
            'rounded-full px-3 py-1 text-xs font-medium',
            !filters.groupId ? 'bg-accent text-white' : 'bg-accent-soft text-accent',
          )}
        >
          Todos os grupos
        </button>
        {groups.map((g) => (
          <button
            key={g.id}
            onClick={() => filters.setGroupId(filters.groupId === g.id ? null : g.id)}
            className={clsx(
              'rounded-full px-3 py-1 text-xs font-medium',
              filters.groupId === g.id ? 'text-white' : 'text-text',
            )}
            style={{
              background: filters.groupId === g.id ? g.color : `${g.color}22`,
              color: filters.groupId === g.id ? '#fff' : g.color,
            }}
          >
            {g.name}
          </button>
        ))}
      </div>

      {selected.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border border-accent bg-accent-soft px-4 py-2">
          <span className="text-sm font-medium text-accent">{selected.size} selecionado(s)</span>
          <select
            value={assignGroupId}
            onChange={(e) => setAssignGroupId(e.target.value)}
            className="rounded-lg border border-border bg-surface px-2 py-1 text-sm"
          >
            <option value="">Adicionar ao grupo...</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
          <button
            onClick={applyBulkGroup}
            disabled={!assignGroupId}
            className="rounded-lg bg-accent px-3 py-1 text-sm font-medium text-white disabled:opacity-40"
          >
            Aplicar
          </button>
          <button onClick={() => setSelected(new Set())} className="ml-auto text-muted hover:text-text">
            <X size={16} />
          </button>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-border bg-surface">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border bg-canvas/50 text-xs uppercase text-muted">
            <tr>
              <th className="w-10 px-4 py-3">
                <input type="checkbox" checked={allSelected} onChange={toggleAll} />
              </th>
              <th className="w-8 px-2 py-3"></th>
              <SortableTh field="name" label="Nome" activeField={filters.sort} direction={filters.sortDir} onSort={filters.toggleSort} />
              <SortableTh field="company" label="Empresa" activeField={filters.sort} direction={filters.sortDir} onSort={filters.toggleSort} />
              <th className="px-2 py-3">Cargo</th>
              <SortableTh field="seniority" label="Senioridade" activeField={filters.sort} direction={filters.sortDir} onSort={filters.toggleSort} />
              <th className="px-2 py-3">Cidade</th>
              <th className="px-2 py-3">Grupos</th>
              <th className="px-2 py-3">Último contato</th>
            </tr>
          </thead>
          <tbody>
            {contacts.map((c) => (
              <tr key={c.id} className="border-b border-border last:border-0 hover:bg-accent-soft/30">
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selected.has(c.id)}
                    onChange={() => toggleOne(c.id)}
                    onClick={(e) => e.stopPropagation()}
                  />
                </td>
                <td className="px-2 py-3">
                  <FavoriteStar isFavorite={c.is_favorite} onToggle={() => toggleFavorite(c.id)} size={16} />
                </td>
                <td className="px-2 py-3">
                  <Link to={`/contacts/${c.id}`} className="flex items-center gap-3">
                    <Avatar firstName={c.first_name} lastName={c.last_name} size={32} />
                    <span className="font-medium text-text">
                      {c.first_name} {c.last_name}
                    </span>
                  </Link>
                </td>
                <td className="px-2 py-3 text-muted">{c.company || '—'}</td>
                <td className="px-2 py-3 text-muted">{c.position || '—'}</td>
                <td className="px-2 py-3 text-muted">{c.seniority || '—'}</td>
                <td className="px-2 py-3 text-muted">{c.city || '—'}</td>
                <td className="px-2 py-3">
                  <div className="flex flex-wrap gap-1">
                    {c.groups.map((g) => (
                      <GroupChip key={g.id} group={g} />
                    ))}
                  </div>
                </td>
                <td className="px-2 py-3 text-muted">{formatDate(c.last_contacted_at)}</td>
              </tr>
            ))}
            {!loading && contacts.length === 0 && (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-muted">
                  Nenhum contato encontrado com esses filtros.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted">
        <span>
          Página {filters.page} de {totalPages}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => filters.setPage(Math.max(1, filters.page - 1))}
            disabled={filters.page <= 1}
            className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 disabled:opacity-40"
          >
            <ChevronLeft size={14} /> Anterior
          </button>
          <button
            onClick={() => filters.setPage(Math.min(totalPages, filters.page + 1))}
            disabled={filters.page >= totalPages}
            className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 disabled:opacity-40"
          >
            Próxima <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}
