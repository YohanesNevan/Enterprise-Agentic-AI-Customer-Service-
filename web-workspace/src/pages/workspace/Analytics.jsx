import React, { useCallback, useEffect, useState } from 'react'
import { req } from '../../api.js'
import { Card, Err, Empty, Json } from '../../shared/ui.jsx'

export function Analytics({ role }) {
  const [e, setE] = useState(null)
  const [d, setD] = useState(null)

  const load = useCallback(async () => {
    setE(null)
    try {
      const [op, tree, res, ho, qa] = await Promise.all([
        req('/v1/analytics/operational', { role }),
        req('/v1/analytics/driver-tree', { role }),
        req('/v1/analytics/resolution', { role }),
        req('/v1/analytics/handoff', { role }),
        req('/v1/analytics/qa', { role }),
      ])
      setD({ op, tree, res, ho, qa })
    } catch (err) {
      setE(err)
    }
  }, [role])

  useEffect(() => { load() }, [load])

  const csv = async (kind) => {
    setE(null)
    try {
      const text = await req(`/v1/analytics/export.csv?kind=${kind}`, { role, download: true })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }))
      a.download = `eaics-${kind}.csv`
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (err) {
      setE(err)
    }
  }

  const treeRows = d ? Object.entries(d.tree).flatMap(([cat, subs]) => Object.entries(subs).map(([sub2, n]) => ({ cat, sub: sub2, n }))) : []

  return (
    <>
      <Err e={e} onClose={() => setE(null)} />
      <div className="row">
        <button className="btn sm" onClick={load}>Refresh Analitik</button>
        <button className="btn sm" onClick={() => csv('cases')}>Export CSV Kasus</button>
        <button className="btn sm" onClick={() => csv('handoffs')}>Export CSV Handoff</button>
      </div>
      {!d ? <Card><Empty text="Memuat laporan analitik..." /></Card> : (
        <>
          <div className="grid g4 mt">
            <Card><div className="stat"><span className="v">{d.op.cases_total}</span><span className="l">Total Kasus • Tiket: {d.op.tickets_total}</span></div></Card>
            <Card><div className="stat"><span className="v">{Math.round(d.op.sla_attainment_ratio * 100)}%</span><span className="l">Ketercapaian SLA</span></div></Card>
            <Card><div className="stat"><span className="v">{Math.round(d.res.reopen_rate * 100)}%</span><span className="l">Reopen Rate (Target &lt; 5%)</span></div></Card>
            <Card><div className="stat"><span className="v">{d.qa.avg_total}</span><span className="l">Rata-rata Skor QA (n={d.qa.n})</span></div></Card>
          </div>
          <Card title="Driver Tree Klasifikasi Masalah" sub="Analisis distribusi masalah berjenjang: Kategori → Sub-kategori">
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl">
                <thead><tr><th>Kategori Masalah</th><th>Sub-Kategori</th><th>Volume Keluhan</th></tr></thead>
                <tbody>{treeRows.map((r, i) => <tr key={i}><td>{r.cat}</td><td>{r.sub}</td><td><b>{r.n}</b></td></tr>)}</tbody>
              </table>
              {!treeRows.length && <Empty text="Belum ada data distribusi masalah." />}
            </div>
          </Card>
          <Card title="Distribusi Alasan Eskalasi Handoff"><Json data={d.ho} /></Card>
        </>
      )}
    </>
  )
}

export default Analytics
