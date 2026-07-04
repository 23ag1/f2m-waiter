import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api, isAuthenticated } from '../api/client'

const IikoCtx = createContext(null)

export function IikoProvider({ children }) {
  const [orgs, setOrgs] = useState([])
  const [terminalGroups, setTerminalGroups] = useState({}) // orgId → terminals[]
  const [loading, setLoading] = useState(false)

  const loadOrgs = useCallback(async () => {
    if (!isAuthenticated()) return
    setLoading(true)
    try {
      const data = await api.organizations.list({})
      setOrgs(data.organizations ?? [])
    } catch {}
    setLoading(false)
  }, [])

  const loadTerminals = useCallback(async (orgId) => {
    if (terminalGroups[orgId]) return
    try {
      const data = await api.terminalGroups.list({ organizationIds: [orgId] })
      const tgs = data.terminalGroups?.[0]?.items ?? []
      setTerminalGroups(prev => ({ ...prev, [orgId]: tgs }))
    } catch {}
  }, [terminalGroups])

  useEffect(() => { loadOrgs() }, [loadOrgs])

  return (
    <IikoCtx.Provider value={{ orgs, terminalGroups, loadTerminals, loadOrgs, loading }}>
      {children}
    </IikoCtx.Provider>
  )
}

export function useIiko() {
  return useContext(IikoCtx)
}
