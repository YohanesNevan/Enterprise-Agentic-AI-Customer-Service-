# Unit 06 — Mentor / Product / Security Approval Checklist

**Status:** awaiting review; all selections below are blank and unresolved.  
**Decision source:** `docs/units/UNIT_06_DECISION_LOG.md` (D-01…D-10).  
**Progress gate:** `context/progress-tracker.md` records Unit 05 as IN PROGRESS. Browser journey and accessibility verification remain required. This checklist does not record approval or authorize implementation.

## Cara menggunakan

Untuk setiap pertanyaan, pilih satu opsi atau tulis alternatif. Rekomendasi teknis hanya usulan, bukan keputusan resmi. Isi nama pemberi persetujuan dan tanggal hanya oleh pihak yang benar-benar menyetujui; tidak ada nama/tanggal yang diisi sebelumnya.

## Lima keputusan P0 — blocker sebelum coding

### P0 — D-01: Siapa yang boleh membuat case dari chat customer, dan assurance apa yang wajib?

**Kondisi aktual:** role `customer` belum memiliki `case.create`; tool registry `create_case` mensyaratkan AL1. Chat/orchestrator belum meneruskan principal customer terverifikasi ke service create case. Jangan mengubah permission atau menurunkan assurance hanya agar alur berhasil.

Pilih arah:

- [ ] Customer boleh membuat case dengan permission dan assurance yang disetujui.
- [ ] Backend memakai kapabilitas service yang didelegasikan secara terbatas, dengan customer tetap menjadi owner dan setiap keputusan policy tercatat.
- [ ] Customer harus step-up/konfirmasi sebelum case dibuat.
- [ ] Case hanya dapat dibuat oleh petugas manusia.
- [ ] Lainnya: ______________________________________________

**Pertanyaan persetujuan:** Siapa aktor yang berwenang membuat case, apakah AL1 diperlukan, dan apakah complaint boleh langsung dicatat dari sesi customer saat ini?

**Rekomendasi teknis saat ini — BELUM DISETUJUI:** jangan menambah `case.create` ke customer dan jangan menurunkan AL. Setelah model delegasi disetujui, gunakan service intake backend dengan principal, tenant, customer, conversation, policy decision, dan provenance yang terikat serta tervalidasi.

**Pihak yang menyetujui:** Product/mentor dan Security.  
**Konsekuensi bila belum disetujui:** tahap D dan customer create flow berhenti; tidak boleh membuat case melalui bypass RBAC/gateway.  
**Tahap terdampak:** A0, B, C, D, F, H.

**Jawaban/keputusan:** `UNRESOLVED` — ______________________________________________  
**Pemberi persetujuan:** ____________________ **Tanggal:** ____________________

### P0 — D-02: Migration/schema akan digelar melalui prosedur apa?

**Kondisi aktual:** `alembic/env.py` belum ada; revision `0001` menggunakan `create_all()` dan downgrade no-op; startup aplikasi juga membuat metadata. Database target tidak diperiksa pada review ini.

Pilih arah:

- [ ] Siapkan dan verifikasi Alembic migration additive setelah baseline database dikonfirmasi.
- [ ] Tunda penambahan schema sampai pemilik database menyiapkan prosedur migration.
- [ ] Lainnya: ______________________________________________

**Pertanyaan persetujuan:** Siapa pemilik migration, database mana yang menjadi baseline, bagaimana data case lama di-backfill, dan bagaimana upgrade/recovery diuji?

**Rekomendasi teknis saat ini — BELUM DISETUJUI:** perbaiki/verifikasi migration runner dan gunakan migration additive yang diuji di database disposable serta schema representatif; jangan menganggap `create_all()` sebagai migration.

**Pihak yang menyetujui:** Architecture/DB owner; Product/mentor menyetujui dampak data dan jadwal rollout bila relevan.  
**Konsekuensi bila belum disetujui:** tahap B dan semua perubahan schema/persistence berhenti; jangan menjalankan migration.

**Tahap terdampak:** A0, B, C, E, F, H.

**Jawaban/keputusan:** `UNRESOLVED` — ______________________________________________  
**Pemberi persetujuan:** ____________________ **Tanggal:** ____________________

### P0 — D-03: Apa yang customer lihat ketika CRM tidak tersedia?

