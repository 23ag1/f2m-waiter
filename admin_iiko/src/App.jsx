import { useState } from 'react'
import { isAuthenticated, clearCredentials, getStoredApiLogin } from './api/client'
import { IikoProvider, useIiko } from './context/IikoContext'
import Login from './pages/Login'
import Sidebar from './components/Sidebar'
import Organizations from './pages/Organizations'
import TerminalGroups from './pages/TerminalGroups'
import Menu from './pages/Menu'
import Deliveries from './pages/Deliveries'
import Orders from './pages/Orders'
import Customers from './pages/Customers'
import Employees from './pages/Employees'
import Addresses from './pages/Addresses'
import Reserves from './pages/Reserves'
import Loyalty from './pages/Loyalty'
import Dictionaries from './pages/Dictionaries'
import Webhooks from './pages/Webhooks'
import Reports from './pages/Reports'

const PAGES = {
  organizations: Organizations,
  terminal_groups: TerminalGroups,
  menu: Menu,
  deliveries: Deliveries,
  orders: Orders,
  customers: Customers,
  employees: Employees,
  addresses: Addresses,
  reserves: Reserves,
  loyalty: Loyalty,
  dictionaries: Dictionaries,
  webhooks: Webhooks,
  reports: Reports,
}

function Dashboard() {
  const [section, setSection] = useState('organizations')
  const { loadOrgs } = useIiko()
  const Page = PAGES[section] ?? Organizations

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar active={section} onSelect={setSection} apiLogin={getStoredApiLogin()} onLogout={() => { clearCredentials(); window.location.reload() }} />
      <main style={{ flex: 1, overflowY: 'auto', padding: '32px 40px', background: '#f0f4f8' }}>
        <Page />
      </main>
    </div>
  )
}

export default function App() {
  const [authed, setAuthed] = useState(isAuthenticated)

  if (!authed) {
    return <Login onSuccess={() => setAuthed(true)} />
  }

  return (
    <IikoProvider>
      <Dashboard />
    </IikoProvider>
  )
}
