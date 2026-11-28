import React, { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, getAuthSession, req, subscribeAuth } from '../../api.js'
import { customerConversationState, navigate } from '../../shared/navigation.js'

const GUEST_SESSION_KEY = 'eaics_guest_chat_session'

function VerificationModal({ title, subtitle, onClose, children }) {
  const dialogRef = useRef(null)

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const target = dialogRef.current?.querySelector(
      '.chat-modal-body input, .chat-modal-body textarea, .chat-modal-body select, .chat-modal-body button',
    )
    target?.focus?.()
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [onClose])

  return (
    <div
      className="chat-modal-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        className="chat-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="chat-verification-title"
        aria-describedby={subtitle ? 'chat-verification-subtitle' : undefined}
        ref={dialogRef}
      >
        <div className="chat-modal-head">
          <div>
            <h3 id="chat-verification-title">{title}</h3>
            {subtitle && <p id="chat-verification-subtitle">{subtitle}</p>}
          </div>
          <button
            type="button"
            className="chat-modal-close"
            aria-label="Tutup jendela verifikasi"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <div className="chat-modal-body">{children}</div>
      </div>
    </div>
  )
}

const TIER_META = {
  1: {
    code: 'PUBLIC_INFORMATION',
    label: 'Informasi Publik',
    hint: 'Tanpa login. Jawaban dibatasi pada informasi produk & layanan.',
  },
  2: {
    code: 'PERSONAL_INQUIRY',
    label: 'Pertanyaan Pribadi',
    hint: 'Status order/transaksi hanya setelah masuk ke akun Anda.',
  },
  3: {
    code: 'SENSITIVE_REQUEST',
    label: 'Permintaan Sensitif',
    hint: 'Perubahan data/pemblokiran memerlukan OTP dan persetujuan Anda.',
  },
  4: {
    code: 'HIGH_RISK_ACTION',
    label: 'Tindakan Berisiko Tinggi',
    hint: 'AI hanya menyiapkan permintaan; petugas wajib menyetujui.',
  },
}

function readStoredGuestSession() {
  try {
    const raw = sessionStorage.getItem(GUEST_SESSION_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed && parsed.token && parsed.conversationId ? parsed : null
  } catch {
    return null
  }
}

function storeGuestSession(guestSession) {
  if (!guestSession?.session_token || !guestSession?.conversation_id) return null
  const record = {
    token: guestSession.session_token,
    conversationId: guestSession.conversation_id,
    expiresAt: guestSession.expires_in
      ? new Date(Date.now() + guestSession.expires_in * 1000).toISOString()
      : null,
  }
  try {
    sessionStorage.setItem(GUEST_SESSION_KEY, JSON.stringify(record))
  } catch {
    return record
  }
  return record
}

function guestTokenFor(conversationId) {
  const stored = readStoredGuestSession()
  if (!stored || !conversationId) return null
  return stored.conversationId === conversationId ? stored.token : null
}

function clearStoredGuestSession() {
  try {
    sessionStorage.removeItem(GUEST_SESSION_KEY)
  } catch {
    // ignore storage failures
  }
}

function formatClock(value) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })
}

function tierOf(value) {
  const tier = Number(value)
  return TIER_META[tier] ? tier : 1
}


function formatConversationTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${hours}.${minutes}`
}

function groupConversationHistory(items) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const groups = new Map()

  items.forEach((item) => {
    const date = new Date(item.last_activity_at)
    const day = new Date(date)
    day.setHours(0, 0, 0, 0)
    const label = Number.isNaN(day.getTime())
      ? 'Percakapan Lain'
      : day.getTime() === today.getTime()
      ? 'Hari Ini'
      : day.getTime() === yesterday.getTime()
      ? 'Kemarin'
      : day.toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric' })
    if (!groups.has(label)) groups.set(label, [])
    groups.get(label).push(item)
  })

  return Array.from(groups, ([label, conversations]) => ({ label, conversations }))
}

function CustomerChatHistoryPanel({
  items,
  groups,
  activeId,
  search,
  onSearch,
  cursor,
  loading,
  error,
  onRetry,
  onLoadMore,
  onSelect,
  onStartNew,
  newChatRef,
  narrow,
  open,
  onClose,
  busy,
  authenticated,
}) {
  return (
    <aside
      id="customer-chat-history"
      className={`chat-history-panel${narrow && open ? ' drawer-open' : ''}`}
      aria-labelledby="chat-history-title"
      aria-hidden={narrow && !open ? 'true' : undefined}
      aria-modal={narrow && open ? 'true' : undefined}
      role={narrow && open ? 'dialog' : undefined}
    >
      <div className="chat-history-heading">
        <div>
          <h2 id="chat-history-title">Riwayat Chat</h2>
          <p>Percakapan Anda sebelumnya</p>
        </div>
        {narrow && (
          <button
            type="button"
            className="chat-history-close"
            aria-label="Tutup riwayat chat"
            onClick={onClose}
          >
            ×
          </button>
        )}
      </div>

      <button
        ref={newChatRef}
        type="button"
        className="chat-history-new"
        onClick={onStartNew}
        disabled={busy}
        title="Mulai percakapan baru"
      >
        <span>+</span> Mulai Chat Baru
      </button>

      <div className="chat-history-search">
        <input
          id="chat-history-search-input"
          type="search"
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Cari percakapan..."
          maxLength={120}
          aria-controls="chat-history-list"
        />
        <span className="chat-history-search-icon" aria-hidden="true">⌕</span>
      </div>

      <div
        id="chat-history-list"
        className="chat-history-list"
        aria-live="polite"
        aria-busy={loading}
      >
        {loading && !items.length ? (
          <div className="chat-history-state" role="status">
            <span className="chat-history-spinner" aria-hidden="true" />
            <p>Memuat riwayat...</p>
          </div>
        ) : !authenticated ? (
          <div className="chat-history-state chat-history-guest" role="status">
            <p>Riwayat chat tersedia setelah Anda masuk ke akun.</p>
            <p className="chat-history-guest-note">
              Anda tetap dapat bertanya tentang informasi publik tanpa login.
            </p>
            <a
              className="btn sm primary"
              href="/customer/login"
              onClick={(event) => {
                event.preventDefault()
                navigate('/customer/login')
              }}
            >
              Masuk untuk Riwayat ↗
            </a>
          </div>
        ) : error ? (
          <div className="chat-history-state chat-history-error" role="alert">
            <p>Riwayat chat gagal dimuat.</p>
            <button type="button" className="btn sm" onClick={onRetry}>
              Coba lagi
            </button>
          </div>
        ) : !items.length ? (
          <div className="chat-history-state" role="status">
            {search.trim()
              ? 'Tidak ada percakapan yang cocok dengan pencarian.'
              : 'Belum ada riwayat chat. Mulai percakapan baru untuk membuat riwayat.'}
          </div>
        ) : (
          <>
            {groups.map(({ label, conversations }) => (
              <section className="chat-history-group" key={label} aria-label={label}>
                <h3>{label}</h3>
                <ul>
                  {conversations.map((item) => {
                    const active = activeId === item.conversation_id
                    return (
                      <li key={item.conversation_id}>
                        <button
                          type="button"
                          className={`chat-history-item${active ? ' is-active' : ''}`}
                          aria-current={active ? 'true' : undefined}
                          onClick={() => onSelect(item.conversation_id)}
                          disabled={busy}
                          title={item.title || 'Percakapan layanan'}
                        >
                          <strong className="chat-history-item-title">
                            {item.title || 'Percakapan layanan'}
                          </strong>
                          <span className="chat-history-preview">
                            {item.preview || 'Belum ada pesan'}
                          </span>
                          <span className="chat-history-meta">
                            <time dateTime={item.last_activity_at}>
                              {formatConversationTime(item.last_activity_at)}
                            </time>
                            {active && (
                              <>
                                <span className="chat-history-meta-sep" aria-hidden="true">·</span>
                                <span className="chat-history-active-label">Sedang dibuka</span>
                              </>
                            )}
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </section>
            ))}
            {loading && (
              <div className="chat-history-loading-more" role="status">
                Memuat percakapan...
              </div>
            )}
            {cursor && (
              <button
                type="button"
                className="chat-history-load-more"
                disabled={loading}
                onClick={onLoadMore}
              >
                {loading ? 'Memuat...' : 'Muat percakapan sebelumnya'}
              </button>
            )}
          </>
        )}
      </div>

      <div className="chat-history-footer">
        <span>Semua percakapan tersimpan di sini.</span>
      </div>
    </aside>
  )
}

export function CustomerChatPreview() {
  return (
    <div className="chat-container-card customer-chat-preview" aria-labelledby="chat-preview-title">
      <div className="chat-card-header">
        <div className="chat-agent-profile">
          <div className="chat-agent-avatar" aria-hidden="true">
            ✦
            <span className="chat-online-dot" title="Online" />
          </div>
          <div className="chat-agent-info">
            <h3 id="chat-preview-title">NEXORA AI Assistant</h3>
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
            <strong>NEXORA AI Assistant</strong>
            <small>Siap membantu</small>
          </div>
          <p>Halo! Selamat datang di layanan NEXORA. Saya dapat membantu menjawab pertanyaan seputar produk komputasi awan, basis data, jam operasional, serta keluhan teknis Anda. Silakan masuk terlebih dahulu untuk memulai percakapan aktif.</p>
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

export function FormattedMessage({ text }) {
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

export function ChatHandoffTrackCard({ conversationId, status, occurredAt }) {
  const currentStatus = status || 'PENDING_HANDOFF'
  const isQueued = currentStatus === 'PENDING_HANDOFF' || currentStatus === 'NEW'
  const isActive = currentStatus === 'ACTIVE_HUMAN'
  const stateLabel = customerConversationState(currentStatus)
  const dateFormatted = occurredAt
    ? new Date(occurredAt).toLocaleString('id-ID')
    : new Date().toLocaleString('id-ID')

  return (
    <div className="chat-tracking-card" role="region" aria-label="Status Pelacakan Layanan">
      <div className="chat-tracking-header">
        <span className={`chat-tracking-badge ${isQueued ? 'queued' : isActive ? 'active' : 'other'}`}>
          <span className="chat-tracking-dot" aria-hidden="true" />
          {stateLabel}
        </span>
        <span className="chat-tracking-meta">Aktivitas terakhir {dateFormatted}</span>
      </div>
      <div className="chat-tracking-body">
        <h4>Percakapan layanan</h4>
        <p className="chat-tracking-ref">{conversationId}</p>
      </div>
      <div className="chat-tracking-footer">
        <span className="chat-tracking-sync-note">
          Tiket investigasi dan percakapan tersinkronisasi secara otomatis dengan pusat operasional EAICS.
        </span>
        <a
          href="/customer/track"
          className="chat-tracking-link"
          onClick={(e) => {
            e.preventDefault()
            navigate('/customer/track')
          }}
          title="Buka halaman pelacakan status & SLA tiket"
        >
          Lacak Status ↗
        </a>
      </div>
    </div>
  )
}

export default function CustomerChat() {
  const getInitialConversationId = () => {
    const fromUrl = new URLSearchParams(window.location.search).get('conversation_id')
    if (fromUrl) return fromUrl
    try {
      return sessionStorage.getItem('eaics_active_customer_conversation_id') || null
    } catch {
      return null
    }
  }

  const [text, setText] = useState(() => new URLSearchParams(window.location.search).get('draft') || '')
  const [conversationId, setConversationId] = useState(getInitialConversationId)
  const [conversationStatus, setConversationStatus] = useState(null)
  const [messages, setMessages] = useState([])
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [retryInfo, setRetryInfo] = useState(null)
  const [historyItems, setHistoryItems] = useState([])
  const [historySearch, setHistorySearch] = useState('')
  const [historyCursor, setHistoryCursor] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState(null)
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false)
  const [isNarrow, setIsNarrow] = useState(() => window.matchMedia('(max-width: 900px)').matches)
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [showScrollBottom, setShowScrollBottom] = useState(false)
  const [authSession, setAuthSession] = useState(null)
  const [guestSession, setGuestSession] = useState(readStoredGuestSession)
  const [sessionInfo, setSessionInfo] = useState(null)
  const [tier, setTier] = useState(null)
  const [stepUp, setStepUp] = useState(null)
  const [verifyModalOpen, setVerifyModalOpen] = useState(true)
  const [consentChecked, setConsentChecked] = useState(false)
  const [consentBusy, setConsentBusy] = useState(false)
  const [pendingText, setPendingText] = useState(null)
  const submitLock = useRef(false)
  const authSessionRef = useRef(null)
  const claimAttemptedRef = useRef(false)
  const accountLoadDoneRef = useRef(false)
  const messagesEndRef = useRef(null)
  const transcriptRef = useRef(null)
  const isNearBottomRef = useRef(true)
  const historyRequestRef = useRef(0)
  const lastMessageSignatureRef = useRef('')
  const historyToggleRef = useRef(null)
  const historyNewChatRef = useRef(null)
  const drawerWasOpenRef = useRef(false)

  const updateActiveConversation = useCallback((id) => {
    setConversationId(id)
    try {
      const url = new URL(window.location.href)
      if (id) {
        sessionStorage.setItem('eaics_active_customer_conversation_id', id)
        url.searchParams.set('conversation_id', id)
      } else {
        sessionStorage.removeItem('eaics_active_customer_conversation_id')
        url.searchParams.delete('conversation_id')
      }
      url.searchParams.delete('draft')
      window.history.replaceState({}, '', url)
    } catch {
      // Safe fallback
    }
  }, [])

  const loadHistory = useCallback(async (search, cursor = null, append = false) => {
    if (!authSessionRef.current) {
      // Guest mode: conversation history belongs to an account.
      setHistoryLoading(false)
      setHistoryError(null)
      return
    }
    const requestId = ++historyRequestRef.current
    setHistoryLoading(true)
    setHistoryError(null)
    if (!append) {
      setHistoryCursor(null)
    }
    const params = new URLSearchParams({ limit: '50' })
    if (search.trim()) params.set('search', search.trim())
    if (cursor) params.set('cursor', cursor)
    try {
      const data = await req(`/v1/customer/conversations?${params.toString()}`)
      if (requestId !== historyRequestRef.current) return
      setHistoryItems((current) => {
        const byId = new Map((append ? current : []).map((item) => [item.conversation_id, item]))
        for (const item of data.items || []) byId.set(item.conversation_id, item)
        return Array.from(byId.values()).sort((a, b) => (
          new Date(b.last_activity_at).getTime() - new Date(a.last_activity_at).getTime()
          || b.conversation_id.localeCompare(a.conversation_id)
        ))
      })
      setHistoryCursor(data.next_cursor || null)
    } catch (err) {
      if (requestId === historyRequestRef.current) setHistoryError(err)
    } finally {
      if (requestId === historyRequestRef.current) setHistoryLoading(false)
    }
  }, [])

  const filteredHistoryItems = React.useMemo(() => {
    const query = historySearch.trim().toLowerCase()
    if (!query) return historyItems
    return historyItems.filter((item) => {
      const title = (item.title || '').toLowerCase()
      const preview = (item.preview || '').toLowerCase()
      const convId = (item.conversation_id || '').toLowerCase()
      return title.includes(query) || preview.includes(query) || convId.includes(query)
    })
  }, [historyItems, historySearch])

  const historyGroups = React.useMemo(() => {
    return groupConversationHistory(filteredHistoryItems)
  }, [filteredHistoryItems])

  useEffect(() => {
    const media = window.matchMedia('(max-width: 900px)')
    const update = () => setIsNarrow(media.matches)
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => loadHistory(historySearch), historySearch ? 250 : 0)
    return () => clearTimeout(timer)
  }, [historySearch, loadHistory])

  useEffect(() => {
    if (!isNarrow) return undefined
    if (historyDrawerOpen) historyNewChatRef.current?.focus()
    else if (drawerWasOpenRef.current) historyToggleRef.current?.focus()
    drawerWasOpenRef.current = historyDrawerOpen
    return undefined
  }, [historyDrawerOpen, isNarrow])

  useEffect(() => {
    if (!isNarrow || !historyDrawerOpen) return undefined
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setHistoryDrawerOpen(false)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [historyDrawerOpen, isNarrow])

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
    updateActiveConversation(null)
    setMessages([])
    setConversationStatus(null)
    setText('')
    setRetryInfo(null)
    setNotice('Sesi percakapan baru siap — kirim pesan untuk memulai obrolan baru.')
    setError(null)
    setTier(null)
    setStepUp(null)
    setPendingText(null)
    setConsentChecked(false)
    isNearBottomRef.current = true
    setShowScrollBottom(false)
    setHistoryDrawerOpen(false)
  }

  const load = useCallback(async (id) => {
    const guestToken = guestTokenFor(id)
    if (!authSessionRef.current && !guestToken) {
      setMessages([])
      setHistoryLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      let cursor = null
      const all = []
      let convStatus = null
      do {
        const suffix = cursor ? `?limit=100&cursor=${encodeURIComponent(cursor)}` : '?limit=100'
        const data = await req(
          `/v1/conversations/${encodeURIComponent(id)}/read-model${suffix}`,
          guestToken ? { auth: 'optional', headers: { 'X-Guest-Session': guestToken } } : {},
        )
        all.push(...(data.messages || []))
        if (data.conversation?.status) convStatus = data.conversation.status
        cursor = data.next_cursor
      } while (cursor)
      setConversationId(id)
      if (convStatus) setConversationStatus(convStatus)
      setMessages(all)
      lastMessageSignatureRef.current = all.map((message) => message.message_id || `${message.sequence_no}:${message.occurred_at}`).join('|')
      setTimeout(() => scrollToBottom(true), 80)
    } catch (err) {
      if (err?.status === 401 && !authSessionRef.current) {
        clearStoredGuestSession()
        setGuestSession(null)
        setNotice('Sesi tamu telah berakhir. Kirim pesan baru untuk memulai percakapan publik.')
      } else {
        setError(err)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const initialId = getInitialConversationId()
    if (initialId) {
      const url = new URL(window.location.href)
      if (url.searchParams.get('conversation_id') !== initialId) {
        url.searchParams.set('conversation_id', initialId)
        window.history.replaceState({}, '', url)
      }
      load(initialId)
    }
  }, [load])

  useEffect(() => {
    let active = true
    const apply = async () => {
      try {
        const session = await getAuthSession()
        if (!active) return
        authSessionRef.current = session || null
        setAuthSession(session || null)
        return session
      } catch {
        if (!active) return null
        authSessionRef.current = null
        setAuthSession(null)
        return null
      }
    }
    apply()
    const unsubscribe = subscribeAuth(apply)
    return () => {
      active = false
      unsubscribe()
    }
  }, [])

  // After login, load the current conversation with the fresh account session.
  useEffect(() => {
    if (!authSession || !conversationId || accountLoadDoneRef.current) return
    const storedGuest = readStoredGuestSession()
    if (storedGuest && storedGuest.conversationId === conversationId) {
      // The claim effect below re-loads after ownership is transferred.
      return
    }
    accountLoadDoneRef.current = true
    load(conversationId)
  }, [authSession, conversationId, load])

  // A guest conversation is linked to the account only with the signed guest proof.
  useEffect(() => {
    if (!authSession || claimAttemptedRef.current) return
    const stored = readStoredGuestSession()
    if (!stored) return
    if (conversationId && stored.conversationId !== conversationId) return
    claimAttemptedRef.current = true
    req('/v1/customer/guest-session/claim', {
      method: 'POST',
      body: { conversation_id: stored.conversationId, guest_session_token: stored.token },
    })
      .then(async () => {
        clearStoredGuestSession()
        setGuestSession(null)
        setNotice('Percakapan tamu Anda berhasil ditautkan ke akun.')
        updateActiveConversation(stored.conversationId)
        await load(stored.conversationId)
        await loadHistory(historySearch)
      })
      .catch(() => {
        // Ownership could not be transferred; keep the guest transcript readable
        // only through its guest proof and surface a normal not-found state.
        load(stored.conversationId)
      })
  }, [authSession, historySearch, load, loadHistory, updateActiveConversation])

  // Session-expiry indicator for an authenticated customer.
  useEffect(() => {
    if (!authSession || !conversationId) {
      setSessionInfo(null)
      return
    }
    req(`/v1/customer/chat/session?conversation_id=${encodeURIComponent(conversationId)}`)
      .then((data) => setSessionInfo(data))
      .catch(() => setSessionInfo(null))
  }, [authSession, conversationId])

  useEffect(() => {
    setConsentChecked(false)
    setVerifyModalOpen(true)
  }, [tier?.consent?.purpose])

  useEffect(() => {
    if (tier?.verification) setVerifyModalOpen(true)
  }, [tier?.verification])

  const closeVerificationModal = useCallback(() => setVerifyModalOpen(false), [])

  useEffect(() => {
    if (!conversationId) return undefined
    const guestToken = guestTokenFor(conversationId)
    if (!authSessionRef.current && !guestToken) return undefined
    const options = guestToken
      ? { auth: 'optional', headers: { 'X-Guest-Session': guestToken } }
      : {}
    const timer = setInterval(() => {
      req(`/v1/conversations/${encodeURIComponent(conversationId)}/read-model?limit=100`, options)
        .then((data) => {
          if (data) {
            if (data.conversation?.status) {
              setConversationStatus(data.conversation.status)
            }
            if (data.messages && data.messages.length > 0) {
              const signature = data.messages.map((message) => message.message_id || `${message.sequence_no}:${message.occurred_at}`).join('|')
              if (signature !== lastMessageSignatureRef.current) {
                lastMessageSignatureRef.current = signature
                setMessages(data.messages)
                loadHistory(historySearch)
              }
            }
          }
        })
        .catch(() => {})
    }, 3500)
    return () => clearInterval(timer)
  }, [conversationId, historySearch, loadHistory])

  const selectConversation = async (id) => {
    if (loading || sending) return
    if (id === conversationId) {
      setHistoryDrawerOpen(false)
      return
    }
    updateActiveConversation(id)
    setMessages([])
    setError(null)
    setNotice(null)
    setRetryInfo(null)
    setTier(null)
    setStepUp(null)
    setPendingText(null)
    await load(id)
    setHistoryDrawerOpen(false)
  }

  const noticeFor = (result) => {
    if (result.verification_required?.method === 'SESSION_LOGIN') {
      return 'Permintaan ini memerlukan login akun (Tier 2). Silakan masuk untuk melanjutkan.'
    }
    if (result.verification_required?.method === 'STEP_UP_OTP') {
      return 'Permintaan sensitif (Tier 3): verifikasi OTP diperlukan sebelum diproses.'
    }
    if (result.consent_required) {
      return 'Persetujuan Anda diperlukan sebelum permintaan sensitif diproses.'
    }
    if (result.human_approval_required) {
      return 'Permintaan berisiko tinggi (Tier 4) telah disiapkan untuk persetujuan petugas.'
    }
    if (result.handoff_status === 'ACCEPTED') return 'Petugas telah menerima permintaan bantuan.'
    if (result.handoff_status === 'QUEUED' || result.handoff_status === 'OFFERED') {
      return 'Permintaan bantuan masuk antrean; petugas belum mengonfirmasi penerimaan.'
    }
    if (result.handoff_status === 'UNAVAILABLE') {
      return 'Pesan tersimpan, tetapi status antrean bantuan belum dapat dipastikan.'
    }
    return 'Pesan diproses oleh layanan.'
  }

  const submitMessage = async (content, idempotencyKey) => {
    const headers = { 'Idempotency-Key': idempotencyKey }
    const guestToken = guestTokenFor(conversationId)
    if (guestToken) headers['X-Guest-Session'] = guestToken
    const canContinue = !!authSessionRef.current || !!guestToken
    const result = await req('/v1/chat/messages', {
      method: 'POST',
      auth: 'optional',
      body: {
        text: content,
        ...(conversationId && canContinue ? { conversation_id: conversationId } : { force_new: true }),
      },
      headers,
    })
    if (!result.conversation_id) {
      throw new ApiError(502, 'MISSING_CONVERSATION', 'Layanan tidak mengembalikan referensi percakapan.')
    }
    if (result.guest_session) setGuestSession(storeGuestSession(result.guest_session))
    updateActiveConversation(result.conversation_id)
    setTier({
      tier: tierOf(result.access_tier),
      verification: result.verification_required || null,
      consent: result.consent_required || null,
      humanApproval: !!result.human_approval_required,
      assurance: result.assurance_level || 'AL0',
    })
    setPendingText(result.verification_required || result.consent_required ? content : null)
    if (result.verification_required?.method === 'STEP_UP_OTP') {
      setStepUp({
        open: true,
        challengeId: null,
        code: '',
        simulatedCode: null,
        error: null,
        busy: false,
        attemptsRemaining: null,
      })
    } else {
      setStepUp(null)
    }
    if (result.handoff_status) {
      setConversationStatus(result.handoff_status === 'ACCEPTED' ? 'ACTIVE_HUMAN' : 'PENDING_HANDOFF')
    }
    return result
  }

  const runSubmission = async (content, retryKey = null) => {
    if (!content || submitLock.current) return
    submitLock.current = true
    setSending(true)
    setError(null)
    setNotice(null)
    isNearBottomRef.current = true
    scrollToBottom(true)
    const idempotencyKey = retryKey || crypto.randomUUID()
    try {
      const result = await submitMessage(content, idempotencyKey)
      setRetryInfo(null)
      setText('')
      setNotice(noticeFor(result))
      await load(result.conversation_id)
      await loadHistory(historySearch)
      scrollToBottom(true)
    } catch (err) {
      setRetryInfo({ text: content, key: idempotencyKey })
      setError(err)
      if (!authSessionRef.current && err?.status === 401) {
        clearStoredGuestSession()
        setGuestSession(null)
        updateActiveConversation(null)
      }
    } finally {
      submitLock.current = false
      setSending(false)
    }
  }

  const send = (event) => {
    event.preventDefault()
    const content = text.trim()
    if (!content) return
    return runSubmission(content, retryInfo?.text === content ? retryInfo.key : null)
  }

  const resumePending = () => {
    const content = (pendingText || '').trim()
    if (!content) return
    setText(content)
    return runSubmission(content)
  }

  const startStepUp = async () => {
    if (!conversationId || !tier?.verification) return
    setStepUp((current) => ({ ...(current || {}), open: true, busy: true, error: null }))
    try {
      const data = await req('/v1/customer/chat/step-up/challenge', {
        method: 'POST',
        body: {
          conversation_id: conversationId,
          purpose: tier.verification.tier_code || 'SENSITIVE_REQUEST',
        },
      })
      setStepUp({
        open: true,
        challengeId: data.challenge_id,
        code: '',
        simulatedCode: data.simulated_code || null,
        error: null,
        busy: false,
        attemptsRemaining: data.max_attempts ?? null,
      })
      setNotice('Kode OTP telah dikirim ke kanal terdaftar Anda.')
    } catch (err) {
      const message = err?.status === 429
        ? 'Terlalu banyak permintaan verifikasi. Coba lagi nanti atau minta bantuan petugas.'
        : err.message
      setStepUp((current) => ({ ...(current || {}), open: true, busy: false, error: message }))
    }
  }

  const verifyStepUp = async (event) => {
    event.preventDefault()
    if (!conversationId || !stepUp?.challengeId || !stepUp.code) return
    setStepUp((current) => ({ ...current, busy: true, error: null }))
    try {
      const data = await req('/v1/customer/chat/step-up/verify', {
        method: 'POST',
        body: {
          conversation_id: conversationId,
          challenge_id: stepUp.challengeId,
          code: stepUp.code,
        },
      })
      if (data.verified) {
        setStepUp(null)
        setTier((current) => (current
          ? { ...current, verification: null, assurance: data.assurance_level || 'AL2' }
          : current))
        setSessionInfo((current) => ({
          ...(current || {}),
          assurance_level: data.assurance_level,
          al_expires_at: data.expires_at || current?.al_expires_at,
        }))
        setNotice('Verifikasi OTP berhasil. Lanjutkan permintaan Anda.')
      } else {
        setStepUp((current) => ({
          ...current,
          busy: false,
          code: '',
          attemptsRemaining: data.attempts_remaining,
        }))
        setNotice(`Kode OTP belum cocok. Sisa percobaan: ${data.attempts_remaining}.`)
      }
    } catch (err) {
      const message = err?.status === 429
        ? 'Verifikasi terkunci sementara karena percobaan gagal berulang. Permintaan akan dialihkan ke petugas.'
        : err?.status === 404
        ? 'Kode verifikasi tidak berlaku lagi. Silakan kirim ulang kode OTP.'
        : err.message
      setStepUp((current) => ({ ...current, busy: false, error: message }))
    }
  }

  const decideConsent = async (granted) => {
    if (!conversationId || !tier?.consent) return
    setConsentBusy(true)
    try {
      await req('/v1/customer/chat/consent', {
        method: 'POST',
        body: {
          conversation_id: conversationId,
          purpose: tier.consent.purpose,
          granted,
          text_version: tier.consent.text_version || 'v1',
        },
      })
      setTier((current) => (current ? { ...current, consent: null } : current))
      if (granted) {
        setNotice('Persetujuan tercatat. Lanjutkan permintaan Anda.')
      } else {
        setPendingText(null)
        setNotice('Permintaan tidak dilanjutkan karena persetujuan tidak diberikan.')
      }
    } catch (err) {
      setError(err)
    } finally {
      setConsentBusy(false)
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

  const effectiveTier = tier?.tier || (authSession ? 2 : 1)
  const tierMeta = TIER_META[effectiveTier]
  const verification = tier?.verification || null
  const consent = tier?.consent || null
  const stepUpRequired = verification?.method === 'STEP_UP_OTP' || !!stepUp
  const humanApproval = !!tier?.humanApproval
  const guestExpiry = guestSession?.conversationId === conversationId ? guestSession.expiresAt : null
  const assuranceChip = authSession
    ? sessionInfo?.assurance_level && sessionInfo.assurance_level !== 'AL0'
      ? `${sessionInfo.assurance_level}${sessionInfo.al_expires_at ? ` s.d. ${formatClock(sessionInfo.al_expires_at)}` : ''}`
      : 'Sesi akun aktif'
    : guestExpiry
    ? `Tamu s.d. ${formatClock(guestExpiry)}`
    : null

  return (
    <div className="chat-layout-container">
      {isNarrow && historyDrawerOpen && (
        <div
          className="chat-history-scrim"
          aria-hidden="true"
          onClick={() => setHistoryDrawerOpen(false)}
        />
      )}

      <CustomerChatHistoryPanel
        items={filteredHistoryItems}
        groups={historyGroups}
        activeId={conversationId}
        search={historySearch}
        onSearch={setHistorySearch}
        cursor={historyCursor}
        loading={historyLoading}
        error={historyError}
        onRetry={() => loadHistory(historySearch)}
        onLoadMore={() => historyCursor && loadHistory(historySearch, historyCursor, true)}
        onSelect={selectConversation}
        onStartNew={startNewChat}
        newChatRef={historyNewChatRef}
        narrow={isNarrow}
        open={historyDrawerOpen}
        onClose={() => setHistoryDrawerOpen(false)}
        busy={loading || sending}
        authenticated={!!authSession}
      />

      <div className="chat-container-card chat-main-panel">
        <div className="chat-card-header">
          <div className="chat-agent-profile">
            <div className="chat-agent-avatar" aria-hidden="true">
              ✦
              <span className="chat-online-dot" title="Online" />
            </div>
            <div className="chat-agent-info">
              <h3>NEXORA AI Assistant</h3>
              <p>
                <span style={{ color: 'var(--success)', fontWeight: 600 }}>● Aktif</span>
                <span>·</span>
                <span>Layanan Pelanggan Agentik 24/7</span>
                {conversationStatus === 'PENDING_HANDOFF' && (
                  <>
                    <span>·</span>
                    <span className="chat-tracking-badge queued" style={{ fontSize: '10px', padding: '1px 6px' }}>
                      <span className="chat-tracking-dot" aria-hidden="true" />
                      Menunggu Petugas
                    </span>
                  </>
                )}
                {conversationStatus === 'ACTIVE_HUMAN' && (
                  <>
                    <span>·</span>
                    <span className="chat-tracking-badge active" style={{ fontSize: '10px', padding: '1px 6px' }}>
                      <span className="chat-tracking-dot" aria-hidden="true" />
                      Dialihkan ke Petugas
                    </span>
                  </>
                )}
              </p>
            </div>
          </div>
          <div className="chat-header-actions">
            {assuranceChip && (
              <span className="source-chip" title="Status sesi dan masa berlaku verifikasi">
                {assuranceChip}
              </span>
            )}
            {conversationId && (
              <span className="source-chip" title="ID Sesi Percakapan" style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                ID: {conversationId.slice(0, 8)}...
              </span>
            )}
            <button type="button" className="btn sm" onClick={startNewChat} title="Mulai sesi percakapan baru">
              + Mulai Baru
            </button>
            {isNarrow && (
              <button
                ref={historyToggleRef}
                type="button"
                className="btn sm chat-history-toggle-btn"
                onClick={() => setHistoryDrawerOpen(true)}
                aria-label="Buka riwayat chat"
                aria-expanded={historyDrawerOpen}
              >
                Riwayat
              </button>
            )}
          </div>
        </div>

        <div className={`chat-access-bar tier-${effectiveTier}`} role="status">
          <span className={`chat-tier-badge tier-${effectiveTier}`}>
            Tier {effectiveTier} · {tierMeta.label}
          </span>
          <span className="chat-access-hint">{tierMeta.hint}</span>
          {!authSession && (
            <button
              type="button"
              className="btn sm"
              onClick={() => navigate('/customer/login')}
              title="Masuk untuk membuka data pribadi dan tindakan sensitif"
            >
              Masuk ke Akun ↗
            </button>
          )}
        </div>

        {verification?.method === 'SESSION_LOGIN' && (
          <div className="chat-guardrail chat-guardrail-login" role="alert">
            <strong>Perlu masuk akun (Tier 2)</strong>
            <p>
              Status order, saldo, dan transaksi hanya dapat dibuka setelah Anda masuk. Mode tamu
              hanya menjawab informasi publik.
            </p>
            <button
              type="button"
              className="btn sm primary"
              onClick={() => navigate('/customer/login')}
            >
              Masuk ke Akun ↗
            </button>
          </div>
        )}

        {(stepUpRequired || consent) && (
          verifyModalOpen ? (
            <VerificationModal
              title={stepUpRequired ? 'Verifikasi tambahan (Tier 3)' : (consent?.title || 'Persetujuan diperlukan')}
              subtitle={stepUpRequired
                ? 'Tindakan sensitif memerlukan OTP ke kanal terdaftar Anda. Pertanyaan keamanan saja tidak cukup untuk tindakan ini.'
                : 'Tinjau ringkasan berikut sebelum permintaan diproses.'}
              onClose={closeVerificationModal}
            >
              {stepUpRequired && (
                <section className="chat-stepup-card" aria-labelledby="chat-stepup-title">
                  <h4 id="chat-stepup-title">
                    {consent ? 'Langkah 1 · Verifikasi OTP' : 'Kode OTP'}
                  </h4>
                  {!stepUp?.challengeId ? (
                    <button
                      type="button"
                      className="btn primary"
                      onClick={startStepUp}
                      disabled={!!stepUp?.busy}
                    >
                      {stepUp?.busy ? 'Mengirim kode...' : 'Kirim Kode OTP'}
                    </button>
                  ) : (
                    <form onSubmit={verifyStepUp} className="chat-stepup-form">
                      {stepUp.simulatedCode && (
                        <p className="chat-otp-simulator">
                          Simulator OTP (mode pengembangan): <code>{stepUp.simulatedCode}</code>
                        </p>
                      )}
                      <label htmlFor="chat-otp-code">Kode OTP</label>
                      <input
                        id="chat-otp-code"
                        className="chat-otp-input"
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        maxLength={6}
                        value={stepUp.code}
                        onChange={(event) => setStepUp((current) => ({
                          ...current,
                          code: event.target.value.replace(/\D/g, ''),
                        }))}
                        disabled={!!stepUp.busy}
                      />
                      {stepUp.attemptsRemaining != null && (
                        <p className="chat-muted">Sisa percobaan: {stepUp.attemptsRemaining}</p>
                      )}
                      <div className="chat-stepup-actions">
                        <button
                          type="submit"
                          className="btn primary"
                          disabled={!!stepUp.busy || stepUp.code.length < 4}
                        >
                          {stepUp.busy ? 'Memverifikasi...' : 'Verifikasi'}
                        </button>
                        <button
                          type="button"
                          className="btn"
                          onClick={startStepUp}
                          disabled={!!stepUp.busy}
                        >
                          Kirim Ulang
                        </button>
                      </div>
                    </form>
                  )}
                  {stepUp?.error && (
                    <p className="chat-stepup-error" role="alert">{stepUp.error}</p>
                  )}
                  <p className="chat-stepup-foot">Kode OTP tidak pernah disimpan di transkrip percakapan.</p>
                </section>
              )}

              {consent && (
                <section className="chat-consent-card" aria-labelledby="chat-consent-title">
                  <h4 id="chat-consent-title">
                    {stepUpRequired ? 'Langkah 2 · Persetujuan' : 'Rincian persetujuan'}
                  </h4>
                  <p>
                    {consent.summary
                      || 'Data yang diproses terbatas pada kebutuhan permintaan ini.'}
                  </p>
                  <label className="chat-consent-check">
                    <input
                      type="checkbox"
                      checked={consentChecked}
                      onChange={(event) => setConsentChecked(event.target.checked)}
                    />
                    <span>Saya memahami dan menyetujui pemrosesan untuk permintaan ini.</span>
                  </label>
                  <div className="chat-consent-actions">
                    <button
                      type="button"
                      className="btn primary"
                      disabled={!consentChecked || consentBusy}
                      onClick={() => decideConsent(true)}
                    >
                      Berikan Persetujuan
                    </button>
                    <button
                      type="button"
                      className="btn"
                      disabled={consentBusy}
                      onClick={() => decideConsent(false)}
                    >
                      Tolak
                    </button>
                  </div>
                </section>
              )}
            </VerificationModal>
          ) : (
            <div className="chat-verification-bar" role="status">
              <div className="chat-verification-bar-text">
                <strong>{stepUpRequired ? 'Verifikasi OTP diperlukan' : 'Persetujuan diperlukan'}</strong>
                <span>
                  {stepUpRequired
                    ? 'Selesaikan verifikasi untuk melanjutkan permintaan sensitif.'
                    : 'Tinjau dan berikan persetujuan untuk melanjutkan.'}
                </span>
              </div>
              <button
                type="button"
                className="btn sm primary"
                onClick={() => setVerifyModalOpen(true)}
              >
                Buka Verifikasi
              </button>
            </div>
          )
        )}

        {pendingText && !verification && !consent && (
          <div className="chat-guardrail chat-guardrail-resume">
            <span>Verifikasi selesai. Permintaan Anda siap dilanjutkan.</span>
            <button
              type="button"
              className="btn sm primary"
              onClick={resumePending}
              disabled={sending}
            >
              Lanjutkan Permintaan
            </button>
          </div>
        )}

        {humanApproval && (
          <div className="chat-guardrail chat-guardrail-approval" role="status">
            <strong>Tindakan berisiko tinggi (Tier 4)</strong>
            <p>
              AI hanya menyiapkan permintaan. Tidak ada eksekusi otomatis; petugas wajib meninjau
              dan menyetujui sebelum tindakan dijalankan.
            </p>
          </div>
        )}

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
              {error.status === 401 && authSession ? (
                <> <a href="/customer/login" onClick={(e) => { e.preventDefault(); navigate('/customer/login') }}>Masuk kembali</a> untuk melanjutkan.</>
              ) : error.status === 401 ? (
                ' Sesi tamu Anda berakhir. Kirim ulang pesan untuk memulai sesi publik baru.'
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
              const isHandoffNotice = !isCustomer && (
                m.content?.toLowerCase().includes('masuk antrean') ||
                m.content?.toLowerCase().includes('bantuan petugas') ||
                m.content?.toLowerCase().includes('belum mengonfirmasi')
              )
              return (
                <article
                  className={`chat-bubble ${isCustomer ? 'from-customer' : 'from-service'}`}
                  key={m.message_id || m.sequence_no}
                >
                  <div className="chat-bubble-byline">
                    <strong>{isCustomer ? 'Anda' : m.author_type === 'AI_AGENT' ? 'NEXORA AI Assistant' : 'Petugas Customer Support'}</strong>
                    <small>{m.occurred_at ? new Date(m.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</small>
                  </div>
                  <FormattedMessage text={m.content} />
                  {isHandoffNotice && (
                    <ChatHandoffTrackCard
                      conversationId={conversationId}
                      status={conversationStatus || 'PENDING_HANDOFF'}
                      occurredAt={m.occurred_at}
                    />
                  )}
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
            <p className="eyebrow" style={{ color: 'var(--electric-blue)' }}>ASISTEN RESMI NEXORA</p>
            <h2 style={{ fontSize: '20px', fontWeight: 600, margin: '8px 0 12px', color: 'var(--ink)' }}>
              Ada yang bisa kami bantu hari ini?
            </h2>
            <p style={{ maxWidth: '480px', margin: '0 auto 20px', fontSize: '13px', color: 'var(--muted)', lineHeight: 1.6 }}>
              Tanyakan seputar produk cloud, infrastruktur, jam operasional, atau kendala teknis.
              Anda dapat mulai tanpa login untuk informasi publik; data akun memerlukan verifikasi bertingkat.
            </p>
            <div className="chat-quick-prompts" aria-label="Saran pertanyaan cepat">
              {[
                'Layanan cloud apa saja yang tersedia di NEXORA?',
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
            disabled={sending || !text.trim() || (!!authSession && (error?.status === 401 || error?.status === 403))}
            title="Kirim pesan"
            aria-label="Kirim pesan"
          >
            {sending ? '⏳' : '➤'}
          </button>
        </div>
        <div className="chat-composer-footer">
          <span>
            {authSession
              ? '🔒 Jangan bagikan kata sandi, OTP, atau informasi kredensial rahasia.'
              : '🔒 Mode tamu: hanya informasi publik. Masuk untuk data akun dan tindakan sensitif.'}
          </span>
          <span>{text.length}/4000</span>
        </div>
      </form>
    </div>
  </div>
  )
}
