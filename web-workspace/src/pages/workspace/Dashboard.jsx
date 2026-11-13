import React, { useCallback, useEffect, useState } from 'react'
import { req } from '../../api.js'
import { Card, Empty, Err } from '../../shared/ui.jsx'

export default function Dashboard({ role }) {
  const [d, setD] = useState(null)
  const [e, setE] = useState(null)
  const load = useCallback(async () => {
    setE(null)
    try {
      const [op, res, ho, qa, ob] = await Promise.all([
        req('/v1/analytics/operational', { role }),
        req('/v1/analytics/resolution', { role }),
        req('/v1/analytics/handoff', { role }),
        req('/v1/analytics/qa', { role }),
        req('/internal/outbox-status', { role }),
      ])
      setD({ op, res, ho, qa, ob })
    } catch (err) { setE(err) }
  }, [role])
  useEffect(() => { load() }, [load])
  return (
    <>
      <div className="hero">
        <h2>Selamat datang di EAICS Workspace</h2>
        <p>Dashboard Operasional Layanan Pelanggan: Monitoring Antrean (Queue), Tiket Layanan, Pemantauan Batas Waktu SLA, Persetujuan (Dual-Custody), dan Metrik Evaluasi Mutu (QA).</p>
        <div className="row mt"><button className="btn" style={{ background: '#fff' }} onClick={load}>Muat Ulang (Refresh)</button></div>
      </div>
      <div className="mt" />
      <Err e={e} onClose={() => setE(null)} />
      {!d ? <Card><Empty text="Memuat metrik..." /></Card> : (
        <>
          <div className="grid g4">
            <Card><div className="stat"><span className="v">{d.op.cases_total}</span><span className="l">Total Kasus (Cases)</span><span className="d">terbuka: {d.op.open_cases}</span></div></Card>
            <Card><div className="stat"><span className="v">{d.op.tickets_total}</span><span className="l">Total Tiket (Tickets)</span><span className="d">pelanggaran SLA: {d.op.sla_breached}</span></div></Card>
            <Card><div className="stat"><span className="v">{Math.round((d.op.sla_attainment_ratio || 0) * 100)}%</span><span className="l">Ketercapaian SLA</span><span className="d">target SLA tercapai</span></div></Card>
            <Card><div className="stat"><span className="v">{d.ob.pending}</span><span className="l">Notifikasi Pending</span><span className="d">terkirim: {d.ob.sent}</span></div></Card>
          </div>
          <div className="grid g3 mt">
            <Card title="Tingkat Resolusi" sub="Rasio kasus yang dibuka kembali (Reopen Rate)">
              <div className="stat"><span className="v">{Math.round((d.res.reopen_rate || 0) * 100)}%</span><span className="l">reopen rate • selesai: {d.res.closed}</span></div>
            </Card>
            <Card title="Kelengkapan Handoff" sub="Rasio paket konteks lengkap saat dialihkan ke petugas">
              <div className="stat"><span className="v">{Math.round((d.ho.complete_rate || 0) * 100)}%</span><span className="l">paket lengkap • total {d.ho.total}</span></div>
            </Card>
            <Card title="Mutu Layanan (QA Score)" sub="Rata-rata total skor evaluasi review">
              <div className="stat"><span className="v">{d.qa.avg_total}</span><span className="l">n = {d.qa.n} • auto-fail {Math.round((d.qa.auto_fail_rate || 0) * 100)}%</span></div>
            </Card>
          </div>
        </>
      )}
    </>
  )
}
