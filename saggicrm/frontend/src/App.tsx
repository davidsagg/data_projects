import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { ContactsListPage } from './pages/ContactsListPage'
import { ContactDetailPage } from './pages/ContactDetailPage'
import { ContactNewPage } from './pages/ContactNewPage'
import { GroupsPage } from './pages/GroupsPage'
import { CompaniesListPage } from './pages/CompaniesListPage'
import { CompanyDetailPage } from './pages/CompanyDetailPage'
import { MapPage } from './pages/MapPage'
import { RemindersPage } from './pages/RemindersPage'
import { ImportPage } from './pages/ImportPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/contacts" element={<ContactsListPage />} />
        <Route path="/contacts/new" element={<ContactNewPage />} />
        <Route path="/contacts/:id" element={<ContactDetailPage />} />
        <Route path="/groups" element={<GroupsPage />} />
        <Route path="/companies" element={<CompaniesListPage />} />
        <Route path="/companies/:id" element={<CompanyDetailPage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/reminders" element={<RemindersPage />} />
        <Route path="/import" element={<ImportPage />} />
      </Route>
    </Routes>
  )
}