**Kondisi aktual:** PostgreSQL dapat menyimpan case dan reference lokal sebelum outbox diproses. FRD v0.9 menyebut reference menyusul setelah recovery; TRD v0.9 menggambarkan reference lokal saat degraded. Konflik ini belum diselesaikan.

Pilih arah:

- [ ] Tampilkan reference lokal setelah case commit dan nyatakan pengiriman CRM masih pending.
- [ ] Tampilkan receipt sementara; reference customer final diberikan setelah penerimaan simulator.
- [ ] Jangan menerima complaint ketika CRM unavailable.
- [ ] Lainnya: ______________________________________________

**Pertanyaan persetujuan:** Apakah case lokal PostgreSQL menjadi catatan yang dapat dilacak customer meski CRM belum menerima data?

**Rekomendasi teknis saat ini — BELUM DISETUJUI:** bila case lokal dinyatakan authoritative, tampilkan reference setelah commit dan pisahkan status case lokal dari status delivery CRM. Jangan menyebut outbox `SENT` sebagai penerimaan CRM.

**Pihak yang menyetujui:** Product/mentor.  
**Konsekuensi bila belum disetujui:** copy/response/API/UI degraded mode tidak dapat ditetapkan; tahap F/G tidak boleh mengklaim reference final saat outage.

**Tahap terdampak:** A0, C, E, F, G, H.

**Jawaban/keputusan:** `UNRESOLVED` — ______________________________________________  
**Pemberi persetujuan:** ____________________ **Tanggal:** ____________________

### P0 — D-04: Apa yang dianggap ACK simulator, kapan retry berhenti, dan siapa menangani kegagalan?

**Kondisi aktual:** worker saat ini hanya mengganti state lokal ke `SENT` bila boolean simulator bernilai tersedia. Tidak ada respons ACK yang tercatat, koneksi CRM eksternal, retry backoff/batas, atau reconciliation task CRM yang terbukti. `HandoffRow` adalah antrean percakapan, bukan otomatis task CRM.

Pilih/isi kontrak:

- Definisi simulator ACK: ______________________________________________
- Batas dan jeda retry: ______________________________________________
- Setelah retry habis, task dibuat di: __________________________________
- Owner/queue dan SLA task: ___________________________________________
- Customer diberi tahu bahwa: _________________________________________

**Rekomendasi teknis saat ini — BELUM DISETUJUI:** pisahkan fakta `case persisted`, state outbox, ACK simulator, dan penerimaan eksternal CRM. Hanya respons adapter eksplisit yang dapat menjadi ACK; buat task rekonsiliasi durable satu kali setelah retry yang disetujui habis.

**Pihak yang menyetujui:** Operations dan Product/mentor; Security/architecture meninjau audit dan idempotency kontraknya.

**Konsekuensi bila belum disetujui:** tahap E dan klaim pemenuhan penuh FR-CASE-001 berhenti. Outbox `SENT` yang sekarang tidak boleh disebut ACK atau CRM receipt.

**Tahap terdampak:** A0, B, C, E, F, H.

**Jawaban/keputusan:** `UNRESOLVED` — ______________________________________________  
**Pemberi persetujuan:** ____________________ **Tanggal:** ____________________

### P0 — D-09: Dokumen FRD/TRD versi mana yang menjadi baseline resmi Unit 06?

**Kondisi aktual:** salinan PDF yang tersedia adalah v0.9 draft; TRD menyebut FRD v1.0 approved, tetapi salinan signed FRD v1.0 dan bukti approval TRD §16 tidak ditemukan. Build plan masih menandai baseline canonical unresolved.

Pilih arah:

- [ ] Setujui FRD/TRD v0.9 sebagai baseline sementara Unit 06 dengan prosedur pencatatan perubahan.
- [ ] Tunggu signed FRD v1.0 dan approval TRD sebelum coding.
- [ ] Izinkan pekerjaan teknis terbatas; keputusan customer/business behavior tetap menunggu baseline.
- [ ] Lainnya: ______________________________________________

**Pertanyaan persetujuan:** Versi dan status dokumen mana yang harus dipakai sebagai acceptance baseline untuk Unit 06?

**Rekomendasi teknis saat ini — BELUM DISETUJUI:** catat baseline tertulis dan persetujuan/pengecualian sebelum keputusan schema atau behavior customer dibuat.

