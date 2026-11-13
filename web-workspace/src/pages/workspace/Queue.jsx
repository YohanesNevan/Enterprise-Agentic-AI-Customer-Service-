import React, { useCallback, useEffect, useState } from 'react'
import { REASONS, SEVERITIES, req } from '../../api.js'
import { navigate } from '../../shared/navigation.js'
import { useForm } from '../../shared/useForm.js'
import { Card, Empty, Err, Json, Sev } from '../../shared/ui.jsx'

export default function Queue({ role }) {
  const [items, setItems] = useState([])
  const [e, setE] = useState(null)
  const [sel, setSel] = useState(null)
  const [filter, setFilter] = useState({ queue_id: '', skills: '' })
  const [f, setF, resetF] = useForm({ conversation_id: 'CNV-DEMO-1', reason_code: 'CUSTOMER_REQUEST', severity: 'MEDIUM', queue_id: 'Q-GENERAL', skill_tags: '', vulnerability_flag: false, package_complete: true })
  const [t, setT] = useForm({ to_queue: 'Q-GENERAL', reason: '', note: '' })
  const [ho, setHo] = useState(null)

  const load = useCallback(async () => {
    setE(null)
    try {
      const q = new URLSearchParams()
      if (filter.queue_id) q.set('queue_id', filter.queue_id)
      if (filter.skills) q.set('skills', filter.skills)
      const r = await req(`/v1/workspace/queue${q.toString() ? `?${q}` : ''}`, { role })
      setItems(r.items || [])
    } catch (err) { setE(err) }
  }, [role, filter.queue_id, filter.skills])
  useEffect(() => { load(); const tmr = setInterval(load, 8000); return () => clearInterval(tmr) }, [load])

  const enqueue = async () => {
    setE(null)
    try {
      const r = await req('/v1/workspace/queue/enqueue', {
        method: 'POST', role,
        body: {
          conversation_id: f.conversation_id, reason_code: f.reason_code, severity: f.severity,
          queue_id: f.queue_id, skill_tags: f.skill_tags.split(',').map((s) => s.trim()).filter(Boolean),
          vulnerability_flag: f.vulnerability_flag, package_complete: f.package_complete,
        },
      })
      setHo({ ok: true, data: r }); resetF(); load()
    } catch (err) { setE(err) }
  }
  const accept = async (it) => {
    setE(null)
    try {
      await req(`/v1/workspace/handoffs/${it.handoff_id}/accept`, { method: 'POST', role, body: {} })
      setSel(null)
      navigate(`/agent/conversations?cid=${encodeURIComponent(it.conversation_id)}`)
    } catch (err) { setE(err) }
  }
  const transfer = async () => {
    if (!sel) return
    setE(null)
    try {
      const r = await req(`/v1/workspace/handoffs/${sel.handoff_id}/transfer`, { method: 'POST', role, body: t })
      setHo({ ok: true, data: r }); load()
    } catch (err) { setE(err) }
  }
  const quickHandoff = async () => {
    setE(null)
    try {
      const r = await req('/v1/handoffs', { method: 'POST', role, body: { conversation_id: f.conversation_id, reason_code: f.reason_code, recent_turns: [] } })
      setHo({ ok: true, data: r })
    } catch (err) { setE(err) }
  }

  return (
    <>
      <Err e={e} onClose={() => setE(null)} />
      <div className="split">
        <Card title={`Antrean Layanan Petugas (Queue: ${items.length})`} sub="Diurutkan otomatis berdasarkan skor prioritas; auto-refresh berkala setiap 8 detik.">
          <div className="row">
            <input placeholder="Filter Queue ID (cth: Q-GENERAL)" value={filter.queue_id} onChange={(e) => setFilter({ ...filter, queue_id: e.target.value })} style={{ width: 180 }} />
            <input placeholder="Filter Skill Tags (cth: chat, id)" value={filter.skills} onChange={(e) => setFilter({ ...filter, skills: e.target.value })} style={{ width: 180 }} />
            <button className="btn sm" onClick={load}>Refresh Data</button>
          </div>
          <div className="mt" style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead><tr><th>Percakapan</th><th>Alasan & Intensi</th><th>Severity</th><th>Skor Prioritas</th><th>Waktu Tunggu</th><th>Queue / Status Paket</th><th>Tindakan</th></tr></thead>
              <tbody>
                {items.map((q) => (
                  <tr key={q.handoff_id} className={`clickable${sel?.handoff_id === q.handoff_id ? ' sel' : ''}`} onClick={() => { setSel(q); setT((o) => ({ ...o })) }}>
                    <td><b>{q.conversation_id}</b><br /><span style={{ fontSize: 11, color: '#64748b' }}>{q.handoff_id}</span></td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{q.reason_code}</div>
                      {q.intent_code && <div style={{ fontSize: 11, color: '#2563eb' }}>{q.intent_code}</div>}
                      {q.summary_snippet && <div style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic', maxWidth: 220, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>"{q.summary_snippet}"</div>}
                    </td>
                    <td><Sev v={q.severity} /></td>
                    <td><b>{q.priority_score}</b></td>
                    <td>{q.wait_s}s</td>
                    <td>
                      {q.queue_id}
                      <div style={{ marginTop: 2 }}>
                        {q.package_complete ? <span className="badge b-green" style={{ fontSize: 10 }}>PAKET LENGKAP</span> : <span className="badge b-amber" style={{ fontSize: 10 }}>PARSIAL</span>}
                      </div>
                    </td>
                    <td><button className="btn sm primary" onClick={(ev) => { ev.stopPropagation(); accept(q) }}>Terima Handoff</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!items.length && <Empty text="Antrean saat ini kosong — belum ada eskalasi baru dari nasabah." />}
          </div>
        </Card>
        <div className="grid">
          <Card title="Tambah ke Antrean (Manual Enqueue)" sub="Eskalasikan percakapan nasabah ke antrean penanganan petugas.">
            <div className="form">
              <label>ID Percakapan<input value={f.conversation_id} onChange={setF('conversation_id')} placeholder="CNV-..." /></label>
              <div className="form2">
                <label>Alasan Eskalasi<select value={f.reason_code} onChange={setF('reason_code')}>{REASONS.map((r) => <option key={r}>{r}</option>)}</select></label>
                <label>Tingkat Severity<select value={f.severity} onChange={setF('severity')}>{SEVERITIES.map((r) => <option key={r}>{r}</option>)}</select></label>
              </div>
              <div className="form2">
                <label>Nama Queue<input value={f.queue_id} onChange={setF('queue_id')} placeholder="Q-GENERAL" /></label>
                <label>Tag Keahlian (Skill Tags)<input value={f.skill_tags} onChange={setF('skill_tags')} placeholder="chat, id, dispute" /></label>
              </div>
              <label className="check"><input type="checkbox" checked={f.vulnerability_flag} onChange={setF('vulnerability_flag')} /> Nasabah prioritas / rentan (Tingkatkan bobot SLA)</label>
              <label className="check"><input type="checkbox" checked={f.package_complete} onChange={setF('package_complete')} /> Paket konteks handoff lengkap</label>
              <div className="row"><button className="btn primary" onClick={enqueue}>Daftarkan ke Antrean</button>
                <button className="btn" onClick={quickHandoff} title="Verifikasi integritas payload paket handoff">Cek Paket Handoff</button></div>
            </div>
          </Card>
          <Card title="Transfer Antrean (Alihkan ke Tim Lain)" sub="Pindahkan penanganan ke tim spesialis lain dengan catatan pendukung.">
            {!sel ? <Empty text="Pilih salah satu baris antrean di sebelah kiri terlebih dahulu." /> : (
              <div className="form">
                <div className="kv"><dt>Handoff ID</dt><dd>{sel.handoff_id}</dd><dt>Percakapan</dt><dd>{sel.conversation_id}</dd></div>
                <label>Target Antrean (Queue)<input value={t.to_queue} onChange={setT('to_queue')} placeholder="Q-FRAUD / Q-SPECIALIST" /></label>
                <label>Alasan Pengalihan<input value={t.reason} onChange={setT('reason')} placeholder="Memerlukan penanganan spesialis" /></label>
                <label>Catatan Internal (Wajib diisi)<textarea value={t.note} onChange={setT('note')} rows={2} placeholder="Jelaskan kronologi dan konteks untuk petugas penerima..." /></label>
                <div className="row"><button className="btn primary" onClick={transfer}>Kirim Pengalihan</button></div>
              </div>
            )}
          </Card>
          {ho && <Card title="Status Operasi" sub={ho.ok ? 'Berhasil' : 'Informasi'}><Json data={ho.data} /></Card>}
        </div>
      </div>
    </>
  )
}
