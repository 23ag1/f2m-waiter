import ApiCard from '../components/ApiCard'
import { api } from '../api/client'

export default function Addresses() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Адреса</h2>

      <ApiCard
        title="Регионы"
        path="/api/1/regions"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
        ]}
        onExecute={(body) => api.addresses.regions(body)}
      />

      <ApiCard
        title="Города"
        path="/api/1/cities"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
          { key: 'regionIds', label: 'ID регионов', type: 'array', placeholder: 'uuid1' },
        ]}
        onExecute={(body) => api.addresses.cities(body)}
      />

      <ApiCard
        title="Улицы по городу"
        path="/api/1/streets/by_city"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'cityId', label: 'ID города *', required: true },
        ]}
        onExecute={(body) => api.addresses.streets(body)}
      />
    </div>
  )
}
