import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAppStore } from './store/appStore'
import ProfileSelector from './pages/ProfileSelector'
import AdminLayout from './pages/AdminLayout'
import MusicianLayout from './pages/MusicianLayout'
import CalendarPage from './pages/admin/CalendarPage'
import SongLibrary from './pages/admin/SongLibrary'
import MusiciansPage from './pages/admin/MusiciansPage'
import SetlistsPage from './pages/admin/SetlistsPage'

function App() {
  const { mode } = useAppStore()
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ProfileSelector />} />
        <Route path="/admin" element={mode === 'admin' ? <AdminLayout /> : <Navigate to="/" replace />}>
          <Route index element={<Navigate to="calendar" replace />} />
          <Route path="calendar" element={<CalendarPage />} />
          <Route path="songs" element={<SongLibrary />} />
          <Route path="musicians" element={<MusiciansPage />} />
          <Route path="setlists" element={<SetlistsPage />} />
        </Route>
        <Route
          path="/musician"
          element={mode !== null ? <MusicianLayout /> : <Navigate to="/" replace />}
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
