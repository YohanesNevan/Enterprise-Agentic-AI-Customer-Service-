import React from 'react'

export function StatePanel({ title, children }) {
  return (
    <section className="state-panel" role="status">
      <h2>{title}</h2>
      <p>{children}</p>
    </section>
  )
}

export function Card({ title, sub, children, wide }) {
  return (
    <div className="card" style={wide ? { gridColumn: '1 / -1' } : undefined}>
      {title && <h3>{title}</h3>}
      {sub && <p className="sub">{sub}</p>}
      {children}
    </div>
  )
}

export function Err({ e, onClose }) {
  if (!e) return null
  return (
    <p className="alert err">
      {e.message || String(e)}
      {onClose && (
        <button className="btn sm" style={{ marginLeft: 10 }} onClick={onClose}>
          Tutup
        </button>
      )}
    </p>
  )
}

export function Empty({ text }) {
  return <div className="empty">{text}</div>
}

export function Json({ data }) {
  return <pre className="dump">{JSON.stringify(data, null, 2)}</pre>
}

export function Sev({ v }) {
  const cls = v === 'CRITICAL' ? 'b-red' : v === 'HIGH' ? 'b-amber' : v === 'MEDIUM' ? 'b-blue' : 'b-green'
  return <span className={`badge ${cls}`}>{v || '-'}</span>
}

export function StateBadge({ v }) {
  const s = String(v || '')
  const cls = /CLOSED|SENT|ACCEPTED|GRANTED/.test(s) ? 'b-green'
    : /BREACHED|DENIED|OPEN|QUEUED|PENDING|RUNNING|AT_RISK/.test(s) ? 'b-amber'
    : /REOPENED|REJECT|FAIL|BLOCK/.test(s) ? 'b-red' : 'b-gray'
  return <span className={`badge ${cls}`}>{s || '-'}</span>
}
