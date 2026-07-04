import { useState, useMemo } from 'react'

function flattenObj(obj) {
  const out = {}
  for (const [k, v] of Object.entries(obj ?? {})) {
    if (v === null || v === undefined) out[k] = ''
    else if (typeof v === 'object') out[k] = JSON.stringify(v)
    else out[k] = v
  }
  return out
}

function detectArrays(data) {
  if (!data || typeof data !== 'object') return []
  const result = []
  for (const [key, val] of Object.entries(data)) {
    if (Array.isArray(val) && val.length > 0 && typeof val[0] === 'object') {
      result.push({ key, count: val.length })
    }
  }
  return result
}

function toCSV(rows, columns) {
  const header = columns.join(';')
  const body = rows.map(row =>
    columns.map(col => {
      const v = String(row[col] ?? '')
      return v.includes(';') || v.includes('"') || v.includes('\n')
        ? `"${v.replace(/"/g, '""')}"`
        : v
    }).join(';')
  )
  return [header, ...body].join('\n')
}

function downloadCSV(csv, name) {
  const bom = '﻿'
  const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${name}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

const ROW_LIMIT = 300

export default function DataPreview({ data }) {
  const [open, setOpen] = useState(false)
  const [arrayKey, setArrayKey] = useState(null)
  const [hiddenCols, setHiddenCols] = useState(new Set())

  const arrays = useMemo(() => detectArrays(data), [data])
  if (arrays.length === 0) return null

  const activeKey = arrayKey ?? arrays[0].key

  const rawRows = useMemo(
    () => (data[activeKey] ?? []).map(flattenObj),
    [activeKey, data]
  )

  const allCols = useMemo(() => {
    const keys = new Set()
    rawRows.forEach(r => Object.keys(r).forEach(k => keys.add(k)))
    return [...keys]
  }, [rawRows])

  const visibleCols = allCols.filter(c => !hiddenCols.has(c))

  const toggleCol = (col) => {
    setHiddenCols(prev => {
      const next = new Set(prev)
      next.has(col) ? next.delete(col) : next.add(col)
      return next
    })
  }

  const openModal = () => {
    setHiddenCols(new Set())
    setOpen(true)
  }

  return (
    <>
      <button
        onClick={openModal}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: '7px',
          padding: '8px 16px',
          background: '#f0fdf4', color: '#15803d',
          border: '1px solid #bbf7d0', borderRadius: '7px',
          fontSize: '14px', fontWeight: 500, cursor: 'pointer',
          marginTop: '10px',
        }}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/>
        </svg>
        Предпросмотр таблицы
      </button>

      {open && (
        <div
          onClick={e => e.target === e.currentTarget && setOpen(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(15,23,42,0.4)',
            display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
            padding: '40px 24px',
            overflowY: 'auto',
          }}
        >
          <div style={{
            background: '#fff', borderRadius: '14px',
            border: '1px solid #e2e8f0',
            width: '100%', maxWidth: '1100px',
            minHeight: '400px',
          }}>
            {/* Modal header */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '18px 24px', borderBottom: '1px solid #f1f5f9',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <span style={{ fontSize: '16px', fontWeight: 600, color: '#0f172a' }}>Предпросмотр данных</span>
                {arrays.length > 1 && (
                  <select
                    value={activeKey}
                    onChange={e => { setArrayKey(e.target.value); setHiddenCols(new Set()) }}
                    style={{ padding: '5px 10px', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '13px', color: '#374151' }}
                  >
                    {arrays.map(a => (
                      <option key={a.key} value={a.key}>{a.key} ({a.count})</option>
                    ))}
                  </select>
                )}
                <span style={{ fontSize: '13px', color: '#64748b' }}>
                  {rawRows.length} строк · {visibleCols.length} из {allCols.length} колонок
                  {rawRows.length > ROW_LIMIT && <span style={{ color: '#f59e0b', marginLeft: '6px' }}>· показано первые {ROW_LIMIT}</span>}
                </span>
              </div>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <button
                  onClick={() => downloadCSV(toCSV(rawRows, visibleCols), activeKey)}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '6px',
                    padding: '7px 14px', background: '#2563eb', color: '#fff',
                    border: 'none', borderRadius: '7px', fontSize: '13px', fontWeight: 500, cursor: 'pointer',
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                  Скачать CSV
                </button>
                <button
                  onClick={() => setOpen(false)}
                  style={{ width: '32px', height: '32px', background: '#f1f5f9', border: 'none', borderRadius: '7px', cursor: 'pointer', fontSize: '18px', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >
                  ×
                </button>
              </div>
            </div>

            {/* Column toggles */}
            <div style={{
              padding: '12px 24px', borderBottom: '1px solid #f1f5f9',
              display: 'flex', flexWrap: 'wrap', gap: '8px', maxHeight: '120px', overflowY: 'auto',
            }}>
              {allCols.map(col => {
                const visible = !hiddenCols.has(col)
                return (
                  <label
                    key={col}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: '5px',
                      padding: '4px 10px', borderRadius: '20px', cursor: 'pointer',
                      fontSize: '12px', fontWeight: 500,
                      background: visible ? '#eff6ff' : '#f8fafc',
                      color: visible ? '#1d4ed8' : '#94a3b8',
                      border: `1px solid ${visible ? '#bfdbfe' : '#e2e8f0'}`,
                      userSelect: 'none',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={visible}
                      onChange={() => toggleCol(col)}
                      style={{ accentColor: '#2563eb', width: '12px', height: '12px' }}
                    />
                    {col}
                  </label>
                )
              })}
            </div>

            {/* Table */}
            <div style={{ overflowX: 'auto', maxHeight: '60vh', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', position: 'sticky', top: 0 }}>
                    {visibleCols.map(col => (
                      <th key={col} style={{
                        padding: '10px 14px', textAlign: 'left',
                        borderBottom: '1px solid #e2e8f0',
                        color: '#374151', fontWeight: 600,
                        whiteSpace: 'nowrap', fontSize: '12px',
                      }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rawRows.slice(0, ROW_LIMIT).map((row, i) => (
                    <tr
                      key={i}
                      style={{ borderBottom: '1px solid #f1f5f9', background: i % 2 === 0 ? '#fff' : '#fafafa' }}
                    >
                      {visibleCols.map(col => (
                        <td key={col} style={{
                          padding: '9px 14px', color: '#1e293b',
                          maxWidth: '260px', overflow: 'hidden',
                          textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}
                          title={String(row[col] ?? '')}
                        >
                          {row[col] === true ? '✓' : row[col] === false ? '—' : (row[col] ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
