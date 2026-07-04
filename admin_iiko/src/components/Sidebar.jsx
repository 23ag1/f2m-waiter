const NAV = [
  { id: 'organizations',   icon: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',  label: 'Организации' },
  { id: 'terminal_groups', icon: 'M20 3H4a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1zM8 17H5v-3h3v3zm0-5H5V9h3v3zm0-5H5V4h3v3zm5 10h-3v-3h3v3zm0-5h-3V9h3v3zm0-5h-3V4h3v3zm5 10h-3v-3h3v3zm0-5h-3V9h3v3zm0-5h-3V4h3v3z', label: 'Терминальные группы' },
  { id: 'menu',            icon: 'M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z', label: 'Меню / Стоп-лист' },
  { id: 'deliveries',      icon: 'M20 8h-3V4H3c-1.1 0-2 .9-2 2v11h2c0 1.66 1.34 3 3 3s3-1.34 3-3h6c0 1.66 1.34 3 3 3s3-1.34 3-3h2v-5l-3-4z', label: 'Доставки' },
  { id: 'orders',          icon: 'M7 4V2H5v2H3v2h2v2h2V6h2V4H7zm9 2h4l3 4v2h-2c0 1.1-.9 2-2 2s-2-.9-2-2H9c0 1.1-.9 2-2 2s-2-.9-2-2H3V6h5V4h8v2z', label: 'Заказы (зал)' },
  { id: 'customers',       icon: 'M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z', label: 'Клиенты' },
  { id: 'employees',       icon: 'M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z', label: 'Сотрудники' },
  { id: 'addresses',       icon: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z', label: 'Адреса' },
  { id: 'reserves',        icon: 'M19 3h-1V1h-2v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11z', label: 'Банкеты / Брони' },
  { id: 'loyalty',         icon: 'M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z', label: 'Лояльность' },
  { id: 'dictionaries',    icon: 'M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z', label: 'Справочники' },
  { id: 'webhooks',        icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z', label: 'Вебхуки' },
  { id: 'reports',         icon: 'M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z', label: 'Отчёты' },
]

function Icon({ d, size = 18, color }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color} style={{ flexShrink: 0 }}>
      <path d={d} />
    </svg>
  )
}

export default function Sidebar({ active, onSelect, apiLogin, onLogout }) {
  return (
    <aside style={{
      width: '232px', minWidth: '232px',
      height: '100vh',
      background: '#fff',
      borderRight: '1px solid #e2e8f0',
      display: 'flex', flexDirection: 'column',
      position: 'sticky', top: 0,
    }}>
      {/* Brand */}
      <div style={{ padding: '20px 16px 16px', borderBottom: '1px solid #f1f5f9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '34px', height: '34px',
            background: '#eff6ff', borderRadius: '8px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </div>
          <div style={{ overflow: 'hidden' }}>
            <div style={{ fontSize: '15px', fontWeight: 600, color: '#0f172a' }}>iiko Admin</div>
            <div style={{ fontSize: '12px', color: '#94a3b8', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {apiLogin}
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '10px 8px', overflowY: 'auto' }}>
        {NAV.map(item => {
          const isActive = active === item.id
          return (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              style={{
                width: '100%',
                display: 'flex', alignItems: 'center', gap: '9px',
                padding: '8px 10px',
                borderRadius: '7px', border: 'none',
                cursor: 'pointer',
                background: isActive ? '#eff6ff' : 'transparent',
                color: isActive ? '#2563eb' : '#475569',
                fontSize: '14px',
                fontWeight: isActive ? 500 : 400,
                textAlign: 'left',
                marginBottom: '1px',
              }}
            >
              <Icon d={item.icon} color={isActive ? '#2563eb' : '#94a3b8'} />
              {item.label}
            </button>
          )
        })}
      </nav>

      {/* Logout */}
      <div style={{ padding: '10px 8px', borderTop: '1px solid #f1f5f9' }}>
        <button
          onClick={onLogout}
          style={{
            width: '100%',
            display: 'flex', alignItems: 'center', gap: '9px',
            padding: '8px 10px',
            borderRadius: '7px', border: 'none',
            cursor: 'pointer', background: 'transparent',
            color: '#94a3b8', fontSize: '14px', textAlign: 'left',
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="#94a3b8" style={{ flexShrink: 0 }}>
            <path d="M10.09 15.59L11.5 17l5-5-5-5-1.41 1.41L12.67 11H3v2h9.67l-2.58 2.59zM19 3H5c-1.11 0-2 .9-2 2v4h2V5h14v14H5v-4H3v4c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/>
          </svg>
          Выйти
        </button>
      </div>
    </aside>
  )
}
