import ApiCard from '../components/ApiCard'
import { api } from '../api/client'

export default function Orders() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Заказы (зал)</h2>

      <ApiCard
        title="Заказы по ID"
        path="/api/1/order/by_id"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'orderIds', label: 'ID заказов *', type: 'array', required: true, placeholder: 'uuid1, uuid2' },
        ]}
        onExecute={(body) => api.orders.byId(body)}
      />

      <ApiCard
        title="Заказы по столику"
        path="/api/1/order/by_table"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'tableIds', label: 'ID столиков *', type: 'array', required: true, placeholder: 'uuid1' },
        ]}
        onExecute={(body) => api.orders.byTable(body)}
      />

      <ApiCard
        title="Создать заказ"
        path="/api/1/order/create"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'terminalGroupId', label: 'Терминальная группа *', type: 'terminal-select', required: true },
          { key: 'order', label: 'Order (JSON) *', type: 'textarea', required: true, placeholder: '{"tableIds":["uuid"],"items":[{"productId":"uuid","amount":1}]}' },
        ]}
        onExecute={(body) => {
          if (body.order && typeof body.order === 'string') try { body.order = JSON.parse(body.order) } catch {}
          return api.orders.create(body)
        }}
      />

      <ApiCard
        title="Добавить позиции"
        path="/api/1/order/add_items"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'orderId', label: 'ID заказа *', required: true },
          { key: 'items', label: 'Позиции (JSON) *', type: 'textarea', required: true, placeholder: '[{"productId":"uuid","amount":1}]' },
        ]}
        onExecute={(body) => {
          if (body.items && typeof body.items === 'string') try { body.items = JSON.parse(body.items) } catch {}
          return api.orders.addItems(body)
        }}
      />

      <ApiCard
        title="Закрыть заказ"
        path="/api/1/order/close"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'orderId', label: 'ID заказа *', required: true },
        ]}
        onExecute={(body) => api.orders.close(body)}
      />

      <ApiCard
        title="Отменить заказ"
        path="/api/1/order/cancel"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'orderId', label: 'ID заказа *', required: true },
        ]}
        onExecute={(body) => api.orders.cancel(body)}
      />
    </div>
  )
}
