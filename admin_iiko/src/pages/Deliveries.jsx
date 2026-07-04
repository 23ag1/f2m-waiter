import ApiCard from '../components/ApiCard'
import { api } from '../api/client'

export default function Deliveries() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Доставки</h2>

      <ApiCard
        title="Заказы по ID"
        path="/api/1/deliveries/by_id"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
          { key: 'orderIds', label: 'ID заказов *', type: 'array', required: true, placeholder: 'uuid1, uuid2' },
        ]}
        onExecute={(body) => api.deliveries.byId(body)}
      />

      <ApiCard
        title="Заказы по статусу и дате"
        path="/api/1/deliveries/by_delivery_date_and_status"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
          { key: 'deliveryDateFrom', label: 'Дата от', placeholder: '2024-01-01 00:00:00.000' },
          { key: 'deliveryDateTo', label: 'Дата до', placeholder: '2024-12-31 23:59:59.999' },
          { key: 'statuses', label: 'Статусы', type: 'array', hint: 'Unconfirmed, WaitCooking, OnWay, Delivered, Closed…', placeholder: 'Unconfirmed, WaitCooking' },
        ]}
        onExecute={(body) => api.deliveries.byDateAndStatus(body)}
      />

      <ApiCard
        title="Заказы по телефону"
        path="/api/1/deliveries/by_delivery_date_and_phone"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
          { key: 'phone', label: 'Телефон *', required: true, placeholder: '+79001234567' },
          { key: 'deliveryDateFrom', label: 'Дата от', placeholder: '2024-01-01 00:00:00.000' },
          { key: 'deliveryDateTo', label: 'Дата до', placeholder: '2024-12-31 23:59:59.999' },
        ]}
        onExecute={(body) => api.deliveries.byPhone(body)}
      />

      <ApiCard
        title="Заказы по ревизии"
        path="/api/1/deliveries/by_revision"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
          { key: 'startRevision', label: 'Ревизия с', type: 'number', placeholder: '0' },
        ]}
        onExecute={(body) => api.deliveries.byRevision(body)}
      />

      <ApiCard
        title="Создать доставку"
        path="/api/1/deliveries/create"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'terminalGroupId', label: 'Терминальная группа *', type: 'terminal-select', required: true },
          { key: 'order', label: 'Order (JSON) *', type: 'textarea', required: true, placeholder: '{"phone":"+79001234567","items":[...]}' },
        ]}
        onExecute={(body) => {
          if (body.order && typeof body.order === 'string') try { body.order = JSON.parse(body.order) } catch {}
          return api.deliveries.create(body)
        }}
      />

      <ApiCard
        title="Подтвердить доставку"
        path="/api/1/deliveries/confirm"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'orderId', label: 'ID заказа *', required: true },
        ]}
        onExecute={(body) => api.deliveries.confirm(body)}
      />

      <ApiCard
        title="Отменить доставку"
        path="/api/1/deliveries/cancel"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'orderId', label: 'ID заказа *', required: true },
          { key: 'cancelCauseId', label: 'Причина отмены (UUID)', placeholder: 'uuid' },
        ]}
        onExecute={(body) => api.deliveries.cancel(body)}
      />

      <ApiCard
        title="Обновить статус доставки"
        path="/api/1/deliveries/update_order_delivery_status"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'orderId', label: 'ID заказа *', required: true },
          { key: 'deliveryStatus', label: 'Новый статус *', type: 'select', default: 'Delivered', options: [
            { value: 'Delivered', label: 'Delivered' },
            { value: 'OnWay', label: 'OnWay' },
            { value: 'Waiting', label: 'Waiting' },
            { value: 'CookingCompleted', label: 'CookingCompleted' },
          ]},
        ]}
        onExecute={(body) => api.deliveries.updateStatus(body)}
      />

      <ApiCard
        title="Назначить курьера"
        path="/api/1/deliveries/update_order_courier"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'orderId', label: 'ID заказа *', required: true },
          { key: 'courierId', label: 'ID курьера *', required: true },
        ]}
        onExecute={(body) => api.deliveries.updateCourier(body)}
      />

      <ApiCard
        title="Изменить комментарий"
        path="/api/1/deliveries/change_comment"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'orderId', label: 'ID заказа *', required: true },
          { key: 'comment', label: 'Комментарий', placeholder: 'Позвонить перед приездом' },
        ]}
        onExecute={(body) => api.deliveries.changeComment(body)}
      />

      <ApiCard
        title="Закрыть заказ доставки"
        path="/api/1/deliveries/close"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'orderId', label: 'ID заказа *', required: true },
        ]}
        onExecute={(body) => api.deliveries.close(body)}
      />
    </div>
  )
}
