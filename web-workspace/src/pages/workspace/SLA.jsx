import React, { useCallback, useEffect, useState } from 'react'
import { req, SEVERITIES } from '../../api.js'
import { Card, Err, Json, StateBadge } from '../../shared/ui.jsx'
import { useForm } from '../../shared/useForm.js'

export function SLA({ role }) {
  const [e, setE] = useState(null)
  const [out, setOut] = useState(null)
  const [st, setSt] = useState(null)
  const [records, setRecords] = useState([])
  const [loadingRecords, setLoadingRecords] = useState(false)
  const [f, setF] = useForm({ object_type: 'CASE', category: 'TRANSACTION_DISPUTE', severity: 'HIGH', created_at: '2026-03-06T09:30:00+00:00' })
  const [nt, setNt] = useForm({ channel: 'REGISTERED_EMAIL', target: 'nasabah@example.test' })

  const loadSlaData = useCallback(async () => {
    try { setSt(await req('/internal/outbox-status', { role })) } catch { /* abaikan */ }
    setLoadingRecords(true)
    try {
      const rList = await req('/v1/workspace/sla/records', { role })
      setRecords(Array.isArray(rList?.items) ? rList.items : [])
    } catch {
      // ignore
    } finally {
      setLoadingRecords(false)
    }
  }, [role])

  useEffect(() => { loadSlaData() }, [loadSlaData])

  const calc = async () => { setE(null); try { setOut(await req('/v1/sla/calculate', { method: 'POST', role, body: f })) } catch (err) { setE(err) } }
  const tick = async () => { setE(null); try { setOut(await req('/internal/sla-tick', { method: 'POST', role })); loadSlaData() } catch (err) { setE(err) } }
  const drain = async () => { setE(null); try { setOut(await req('/internal/outbox-drain', { method: 'POST', role })); loadSlaData() } catch (err) { setE(err) } }
  const notify = async () => { setE(null); try { setOut(await req('/v1/notifications', { method: 'POST', role, body: { ...nt } })) } catch (err) { setE(err) } }

  return (
    <>
      <Err e={e} onClose={() => setE(null)} />
      {st && (
        <div className="grid g3">
          <Card><div className="stat"><span className="v">{records.filter(r => r.is_breached).length}</span><span className="l" style={{ color: '#b42318' }}>SLA Terlanggar (Breached)</span></div></Card>
          <Card><div className="stat"><span className="v">{records.filter(r => r.is_at_risk).length}</span><span className="l" style={{ color: '#b54708' }}>Mendekati Batas (At-Risk &lt; 2 Jam)</span></div></Card>
          <Card><div className="stat"><span className="v">{st.pending}</span><span className="l">Notifikasi Outbox Pending</span></div></Card>
        </div>
      )}

      {/* Live SLA Records Table */}
      <Card title="Monitoring Komitmen Waktu Layanan (Live SLA Tracking)" sub="Pemantauan tenggat waktu respon awal dan penyelesaian tiket/kasus nasabah." wide className="mt">
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
          <button className="btn sm" onClick={loadSlaData} disabled={loadingRecords}>
            {loadingRecords ? 'Memuat...' : '↻ Segarkan SLA'}
          </button>
        </div>
        {records.length === 0 ? (
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Belum ada catatan SLA aktif.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '8px' }}>ID Objek</th>
                  <th style={{ padding: '8px' }}>Tipe</th>
                  <th style={{ padding: '8px' }}>Status SLA</th>
                  <th style={{ padding: '8px' }}>Mulai Masuk</th>
                  <th style={{ padding: '8px' }}>Batas Penyelesaian</th>
                  <th style={{ padding: '8px' }}>Sisa Waktu</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.sla_id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px', fontWeight: 600 }}>{r.object_id}</td>
                    <td style={{ padding: '8px' }}>{r.object_type}</td>
                    <td style={{ padding: '8px' }}>
                      {r.is_breached ? (
                        <span style={{ background: '#fef3f2', color: '#b42318', padding: '3px 8px', borderRadius: 4, fontWeight: 600 }}>
                          BREACHED (Terlambat)
                        </span>
                      ) : r.is_at_risk ? (
                        <span style={{ background: '#fffaeb', color: '#b54708', padding: '3px 8px', borderRadius: 4, fontWeight: 600 }}>
                          AT RISK (&lt; 2 Jam)
                        </span>
                      ) : r.state === 'MET' ? (
                        <span style={{ background: '#ecfdf3', color: '#027a48', padding: '3px 8px', borderRadius: 4 }}>
                          TERPENUHI (MET)
                        </span>
                      ) : (
                        <span style={{ background: '#f2f4f7', color: 'var(--text-primary)', padding: '3px 8px', borderRadius: 4 }}>
                          {r.state}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '8px', color: 'var(--text-secondary)' }}>
                      {r.started_at ? new Date(r.started_at).toLocaleString('id-ID') : '-'}
                    </td>
                    <td style={{ padding: '8px', color: 'var(--text-secondary)' }}>
                      {r.resolution_due_at ? new Date(r.resolution_due_at).toLocaleString('id-ID') : '-'}
                    </td>
                    <td style={{ padding: '8px', fontWeight: 600 }}>
                      {r.state === 'MET' ? '-' : r.is_breached ? (
                        <span style={{ color: '#b42318' }}>Terlambat {Math.abs(r.remaining_minutes)} mnt</span>
                      ) : (
                        <span style={{ color: '#027a48' }}>{Math.floor(r.remaining_minutes / 60)}j {r.remaining_minutes % 60}m</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {out && <Card title="Hasil Operasi" className="mt"><Json data={out} /></Card>}
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
            <button className="btn sm" onClick={loadSlaData}>Cek Status Outbox</button>
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
