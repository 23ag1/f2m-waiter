import ApiCard from '../components/ApiCard'
import { api } from '../api/client'

export default function Loyalty() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Лояльность и акции</h2>

      <ApiCard title="Программы лояльности" path="/api/1/loyalty/iiko/program"
        fields={[{ key: 'organizationId', label: 'Организация *', type: 'org-select', required: true }]}
        onExecute={(body) => api.loyalty.programs(body)} />

      <ApiCard title="Ручные условия" path="/api/1/loyalty/iiko/manual_condition"
        fields={[{ key: 'organizationId', label: 'Организация *', type: 'org-select', required: true }]}
        onExecute={(body) => api.loyalty.manualConditions(body)} />

      <ApiCard
        title="Рассчитать чек-ин"
        path="/api/1/loyalty/iiko/calculate"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'terminalGroupId', label: 'Терминальная группа *', type: 'terminal-select', required: true },
          { key: 'order', label: 'Order (JSON) *', type: 'textarea', required: true, placeholder: '{"phone":"+79001234567","items":[...]}' },
        ]}
        onExecute={(body) => {
          if (body.order && typeof body.order === 'string') try { body.order = JSON.parse(body.order) } catch {}
          return api.loyalty.calculate(body)
        }}
      />
    </div>
  )
}
