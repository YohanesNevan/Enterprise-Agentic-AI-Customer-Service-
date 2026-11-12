import React, { useEffect, useState } from 'react'
import { req } from '../../api.js'
import { Card, Err, Empty, Sev, StateBadge } from '../../shared/ui.jsx'

export function AgentConversationActions({ d, role, session, onRefresh }) {
  const [reply, setReply] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState('')
  const [caseForm, setCaseForm] = useState({ category: 'TRANSACTION_DISPUTE', severity_proposed: 'MEDIUM', description: '' })
  const [ticketForm, setTicketForm] = useState({ type: 'GENERAL', priority: 'NORMAL', description: '' })
  const actorId = session?.principal?.actor_id
  const canCreateLinkedWork = ['cs_agent', 'supervisor'].includes(role)
  const ownsHandoff = d.handoff?.state === 'ACCEPTED' && d.handoff.accepted_by === actorId
  const canReply = ownsHandoff && d.conversation?.status === 'ACTIVE_HUMAN'
  const path = `/v1/workspace/conversations/${encodeURIComponent(d.conversation_id)}`

  const run = async (key, operation, success) => {
    setBusy(key)
    setError(null)
    setNotice('')
    try {
      await operation()
      setNotice(success)
      await onRefresh(d.conversation_id, true)
    } catch (err) {
      setError(err)
    } finally {
      setBusy('')
    }
  }

  const sendReply = (event) => {
    event.preventDefault()
    const content = reply.trim()
    if (!content) {
      setError(new Error('Balasan tidak boleh kosong.'))
      return
    }
    run('reply', async () => {
      await req(`${path}/messages`, { method: 'POST', body: { content } })
      setReply('')
    }, 'Balasan tersimpan dan tampil pada transkrip.')
  }

  const accept = () =>
    run(
      'accept',
      () => req(`/v1/workspace/handoffs/${encodeURIComponent(d.handoff.handoff_id)}/accept`, { method: 'POST', body: {} }),
      'Handoff diterima. Percakapan aktif ditangani petugas.'
    )

  const resolve = () =>
    run(
      'resolve',
      () => req(`${path}/resolve`, { method: 'POST', body: {} }),
      'Penanganan selesai dan menunggu konfirmasi customer.'
    )

  const createCase = (event) => {
    event.preventDefault()
    if (!caseForm.description.trim()) {
      setError(new Error('Deskripsi kasus wajib diisi.'))
      return
    }
    run('case', () => req('/v1/cases', { method: 'POST', body: { ...caseForm, description: caseForm.description.trim(), conversation_id: d.conversation_id, source_channel: 'WEB_CHAT' } }), 'Kasus dibuat dan ditautkan ke percakapan.')
  }

  const createTicket = (event) => {
    event.preventDefault()
    if (!ticketForm.description.trim()) {
      setError(new Error('Deskripsi tiket wajib diisi.'))
      return
    }
    run('ticket', () => req('/v1/tickets', { method: 'POST', body: { ...ticketForm, description: ticketForm.description.trim(), conversation_id: d.conversation_id, source_channel: 'WEB_CHAT' } }), 'Tiket dibuat dan ditautkan ke percakapan.')
  }

  return (
    <>
      <Card title="Penanganan petugas" sub="Balasan dan status mengikuti handoff yang diterima oleh petugas yang sedang login." wide>
        {notice && <p className="alert info" role="status">{notice}</p>}
        {error && <p className="alert err" role="alert">{error.message || 'Tindakan tidak berhasil.'}</p>}
        {d.handoff?.state === 'QUEUED' && (
          <div className="agent-handoff-actions">
            <p>Handoff menunggu petugas. Terima handoff untuk memulai penanganan.</p>
            <button className="btn primary" type="button" disabled={!!busy} onClick={accept}>
              {busy === 'accept' ? 'Menerima...' : 'Terima handoff'}
            </button>
          </div>
        )}
        {d.handoff?.state === 'ACCEPTED' && !ownsHandoff && (
          <p className="section-note">Handoff diterima oleh {d.handoff.accepted_by || 'petugas lain'}; hanya petugas penerima yang dapat membalas atau menyelesaikannya.</p>
        )}
        {canReply && (
          <form className="agent-reply-form" onSubmit={sendReply}>
            <label htmlFor={`agent-reply-${d.conversation_id}`}>Balas customer</label>
            <textarea
              id={`agent-reply-${d.conversation_id}`}
              value={reply}
              onChange={(event) => setReply(event.target.value)}
              maxLength={4000}
              rows={3}
              placeholder="Tulis balasan untuk customer..."
              disabled={!!busy}
            />
            <div className="agent-reply-actions">
              <small>{reply.length}/4000 karakter</small>
              <button className="btn primary" type="submit" disabled={!!busy || !reply.trim()}>
                {busy === 'reply' ? 'Menyimpan...' : 'Kirim balasan'}
              </button>
            </div>
            <button className="btn" type="button" disabled={!!busy} onClick={resolve}>
              {busy === 'resolve' ? 'Menyelesaikan...' : 'Selesaikan penanganan'}
            </button>
            <small>Status selesai adalah menunggu konfirmasi customer.</small>
          </form>
        )}
        {d.conversation?.status === 'RESOLVED_PENDING_CONFIRMATION' && (
          <p className="alert info" role="status">Penanganan petugas selesai; percakapan menunggu konfirmasi customer.</p>
        )}
        {d.handoff?.state !== 'QUEUED' && !ownsHandoff && d.conversation?.status !== 'RESOLVED_PENDING_CONFIRMATION' && (
          <p className="section-note">Balasan tersedia setelah handoff diterima oleh petugas yang sedang login.</p>
        )}
      </Card>
      {canCreateLinkedWork && (
        <Card title="Buat kasus atau tiket" sub="Memakai endpoint yang tersedia; kasus/tiket ditautkan ke percakapan ini dan backend membuat SLA serta outbox." wide>
          <div className="agent-linked-work-grid">
            <form className="agent-reply-form" onSubmit={createCase}>
              <h3>Kasus</h3>
              <label>Kategori<select value={caseForm.category} onChange={(event) => setCaseForm({ ...caseForm, category: event.target.value })}><option value="TRANSACTION_DISPUTE">Sengketa transaksi</option><option value="SERVICE_FAILURE">Gangguan layanan</option><option value="GENERAL">Umum</option></select></label>
              <label>Severity<select value={caseForm.severity_proposed} onChange={(event) => setCaseForm({ ...caseForm, severity_proposed: event.target.value })}><option value="LOW">Low</option><option value="MEDIUM">Medium</option><option value="HIGH">High</option><option value="CRITICAL">Critical</option></select></label>
              <label>Deskripsi<textarea value={caseForm.description} onChange={(event) => setCaseForm({ ...caseForm, description: event.target.value })} maxLength={4000} rows={3} required /></label>
              <button className="btn primary" type="submit" disabled={!!busy || !caseForm.description.trim()}>{busy === 'case' ? 'Membuat kasus...' : 'Buat kasus'}</button>
            </form>
            <form className="agent-reply-form" onSubmit={createTicket}>
              <h3>Tiket</h3>
              <label>Jenis<select value={ticketForm.type} onChange={(event) => setTicketForm({ ...ticketForm, type: event.target.value })}><option value="GENERAL">Umum</option><option value="COMPLAINT">Keluhan</option><option value="FOLLOW_UP">Tindak lanjut</option></select></label>
              <label>Prioritas<select value={ticketForm.priority} onChange={(event) => setTicketForm({ ...ticketForm, priority: event.target.value })}><option value="LOW">Low</option><option value="NORMAL">Normal</option><option value="HIGH">High</option></select></label>
              <label>Deskripsi<textarea value={ticketForm.description} onChange={(event) => setTicketForm({ ...ticketForm, description: event.target.value })} maxLength={4000} rows={3} required /></label>
              <button className="btn primary" type="submit" disabled={!!busy || !ticketForm.description.trim()}>{busy === 'ticket' ? 'Membuat tiket...' : 'Buat tiket'}</button>
            </form>
          </div>
        </Card>
      )}
    </>
  )
}

