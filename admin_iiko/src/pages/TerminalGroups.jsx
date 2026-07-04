import ApiCard from '../components/ApiCard'
import { api } from '../api/client'

export default function TerminalGroups() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Терминальные группы</h2>

      <ApiCard
        title="Список терминальных групп"
        path="/api/1/terminal_groups"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
          { key: 'includeDisabled', label: 'Включить отключённые', type: 'select', default: 'false', options: [{ value: 'false', label: 'Нет' }, { value: 'true', label: 'Да' }] },
        ]}
        onExecute={(body) => api.terminalGroups.list(body)}
      />

      <ApiCard
        title="Доступность терминалов"
        path="/api/1/terminal_groups/is_alive"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
        ]}
        onExecute={(body) => api.terminalGroups.isAlive(body)}
      />

      <ApiCard
        title="Разбудить терминалы"
        path="/api/1/terminal_groups/awake"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
        ]}
        onExecute={(body) => api.terminalGroups.awake(body)}
      />
    </div>
  )
}