**Pihak yang menyetujui:** Product/mentor.  
**Konsekuensi bila belum disetujui:** persyaratan dan acceptance criteria Unit 06 tetap provisional; tahap A0–H tidak dapat dinyatakan memiliki baseline resmi.

**Tahap terdampak:** A0 dan semua tahap B–H.

**Jawaban/keputusan:** `UNRESOLVED` — ______________________________________________  
**Pemberi persetujuan:** ____________________ **Tanggal:** ____________________

## Keputusan lain D-05 sampai D-08 dan D-10

### D-05 — Bagaimana complaint tanpa transaction ID dideduplikasi? — **UNRESOLVED / P1**

**Pertanyaan:** Apakah customer harus memberikan transaction reference sebelum case dapat dicocokkan dengan case terbuka? Jika tidak, apakah dedupe dibatasi pada request yang sama atau conversation yang sama?

**Pilihan ringkas:** same-request saja; exact transaction reference + customer/tenant/category + open status; conversation + category; fuzzy text matching; lainnya.

**Rekomendasi teknis saat ini — BELUM DISETUJUI:** idempotency durable untuk request yang sama; lintas request hanya exact incident key. Tanpa key, klarifikasi atau buat complaint terpisah sesuai minimum intake yang disetujui; hindari fuzzy merge.

**Pihak yang menyetujui:** Product/mentor. **Developer setelah kontrak:** unique constraint, canonical key dan transaksi atomik.  
**Jika belum diputuskan:** dedupe lintas request tidak dapat diklaim; tahap C tidak boleh memakai fuzzy merge.  
**Tahap:** A0, B, C, H.

**Jawaban:** `UNRESOLVED` — ______________________________________________

### D-06 — Status apa yang aman dan mudah dipahami customer? — **UNRESOLVED / P1**

**Pertanyaan:** Apakah API mempertahankan enum saat ini (`RECEIVED`, `BEING_INVESTIGATED`, `WAITING_FOR_YOU`, dll.) atau memakai enum publik sesuai label FRD? Apakah status detail reference membutuhkan AL2?

**Rekomendasi teknis saat ini — BELUM DISETUJUI:** buat projection customer allowlisted terpisah dari status internal; sepakati enum/label dan tingkat assurance sebelum API/UI.

**Pihak yang menyetujui:** Product/API owner; Security untuk assurance/disclosure. **Developer setelah kontrak:** mapping/versioning dan test projection.  
**Fakta terkait:** `/v1/cases/{cid}` saat ini mengembalikan internal `status`; `/v1/status/{reference}` tidak mengimplementasikan syarat AL2 yang tertulis di Unit 02. Jangan menganggap kedua route sudah menjadi kontrak customer final.  
**Jika belum diputuskan:** tahap F/G tidak boleh menampilkan internal status atau mengandalkan aturan AL2 yang belum diterapkan.  
**Tahap:** A0, F, G, H.

**Jawaban:** `UNRESOLVED` — ______________________________________________

### D-07 — Apa yang harus disimpan dalam audit/timeline dan berapa lama? — **UNRESOLVED / P1**

**Pertanyaan:** Apakah Unit 06 menambah timeline case durable dan atomik dengan mutasi, dan field/retensi apa yang diizinkan? Apakah audit global durable termasuk scope Unit 06 atau unit terpisah?

**Rekomendasi teknis saat ini — BELUM DISETUJUI:** timeline case append-only dalam transaksi case/outbox, memuat actor/provenance/correlation dan visibility; minimalkan payload sensitif. Jangan klaim audit durable dari `audit_svc` in-memory.

**Pihak yang menyetujui:** Architecture/Product/Compliance. **Developer setelah kontrak:** table/service invariants dan atomicity tests.  
**Jika belum diputuskan:** timeline dan compliance acceptance tetap unresolved; payload audit tidak boleh dirancang berdasarkan asumsi retensi.  
**Tahap:** A0, B, C, E, H.

**Jawaban:** `UNRESOLVED` — ______________________________________________

### D-08 — Bagaimana chat idempotency terhubung ke create-case operation? — **UNRESOLVED / P1**

**Pertanyaan:** Berapa lama request key/hash disimpan dan bagaimana retry dipulihkan jika case telah commit tetapi chat ledger belum COMPLETE?

**Rekomendasi teknis saat ini — BELUM DISETUJUI:** pakai identitas request yang diturunkan server-side, jangan simpan raw header; durable unique operation mapping disimpan atomik bersama case/outbox/timeline dan dipakai untuk resolve crash-window retry.

