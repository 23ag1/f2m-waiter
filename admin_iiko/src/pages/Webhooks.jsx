import ApiCard from '../components/ApiCard'
import { api } from '../api/client'

export default function Webhooks() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Вебхуки</h2>

      <ApiCard title="Настройки вебхуков" path="/api/1/webhooks/settings"
        fields={[{ key: 'organizationId', label: 'Организация *', type: 'org-select', required: true }]}
        onExecute={(body) => api.webhooks.settings(body)} />

      <ApiCard
        title="Обновить настройки вебхуков"
        path="/api/1/webhooks/update_settings"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'webHooksUri', label: 'URL вебхука *', required: true, placeholder: 'https://your-server.com/webhook' },
          { key: 'authToken', label: 'Auth token' },
        ]}
        onExecute={(body) => api.webhooks.updateSettings(body)}
      />
    </div>
  )
}
