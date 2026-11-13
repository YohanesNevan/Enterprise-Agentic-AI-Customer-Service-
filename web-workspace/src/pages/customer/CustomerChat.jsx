import React, { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, req } from '../../api.js'
import { navigate } from '../../shared/navigation.js'

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
  const submitLock = useRef(false)
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
    setText('')
    setRetryInfo(null)
    setNotice('Sesi percakapan baru siap — kirim pesan untuk memulai obrolan baru.')
    setError(null)
    isNearBottomRef.current = true
    setShowScrollBottom(false)
    setHistoryDrawerOpen(false)
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
      lastMessageSignatureRef.current = all.map((message) => message.message_id || `${message.sequence_no}:${message.occurred_at}`).join('|')
      setTimeout(() => scrollToBottom(true), 80)
    } catch (err) {
      setError(err)
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
    if (!conversationId) return
    const timer = setInterval(() => {
      req(`/v1/conversations/${encodeURIComponent(conversationId)}/read-model?limit=100`)
        .then((data) => {
          if (data && data.messages && data.messages.length > 0) {
            const signature = data.messages.map((message) => message.message_id || `${message.sequence_no}:${message.occurred_at}`).join('|')
            if (signature !== lastMessageSignatureRef.current) {
              lastMessageSignatureRef.current = signature
              setMessages(data.messages)
              loadHistory(historySearch)
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
    await load(id)
    setHistoryDrawerOpen(false)
  }

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
        body: { text: content, ...(conversationId ? { conversation_id: conversationId } : { force_new: true }) },
        headers: { 'Idempotency-Key': idempotencyKey }
      })
      if (!result.conversation_id) throw new ApiError(502, 'MISSING_CONVERSATION', 'Layanan tidak mengembalikan referensi percakapan.')
      updateActiveConversation(result.conversation_id)
      setRetryInfo(null)
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
      await loadHistory(historySearch)
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
                    <strong>{isCustomer ? 'Anda' : m.author_type === 'AI_AGENT' ? 'NEXORA AI Assistant' : 'Petugas Customer Support'}</strong>
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
            <p className="eyebrow" style={{ color: 'var(--electric-blue)' }}>ASISTEN RESMI NEXORA</p>
            <h2 style={{ fontSize: '20px', fontWeight: 600, margin: '8px 0 12px', color: 'var(--ink)' }}>
              Ada yang bisa kami bantu hari ini?
            </h2>
            <p style={{ maxWidth: '480px', margin: '0 auto 20px', fontSize: '13px', color: 'var(--muted)', lineHeight: 1.6 }}>
              Tanyakan seputar produk cloud, infrastruktur, jam operasional, atau kendala teknis. Asisten agentik kami siap membantu Anda dengan cepat dan akurat.
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
  </div>
  )
}
