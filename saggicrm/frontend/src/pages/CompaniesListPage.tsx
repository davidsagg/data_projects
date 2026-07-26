import { useEffect, useState, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { companiesApi } from '../api/client'
import type { Company } from '../types'
import { SECTORS } from '../lib/sectors'
import { SortableTh } from '../components/SortableTh'

type SortField = 'contacts' | 'name' | 'sector'
type SortDir = 'asc' | 'desc'

const DEFAULT_DIR: Record<SortField, SortDir> = {
  contacts: 'desc',
  name: 'asc',
  sector: 'asc',
}

const COLUMNS: { field: SortField; label: string; align?: 'right' }[] = [
  { field: 'name', label: 'Empresa' },
  { field: 'sector', label: 'Setor' },
  { field: 'contacts', label: 'Contatos', align: 'right' },
]

export function CompaniesListPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [sector, setSector] = useState(searchParams.get('sector') || '')
  const [sort, setSort] = useState<SortField>('contacts')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [bulkSector, setBulkSector] = useState('')

  function handleSort(field: SortField) {
    if (field === sort) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSort(field)
      setSortDir(DEFAULT_DIR[field])
    }
  }

  function updateSector(value: string) {
    setSector(value)
    setSearchParams(value ? { sector: value } : {})
  }

  // Keeps the dropdown in sync when arriving here from another page (e.g. the
  // Dashboard's sector chart) while this route instance is already mounted.
  useEffect(() => {
    setSector(searchParams.get('sector') || '')
  }, [searchParams])

  const load = useCallback(() => {
    setLoading(true)
    companiesApi
      .list({ q: q || undefined, sector: sector || undefined, sort, sort_dir: sortDir })
      .then((data) => {
        setCompanies(data)
        setLoading(false)
      })
  }, [q, sector, sort, sortDir])

  useEffect(() => {
    load()
  }, [load])

  function toggleOne(id: number) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  function toggleAll() {
    if (selected.size === companies.length) setSelected(new Set())
    else setSelected(new Set(companies.map((c) => c.id)))
  }

  async function applyBulkSector() {
    if (!bulkSector) return
    await companiesApi.bulkSector([...selected], bulkSector)
    setSelected(new Set())
    setBulkSector('')
    load()
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5 p-8">
      <div>
        <h1 className="text-2xl font-semibold text-text">Empresas</h1>
        <p className="text-sm text-muted">
          {companies.length.toLocaleString('pt-BR')} empresas na sua rede — organize por setor.
        </p>
        {sector && (
          <button
            onClick={() => updateSector('')}
            className="mt-2 flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent hover:opacity-80"
          >
            Setor: {sector}
            <X size={12} />
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-64">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar empresa..."
            className="w-full rounded-lg border border-border bg-surface py-2 pl-9 pr-3 text-sm outline-none focus:border-accent"
          />
        </div>
        <select
          value={sector}
          onChange={(e) => updateSector(e.target.value)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text"
        >
          <option value="">Todos os setores</option>
          {SECTORS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {selected.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border border-accent bg-accent-soft px-4 py-2">
          <span className="text-sm font-medium text-accent">{selected.size} selecionada(s)</span>
          <select
            value={bulkSector}
            onChange={(e) => setBulkSector(e.target.value)}
            className="rounded-lg border border-border bg-surface px-2 py-1 text-sm"
          >
            <option value="">Atribuir setor...</option>
            {SECTORS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <button
            onClick={applyBulkSector}
            disabled={!bulkSector}
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
                <input
                  type="checkbox"
                  checked={companies.length > 0 && selected.size === companies.length}
                  onChange={toggleAll}
                />
              </th>
              {COLUMNS.map((col) => (
                <SortableTh
                  key={col.field}
                  field={col.field}
                  label={col.label}
                  activeField={sort}
                  direction={sortDir}
                  onSort={handleSort}
                  align={col.align === 'right' ? 'right' : 'left'}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {companies.map((c) => (
              <tr key={c.id} className="border-b border-border last:border-0 hover:bg-accent-soft/30">
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selected.has(c.id)}
                    onChange={() => toggleOne(c.id)}
                  />
                </td>
                <td className="px-2 py-3">
                  <Link to={`/companies/${c.id}`} className="font-medium text-text hover:text-accent">
                    {c.name}
                  </Link>
                </td>
                <td className="px-2 py-3 text-muted">
                  {c.sector || <span className="italic text-border">sem setor</span>}
                </td>
                <td className="px-2 py-3 text-right text-muted">{c.contact_count}</td>
              </tr>
            ))}
            {!loading && companies.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-muted">
                  Nenhuma empresa encontrada.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
