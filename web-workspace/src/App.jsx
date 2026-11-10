// EAICS Workspace — UI layanan pelanggan agentik (Kelompok B, TRD §4.13, NFR-08).
// Semua data live dari backend via proxy Vite (/v1, /internal -> :8000).
import React, { useCallback, useEffect, useRef, useState } from 'react'
import './app.css'
import {
  req, ApiError, getAuthSession, subscribeAuth, devUniversalLogin, devCustomerLogin, devStaffLogin, devCustomerLogout, isDevelopmentAuthEnabled, isDevelopmentStaffAuthEnabled,
  CLOSURE_ITEMS, QA_FIELDS, QA_AUTO_FAIL, QA_FINDING_TYPES, SEVERITIES, REASONS,
} from './api.js'
import { KNOWLEDGE_WORKSPACE_ROLES, staffNavigationFor } from './workspace-access.js'
const CUSTOMER_LINKS = [
  ['/customer/chat', 'Live Chat & AI Assistant'],
  ['/customer/requests/new', 'Pengaduan & Tiket (Submit)'],
  ['/customer/requests', 'Track Status & SLA'],
  ['/customer/conversations', 'Riwayat Chat (History)'],
  ['/customer/account', 'Profil Akun'],
]
const ROUTES = {
  '/login': { title: 'Portal Login', audience: 'public', page: 'login' },
  '/customer/login': { title: 'Customer Login', audience: 'public', page: 'login' },
  '/staff/login': { title: 'Staff Workspace Login', audience: 'public', page: 'login' },
  '/customer/chat': { title: 'Customer Live Chat & Assistant', audience: 'customer', page: 'customer-chat' },
  '/customer/requests/new': { title: 'Submit Complaint & Ticket', audience: 'customer', page: 'customer-request' },
  '/customer/requests': { title: 'Track Status & SLA Tickets', audience: 'customer', page: 'customer-track' },
  '/customer/conversations': { title: 'Conversation History', audience: 'customer', page: 'customer-history' },
  '/customer/account': { title: 'Customer Account Profile', audience: 'customer', page: 'customer-account' },
  '/agent/queue': { title: 'Queue & Handoff Management', audience: ['cs_agent', 'supervisor'], page: 'queue' },
  '/agent/conversations': { title: 'Customer Conversations Workbench', audience: ['cs_agent', 'supervisor'], page: 'conv' },
  '/agent/cases': { title: 'Tickets & Case Management', audience: ['cs_agent', 'supervisor'], page: 'cases' },
  '/supervisor': { title: 'Supervisor Operations Dashboard', audience: 'supervisor', page: 'dash' },
  '/supervisor/queue': { title: 'Queue & Escalation Monitor', audience: 'supervisor', page: 'queue' },
  '/supervisor/cases': { title: 'Cases & Dispute Resolution', audience: 'supervisor', page: 'cases' },
  '/supervisor/approvals': { title: 'Approval Requests (Dual Custody)', audience: 'supervisor', page: 'approvals' },
  '/supervisor/sla': { title: 'SLA Monitoring & Notifications', audience: 'supervisor', page: 'sla' },
  '/supervisor/audit': { title: 'Audit Trail & Compliance', audience: 'supervisor', page: 'audit' },
  '/complaints': { title: 'Complaint & Dispute Officer', audience: 'complaint_officer', unit: '09' },
  '/knowledge': { title: 'Knowledge Base Manager', audience: KNOWLEDGE_WORKSPACE_ROLES, page: 'knowledge' },
  '/qa': { title: 'QA Review & Quality Assurance', audience: 'qa_analyst', page: 'qa' },
  '/management': { title: 'Executive Analytics & Performance', audience: 'management', page: 'analytics' },
  '/admin': { title: 'System Administration', audience: 'admin', unit: '14' },
}
const CUSTOMER_CONVERSATION_STATES = {
  NEW: 'Percakapan baru', ACTIVE_AI: 'Sedang ditangani layanan', AWAITING_CUSTOMER: 'Menunggu balasan Anda',
  AWAITING_AUTH: 'Menunggu verifikasi', AWAITING_EVIDENCE: 'Menunggu informasi tambahan',
  PENDING_HANDOFF: 'Menunggu petugas', ACTIVE_HUMAN: 'Dialihkan ke petugas',
  RESOLVED_PENDING_CONFIRMATION: 'Menunggu konfirmasi Anda', CLOSED: 'Selesai',
  ABANDONED: 'Tidak dilanjutkan', REOPENED: 'Dibuka kembali',
}
function customerConversationState(status) { return CUSTOMER_CONVERSATION_STATES[status] || 'Status layanan diperbarui' }
function navigate(path) { if (window.location.pathname !== path) window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')) }
function StatePanel({ title, children }) { return <section className="state-panel" role="status"><h2>{title}</h2><p>{children}</p></section> }

/* ---------- komponen kecil ---------- */
function Card({ title, sub, children, wide }) {
  return (
    <div className="card" style={wide ? { gridColumn: '1 / -1' } : undefined}>
      {title && <h3>{title}</h3>}
      {sub && <p className="sub">{sub}</p>}
      {children}
    </div>
  )
}
function Err({ e, onClose }) {
  if (!e) return null
  return <p className="alert err">{e.message || String(e)}{onClose && <button className="btn sm" style={{ marginLeft: 10 }} onClick={onClose}>Tutup</button>}</p>
}
function Empty({ text }) { return <div className="empty">{text}</div> }
function Json({ data }) { return <pre className="dump">{JSON.stringify(data, null, 2)}</pre> }
function Sev({ v }) {
  const cls = v === 'CRITICAL' ? 'b-red' : v === 'HIGH' ? 'b-amber' : v === 'MEDIUM' ? 'b-blue' : 'b-green'
  return <span className={`badge ${cls}`}>{v || '-'}</span>
}
function StateBadge({ v }) {
  const s = String(v || '')
  const cls = /CLOSED|SENT|ACCEPTED|GRANTED/.test(s) ? 'b-green'
    : /BREACHED|DENIED|OPEN|QUEUED|PENDING|RUNNING|AT_RISK/.test(s) ? 'b-amber'
    : /REOPENED|REJECT|FAIL|BLOCK/.test(s) ? 'b-red' : 'b-gray'
  return <span className={`badge ${cls}`}>{s || '-'}</span>
}
function useForm(initial) {
  const [v, setV] = useState(initial)
  const set = (k) => (e) => {
    const t = e.target
    const val = t.type === 'checkbox' ? t.checked : t.value
    setV((o) => ({ ...o, [k]: val }))
  }
  const reset = () => setV(initial)
  return [v, set, reset, setV]
}

/* ================= App ================= */
export default function App() {
  const [path, setPath] = useState(window.location.pathname)
  const [session, setSession] = useState(undefined)
  const [authError, setAuthError] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [navCollapsed, setNavCollapsed] = useState(false)
  const menuButtonRef = useRef(null)
  const navRef = useRef(null)
  const menuWasOpen = useRef(false)
  useEffect(() => {
    const sync = () => { setPath(window.location.pathname); setMenuOpen(false) }
    window.addEventListener('popstate', sync)
    return () => window.removeEventListener('popstate', sync)
  }, [])
  useEffect(() => {
    if (menuOpen) navRef.current?.querySelector('a, button')?.focus()
    else if (menuWasOpen.current) menuButtonRef.current?.focus()
    menuWasOpen.current = menuOpen
  }, [menuOpen])
  useEffect(() => {
    let active = true
    const load = async () => { try { const value = await getAuthSession(); if (active) { setSession(value); setAuthError(false) } } catch { if (active) { setSession(null); setAuthError(true) } } }
    const unsubscribe = subscribeAuth(load)
    load()
    return () => { active = false; unsubscribe() }
  }, [])

  const route = ROUTES[path]
  const role = session?.principal?.role
  const customerRoute = route?.audience === 'customer'
  const isPublic = path === '/' || path === '/customer/login' || path === '/staff/login' || path === '/login'
  const permitted = customerRoute ? role === 'customer' : Array.isArray(route?.audience) ? route.audience.includes(role) : route?.audience === role
  const needsAuth = !isPublic && !session
  const navItems = isPublic || (customerRoute && (!session || role === 'customer')) ? CUSTOMER_LINKS : staffNavigationFor(role)
  const title = route?.title || (isPublic ? 'Layanan pelanggan' : 'Halaman tidak ditemukan')
  const Page = (route?.page === 'customer-login' || route?.page === 'staff-login' || route?.page === 'login') ? UniversalLogin : route?.page === 'customer-chat' ? CustomerChat : route?.page === 'customer-history' ? CustomerHistory : route?.page === 'customer-request' ? CustomerRequest : route?.page === 'customer-track' ? CustomerTrack : route?.page === 'customer-account' ? CustomerAccount : route?.page === 'dash' ? Dash : route?.page === 'queue' ? Queue : route?.page === 'conv' ? Conv : route?.page === 'cases' ? Cases : route?.page === 'approvals' ? Approvals : route?.page === 'qa' ? QA : route?.page === 'analytics' ? Analytics : route?.page === 'sla' ? SLA : route?.page === 'audit' ? Audit : route?.page === 'knowledge' ? KnowledgeManager : null
  const customerShell = isPublic || customerRoute
  let content
  if (path === '/') content = <CustomerHome />
  else if (path === '/customer/login' || path === '/staff/login' || path === '/login') content = <UniversalLogin />

  else if (!route) content = <StatePanel title="Halaman tidak ditemukan">Alamat ini tidak tersedia.</StatePanel>
  else if (session === undefined) content = <StatePanel title="Memeriksa sesi">Sesi autentikasi sedang diperiksa.</StatePanel>
  else if (authError) content = <StatePanel title="Sesi tidak dapat diperiksa">Penyedia identitas tidak dapat memeriksa sesi ini. Muat ulang atau hubungi administrator.</StatePanel>
  else if (needsAuth) {
    const loginPath = '/customer/login'
    content = path === '/customer/chat' ? <CustomerChatPreview /> : <StatePanel title="Autentikasi diperlukan">{customerRoute ? 'Akses memerlukan sesi pelanggan terverifikasi.' : 'Akses memerlukan sesi staf terverifikasi.'} <a href={loginPath} onClick={(e) => { e.preventDefault(); navigate(loginPath) }}>Masuk</a> untuk melanjutkan.</StatePanel>
  }
  else if (!permitted) content = <StatePanel title="Akses tidak diizinkan">Sesi ini tidak memiliki akses ke halaman tersebut.</StatePanel>
  else if (Page) content = <Page role={role} session={session} />
  else content = <StatePanel title="Belum tersedia">Alur ini direncanakan pada Unit {route.unit}. Fungsionalitas dan data belum terhubung.</StatePanel>

  return <div className={`product-shell${customerShell ? ' customer-shell' : ' staff-shell'}${navCollapsed ? ' nav-collapsed' : ''}${menuOpen ? ' nav-open' : ''}`} onKeyDown={(event) => { if (event.key === 'Escape' && menuOpen) setMenuOpen(false) }}>
    <a className="skip-link" href="#main-content">Lewati ke konten</a>
    {menuOpen && <button className="nav-scrim" aria-label="Tutup navigasi" onClick={() => setMenuOpen(false)} />}
    <aside className="product-sidebar" aria-label={customerShell ? 'Navigasi portal pelanggan' : 'Navigasi ruang kerja'}>
      <a href="/" onClick={(e) => { e.preventDefault(); navigate('/') }} className="product-brand">
        <span className="product-mark" aria-hidden="true">E</span>
        <span className="brand-copy"><strong>EAICS</strong><small>Enterprise service desk</small></span>
      </a>
      <div className="sidebar-section-label">{customerShell ? 'PORTAL PELANGGAN' : 'RUANG KERJA'}</div>
      <nav ref={navRef} id="primary-navigation" className="primary-navigation" aria-label={customerShell ? 'Navigasi pelanggan' : 'Navigasi staf'}>
        {navItems.map(([href, label], index) => <a className="nav-item" key={href} href={href} title={label} aria-current={path === href ? 'page' : undefined} onClick={(e) => { e.preventDefault(); navigate(href) }}>
          <span className="nav-index" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span><span className="nav-copy">{label}</span><span className="nav-arrow" aria-hidden="true">↗</span>
        </a>)}
        {customerShell && !session && <a className="nav-item nav-login" href="/customer/login" title="Masuk" aria-current={path === '/customer/login' || path === '/login' ? 'page' : undefined} onClick={(e) => { e.preventDefault(); navigate('/customer/login') }}>
          <span className="nav-index" aria-hidden="true">↳</span><span className="nav-copy">Masuk akun</span><span className="nav-arrow" aria-hidden="true">↗</span>
        </a>}




      </nav>
      <div className="sidebar-bottom">
        <div className="sidebar-account-mark" aria-hidden="true">{customerShell ? 'C' : (role || 'S').slice(0, 1).toUpperCase()}</div>
        <div className="sidebar-account-copy"><strong>{session?.principal?.role === 'customer' ? 'Akun pelanggan' : role ? role.replaceAll('_', ' ') : customerShell ? 'Layanan terbuka' : 'Sesi staf'}</strong><span>{session ? 'Sesi terverifikasi' : 'Akses mengikuti autentikasi'}</span></div>
        {session && <button className="logout-button" title="Keluar" aria-label="Keluar" onClick={() => { devCustomerLogout(); navigate('/') }}>↗</button>}
      </div>
    </aside>
    <div className="product-mainframe">
      <header className="product-header">
        <div className="header-leading">
          <button ref={menuButtonRef} className="menu-toggle" aria-expanded={menuOpen} aria-controls="primary-navigation" onClick={() => setMenuOpen((v) => !v)} aria-label={menuOpen ? 'Tutup navigasi' : 'Buka navigasi'}><span aria-hidden="true">{menuOpen ? '×' : '☰'}</span></button>
          <button className="collapse-toggle" aria-expanded={!navCollapsed} aria-label={navCollapsed ? 'Perluas navigasi' : 'Perkecil navigasi'} title={navCollapsed ? 'Perluas navigasi' : 'Perkecil navigasi'} onClick={() => setNavCollapsed((v) => !v)}><span aria-hidden="true">{navCollapsed ? '»' : '«'}</span></button>
          <div className="header-context"><span className="header-kicker">{customerShell ? 'EAICS / LAYANAN PELANGGAN' : `EAICS / ${(role || 'WORKSPACE').replaceAll('_', ' ').toUpperCase()}`}</span><span className="header-title">{isPublic ? 'Pusat bantuan' : title}</span></div>
        </div>
        <div className="header-trailing">
          <span className="header-environment"><span className="environment-dot" aria-hidden="true" />{session ? 'Sesi aktif' : customerShell ? 'Portal publik' : 'Akses terbatas'}</span>
        </div>
      </header>
      <main id="main-content" className="product-main">
        {!isPublic && <div className="page-heading"><a href="/" onClick={(e) => { e.preventDefault(); navigate('/') }}>Beranda</a><span aria-hidden="true">/</span><h1>{title}</h1></div>}
        {content}
      </main>
      <footer className="product-footer"><span>EAICS</span><span>·</span><span>Pengalaman layanan yang lebih jelas</span></footer>
    </div>
  </div>
}

function CustomerHome() {
  return <div className="customer-home">
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
}

function UniversalLogin() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const submit = async (event) => {
    event.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const principal = await devUniversalLogin(username, password)
      const role = principal?.role
      if (role === 'customer') {
        navigate('/customer/chat')
      } else {
        const destination = {
          cs_agent: '/agent/queue',
          supervisor: '/supervisor',
          complaint_officer: '/complaints',
          knowledge_manager: '/knowledge',
          qa_analyst: '/qa',
          management: '/management',
          admin: '/admin'
        }[role] || '/agent/queue'
        navigate(destination)
      }
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }
  return <section className="customer-auth">
    <p className="eyebrow"><span className="eyebrow-rule" />PORTAL LAYANAN</p>
    <h2>Masuk ke Akun Anda</h2>
    <p className="auth-intro">Silakan masuk menggunakan nama pengguna dan kata sandi yang telah terdaftar.</p>
    {!isDevelopmentAuthEnabled && !isDevelopmentStaffAuthEnabled ? (
      <p className="alert info">Autentikasi belum diaktifkan di server pengembangan.</p>
    ) : (
      <form className="form" onSubmit={submit}>
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <button type="button" className="btn secondary" style={{ fontSize: '0.82rem', padding: '0.35rem 0.75rem', cursor: 'pointer' }} onClick={() => { setUsername('customer_dev'); setPassword('M8GvyVkrEF5wJZUCg47ylIJHeulmVA6sK0sc') }}>
            Autofill Nasabah (customer_dev)
          </button>
          <button type="button" className="btn secondary" style={{ fontSize: '0.82rem', padding: '0.35rem 0.75rem', cursor: 'pointer' }} onClick={() => { setUsername('kb.staff'); setPassword('L5Tz88EhNmxZsRshdqsI0DrMKipGf9dw') }}>
            Autofill Staf CS (kb.staff)
          </button>
        </div>
        <label>Nama pengguna<input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required /></label>
        <label>Kata sandi<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        {error && <p className="alert err" role="alert">{error.message || 'Nama pengguna atau kata sandi tidak valid.'}</p>}
        <button className="btn primary" disabled={loading}>{loading ? 'Memeriksa…' : 'Masuk'}</button>
      </form>
    )}
  </section>
}
const CustomerLogin = UniversalLogin
const StaffLogin = UniversalLogin

