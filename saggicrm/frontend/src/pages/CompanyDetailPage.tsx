import { useCallback, useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { companiesApi } from '../api/client'
import type { CompanyDetail } from '../types'
import { Card } from '../components/Card'
import { Avatar } from '../components/Avatar'
import { GroupChip } from '../components/GroupChip'
import { HorizontalBarChart } from '../components/charts/HorizontalBarChart'
import { SECTORS } from '../lib/sectors'

export function CompanyDetailPage() {
  const { id } = useParams()
  const companyId = Number(id)
  const [company, setCompany] = useState<CompanyDetail | null>(null)

  const load = useCallback(() => {
    companiesApi.get(companyId).then(setCompany)
  }, [companyId])

  useEffect(() => {
    load()
  }, [load])

  async function updateSector(sector: string) {
    await companiesApi.update(companyId, { sector: sector || undefined })
    load()
  }

  if (!company) {
    return <div className="p-8 text-muted">Carregando...</div>
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-8">
      <Link to="/companies" className="flex items-center gap-1 text-sm text-muted hover:text-text">
        <ArrowLeft size={14} /> Empresas
      </Link>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">{company.name}</h1>
          <p className="text-sm text-muted">{company.contact_count} contatos na sua rede</p>
        </div>
        <select
          value={company.sector || ''}
          onChange={(e) => updateSector(e.target.value)}
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text"
        >
          <option value="">Sem setor</option>
          {SECTORS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <Card>
        <h2 className="mb-4 text-sm font-semibold text-text">Cargos por senioridade</h2>
        <HorizontalBarChart
          data={company.seniority_breakdown.map((s) => ({ label: s.value, value: s.count }))}
        />
      </Card>

      <Card>
        <h2 className="mb-4 text-sm font-semibold text-text">Contatos</h2>
        <ul className="divide-y divide-border">
          {company.contacts.map((c) => (
            <li key={c.id} className="flex items-center gap-3 py-3">
              <Link to={`/contacts/${c.id}`} className="flex flex-1 items-center gap-3">
                <Avatar firstName={c.first_name} lastName={c.last_name} size={32} />
                <div>
                  <div className="text-sm font-medium text-text">
                    {c.first_name} {c.last_name}
                  </div>
                  <div className="text-xs text-muted">{c.position || '—'}</div>
                </div>
              </Link>
              <div className="flex flex-wrap gap-1">
                {c.groups.map((g) => (
                  <GroupChip key={g.id} group={g} />
                ))}
              </div>
            </li>
          ))}
          {company.contacts.length === 0 && (
            <li className="py-6 text-center text-sm text-muted">Nenhum contato vinculado.</li>
          )}
        </ul>
      </Card>
    </div>
  )
}
