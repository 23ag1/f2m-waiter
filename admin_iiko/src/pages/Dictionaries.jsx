import ApiCard from '../components/ApiCard'
import { api } from '../api/client'

export default function Dictionaries() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Справочники</h2>

      <ApiCard title="Причины отмены" path="/api/1/cancel_causes"
        fields={[{ key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true }]}
        onExecute={(body) => api.dictionaries.cancelCauses(body)} />

      <ApiCard title="Типы заказов" path="/api/1/deliveries/order_types"
        fields={[{ key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true }]}
        onExecute={(body) => api.dictionaries.orderTypes(body)} />

      <ApiCard title="Скидки / Наценки" path="/api/1/discounts"
        fields={[{ key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true }]}
        onExecute={(body) => api.dictionaries.discounts(body)} />

      <ApiCard title="Типы оплаты" path="/api/1/payment_types"
        fields={[{ key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true }]}
        onExecute={(body) => api.dictionaries.paymentTypes(body)} />
    </div>
  )
}
