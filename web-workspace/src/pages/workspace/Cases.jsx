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
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--border)', color: 'var(--muted)' }}>
                      <th style={{ padding: '0.5rem' }}>No. Ref / ID</th>
                      <th style={{ padding: '0.5rem' }}>Nasabah</th>
                      <th style={{ padding: '0.5rem' }}>Tipe</th>
                      <th style={{ padding: '0.5rem' }}>Prioritas</th>
                      <th style={{ padding: '0.5rem' }}>Status</th>
                      <th style={{ padding: '0.5rem' }}>Deskripsi</th>
                      <th style={{ padding: '0.5rem' }}>Percakapan</th>
                      <th style={{ padding: '0.5rem' }}>Waktu</th>
                      <th style={{ padding: '0.5rem' }}>Aksi</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tickets.map((t) => (
                      <tr key={t.ticket_id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '0.5rem', fontWeight: 600 }}>{t.customer_reference || t.ticket_id}</td>
                        <td style={{ padding: '0.5rem' }}>{t.customer_id || '-'}</td>
                        <td style={{ padding: '0.5rem' }}><span className="badge b-blue">{t.type}</span></td>
                        <td style={{ padding: '0.5rem' }}><span className={`badge ${t.priority === 'HIGH' || t.priority === 'URGENT' ? 'b-amber' : 'b-gray'}`}>{t.priority}</span></td>
                        <td style={{ padding: '0.5rem' }}><StateBadge v={t.status} /></td>
                        <td style={{ padding: '0.5rem', maxWidth: 280 }}>{t.description}</td>
                        <td style={{ padding: '0.5rem' }}>
                          {t.conversation_id ? (
                            <button
                              className="btn sm"
                              style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}
                              type="button"
                              onClick={() => navigate(`/agent/conversations?cid=${encodeURIComponent(t.conversation_id)}`)}
                            >
                              {t.conversation_id}
                            </button>
                          ) : '-'}
                        </td>
                        <td style={{ padding: '0.5rem', whiteSpace: 'nowrap', fontSize: '0.75rem', color: 'var(--muted)' }}>
                          {t.created_at ? new Date(t.created_at).toLocaleString('id-ID') : '-'}
                        </td>
                        <td style={{ padding: '0.5rem' }}>
                          {t.status === 'OPEN' && (
                            <button
                              className="btn sm primary"
                              style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}
                              type="button"
                              onClick={() => updateTicketStatus(t.ticket_id, 'RESOLVED')}
                            >
                              Selesaikan
                            </button>
                          )}
                          {t.status === 'RESOLVED' && (
                            <button
                              className="btn sm"
                              style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}
                              type="button"
                              onClick={() => updateTicketStatus(t.ticket_id, 'CLOSED')}
                            >
                              Tutup
                            </button>
                          )}
                          {(role === 'supervisor' || role === 'admin') && (
                            <button
                              className="btn sm"
                              style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem', marginLeft: 4 }}
                              type="button"
                              title="Tugaskan ulang antrean"
                              onClick={() => reassignTicket(t.ticket_id)}
                            >
                              Reassign ({t.owner_queue || 'GENERAL'})
                            </button>
                          )}
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
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--border)', color: 'var(--muted)' }}>
                      <th style={{ padding: '0.5rem' }}>No. Kasus</th>
                      <th style={{ padding: '0.5rem' }}>Nasabah</th>
                      <th style={{ padding: '0.5rem' }}>Kategori</th>
                      <th style={{ padding: '0.5rem' }}>Severity</th>
                      <th style={{ padding: '0.5rem' }}>Status</th>
                      <th style={{ padding: '0.5rem' }}>Status Nasabah</th>
                      <th style={{ padding: '0.5rem' }}>Antrean</th>
                      <th style={{ padding: '0.5rem' }}>Waktu Masuk</th>
                      <th style={{ padding: '0.5rem' }}>Tindakan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {casesList.map((c) => (
                      <tr key={c.case_id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '0.5rem', fontWeight: 600 }}>{c.customer_reference || c.case_id}</td>
                        <td style={{ padding: '0.5rem' }}>{c.customer_id || '-'}</td>
                        <td style={{ padding: '0.5rem' }}><span className="badge b-blue">{c.category}</span></td>
                        <td style={{ padding: '0.5rem' }}><Sev v={c.severity_confirmed || c.severity_proposed} /></td>
                        <td style={{ padding: '0.5rem' }}><StateBadge v={c.status} /></td>
                        <td style={{ padding: '0.5rem' }}><StateBadge v={c.customer_visible_status} /></td>
                        <td style={{ padding: '0.5rem' }}>{c.owner_queue}</td>
                        <td style={{ padding: '0.5rem', whiteSpace: 'nowrap', fontSize: '0.75rem', color: 'var(--muted)' }}>
                          {c.logged_at ? new Date(c.logged_at).toLocaleString('id-ID') : '-'}
                        </td>
                        <td style={{ padding: '0.5rem' }}>
                          <button
                            className="btn sm"
                            style={{ padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}
                            type="button"
                            onClick={() => {
                              setCx((prev) => ({ ...prev, case_id: c.case_id }))
                              setEv((prev) => ({ ...prev, case_id: c.case_id }))
                              setActiveTab('manage')
                            }}
                          >
                            Kelola
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
