import ApiCard from '../components/ApiCard'

function reserveApi(path, body) {
  const token = localStorage.getItem('iiko_token')
  return fetch(`/iiko${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  }).then(r => r.json())
}

export default function Reserves() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Банкеты / Брони</h2>

      <ApiCard title="Доступные организации для броней" path="/api/1/reserve/available_organizations"
        fields={[{ key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true }]}
        onExecute={(body) => reserveApi('/api/1/reserve/available_organizations', body)} />

      <ApiCard title="Доступные терминальные группы" path="/api/1/reserve/available_terminal_groups"
        fields={[{ key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true }]}
        onExecute={(body) => reserveApi('/api/1/reserve/available_terminal_groups', body)} />

      <ApiCard title="Секции ресторана" path="/api/1/reserve/available_restaurant_sections"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
          { key: 'terminalGroupIds', label: 'ID терминальных групп *', type: 'array', required: true, placeholder: 'uuid1' },
        ]}
        onExecute={(body) => reserveApi('/api/1/reserve/available_restaurant_sections', body)} />

      <ApiCard
        title="Создать бронь"
        path="/api/1/reserve/create"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'terminalGroupId', label: 'Терминальная группа *', type: 'terminal-select', required: true },
          { key: 'reserve', label: 'Reserve (JSON) *', type: 'textarea', required: true, placeholder: '{"tableIds":["uuid"],"guestsCount":4,"startTime":"2024-12-01 19:00:00.000"}' },
        ]}
        onExecute={(body) => {
          if (body.reserve && typeof body.reserve === 'string') try { body.reserve = JSON.parse(body.reserve) } catch {}
          return reserveApi('/api/1/reserve/create', body)
        }}
      />

      <ApiCard title="Статус броней по ID" path="/api/1/reserve/status_by_id"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
          { key: 'reserveIds', label: 'ID броней *', type: 'array', required: true, placeholder: 'uuid1' },
        ]}
        onExecute={(body) => reserveApi('/api/1/reserve/status_by_id', body)} />

      <ApiCard title="Отменить бронь" path="/api/1/reserve/cancel"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'reserveId', label: 'ID брони *', required: true },
        ]}
        onExecute={(body) => reserveApi('/api/1/reserve/cancel', body)} />
    </div>
  )
}
