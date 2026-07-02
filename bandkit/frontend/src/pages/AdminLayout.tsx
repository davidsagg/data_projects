import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAppStore } from '../store/appStore'
// setMode removido de goMusician — evita race condition com route guard

const navClass = ({ isActive }: { isActive: boolean }) =>
  `block px-4 py-2 rounded-lg text-sm font-medium transition ${
    isActive ? 'bg-blue-100 text-blue-700' : 'text-gray-700 hover:bg-gray-100'
  }`

export default function AdminLayout() {
  const { currentMusician, logout } = useAppStore()
  const navigate = useNavigate()

  const goMusician = () => {
    navigate('/musician')
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col shrink-0">
        <div className="p-5 border-b border-gray-100">
          <div className="text-lg font-bold text-gray-900">BandKit</div>
          <div className="text-sm text-gray-500 truncate">{currentMusician?.name}</div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          <NavLink to="/admin/calendar" className={navClass}>Calendário</NavLink>
          <NavLink to="/admin/setlists" className={navClass}>Setlists</NavLink>
          <NavLink to="/admin/songs" className={navClass}>Músicas</NavLink>
          <NavLink to="/admin/musicians" className={navClass}>Músicos</NavLink>
        </nav>

        <div className="p-3 border-t border-gray-100 space-y-1">
          <button
            onClick={goMusician}
            className="w-full text-left px-4 py-2 text-sm bg-green-50 text-green-700 rounded-lg hover:bg-green-100 font-medium"
          >
            Modo Músico
          </button>
          <button
            onClick={() => { logout(); navigate('/') }}
            className="w-full text-left px-4 py-2 text-sm text-gray-500 hover:bg-gray-100 rounded-lg"
          >
            Sair
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto min-w-0">
        <Outlet />
      </main>
    </div>
  )
}
