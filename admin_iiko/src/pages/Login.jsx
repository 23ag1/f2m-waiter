import { useState } from 'react'
import { getAccessToken, saveCredentials } from '../api/client'

export default function Login({ onSuccess }) {
  const [apiLogin, setApiLogin] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!apiLogin.trim()) return
    setLoading(true)
    setError('')
    try {
      const data = await getAccessToken(apiLogin.trim(), clientSecret.trim())
      saveCredentials(apiLogin.trim(), data.token)
      onSuccess()
    } catch (err) {
      setError(err?.data?.errorDescription ?? err?.data?.description ?? 'Ошибка авторизации')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: '#f0f4f8',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}>
      <div style={{
        width: '440px',
        background: '#fff',
        borderRadius: '16px',
        border: '1px solid #e2e8f0',
        padding: '48px 40px',
      }}>
        <div style={{ marginBottom: '32px' }}>
          <div style={{
            width: '48px', height: '48px',
            background: '#eff6ff',
            borderRadius: '12px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: '20px',
          }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
          </div>
          <h1 style={{ fontSize: '22px', fontWeight: 600, color: '#0f172a', marginBottom: '6px' }}>iiko Admin Panel</h1>
          <p style={{ fontSize: '15px', color: '#64748b' }}>Введите API Login для подключения к iikoCloud</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#374151', marginBottom: '6px' }}>
              API Login
            </label>
            <input
              type="text"
              value={apiLogin}
              onChange={e => setApiLogin(e.target.value)}
              placeholder="your-api-login"
              autoFocus
              style={{
                width: '100%', padding: '10px 14px',
                background: '#fff', border: '1px solid #d1d5db',
                borderRadius: '8px', fontSize: '15px', color: '#0f172a',
                outline: 'none', fontFamily: 'monospace',
                transition: 'border-color 0.15s',
              }}
              onFocus={e => e.target.style.borderColor = '#2563eb'}
              onBlur={e => e.target.style.borderColor = '#d1d5db'}
            />
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, color: '#374151', marginBottom: '6px' }}>
              Client Secret
              <span style={{ marginLeft: '8px', fontSize: '13px', color: '#94a3b8', fontWeight: 400 }}>только для v2 ключей</span>
            </label>
            <input
              type="password"
              value={clientSecret}
              onChange={e => setClientSecret(e.target.value)}
              placeholder="оставьте пустым для v1"
              style={{
                width: '100%', padding: '10px 14px',
                background: '#fff', border: '1px solid #d1d5db',
                borderRadius: '8px', fontSize: '15px', color: '#0f172a',
                outline: 'none',
                transition: 'border-color 0.15s',
              }}
              onFocus={e => e.target.style.borderColor = '#2563eb'}
              onBlur={e => e.target.style.borderColor = '#d1d5db'}
            />
          </div>

          {error && (
            <div style={{
              padding: '12px 14px', background: '#fef2f2',
              border: '1px solid #fecaca', borderRadius: '8px',
              fontSize: '14px', color: '#b91c1c', marginBottom: '16px',
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !apiLogin.trim()}
            style={{
              width: '100%', padding: '11px',
              background: loading || !apiLogin.trim() ? '#e2e8f0' : '#2563eb',
              color: loading || !apiLogin.trim() ? '#94a3b8' : '#fff',
              border: 'none', borderRadius: '8px',
              fontSize: '15px', fontWeight: 500,
              cursor: loading || !apiLogin.trim() ? 'not-allowed' : 'pointer',
              transition: 'background 0.15s',
            }}
          >
            {loading ? 'Подключение…' : 'Войти'}
          </button>
        </form>

        <p style={{ textAlign: 'center', fontSize: '13px', color: '#94a3b8', marginTop: '24px' }}>
          api-ru.iiko.services
        </p>
      </div>
    </div>
  )
}
