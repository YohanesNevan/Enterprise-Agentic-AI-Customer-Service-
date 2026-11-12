import React, { useCallback, useEffect, useState } from 'react'
import { req, SEVERITIES } from '../../api.js'
import { Card, Err, Json } from '../../shared/ui.jsx'
import { useForm } from '../../shared/useForm.js'

export function SLA({ role }) {
  const [e, setE] = useState(null)
  const [out, setOut] = useState(null)
  const [st, setSt] = useState(null)
  const [f, setF] = useForm({ object_type: 'CASE', category: 'TRANSACTION_DISPUTE', severity: 'HIGH', created_at: '2026-03-06T09:30:00+00:00' })
  const [nt, setNt] = useForm({ channel: 'REGISTERED_EMAIL', target: 'nasabah@example.test' })

  const status = useCallback(async () => {
    try { setSt(await req('/internal/outbox-status', { role })) } catch { /* abaikan */ }
  }, [role])

  useEffect(() => { status() }, [status])

  const calc = async () => { setE(null); try { setOut(await req('/v1/sla/calculate', { method: 'POST', role, body: f })) } catch (err) { setE(err) } }
  const tick = async () => { setE(null); try { setOut(await req('/internal/sla-tick', { method: 'POST', role })); status() } catch (err) { setE(err) } }
  const drain = async () => { setE(null); try { setOut(await req('/internal/outbox-drain', { method: 'POST', role })); status() } catch (err) { setE(err) } }
  const notify = async () => { setE(null); try { setOut(await req('/v1/notifications', { method: 'POST', role, body: { ...nt } })) } catch (err) { setE(err) } }

  return (
    <>
      <Err e={e} onClose={() => setE(null)} />
      {st && (
        <div className="grid g2">
          <Card><div className="stat"><span className="v">{st.pending}</span><span className="l">Notifikasi Outbox Pending</span></div></Card>
          <Card><div className="stat"><span className="v">{st.sent}</span><span className="l">Notifikasi Terkirim</span></div></Card>
        </div>
      )}
      {out && <Card title="Hasil Operasi"><Json data={out} /></Card>}
      <div className="grid g3 mt">
        <Card title="Hitung Batas SLA" sub="Kalkulasi jam kerja operasional; Jumat sore → Senin.">
          <div className="form">
            <div className="form2">
              <label>Objek Layanan<select value={f.object_type} onChange={setF('object_type')}><option>CASE</option><option>TICKET</option></select></label>
              <label>Severity<select value={f.severity} onChange={setF('severity')}>{SEVERITIES.map((o) => <option key={o}>{o}</option>)}</select></label>
            </div>
            <label>Kategori Masalah<input value={f.category} onChange={setF('category')} placeholder="TRANSACTION_DISPUTE" /></label>
            <label>Waktu Masuk (ISO Timestamp)<input value={f.created_at} onChange={setF('created_at')} /></label>
            <div className="row"><button className="btn primary" onClick={calc}>Hitung Batas Waktu SLA</button></div>
          </div>
        </Card>
        <Card title="Pemantauan SLA & Outbox" sub="Pemeriksaan status keterlambatan (Breach) dan pengiriman notifikasi.">
          <div className="row">
            <button className="btn primary" onClick={tick}>Jalankan Pemeriksaan SLA</button>
            <button className="btn" onClick={drain}>Kirim Antrean Notifikasi</button>
            <button className="btn sm" onClick={status}>Cek Status Outbox</button>
          </div>
        </Card>
        <Card title="Kirim Notifikasi Langsung" sub="Pengiriman pesan ke kanal resmi terdaftar nasabah.">
          <div className="form">
            <label>Kanal Notifikasi<select value={nt.channel} onChange={setNt('channel')}>{['REGISTERED_EMAIL', 'REGISTERED_SMS', 'REGISTERED_PUSH', 'REGISTERED_WHATSAPP'].map((o) => <option key={o}>{o}</option>)}</select></label>
            <label>Tujuan Kontak<input value={nt.target} onChange={setNt('target')} placeholder="nasabah@example.test" /></label>
            <div className="row"><button className="btn primary" onClick={notify}>Kirim Notifikasi</button></div>
          </div>
        </Card>
      </div>
    </>
  )
}

export default SLA
