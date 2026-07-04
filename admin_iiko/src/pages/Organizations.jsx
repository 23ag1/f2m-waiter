import ApiCard from '../components/ApiCard'
import { api } from '../api/client'

export default function Organizations() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Организации</h2>

      <ApiCard
        title="Список организаций"
        path="/api/1/organizations"
        description="Возвращает все организации доступные api-login пользователю."
        fields={[
          { key: 'organizationIds', label: 'Организации', type: 'org-multi', hint: 'необязательно' },
          { key: 'returnAdditionalInfo', label: 'Вернуть доп. информацию', type: 'select', default: 'false', options: [{ value: 'false', label: 'Нет' }, { value: 'true', label: 'Да' }] },
          { key: 'includeDisabled', label: 'Включить отключённые', type: 'select', default: 'false', options: [{ value: 'false', label: 'Нет' }, { value: 'true', label: 'Да' }] },
        ]}
        onExecute={(body) => api.organizations.list(body)}
      />

      <ApiCard
        title="Настройки организации"
        path="/api/1/organizations/settings"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
        ]}
        onExecute={(body) => api.organizations.settings(body)}
      />
    </div>
  )
}
