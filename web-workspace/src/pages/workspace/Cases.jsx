import React, { useCallback, useEffect, useState } from 'react'
import { req, CLOSURE_ITEMS, SEVERITIES } from '../../api.js'
import { navigate } from '../../shared/navigation.js'
import { Card, Err, Empty, Json, Sev, StateBadge } from '../../shared/ui.jsx'
import { useForm } from '../../shared/useForm.js'

export function Cases({ role }) {
  const [e, setE] = useState(null)
  const [out, setOut] = useState(null)
  const [tickets, setTickets] = useState([])
  const [casesList, setCasesList] = useState([])
  const [loadingList, setLoadingList] = useState(false)
  const [activeTab, setActiveTab] = useState('tickets') // 'tickets' | 'cases' | 'manage'
  const [ct, setCt, resetCt] = useForm({ conversation_id: 'CNV-DEMO-1', type: 'GENERAL', priority: 'NORMAL', description: 'Dana belum masuk ke rekening tujuan' })
  const [cc, setCc, resetCc] = useForm({ conversation_id: 'CNV-DEMO-1', category: 'TRANSACTION_DISPUTE', severity_proposed: 'HIGH', description: 'Tidak mengenal transaksi Rp1.200.000', vulnerability_flag: false })
  const [cx, setCx] = useForm({ case_id: '', reason: '' })
  const [check, setCheck] = useState({ outcome_recorded: true })
  const [ev, setEv] = useForm({ case_id: '', description: 'Transaction detail showing date, amount and merchant', reason: 'Verifikasi sengketa' })

  const loadLists = useCallback(async () => {
    setLoadingList(true)
    try {
      const [tList, cList] = await Promise.all([
        req('/v1/tickets', { role }).catch(() => []),
        req('/v1/cases', { role }).catch(() => [])
      ])
      setTickets(Array.isArray(tList) ? tList : [])
      setCasesList(Array.isArray(cList) ? cList : [])
    } catch (err) {
      // ignore
    } finally {
      setLoadingList(false)
    }
  }, [role])

  useEffect(() => {
    loadLists()
  }, [loadLists])

  const run = async (fn) => {
    setE(null)
    setOut(null)
    try {
      const r = await fn()
      setOut(r)
      await loadLists()
    } catch (err) {
      setE(err)
    }
  }

  const updateTicketStatus = async (tid, newStatus) => {
    setE(null)
    try {
      await req(`/v1/tickets/${encodeURIComponent(tid)}`, {
        method: 'PATCH',
        role,
        body: { status: newStatus }
      })
      await loadLists()
    } catch (err) {
      setE(err)
    }
  }

  const reassignTicket = async (tid) => {
    const newQueue = window.prompt("Tentukan antrean / spesialis baru untuk tiket ini:", "SPECIALIST_TIER2")
    if (!newQueue) return
    setE(null)
    try {
      await req(`/v1/tickets/${encodeURIComponent(tid)}/assign`, {
        method: 'PATCH',
        role,
        body: { owner_queue: newQueue, reason: "Tugaskan ulang oleh supervisor" }
      })
      await loadLists()
    } catch (err) {
      setE(err)
    }
  }

  const mkTicket = () => run(() => req('/v1/tickets', { method: 'POST', role, body: { ...ct } }).then((r) => { resetCt(); return r }))
  const mkCase = () => run(() => req('/v1/cases', { method: 'POST', role, body: { ...cc } }).then((r) => { resetCc(); return r }))
  const close = () => run(() => req(`/v1/cases/${cx.case_id}/close`, { method: 'POST', role, body: { checklist: check } }))
  const reopen = () => run(() => req(`/v1/cases/${cx.case_id}/reopen`, { method: 'POST', role, body: { reason: cx.reason || 'Nasabah melapor masalah berlanjut' } }))
  const evReq = () => run(() => req(`/v1/cases/${ev.case_id}/evidence-requests`, { method: 'POST', role, body: { items: [{ description: ev.description }], reason: ev.reason } }))

  return (
    <>
      <Err e={e} onClose={() => setE(null)} />
      {out && <Card title="Hasil operasi"><Json data={out} /></Card>}

      {/* Tab Switcher & Overview Card */}
      <Card
        title="Pusat Tiket & Manajemen Kasus"
        sub="Kelola tiket investigasi otomatis (AI-generated) dan eskalasi kasus nasabah."
        wide
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className={`btn sm ${activeTab === 'tickets' ? 'primary' : ''}`}
              type="button"
              onClick={() => setActiveTab('tickets')}
            >
              Tiket Layanan ({tickets.length})
            </button>
            <button
              className={`btn sm ${activeTab === 'cases' ? 'primary' : ''}`}
              type="button"
              onClick={() => setActiveTab('cases')}
            >
              Kasus & Sengketa ({casesList.length})
            </button>
            <button
              className={`btn sm ${activeTab === 'manage' ? 'primary' : ''}`}
              type="button"
              onClick={() => setActiveTab('manage')}
            >
              Form Pembuatan & Penutupan
            </button>
          </div>
          <button className="btn sm" type="button" onClick={() => loadLists()} disabled={loadingList}>
            {loadingList ? 'Memuat...' : 'Segarkan Data'}
          </button>
        </div>

        {activeTab === 'tickets' && (
          <div>
            {!tickets.length ? (
              <Empty text="Belum ada tiket investigasi yang terdaftar di database." />
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--line-strong)', color: 'var(--muted)' }}>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '90px' }}>No. Ref</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '120px' }}>Nasabah</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '95px' }}>Tipe</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '75px' }}>Prioritas</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '70px' }}>Status</th>
                      <th style={{ padding: '0.6rem 0.6rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', minWidth: '220px' }}>Deskripsi</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '95px' }}>Percakapan</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '75px' }}>Waktu</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '105px' }}>Aksi</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tickets.map((t) => (
                      <tr key={t.ticket_id} style={{ borderBottom: '1px solid var(--line)' }}>
                        <td style={{ padding: '0.6rem 0.5rem', fontWeight: 700, verticalAlign: 'middle', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)' }}>
                          {t.customer_reference || t.ticket_id}
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle', whiteSpace: 'nowrap', fontSize: '11px', color: 'var(--ink-soft)' }}>
                          {t.customer_id || '-'}
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle' }}>
                          <span className="badge b-blue" style={{ fontSize: '10px' }}>{t.type}</span>
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle' }}>
                          <span className={`badge ${t.priority === 'HIGH' || t.priority === 'URGENT' ? 'b-amber' : 'b-gray'}`} style={{ fontSize: '10px' }}>
                            {t.priority}
                          </span>
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle' }}>
                          <StateBadge v={t.status} />
                        </td>
                        <td style={{ padding: '0.6rem 0.6rem', verticalAlign: 'middle', lineHeight: 1.5, color: 'var(--ink)' }}>
                          {t.description}
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                          {t.conversation_id ? (
                            <button
                              className="btn sm"
                              style={{
                                height: '24px',
                                minHeight: '24px',
                                padding: '0 8px',
                                fontSize: '11px',
                                borderRadius: '5px',
                                background: 'var(--surface-alt)',
                                border: '1px solid var(--line)',
                                whiteSpace: 'nowrap'
                              }}
                              type="button"
                              title={`Buka percakapan ${t.conversation_id}`}
                              onClick={() => navigate(`/agent/conversations?cid=${encodeURIComponent(t.conversation_id)}`)}
                            >
                              💬 Buka Chat
                            </button>
                          ) : '-'}
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', whiteSpace: 'nowrap', verticalAlign: 'middle' }}>
                          <div style={{ fontSize: '11px', fontWeight: 500, color: 'var(--ink-soft)' }}>
                            {t.created_at ? new Date(t.created_at).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' }) : '-'}
                          </div>
                          <div style={{ fontSize: '10px', color: 'var(--muted)' }}>
                            {t.created_at ? new Date(t.created_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }) : ''}
                          </div>
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '100px' }}>
                            {t.status === 'OPEN' && (
                              <button
                                className="btn sm primary"
                                style={{
                                  height: '24px',
                                  minHeight: '24px',
                                  padding: '0 6px',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  whiteSpace: 'nowrap',
                                  borderRadius: '5px',
                                  width: '100%',
                                  justifyContent: 'center'
                                }}
                                type="button"
                                onClick={() => updateTicketStatus(t.ticket_id, 'RESOLVED')}
                              >
                                ✓ Selesaikan
                              </button>
                            )}
                            {t.status === 'RESOLVED' && (
                              <button
                                className="btn sm"
                                style={{
                                  height: '24px',
                                  minHeight: '24px',
                                  padding: '0 6px',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  whiteSpace: 'nowrap',
                                  borderRadius: '5px',
                                  width: '100%',
                                  justifyContent: 'center'
                                }}
                                type="button"
                                onClick={() => updateTicketStatus(t.ticket_id, 'CLOSED')}
                              >
                                Tutup Tiket
                              </button>
                            )}
                            {(role === 'supervisor' || role === 'admin') && (
                              <button
                                className="btn sm"
                                style={{
                                  height: '24px',
                                  minHeight: '24px',
                                  padding: '0 6px',
                                  fontSize: '10px',
                                  whiteSpace: 'nowrap',
                                  background: 'var(--surface-alt)',
                                  borderColor: 'var(--line-strong)',
                                  borderRadius: '5px',
                                  width: '100%',
                                  justifyContent: 'center'
                                }}
                                type="button"
                                title={`Antrean saat ini: ${t.owner_queue || 'GENERAL'}. Klik untuk alihkan antrean.`}
                                onClick={() => reassignTicket(t.ticket_id)}
                              >
                                ⇄ Alihkan ({t.owner_queue ? (t.owner_queue.length > 8 ? t.owner_queue.slice(0, 7) + '…' : t.owner_queue) : 'GEN'})
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === 'cases' && (
          <div>
            {!casesList.length ? (
              <Empty text="Belum ada kasus yang terdaftar." />
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--line-strong)', color: 'var(--muted)' }}>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '90px' }}>No. Kasus</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '120px' }}>Nasabah</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '110px' }}>Kategori</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '75px' }}>Severity</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '70px' }}>Status</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '85px' }}>Status Nasabah</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '80px' }}>Antrean</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '75px' }}>Waktu</th>
                      <th style={{ padding: '0.6rem 0.5rem', fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', width: '80px' }}>Tindakan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {casesList.map((c) => (
                      <tr key={c.case_id} style={{ borderBottom: '1px solid var(--line)' }}>
                        <td style={{ padding: '0.6rem 0.5rem', fontWeight: 700, verticalAlign: 'middle', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)' }}>
                          {c.customer_reference || c.case_id}
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle', whiteSpace: 'nowrap', fontSize: '11px', color: 'var(--ink-soft)' }}>
                          {c.customer_id || '-'}
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle' }}>
                          <span className="badge b-blue" style={{ fontSize: '10px' }}>{c.category}</span>
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle' }}>
                          <Sev v={c.severity_confirmed || c.severity_proposed} />
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle' }}>
                          <StateBadge v={c.status} />
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle' }}>
                          <StateBadge v={c.customer_visible_status} />
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle', fontSize: '11px' }}>
                          {c.owner_queue}
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', whiteSpace: 'nowrap', verticalAlign: 'middle' }}>
                          <div style={{ fontSize: '11px', fontWeight: 500, color: 'var(--ink-soft)' }}>
                            {c.logged_at ? new Date(c.logged_at).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' }) : '-'}
                          </div>
                          <div style={{ fontSize: '10px', color: 'var(--muted)' }}>
                            {c.logged_at ? new Date(c.logged_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }) : ''}
                          </div>
                        </td>
                        <td style={{ padding: '0.6rem 0.5rem', verticalAlign: 'middle' }}>
                          <button
                            className="btn sm"
                            style={{
                              height: '24px',
                              minHeight: '24px',
                              padding: '0 10px',
                              fontSize: '11px',
                              fontWeight: 600,
                              whiteSpace: 'nowrap',
                              borderRadius: '5px'
                            }}
                            type="button"
                            onClick={() => {
                              setCx((prev) => ({ ...prev, case_id: c.case_id }))
                              setEv((prev) => ({ ...prev, case_id: c.case_id }))
                              setActiveTab('manage')
                            }}
                          >
                            Kelola →
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Formulir Pembuatan & Tindakan Manual */}
      {(activeTab === 'manage' || (!tickets.length && !casesList.length)) && (
        <div className="grid g2 mt">
          <Card title="Buat Tiket Layanan (Create Ticket)" sub="Penerbitan tiket CRM resmi untuk tindak lanjut operasional.">
            <div className="form">
              <label>ID Percakapan<input value={ct.conversation_id} onChange={setCt('conversation_id')} placeholder="CNV-..." /></label>
              <div className="form2">
                <label>Tipe Tiket<input value={ct.type} onChange={setCt('type')} placeholder="GENERAL / COMPLAINT" /></label>
                <label>Prioritas<select value={ct.priority} onChange={setCt('priority')}>{['LOW', 'NORMAL', 'HIGH', 'URGENT'].map((o) => <option key={o}>{o}</option>)}</select></label>
              </div>
              <label>Deskripsi Masalah<textarea value={ct.description} onChange={setCt('description')} rows={2} placeholder="Rincian kendala nasabah..." /></label>
              <div className="row"><button className="btn primary" onClick={mkTicket}>Buat Tiket Baru</button></div>
            </div>
          </Card>
          <Card title="Eskalasi Kasus Investigasi (Create Case)" sub="Eskalasi kasus sengketa dengan konfirmasi tingkat severity oleh staf.">
            <div className="form">
              <label>ID Percakapan<input value={cc.conversation_id} onChange={setCc('conversation_id')} placeholder="CNV-..." /></label>
              <div className="form2">
                <label>Kategori Sengketa<select value={cc.category} onChange={setCc('category')}>{['TRANSACTION_DISPUTE', 'GENERAL', 'COMPLAINT', 'FRAUD', 'ACCOUNT'].map((o) => <option key={o}>{o}</option>)}</select></label>
                <label>Severity yang Diusulkan<select value={cc.severity_proposed} onChange={setCc('severity_proposed')}>{SEVERITIES.map((o) => <option key={o}>{o}</option>)}</select></label>
              </div>
              <label>Deskripsi Kasus<textarea value={cc.description} onChange={setCc('description')} rows={2} placeholder="Jelaskan indikasi sengketa/masalah..." /></label>
              <label className="check"><input type="checkbox" checked={cc.vulnerability_flag} onChange={setCc('vulnerability_flag')} /> Nasabah prioritas / rentan (Percepat SLA)</label>
              <div className="row"><button className="btn primary" onClick={mkCase}>Daftarkan Kasus Baru</button></div>
            </div>
          </Card>
          <Card title="Penyelesaian & Penutupan Kasus (Close Case)" sub="Checklist pemenuhan butir solusi sebelum kasus dinyatakan selesai (Closed).">
            <div className="form">
              <label>Case ID<input value={cx.case_id} onChange={setCx('case_id')} placeholder="CAS-..." /></label>
              {CLOSURE_ITEMS.map(([k, label]) => (
                <label className="check" key={k}><input type="checkbox" checked={!!check[k]} onChange={(ev) => setCheck({ ...check, [k]: ev.target.checked })} />{label}</label>
              ))}
              <div className="row"><button className="btn primary" onClick={close}>Tutup Kasus (Close Case)</button></div>
              <label>Alasan Buka Kembali (Reopen)<input value={cx.reason} onChange={setCx('reason')} placeholder="Alasan bila nasabah melapor kendala berulang..." /></label>
              <div className="row"><button className="btn" onClick={reopen}>Buka Kembali Kasus</button></div>
            </div>
          </Card>
          <Card title="Permintaan Bukti Tambahan (Request Evidence)" sub="Kirim permintaan dokumen pendukung (struk/bukti transaksi) kepada nasabah.">
            <div className="form">
              <label>Case ID<input value={ev.case_id} onChange={setEv('case_id')} placeholder="CAS-..." /></label>
              <label>Deskripsi Dokumen Bukti<input value={ev.description} onChange={setEv('description')} placeholder="Contoh: Bukti mutasi rekening atau foto fisik kartu" /></label>
              <label>Alasan Permintaan<input value={ev.reason} onChange={setEv('reason')} placeholder="Verifikasi sengketa transaksi" /></label>
              <div className="row"><button className="btn primary" onClick={evReq}>Kirim Permintaan Bukti</button></div>
            </div>
          </Card>
        </div>
      )}
    </>
  )
}

export default Cases
