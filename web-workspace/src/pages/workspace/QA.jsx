import React, { useCallback, useEffect, useState } from 'react'
import { req, QA_FIELDS, QA_AUTO_FAIL, QA_FINDING_TYPES, SEVERITIES } from '../../api.js'
import { Card, Err, Empty, Json } from '../../shared/ui.jsx'
import { useForm } from '../../shared/useForm.js'

export function QA({ role }) {
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
          <div className="form">
            <label>Random Seed<input type="number" value={seed} onChange={(e) => setSeed(e.target.value)} /></label>
            <div className="row"><button className="btn primary" onClick={sample}>Tarik Sampel Evaluasi</button></div>
          </div>
        </Card>
        <Card title="Penilaian Mutu (Review Scoring)" sub="Skor skala 0–10 untuk setiap dimensi pelayanan.">
          <div className="form">
            <label>Item ID (Kasus / Percakapan)<input value={sc.item_id} onChange={setSc('item_id')} placeholder="CAS-..." /></label>
            <div className="form2">
              {QA_FIELDS.map((fld) => (
                <label key={fld}>{fld}<input type="number" min={0} max={10} value={scores[fld]} onChange={(e) => setScores({ ...scores, [fld]: e.target.value })} /></label>
              ))}
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

export default QA
