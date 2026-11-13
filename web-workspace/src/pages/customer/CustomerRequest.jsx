import React, { useRef, useState } from 'react'
import { ApiError, req } from '../../api.js'
import { navigate } from '../../shared/navigation.js'

export default function CustomerRequest() {
  const [tab, setTab] = useState('complaint')
  const [category, setCategory] = useState('TRANSACTION_DISPUTE')
  const [title, setTitle] = useState('')
  const [reference, setReference] = useState('')
  const [description, setDescription] = useState('')
  const [text, setText] = useState('')
  const [error, setError] = useState(null)
  const [sending, setSending] = useState(false)
  const [successTicket, setSuccessTicket] = useState(null)
  const [retryInfo, setRetryInfo] = useState(null)
  const submitLock = useRef(false)

  const submitComplaint = async (event) => {
    event.preventDefault()
    if (!description.trim() || submitLock.current) return
    submitLock.current = true
    setSending(true)
    setError(null)
    try {
      const result = await req('/v1/customer/complaints', {
        method: 'POST',
        body: {
          category,
          title: title.trim() || undefined,
          description: description.trim(),
          reference: reference.trim() || undefined,
        },
      })
      setSuccessTicket(result)
    } catch (err) {
      setError(err)
    } finally {
      submitLock.current = false
      setSending(false)
    }
  }

  const submitMessage = async (event) => {
    event.preventDefault()
    const content = text.trim()
    if (!content || submitLock.current) return
    submitLock.current = true
    setSending(true)
    setError(null)
    const idempotencyKey = retryInfo?.text === content ? retryInfo.key : crypto.randomUUID()
    try {
      const result = await req('/v1/chat/messages', {
        method: 'POST',
        body: { text: content },
        headers: { 'Idempotency-Key': idempotencyKey },
      })
      if (!result.conversation_id) throw new ApiError(502, 'MISSING_CONVERSATION', 'Layanan belum mengembalikan referensi percakapan.')
      navigate(`/customer/chat?conversation_id=${encodeURIComponent(result.conversation_id)}`)
    } catch (err) {
      setRetryInfo({ text: content, key: idempotencyKey })
      setError(err)
    } finally {
      submitLock.current = false
      setSending(false)
    }
  }

  if (successTicket) {
    return (
      <section className="customer-work-page customer-request-page">
        <div className="card" style={{ maxWidth: '640px', margin: '2rem auto', textAlign: 'center', padding: '2.5rem 2rem' }}>
          <div style={{ width: '56px', height: '56px', borderRadius: '50%', background: '#dcfce7', color: '#16a34a', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.25rem', fontSize: '24px' }}>✓</div>
          <span className="customer-request-state" style={{ background: '#e0f2fe', color: '#0369a1', padding: '4px 12px', borderRadius: '12px', fontSize: '12px', fontWeight: 600 }}>PENGADUAN DITERIMA</span>
          <h2 style={{ margin: '1rem 0 0.5rem', fontSize: '1.5rem', fontWeight: 700 }}>Nomor Tiket: {successTicket.customer_reference || successTicket.ticket_id}</h2>
          <p style={{ color: 'var(--muted)', fontSize: '0.95rem', marginBottom: '1.5rem' }}>
            Pengaduan resmi Anda telah tercatat dalam sistem dengan estimasi SLA penanganan prioritas.
          </p>
          <div style={{ background: 'var(--surface-muted, #f8fafc)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', textAlign: 'left', fontSize: '0.875rem' }}>
            <p style={{ margin: '0.25rem 0' }}><strong>Kategori:</strong> {successTicket.category || category}</p>
            {successTicket.sla?.first_response_due_at && (
              <p style={{ margin: '0.25rem 0' }}><strong>Target Respons Pertama:</strong> {new Date(successTicket.sla.first_response_due_at).toLocaleString('id-ID')}</p>
            )}
            <p style={{ margin: '0.25rem 0' }}><strong>Status:</strong> Sedang Dalam Antrean Penanganan</p>
          </div>
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button className="btn primary" onClick={() => navigate('/customer/requests')}>Lihat di Status Pelacakan</button>
            <button className="btn" onClick={() => { setSuccessTicket(null); setTitle(''); setDescription(''); setReference('') }}>Ajukan Pengaduan Lain</button>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="customer-work-page customer-request-page">
      <div className="customer-page-intro">
        <p className="eyebrow"><span className="eyebrow-rule" />PERMINTAAN & PENGADUAN</p>
        <h2>Ajukan Permintaan atau Pengaduan Layanan</h2>
        <p>Pilih pengaduan resmi untuk mendapatkan nomor tiket investigasi, atau kirimkan pesan percakapan langsung ke asisten layanan.</p>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '1px solid var(--line)', paddingBottom: '0.5rem' }}>
        <button
          type="button"
          className={`btn ${tab === 'complaint' ? 'primary' : ''}`}
          style={{ padding: '6px 16px', fontSize: '13px' }}
          onClick={() => { setTab('complaint'); setError(null) }}
        >
          Pengaduan Resmi (Buat Tiket)
        </button>
        <button
          type="button"
          className={`btn ${tab === 'message' ? 'primary' : ''}`}
          style={{ padding: '6px 16px', fontSize: '13px' }}
          onClick={() => { setTab('message'); setError(null) }}
        >
          Pesan Percakapan Langsung
        </button>
      </div>

      {tab === 'complaint' ? (
        <form className="customer-request-form" onSubmit={submitComplaint}>
          <div>
            <label htmlFor="complaint-category" style={{ display: 'block', marginBottom: '6px' }}>Kategori Pengaduan</label>
            <select
              id="complaint-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--line-strong)', background: 'var(--surface)', color: 'var(--ink)' }}
            >
              <option value="TRANSACTION_DISPUTE">Sengketa Transaksi (Debit Ganda / Gagal Transfer / Saldo Berkurang)</option>
              <option value="CARD_ISSUE">Kendala Kartu ATM / Debit (Tertelan / Rusak / Terblokir)</option>
              <option value="ACCOUNT_ACCESS">Kendala Akses Rekening / Mobile Banking</option>
              <option value="SERVICE_QUALITY">Keluhan Kualitas Pelayanan Petugas</option>
              <option value="GENERAL">Pengaduan Umum Lainnya</option>
            </select>
          </div>

          <div>
            <label htmlFor="complaint-ref" style={{ display: 'block', marginBottom: '6px' }}>Nomor Referensi Terkait (Opsional)</label>
            <input
              id="complaint-ref"
              type="text"
              placeholder="Contoh: No. Transaksi (TRX-1234), 4 digit akhir kartu (4821), atau No. Rekening"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              maxLength={80}
              style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--line-strong)', background: 'var(--surface)', color: 'var(--ink)' }}
            />
          </div>

          <div>
            <label htmlFor="complaint-title" style={{ display: 'block', marginBottom: '6px' }}>Judul Pengaduan</label>
            <input
              id="complaint-title"
              type="text"
              placeholder="Ringkasan kendala Anda"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={150}
              required
              style={{ width: '100%', padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--line-strong)', background: 'var(--surface)', color: 'var(--ink)' }}
            />
          </div>

          <div>
            <label htmlFor="complaint-desc" style={{ display: 'block', marginBottom: '6px' }}>Rincian Masalah</label>
            <textarea
              id="complaint-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={4000}
              rows={5}
              required
              placeholder="Jelaskan secara lengkap kronologi masalah, waktu kejadian, dan tindakan yang diharapkan..."
            />
            <div className="customer-form-meta">
              <p>Jangan sertakan PIN, kata sandi, atau CVV kartu perbankan Anda.</p>
              <span>{description.length}/4000</span>
            </div>
          </div>

          {error && <p className="alert err" role="alert">{error.message || 'Gagal mengirimkan pengaduan. Silakan coba kembali.'}</p>}

          <div className="customer-form-actions">
            <a className="btn" href="/customer/requests" onClick={(e) => { e.preventDefault(); navigate('/customer/requests') }}>Batal</a>
            <button className="btn primary" type="submit" disabled={sending || !description.trim()}>
              {sending ? 'Mendaftarkan Tiket...' : 'Kirim Pengaduan Resmi'}
            </button>
          </div>
        </form>
      ) : (
        <form className="customer-request-form" onSubmit={submitMessage}>
          <label htmlFor="service-request">Permintaan Anda</label>
          <textarea
            id="service-request"
            value={text}
            onChange={(event) => setText(event.target.value)}
            maxLength={4000}
            rows={6}
            required
            aria-describedby="request-guidance"
            placeholder="Jelaskan kebutuhan atau pertanyaan Anda..."
          />
          <div className="customer-form-meta">
            <p id="request-guidance">Pesan akan diteruskan ke asisten cerdas virtual atau staf operasional.</p>
            <span>{text.length}/4000</span>
          </div>
          {error && <p className="alert err" role="alert">{error.message} Pesan tetap di formulir; coba lagi untuk mengirim ulang.</p>}
          <div className="customer-form-actions">
            <a className="btn" href="/customer/chat" onClick={(event) => { event.preventDefault(); navigate('/customer/chat') }}>Kembali ke chat</a>
            <button className="btn primary" type="submit" disabled={sending || !text.trim()}>
              {sending ? 'Mengirim...' : retryInfo?.text === text.trim() ? 'Coba kirim lagi' : 'Kirim pesan'}
            </button>
          </div>
        </form>
      )}
    </section>
  )
}
