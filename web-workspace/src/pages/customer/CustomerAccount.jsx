import React from 'react'
import { devCustomerLogout } from '../../api.js'
import { navigate } from '../../shared/navigation.js'

export default function CustomerAccount({ session }) {
  const principal = session?.principal || {}
  return <section className="customer-work-page customer-account-page">
    <div className="customer-page-intro"><p className="eyebrow"><span className="eyebrow-rule" />AKUN PELANGGAN</p><h2>Akun layanan Anda.</h2><p>Informasi yang ditampilkan berasal dari sesi masuk saat ini.</p></div>
    <dl className="customer-account-details">
      <div><dt>ID akun</dt><dd>{principal.actor_id || 'Tidak tersedia'}</dd></div>
      <div><dt>Jenis akun</dt><dd>{principal.role === 'customer' ? 'Pelanggan' : 'Tidak diketahui'}</dd></div>
      <div><dt>Sesi</dt><dd><span className="customer-session-mark" aria-hidden="true" />Aktif</dd></div>
    </dl>
    <p className="customer-scope-note">Pengubahan nama dan informasi kontak belum tersedia untuk akun lokal ini. Riwayat percakapan disimpan sebagai jejak layanan dan belum dapat dihapus dari portal.</p>
    <div className="customer-form-actions"><a className="btn" href="/customer/conversations" onClick={(event) => { event.preventDefault(); navigate('/customer/conversations') }}>Lihat riwayat</a><button className="btn" type="button" onClick={() => { devCustomerLogout(); navigate('/customer/login') }}>Keluar dari akun</button></div>
  </section>
}
