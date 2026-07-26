import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Users, FolderKanban, MapPin, Star } from 'lucide-react'
import { statsApi } from '../api/client'
import type { StatsOut } from '../types'
import { StatTile } from '../components/StatTile'
import { Card } from '../components/Card'
import { HorizontalBarChart } from '../components/charts/HorizontalBarChart'
import { TimeSeriesChart } from '../components/charts/TimeSeriesChart'
import { Avatar } from '../components/Avatar'
import { FavoriteStar } from '../components/FavoriteStar'
import { formatDateOnly } from '../lib/date'
import { useFiltersStore } from '../store/filters'
import { contactsApi } from '../api/client'

export function DashboardPage() {
  const [stats, setStats] = useState<StatsOut | null>(null)
  const navigate = useNavigate()
  const filters = useFiltersStore()

  function load() {
    statsApi.get().then(setStats)
  }

  useEffect(load, [])

  function goToCompany(companyId: number | null | undefined) {
    if (!companyId) return
    filters.reset()
    filters.setCompanyId(companyId)
    navigate('/contacts')
  }

  function goToSeniority(level: string) {
    filters.reset()
    filters.setSeniority(level)
    navigate('/contacts')
  }

  function goToSector(sector: string) {
    navigate(`/companies?sector=${encodeURIComponent(sector)}`)
  }

  async function toggleFavorite(id: number) {
    await contactsApi.toggleFavorite(id)
    load()
  }

  if (!stats) {
    return <div className="p-8 text-muted">Carregando...</div>
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold text-text">Dashboard</h1>
        <p className="text-sm text-muted">Visão geral da sua rede de contatos.</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatTile label="Contatos" value={stats.total_contacts.toLocaleString('pt-BR')} icon={<Users size={20} />} />
        <StatTile label="Grupos" value={stats.total_groups} icon={<FolderKanban size={20} />} />
        <StatTile label="Sem cidade definida" value={stats.contacts_missing_city.toLocaleString('pt-BR')} icon={<MapPin size={20} />} />
        <StatTile label="Favoritos" value={stats.total_favorites} icon={<Star size={20} />} />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-text">Top empresas</h2>
          <HorizontalBarChart
            data={stats.top_companies.map((c) => ({ label: c.value, value: c.count, id: c.id }))}
            onSelect={(d) => goToCompany(d.id)}
          />
          <Link to="/companies" className="mt-3 block text-xs font-medium text-accent hover:underline">
            Ver todas as empresas
          </Link>
        </Card>
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-text">Conexões por ano</h2>
          <TimeSeriesChart data={stats.connections_by_year.map((c) => ({ label: c.value, value: c.count }))} />
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-text">Cargos por senioridade</h2>
          <HorizontalBarChart
            data={stats.seniority_breakdown.map((s) => ({ label: s.value, value: s.count }))}
            onSelect={(d) => goToSeniority(d.label)}
          />
        </Card>
        <Card>
          <h2 className="mb-4 text-sm font-semibold text-text">Top setores</h2>
          <HorizontalBarChart
            data={stats.top_sectors.map((s) => ({ label: s.value, value: s.count }))}
            onSelect={(d) => goToSector(d.label)}
          />
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text">Próximos lembretes</h2>
            <Link to="/reminders" className="text-xs font-medium text-accent hover:underline">
              Ver todos
            </Link>
          </div>
          {stats.upcoming_reminders.length === 0 && (
            <p className="text-sm text-muted">Nenhum lembrete pendente.</p>
          )}
          <ul className="space-y-3">
            {stats.upcoming_reminders.map((r) => (
              <li key={r.id}>
                <Link to={`/contacts/${r.contact_id}`} className="block rounded-lg p-2 hover:bg-accent-soft/50">
                  <div className="text-sm font-medium text-text">{r.note || 'Follow-up'}</div>
                  <div className="text-xs text-muted">{formatDateOnly(r.due_date)}</div>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text">Contatos recentes</h2>
            <Link to="/contacts" className="text-xs font-medium text-accent hover:underline">
              Ver todos
            </Link>
          </div>
          <ul className="space-y-3">
            {stats.recent_contacts.map((c) => (
              <li key={c.id}>
                <Link to={`/contacts/${c.id}`} className="flex items-center gap-3 rounded-lg p-2 hover:bg-accent-soft/50">
                  <Avatar firstName={c.first_name} lastName={c.last_name} size={32} />
                  <div>
                    <div className="text-sm font-medium text-text">
                      {c.first_name} {c.last_name}
                    </div>
                    <div className="text-xs text-muted">{c.company || '—'}</div>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text">Favoritos</h2>
          <Link to="/contacts" className="text-xs font-medium text-accent hover:underline">
            Ver todos
          </Link>
        </div>
        {stats.favorite_contacts.length === 0 ? (
          <p className="text-sm text-muted">
            Marque contatos importantes como favoritos para reforçar o networking com eles.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {stats.favorite_contacts.map((c) => (
              <div key={c.id} className="flex items-center gap-3 rounded-lg p-2 hover:bg-accent-soft/50">
                <Link to={`/contacts/${c.id}`} className="flex flex-1 items-center gap-3">
                  <Avatar firstName={c.first_name} lastName={c.last_name} size={32} />
                  <div>
                    <div className="text-sm font-medium text-text">
                      {c.first_name} {c.last_name}
                    </div>
                    <div className="text-xs text-muted">{c.company || '—'}</div>
                  </div>
                </Link>
                <FavoriteStar isFavorite={c.is_favorite} onToggle={() => toggleFavorite(c.id)} size={16} />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