function CustomerChatPreview() {
  return (
    <div className="chat-container-card customer-chat-preview" aria-labelledby="chat-preview-title">
      <div className="chat-card-header">
        <div className="chat-agent-profile">
          <div className="chat-agent-avatar" aria-hidden="true">
            ✦
            <span className="chat-online-dot" title="Online" />
          </div>
          <div className="chat-agent-info">
            <h3 id="chat-preview-title">CloudNova AI Assistant</h3>
            <p>
              <span style={{ color: 'var(--success)', fontWeight: 600 }}>● Mode Pratinjau</span>
              <span>·</span>
              <span>Masuk untuk Mulai Percakapan</span>
            </p>
          </div>
        </div>
        <a className="btn sm primary" href="/customer/login" onClick={(e) => { e.preventDefault(); navigate('/customer/login') }}>
          Masuk ke Akun ↗
        </a>
      </div>
      <div className="chat-transcript-area chat-preview-transcript">
        <article className="chat-bubble from-service">
          <div className="chat-bubble-byline">
            <strong>CloudNova AI Assistant</strong>
            <small>Siap membantu</small>
          </div>
          <p>Halo! Selamat datang di layanan CloudNova. Saya dapat membantu menjawab pertanyaan seputar produk komputasi awan, basis data, jam operasional, serta keluhan teknis Anda. Silakan masuk terlebih dahulu untuk memulai percakapan aktif.</p>
        </article>
        <div className="chat-quick-prompts" aria-label="Contoh topik pertanyaan">
          <span className="chat-quick-pill">✦ Informasi Layanan Cloud</span>
          <span className="chat-quick-pill">✦ Bantuan Teknis & Tagihan</span>
          <span className="chat-quick-pill">✦ Berbicara dengan Petugas</span>
        </div>
      </div>
      <div className="chat-composer-area chat-preview-composer">
        <div className="chat-input-row" style={{ opacity: 0.75 }}>
          <textarea className="chat-textarea" placeholder="Masuk ke akun Anda untuk mulai menulis pesan..." rows={2} disabled aria-disabled="true" />
          <a className="btn primary send-button" href="/customer/login" onClick={(event) => { event.preventDefault(); navigate('/customer/login') }}>
            Masuk untuk Mulai Chat →
          </a>
        </div>
        <div className="chat-composer-footer">
          <span>🔒 Percakapan live hanya tersedia setelah masuk akun demi keamanan data Anda.</span>
        </div>
      </div>
    </div>
  )
}

function FormattedMessage({ text }) {
  if (!text) return null
  const paragraphs = text.split(/\n\n+/)
  return (
    <div className="chat-bubble-content">
      {paragraphs.map((p, idx) => {
        const lines = p.split('\n')
        return (
          <p key={idx} className="chat-paragraph">
            {lines.map((line, lineIdx) => {
              const isHdr = /^(Tentang Kami|Visi|Misi|Profil Perusahaan|Sejarah Singkat|Layanan Utama|Fitur Utama|Paket Layanan|Harga & Spesifikasi|Kontak|Jam Operasional|Catatan|Ketentuan|Syarat & Ketentuan|SLA|Daftar Produk)\b.*:?$/i.test(line) || /^###\s+/.test(line)
              const cleanLine = line.replace(/^###\s+/, '')
              if (isHdr) {
                return (
                  <strong key={lineIdx} className="chat-section-header">
                    {cleanLine}
                  </strong>
                )
              }
              const isBullet = /^([-*•–—]|\d+[\.\)])\s+/.test(line)
              if (isBullet) {
                return (
                  <span key={lineIdx} className="chat-list-line">
                    {cleanLine}
                  </span>
                )
              }
              return (
                <span key={lineIdx}>
                  {cleanLine}
                  {lineIdx < lines.length - 1 && <br />}
                </span>
              )
            })}
          </p>
        )
      })}
    </div>
  )
}

