import { useState, useEffect } from 'react'
import JsonViewer from './JsonViewer'
import DataPreview from './DataPreview'
import { useIiko } from '../context/IikoContext'

const inp = {
  width: '100%', padding: '9px 12px',
  background: '#fff', border: '1px solid #d1d5db',
  borderRadius: '7px', fontSize: '14px', color: '#0f172a',
  outline: 'none', fontFamily: 'inherit',
}
const sel = { ...inp, cursor: 'pointer' }

function OrgSelect({ value, onChange }) {
  const { orgs } = useIiko()
  if (orgs.length === 0) return <p style={{ fontSize: '13px', color: '#94a3b8' }}>Загрузка организаций…</p>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {orgs.map(o => (
        <label key={o.id} style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '14px', color: '#1e293b', padding: '6px 10px', borderRadius: '6px', background: value === o.id ? '#eff6ff' : '#f8fafc', border: `1px solid ${value === o.id ? '#bfdbfe' : '#e2e8f0'}` }}>
          <input type="radio" name={`org-${o.id}`} checked={value === o.id} onChange={() => onChange(o.id)} style={{ accentColor: '#2563eb', width: '15px', height: '15px' }} />
          <span style={{ fontWeight: value === o.id ? 500 : 400 }}>{o.name}</span>
        </label>
      ))}
    </div>
  )
}

function OrgMultiSelect({ value, onChange }) {
  const { orgs } = useIiko()
  const selected = value ? value.split(',').map(s => s.trim()).filter(Boolean) : []
  const toggle = id => {
    const next = selected.includes(id) ? selected.filter(x => x !== id) : [...selected, id]
    onChange(next.join(', '))
  }
  if (orgs.length === 0) return <p style={{ fontSize: '13px', color: '#94a3b8' }}>Загрузка организаций…</p>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {orgs.map(o => (
        <label key={o.id} style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '14px', color: '#1e293b', padding: '6px 10px', borderRadius: '6px', background: selected.includes(o.id) ? '#eff6ff' : '#f8fafc', border: `1px solid ${selected.includes(o.id) ? '#bfdbfe' : '#e2e8f0'}` }}>
          <input type="checkbox" checked={selected.includes(o.id)} onChange={() => toggle(o.id)} style={{ accentColor: '#2563eb', width: '15px', height: '15px' }} />
          <span style={{ fontWeight: selected.includes(o.id) ? 500 : 400 }}>{o.name}</span>
        </label>
      ))}
    </div>
  )
}

function TerminalSelect({ orgId, value, onChange }) {
  const { terminalGroups, loadTerminals } = useIiko()
  useEffect(() => { if (orgId) loadTerminals(orgId) }, [orgId])
  const tgs = orgId ? (terminalGroups[orgId] ?? []) : []
  return (
    <select value={value} onChange={e => onChange(e.target.value)} style={sel}>
      <option value="">— выберите терминальную группу —</option>
      {tgs.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
      {orgId && tgs.length === 0 && <option disabled>Загрузка…</option>}
    </select>
  )
}

export default function ApiCard({ title, description, fields = [], onExecute, method = 'POST', path }) {
  const [open, setOpen] = useState(false)
  const [values, setValues] = useState(() => Object.fromEntries(fields.map(f => [f.key, f.default ?? ''])))
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const set = (key, val) => setValues(v => ({ ...v, [key]: val }))
  const orgField = fields.find(f => f.type === 'org-select')
  const selectedOrgId = orgField ? values[orgField.key] : ''

  const handle = async () => {
    setLoading(true); setResult(null); setError(null)
    try {
      const body = {}
      for (const f of fields) {
        const v = values[f.key]
        if (v === '' || v === null || v === undefined) continue
        if (f.type === 'org-multi' || f.type === 'array') body[f.key] = v.split(',').map(s => s.trim()).filter(Boolean)
        else if (f.type === 'textarea') { try { body[f.key] = JSON.parse(v) } catch { body[f.key] = v } }
        else if (f.type === 'number') body[f.key] = Number(v)
        else body[f.key] = v
      }
      setResult(await onExecute(body))
    } catch (e) { setError(e?.data ?? e) }
    finally { setLoading(false) }
  }

  return (
    <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '10px', marginBottom: '10px', overflow: 'hidden' }}>
      {/* Header */}
      <button
        onClick={() => setOpen(o => !o)}
        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '12px', padding: '14px 18px', background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left' }}
      >
        <span style={{ fontSize: '12px', fontWeight: 600, color: '#1d4ed8', background: '#dbeafe', padding: '3px 8px', borderRadius: '5px', fontFamily: 'monospace', flexShrink: 0 }}>{method}</span>
        <span style={{ fontSize: '13px', color: '#64748b', fontFamily: 'monospace', flexShrink: 0 }}>{path}</span>
        <span style={{ fontSize: '15px', fontWeight: 500, color: '#0f172a' }}>{title}</span>
        <span style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: '18px' }}>{open ? '▴' : '▾'}</span>
      </button>

      {open && (
        <div style={{ padding: '0 18px 20px', borderTop: '1px solid #f1f5f9' }}>
          {description && <p style={{ fontSize: '14px', color: '#64748b', margin: '14px 0 16px' }}>{description}</p>}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '16px', marginTop: description ? 0 : '16px' }}>
            {fields.map(f => (
              <div key={f.key}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: '#374151', marginBottom: '6px' }}>
                  {f.label ?? f.key}
                  {f.required && <span style={{ color: '#ef4444', marginLeft: '3px' }}>*</span>}
                  {f.hint && <span style={{ color: '#94a3b8', marginLeft: '8px', fontSize: '12px', fontWeight: 400 }}>{f.hint}</span>}
                </label>
                {f.type === 'org-select' ? <OrgSelect value={values[f.key]} onChange={v => set(f.key, v)} />
                  : f.type === 'org-multi' ? <OrgMultiSelect value={values[f.key]} onChange={v => set(f.key, v)} />
                  : f.type === 'terminal-select' ? <TerminalSelect orgId={selectedOrgId} value={values[f.key]} onChange={v => set(f.key, v)} />
                  : f.type === 'textarea' ? <textarea rows={4} value={values[f.key]} onChange={e => set(f.key, e.target.value)} placeholder={f.placeholder ?? ''} style={{ ...inp, fontFamily: 'monospace', fontSize: '13px', resize: 'vertical' }} />
                  : f.type === 'select' ? (
                    <select value={values[f.key]} onChange={e => set(f.key, e.target.value)} style={sel}>
                      {f.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  ) : (
                    <input type={f.type === 'number' ? 'number' : 'text'} value={values[f.key]} onChange={e => set(f.key, e.target.value)} placeholder={f.placeholder ?? ''} style={inp} />
                  )}
              </div>
            ))}
          </div>

          <button
            onClick={handle}
            disabled={loading}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '7px',
              padding: '9px 20px',
              background: loading ? '#e2e8f0' : '#2563eb',
              color: loading ? '#94a3b8' : '#fff',
              border: 'none', borderRadius: '7px',
              fontSize: '14px', fontWeight: 500,
              cursor: loading ? 'not-allowed' : 'pointer',
              marginBottom: '14px',
            }}
          >
            {loading ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" style={{ animation: 'spin 0.8s linear infinite' }}>
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                </svg>
                Выполняется…
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="5 3 19 12 5 21 5 3"/>
                </svg>
                Выполнить
              </>
            )}
          </button>

          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          <JsonViewer data={result} error={error} />
          {result && <DataPreview data={result} />}
        </div>
      )}
    </div>
  )
}