export function ConversationWorkbench({ role, session }) {
  const [cid, setCid] = useState(() => new URLSearchParams(window.location.search).get('cid') || 'CNV-DEMO-1')
  const [d, setD] = useState(null)
  const [e, setE] = useState(null)
  const [sug, setSug] = useState(null)
  const [loading, setLoading] = useState(false)

  const open = async (conversationId = cid, keepCurrent = false) => {
    const target = (conversationId || cid || '').trim()
    if (!target) {
      setE(new Error('Masukkan ID percakapan terlebih dahulu.'))
      return
    }
    setE(null)
    if (!keepCurrent) setD(null)
    setSug(null)
    setLoading(true)
    try {
      setD(await req(`/v1/workspace/conversations/${encodeURIComponent(target)}`))
    } catch (err) {
      setE(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const targetCid = new URLSearchParams(window.location.search).get('cid')
    if (targetCid) {
      setCid(targetCid)
      open(targetCid)
    }
  }, [])

  const suggest = async () => {
    setE(null)
    try {
      setSug(await req('/v1/copilot/suggest', { method: 'POST', body: { conversation_id: cid } }))
    } catch (err) {
      setE(err)
    }
  }

  return (
    <>
      <Err e={e} onClose={() => setE(null)} />
      <Card title="Pencarian Percakapan Nasabah" sub="Customer Context, AI Classification, Riwayat Chat, Tool Execution, dan Status Penanganan Petugas.">
        <div className="row">
          <input aria-label="ID percakapan" value={cid} onChange={(e) => setCid(e.target.value)} style={{ minWidth: 260 }} placeholder="Contoh: CNV-..." />
          <button className="btn primary" onClick={() => open()} disabled={loading}>{loading ? 'Memuat...' : 'Buka Percakapan'}</button>
          <button className="btn" onClick={suggest} disabled={!d || loading}>Saran AI Copilot</button>
        </div>
      </Card>
      {sug && (
        <Card title="Rekomendasi AI Copilot" sub="Saran tindakan dan respons otomatis untuk membantu petugas menangani nasabah">
          <div style={{ padding: '12px 16px', background: 'var(--surface-muted, #f8fafc)', borderRadius: '8px', border: '1px solid var(--border)' }}>
            <h4 style={{ margin: '0 0 6px', color: 'var(--primary)' }}>{sug.suggested_action || sug.title || 'Rekomendasi Respons'}</h4>
            <p style={{ margin: 0, fontSize: '14px', lineHeight: 1.6 }}>{sug.summary || sug.response || sug.text || (typeof sug === 'string' ? sug : JSON.stringify(sug))}</p>
          </div>
        </Card>
      )}
      {loading && <Card title="Memuat percakapan"><p role="status">Mengambil transkrip dan informasi penanganan...</p></Card>}
      {d && (
        <>
          {d.handoff_package && (
            <Card title="📦 Paket Konteks Eskalasi Petugas (Handoff Context Package)" sub="Ringkasan otomatis dari Agentic AI untuk panduan petugas (Slide 20 Panduan Mitra)" wide>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                <div style={{ background: '#f8fafc', padding: '14px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                  <h4 style={{ margin: '0 0 8px', color: '#1e293b', fontSize: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    👤 Profil & Status Nasabah
                  </h4>
                  <div style={{ fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <div><strong>ID Nasabah:</strong> <code>{d.handoff_package.customer_id}</code></div>
                    <div><strong>Urgensi Masalah:</strong> <span className={`badge ${d.handoff_package.urgency === 'HIGH' ? 'b-red' : d.handoff_package.urgency === 'MEDIUM' ? 'b-amber' : 'b-blue'}`}>{d.handoff_package.urgency}</span></div>
                    <div><strong>Sentimen:</strong> <span className={`badge ${d.handoff_package.sentiment === 'NEGATIVE' ? 'b-red' : 'b-green'}`}>{d.handoff_package.sentiment}</span></div>
                    <div><strong>Alasan Eskalasi:</strong> <code>{d.handoff_package.reason}</code></div>
                  </div>
                </div>

                <div style={{ background: '#f8fafc', padding: '14px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                  <h4 style={{ margin: '0 0 8px', color: '#1e293b', fontSize: '14px' }}>
                    🧠 Analisis & Kronologi Masalah (AI)
                  </h4>
                  <p style={{ margin: '0 0 8px', fontSize: '13px', lineHeight: 1.5, color: '#334155' }}>
                    <strong>Keluhan Awal:</strong> "{d.handoff_package.summary}"
                  </p>
                  {d.handoff_package.last_message && d.handoff_package.last_message !== d.handoff_package.summary && (
                    <p style={{ margin: '0 0 8px', fontSize: '12px', lineHeight: 1.4, color: '#64748b' }}>
                      <strong>Pesan Terakhir:</strong> "{d.handoff_package.last_message}"
                    </p>
                  )}
                  <div style={{ fontSize: '12px', color: '#64748b' }}>
                    <strong>Intensi Terdeteksi:</strong> <code>{d.handoff_package.intent_code}</code> ({Math.round((d.handoff_package.confidence || 0.85) * 100)}%)
                  </div>
                </div>

                <div style={{ background: '#eff6ff', padding: '14px', borderRadius: '8px', border: '1px solid #bfdbfe' }}>
                  <h4 style={{ margin: '0 0 8px', color: '#1e40af', fontSize: '14px' }}>
                    🛠️ Riwayat Tindakan AI (Tools)
                  </h4>
                  {d.handoff_package.tools_called?.length ? (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
                      {d.handoff_package.tools_called.map((tool, idx) => (
                        <span key={idx} className="badge b-blue" style={{ fontSize: '11px' }}>
                          ✓ {tool}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '8px' }}>Tidak ada tools otomatis yang dijalankan.</div>
                  )}
                  <h4 style={{ margin: '8px 0 4px', color: '#1e40af', fontSize: '13px' }}>
                    💡 Rekomendasi Tindakan untuk Petugas:
                  </h4>
                  <p style={{ margin: 0, fontSize: '13px', lineHeight: 1.5, color: '#1e3a8a', fontWeight: 600 }}>
                    {d.handoff_package.recommended_action}
                  </p>
                </div>
              </div>
            </Card>
          )}
          <div className="grid g2 mt">
            <Card title={`Status Handoff • ${d.conversation_id}`} sub={d.conversation?.intent_current || 'Tingkat risiko dan eskalasi petugas'}>
              {d.handoff ? (
                <div className="kv">
                  <dt>Alasan Eskalasi</dt><dd>{d.handoff.reason_code}</dd>
                  <dt>Status Handoff</dt><dd><StateBadge v={d.handoff.state} /></dd>
                  <dt>Skor Prioritas</dt><dd><b>{d.handoff.priority_score}</b></dd>
                  <dt>Tingkat Severity</dt><dd><Sev v={d.handoff.severity} /></dd>
                  <dt>Ditangani Oleh</dt><dd><b>{d.handoff.accepted_by || 'Belum Diterima'}</b></dd>
                </div>
              ) : <Empty text="Belum ada eskalasi handoff untuk percakapan ini." />}
            </Card>
            <Card title={`Kasus Terkait (${d.cases.length}) • Tiket (${d.tickets.length})`}>
              <div className="kv">
                {d.cases.map((c) => (<React.Fragment key={c.case_id}><dt>{c.case_id}</dt><dd><StateBadge v={c.status} /> <Sev v={c.severity_confirmed} /></dd></React.Fragment>))}
                {d.tickets.map((t) => (<React.Fragment key={t.ticket_id}><dt>{t.ticket_id}</dt><dd><StateBadge v={t.status} /></dd></React.Fragment>))}
                {!d.cases.length && !d.tickets.length && <dt>Tidak ada tiket/kasus aktif</dt>}
              </div>
              <h3 className="mt">Target SLA</h3>
              <div className="kv">{d.sla.map((s) => (<React.Fragment key={s.sla_id}><dt>{s.sla_id}</dt><dd><StateBadge v={s.state} /> • Batas: {new Date(s.resolution_due_at).toLocaleString('id-ID')}</dd></React.Fragment>))}</div>
            </Card>
            <Card title={`Transkrip Percakapan (${d.messages?.length || 0} Pesan)`} sub={d.conversation ? `Status: ${d.conversation.status} • Bahasa: ${d.conversation.language}` : 'Data percakapan'} wide>
              {!d.messages?.length ? <Empty text="Belum ada pesan dalam percakapan ini." /> : (
                <ul className="timeline">{d.messages.map((m) => (
                  <li key={m.message_id || m.sequence_no}><b>{m.author_type === 'CUSTOMER' ? 'Customer' : m.author_type === 'AI_AGENT' ? 'Asisten AI' : m.author_type === 'HUMAN_AGENT' ? 'Petugas' : m.author_type} · {m.direction}</b>
                    <div className="t">{m.occurred_at ? new Date(m.occurred_at).toLocaleString('id-ID') : ''}{m.author_type === 'HUMAN_AGENT' && m.author_id ? ` · ${m.author_id}` : ''}</div><p>{m.content}</p>
                    {!!m.citations?.length && <small>Sumber Rujukan: {m.citations.map((c) => c.title || c.article_id || 'sumber').join(', ')}</small>}
                  </li>))}</ul>
              )}
              <div className="grid g2 mt">
                <div>
                  <h3>Klasifikasi Intent AI</h3>
                  {d.intents?.length ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {d.intents.map((it, idx) => (
                        <div key={idx} style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: '6px', background: 'var(--surface-muted, #f8fafc)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <strong>{it.intent_code || it.intent || 'INQUIRY'}</strong>
                            <span className="badge b-blue">{Math.round((it.confidence || it.confidence_hint || 0.9) * 100)}% Confidence</span>
                          </div>
                          <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--muted)' }}>
                            Kategori: {it.category || 'INQUIRY'} • Decision: {it.decision || 'ACT'}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : <Empty text="Belum ada klasifikasi intent." />}
                </div>
                <div>
                  <h3>Eksekusi Tool Perbankan</h3>
                  {d.tool_calls?.length ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {d.tool_calls.map((tc, idx) => (
                        <div key={idx} style={{ padding: '8px 12px', border: '1px solid var(--border)', borderRadius: '6px', background: 'var(--surface-muted, #f8fafc)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <strong>{tc.tool || tc.tool_name || 'Tool'}</strong>
                            <span className="badge b-green">Executed</span>
                          </div>
                          <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--muted)' }}>
                            Policy Decision ID: {tc.policy_decision_id || 'POL-DEFAULT'}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : <Empty text="Belum ada eksekusi tool otomatis." />}
                </div>
              </div>
            </Card>
            <AgentConversationActions d={d} role={role} session={session} onRefresh={open} />
          </div>
        </>
      )}
    </>
  )
}

export const Conv = ConversationWorkbench
export default ConversationWorkbench
