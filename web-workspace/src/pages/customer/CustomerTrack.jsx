import React, { useCallback, useEffect, useState } from 'react'
import { req, devCustomerLogout } from '../../api.js'
import { customerConversationState, navigate } from '../../shared/navigation.js'
import { Empty } from '../../shared/ui.jsx'

export function CustomerTrack() {
  const [items, setItems] = useState([])
  const [tickets, setTickets] = useState([])
  const [nextCursor, setNextCursor] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async (cursor = null, append = false) => {
    setLoading(true)
    setError(null)
    try {
      const suffix = cursor ? `?limit=20&cursor=${encodeURIComponent(cursor)}` : '?limit=20'
      const [convRes, tktRes] = await Promise.all([
        req(`/v1/customer/conversations${suffix}`).catch(() => ({ items: [] })),
        req('/v1/customer/complaints').catch(() => req('/v1/tickets').catch(() => []))
      ])
      setItems((current) => append ? [...current, ...(convRes.items || [])] : convRes.items || [])
      setNextCursor(convRes.next_cursor || null)
      if (!append) {
        setTickets(Array.isArray(tktRes) ? tktRes : [])
      }
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <section className="customer-work-page customer-track-page">
      <div className="customer-page-intro customer-track-intro">
        <div>
          <p className="eyebrow"><span className="eyebrow-rule" />AKTIVITAS LAYANAN</p>
          <h2>Permintaan & Pengaduan Anda.</h2>
          <p>Pantau tiket pengaduan aktif dan riwayat percakapan layanan yang tersimpan pada akun Anda.</p>
        </div>
        <div className="row">
          <button className="btn sm" type="button" onClick={() => load()}>Muat ulang</button>
          <a className="btn primary" href="/customer/requests/new" onClick={(event) => { event.preventDefault(); navigate('/customer/requests/new') }}>Kirim permintaan</a>
        </div>
      </div>
      {error && <p className="alert err" role="alert">{error.message}</p>}

      {/* Section Tiket Pengaduan */}
      {tickets.length > 0 && (
        <div style={{ marginBottom: '2rem' }}>
          <h3 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: '0.5rem' }}>Tiket Pengaduan & Sengketa ({tickets.length})</h3>
          <p style={{ color: 'var(--muted)', fontSize: '0.875rem', marginBottom: '1rem' }}>Tiket investigasi resmi yang diterbitkan untuk menangani laporan sengketa transaksi atau pengaduan Anda.</p>
          <ul className="customer-request-list">
            {tickets.map((t) => (
              <li key={t.ticket_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
                <div>
                  <span className="customer-request-state" style={{ background: t.status === 'OPEN' ? '#e0f2fe' : '#dcfce7', color: t.status === 'OPEN' ? '#0369a1' : '#15803d', padding: '2px 8px', borderRadius: '4px' }}>
                    {t.status === 'OPEN' ? 'Sedang Diproses' : t.status === 'RESOLVED' ? 'Selesai' : t.status}
                  </span>
                  <h4 style={{ margin: '0.35rem 0', fontWeight: 600, fontSize: '1rem' }}>{t.customer_reference || t.ticket_id} &bull; {t.category || t.type}</h4>
                  <p style={{ margin: '0.2rem 0', color: 'var(--fg)', fontSize: '0.9rem' }}>{t.description}</p>
                  <time style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                    Prioritas: {t.priority || 'NORMAL'} &bull; Dibuat: {t.created_at ? new Date(t.created_at).toLocaleString('id-ID') : '-'}
                    {t.resolution_due_at && ` • Target SLA: ${new Date(t.resolution_due_at).toLocaleString('id-ID')}`}
                  </time>
                </div>
                {t.conversation_id && (
                  <a className="btn sm" href={`/customer/chat?conversation_id=${encodeURIComponent(t.conversation_id)}`} onClick={(event) => { event.preventDefault(); navigate(`/customer/chat?conversation_id=${encodeURIComponent(t.conversation_id)}`) }}>
                    Buka percakapan
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Section Riwayat Percakapan */}
      <h3 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: '0.5rem' }}>Percakapan Layanan ({items.length})</h3>
      {loading && !items.length ? (
        <Empty text="Memuat percakapan..." />
      ) : !items.length ? (
        <div className="customer-empty-state">
          <h3>Belum ada percakapan layanan.</h3>
          <p>Kirim pesan layanan untuk memulai.</p>
          <a className="btn primary" href="/customer/requests/new" onClick={(event) => { event.preventDefault(); navigate('/customer/requests/new') }}>Kirim permintaan</a>
        </div>
      ) : (
        <ul className="customer-request-list">
          {items.map((item) => (
            <li key={item.conversation_id}>
              <div>
                <span className="customer-request-state">{customerConversationState(item.status)}</span>
                <h3>Percakapan layanan</h3>
                <p>{item.conversation_id}</p>
                <time dateTime={item.last_activity_at}>Aktivitas terakhir {new Date(item.last_activity_at).toLocaleString('id-ID')}</time>
              </div>
              <a className="btn sm" href={`/customer/chat?conversation_id=${encodeURIComponent(item.conversation_id)}`} onClick={(event) => { event.preventDefault(); navigate(`/customer/chat?conversation_id=${encodeURIComponent(item.conversation_id)}`) }}>
                Buka percakapan
              </a>
            </li>
          ))}
        </ul>
      )}
      {nextCursor && <button className="btn" type="button" disabled={loading} onClick={() => load(nextCursor, true)}>{loading ? 'Memuat...' : 'Muat permintaan sebelumnya'}</button>}
      <p className="customer-scope-note">Tiket investigasi dan percakapan tersinkronisasi secara otomatis dengan pusat operasional EAICS.</p>
    </section>
  )
}

export function CustomerAccount({ session }) {
  const principal = session?.principal || {}
  return (
    <section className="customer-work-page customer-account-page">
      <div className="customer-page-intro">
        <p className="eyebrow"><span className="eyebrow-rule" />AKUN PELANGGAN</p>
        <h2>Akun layanan Anda.</h2>
        <p>Informasi yang ditampilkan berasal dari sesi masuk saat ini.</p>
      </div>
      <dl className="customer-account-details">
        <div><dt>ID akun</dt><dd>{principal.actor_id || 'Tidak tersedia'}</dd></div>
        <div><dt>Jenis akun</dt><dd>{principal.role === 'customer' ? 'Pelanggan' : 'Tidak diketahui'}</dd></div>
        <div><dt>Sesi</dt><dd><span className="customer-session-mark" aria-hidden="true" />Aktif</dd></div>
      </dl>
      <p className="customer-scope-note">Pengubahan nama dan informasi kontak belum tersedia untuk akun lokal ini. Riwayat percakapan disimpan sebagai jejak layanan dan belum dapat dihapus dari portal.</p>
      <div className="customer-form-actions">
        <a className="btn" href="/customer/conversations" onClick={(event) => { event.preventDefault(); navigate('/customer/conversations') }}>Lihat riwayat</a>
        <button className="btn" type="button" onClick={() => { devCustomerLogout(); navigate('/customer/login') }}>Keluar dari akun</button>
      </div>
    </section>
  )
}

export default CustomerTrack
