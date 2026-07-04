const BASE = '/iiko'

function getToken() {
  return localStorage.getItem('iiko_token')
}

export function getStoredApiLogin() {
  return localStorage.getItem('iiko_api_login') || ''
}

export function saveCredentials(apiLogin, token) {
  localStorage.setItem('iiko_api_login', apiLogin)
  localStorage.setItem('iiko_token', token)
}

export function clearCredentials() {
  localStorage.removeItem('iiko_api_login')
  localStorage.removeItem('iiko_token')
}

export function isAuthenticated() {
  return !!getToken()
}

async function request(path, body = {}, extraHeaders = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...extraHeaders,
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })

  const text = await res.text()
  let data
  try {
    data = JSON.parse(text)
  } catch {
    data = { raw: text }
  }

  if (!res.ok) {
    throw { status: res.status, data }
  }
  return data
}

// Auth — tries v1 first; if server says use v2, retries with clientSecret
export async function getAccessToken(apiLogin, clientSecret = '') {
  const v1 = await fetch(`${BASE}/api/1/access_token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ apiLogin }),
  })
  const d1 = await v1.json()
  if (v1.ok) return d1

  const msg = d1?.errorDescription ?? d1?.description ?? ''
  if (!msg.includes('/api/v2/access_token')) throw { status: v1.status, data: d1 }

  // v2 requires clientSecret
  const body = { apiLogin, clientSecret }
  const v2 = await fetch(`${BASE}/api/v2/access_token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const d2 = await v2.json()
  if (v2.ok) return d2
  throw { status: v2.status, data: d2 }
}

// Organizations
export const api = {
  organizations: {
    list: (body = {}) => request('/api/1/organizations', body),
    settings: (body) => request('/api/1/organizations/settings', body),
  },
  terminalGroups: {
    list: (body) => request('/api/1/terminal_groups', body),
    isAlive: (body) => request('/api/1/terminal_groups/is_alive', body),
    awake: (body) => request('/api/1/terminal_groups/awake', body),
  },
  menu: {
    nomenclature: (body) => request('/api/1/nomenclature', body),
    externalMenus: (body) => request('/api/2/menu', body),
    externalMenuById: (body) => request('/api/2/menu/by_id', body),
    stopLists: (body) => request('/api/1/stop_lists', body),
    checkStopList: (body) => request('/api/1/stop_lists/check', body),
    addToStopList: (body) => request('/api/1/stop_lists/add', body),
    removeFromStopList: (body) => request('/api/1/stop_lists/remove', body),
    clearStopList: (body) => request('/api/1/stop_lists/clear', body),
    combos: (body) => request('/api/1/combo', body),
    calculateCombo: (body) => request('/api/1/combo/calculate', body),
  },
  deliveries: {
    create: (body) => request('/api/1/deliveries/create', body),
    byId: (body) => request('/api/1/deliveries/by_id', body),
    byDateAndStatus: (body) => request('/api/1/deliveries/by_delivery_date_and_status', body),
    byRevision: (body) => request('/api/1/deliveries/by_revision', body),
    byPhone: (body) => request('/api/1/deliveries/by_delivery_date_and_phone', body),
    cancel: (body) => request('/api/1/deliveries/cancel', body),
    close: (body) => request('/api/1/deliveries/close', body),
    confirm: (body) => request('/api/1/deliveries/confirm', body),
    updateStatus: (body) => request('/api/1/deliveries/update_order_delivery_status', body),
    updateCourier: (body) => request('/api/1/deliveries/update_order_courier', body),
    addItems: (body) => request('/api/1/deliveries/add_items', body),
    addPayments: (body) => request('/api/1/deliveries/add_payments', body),
    changeComment: (body) => request('/api/1/deliveries/change_comment', body),
  },
  orders: {
    create: (body) => request('/api/1/order/create', body),
    byId: (body) => request('/api/1/order/by_id', body),
    byTable: (body) => request('/api/1/order/by_table', body),
    addItems: (body) => request('/api/1/order/add_items', body),
    close: (body) => request('/api/1/order/close', body),
    cancel: (body) => request('/api/1/order/cancel', body),
    addPayments: (body) => request('/api/1/order/add_payments', body),
  },
  customers: {
    info: (body) => request('/api/1/loyalty/iiko/customer/info', body),
    createOrUpdate: (body) => request('/api/1/loyalty/iiko/customer/create_or_update', body),
    delete: (body) => request('/api/1/loyalty/iiko/delete_customers', body),
    addCard: (body) => request('/api/1/loyalty/iiko/customer/card/add', body),
    removeCard: (body) => request('/api/1/loyalty/iiko/customer/card/remove', body),
    topupWallet: (body) => request('/api/1/loyalty/iiko/customer/wallet/topup', body),
    chargeoffWallet: (body) => request('/api/1/loyalty/iiko/customer/wallet/chargeoff', body),
    transactionsByDate: (body) => request('/api/1/loyalty/iiko/customer/transactions/by_date', body),
  },
  employees: {
    couriers: (body) => request('/api/1/employees/couriers', body),
    info: (body) => request('/api/1/employees/info', body),
    activeLocations: (body) => request('/api/1/employees/couriers/active_location', body),
  },
  dictionaries: {
    cancelCauses: (body) => request('/api/1/cancel_causes', body),
    orderTypes: (body) => request('/api/1/deliveries/order_types', body),
    discounts: (body) => request('/api/1/discounts', body),
    paymentTypes: (body) => request('/api/1/payment_types', body),
  },
  addresses: {
    regions: (body) => request('/api/1/regions', body),
    cities: (body) => request('/api/1/cities', body),
    streets: (body) => request('/api/1/streets/by_city', body),
  },
  webhooks: {
    settings: (body) => request('/api/1/webhooks/settings', body),
    updateSettings: (body) => request('/api/1/webhooks/update_settings', body),
  },
  loyalty: {
    programs: (body) => request('/api/1/loyalty/iiko/program', body),
    calculate: (body) => request('/api/1/loyalty/iiko/calculate', body),
    manualConditions: (body) => request('/api/1/loyalty/iiko/manual_condition', body),
  },
}
