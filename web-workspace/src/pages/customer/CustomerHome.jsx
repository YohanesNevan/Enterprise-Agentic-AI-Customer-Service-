import React from 'react'
import { navigate } from '../../shared/navigation.js'

export function CustomerHome() {
  return (
    <div className="customer-home">
      <section className="customer-intro">
        <div className="intro-copy">
          <p className="eyebrow"><span className="eyebrow-rule" />EAICS CUSTOMER SERVICE PORTAL</p>
          <h1>Pusat Bantuan &<br /><em>Layanan Digital Terpadu</em></h1>
          <p className="intro-description">Solusi terpadu untuk konsultasi produk, bantuan transaksi, pembuatan tiket pengaduan resmi, dan pelacakan status penanganan secara real-time.</p>
          <div className="intro-primary-row">
            <a className="btn primary intro-cta" href="/customer/chat" onClick={(e) => { e.preventDefault(); navigate('/customer/chat') }}>
              Mulai Live Chat & Assistant <span aria-hidden="true">↗</span>
            </a>
            <span className="intro-caption">Didukung AI Agentik dan integrasi langsung ke staf operasional.</span>
          </div>
        </div>
        <aside className="welcome-panel" aria-label="Layanan Utama">
          <div className="welcome-panel-top"><span className="panel-index">PORTAL</span><span className="panel-mark" aria-hidden="true">★</span></div>
          <p className="eyebrow">MENU CEPAT</p>
          <h2>Apa yang Anda butuhkan?</h2>
          <p className="welcome-panel-copy">Pilih layanan di bawah ini. Anda dapat bertanya langsung ke AI atau mendaftarkan pengaduan resmi.</p>
          <a className="welcome-link" href="/customer/chat" onClick={(e) => { e.preventDefault(); navigate('/customer/chat') }}>
            <span><strong>Live Chat & Tanya AI</strong><small>Konsultasi produk & info rekening</small></span><b aria-hidden="true">↗</b>
          </a>
          <a className="welcome-link" href="/customer/requests/new" onClick={(e) => { e.preventDefault(); navigate('/customer/requests/new') }}>
            <span><strong>Pengaduan Resmi (Buat Tiket)</strong><small>Lapor kendala & sengketa transaksi</small></span><b aria-hidden="true">↗</b>
          </a>
          <a className="welcome-link" href="/customer/requests" onClick={(e) => { e.preventDefault(); navigate('/customer/requests') }}>
            <span><strong>Track Status & SLA Tiket</strong><small>Cek progres penanganan tiket Anda</small></span><b aria-hidden="true">↗</b>
          </a>
        </aside>
      </section>
      <section className="customer-services" aria-labelledby="service-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">FITUR LAYANAN</p>
            <h2 id="service-heading">Akses Layanan Pelanggan</h2>
          </div>
          <span className="section-note">Gunakan akun pelanggan terdaftar untuk akses penuh.</span>
        </div>
        <div className="customer-actions" aria-label="Pilihan bantuan">
          <a className="portal-action" href="/customer/chat" onClick={(e) => { e.preventDefault(); navigate('/customer/chat') }}>
            <span className="action-number">01</span>
            <strong>Live Chat & AI Assistant</strong>
            <span>Tanya jawab seputar informasi produk, layanan, dan panduan transaksi.</span>
            <b aria-hidden="true">↗</b>
          </a>
          <a className="portal-action" href="/customer/requests/new" onClick={(e) => { e.preventDefault(); navigate('/customer/requests/new') }}>
            <span className="action-number">02</span>
            <strong>Pengaduan Resmi (Submit Ticket)</strong>
            <span>Laporkan kendala transaksi, kartu, atau masalah layanan untuk investigasi.</span>
            <b aria-hidden="true">↗</b>
          </a>
          <a className="portal-action" href="/customer/requests" onClick={(e) => { e.preventDefault(); navigate('/customer/requests') }}>
            <span className="action-number">03</span>
            <strong>Track Status & SLA</strong>
            <span>Pantau batas waktu (SLA) dan status penyelesaian tiket aktif Anda.</span>
            <b aria-hidden="true">↗</b>
          </a>
          <a className="portal-action" href="/customer/conversations" onClick={(e) => { e.preventDefault(); navigate('/customer/conversations') }}>
            <span className="action-number">04</span>
            <strong>Riwayat Chat (History)</strong>
            <span>Buka kembali transkrip riwayat percakapan Anda sebelumnya.</span>
            <b aria-hidden="true">↗</b>
          </a>
        </div>
      </section>
      <p className="portal-note"><span aria-hidden="true">◇</span> Masuk akun diperlukan untuk fitur pengaduan dan riwayat personal.</p>
    </div>
  )
}

export default CustomerHome
