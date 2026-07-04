import ApiCard from '../components/ApiCard'
import { api } from '../api/client'

export default function Menu() {
  return (
    <div>
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '20px', color: '#0f172a' }}>Меню / Стоп-лист</h2>

      <ApiCard
        title="Номенклатура (меню)"
        path="/api/1/nomenclature"
        description="Возвращает полное меню организации."
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'startRevision', label: 'Ревизия (инкрементально)', placeholder: '0' },
        ]}
        onExecute={(body) => api.menu.nomenclature(body)}
      />

      <ApiCard
        title="Внешние меню (v2)"
        path="/api/2/menu"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
        ]}
        onExecute={(body) => api.menu.externalMenus(body)}
      />

      <ApiCard
        title="Внешнее меню по ID"
        path="/api/2/menu/by_id"
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
          { key: 'externalMenuId', label: 'ID внешнего меню *', required: true },
          { key: 'priceCategoryId', label: 'ID ценовой категории' },
        ]}
        onExecute={(body) => api.menu.externalMenuById(body)}
      />

      <ApiCard
        title="Стоп-лист"
        path="/api/1/stop_lists"
        description="Позиции, которых нет в наличии."
        fields={[
          { key: 'organizationIds', label: 'Организации *', type: 'org-multi', required: true },
        ]}
        onExecute={(body) => api.menu.stopLists(body)}
      />

      <ApiCard
        title="Проверить позицию в стоп-листе"
        path="/api/1/stop_lists/check"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'terminalGroupId', label: 'Терминальная группа *', type: 'terminal-select', required: true },
          { key: 'items', label: 'Позиции (JSON)', type: 'textarea', placeholder: '[{"productId": "uuid", "sizeId": null}]' },
        ]}
        onExecute={(body) => {
          if (body.items && typeof body.items === 'string') try { body.items = JSON.parse(body.items) } catch {}
          return api.menu.checkStopList(body)
        }}
      />

      <ApiCard
        title="Добавить в стоп-лист"
        path="/api/1/stop_lists/add"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'terminalGroupId', label: 'Терминальная группа *', type: 'terminal-select', required: true },
          { key: 'items', label: 'Позиции (JSON)', type: 'textarea', placeholder: '[{"productId": "uuid", "sizeId": null}]' },
        ]}
        onExecute={(body) => {
          if (body.items && typeof body.items === 'string') try { body.items = JSON.parse(body.items) } catch {}
          return api.menu.addToStopList(body)
        }}
      />

      <ApiCard
        title="Убрать из стоп-листа"
        path="/api/1/stop_lists/remove"
        fields={[
          { key: 'organizationId', label: 'Организация *', type: 'org-select', required: true },
          { key: 'terminalGroupId', label: 'Терминальная группа *', type: 'terminal-select', required: true },
          { key: 'items', label: 'Позиции (JSON)', type: 'textarea', placeholder: '[{"productId": "uuid", "sizeId": null}]' },
        ]}
        onExecute={(body) => {
          if (body.items && typeof body.items === 'string') try { body.items = JSON.parse(body.items) } catch {}
          return api.menu.removeFromStopList(body)
        }}
      />
    </div>
  )
}