function CustomerChat() {
  const [text, setText] = useState(() => new URLSearchParams(window.location.search).get('draft') || '')
  const [conversationId, setConversationId] = useState(() => new URLSearchParams(window.location.search).get('conversation_id'))
  const [messages, setMessages] = useState([])
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [retryInfo, setRetryInfo] = useState(null)
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [showScrollBottom, setShowScrollBottom] = useState(false)
  const submitLock = useRef(false)
  const messagesEndRef = useRef(null)
  const transcriptRef = useRef(null)
  const isNearBottomRef = useRef(true)

  const handleScroll = () => {
    const el = transcriptRef.current
    if (!el) return
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    const nearBottom = distanceToBottom < 80
    isNearBottomRef.current = nearBottom
    setShowScrollBottom(!nearBottom && messages.length > 2)
  }

  const scrollToBottom = (force = false) => {
    if (force || isNearBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }

  // Only auto-scroll when message count increases or sending changes, and ONLY if user was already at bottom
  useEffect(() => {
    scrollToBottom(false)
  }, [messages.length, sending])

  const startNewChat = () => {
    setConversationId(null)
    setMessages([])
    setText('')
    setNotice(null)
    setError(null)
    isNearBottomRef.current = true
    setShowScrollBottom(false)
    const url = new URL(window.location.href)
    url.searchParams.delete('conversation_id')
    url.searchParams.delete('draft')
    window.history.replaceState({}, '', url)
  }

  const load = useCallback(async (id) => {
    setLoading(true)
    setError(null)
    try {
      let cursor = null
      const all = []
      do {
        const suffix = cursor ? `?limit=100&cursor=${encodeURIComponent(cursor)}` : '?limit=100'
        const data = await req(`/v1/conversations/${encodeURIComponent(id)}/read-model${suffix}`)
        all.push(...(data.messages || []))
        cursor = data.next_cursor
      } while (cursor)
      setConversationId(id)
      setMessages(all)
      setTimeout(() => scrollToBottom(true), 80)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const initialId = new URLSearchParams(window.location.search).get('conversation_id')
    if (initialId) load(initialId)
  }, [load])

  useEffect(() => {
    if (!conversationId) return
    const timer = setInterval(() => {
      req(`/v1/conversations/${encodeURIComponent(conversationId)}/read-model?limit=100`)
        .then((data) => {
          if (data && data.messages && data.messages.length > 0) {
            setMessages((prev) => {
              if (
                prev.length === data.messages.length &&
                prev[prev.length - 1]?.message_id === data.messages[data.messages.length - 1]?.message_id &&
                prev[prev.length - 1]?.content === data.messages[data.messages.length - 1]?.content
              ) {
                return prev // Keep same reference so React avoids re-renders and auto-scroll
              }
              return data.messages
            })
          }
        })
        .catch(() => {})
    }, 3500)
    return () => clearInterval(timer)
  }, [conversationId])

  const send = async (event) => {
    event.preventDefault()
    const content = text.trim()
    if (!content || submitLock.current) return
    submitLock.current = true
    setSending(true)
    setError(null)
    setNotice(null)
    isNearBottomRef.current = true
    scrollToBottom(true)
    const idempotencyKey = retryInfo?.text === content ? retryInfo.key : crypto.randomUUID()
    try {
      const result = await req('/v1/chat/messages', {
        method: 'POST',
        body: { text: content, ...(conversationId ? { conversation_id: conversationId } : {}) },
        headers: { 'Idempotency-Key': idempotencyKey }
      })
      if (!result.conversation_id) throw new ApiError(502, 'MISSING_CONVERSATION', 'Layanan tidak mengembalikan referensi percakapan.')
      const url = new URL(window.location.href)
      url.searchParams.set('conversation_id', result.conversation_id)
      window.history.replaceState({}, '', url)
      setRetryInfo(null)
      setConversationId(result.conversation_id)
      setText('')
      setNotice(
        result.handoff_status === 'ACCEPTED'
          ? 'Petugas telah menerima permintaan bantuan.'
          : result.handoff_status === 'QUEUED' || result.handoff_status === 'OFFERED'
          ? 'Permintaan bantuan masuk antrean; petugas belum mengonfirmasi penerimaan.'
          : result.handoff_status === 'UNAVAILABLE'
          ? 'Pesan tersimpan, tetapi status antrean bantuan belum dapat dipastikan.'
          : 'Pesan diproses oleh layanan.'
      )
      await load(result.conversation_id)
      scrollToBottom(true)
    } catch (err) {
      setRetryInfo({ text: content, key: idempotencyKey })
      setError(err)
    } finally {
      submitLock.current = false
      setSending(false)
    }
  }

  const handleComposerKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      const form = event.currentTarget.form
      const submitButton = form?.querySelector('button[type="submit"]')
      if (!submitButton?.disabled) {
        form?.requestSubmit()
      }
    }
  }

  return (
    <div className="chat-container-card">
      <div className="chat-card-header">
        <div className="chat-agent-profile">
          <div className="chat-agent-avatar" aria-hidden="true">
            ✦
            <span className="chat-online-dot" title="Online" />
          </div>
          <div className="chat-agent-info">
            <h3>CloudNova AI Assistant</h3>
            <p>
              <span style={{ color: 'var(--success)', fontWeight: 600 }}>● Aktif</span>
              <span>·</span>
              <span>Layanan Pelanggan Agentik 24/7</span>
            </p>
          </div>
        </div>
        <div className="chat-header-actions">
          {conversationId && (
            <span className="source-chip" title="ID Sesi Percakapan" style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
              ID: {conversationId.slice(0, 8)}...
            </span>
          )}
          <button type="button" className="btn sm" onClick={startNewChat} title="Mulai sesi percakapan baru">
            + Mulai Baru
          </button>
          <a href="/customer/conversations" className="btn sm" onClick={(e) => { e.preventDefault(); navigate('/customer/conversations') }}>
            Riwayat ↗
          </a>
        </div>
      </div>

      {notice && (
        <div className="alert info chat-notice" role="status" style={{ margin: '14px 20px 0' }}>
          <span>{notice}</span>
        </div>
      )}

      {error && (
        <div className="talkback" role="alert" style={{ margin: '14px 20px 0' }}>
          <span className="talkback-mark" aria-hidden="true">!</span>
          <div>
            <strong>Pesan belum berhasil diproses.</strong>
            <p>
              {error.message}
              {error.status === 401 ? (
                <> <a href="/customer/login" onClick={(e) => { e.preventDefault(); navigate('/customer/login') }}>Masuk kembali</a> untuk melanjutkan.</>
              ) : error.status === 403 ? (
                ' Hubungi pengelola layanan jika menurut Anda akses ini seharusnya tersedia.'
              ) : (
                ' Pesan Anda tetap berada di kolom; pengiriman ulang memakai kunci idempotensi yang sama.'
              )}
            </p>
          </div>
        </div>
      )}

      <div className="chat-transcript-area" ref={transcriptRef} onScroll={handleScroll} aria-live="polite" aria-busy={loading}>
        {loading && !messages.length ? (
          <div className="transcript-skeleton" role="status" aria-label="Memuat percakapan">
            <span /><span /><span />
          </div>
        ) : messages.length ? (
          <>
            {messages.map((m) => {
              const isCustomer = m.direction === 'INBOUND'
              return (
                <article
                  className={`chat-bubble ${isCustomer ? 'from-customer' : 'from-service'}`}
                  key={m.message_id || m.sequence_no}
                >
                  <div className="chat-bubble-byline">
                    <strong>{isCustomer ? 'Anda' : m.author_type === 'AI_AGENT' ? 'CloudNova AI Assistant' : 'Petugas Customer Support'}</strong>
                    <small>{m.occurred_at ? new Date(m.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</small>
                  </div>
                  <FormattedMessage text={m.content} />
                  {!isCustomer && (m.citations || []).length > 0 && (
                    <div className="chat-citation-box">
                      <span className="chat-citation-title">Sumber Informasi Resmi</span>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {m.citations.map((c, i) => (
                          <span className="chat-citation-item" key={c.version_id || c.article_id || i}>
                            ↗ {c.title || c.source || 'Knowledge Base'}
                            {c.version ? ` · v${c.version}` : ''}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </article>
              )
            })}
            {sending && (
              <div className="typing-bubble">
                <div style={{ fontSize: '11px', color: 'var(--muted)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>✦</span> Asisten sedang menyusun jawaban...
                </div>
                <div className="typing-dots">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="chat-empty" style={{ margin: 'auto', textAlign: 'center', padding: '36px 16px' }}>
            <div className="empty-emblem" aria-hidden="true" style={{ margin: '0 auto 16px' }}>
              <span>✦</span>
              <i />
            </div>
            <p className="eyebrow" style={{ color: 'var(--electric-blue)' }}>ASISTEN RESMI CLOUDNOVA</p>
            <h2 style={{ fontSize: '20px', fontWeight: 600, margin: '8px 0 12px', color: 'var(--ink)' }}>
              Ada yang bisa kami bantu hari ini?
            </h2>
            <p style={{ maxWidth: '480px', margin: '0 auto 20px', fontSize: '13px', color: 'var(--muted)', lineHeight: 1.6 }}>
              Tanyakan seputar produk cloud, infrastruktur, jam operasional, atau kendala teknis. Asisten agentik kami siap membantu Anda dengan cepat dan akurat.
            </p>
            <div className="chat-quick-prompts" aria-label="Saran pertanyaan cepat">
              {[
                'Layanan cloud apa saja yang tersedia di CloudNova?',
                'Berapa daftar harga dan spesifikasi server Compute?',
                'Jam operasional customer support?',
                'Saya ingin berbicara langsung dengan petugas manusia.'
              ].map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="chat-quick-pill"
                  onClick={() => setText(prompt)}
                >
                  <span>✦</span> {prompt}
                </button>
              ))}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {showScrollBottom && (
        <button
          type="button"
          className="chat-scroll-bottom-btn"
          onClick={() => {
            isNearBottomRef.current = true
            scrollToBottom(true)
            setShowScrollBottom(false)
          }}
          title="Gulir ke pesan terbaru"
        >
          ↓ Pesan Terbaru
        </button>
      )}

      <form className="chat-composer-area" onSubmit={send}>
        <div className="chat-input-row">
          <textarea
            className="chat-textarea"
            id="customer-message"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder="Tulis pesan pertanyaan atau keluhan Anda di sini... (Enter untuk kirim, Shift+Enter untuk baris baru)"
            maxLength={4000}
            rows={2}
            disabled={sending}
          />
          <button
            type="submit"
            className="chat-send-btn"
            disabled={sending || !text.trim() || error?.status === 401 || error?.status === 403}
            title="Kirim pesan"
            aria-label="Kirim pesan"
          >
            {sending ? '⏳' : '➤'}
          </button>
        </div>
        <div className="chat-composer-footer">
          <span>🔒 Jangan bagikan kata sandi, OTP, atau informasi kredensial rahasia.</span>
          <span>{text.length}/4000</span>
        </div>
      </form>
    </div>
  )
}

function CustomerHistory() {
  const [items, setItems] = useState([]); const [selected, setSelected] = useState(null); const [error, setError] = useState(null); const [loading, setLoading] = useState(true); const [nextCursor, setNextCursor] = useState(null)
  const load = useCallback(async (cursor = null, append = false) => { setLoading(true); setError(null); try { const query = cursor ? `?limit=20&cursor=${encodeURIComponent(cursor)}` : '?limit=20'; const data = await req(`/v1/customer/conversations${query}`); setItems((current) => append ? [...current, ...(data.items || [])] : data.items || []); setNextCursor(data.next_cursor || null) } catch (err) { setError(err) } finally { setLoading(false) } }, [])
  useEffect(() => { load() }, [load])
  const detail = async (id) => { setError(null); try { let cursor = null; let data; const messages = []; do { const suffix = cursor ? `?limit=100&cursor=${encodeURIComponent(cursor)}` : '?limit=100'; data = await req(`/v1/conversations/${encodeURIComponent(id)}/read-model${suffix}`); messages.push(...(data.messages || [])); cursor = data.next_cursor } while (cursor); setSelected({ ...data, messages }) } catch (err) { setError(err) } }
  return <section className="customer-history"><div className="customer-list-heading"><div><p className="sub">Percakapan tersimpan sebagai riwayat layanan pada akun Anda.</p><p className="customer-retention-note">Riwayat tidak dapat dihapus dari portal ini.</p></div><div className="row"><button className="btn sm" onClick={() => load()}>Muat ulang</button><a className="btn sm primary" href="/customer/requests/new" onClick={(e) => { e.preventDefault(); navigate('/customer/requests/new') }}>Kirim permintaan</a></div></div>
    {error && <p className="alert err" role="alert">{error.message}</p>}{loading && !items.length ? <Empty text="Memuat riwayat..." /> : !items.length ? <Empty text="Belum ada percakapan." /> : <ul className="conversation-list">{items.map((item) => <li key={item.conversation_id}><button className="conversation-list-item" onClick={() => detail(item.conversation_id)}><strong>{item.conversation_id}</strong><span>{customerConversationState(item.status)} / {new Date(item.last_activity_at).toLocaleString()}</span></button></li>)}</ul>}
    {nextCursor && <button className="btn" disabled={loading} onClick={() => load(nextCursor, true)}>{loading ? 'Memuat...' : 'Muat percakapan sebelumnya'}</button>}
      {selected && <div className="customer-transcript"><h2>{selected.conversation.conversation_id}</h2>{selected.messages.map((m) => <article className={`customer-message ${m.direction === 'INBOUND' ? 'from-customer' : 'from-service'}`} key={m.message_id || m.sequence_no}><p>{m.content}</p><small>{m.direction === 'INBOUND' ? 'Anda' : 'Layanan'}</small>{(m.citations || []).map((citation, i) => <small key={i}>Sumber: {citation.title || citation.source || 'Referensi layanan'}{citation.passage_ref ? ` / ${citation.passage_ref}` : ''}</small>)}</article>)}</div>}
  </section>
}

function CustomerRequest() {
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

function CustomerTrack() {
  const [items, setItems] = useState([])
  const [tickets, setTickets] = useState([])
  const [nextCursor, setNextCursor] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async (cursor = null, append = false) => {
    setLoading(true); setError(null)
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
    } catch (err) { setError(err) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  return <section className="customer-work-page customer-track-page">
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
}

function CustomerAccount({ session }) {
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

/* ---------- Dasbor ---------- */
function Dash({ role }) {
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

/* ---------- Antrean ---------- */
function Queue({ role }) {
  const [items, setItems] = useState([])
  const [e, setE] = useState(null)
  const [sel, setSel] = useState(null)
  const [filter, setFilter] = useState({ queue_id: '', skills: '' })
  const [f, setF, resetF] = useForm({ conversation_id: 'CNV-DEMO-1', reason_code: 'CUSTOMER_REQUEST', severity: 'MEDIUM', queue_id: 'Q-GENERAL', skill_tags: '', vulnerability_flag: false, package_complete: true })
  const [t, setT] = useForm({ to_queue: 'Q-GENERAL', reason: '', note: '' })
  const [ho, setHo] = useState(null)

  const load = useCallback(async () => {
    setE(null)
    try {
      const q = new URLSearchParams()
      if (filter.queue_id) q.set('queue_id', filter.queue_id)
      if (filter.skills) q.set('skills', filter.skills)
      const r = await req(`/v1/workspace/queue${q.toString() ? `?${q}` : ''}`, { role })
      setItems(r.items || [])
    } catch (err) { setE(err) }
  }, [role, filter.queue_id, filter.skills])
  useEffect(() => { load(); const tmr = setInterval(load, 8000); return () => clearInterval(tmr) }, [load])

  const enqueue = async () => {
    setE(null)
    try {
      const r = await req('/v1/workspace/queue/enqueue', {
        method: 'POST', role,
        body: {
          conversation_id: f.conversation_id, reason_code: f.reason_code, severity: f.severity,
          queue_id: f.queue_id, skill_tags: f.skill_tags.split(',').map((s) => s.trim()).filter(Boolean),
          vulnerability_flag: f.vulnerability_flag, package_complete: f.package_complete,
        },
      })
      setHo({ ok: true, data: r }); resetF(); load()
    } catch (err) { setE(err) }
  }
  const accept = async (it) => {
    setE(null)
    try {
      await req(`/v1/workspace/handoffs/${it.handoff_id}/accept`, { method: 'POST', role, body: {} })
      setSel(null)
      navigate(`/agent/conversations?cid=${encodeURIComponent(it.conversation_id)}`)
    } catch (err) { setE(err) }
  }
  const transfer = async () => {
    if (!sel) return
    setE(null)
    try {
      const r = await req(`/v1/workspace/handoffs/${sel.handoff_id}/transfer`, { method: 'POST', role, body: t })
      setHo({ ok: true, data: r }); load()
    } catch (err) { setE(err) }
  }
  const quickHandoff = async () => {
    setE(null)
    try {
      const r = await req('/v1/handoffs', { method: 'POST', role, body: { conversation_id: f.conversation_id, reason_code: f.reason_code, recent_turns: [] } })
      setHo({ ok: true, data: r })
    } catch (err) { setE(err) }
  }

  return (
    <>
      <Err e={e} onClose={() => setE(null)} />
      <div className="split">
        <Card title={`Antrean Layanan Petugas (Queue: ${items.length})`} sub="Diurutkan otomatis berdasarkan skor prioritas; auto-refresh berkala setiap 8 detik.">
          <div className="row">
            <input placeholder="Filter Queue ID (cth: Q-GENERAL)" value={filter.queue_id} onChange={(e) => setFilter({ ...filter, queue_id: e.target.value })} style={{ width: 180 }} />
            <input placeholder="Filter Skill Tags (cth: chat, id)" value={filter.skills} onChange={(e) => setFilter({ ...filter, skills: e.target.value })} style={{ width: 180 }} />
            <button className="btn sm" onClick={load}>Refresh Data</button>
          </div>
          <div className="mt" style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead><tr><th>Percakapan</th><th>Alasan Eskalasi</th><th>Severity</th><th>Skor Prioritas</th><th>Waktu Tunggu</th><th>Queue / Status Paket</th><th>Tindakan</th></tr></thead>
              <tbody>
                {items.map((q) => (
                  <tr key={q.handoff_id} className={`clickable${sel?.handoff_id === q.handoff_id ? ' sel' : ''}`} onClick={() => { setSel(q); setT((o) => ({ ...o })) }}>
                    <td><b>{q.conversation_id}</b><br /><span style={{ fontSize: 11, color: '#64748b' }}>{q.handoff_id}</span></td>
                    <td>{q.reason_code}</td>
                    <td><Sev v={q.severity} /></td>
                    <td><b>{q.priority_score}</b></td>
                    <td>{q.wait_s}s</td>
                    <td>{q.queue_id}{!q.package_complete && <> <span className="badge b-amber">PARSIAL</span></>}</td>
                    <td><button className="btn sm primary" onClick={(ev) => { ev.stopPropagation(); accept(q) }}>Terima Handoff</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!items.length && <Empty text="Antrean saat ini kosong — belum ada eskalasi baru dari nasabah." />}
          </div>
        </Card>
        <div className="grid">
          <Card title="Tambah ke Antrean (Manual Enqueue)" sub="Eskalasikan percakapan nasabah ke antrean penanganan petugas.">
            <div className="form">
              <label>ID Percakapan<input value={f.conversation_id} onChange={setF('conversation_id')} placeholder="CNV-..." /></label>
              <div className="form2">
                <label>Alasan Eskalasi<select value={f.reason_code} onChange={setF('reason_code')}>{REASONS.map((r) => <option key={r}>{r}</option>)}</select></label>
                <label>Tingkat Severity<select value={f.severity} onChange={setF('severity')}>{SEVERITIES.map((r) => <option key={r}>{r}</option>)}</select></label>
              </div>
              <div className="form2">
                <label>Nama Queue<input value={f.queue_id} onChange={setF('queue_id')} placeholder="Q-GENERAL" /></label>
                <label>Tag Keahlian (Skill Tags)<input value={f.skill_tags} onChange={setF('skill_tags')} placeholder="chat, id, dispute" /></label>
              </div>
              <label className="check"><input type="checkbox" checked={f.vulnerability_flag} onChange={setF('vulnerability_flag')} /> Nasabah prioritas / rentan (Tingkatkan bobot SLA)</label>
              <label className="check"><input type="checkbox" checked={f.package_complete} onChange={setF('package_complete')} /> Paket konteks handoff lengkap</label>
              <div className="row"><button className="btn primary" onClick={enqueue}>Daftarkan ke Antrean</button>
                <button className="btn" onClick={quickHandoff} title="Verifikasi integritas payload paket handoff">Cek Paket Handoff</button></div>
            </div>
          </Card>
          <Card title="Transfer Antrean (Alihkan ke Tim Lain)" sub="Pindahkan penanganan ke tim spesialis lain dengan catatan pendukung.">
            {!sel ? <Empty text="Pilih salah satu baris antrean di sebelah kiri terlebih dahulu." /> : (
              <div className="form">
                <div className="kv"><dt>Handoff ID</dt><dd>{sel.handoff_id}</dd><dt>Percakapan</dt><dd>{sel.conversation_id}</dd></div>
                <label>Target Antrean (Queue)<input value={t.to_queue} onChange={setT('to_queue')} placeholder="Q-FRAUD / Q-SPECIALIST" /></label>
                <label>Alasan Pengalihan<input value={t.reason} onChange={setT('reason')} placeholder="Memerlukan penanganan spesialis" /></label>
                <label>Catatan Internal (Wajib diisi)<textarea value={t.note} onChange={setT('note')} rows={2} placeholder="Jelaskan kronologi dan konteks untuk petugas penerima..." /></label>
                <div className="row"><button className="btn primary" onClick={transfer}>Kirim Pengalihan</button></div>
              </div>
            )}
          </Card>
          {ho && <Card title="Status Operasi" sub={ho.ok ? 'Berhasil' : 'Informasi'}><Json data={ho.data} /></Card>}
        </div>
      </div>
    </>
  )
}

/* ---------- Percakapan ---------- */
function Conv({ role, session }) {
  const [cid, setCid] = useState(() => new URLSearchParams(window.location.search).get('cid') || 'CNV-DEMO-1')
  const [d, setD] = useState(null)
  const [e, setE] = useState(null)
  const [sug, setSug] = useState(null)
  const [loading, setLoading] = useState(false)
  const open = async (conversationId = cid, keepCurrent = false) => {
    const target = (conversationId || cid || '').trim()
    if (!target) { setE(new Error('Masukkan ID percakapan terlebih dahulu.')); return }
    setE(null); if (!keepCurrent) setD(null); setSug(null); setLoading(true)
    try { setD(await req(`/v1/workspace/conversations/${encodeURIComponent(target)}`)) }
    catch (err) { setE(err) }
    finally { setLoading(false) }
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
    try { setSug(await req('/v1/copilot/suggest', { method: 'POST', body: { conversation_id: cid } })) }
    catch (err) { setE(err) }
  }
  return (
    <>
      <Err e={e} onClose={() => setE(null)} />
      <Card title="Pencarian Percakapan Nasabah" sub="Customer Context, AI Classification, Riwayat Chat, Tool Execution, dan Status Penanganan Petugas.">
        <div className="row"><input aria-label="ID percakapan" value={cid} onChange={(e) => setCid(e.target.value)} style={{ minWidth: 260 }} placeholder="Contoh: CNV-..." />
          <button className="btn primary" onClick={() => open()} disabled={loading}>{loading ? 'Memuat...' : 'Buka Percakapan'}</button>
          <button className="btn" onClick={suggest} disabled={!d || loading}>Saran AI Copilot</button></div>
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
                <li key={m.message_id || m.sequence_no}><b>{m.author_type === 'CUSTOMER' ? 'Customer' : m.author_type === 'AI_AGENT' ? 'Asisten AI' : m.author_type === 'HUMAN_AGENT' ? 'Petugas CS' : m.author_type} · {m.direction}</b>
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
      )}
    </>
  )
}

function AgentConversationActions({ d, role, session, onRefresh }) {
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
    setBusy(key); setError(null); setNotice('')
    try { await operation(); setNotice(success); await onRefresh(d.conversation_id, true) }
    catch (err) { setError(err) }
    finally { setBusy('') }
  }
  const sendReply = (event) => {
    event.preventDefault()
    const content = reply.trim()
    if (!content) { setError(new Error('Balasan tidak boleh kosong.')); return }
    run('reply', async () => {
      await req(`${path}/messages`, { method: 'POST', body: { content } })
      setReply('')
    }, 'Balasan tersimpan dan tampil pada transkrip.')
  }
  const accept = () => run('accept', () => req(`/v1/workspace/handoffs/${encodeURIComponent(d.handoff.handoff_id)}/accept`, { method: 'POST', body: {} }), 'Handoff diterima. Percakapan aktif ditangani petugas.')
  const resolve = () => run('resolve', () => req(`${path}/resolve`, { method: 'POST', body: {} }), 'Penanganan selesai dan menunggu konfirmasi customer.')
  const createCase = (event) => {
    event.preventDefault()
    if (!caseForm.description.trim()) { setError(new Error('Deskripsi kasus wajib diisi.')); return }
    run('case', () => req('/v1/cases', { method: 'POST', body: { ...caseForm, description: caseForm.description.trim(), conversation_id: d.conversation_id, source_channel: 'WEB_CHAT' } }), 'Kasus dibuat dan ditautkan ke percakapan.')
  }
  const createTicket = (event) => {
    event.preventDefault()
    if (!ticketForm.description.trim()) { setError(new Error('Deskripsi tiket wajib diisi.')); return }
    run('ticket', () => req('/v1/tickets', { method: 'POST', body: { ...ticketForm, description: ticketForm.description.trim(), conversation_id: d.conversation_id, source_channel: 'WEB_CHAT' } }), 'Tiket dibuat dan ditautkan ke percakapan.')
  }
  return <>
    <Card title="Penanganan petugas" sub="Balasan dan status mengikuti handoff yang diterima oleh petugas yang sedang login." wide>
      {notice && <p className="alert info" role="status">{notice}</p>}
      {error && <p className="alert err" role="alert">{error.message || 'Tindakan tidak berhasil.'}</p>}
      {d.handoff?.state === 'QUEUED' && <div className="agent-handoff-actions"><p>Handoff menunggu petugas. Terima handoff untuk memulai penanganan.</p><button className="btn primary" type="button" disabled={!!busy} onClick={accept}>{busy === 'accept' ? 'Menerima...' : 'Terima handoff'}</button></div>}
      {d.handoff?.state === 'ACCEPTED' && !ownsHandoff && <p className="section-note">Handoff diterima oleh {d.handoff.accepted_by || 'petugas lain'}; hanya petugas penerima yang dapat membalas atau menyelesaikannya.</p>}
      {canReply && <form className="agent-reply-form" onSubmit={sendReply}>
        <label htmlFor={`agent-reply-${d.conversation_id}`}>Balas customer</label>
        <textarea id={`agent-reply-${d.conversation_id}`} value={reply} onChange={(event) => setReply(event.target.value)} maxLength={4000} rows={3} placeholder="Tulis balasan untuk customer..." disabled={!!busy} />
        <div className="agent-reply-actions"><small>{reply.length}/4000 karakter</small><button className="btn primary" type="submit" disabled={!!busy || !reply.trim()}>{busy === 'reply' ? 'Menyimpan...' : 'Kirim balasan'}</button></div>
        <button className="btn" type="button" disabled={!!busy} onClick={resolve}>{busy === 'resolve' ? 'Menyelesaikan...' : 'Selesaikan penanganan'}</button>
        <small>Status selesai adalah menunggu konfirmasi customer.</small>
      </form>}
      {d.conversation?.status === 'RESOLVED_PENDING_CONFIRMATION' && <p className="alert info" role="status">Penanganan petugas selesai; percakapan menunggu konfirmasi customer.</p>}
      {d.handoff?.state !== 'QUEUED' && !ownsHandoff && d.conversation?.status !== 'RESOLVED_PENDING_CONFIRMATION' && <p className="section-note">Balasan tersedia setelah handoff diterima oleh petugas yang sedang login.</p>}
    </Card>
    {canCreateLinkedWork && <Card title="Buat kasus atau tiket" sub="Memakai endpoint yang tersedia; kasus/tiket ditautkan ke percakapan ini dan backend membuat SLA serta outbox." wide>
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
    </Card>}
  </>
}

/* ---------- Kasus & Tiket ---------- */
function Cases({ role }) {
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
    setE(null); setOut(null)
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

/* ---------- Persetujuan ---------- */
function Approvals({ role }) {
  const [e, setE] = useState(null)
  const [list, setList] = useState([])
  const [onlyPending, setOnlyPending] = useState(true)
  const [det, setDet] = useState(null)
  const [f, setF, resetF] = useForm({ conversation_id: 'CNV-DEMO-1', tool_name: 'card_status_update', args: '{"card_id":"CARD-1","status":"BLOCKED"}', justification: 'Dugaan fraud, blokir sementara', risk_class: 'WRITE_MEDIUM' })
  const [dec, setDec] = useForm({ decision: 'GRANTED', comment: 'Setuju, argumen sesuai' })

  const load = useCallback(async () => {
    setE(null)
    try { const r = await req(`/v1/approvals${onlyPending ? '?state=pending' : ''}`, { role }); setList(r.items || []) }
    catch (err) { setE(err) }
  }, [role, onlyPending])
  useEffect(() => { load() }, [load])

  const create = async () => {
    setE(null)
    try {
      const args = JSON.parse(f.args)
      const r = await req('/v1/approvals', { method: 'POST', role, body: { conversation_id: f.conversation_id, tool_name: f.tool_name, args, justification: f.justification, risk_class: f.risk_class } })
      setDet(r); resetF(); load()
    } catch (err) { setE(err instanceof SyntaxError ? new ApiError(0, '', 'Args harus JSON valid.') : err) }
  }
  const open = async (aid) => { setE(null); try { setDet(await req(`/v1/approvals/${aid}`, { role })) } catch (err) { setE(err) } }
  const decide = async () => {
    if (!det) return
    setE(null)
    try {
      const r = await req(`/v1/approvals/${det.approval_id}/decide`, { method: 'POST', role, body: dec })
      setDet(r); load()
    } catch (err) { setE(err) }
  }

  return (
    <>
      <Err e={e} onClose={() => setE(null)} />
      <div className="split">
        <Card title={`Daftar (${list.length})`} sub="RBAC-02: peminta tak boleh menyetujui sendiri.">
          <div className="row"><label className="check"><input type="checkbox" checked={onlyPending} onChange={(e) => setOnlyPending(e.target.checked)} /> Hanya pending</label>
            <button className="btn sm" onClick={load}>Muat ulang</button></div>
          <div className="mt" style={{ overflowX: 'auto' }}>
            <table className="tbl"><thead><tr><th>ID</th><th>Tool</th><th>Peminta</th><th>Keputusan</th></tr></thead>
              <tbody>{list.map((a) => (
                <tr key={a.approval_id} className="clickable" onClick={() => open(a.approval_id)}>
                  <td style={{ fontSize: 11 }}>{a.approval_id}</td><td>{a.tool_name}</td><td>{a.requested_by}</td>
                  <td>{a.decision ? <StateBadge v={a.decision} /> : <span className="badge b-amber">PENDING</span>}</td>
                </tr>))}
              </tbody></table>
            {!list.length && <Empty text="Tidak ada permintaan." />}
          </div>
        </Card>
        <div className="grid">
          <Card title="Minta persetujuan" sub="Gerbang tool tulis sensitif (FR-ORC-005).">
            <div className="form">
              <label>Percakapan<input value={f.conversation_id} onChange={setF('conversation_id')} /></label>
              <div className="form2">
                <label>Tool<input value={f.tool_name} onChange={setF('tool_name')} /></label>
                <label>Kelas risiko<input value={f.risk_class} onChange={setF('risk_class')} /></label>
              </div>
              <label>Args (JSON)<textarea value={f.args} onChange={setF('args')} rows={3} /></label>
              <label>Justifikasi<input value={f.justification} onChange={setF('justification')} /></label>
              <div className="row"><button className="btn primary" onClick={create}>Ajukan</button></div>
            </div>
          </Card>
          <Card title="Detail & keputusan" sub="Bandingkan hash argumen sebelum menyetujui (BR-ORC-07). Komentar wajib.">
            {!det ? <Empty text="Pilih permintaan di kiri." /> : (
              <div className="form">
                <div className="kv"><dt>ID</dt><dd>{det.approval_id}</dd><dt>Tool</dt><dd>{det.tool_name}</dd>
                  <dt>Peminta</dt><dd>{det.requested_by}</dd><dt>Keputusan</dt><dd>{det.decision ? <StateBadge v={det.decision} /> : 'PENDING'}</dd></div>
                <label>Hash argumen (sha256)<code className="hash">{det.arguments_hash}</code></label>
                <label>Snapshot argumen</label><Json data={det.arguments_snapshot} />
                <div className="form2">
                  <label>Keputusan<select value={dec.decision} onChange={setDec('decision')}><option>GRANTED</option><option>DENIED</option></select></label>
                </div>
                <label>Komentar (wajib)<input value={dec.comment} onChange={setDec('comment')} /></label>
                <div className="row"><button className="btn primary" onClick={decide}>Kirim keputusan</button></div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  )
}

/* ---------- QA ---------- */
function QA({ role }) {
  const [e, setE] = useState(null)
  const [out, setOut] = useState(null)
  const [sum, setSum] = useState(null)
  const [seed, setSeed] = useState(42)
  const [sc, setSc] = useForm({ item_id: '', auto_fail: '' })
  const [scores, setScores] = useState({ identitas: 8, sitasi: 8, klasifikasi: 8, tool: 8, bukti: 8, komunikasi: 8, komitmen: 8, penutupan: 8 })
  const [fo, setFo] = useForm({ review_id: '', type: 'individual_coaching', severity: 'MEDIUM', description: '' })

  const loadSum = useCallback(async () => {
    try { setSum(await req('/v1/analytics/qa', { role })) } catch { /* peran tanpa analytics.read */ }
  }, [role])
  useEffect(() => { loadSum() }, [loadSum])

  const sample = async () => { setE(null); try { const r = await req('/v1/qa/sample', { method: 'POST', role, body: { seed: Number(seed) } }); setOut(r); } catch (err) { setE(err) } }
  const review = async () => {
    setE(null)
    try {
      const s = Object.fromEntries(Object.entries(scores).map(([k, v]) => [k, Number(v)]))
      const r = await req('/v1/qa/reviews', { method: 'POST', role, body: { item_id: sc.item_id, scores: s, ...(sc.auto_fail ? { auto_fail: sc.auto_fail } : {}) } })
      setOut(r); loadSum()
    } catch (err) { setE(err) }
  }
  const finding = async () => { setE(null); try { const r = await req('/v1/qa/findings', { method: 'POST', role, body: { ...fo } }); setOut(r) } catch (err) { setE(err) } }

  return (
    <>
      <p className="alert info">Review hanya dapat dilakukan oleh pengguna yang memiliki izin QA. Akses ditentukan oleh sesi terverifikasi.</p>
      <Err e={e} onClose={() => setE(null)} />
      {sum && (
        <div className="grid g4">
          <Card><div className="stat"><span className="v">{sum.n}</span><span className="l">Review</span></div></Card>
          <Card><div className="stat"><span className="v">{sum.avg_total}</span><span className="l">Rata-rata total</span></div></Card>
          <Card><div className="stat"><span className="v">{Math.round((sum.auto_fail_rate || 0) * 100)}%</span><span className="l">Auto-fail rate</span></div></Card>
          <Card><div className="stat"><span className="v">{sum.by_field ? Object.keys(sum.by_field).length : 0}</span><span className="l">Dimensi nilai</span></div></Card>
        </div>
      )}
      {out && <Card title="Hasil Operasi"><Json data={out} /></Card>}
      <div className="grid g3 mt">
        <Card title="Tarik Sampel Acak (Sampling)" sub="Pengambilan sampel acak percakapan untuk audit kualitas pelayanan.">
          <div className="form"><label>Random Seed<input type="number" value={seed} onChange={(e) => setSeed(e.target.value)} /></label>
            <div className="row"><button className="btn primary" onClick={sample}>Tarik Sampel Evaluasi</button></div></div>
        </Card>
        <Card title="Penilaian Mutu (Review Scoring)" sub="Skor skala 0–10 untuk setiap dimensi pelayanan.">
          <div className="form">
            <label>Item ID (Kasus / Percakapan)<input value={sc.item_id} onChange={setSc('item_id')} placeholder="CAS-..." /></label>
            <div className="form2">{QA_FIELDS.map((fld) => (
              <label key={fld}>{fld}<input type="number" min={0} max={10} value={scores[fld]} onChange={(e) => setScores({ ...scores, [fld]: e.target.value })} /></label>))}
            </div>
            <label>Auto-Fail Trigger<select value={sc.auto_fail} onChange={setSc('auto_fail')}><option value="">— Tidak ada pelanggaran fatal —</option>{QA_AUTO_FAIL.map((o) => <option key={o}>{o}</option>)}</select></label>
            <div className="row"><button className="btn primary" onClick={review}>Simpan Hasil Review</button></div>
          </div>
        </Card>
        <Card title="Catat Temuan (Findings)" sub="Tindak lanjut hasil penilaian: Coaching, Knowledge Base, atau Investigasi.">
          <div className="form">
            <label>Review ID<input value={fo.review_id} onChange={setFo('review_id')} placeholder="REV-..." /></label>
            <div className="form2">
              <label>Tipe Tindak Lanjut<select value={fo.type} onChange={setFo('type')}>{QA_FINDING_TYPES.map((o) => <option key={o}>{o}</option>)}</select></label>
              <label>Severity<select value={fo.severity} onChange={setFo('severity')}>{SEVERITIES.map((o) => <option key={o}>{o}</option>)}</select></label>
            </div>
            <label>Deskripsi Temuan<textarea value={fo.description} onChange={setFo('description')} rows={2} placeholder="Rincian catatan dan rekomendasi perbaikan..." /></label>
            <div className="row"><button className="btn primary" onClick={finding}>Daftarkan Temuan</button></div>
          </div>
        </Card>
      </div>
    </>
  )
}

/* ---------- Analitik ---------- */
function Analytics({ role }) {
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
    } catch (err) { setE(err) }
  }, [role])
  useEffect(() => { load() }, [load])
  const csv = async (kind) => {
    setE(null)
    try {
      const text = await req(`/v1/analytics/export.csv?kind=${kind}`, { role, download: true })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }))
      a.download = `eaics-${kind}.csv`; a.click(); URL.revokeObjectURL(a.href)
    } catch (err) { setE(err) }
  }
  const treeRows = d ? Object.entries(d.tree).flatMap(([cat, subs]) => Object.entries(subs).map(([sub2, n]) => ({ cat, sub: sub2, n }))) : []
  return (
    <>
      <Err e={e} onClose={() => setE(null)} />
      <div className="row"><button className="btn sm" onClick={load}>Refresh Analitik</button>
        <button className="btn sm" onClick={() => csv('cases')}>Export CSV Kasus</button>
        <button className="btn sm" onClick={() => csv('handoffs')}>Export CSV Handoff</button></div>
      {!d ? <Card><Empty text="Memuat laporan analitik..." /></Card> : (
        <>
          <div className="grid g4 mt">
            <Card><div className="stat"><span className="v">{d.op.cases_total}</span><span className="l">Total Kasus • Tiket: {d.op.tickets_total}</span></div></Card>
            <Card><div className="stat"><span className="v">{Math.round(d.op.sla_attainment_ratio * 100)}%</span><span className="l">Ketercapaian SLA</span></div></Card>
            <Card><div className="stat"><span className="v">{Math.round(d.res.reopen_rate * 100)}%</span><span className="l">Reopen Rate (Target &lt; 5%)</span></div></Card>
            <Card><div className="stat"><span className="v">{d.qa.avg_total}</span><span className="l">Rata-rata Skor QA (n={d.qa.n})</span></div></Card>
          </div>
          <Card title="Driver Tree Klasifikasi Masalah" sub="Analisis distribusi masalah berjenjang: Kategori → Sub-kategori">
            <div style={{ overflowX: 'auto' }}><table className="tbl"><thead><tr><th>Kategori Masalah</th><th>Sub-Kategori</th><th>Volume Keluhan</th></tr></thead>
              <tbody>{treeRows.map((r, i) => <tr key={i}><td>{r.cat}</td><td>{r.sub}</td><td><b>{r.n}</b></td></tr>)}</tbody></table>
              {!treeRows.length && <Empty text="Belum ada data distribusi masalah." />}</div>
          </Card>
          <Card title="Distribusi Alasan Eskalasi Handoff"><Json data={d.ho} /></Card>
        </>
      )}
    </>
  )
}

/* ---------- SLA & Outbox ---------- */
function SLA({ role }) {
  const [e, setE] = useState(null)
  const [out, setOut] = useState(null)
  const [st, setSt] = useState(null)
  const [f, setF] = useForm({ object_type: 'CASE', category: 'TRANSACTION_DISPUTE', severity: 'HIGH', created_at: '2026-03-06T09:30:00+00:00' })
  const [nt, setNt] = useForm({ channel: 'REGISTERED_EMAIL', target: 'nasabah@example.test' })

  const status = useCallback(async () => { try { setSt(await req('/internal/outbox-status', { role })) } catch { /* abaikan */ } }, [role])
  useEffect(() => { status() }, [status])
  const calc = async () => { setE(null); try { setOut(await req('/v1/sla/calculate', { method: 'POST', role, body: f })) } catch (err) { setE(err) } }
  const tick = async () => { setE(null); try { setOut(await req('/internal/sla-tick', { method: 'POST', role })); status() } catch (err) { setE(err) } }
  const drain = async () => { setE(null); try { setOut(await req('/internal/outbox-drain', { method: 'POST', role })); status() } catch (err) { setE(err) } }
  const notify = async () => { setE(null); try { setOut(await req('/v1/notifications', { method: 'POST', role, body: { ...nt } })) } catch (err) { setE(err) } }

  return (
    <>
      <Err e={e} onClose={() => setE(null)} />
      {st && <div className="grid g2"><Card><div className="stat"><span className="v">{st.pending}</span><span className="l">Notifikasi Outbox Pending</span></div></Card>
        <Card><div className="stat"><span className="v">{st.sent}</span><span className="l">Notifikasi Terkirim</span></div></Card></div>}
      {out && <Card title="Hasil Operasi"><Json data={out} /></Card>}
      <div className="grid g3 mt">
        <Card title="Hitung Batas SLA" sub="Kalkulasi jam kerja operasional; Jumat sore → Senin.">
          <div className="form">
            <div className="form2">
              <label>Objek Layanan<select value={f.object_type} onChange={setF('object_type')}><option>CASE</option><option>TICKET</option></select></label>
              <label>Severity<select value={f.severity} onChange={setF('severity')}>{SEVERITIES.map((o) => <option key={o}>{o}</option>)}</select></label>
            </div>
            <label>Kategori Masalah<input value={f.category} onChange={setF('category')} placeholder="TRANSACTION_DISPUTE" /></label>
            <label>Waktu Masuk (ISO Timestamp)<input value={f.created_at} onChange={setF('created_at')} /></label>
            <div className="row"><button className="btn primary" onClick={calc}>Hitung Batas Waktu SLA</button></div>
          </div>
        </Card>
        <Card title="Pemantauan SLA & Outbox" sub="Pemeriksaan status keterlambatan (Breach) dan pengiriman notifikasi.">
          <div className="row"><button className="btn primary" onClick={tick}>Jalankan Pemeriksaan SLA</button>
            <button className="btn" onClick={drain}>Kirim Antrean Notifikasi</button>
            <button className="btn sm" onClick={status}>Cek Status Outbox</button></div>
        </Card>
        <Card title="Kirim Notifikasi Langsung" sub="Pengiriman pesan ke kanal resmi terdaftar nasabah.">
          <div className="form">
            <label>Kanal Notifikasi<select value={nt.channel} onChange={setNt('channel')}>{['REGISTERED_EMAIL', 'REGISTERED_SMS', 'REGISTERED_PUSH', 'REGISTERED_WHATSAPP'].map((o) => <option key={o}>{o}</option>)}</select></label>
            <label>Tujuan Kontak<input value={nt.target} onChange={setNt('target')} placeholder="nasabah@example.test" /></label>
            <div className="row"><button className="btn primary" onClick={notify}>Kirim Notifikasi</button></div>
          </div>
        </Card>
      </div>
    </>
  )
}

/* ---------- Audit ---------- */
function Audit({ role }) {
  const [corr, setCorr] = useState('')
  const [trail, setTrail] = useState(null)
  const [e, setE] = useState(null)
  const open = async () => {
    setE(null); setTrail(null)
    try { const r = await req(`/v1/audit/trail/${corr}`, { role }); setTrail(r.trail || []) }
    catch (err) { setE(err) }
  }
  return (
    <>
      <p className="alert info">Hanya dapat diakses oleh peran <b>supervisor</b> (izin audit.read). Setiap respons API menyertakan Correlation ID pada header.</p>
      <Err e={e} onClose={() => setE(null)} />
      <Card title="Lacak Correlation ID" sub="Audit Trail berbasis append-only dan hash-chain untuk kepatuhan perbankan.">
        <div className="row"><input value={corr} onChange={(e) => setCorr(e.target.value)} placeholder="Contoh: COR-..." style={{ minWidth: 300 }} />
          <button className="btn primary" onClick={open}>Lacak Jejak Audit</button></div>
      </Card>
      {trail && (
        <Card title={`Jejak Audit Trail (${trail.length} Riwayat Kejadian)`}>
          {!trail.length ? <Empty text="Tidak ada riwayat kejadian untuk Correlation ID ini." /> : (
            <ul className="timeline">{trail.map((t, i) => (
              <li key={i}><b>{t.action || t.event || JSON.stringify(t).slice(0, 80)}</b>
                <div className="t">{t.timestamp || t.ts || t.created_at || ''} • {t.actor_id || t.actor || ''} • {t.service || ''}</div>
              </li>))}</ul>
          )}
          <h3 className="mt">Detail Payload Mentah</h3><Json data={trail} />
        </Card>
      )}
    </>
  )
}

/* ---------- Basis Pengetahuan (Knowledge Manager) ---------- */
function KnowledgeManager({ role }) {
  const [documents, setDocuments] = useState([])
  const [selected, setSelected] = useState(null)
  const [editing, setEditing] = useState(null)
  const [editFile, setEditFile] = useState(null)
  const [savingEdit, setSavingEdit] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [copied, setCopied] = useState(false)

  // Creation panel state
  const [showCreate, setShowCreate] = useState(false)
  const [createMode, setCreateMode] = useState('upload') // 'upload' | 'write'
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadName, setUploadName] = useState('')
  const [uploadSize, setUploadSize] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)

  // Direct text creation state
  const [directTitle, setDirectTitle] = useState('')
  const [directContent, setDirectContent] = useState('')
  const [directSubmitting, setDirectSubmitting] = useState(false)

  // Filter & search state
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  const fileInputRef = useRef(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await req('/v1/knowledge/documents', { role })
      setDocuments(r.items || [])
    } catch (err) { setError(err) }
    finally { setLoading(false) }
  }, [role])

  useEffect(() => {
    load()
    const refreshOnFocus = () => { if (document.visibilityState === 'visible') load() }
    window.addEventListener('focus', refreshOnFocus)
    document.addEventListener('visibilitychange', refreshOnFocus)
    return () => {
      window.removeEventListener('focus', refreshOnFocus)
      document.removeEventListener('visibilitychange', refreshOnFocus)
    }
  }, [load])

  const MAX_SIZE = 10 * 1024 * 1024
  const EXT_ALLOWED = ['.pdf', '.docx', '.txt']

  const handleFile = (file) => {
    if (!file) return
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!EXT_ALLOWED.includes(ext)) {
      setError(new ApiError(400, 'UNSUPPORTED_FORMAT', 'Format berkas tidak didukung. Harap gunakan: ' + EXT_ALLOWED.join(', ')))
      return
    }
    if (file.size > MAX_SIZE) {
      setError(new ApiError(400, 'FILE_TOO_LARGE', 'Ukuran berkas terlalu besar (maksimal 10 MB).'))
      return
    }
    setUploadFile(file)
    setUploadName(file.name)
    setUploadSize(file.size)
    setError(null)
    setNotice(null)
  }

  const handleFileChange = (event) => {
    const file = event.target.files && event.target.files[0]
    handleFile(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0])
    }
  }

  const clearFile = () => {
    setUploadFile(null)
    setUploadName('')
    setUploadSize(0)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const upload = async (event) => {
    event.preventDefault()
    setError(null); setNotice(null)
    if (!uploadFile) { setError(new ApiError(400, 'NO_FILE', 'Pilih berkas terlebih dahulu.')); return }

    setUploading(true)
    const formData = new FormData()
    formData.append('file', uploadFile)
    try {
      const result = await req('/v1/knowledge/documents/upload', { method: 'POST', role, body: formData })
      setNotice(result.status === 'ready'
        ? `Dokumen "${uploadName}" berhasil diproses & diindeks! Status: Siap (${result.chunk_count || 0} potongan teks aktif untuk AI Agent).`
        : (result.message || `Dokumen berstatus ${statusLabel(result.status)}.`))
      clearFile()
      setShowCreate(false)
      await load()
    } catch (err) {
      setError(err)
    } finally { setUploading(false) }
  }

  const handleDirectSubmit = async (event) => {
    event.preventDefault()
    setError(null); setNotice(null)
    const title = directTitle.trim()
    const content = directContent.trim()
    if (!title) { setError(new ApiError(400, 'EMPTY_TITLE', 'Judul dokumen wajib diisi.')); return }
    if (!content) { setError(new ApiError(400, 'EMPTY_CONTENT', 'Isi teks pengetahuan wajib diisi.')); return }

    setDirectSubmitting(true)
    try {
      const safeFilename = `${title.replace(/[^a-zA-Z0-9_\-\u00C0-\u017F ]/g, '').trim() || 'knowledge_article'}.txt`
      const file = new File([content], safeFilename, { type: 'text/plain;charset=utf-8' })
      const formData = new FormData()
      formData.append('file', file)
      formData.append('title', title)

      const result = await req('/v1/knowledge/documents/upload', { method: 'POST', role, body: formData })
      setNotice(result.status === 'ready'
        ? `Knowledge "${title}" berhasil disimpan & diindeks! (${result.chunk_count || 0} potongan teks siap digunakan AI).`
        : (result.message || 'Dokumen pengetahuan berhasil disimpan.'))
      setDirectTitle('')
      setDirectContent('')
      setShowCreate(false)
      await load()
    } catch (err) {
      setError(err)
    } finally {
      setDirectSubmitting(false)
    }
  }

  const retry = async (documentId) => {
    setError(null)
    try {
      const result = await req(`/v1/knowledge/documents/${encodeURIComponent(documentId)}/retry`, { method: 'POST', role })
      setNotice(result.message || 'Dokumen sedang diproses ulang.')
      await load()
    } catch (err) { setError(err) }
  }

  const openDetail = async (documentId) => {
    setError(null)
    setCopied(false)
    try {
      setSelected(await req(`/v1/knowledge/documents/${encodeURIComponent(documentId)}`, { role }))
    } catch (err) { setError(err) }
  }

  const copyText = (text) => {
    if (!text) return
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const openEdit = async (documentId) => {
    setError(null)
    setNotice(null)
    try {
      const doc = await req(`/v1/knowledge/documents/${encodeURIComponent(documentId)}`, { role })
      setEditing({
        document_id: doc.document_id,
        title: doc.title || doc.original_filename || '',
        content: doc.content || '',
        original_filename: doc.original_filename,
        version_no: doc.version_no,
      })
      setEditFile(null)
      setConfirmDelete(null)
    } catch (err) { setError(err) }
  }

  const handleEditFileChange = (event) => {
    const file = event.target.files && event.target.files[0]
    if (!file) { setEditFile(null); return }
    setEditFile(file)
    setError(null)
  }

  const saveEdit = async (event) => {
    event.preventDefault()
    if (!editing) return
    setError(null); setNotice(null)
    const trimmedTitle = (editing.title || '').trim()
    if (!trimmedTitle) {
      setError(new ApiError(400, 'EMPTY_TITLE', 'Judul dokumen tidak boleh kosong.'))
      return
    }

    setSavingEdit(true)
    try {
      let result
      if (editFile) {
        const ext = '.' + editFile.name.split('.').pop().toLowerCase()
        if (!EXT_ALLOWED.includes(ext)) {
          setError(new ApiError(400, 'UNSUPPORTED_FORMAT', 'Format berkas pengganti tidak didukung. Terima: ' + EXT_ALLOWED.join(', ')))
          setSavingEdit(false)
          return
        }
        if (editFile.size > MAX_SIZE) {
          setError(new ApiError(400, 'FILE_TOO_LARGE', 'Berkas pengganti terlalu besar (maks 10 MB).'))
          setSavingEdit(false)
          return
        }
        if (!editFile.size) {
          setError(new ApiError(400, 'EMPTY_FILE', 'Berkas pengganti kosong.'))
          setSavingEdit(false)
          return
        }
        const formData = new FormData()
        formData.append('file', editFile)
        formData.append('title', trimmedTitle)
        result = await req(`/v1/knowledge/documents/${encodeURIComponent(editing.document_id)}/replace`, {
          method: 'POST', role, body: formData,
        })
      } else {
        const trimmedContent = (editing.content || '').trim()
        if (!trimmedContent) {
          setError(new ApiError(400, 'EMPTY_CONTENT', 'Isi teks dokumen tidak boleh kosong.'))
          setSavingEdit(false)
          return
        }
        result = await req(`/v1/knowledge/documents/${encodeURIComponent(editing.document_id)}`, {
          method: 'PUT', role, body: { title: trimmedTitle, content: editing.content },
        })
      }
      setNotice(`${result.message || 'Dokumen berhasil diperbarui.'} Versi: v${result.version_no}; ${result.chunk_count || 0} potongan terindeks.`)
      const editedId = editing.document_id
      setEditing(null)
      setEditFile(null)
      await load()
      if (selected && selected.document_id === editedId) {
        setSelected(await req(`/v1/knowledge/documents/${encodeURIComponent(editedId)}`, { role }))
      }
    } catch (err) {
      setError(err)
    } finally {
      setSavingEdit(false)
    }
  }

  const askDelete = (doc) => {
    setError(null)
    setNotice(null)
    setConfirmDelete(doc)
  }

  const executeDelete = async () => {
    if (!confirmDelete) return
    setError(null); setNotice(null)
    setDeleting(true)
    try {
      const targetId = confirmDelete.document_id
      const result = await req(`/v1/knowledge/documents/${encodeURIComponent(targetId)}`, { method: 'DELETE', role })
      setNotice(result.message || 'Dokumen pengetahuan berhasil dihapus.')
      if (selected && selected.document_id === targetId) setSelected(null)
      if (editing && editing.document_id === targetId) { setEditing(null); setEditFile(null) }
      setConfirmDelete(null)
      await load()
    } catch (err) {
      setError(err)
    } finally {
      setDeleting(false)
    }
  }

  const statusLabel = (s) => {
    const map = { pending: 'Menunggu', processing: 'Sedang diproses', ready: 'Siap', failed: 'Gagal' }
    return map[s] || s
  }

  const statusBadgeClass = (s) => {
    const map = { ready: 'b-green', processing: 'b-blue', pending: 'b-amber', failed: 'b-red' }
    return `badge ${map[s] || 'b-gray'}`
  }

  // Calculated overview stats
  const totalDocs = documents.length
  const readyDocs = documents.filter((d) => d.status === 'ready').length
  const totalChunks = documents.reduce((acc, d) => acc + (d.chunk_count || 0), 0)
  const totalSizeBytes = documents.reduce((acc, d) => acc + (d.file_size || 0), 0)
  const totalSizeFormatted = (totalSizeBytes / 1024).toFixed(1) + ' KB'

  // Filtered documents
  const filteredDocs = documents.filter((d) => {
    const matchesSearch = !searchQuery ||
      (d.title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (d.original_filename || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (d.uploaded_by || '').toLowerCase().includes(searchQuery.toLowerCase())

    const matchesStatus = statusFilter === 'all' || d.status === statusFilter
    return matchesSearch && matchesStatus
  })

  return (
    <section className="km-workspace">
      {/* Top bar with quick title & toggle create button */}
      <div className="km-topbar">
        <div className="km-topbar-copy">
          <h2>Knowledge Base Manager</h2>
          <p>Kelola dokumen referensi resmi dan materi kebijakan yang digunakan AI Customer Service untuk menjawab pertanyaan pelanggan.</p>
        </div>
        <button
          type="button"
          className="btn primary"
          onClick={() => setShowCreate(!showCreate)}
        >
          {showCreate ? 'Tutup Formulir Input' : '+ Tambah Knowledge Base Baru'}
        </button>
      </div>

      <Err e={error} onClose={() => setError(null)} />
      {notice && (
        <div className="alert ok chat-notice" role="status">
          <span>{notice}</span>
          <button type="button" className="btn sm" style={{ marginLeft: 'auto' }} onClick={() => setNotice(null)}>✕</button>
        </div>
      )}

      {/* KPI / Stats Overview Row */}
      <div className="km-stats-row">
        <div className="km-stat-box">
          <span className="km-stat-label">Total Dokumen</span>
          <span className="km-stat-value">{totalDocs}</span>
          <span className="km-stat-meta">Materi terdaftar di sistem</span>
        </div>
        <div className="km-stat-box">
          <span className="km-stat-label">Dokumen Siap (Ready)</span>
          <span className="km-stat-value" style={{ color: 'var(--success)' }}>{readyDocs}</span>
          <span className="km-stat-meta">Aktif untuk retrieval AI</span>
        </div>
        <div className="km-stat-box">
          <span className="km-stat-label">Total Potongan (Chunks)</span>
          <span className="km-stat-value" style={{ color: 'var(--electric-blue)' }}>{totalChunks}</span>
          <span className="km-stat-meta">Unit vektor & teks terindeks</span>
        </div>
        <div className="km-stat-box">
          <span className="km-stat-label">Total Kapasitas</span>
          <span className="km-stat-value">{totalSizeFormatted}</span>
          <span className="km-stat-meta">Ukuran dokumen tersimpan</span>
        </div>
      </div>

      {/* Panel Tambah Knowledge Baru (Expandable) */}
      {showCreate && (
        <div className="km-card" style={{ borderColor: 'var(--electric-blue)' }}>
          <div className="km-card-header">
            <div>
              <h3 className="km-card-title">Tambah Materi Knowledge Base</h3>
              <p className="km-card-sub">Pilih metode penambahan: unggah berkas PDF/DOCX/TXT atau tulis dokumen teks langsung.</p>
            </div>
            <div className="km-tabs">
              <button
                type="button"
                className={`km-tab-btn ${createMode === 'upload' ? 'active' : ''}`}
                onClick={() => setCreateMode('upload')}
              >
                Unggah Berkas File
              </button>
              <button
                type="button"
                className={`km-tab-btn ${createMode === 'write' ? 'active' : ''}`}
                onClick={() => setCreateMode('write')}
              >
                Tulis Teks Langsung
              </button>
            </div>
          </div>

          {createMode === 'upload' ? (
            <form className="form" onSubmit={upload}>
              <div
                className={`km-dropzone ${isDragOver ? 'drag-active' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setIsDragOver(true) }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  id="knowledge-document-file"
                  type="file"
                  accept=".pdf,.docx,.txt"
                  style={{ display: 'none' }}
                  onChange={handleFileChange}
                />
                <div className="km-dropzone-icon">📁</div>
                <h4>Tarik & lepas berkas ke sini, atau klik untuk memilih</h4>
                <p>Mendukung format berkas <strong>PDF, DOCX, dan TXT</strong> (maksimal 10 MB).</p>
              </div>

              {uploadFile && (
                <div className="km-file-preview">
                  <div>
                    <strong>{uploadName}</strong>
                    <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--muted)' }}>
                      ({(uploadSize / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                  <button type="button" className="btn sm danger" onClick={clearFile}>Batalkan</button>
                </div>
              )}

              <div className="row mt" style={{ justifyContent: 'flex-end', gap: 10 }}>
                <button type="button" className="btn" onClick={() => setShowCreate(false)}>Tutup</button>
                <button type="submit" className="btn primary" disabled={uploading || !uploadFile}>
                  {uploading ? <><span className="button-spinner" aria-hidden="true" />Memproses & Mengindeks…</> : 'Unggah & Indeks ke AI'}
                </button>
              </div>
            </form>
          ) : (
            <form className="form" onSubmit={handleDirectSubmit}>
              <label htmlFor="direct-kb-title">
                Judul Pengetahuan (Title)
                <input
                  id="direct-kb-title"
                  type="text"
                  placeholder="Contoh: Prosedur Pengembalian Dana & Ganti Metode Pembayaran"
                  value={directTitle}
                  onChange={(e) => setDirectTitle(e.target.value)}
                  required
                />
              </label>

              <label htmlFor="direct-kb-content">
                Isi Teks Pengetahuan (Content)
                <textarea
                  id="direct-kb-content"
                  rows={8}
                  placeholder="Tuliskan materi kebijakan, SOP, atau panduan secara rinci di sini. Teks ini akan otomatis dipotong (chunking) dan diindeks agar langsung dapat dijawab oleh AI..."
                  value={directContent}
                  onChange={(e) => setDirectContent(e.target.value)}
                  required
                />
              </label>

              <div className="row mt" style={{ justifyContent: 'flex-end', gap: 10 }}>
                <button type="button" className="btn" onClick={() => setShowCreate(false)}>Tutup</button>
                <button type="submit" className="btn primary" disabled={directSubmitting || !directTitle.trim() || !directContent.trim()}>
                  {directSubmitting ? <><span className="button-spinner" aria-hidden="true" />Menyimpan & Mengindeks…</> : 'Simpan & Indeks ke AI'}
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* Konfirmasi Hapus Modal/Card */}
      {confirmDelete && (
        <Card title={`Konfirmasi Hapus: ${confirmDelete.title || confirmDelete.original_filename}`} wide>
          <p className="sub" style={{ marginBottom: 14 }}>
            Apakah Anda yakin ingin menghapus dokumen <strong>{confirmDelete.title || confirmDelete.original_filename}</strong>?
            Seluruh potongan indeks ({confirmDelete.chunk_count || 0} potongan) akan dihapus secara permanen dari pencarian chatbot AI.
          </p>
          <div className="row" style={{ gap: 8 }}>
            <button type="button" className="btn danger" disabled={deleting} onClick={executeDelete}>
              {deleting ? 'Menghapus…' : 'Ya, Hapus Dokumen'}
            </button>
            <button type="button" className="btn" disabled={deleting} onClick={() => setConfirmDelete(null)}>Batal</button>
          </div>
        </Card>
      )}

      {/* Main Document Catalog Card (Full Width) */}
      <div className="km-card">
        <div className="km-card-header">
          <div>
            <h3 className="km-card-title">Katalog Dokumen Pengetahuan ({filteredDocs.length} dari {documents.length})</h3>
            <p className="km-card-sub">Seluruh materi yang berstatus Siap digunakan oleh AI Customer Service dalam proses knowledge retrieval.</p>
          </div>
          <button className="btn sm" onClick={load} disabled={loading}>
            {loading ? 'Menyinkronkan...' : '↻ Muat Ulang'}
          </button>
        </div>

        {/* Filter & Live Search Controls */}
        <div className="km-controls">
          <div className="km-search-box">
            <span className="km-search-icon">🔍</span>
            <input
              type="text"
              placeholder="Cari berdasarkan judul, nama file, atau pengunggah..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="km-filter-pills">
            <button
              type="button"
              className={`km-pill ${statusFilter === 'all' ? 'active' : ''}`}
              onClick={() => setStatusFilter('all')}
            >
              Semua ({documents.length})
            </button>
            <button
              type="button"
              className={`km-pill ${statusFilter === 'ready' ? 'active' : ''}`}
              onClick={() => setStatusFilter('ready')}
            >
              Siap ({documents.filter((d) => d.status === 'ready').length})
            </button>
            <button
              type="button"
              className={`km-pill ${statusFilter === 'processing' ? 'active' : ''}`}
              onClick={() => setStatusFilter('processing')}
            >
              Memproses ({documents.filter((d) => d.status === 'processing').length})
            </button>
            <button
              type="button"
              className={`km-pill ${statusFilter === 'failed' ? 'active' : ''}`}
              onClick={() => setStatusFilter('failed')}
            >
              Gagal ({documents.filter((d) => d.status === 'failed').length})
            </button>
          </div>
        </div>

        {/* Full-width Table */}
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Judul & Berkas Dokumen</th>
                <th>Ukuran</th>
                <th>Versi</th>
                <th>Status</th>
                <th>Potongan Teks</th>
                <th>Pengunggah</th>
                <th>Waktu Diperbarui</th>
                <th style={{ textAlign: 'right' }}>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {filteredDocs.length === 0 ? (
                <tr>
                  <td colSpan="8">
                    <Empty text={documents.length === 0 ? 'Belum ada dokumen pengetahuan. Klik tombol "+ Tambah Knowledge Base Baru" di atas untuk menambahkan.' : 'Tidak ada dokumen yang cocok dengan filter pencarian.'} />
                  </td>
                </tr>
              ) : (
                filteredDocs.map((d) => (
                  <tr key={d.document_id}>
                    <td>
                      <strong style={{ color: 'var(--ink)' }}>{d.title || d.original_filename}</strong>
                      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                        {d.original_filename && d.original_filename !== d.title ? `${d.original_filename} • ` : ''}
                        <span style={{ fontFamily: 'var(--font-mono)' }}>{d.mime_type || '-'}</span>
                      </div>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>{(d.file_size / 1024).toFixed(1)} KB</td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>v{d.version_no}</td>
                    <td><span className={statusBadgeClass(d.status)}>{statusLabel(d.status)}</span></td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{d.chunk_count} chunk</td>
                    <td><span style={{ color: 'var(--ink-soft)' }}>{d.uploaded_by || '-'}</span></td>
                    <td style={{ color: 'var(--muted)', fontSize: 11 }}>
                      {d.created_at ? new Date(d.created_at).toLocaleString() : '-'}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div className="row" style={{ gap: 6, justifyContent: 'flex-end' }}>
                        {d.status === 'failed' && (
                          <button type="button" className="btn sm primary" onClick={() => retry(d.document_id)}>Coba Lagi</button>
                        )}
                        <button type="button" className="btn sm" onClick={() => openDetail(d.document_id)}>Detail</button>
                        <button type="button" className="btn sm" onClick={() => openEdit(d.document_id)}>Edit</button>
                        <button type="button" className="btn sm danger" onClick={() => askDelete(d)}>Hapus</button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Edit Form Modal/Card */}
      {editing && (
        <div className="mt">
          <Card title={`Edit Dokumen: ${editing.original_filename || editing.title} (v${editing.version_no})`} sub="Perbarui judul, sunting isi teks pengetahuan secara langsung, atau unggah berkas revisi baru untuk diindeks ulang." wide>
            <form className="form" onSubmit={saveEdit}>
              <label htmlFor="knowledge-edit-title">
                Judul Dokumen
                <input
                  id="knowledge-edit-title"
                  type="text"
                  value={editing.title}
                  onChange={(e) => setEditing({ ...editing, title: e.target.value })}
                  required
                />
              </label>

              <label htmlFor="knowledge-edit-file">
                Ganti dengan Berkas Revisi Baru (Opsional — PDF, DOCX, TXT)
                <input
                  id="knowledge-edit-file"
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={handleEditFileChange}
                />
              </label>
              {editFile && (
                <div className="row" style={{ gap: 8 }}>
                  <span className="badge b-blue">Berkas baru: {editFile.name} ({(editFile.size / 1024).toFixed(1)} KB)</span>
                  <button type="button" className="btn sm" onClick={() => setEditFile(null)}>Batal ganti berkas</button>
                </div>
              )}

              {!editFile && (
                <label htmlFor="knowledge-edit-content">
                  Isi Teks Pengetahuan (Akan dipotong/di-chunk & diindeks ulang saat disimpan)
                  <textarea
                    id="knowledge-edit-content"
                    rows={10}
                    value={editing.content}
                    onChange={(e) => setEditing({ ...editing, content: e.target.value })}
                    placeholder="Masukkan atau perbarui isi teks dokumen pengetahuan..."
                  />
                </label>
              )}

              <div className="row mt" style={{ gap: 8 }}>
                <button type="submit" className="btn primary" disabled={savingEdit}>
                  {savingEdit ? <><span className="button-spinner" aria-hidden="true" />Menyimpan…</> : 'Simpan & Indeks Ulang'}
                </button>
                <button type="button" className="btn" disabled={savingEdit} onClick={() => { setEditing(null); setEditFile(null) }}>
                  Batal
                </button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Detail Modal/Card */}
      {selected && (
        <div className="mt">
          <Card title={`Detail Pengetahuan: ${selected.title || selected.original_filename}`} wide>
            <div className="kv">
              <dt>Document ID</dt><dd style={{ fontFamily: 'var(--font-mono)' }}>{selected.document_id}</dd>
              <dt>Judul</dt><dd><strong>{selected.title || selected.original_filename}</strong></dd>
              <dt>Berkas Asli</dt><dd>{selected.original_filename}</dd>
              <dt>Format / MIME</dt><dd style={{ fontFamily: 'var(--font-mono)' }}>{selected.mime_type || '-'}</dd>
              <dt>Ukuran</dt><dd style={{ fontFamily: 'var(--font-mono)' }}>{(selected.file_size / 1024).toFixed(1)} KB</dd>
              <dt>Versi</dt><dd style={{ fontFamily: 'var(--font-mono)' }}>v{selected.version_no}</dd>
              <dt>Status Indeks</dt><dd><span className={`badge ${statusBadgeClass(selected.status)}`}>{statusLabel(selected.status)}</span></dd>
              <dt>Potongan Teks</dt><dd><strong>{selected.chunk_count} chunk</strong> tersedia untuk AI</dd>
              <dt>Diunggah Oleh</dt><dd>{selected.uploaded_by || '-'} ({selected.uploaded_by_type || '-'})</dd>
              <dt>Waktu Dibuat</dt><dd>{selected.created_at || '-'}</dd>
              <dt>Waktu Diperbarui</dt><dd>{selected.updated_at || '-'}</dd>
              {selected.status === 'failed' && selected.error_message ? (
                <><dt>Pesan Kesalahan</dt><dd style={{ color: 'var(--danger)' }}>{selected.error_message}</dd></>
              ) : null}
            </div>

            {selected.content && (
              <div className="mt" style={{ borderTop: '1px solid var(--line)', paddingTop: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <strong style={{ fontSize: 12, color: 'var(--ink)' }}>Isi Teks Terindeks (Indexed Knowledge):</strong>
                  <button type="button" className="btn sm" onClick={() => copyText(selected.content)}>
                    {copied ? '✓ Tersalin!' : 'Salin Teks'}
                  </button>
                </div>
                <pre className="dump" style={{ whiteSpace: 'pre-wrap', maxHeight: 360, background: '#0b1523', border: '1px solid var(--sidebar-border)' }}>
                  {selected.content}
                </pre>
              </div>
            )}

            <div className="row mt" style={{ gap: 8, justifyContent: 'flex-end' }}>
              <button type="button" className="btn" onClick={() => { setSelected(null); load() }}>Tutup</button>
              <button type="button" className="btn" onClick={() => openEdit(selected.document_id)}>Edit Dokumen</button>
              <button type="button" className="btn danger" onClick={() => askDelete(selected)}>Hapus Dokumen</button>
              {selected.status === 'failed' && (
                <button type="button" className="btn primary" onClick={() => { retry(selected.document_id); setSelected(null) }}>Coba Lagi Proses</button>
              )}
            </div>
          </Card>
        </div>
      )}
    </section>
  )
}