**Pihak yang menyetujui:** Architecture/Security untuk expiry, scope dan correlation. **Developer setelah kontrak:** mapping table/unique key/transaction.  
**Jika belum diputuskan:** replay test hanya membuktikan chat-level replay biasa, bukan no-duplicate setelah crash/concurrency.  
**Tahap:** A0, B, C, D, H.

**Jawaban:** `UNRESOLVED` — ______________________________________________

### D-10 — Apakah Unit 06 boleh mulai sebelum gate Unit 05 selesai? — **UNRESOLVED / P1**

**Progress aktual:** tracker menyatakan Unit 05 masih `IN PROGRESS`; browser journey dan accessibility verification belum selesai. Build plan menyebut Unit 06 berikutnya setelah pemeriksaan tersebut.

Pilih arah:

- [ ] Selesaikan browser/accessibility Unit 05 sebelum Unit 06 code.
- [ ] Izinkan Unit 06 backend berjalan paralel; UI Unit 06 tetap menunggu hasil Unit 05.
- [ ] Izinkan seluruh Unit 06 paralel dengan batas file/scope yang disepakati.
- [ ] Lainnya: ______________________________________________

**Rekomendasi teknis saat ini — BELUM DISETUJUI:** selesaikan gate Unit 05 sebelum application-code work; pengecualian paralel memerlukan persetujuan mentor/project owner. Hindari perubahan bersamaan pada chat UI.

**Pihak yang menyetujui:** Mentor/project owner. **Developer setelah kontrak:** menjadwalkan tahap dan menghindari konflik file.  
**Jika belum diputuskan:** ikuti urutan build plan dan jangan mulai implementasi Unit 06.  
**Tahap:** A0 dan semua tahap implementasi.

**Jawaban:** `UNRESOLVED` — ______________________________________________

## Keputusan bisnis/keamanan vs pilihan teknis developer

### Persetujuan bisnis/keamanan/operasi yang dibutuhkan

- Aktor dan assurance create case, serta delegated authority — D-01.
- Source-of-truth reference saat outage, customer wording dan perilaku penerimaan — D-03.
- Makna ACK, batas retry, reconciliation owner/queue/SLA — D-04.
- Definisi matching complaint/open case dan minimum data customer — D-05.
- Label/status publik dan assurance disclosure — D-06.
- Audit/timeline fields, visibility, scope dan retention — D-07.
- Retensi/expiry idempotency bila berdampak pada audit/data policy — D-08.
- Baseline FRD/TRD dan Unit05 sequencing/scope exception — D-09/D-10.
- Migration baseline, existing data treatment dan rollout window — D-02.

### Hal teknis yang dapat diputus developer setelah kontrak disetujui

- Cara menambahkan migration additive, index/constraint, backfill dan menguji upgrade di DB disposable; tidak boleh mengganti requirement/retensi yang disetujui.
- Implementasi transaksi atomik case/SLA/outbox/idempotency/timeline dan unique constraint.
- Adapter/test fixture yang merepresentasikan ACK contract yang sudah dipilih; tidak boleh menyamakan simulator dengan CRM eksternal.
- Mapping status internal ke public projection sesuai enum/label yang disetujui.
- Pagination/cursor, response Pydantic schema, dan struktur komponen UI dalam scope yang disetujui.
- Pemilihan test organization/fixtures dan command yang tidak menyentuh database non-test.

## Ringkasan jawaban yang dibutuhkan mentor

1. D-01: siapa yang boleh membuat case dan assurance apa yang wajib?
2. D-02: siapa pemilik dan baseline migration/schema yang aman?
3. D-03: apakah reference lokal boleh diberikan ketika CRM tidak tersedia?
4. D-04: apa ACK simulator, retry policy dan owner reconciliation task?
5. D-09: FRD/TRD versi mana yang disetujui sebagai baseline?
6. D-05–D-08: aturan dedupe, status publik, audit/timeline dan idempotency apa yang disepakati?
7. D-10: Unit 05 browser/accessibility gate harus selesai dahulu atau ada pengecualian paralel?

**Tidak ada jawaban atau persetujuan yang dicatat dalam dokumen ini. Seluruh butir tetap UNRESOLVED sampai diisi pihak berwenang.**
