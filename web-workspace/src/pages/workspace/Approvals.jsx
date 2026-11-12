import React, { useCallback, useEffect, useState } from 'react'
import { req, ApiError } from '../../api.js'
import { Card, Err, Empty, Json, StateBadge } from '../../shared/ui.jsx'
import { useForm } from '../../shared/useForm.js'

export function Approvals({ role }) {
  const [e, setE] = useState(null)
  const [list, setList] = useState([])
  const [onlyPending, setOnlyPending] = useState(true)
  const [det, setDet] = useState(null)
  const [f, setF, resetF] = useForm({ conversation_id: 'CNV-DEMO-1', tool_name: 'card_status_update', args: '{"card_id":"CARD-1","status":"BLOCKED"}', justification: 'Dugaan fraud, blokir sementara', risk_class: 'WRITE_MEDIUM' })
  const [dec, setDec] = useForm({ decision: 'GRANTED', comment: 'Setuju, argumen sesuai' })

  const load = useCallback(async () => {
    setE(null)
    try {
      const r = await req(`/v1/approvals${onlyPending ? '?state=pending' : ''}`, { role })
      setList(r.items || [])
    } catch (err) {
      setE(err)
    }
  }, [role, onlyPending])

  useEffect(() => { load() }, [load])

  const create = async () => {
    setE(null)
    try {
      const args = JSON.parse(f.args)
      const r = await req('/v1/approvals', { method: 'POST', role, body: { conversation_id: f.conversation_id, tool_name: f.tool_name, args, justification: f.justification, risk_class: f.risk_class } })
      setDet(r); resetF(); load()
    } catch (err) {
      setE(err instanceof SyntaxError ? new ApiError(0, '', 'Args harus JSON valid.') : err)
    }
  }

  const open = async (aid) => {
    setE(null)
    try {
      setDet(await req(`/v1/approvals/${aid}`, { role }))
    } catch (err) {
      setE(err)
    }
  }

  const decide = async () => {
    if (!det) return
    setE(null)
    try {
      const r = await req(`/v1/approvals/${det.approval_id}/decide`, { method: 'POST', role, body: dec })
      setDet(r); load()
    } catch (err) {
      setE(err)
    }
  }

  return (
    <>
      <Err e={e} onClose={() => setE(null)} />
      <div className="split">
        <Card title={`Daftar (${list.length})`} sub="RBAC-02: peminta tak boleh menyetujui sendiri.">
          <div className="row">
            <label className="check">
              <input type="checkbox" checked={onlyPending} onChange={(e) => setOnlyPending(e.target.checked)} /> Hanya pending
            </label>
            <button className="btn sm" onClick={load}>Muat ulang</button>
          </div>
          <div className="mt" style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead><tr><th>ID</th><th>Tool</th><th>Peminta</th><th>Keputusan</th></tr></thead>
              <tbody>
                {list.map((a) => (
                  <tr key={a.approval_id} className="clickable" onClick={() => open(a.approval_id)}>
                    <td style={{ fontSize: 11 }}>{a.approval_id}</td>
                    <td>{a.tool_name}</td>
                    <td>{a.requested_by}</td>
                    <td>{a.decision ? <StateBadge v={a.decision} /> : <span className="badge b-amber">PENDING</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!list.length && <Empty text="Tidak ada permintaan." />}
          </div>
        </Card>
        <div className="grid">
          <Card title="Minta persetujuan" sub="Gerbang tool tulis sensitif (FR-ORC-005).">
            <div className="form">
              <label>Percakapan<input value={f.conversation_id} onChange={setF('conversation_id')} /></label>
              <div className="form2">
                <label>Tool<input value={f.tool_name} onChange={setF('tool_name')} /></label>
                <label>Kelas risiko<input value={f.risk_class} onChange={setF('risk_class')} /></label>
              </div>
              <label>Args (JSON)<textarea value={f.args} onChange={setF('args')} rows={3} /></label>
              <label>Justifikasi<input value={f.justification} onChange={setF('justification')} /></label>
              <div className="row"><button className="btn primary" onClick={create}>Ajukan</button></div>
            </div>
          </Card>
          <Card title="Detail & keputusan" sub="Bandingkan hash argumen sebelum menyetujui (BR-ORC-07). Komentar wajib.">
            {!det ? <Empty text="Pilih permintaan di kiri." /> : (
              <div className="form">
                <div className="kv">
                  <dt>ID</dt><dd>{det.approval_id}</dd>
                  <dt>Tool</dt><dd>{det.tool_name}</dd>
                  <dt>Peminta</dt><dd>{det.requested_by}</dd>
                  <dt>Keputusan</dt><dd>{det.decision ? <StateBadge v={det.decision} /> : 'PENDING'}</dd>
                </div>
                <label>Hash argumen (sha256)<code className="hash">{det.arguments_hash}</code></label>
                <label>Snapshot argumen</label><Json data={det.arguments_snapshot} />
                <div className="form2">
                  <label>Keputusan<select value={dec.decision} onChange={setDec('decision')}><option>GRANTED</option><option>DENIED</option></select></label>
                </div>
                <label>Komentar (wajib)<input value={dec.comment} onChange={setDec('comment')} /></label>
                <div className="row"><button className="btn primary" onClick={decide}>Kirim keputusan</button></div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  )
}

export default Approvals
