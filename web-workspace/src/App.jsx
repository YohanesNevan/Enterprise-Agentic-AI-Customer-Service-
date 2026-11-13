import React, { useEffect, useRef, useState } from 'react'
import './app.css'
import { devCustomerLogout, getAuthSession, subscribeAuth } from './api.js'
import { ROUTES, CUSTOMER_LINKS } from './routes.js'
import { navigate } from './shared/navigation.js'
import { StatePanel } from './shared/ui.jsx'
import { staffNavigationFor } from './workspace-access.js'
import CustomerHome from './pages/customer/CustomerHome.jsx'
import UniversalLogin from './pages/customer/UniversalLogin.jsx'
import CustomerChat, { CustomerChatPreview } from './pages/customer/CustomerChat.jsx'
import CustomerHistory from './pages/customer/CustomerHistory.jsx'
import CustomerRequest from './pages/customer/CustomerRequest.jsx'
import CustomerTrack from './pages/customer/CustomerTrack.jsx'
import CustomerAccount from './pages/customer/CustomerAccount.jsx'
import Dashboard from './pages/workspace/Dashboard.jsx'
import Queue from './pages/workspace/Queue.jsx'
import ConversationWorkbench from './pages/workspace/ConversationWorkbench.jsx'
import Cases from './pages/workspace/Cases.jsx'
import Approvals from './pages/workspace/Approvals.jsx'
import QA from './pages/workspace/QA.jsx'
import Analytics from './pages/workspace/Analytics.jsx'
import SLA from './pages/workspace/SLA.jsx'
import Audit from './pages/workspace/Audit.jsx'
import KnowledgeManager from './pages/workspace/KnowledgeManager.jsx'

const PAGE_COMPONENTS = {
  login: UniversalLogin,
  'customer-chat': CustomerChat,
  'customer-history': CustomerHistory,
  'customer-request': CustomerRequest,
  'customer-track': CustomerTrack,
  'customer-account': CustomerAccount,
  dash: Dashboard,
  queue: Queue,
  conv: ConversationWorkbench,
  cases: Cases,
  approvals: Approvals,
  qa: QA,
  analytics: Analytics,
  sla: SLA,
  audit: Audit,
  knowledge: KnowledgeManager,
}

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
  const isStaff = Boolean(session && role && role !== 'customer')
  const staffHome = staffNavigationFor(role)[0]?.[0] || '/agent/queue'
  const homePath = isStaff ? staffHome : '/'

  const customerRoute = route?.audience === 'customer'
  const isPublic = !isStaff && (path === '/' || path === '/customer/login' || path === '/staff/login' || path === '/login')
  const permitted = customerRoute ? role === 'customer' : Array.isArray(route?.audience) ? route.audience.includes(role) : route?.audience === role
  const needsAuth = !isPublic && !session
  const navItems = isPublic || (customerRoute && (!session || role === 'customer')) ? CUSTOMER_LINKS : staffNavigationFor(role)
  const title = route?.title || (isPublic ? 'Layanan pelanggan' : 'Halaman tidak ditemukan')
  const Page = PAGE_COMPONENTS[route?.page]
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
