import ApiCard from '../components/ApiCard'
import { api } from '../api/client'

export default function Customers() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Клиенты</h2>

      <ApiCard
        title="Информация о клиенте"
        path="/api/1/loyalty/iiko/customer/info"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'phone', label: 'Телефон', placeholder: '+79001234567' },
          { key: 'email', label: 'Email' },
          { key: 'cardNumber', label: 'Номер карты' },
          { key: 'id', label: 'UUID клиента' },
        ]}
        onExecute={(body) => api.customers.info(body)}
      />

      <ApiCard
        title="Создать / обновить клиента"
        path="/api/1/loyalty/iiko/customer/create_or_update"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'phone', label: 'Телефон', placeholder: '+79001234567' },
          { key: 'name', label: 'Имя' },
          { key: 'surname', label: 'Фамилия' },
          { key: 'email', label: 'Email' },
          { key: 'birthday', label: 'День рождения', placeholder: '1990-01-15' },
          { key: 'sex', label: 'Пол', type: 'select', default: '', options: [{ value: '', label: '—' }, { value: 'Male', label: 'Мужской' }, { value: 'Female', label: 'Женский' }] },
          { key: 'id', label: 'UUID (если обновление)' },
        ]}
        onExecute={(body) => api.customers.createOrUpdate(body)}
      />

      <ApiCard
        title="Пополнить кошелёк"
        path="/api/1/loyalty/iiko/customer/wallet/topup"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'customerId', label: 'UUID клиента *', required: true },
          { key: 'walletId', label: 'UUID кошелька *', required: true },
          { key: 'sum', label: 'Сумма *', type: 'number', required: true, placeholder: '500' },
          { key: 'comment', label: 'Комментарий' },
        ]}
        onExecute={(body) => { if (body.sum) body.sum = Number(body.sum); return api.customers.topupWallet(body) }}
      />

      <ApiCard
        title="Списать с кошелька"
        path="/api/1/loyalty/iiko/customer/wallet/chargeoff"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'customerId', label: 'UUID клиента *', required: true },
          { key: 'walletId', label: 'UUID кошелька *', required: true },
          { key: 'sum', label: 'Сумма *', type: 'number', required: true, placeholder: '100' },
        ]}
        onExecute={(body) => { if (body.sum) body.sum = Number(body.sum); return api.customers.chargeoffWallet(body) }}
      />

      <ApiCard
        title="Добавить карту"
        path="/api/1/loyalty/iiko/customer/card/add"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'customerId', label: 'UUID клиента *', required: true },
          { key: 'cardNumber', label: 'Номер карты *', required: true },
        ]}
        onExecute={(body) => api.customers.addCard(body)}
      />

      <ApiCard
        title="Транзакции по дате"
        path="/api/1/loyalty/iiko/customer/transactions/by_date"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'dateFrom', label: 'Дата от *', required: true, placeholder: '2024-01-01 00:00:00.000' },
          { key: 'dateTo', label: 'Дата до *', required: true, placeholder: '2024-12-31 23:59:59.999' },
          { key: 'customerId', label: 'UUID клиента' },
        ]}
        onExecute={(body) => api.customers.transactionsByDate(body)}
      />
    </div>
  )
}
