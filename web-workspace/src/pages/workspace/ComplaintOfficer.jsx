import React, { useCallback, useEffect, useState } from 'react'
import { req, SEVERITIES } from '../../api.js'
import { Card, Err, Empty, Json, Sev, StateBadge } from '../../shared/ui.jsx'
import { useForm } from '../../shared/useForm.js'

export function ComplaintOfficer({ role }) {
  const [e, setE] = useState(null)
  const [success, setSuccess] = useState(null)
  const [casesList, setCasesList] = useState([])
  const [escalations, setEscalations] = useState([])
  const [selectedCase, setSelectedCase] = useState(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('cases') // 'cases' | 'escalations' | 'adjudicate'

  const [adj, setAdj, resetAdj] = useForm({
    decision: 'UPHELD',
    compensation_amount: '0',
    notes: 'Bukti sanggahan valid dan telah diverifikasi oleh tim investigasi.',
    customer_explanation: 'Klaim pengaduan Anda telah kami setujui setelah verifikasi bukti transaksi.',
  })

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [cList, escList] = await Promise.all([
        req('/v1/cases', { role }).catch(() => []),
        req('/v1/workspace/escalations?role_target=COMPLAINT_OFFICER', { role }).catch(() => ({ items: [] })),
      ])
      setCasesList(Array.isArray(cList) ? cList : [])
      setEscalations(Array.isArray(escList?.items) ? escList.items : [])
    } catch (err) {
      setE(err)
    } finally {
      setLoading(false)
    }
  }, [role])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleSelectCase = (c) => {
    setSelectedCase(c)
    setActiveTab('adjudicate')
    setSuccess(null)
    setE(null)
  }

  const handleAdjudicate = async () => {
    if (!selectedCase) return
    setE(null)
    setSuccess(null)
    try {
      const cid = selectedCase.case_id
      const body = {
        decision: adj.decision,
        compensation_amount: parseFloat(adj.compensation_amount) || 0,
        notes: adj.notes,
        customer_explanation: adj.customer_explanation,
      }
      const res = await req(`/v1/cases/${encodeURIComponent(cid)}/adjudicate`, {
        method: 'POST',
        role,
        body,
      })
      setSuccess(`Kasus ${selectedCase.customer_reference || cid} berhasil diadjudikasi dengan keputusan ${adj.decision}!`)
      await loadData()
      setSelectedCase(null)
      setActiveTab('cases')
    } catch (err) {
      setE(err)
    }
  }

  const handleAcknowledgeEscalation = async (eid) => {
    setE(null)
    try {
      await req(`/v1/workspace/escalations/${encodeURIComponent(eid)}/acknowledge`, {
        method: 'POST',
        role,
      })
      await loadData()
    } catch (err) {
      setE(err)
    }
  }

  return (
    <div className="complaint-officer-workspace" style={{ padding: '8px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h2 style={{ margin: '0 0 4px', fontSize: '1.25rem', fontWeight: 600 }}>Ruang Kerja Complaint Officer</h2>
          <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Investigasi klaim sengketa nasabah, evaluasi berkas bukti transaksi, dan eksekusi resolusi pengaduan resmi.
          </p>
        </div>
        <button className="btn sm" onClick={loadData} disabled={loading}>
          {loading ? 'Memuat...' : '↻ Segarkan Data'}
        </button>
      </div>

      <Err e={e} onClose={() => setE(null)} />
      {success && (
        <div style={{ background: '#ecfdf3', border: '1px solid #a6f4c5', borderRadius: 8, padding: '12px 16px', color: '#027a48', marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span><strong>Berhasil:</strong> {success}</span>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#027a48', fontWeight: 'bold' }} onClick={() => setSuccess(null)}>×</button>
        </div>
      )}

      {/* Tabs */}
      <div className="tab-buttons" style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button
          className={`btn ${activeTab === 'cases' ? 'primary' : ''}`}
          onClick={() => setActiveTab('cases')}
        >
          Daftar Kasus Pengaduan ({casesList.length})
        </button>
        <button
          className={`btn ${activeTab === 'escalations' ? 'primary' : ''}`}
          onClick={() => setActiveTab('escalations')}
        >
          Antrean Eskalasi Tingkat 2 ({escalations.filter(e => !e.acknowledged_by).length})
        </button>
        {selectedCase && (
          <button
            className={`btn ${activeTab === 'adjudicate' ? 'primary' : ''}`}
            onClick={() => setActiveTab('adjudicate')}
          >
            Adjudikasi Sengketa: {selectedCase.customer_reference || selectedCase.case_id}
          </button>
        )}
      </div>

      {/* Tab 1: Cases Table */}
      {activeTab === 'cases' && (
        <Card title="Daftar Pengaduan & Sengketa Nasabah" sub="Menampilkan seluruh tiket pengaduan resmi yang diajukan nasabah melalui portal.">
          {casesList.length === 0 ? (
            <Empty msg="Belum ada pengaduan atau sengketa aktif saat ini." />
          ) : (
            <div className="table-responsive" style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={{ padding: '10px 8px' }}>Referensi Tiket</th>
                    <th style={{ padding: '10px 8px' }}>Nasabah</th>
                    <th style={{ padding: '10px 8px' }}>Kategori</th>
                    <th style={{ padding: '10px 8px' }}>Severity</th>
                    <th style={{ padding: '10px 8px' }}>Status Internal</th>
                    <th style={{ padding: '10px 8px' }}>Status Nasabah</th>
                    <th style={{ padding: '10px 8px' }}>Waktu Masuk</th>
                    <th style={{ padding: '10px 8px' }}>Aksi Tindakan</th>
                  </tr>
                </thead>
                <tbody>
                  {casesList.map((c) => (
                    <tr key={c.case_id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '10px 8px', fontFamily: 'monospace', fontWeight: 600 }}>
                        {c.customer_reference || c.case_id}
                      </td>
                      <td style={{ padding: '10px 8px' }}>{c.customer_id || 'Anonim'}</td>
                      <td style={{ padding: '10px 8px' }}>
                        <span style={{ background: '#f2f4f7', padding: '2px 6px', borderRadius: 4, fontSize: '0.75rem' }}>
                          {c.category}
                        </span>
                      </td>
                      <td style={{ padding: '10px 8px' }}>
                        <Sev s={c.severity_proposed || 'MEDIUM'} />
                      </td>
                      <td style={{ padding: '10px 8px' }}>
                        <StateBadge s={c.status} />
                      </td>
                      <td style={{ padding: '10px 8px' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>{c.customer_visible_status || '-'}</span>
                      </td>
                      <td style={{ padding: '10px 8px', color: 'var(--text-secondary)' }}>
                        {c.logged_at ? new Date(c.logged_at).toLocaleDateString('id-ID', { hour: '2-digit', minute: '2-digit' }) : '-'}
                      </td>
                      <td style={{ padding: '10px 8px' }}>
                        <button
                          className="btn sm primary"
                          onClick={() => handleSelectCase(c)}
                        >
                          Tinjau & Adjudikasi
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* Tab 2: Escalations Table */}
      {activeTab === 'escalations' && (
        <Card title="Antrean Eskalasi Tingkat 2 (Complaint Officer)" sub="Eskalasi otomatis yang dipicu oleh pengulangan keluhan (repeat contact) atau risiko keterlambatan investigasi.">
          {escalations.length === 0 ? (
            <Empty msg="Tidak ada eskalasi tingkat 2 yang menunggu respon." />
          ) : (
            <div className="table-responsive">
              <table className="data-table" style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={{ padding: '10px 8px' }}>ID Eskalasi</th>
                    <th style={{ padding: '10px 8px' }}>Tipe Objek</th>
                    <th style={{ padding: '10px 8px' }}>ID Objek</th>
                    <th style={{ padding: '10px 8px' }}>Pemicu (Trigger)</th>
                    <th style={{ padding: '10px 8px' }}>Status Acknowledge</th>
                    <th style={{ padding: '10px 8px' }}>Waktu Eskalasi</th>
                    <th style={{ padding: '10px 8px' }}>Tindakan</th>
                  </tr>
                </thead>
                <tbody>
                  {escalations.map((esc) => (
                    <tr key={esc.escalation_id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '10px 8px', fontFamily: 'monospace' }}>{esc.escalation_id}</td>
                      <td style={{ padding: '10px 8px' }}>{esc.object_type}</td>
                      <td style={{ padding: '10px 8px', fontWeight: 600 }}>{esc.object_id}</td>
                      <td style={{ padding: '10px 8px', color: '#b42318' }}><strong>{esc.trigger_type}</strong></td>
                      <td style={{ padding: '10px 8px' }}>
                        {esc.acknowledged_by ? (
                          <span style={{ color: '#16794b' }}>Diterima oleh {esc.acknowledged_by}</span>
                        ) : (
                          <span style={{ color: '#b42318', fontWeight: 600 }}>Menunggu Konfirmasi</span>
                        )}
                      </td>
                      <td style={{ padding: '10px 8px', color: 'var(--text-secondary)' }}>
                        {esc.created_at ? new Date(esc.created_at).toLocaleString('id-ID') : '-'}
                      </td>
                      <td style={{ padding: '10px 8px' }}>
                        {!esc.acknowledged_by && (
                          <button
                            className="btn sm"
                            onClick={() => handleAcknowledgeEscalation(esc.escalation_id)}
                          >
                            ✓ Konfirmasi Penerimaan
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* Tab 3: Adjudication Form */}
      {activeTab === 'adjudicate' && selectedCase && (
        <div className="grid g2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Card title={`Detail Kasus: ${selectedCase.customer_reference || selectedCase.case_id}`}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: '0.875rem' }}>
              <div><strong>Kategori:</strong> {selectedCase.category}</div>
              <div><strong>ID Nasabah:</strong> {selectedCase.customer_id || 'Anonim'}</div>
              <div><strong>Status Saat Ini:</strong> <StateBadge s={selectedCase.status} /></div>
              <div><strong>Severity:</strong> <Sev s={selectedCase.severity_proposed || 'MEDIUM'} /></div>
              <div>
                <strong>Ringkasan Masalah / Laporan:</strong>
                <p style={{ margin: '6px 0 0', padding: 10, background: '#f9fafb', borderRadius: 6, border: '1px solid #eaecf0', color: 'var(--text-primary)' }}>
                  {selectedCase.description || 'Tidak ada deskripsi rinci yang tercantum.'}
                </p>
              </div>
            </div>
          </Card>

          <Card title="Formulir Adjudikasi & Keputusan Kasus" sub="Menentukan putusan akhir atas klaim atau sengketa nasabah.">
            <div className="form" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <label>
                <strong>Keputusan Adjudikasi:</strong>
                <select value={adj.decision} onChange={setAdj('decision')} style={{ width: '100%', marginTop: 4, padding: 8, borderRadius: 6, border: '1px solid var(--border)' }}>
                  <option value="UPHELD">UPHELD — Sengketa Diterima (Disetujui Penuh)</option>
                  <option value="REJECTED">REJECTED — Sengketa Ditolak (Tidak Valid)</option>
                  <option value="SETTLED">SETTLED — Penyelesaian Damai (Goodwill Settlement)</option>
                </select>
              </label>

              <label>
                <strong>Jumlah Kompensasi / Pengembalian (Rp):</strong>
                <input
                  type="number"
                  value={adj.compensation_amount}
                  onChange={setAdj('compensation_amount')}
                  style={{ width: '100%', marginTop: 4, padding: 8, borderRadius: 6, border: '1px solid var(--border)' }}
                />
              </label>

              <label>
                <strong>Catatan Audit Internal Petugas:</strong>
                <textarea
                  rows={3}
                  value={adj.notes}
                  onChange={setAdj('notes')}
                  style={{ width: '100%', marginTop: 4, padding: 8, borderRadius: 6, border: '1px solid var(--border)', resize: 'vertical' }}
                />
              </label>

              <label>
                <strong>Penjelasan Resmi ke Nasabah:</strong>
                <textarea
                  rows={3}
                  value={adj.customer_explanation}
                  onChange={setAdj('customer_explanation')}
                  style={{ width: '100%', marginTop: 4, padding: 8, borderRadius: 6, border: '1px solid var(--border)', resize: 'vertical' }}
                />
              </label>

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button className="btn primary" onClick={handleAdjudicate} style={{ flex: 1 }}>
                  ⚖ Eksekusi Keputusan Adjudikasi
                </button>
                <button className="btn" onClick={() => setActiveTab('cases')}>
                  Batal
                </button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
export default ComplaintOfficer
