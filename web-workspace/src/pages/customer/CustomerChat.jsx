import React, { useCallback, useEffect, useRef, useState } from 'react'
import { req, ApiError } from '../../api.js'
import { navigate } from '../../shared/navigation.js'

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

export function CustomerChat() {
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
    setNotice('Sesi percakapan baru siap — kirim pesan untuk memulai obrolan baru.')
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
                return prev
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
        body: { text: content, ...(conversationId ? { conversation_id: conversationId } : { force_new: true }) },
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

export default CustomerChat
