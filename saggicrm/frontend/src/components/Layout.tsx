import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  FolderKanban,
  Building2,
  Map,
  BellRing,
  UploadCloud,
  Contact2,
} from 'lucide-react'
import clsx from 'clsx'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/contacts', label: 'Contatos', icon: Users },
  { to: '/groups', label: 'Grupos', icon: FolderKanban },
  { to: '/companies', label: 'Empresas', icon: Building2 },
  { to: '/map', label: 'Mapa', icon: Map },
  { to: '/reminders', label: 'Lembretes', icon: BellRing },
  { to: '/import', label: 'Importar', icon: UploadCloud },
]

export function Layout() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-canvas text-text">
      <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-white">
            <Contact2 size={18} />
          </div>
          <span className="text-lg font-semibold">SaggiCRM</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-accent-soft text-accent'
                    : 'text-muted hover:bg-accent-soft/60 hover:text-text',
                )
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-4 text-xs text-muted">CRM pessoal · 100% local</div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
