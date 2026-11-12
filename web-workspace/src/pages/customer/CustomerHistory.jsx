import React, { useCallback, useEffect, useState } from 'react'
import { req } from '../../api.js'
import { customerConversationState, navigate } from '../../shared/navigation.js'
import { Empty } from '../../shared/ui.jsx'

export function CustomerHistory() {
  const [items, setItems] = useState([])
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [nextCursor, setNextCursor] = useState(null)

  const load = useCallback(async (cursor = null, append = false) => {
    setLoading(true)
    setError(null)
    try {
      const query = cursor ? `?limit=20&cursor=${encodeURIComponent(cursor)}` : '?limit=20'
      const data = await req(`/v1/customer/conversations${query}`)
      setItems((current) => append ? [...current, ...(data.items || [])] : data.items || [])
      setNextCursor(data.next_cursor || null)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const detail = async (id) => {
    setError(null)
    try {
      let cursor = null
      let data
      const messages = []
      do {
        const suffix = cursor ? `?limit=100&cursor=${encodeURIComponent(cursor)}` : '?limit=100'
        data = await req(`/v1/conversations/${encodeURIComponent(id)}/read-model${suffix}`)
        messages.push(...(data.messages || []))
        cursor = data.next_cursor
      } while (cursor)
      setSelected({ ...data, messages })
    } catch (err) {
      setError(err)
    }
  }

  return (
    <section className="customer-history">
      <div className="customer-list-heading">
        <div>
          <p className="sub">Percakapan tersimpan sebagai riwayat layanan pada akun Anda.</p>
          <p className="customer-retention-note">Riwayat tidak dapat dihapus dari portal ini.</p>
        </div>
        <div className="row">
          <button className="btn sm" onClick={() => load()}>Muat ulang</button>
          <a className="btn sm primary" href="/customer/requests/new" onClick={(e) => { e.preventDefault(); navigate('/customer/requests/new') }}>
            Kirim permintaan
          </a>
        </div>
      </div>
      {error && <p className="alert err" role="alert">{error.message}</p>}
      {loading && !items.length ? (
        <Empty text="Memuat riwayat..." />
      ) : !items.length ? (
        <Empty text="Belum ada percakapan." />
      ) : (
        <ul className="conversation-list">
          {items.map((item) => (
            <li key={item.conversation_id}>
              <button className="conversation-list-item" onClick={() => detail(item.conversation_id)}>
                <strong>{item.conversation_id}</strong>
                <span>{customerConversationState(item.status)} / {new Date(item.last_activity_at).toLocaleString()}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {nextCursor && (
        <button className="btn" disabled={loading} onClick={() => load(nextCursor, true)}>
          {loading ? 'Memuat...' : 'Muat percakapan sebelumnya'}
        </button>
      )}
      {selected && (
        <div className="customer-transcript">
          <h2>{selected.conversation.conversation_id}</h2>
          {selected.messages.map((m) => (
            <article className={`customer-message ${m.direction === 'INBOUND' ? 'from-customer' : 'from-service'}`} key={m.message_id || m.sequence_no}>
              <p>{m.content}</p>
              <small>{m.direction === 'INBOUND' ? 'Anda' : 'Layanan'}</small>
              {(m.citations || []).map((citation, i) => (
                <small key={i}>
                  Sumber: {citation.title || citation.source || 'Referensi layanan'}{citation.passage_ref ? ` / ${citation.passage_ref}` : ''}
                </small>
              ))}
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

export default CustomerHistory
