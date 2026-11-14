import React, { useCallback, useEffect, useRef, useState } from 'react'
import { req, ApiError } from '../../api.js'
import { Card, Err, Empty } from '../../shared/ui.jsx'

export function KnowledgeManager({ role }) {
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
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [role])

  useEffect(() => {
    load()
    const refreshOnFocus = () => {
      if (document.visibilityState === 'visible') load()
    }
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
    setError(null)
    setNotice(null)
    if (!uploadFile) {
      setError(new ApiError(400, 'NO_FILE', 'Pilih berkas terlebih dahulu.'))
      return
    }

    setUploading(true)
    const formData = new FormData()
    formData.append('file', uploadFile)
    try {
      const result = await req('/v1/knowledge/documents/upload', { method: 'POST', role, body: formData })
      setNotice(
        result.status === 'ready'
          ? `Dokumen "${uploadName}" berhasil diproses & diindeks! Status: Siap (${result.chunk_count || 0} potongan teks aktif untuk AI Agent).`
          : (result.message || `Dokumen berstatus ${statusLabel(result.status)}.`)
      )
      clearFile()
      setShowCreate(false)
      await load()
    } catch (err) {
      setError(err)
    } finally {
      setUploading(false)
    }
  }

  const handleDirectSubmit = async (event) => {
    event.preventDefault()
    setError(null)
    setNotice(null)
    const title = directTitle.trim()
    const content = directContent.trim()
    if (!title) {
      setError(new ApiError(400, 'EMPTY_TITLE', 'Judul dokumen wajib diisi.'))
      return
    }
    if (!content) {
      setError(new ApiError(400, 'EMPTY_CONTENT', 'Isi teks pengetahuan wajib diisi.'))
      return
    }

    setDirectSubmitting(true)
    try {
      const safeFilename = `${title.replace(/[^a-zA-Z0-9_\-\u00C0-\u017F ]/g, '').trim() || 'knowledge_article'}.txt`
      const file = new File([content], safeFilename, { type: 'text/plain;charset=utf-8' })
      const formData = new FormData()
      formData.append('file', file)
      formData.append('title', title)

      const result = await req('/v1/knowledge/documents/upload', { method: 'POST', role, body: formData })
      setNotice(
        result.status === 'ready'
          ? `Knowledge "${title}" berhasil disimpan & diindeks! (${result.chunk_count || 0} potongan teks siap digunakan AI).`
          : (result.message || 'Dokumen pengetahuan berhasil disimpan.')
      )
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
    } catch (err) {
      setError(err)
    }
  }

  const openDetail = async (documentId) => {
    setError(null)
    setCopied(false)
    try {
      const doc = await req(`/v1/knowledge/documents/${encodeURIComponent(documentId)}`, { role })
      setSelected(doc)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(err)
    }
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
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(err)
    }
  }

  const handleEditFileChange = (event) => {
    const file = event.target.files && event.target.files[0]
    if (!file) {
      setEditFile(null)
      return
    }
    setEditFile(file)
    setError(null)
  }

  const saveEdit = async (event) => {
    event.preventDefault()
    if (!editing) return
    setError(null)
    setNotice(null)
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
          method: 'POST',
          role,
          body: formData,
        })
      } else {
        const trimmedContent = (editing.content || '').trim()
        if (!trimmedContent) {
          setError(new ApiError(400, 'EMPTY_CONTENT', 'Isi teks dokumen tidak boleh kosong.'))
          setSavingEdit(false)
          return
        }
        result = await req(`/v1/knowledge/documents/${encodeURIComponent(editing.document_id)}`, {
          method: 'PUT',
          role,
          body: { title: trimmedTitle, content: editing.content },
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
    setError(null)
    setNotice(null)
    setDeleting(true)
    try {
      const targetId = confirmDelete.document_id
      const result = await req(`/v1/knowledge/documents/${encodeURIComponent(targetId)}`, { method: 'DELETE', role })
      setNotice(result.message || 'Dokumen pengetahuan berhasil dihapus.')
      if (selected && selected.document_id === targetId) setSelected(null)
      if (editing && editing.document_id === targetId) {
        setEditing(null)
        setEditFile(null)
      }
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
    const matchesSearch =
      !searchQuery ||
      (d.title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (d.original_filename || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (d.uploaded_by || '').toLowerCase().includes(searchQuery.toLowerCase())

    const matchesStatus = statusFilter === 'all' || d.status === statusFilter
    return matchesSearch && matchesStatus
  })

  return (
    <section className="km-workspace">
      {/* Global Alerts / Notices */}
      <Err e={error} onClose={() => setError(null)} />
      {notice && (
        <div className="alert ok chat-notice" role="status">
          <span>{notice}</span>
          <button type="button" className="btn sm" style={{ marginLeft: 'auto' }} onClick={() => setNotice(null)}>✕</button>
        </div>
      )}

      {/* =========================================================================
          VIEW MODE 1: DEDICATED EDIT SCREEN
          ========================================================================= */}
      {editing ? (
        <div>
          <div className="km-view-header">
            <button
              type="button"
              className="km-back-btn"
              onClick={() => { setEditing(null); setEditFile(null) }}
            >
              ← Kembali ke Katalog Dokumen
            </button>
            <span className="badge b-gray" style={{ fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
              Versi Dokumen: v{editing.version_no}
            </span>
          </div>

          <Card
            title={`Edit Dokumen: ${editing.original_filename || editing.title}`}
            sub="Perbarui judul, sunting teks dokumen secara langsung, atau unggah berkas revisi pengganti untuk diindeks ulang ke sistem AI."
            wide
          >
            <form className="form" onSubmit={saveEdit}>
              <label htmlFor="knowledge-edit-title">
                Judul Dokumen (Title)
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
                  <span className="badge b-blue">Berkas pengganti: {editFile.name} ({(editFile.size / 1024).toFixed(1)} KB)</span>
                  <button type="button" className="btn sm" onClick={() => setEditFile(null)}>Batal ganti berkas</button>
                </div>
              )}

              {!editFile && (
                <label htmlFor="knowledge-edit-content">
                  Isi Teks Pengetahuan (Akan dipotong dan diindeks ulang otomatis saat disimpan)
                  <textarea
                    id="knowledge-edit-content"
                    rows={12}
                    value={editing.content}
                    onChange={(e) => setEditing({ ...editing, content: e.target.value })}
                    placeholder="Masukkan atau perbarui isi materi pengetahuan resmi..."
                  />
                </label>
              )}

              <div className="row mt" style={{ gap: 10, justifyContent: 'flex-end', paddingTop: 12, borderTop: '1px solid var(--line)' }}>
                <button
                  type="button"
                  className="btn"
                  disabled={savingEdit}
                  onClick={() => { setEditing(null); setEditFile(null) }}
                >
                  Batal
                </button>
                <button type="submit" className="btn primary" disabled={savingEdit}>
                  {savingEdit ? <><span className="button-spinner" aria-hidden="true" />Menyimpan & Mengindeks Ulang…</> : 'Simpan & Indeks Ulang'}
                </button>
              </div>
            </form>
          </Card>
        </div>
      ) : selected ? (
        /* =========================================================================
            VIEW MODE 2: DEDICATED DETAIL SCREEN
            ========================================================================= */
        <div>
          <div className="km-view-header">
            <button
              type="button"
              className="km-back-btn"
              onClick={() => setSelected(null)}
            >
              ← Kembali ke Katalog Dokumen
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className={statusBadgeClass(selected.status)} style={{ padding: '4px 10px', fontSize: '11px' }}>
                Status: {statusLabel(selected.status)}
              </span>
              <span className="badge b-gray" style={{ padding: '4px 10px', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                v{selected.version_no}
              </span>
            </div>
          </div>

          <Card title={`Detail Dokumen: ${selected.title || selected.original_filename}`} wide>
            <div className="kv" style={{ fontSize: '13px' }}>
              <dt>Document ID</dt><dd style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{selected.document_id}</dd>
              <dt>Judul Dokumen</dt><dd><strong>{selected.title || selected.original_filename}</strong></dd>
              <dt>Nama Berkas Asli</dt><dd>{selected.original_filename}</dd>
              <dt>Format Berkas</dt><dd style={{ fontFamily: 'var(--font-mono)' }}>{selected.mime_type || '-'}</dd>
              <dt>Ukuran Berkas</dt><dd style={{ fontFamily: 'var(--font-mono)' }}>{(selected.file_size / 1024).toFixed(1)} KB</dd>
              <dt>Versi Materi</dt><dd style={{ fontFamily: 'var(--font-mono)' }}>v{selected.version_no}</dd>
              <dt>Status Indeks</dt><dd><span className={statusBadgeClass(selected.status)}>{statusLabel(selected.status)}</span></dd>
              <dt>Potongan Teks (Chunks)</dt><dd><strong style={{ color: 'var(--electric-blue)' }}>{selected.chunk_count} chunk</strong> aktif diindeks AI</dd>
              <dt>Pengunggah</dt><dd>{selected.uploaded_by || '-'} ({selected.uploaded_by_type || '-'})</dd>
              <dt>Waktu Dibuat</dt><dd>{selected.created_at ? new Date(selected.created_at).toLocaleString('id-ID') : '-'}</dd>
              <dt>Waktu Diperbarui</dt><dd>{selected.updated_at ? new Date(selected.updated_at).toLocaleString('id-ID') : '-'}</dd>
              {selected.status === 'failed' && selected.error_message && (
                <><dt>Pesan Kesalahan</dt><dd style={{ color: 'var(--danger)', fontWeight: 600 }}>{selected.error_message}</dd></>
              )}
            </div>

            {selected.content && (
              <div className="mt" style={{ borderTop: '1px solid var(--line)', paddingTop: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <strong style={{ fontSize: 13, color: 'var(--ink)' }}>Isi Teks Dokumen Terindeks (Knowledge Content):</strong>
                  <button type="button" className="btn sm" onClick={() => copyText(selected.content)}>
                    {copied ? '✓ Teks Tersalin!' : 'Salin Teks'}
                  </button>
                </div>
                <pre
                  className="dump"
                  style={{
                    whiteSpace: 'pre-wrap',
                    maxHeight: 400,
                    background: '#0b1523',
                    border: '1px solid var(--sidebar-border)',
                    padding: '16px',
                    fontSize: '12px',
                    lineHeight: '1.6'
                  }}
                >
                  {selected.content}
                </pre>
              </div>
            )}

            <div className="row mt" style={{ gap: 10, justifyContent: 'flex-end', paddingTop: 16, borderTop: '1px solid var(--line)' }}>
              <button type="button" className="btn" onClick={() => setSelected(null)}>
                ← Kembali ke Katalog
              </button>
              <button type="button" className="btn" onClick={() => openEdit(selected.document_id)}>
                Edit Dokumen Ini
              </button>
              <button type="button" className="btn danger" onClick={() => askDelete(selected)}>
                Hapus Dokumen
              </button>
              {selected.status === 'failed' && (
                <button type="button" className="btn primary" onClick={() => { retry(selected.document_id); setSelected(null) }}>
                  Coba Lagi Proses
                </button>
              )}
            </div>
          </Card>
        </div>
      ) : (
        /* =========================================================================
            VIEW MODE 3: MAIN CATALOG DASHBOARD & TABLE
            ========================================================================= */
        <>
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

          {/* Panel Tambah Knowledge Baru (Expandable Drawer) */}
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

          {/* Main Document Catalog Card */}
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
                    <th style={{ textAlign: 'right', minWidth: '160px' }}>Aksi</th>
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
                        <td style={{ verticalAlign: 'middle' }}>
                          <strong style={{ color: 'var(--ink)' }}>{d.title || d.original_filename}</strong>
                          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                            {d.original_filename && d.original_filename !== d.title ? `${d.original_filename} • ` : ''}
                            <span style={{ fontFamily: 'var(--font-mono)' }}>{d.mime_type || '-'}</span>
                          </div>
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', verticalAlign: 'middle' }}>{(d.file_size / 1024).toFixed(1)} KB</td>
                        <td style={{ fontFamily: 'var(--font-mono)', verticalAlign: 'middle' }}>v{d.version_no}</td>
                        <td style={{ verticalAlign: 'middle' }}><span className={statusBadgeClass(d.status)}>{statusLabel(d.status)}</span></td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, verticalAlign: 'middle' }}>{d.chunk_count} chunk</td>
                        <td style={{ verticalAlign: 'middle' }}><span style={{ color: 'var(--ink-soft)' }}>{d.uploaded_by || '-'}</span></td>
                        <td style={{ color: 'var(--muted)', fontSize: 11, verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                          {d.created_at ? new Date(d.created_at).toLocaleString('id-ID') : '-'}
                        </td>
                        <td style={{ textAlign: 'right', verticalAlign: 'middle' }}>
                          <div className="row" style={{ gap: 6, justifyContent: 'flex-end', flexWrap: 'nowrap' }}>
                            {d.status === 'failed' && (
                              <button type="button" className="btn sm primary" onClick={() => retry(d.document_id)}>Coba Lagi</button>
                            )}
                            <button
                              type="button"
                              className="btn sm"
                              style={{ height: '26px', minHeight: '26px', padding: '0 10px', fontSize: '11px', fontWeight: 600 }}
                              onClick={() => openDetail(d.document_id)}
                            >
                              Detail
                            </button>
                            <button
                              type="button"
                              className="btn sm"
                              style={{ height: '26px', minHeight: '26px', padding: '0 10px', fontSize: '11px', fontWeight: 600 }}
                              onClick={() => openEdit(d.document_id)}
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              className="btn sm danger"
                              style={{ height: '26px', minHeight: '26px', padding: '0 10px', fontSize: '11px', fontWeight: 600 }}
                              onClick={() => askDelete(d)}
                            >
                              Hapus
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* =========================================================================
          GLOBAL MODAL: CENTERED PROMINENT DELETE CONFIRMATION DIALOG
          ========================================================================= */}
      {confirmDelete && (
        <div className="km-modal-overlay" onClick={() => !deleting && setConfirmDelete(null)}>
          <div className="km-modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="km-modal-header">
              <div className="km-modal-icon-danger">⚠️</div>
              <div>
                <h3 className="km-modal-title">Konfirmasi Hapus Dokumen</h3>
                <p className="km-modal-sub">Tindakan ini akan menghapus materi dari AI Agent</p>
              </div>
            </div>
            <div className="km-modal-body">
              <p>
                Apakah Anda yakin ingin menghapus materi pengetahuan{' '}
                <strong>"{confirmDelete.title || confirmDelete.original_filename}"</strong>?
              </p>
              <div className="km-modal-alert">
                Seluruh <strong>{confirmDelete.chunk_count || 0} potongan teks (chunks)</strong> dan data embedding vektor dokumen ini akan dihapus secara permanen dari pencarian chatbot AI.
              </div>
            </div>
            <div className="km-modal-actions">
              <button
                type="button"
                className="btn"
                disabled={deleting}
                onClick={() => setConfirmDelete(null)}
              >
                Batal
              </button>
              <button
                type="button"
                className="btn danger"
                disabled={deleting}
                onClick={executeDelete}
              >
                {deleting ? 'Menghapus…' : 'Ya, Hapus Dokumen'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

export default KnowledgeManager
