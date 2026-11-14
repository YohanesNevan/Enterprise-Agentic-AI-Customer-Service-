import React, { useCallback, useEffect, useState } from 'react'
import { req } from '../../api.js'
import { navigate } from '../../shared/navigation.js'
import { Card, Err, Empty } from '../../shared/ui.jsx'

export function Dashboard({ role }) {
  const [d, setD] = useState(null)
  const [e, setE] = useState(null)
  const [loading, setLoading] = useState(false)
  const [lastRefreshed, setLastRefreshed] = useState(null)
  const [refreshNotice, setRefreshNotice] = useState(null)
  const [ackingId, setAckingId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setE(null)
    try {
      const results = await Promise.allSettled([
        req('/v1/analytics/operational'),
        req('/v1/analytics/resolution'),
        req('/v1/analytics/handoff'),
        req('/v1/analytics/qa'),
        req('/internal/outbox-status'),
        req('/v1/workspace/escalations?role_target=SUPERVISOR'),
        req('/v1/workspace/sla/records'),
        req('/v1/analytics/driver-tree'),
      ])

      const [opRes, resRes, hoRes, qaRes, obRes, escRes, slaRes, treeRes] = results

      const op = opRes.status === 'fulfilled' ? opRes.value : {}
      const res = resRes.status === 'fulfilled' ? resRes.value : {}
      const ho = hoRes.status === 'fulfilled' ? hoRes.value : {}
      const qa = qaRes.status === 'fulfilled' ? qaRes.value : {}
      const ob = obRes.status === 'fulfilled' ? obRes.value : {}
      const esc = escRes.status === 'fulfilled' ? escRes.value : { items: [] }
      const sla = slaRes.status === 'fulfilled' ? slaRes.value : { items: [] }
      const tree = treeRes.status === 'fulfilled' ? treeRes.value : {}

      setD({ op, res, ho, qa, ob, esc, sla, tree })
      
      const now = new Date()
      const timeStr = now.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' WIB'
      setLastRefreshed(timeStr)
      setRefreshNotice('Data berhasil dimuat ulang')
      setTimeout(() => setRefreshNotice(null), 2500)
    } catch (err) {
      setE(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const acknowledgeEscalation = async (escalationId) => {
    setAckingId(escalationId)
    try {
      await req(`/v1/workspace/escalations/${encodeURIComponent(escalationId)}/acknowledge`, {
        method: 'POST',
      })
      await load()
    } catch (err) {
      setE(err)
    } finally {
      setAckingId(null)
    }
  }

  // Pre-calculations for visualizations
  const slaAttainment = d?.op?.sla_attainment_ratio !== undefined ? Math.round(d.op.sla_attainment_ratio * 100) : 100
  const reopenRate = d?.res?.reopen_rate !== undefined ? Math.round(d.res.reopen_rate * 100) : 0
  const completeRate = d?.ho?.complete_rate !== undefined ? Math.round(d.ho.complete_rate * 100) : 100
  const qaScore = d?.qa?.avg_total !== undefined ? d.qa.avg_total : 0
  const qaAutoFail = d?.qa?.auto_fail_rate !== undefined ? Math.round(d.qa.auto_fail_rate * 100) : 0

  // Category breakdown from driver tree
  const categories = []
  if (d?.tree && typeof d.tree === 'object') {
    let grandTotal = 0
    Object.entries(d.tree).forEach(([cat, subs]) => {
      let count = 0
      if (typeof subs === 'object' && subs !== null) {
        Object.values(subs).forEach((v) => { count += Number(v) || 0 })
      } else {
        count = Number(subs) || 0
      }
      if (count > 0) {
        categories.push({ name: cat, count })
        grandTotal += count
      }
    })
    categories.forEach((c) => {
      c.percent = grandTotal > 0 ? Math.round((c.count / grandTotal) * 100) : 0
    })
  }

  const categoryColors = ['#006ad2', '#00bb7f', '#f99c00', '#9333ea', '#e40014', '#0084cc']

  // Active unacknowledged escalations
  const pendingEscalations = (d?.esc?.items || []).filter((it) => !it.acknowledged_by)

  // SLA at risk or breached
  const slaAlerts = (d?.sla?.items || []).filter((it) => it.state === 'BREACHED' || it.state === 'AT_RISK')

  return (
    <>
      {/* Hero Header Section */}
      <div className="dashboard-hero">
        <div className="dashboard-hero-title">
          <h2>Supervisor Operations Dashboard</h2>
          <span className="badge b-violet" style={{ fontSize: 11, padding: '4px 10px' }}>
            Supervisor Console
          </span>
        </div>
        <p>
          Pusat pemantauan operasional terpadu: metrik real-time antrean tiket layanan, kepatuhan batas waktu SLA,
          alokasi penyelesaian sengketa, dan kontrol jaminan mutu interaksi agen AI dan staf.
        </p>

        <div className="dashboard-hero-controls">
          <button
            type="button"
            className={`btn-refresh ${loading ? 'is-loading' : ''}`}
            onClick={load}
            disabled={loading}
            title="Klik untuk memuat ulang metrik secara langsung"
          >
            <span className={`refresh-icon ${loading ? 'spinning' : ''}`}>↻</span>
            <span>{loading ? 'Memperbarui Metrik...' : 'Muat Ulang (Refresh)'}</span>
          </button>

          {lastRefreshed && (
            <div className="live-status-pill">
              <span className="pulse-dot" />
              <span>Live • Terakhir diperbarui pk {lastRefreshed}</span>
            </div>
          )}

          {refreshNotice && (
            <span className="badge b-green" style={{ padding: '6px 12px' }}>
              ✓ {refreshNotice}
            </span>
          )}

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              className="quick-nav-pill"
              onClick={() => navigate('/supervisor/queue')}
            >
              Antrean Layanan →
            </button>
            <button
              type="button"
              className="quick-nav-pill"
              onClick={() => navigate('/supervisor/sla')}
            >
              Monitor SLA →
            </button>
            <button
              type="button"
              className="quick-nav-pill"
              onClick={() => navigate('/complaints')}
            >
              Ajudikasi Komplain →
            </button>
          </div>
        </div>
      </div>

      <div className="mt" />
      <Err e={e} onClose={() => setE(null)} />

      {!d ? (
        <Card><Empty text="Memuat metrik operasional..." /></Card>
      ) : (
        <>
          {/* Top Primary KPI Grid */}
          <div className="grid g4">
            {/* Total Cases */}
            <Card>
              <div className="metric-card">
                <div className="metric-header">
                  <span className="metric-title">Total Kasus (Cases)</span>
                  <span className="badge b-blue">{d.op.open_cases || 0} Terbuka</span>
                </div>
                <div className="metric-body">
                  <div className="metric-value-row">
                    <span className="metric-value">{d.op.cases_total || 0}</span>
                    <span className="metric-unit">kasus</span>
                  </div>
                </div>
                <div className="metric-footer">
                  <span>Kasus dalam penanganan</span>
                  <a
                    href="/supervisor/cases"
                    onClick={(ev) => { ev.preventDefault(); navigate('/supervisor/cases') }}
                    style={{ fontSize: 11, fontWeight: 600 }}
                  >
                    Kelola Kasus →
                  </a>
                </div>
              </div>
            </Card>

            {/* Total Tickets */}
            <Card>
              <div className="metric-card">
                <div className="metric-header">
                  <span className="metric-title">Total Tiket (Tickets)</span>
                  <span className={`badge ${d.op.sla_breached > 0 ? 'b-red' : 'b-green'}`}>
                    {d.op.sla_breached > 0 ? `${d.op.sla_breached} Pelanggaran` : 'SLA Aman'}
                  </span>
                </div>
                <div className="metric-body">
                  <div className="metric-value-row">
                    <span className="metric-value">{d.op.tickets_total || 0}</span>
                    <span className="metric-unit">tiket terdaftar</span>
                  </div>
                </div>
                <div className="metric-footer">
                  <span>Pelanggaran SLA: <strong>{d.op.sla_breached || 0}</strong></span>
                  <a
                    href="/supervisor/cases"
                    onClick={(ev) => { ev.preventDefault(); navigate('/supervisor/cases') }}
                    style={{ fontSize: 11, fontWeight: 600 }}
                  >
                    Daftar Tiket →
                  </a>
                </div>
              </div>
            </Card>

            {/* SLA Attainment */}
            <Card>
              <div className="metric-card">
                <div className="metric-header">
                  <span className="metric-title">Ketercapaian SLA</span>
                  <span className={`badge ${slaAttainment >= 95 ? 'b-green' : slaAttainment >= 85 ? 'b-amber' : 'b-red'}`}>
                    {slaAttainment >= 95 ? 'Target Tercapai' : 'Perlu Perhatian'}
                  </span>
                </div>
                <div className="metric-body">
                  <div className="metric-value-row">
                    <span className="metric-value">{slaAttainment}%</span>
                    <span className="metric-unit">kepatuhan</span>
                  </div>
                  <div className="progress-track" title={`Ketercapaian: ${slaAttainment}% (Target: >= 95%)`}>
                    <div
                      className={`progress-fill ${slaAttainment >= 95 ? 'green' : slaAttainment >= 85 ? 'amber' : 'red'}`}
                      style={{ width: `${Math.min(100, Math.max(0, slaAttainment))}%` }}
                    />
                  </div>
                </div>
                <div className="metric-footer">
                  <span>Target resmi: <strong>≥ 95.0%</strong></span>
                  <a
                    href="/supervisor/sla"
                    onClick={(ev) => { ev.preventDefault(); navigate('/supervisor/sla') }}
                    style={{ fontSize: 11, fontWeight: 600 }}
                  >
                    Detail SLA →
                  </a>
                </div>
              </div>
            </Card>

            {/* Outbox Notifications */}
            <Card>
              <div className="metric-card">
                <div className="metric-header">
                  <span className="metric-title">Notifikasi Outbox</span>
                  <span className="badge b-gray">
                    {d.ob.pending > 0 ? `${d.ob.pending} Menunggu` : 'Antrean Bersih'}
                  </span>
                </div>
                <div className="metric-body">
                  <div className="metric-value-row">
                    <span className="metric-value">{d.ob.pending || 0}</span>
                    <span className="metric-unit">pending</span>
                  </div>
                </div>
                <div className="metric-footer">
                  <span>Berhasil terkirim: <strong>{d.ob.sent || 0}</strong></span>
                  <span style={{ fontSize: 10, color: 'var(--muted)' }}>Reliable Queue</span>
                </div>
              </div>
            </Card>
          </div>

          {/* Secondary In-Depth Visual Performance Metrics */}
          <div className="grid g3 mt">
            {/* Resolution Rate Card */}
            <Card
              title="Tingkat Resolusi & Reopen Rate"
              sub="Rasio kasus yang dibuka kembali setelah status ditutup"
            >
              <div className="metric-body" style={{ marginTop: 6 }}>
                <div className="metric-value-row">
                  <span className="metric-value" style={{ color: reopenRate <= 10 ? 'var(--ink)' : 'var(--danger)' }}>
                    {reopenRate}%
                  </span>
                  <span className="metric-unit">reopen rate</span>
                  <span
                    className={`badge ${reopenRate <= 10 ? 'b-green' : 'b-red'}`}
                    style={{ marginLeft: 'auto' }}
                  >
                    {reopenRate <= 10 ? 'Optimal (≤ 10%)' : 'Di Atas Ambang'}
                  </span>
                </div>

                <div className="progress-track" style={{ height: 10 }}>
                  <div
                    className={`progress-fill ${reopenRate <= 10 ? 'green' : 'red'}`}
                    style={{ width: `${Math.min(100, Math.max(reopenRate, 5))}%` }}
                  />
                </div>

                <div className="kv" style={{ marginTop: 12 }}>
                  <dt>Kasus Selesai (Closed)</dt>
                  <dd><strong>{d.res.closed || 0}</strong> kasus</dd>
                  <dt>Dibuka Kembali (Reopened)</dt>
                  <dd><strong>{d.res.reopen_count || 0}</strong> kasus</dd>
                  <dt>Batas Toleransi (SM13)</dt>
                  <dd>Maksimal 10% dari total kasus</dd>
                </div>
              </div>
            </Card>

            {/* Handoff Completeness Card */}
            <Card
              title="Kelengkapan Paket Handoff"
              sub="Rasio kelengkapan konteks percakapan saat dialihkan ke petugas"
            >
              <div className="metric-body" style={{ marginTop: 6 }}>
                <div className="metric-value-row">
                  <span className="metric-value" style={{ color: completeRate >= 95 ? 'var(--ink)' : 'var(--amber)' }}>
                    {completeRate}%
                  </span>
                  <span className="metric-unit">paket lengkap</span>
                  <span
                    className={`badge ${completeRate >= 95 ? 'b-green' : 'b-amber'}`}
                    style={{ marginLeft: 'auto' }}
                  >
                    Target SM07: 100%
                  </span>
                </div>

                <div className="progress-track" style={{ height: 10 }}>
                  <div
                    className={`progress-fill ${completeRate >= 95 ? 'green' : 'amber'}`}
                    style={{ width: `${Math.min(100, Math.max(completeRate, 5))}%` }}
                  />
                </div>

                <div className="kv" style={{ marginTop: 12 }}>
                  <dt>Total Sesi Handoff</dt>
                  <dd><strong>{d.ho.total || 0}</strong> pengalihan</dd>
                  <dt>Distribusi Alasan</dt>
                  <dd>
                    {d.ho.by_reason && Object.keys(d.ho.by_reason).length > 0 ? (
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {Object.entries(d.ho.by_reason).map(([k, v]) => (
                          <span key={k} className="badge b-gray" style={{ fontSize: 10 }}>
                            {k}: {v}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span style={{ color: 'var(--muted)' }}>Belum ada data handoff</span>
                    )}
                  </dd>
                </div>
              </div>
            </Card>

            {/* QA Score Card */}
            <Card
              title="Mutu Layanan (QA Score)"
              sub="Rata-rata total skor evaluasi review mutu berkala"
            >
              <div className="metric-body" style={{ marginTop: 6 }}>
                <div className="metric-value-row">
                  <span className="metric-value">{qaScore}</span>
                  <span className="metric-unit">/ 100 poin</span>
                  <span
                    className={`badge ${qaAutoFail === 0 ? 'b-green' : 'b-red'}`}
                    style={{ marginLeft: 'auto' }}
                  >
                    {qaAutoFail === 0 ? '0% Auto-Fail' : `${qaAutoFail}% Auto-Fail`}
                  </span>
                </div>

                <div className="progress-track" style={{ height: 10 }}>
                  <div
                    className={`progress-fill ${qaScore >= 80 ? 'green' : qaScore >= 60 ? 'amber' : 'blue'}`}
                    style={{ width: `${Math.min(100, Math.max(qaScore, qaScore === 0 ? 0 : 5))}%` }}
                  />
                </div>

                <div className="kv" style={{ marginTop: 12 }}>
                  <dt>Total Kasus Di-Review</dt>
                  <dd><strong>{d.qa.n || 0}</strong> sampel kasus</dd>
                  <dt>Persentase Auto-Fail</dt>
                  <dd>
                    <span style={{ color: qaAutoFail > 0 ? 'var(--danger)' : 'var(--ink-soft)' }}>
                      {qaAutoFail}% pelanggaran fatal
                    </span>
                  </dd>
                  <dt>Standar Kelulusan</dt>
                  <dd>Minimal 80.0 poin tanpa auto-fail</dd>
                </div>
              </div>
            </Card>
          </div>

          {/* Tertiary Row: Live Supervisor Feeds & Case Category Distribution */}
          <div className="grid g2 mt">
            {/* Live Alerts & Escalation Feed */}
            <Card
              title="Peringatan Batas Waktu SLA & Eskalasi Aktif"
              sub="Antrean eskalasi dan tiket yang membutuhkan tindakan supervisor"
            >
              {pendingEscalations.length === 0 && slaAlerts.length === 0 ? (
                <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--muted)' }}>
                  <div style={{ fontSize: 28, color: 'var(--success)', marginBottom: 6 }}>✓</div>
                  <strong style={{ display: 'block', color: 'var(--ink)', fontSize: 13, marginBottom: 4 }}>
                    Semua Operasional Berjalan Optimal
                  </strong>
                  <span style={{ fontSize: 12 }}>
                    Tidak ada eskalasi pending atau pelanggaran SLA yang memerlukan tindakan segera.
                  </span>
                </div>
              ) : (
                <div className="alert-feed-list">
                  {pendingEscalations.map((esc) => (
                    <div key={esc.escalation_id} className="alert-feed-item warning">
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                          <span className="badge b-amber">{esc.level || 'L1'}</span>
                          <strong style={{ fontSize: 12, color: 'var(--ink)' }}>{esc.trigger_type}</strong>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--ink-soft)' }}>
                          Objek: <code>{esc.object_type} #{esc.object_id}</code> • Ditujukan ke: <strong>{esc.target_role}</strong>
                        </div>
                      </div>
                      <button
                        type="button"
                        className="btn sm primary"
                        disabled={ackingId === esc.escalation_id}
                        onClick={() => acknowledgeEscalation(esc.escalation_id)}
                      >
                        {ackingId === esc.escalation_id ? 'Memproses...' : 'Konfirmasi (Acknowledge)'}
                      </button>
                    </div>
                  ))}

                  {slaAlerts.slice(0, 3).map((s) => (
                    <div key={s.record_id} className={`alert-feed-item ${s.state === 'BREACHED' ? 'danger' : 'warning'}`}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                          <span className={`badge ${s.state === 'BREACHED' ? 'b-red' : 'b-amber'}`}>{s.state}</span>
                          <strong style={{ fontSize: 12, color: 'var(--ink)' }}>Tiket #{s.ticket_id}</strong>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--ink-soft)' }}>
                          Batas Waktu: {s.target_completion_at ? new Date(s.target_completion_at).toLocaleTimeString('id-ID') : '-'}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="btn sm"
                        onClick={() => navigate('/supervisor/sla')}
                      >
                        Buka SLA →
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Case Categories Distribution (Driver-Tree) */}
            <Card
              title="Distribusi Topik Kasus Layanan"
              sub="Proporsi kategori permasalahan pelanggan (Driver-Tree Analytics)"
            >
              {categories.length === 0 ? (
                <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
                  Belum ada kategori kasus yang tercatat dalam sistem.
                </div>
              ) : (
                <div style={{ marginTop: 8 }}>
                  {/* Proportional Segmented Bar */}
                  <div className="dist-bar">
                    {categories.map((c, i) => (
                      <div
                        key={c.name}
                        className="dist-segment"
                        style={{
                          width: `${c.percent}%`,
                          backgroundColor: categoryColors[i % categoryColors.length],
                        }}
                        title={`${c.name}: ${c.count} kasus (${c.percent}%)`}
                      />
                    ))}
                  </div>

                  {/* Legend list */}
                  <div className="dist-legend">
                    {categories.map((c, i) => (
                      <div key={c.name} className="dist-legend-item">
                        <span
                          className="dist-dot"
                          style={{ backgroundColor: categoryColors[i % categoryColors.length] }}
                        />
                        <span>
                          <strong>{c.name}</strong>: {c.count} ({c.percent}%)
                        </span>
                      </div>
                    ))}
                  </div>

                  <div style={{ marginTop: 18, paddingTop: 10, borderTop: '1px solid var(--line)', fontSize: 11, color: 'var(--muted)' }}>
                    Total kasus dianalisis: <strong>{categories.reduce((acc, c) => acc + c.count, 0)}</strong> kasus aktif.
                  </div>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </>
  )
}

export const Dash = Dashboard
export default Dashboard
