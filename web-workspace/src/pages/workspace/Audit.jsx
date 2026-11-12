import React, { useState } from 'react'
import { req } from '../../api.js'
import { Card, Err, Empty, Json } from '../../shared/ui.jsx'

export function Audit({ role }) {
  const [corr, setCorr] = useState('')
  const [trail, setTrail] = useState(null)
  const [e, setE] = useState(null)

  const open = async () => {
    setE(null)
    setTrail(null)
    try {
      const r = await req(`/v1/audit/trail/${corr}`, { role })
      setTrail(r.trail || [])
    } catch (err) {
      setE(err)
    }
  }

  return (
    <>
      <p className="alert info">Hanya dapat diakses oleh peran <b>supervisor</b> (izin audit.read). Setiap respons API menyertakan Correlation ID pada header.</p>
      <Err e={e} onClose={() => setE(null)} />
      <Card title="Lacak Correlation ID" sub="Audit Trail berbasis append-only dan hash-chain untuk kepatuhan perbankan.">
        <div className="row">
          <input value={corr} onChange={(e) => setCorr(e.target.value)} placeholder="Contoh: COR-..." style={{ minWidth: 300 }} />
          <button className="btn primary" onClick={open}>Lacak Jejak Audit</button>
        </div>
      </Card>
      {trail && (
        <Card title={`Jejak Audit Trail (${trail.length} Riwayat Kejadian)`}>
          {!trail.length ? (
            <Empty text="Tidak ada riwayat kejadian untuk Correlation ID ini." />
          ) : (
            <ul className="timeline">
              {trail.map((t, i) => (
                <li key={i}>
                  <b>{t.action || t.event || JSON.stringify(t).slice(0, 80)}</b>
                  <div className="t">{t.timestamp || t.ts || t.created_at || ''} • {t.actor_id || t.actor || ''} • {t.service || ''}</div>
                </li>
              ))}
            </ul>
          )}
          <h3 className="mt">Detail Payload Mentah</h3>
          <Json data={trail} />
        </Card>
      )}
    </>
  )
}

export default Audit
