import ApiCard from '../components/ApiCard'
import { api } from '../api/client'

export default function Employees() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Сотрудники / Курьеры</h2>

      <ApiCard
        title="Список курьеров"
        path="/api/1/employees/couriers"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
        ]}
        onExecute={(body) => api.employees.couriers(body)}
      />

      <ApiCard
        title="Активные локации курьеров"
        path="/api/1/employees/couriers/active_location"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
        ]}
        onExecute={(body) => api.employees.activeLocations(body)}
      />

      <ApiCard
        title="Информация о сотруднике"
        path="/api/1/employees/info"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
          { key: 'ids', label: 'ID сотрудников', type: 'array', placeholder: 'uuid1' },
        ]}
        onExecute={(body) => api.employees.info(body)}
      />
    </div>
  )
}
