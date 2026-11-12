import React, { useState } from 'react'
import {
  devUniversalLogin,
  isDevelopmentAuthEnabled,
  isDevelopmentStaffAuthEnabled,
} from '../../api.js'
import { navigate } from '../../shared/navigation.js'

export function UniversalLogin() {
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

  return (
    <section className="customer-auth">
      <p className="eyebrow"><span className="eyebrow-rule" />PORTAL LAYANAN</p>
      <h2>Masuk ke Akun Anda</h2>
      <p className="auth-intro">Silakan masuk menggunakan nama pengguna dan kata sandi yang telah terdaftar.</p>
      {!isDevelopmentAuthEnabled && !isDevelopmentStaffAuthEnabled ? (
        <p className="alert info">Autentikasi belum diaktifkan di server pengembangan.</p>
      ) : (
        <form className="form" onSubmit={submit}>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn secondary"
              style={{ fontSize: '0.82rem', padding: '0.35rem 0.75rem', cursor: 'pointer' }}
              onClick={() => {
                setUsername('customer_dev')
                setPassword('M8GvyVkrEF5wJZUCg47ylIJHeulmVA6sK0sc')
              }}
            >
              Autofill Nasabah (customer_dev)
            </button>
            <button
              type="button"
              className="btn secondary"
              style={{ fontSize: '0.82rem', padding: '0.35rem 0.75rem', cursor: 'pointer' }}
              onClick={() => {
                setUsername('kb.staff')
                setPassword('L5Tz88EhNmxZsRshdqsI0DrMKipGf9dw')
              }}
            >
              Autofill Staf CS (kb.staff)
            </button>
          </div>
          <label>
            Nama pengguna
            <input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </label>
          <label>
            Kata sandi
            <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {error && <p className="alert err" role="alert">{error.message || 'Nama pengguna atau kata sandi tidak valid.'}</p>}
          <button className="btn primary" disabled={loading}>{loading ? 'Memeriksa…' : 'Masuk'}</button>
        </form>
      )}
    </section>
  )
}

export const CustomerLogin = UniversalLogin
export const StaffLogin = UniversalLogin
export default UniversalLogin
