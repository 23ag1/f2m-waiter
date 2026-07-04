export default function JsonViewer({ data, error }) {
  if (!data && !error) return null
  if (error) {
    return (
      <div style={{
        background: '#fef2f2', border: '1px solid #fecaca',
        borderRadius: '8px', padding: '14px 16px',
        fontSize: '13px', fontFamily: 'monospace',
        color: '#b91c1c', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
        maxHeight: '300px', overflowY: 'auto',
      }}>
        {JSON.stringify(error, null, 2)}
      </div>
    )
  }
  return (
    <div className="json-viewer">
      {JSON.stringify(data, null, 2)}
    </div>
  )
}
