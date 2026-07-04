import ApiCard from '../components/ApiCard'
import { api } from '../api/client'

export default function Reports() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Отчёты</h2>

      <ApiCard
        title="Транзакции клиентов по дате"
        path="/api/1/loyalty/iiko/customer/transactions/by_date"
        fields={[
          { key: 'organizationId', label: 'ID организации *', required: true },
          { key: 'dateFrom', label: 'Дата от *', required: true, placeholder: '2024-01-01 00:00:00.000' },
          { key: 'dateTo', label: 'Дата до *', required: true, placeholder: '2024-12-31 23:59:59.999' },
          { key: 'customerId', label: 'UUID клиента' },
          { key: 'pageSize', label: 'Размер страницы', type: 'number', placeholder: '100' },
          { key: 'pageNumber', label: 'Номер страницы', type: 'number', placeholder: '1' },
        ]}
        onExecute={(body) => {
          if (body.pageSize) body.pageSize = Number(body.pageSize)
          if (body.pageNumber) body.pageNumber = Number(body.pageNumber)
          return api.customers.transactionsByDate(body)
        }}
      />

      <ApiCard
        title="Транзакции по ревизии"
        path="/api/1/loyalty/iiko/customer/transactions/by_revision"
        fields={[
          { key: 'organizationId', label: 'ID организации *', required: true },
          { key: 'startRevision', label: 'Ревизия с', type: 'number', placeholder: '0' },
          { key: 'pageSize', label: 'Размер страницы', type: 'number', placeholder: '100' },
          { key: 'pageNumber', label: 'Номер страницы', type: 'number', placeholder: '1' },
        ]}
        onExecute={(body) => {
          const token = localStorage.getItem('iiko_token')
          if (body.startRevision) body.startRevision = Number(body.startRevision)
          if (body.pageSize) body.pageSize = Number(body.pageSize)
          if (body.pageNumber) body.pageNumber = Number(body.pageNumber)
          return fetch('/iiko/api/1/loyalty/iiko/customer/transactions/by_revision', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify(body),
          }).then(r => r.json())
        }}
      />
    </div>
  )
}
