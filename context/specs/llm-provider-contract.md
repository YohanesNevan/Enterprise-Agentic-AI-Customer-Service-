# Persiapan Kontrak Provider LLM

Status: fondasi provider lokal dan tes kontrak diimplementasikan; spesifikasi provider eksternal tetap belum disahkan dan belum diimplementasikan.

## Tujuan dan batas

Dokumen ini menyiapkan kontrak internal sebelum adapter provider eksternal dibuat. Ini bukan spesifikasi implementasi Gemini yang telah disetujui. Audit baseline menemukan belum ada gateway/interface, adapter, atau pemanggilan model; tahap ini menambahkan interface dan validasi kontrak lokal di app/modules/llm_provider.py, tetapi tidak menghubungkannya ke orchestrator. BUDGET_LLM = 4 di app/modules/orchestrator.py bukan bukti adanya empat call site. Stub di modul baru memberi fixture deterministik, sementara perilaku aplikasi tetap deterministik tanpa memanggil provider.

Tidak ada kode, .env, .env.example, dependensi, atau konfigurasi provider yang berubah dalam tahap persiapan ini. Tidak ada kredensial yang dibaca, tidak ada request provider yang dikirim, dan tidak ada integrasi live yang diuji.

## Status sumber dan persetujuan

- FRD-EAICS-001 v0.9 yang tersedia berstatus draft.
- TRD-EAICS-001 v0.9 yang tersedia merujuk FRD v1.0 yang dibekukan/disahkan. FRD v1.0 bertanda tangan belum tersedia di repo.
- TRD §16 menyatakan gerbang persetujuan integrasi. Tabel kontrak di salinan TRD yang diperiksa belum menunjukkan persetujuan yang dapat diverifikasi; kontrak §16 belum dikonfirmasi.
- Definisi fungsi dan aturan alur di bawah ini mengutip rancangan TRD §§8.1–8.2 (PDF hlm. 43) sebagai baseline kerja, bukan klaim kontrak final.
- TRD §13.9 menyebut kegagalan provider LLM (timeout, error_500, rate_limited) masuk ke mode degraded. TRD §13.11 mengarahkan penggunaan stub dan fixture untuk pengujian, dengan model nyata hanya pada EVAL/E2E terjadwal yang dipatok. Waktu, biaya, izin data, dan prosedur live run masih perlu persetujuan.

## Kontrak abstraksi yang diusulkan

### Interface provider

Usulkan satu interface internal generasi terstruktur dengan operasi konseptual generate(task, input, output_schema, timeout) -> validated_output. task hanya salah satu F1, F2, F3, F4. Implementasi provider menerima payload minimal yang telah disusun orchestrator; ia tidak menerima akses database, principal, sesi otorisasi, policy engine, status workflow, atau tool executor. Gateway memvalidasi respons dengan model Pydantic khusus fungsi sebelum hasil dapat dikembalikan ke orchestrator.

Kontrak ini tidak mewajibkan method signature Python tertentu. Generic dict tidak cukup sebagai hasil tervalidasi. Adapter tidak boleh mengeksekusi function/tool call dari provider. F3 hanya mengembalikan usulan data terstruktur; komponen kode yang ada tetap menghitung allowlist, mengevaluasi policy, dan memanggil gateway tool.

### Stub deterministik

Stub menjadi implementasi referensi/offline yang menerima fixture input dan memberikan fixture output tervalidasi untuk F1–F4. Kasus yang tidak memiliki fixture harus gagal eksplisit dengan hasil terklasifikasi, bukan menebak output. Stub tidak mengakses jaringan, environment key, atau layanan eksternal. Fixture disimpan sebagai data sintetis dan tidak mengandung data pelanggan atau kredensial. CI dan tes unit/kontrak wajib menggunakan stub atau fake provider; default tetap stub sampai keputusan konfigurasi disahkan.

### Adapter eksternal

Adapter eksternal terpisah dari interface dan tidak menjadi default otomatis. Gemini adalah kandidat teknis dari audit, bukan keputusan provider. Adapter hanya mengirim permintaan generasi terstruktur untuk fungsi yang diaktifkan, memetakan respons/error ke kontrak internal, dan tidak melakukan retry di luar kebijakan orkestrator. SDK, endpoint/region, versi model, retensi data, dan batas pengiriman data harus diputuskan dan disetujui sebelum implementasi.

## Konfigurasi yang perlu diputuskan

| Setting | Rancangan | Status |
|---|---|---|
| Provider | stub sebagai default deterministik; nama provider eksternal hanya aktif melalui konfigurasi server | Pilihan dan nama nilai provider belum disetujui |
| Model | Nama/versi model dibaca oleh adapter dari konfigurasi server | Model Gemini dan kebijakan pin versi belum disetujui |
| API key | Rahasia sisi server, tidak pernah tersedia ke SPA, respons API, log, atau repo | Nama variabel unresolved: mempertahankan LLM_API_KEY atau memakai nama provider seperti GEMINI_API_KEY; secret manager dan rotasi juga belum disetujui |
| Timeout | Nilai positif dan terbatas untuk setiap request provider, tidak boleh melampaui sisa budget giliran | Nama env dan angka default belum disetujui. TRD §8.2 memberi total wall_ms=20000, bukan timeout per request |
| Retry | Tidak mengulang otomatis kegagalan provider pada tahap adapter | Rancangan konservatif; retry/rate-limit policy memerlukan persetujuan. Retry F4 satu kali untuk klaim unsupported di §8.2 adalah retry orkestrasi yang berbeda dan terbatas pada kasus itu |
| Jumlah call | Maksimum empat call logis per giliran, hanya F1–F4 menurut rancangan §8 | Batas draft TRD; enablement fungsi dan interpretasi sub-call perlu dikonfirmasi pada kontrak final |

Tidak ada satu pun nama environment variable atau nilai timeout di tabel ini yang boleh diterapkan sebelum diputuskan. Nilai yang sudah ada pada .env.example belum dibaca aplikasi menurut audit, sehingga tidak otomatis menjadi kontrak konfigurasi.

## Kontrak fungsi F1–F4

Skema di bawah memisahkan fakta dari TRD dan detail validasi yang diusulkan. TRD tidak memberi JSON Schema lengkap untuk keluaran fungsi LLM; bentuk field tambahan yang ditandai usulan harus disahkan sebelum implementasi. Untuk semua fungsi, Pydantic menolak field ekstra, tipe salah, nilai kosong yang dilarang, enum tidak dikenal, dan output yang gagal validasi. Keluaran mentah provider tidak diteruskan ke customer atau tool.

### F1 — Penyempurnaan intent

- Input TRD: pesan masuk dan konteks singkat.
- Output TRD: {intent_code, confidence_hint, entities, is_multi}.
- Larangan TRD: kode di luar enum; model menetapkan confidence akhir (tahap pertama/kode yang menetapkannya).
- Skema validasi yang diusulkan: intent_code enum V-1 TRD §16.2 (termasuk OTHER_UNCLASSIFIED); confidence_hint angka finite dalam rentang 0–1; entities objek dengan field yang telah ditetapkan; is_multi boolean. Range numerik, daftar entity yang boleh diisi, tipe masing-masing entity, dan arti is_multi perlu disahkan karena tidak dirinci §8.1.
- Validasi semantik: model tidak boleh menetapkan decision, kategori/otorisasi, threshold, mandatory handoff, atau confidence final. Hasil kode divalidasi terhadap taksonomi, kemudian aturan deterministik menerapkan mandatory handoff, confidence bands, kerentanan, dan policy.
- Fallback: gunakan hasil classifier deterministik yang ada (intent.classify). Jika classifier mengembalikan intent tak dikenal/tidak cukup bukti, ikuti jalur unknown-intent yang ada: abstain dari tebakan dan handoff sesuai policy. Jangan mengubah keputusan deterministik dengan confidence_hint yang tidak valid.

### F2 — Penyusunan klarifikasi

- Input TRD: kandidat intent.
- Output TRD: {question, options[<=3]}.
- Larangan TRD: lebih dari tiga opsi atau menampilkan kode internal.
- Skema validasi yang diusulkan: question string nonkosong; options array string yang berisi paling banyak tiga opsi nonkosong. Maksud apakah nol opsi diperbolehkan dan aturan bahasa/ukuran teks memerlukan pengesahan.
- Validasi semantik: pilihan harus sesuai kandidat intent yang disediakan; tidak boleh menambah fakta, tindakan, status, atau opsi yang mengubah policy. Kode intent internal tidak boleh tampil pada teks customer. Hitungan klarifikasi dan batas maksimal dua upaya pada §8.2 tetap dikelola kode.
- Fallback: gunakan klarifikasi deterministik yang ada (_options) bila masih di bawah batas. Bila output tidak valid, jangan tampilkan teks mentah model; fallback ke opsi deterministik. Bila batas klarifikasi tercapai, gunakan handoff LOW_CONFIDENCE sesuai alur deterministik.

### F3 — Penyusunan argumen tool

- Input TRD: skema tool yang sudah diizinkan dan konteks.
- Output TRD: satu pemanggilan fungsi yang sesuai dengan salah satu skema yang diizinkan.
- Larangan TRD: mengusulkan apa pun di luar himpunan yang diizinkan; mengarang argumen yang tidak dapat diturunkan dari konteks.
- Skema validasi yang diusulkan: {tool_name, arguments} dengan tool_name harus tepat salah satu nama dalam himpunan policy untuk giliran ini; arguments harus lolos schema versi tool yang bersangkutan, dengan field ekstra ditolak. Bentuk envelope final harus diselaraskan dengan kontrak tool §16.3.
- Validasi semantik: himpunan izin dihitung oleh policy engine sebelum prompt (ADR-04); model tidak dapat mengubahnya. Policy mengevaluasi ulang usulan dan argumen spesifik. Hanya executor kode yang boleh memanggil tool setelah ALLOW; approval, step-up, deny, dan status lain mengikuti workflow yang ada. Tidak ada panggilan tool dari SDK/provider secara langsung.
- Fallback: usulan tidak valid, out-of-set, atau argumen yang tidak bisa diturunkan dari konteks tidak pernah dieksekusi. Catat hasil policy/guardrail sesuai kontrak audit; gunakan jalur aman yang sudah ada seperti tolak/handoff. Mekanisme jumlah pelanggaran dan kapan handoff harus tetap mengikuti §8.2 dan memerlukan kontrak final, bukan kebijakan baru di adapter.

### F4 — Penyusunan jawaban

- Input TRD: kutipan hasil retrieval dan hasil tool pada giliran saat ini.
- Output TRD: {text, claim_map[]}.
- Larangan TRD: klaim tanpa referensi sumber di claim_map.
- Skema validasi yang diusulkan: text string; setiap item claim_map menghubungkan klaim dalam teks ke referensi source yang termasuk input giliran saat ini. Kandidat minimal: teks/locator klaim, jenis sumber (KNOWLEDGE_CITATION atau hasil tool), dan ID referensi. Bentuk final field, apakah klaim nonfaktual perlu dipetakan, serta granularitas locator belum ditetapkan TRD dan wajib disahkan. Referensi bebas/URL yang tidak ada pada input dilarang.
- Validasi semantik: semua fakta yang dapat diverifikasi harus didukung citation/tool result yang benar-benar tersedia, masih eligible, dan sesuai tenant/assurance yang sudah diperiksa kode. Pemeriksaan grounding/action-state tetap berjalan setelah respons; provider tidak menetapkan status aksi atau membuat sitasi.
- Fallback: bila sumber kosong, tidak eligible, atau hasil tidak dapat di-ground, jangan mengarang. Ikuti §8.2: satu retry F4 dengan instruksi lebih ketat hanya untuk output unsupported; bila tetap unsupported, kirim safe fallback dan handoff. Tanpa bukti, gunakan abstain/handoff deterministik. Untuk respons provider gagal sebelum validasi, gunakan jawaban deterministik/extractive hanya jika sumber yang valid tersedia; selain itu degraded/abstain.

## Error, fallback, dan logging

Gateway mengubah kondisi upstream menjadi kategori internal yang tidak memuat pesan mentah provider: timeout, rate limit, autentikasi/konfigurasi, respons kosong, output tidak valid, konektivitas, dan provider unavailable. Respons error provider, prompt, output mentah, exception detail yang mungkin memuat header, dan credential tidak boleh dikirim ke customer. Pemetaan akhir ke kode error TRD §16.6 harus disetujui; TRD menyebut E_TIMEOUT, E_RATE_LIMIT, E_UPSTREAM, dan E_UNAVAILABLE dengan status HTTP terkait, tetapi alur chat dapat memakai degraded response alih-alih mengembalikan error langsung.

Kegagalan provider LLM pada §13.9 masuk mode degraded: pesan jujur, tanpa aksi otonom. Bila F1 gagal, classifier deterministik boleh tetap menentukan intent; bila F2 gagal, gunakan klarifikasi deterministik yang ada. Bila F3 gagal, jangan jalankan tool atau tindakan otonom pada giliran degraded tersebut. Bila F4 gagal, sistem hanya boleh memberi jawaban extractive jika sumber valid tersedia dan aturan degraded yang disahkan mengizinkannya; selain itu abstain dan handoff. Pengulangan provider otomatis tidak dilakukan kecuali kebijakan retry disahkan; error rate limit tidak boleh diputar sebagai respons sukses.

Log/metric yang diusulkan hanya memuat task F1–F4, provider/model version yang tidak rahasia, correlation ID, durasi, kategori hasil/error, dan metrik pemakaian yang disetujui. Jangan mencatat API key, authorization header, prompt, teks pesan pelanggan, entity, argumen tool mentah, output mentah, atau PII. Audit event dan field final harus mengikuti kontrak audit §16.7 yang disahkan; jangan membuat nama event baru diam-diam. Redaksi rahasia wajib diuji pada exception, debug logging SDK, dan HTTP client logging.

## Invarian keamanan dan perilaku

Provider hanya komponen generasi teks/struktur. Ia tidak menerima atau menentukan principal, role, permission, assurance level, tenant ownership, idempotency key, policy decision, approval, status percakapan/kasus/tiket, audit result, atau tool execution. Semua invarian berikut harus lulus regresi:

- Authentikasi dan RBAC tetap diperiksa oleh backend; keluaran provider tidak dapat menaikkan hak akses atau assurance.
- Tenant/owner scoping dan pemaskeran berlaku sebelum data dimasukkan ke konteks model. Data pelanggan yang tidak diperlukan tidak dikirim; lampiran/bukti tidak dikirim ke LLM sesuai TRD §11.5–§11.6.
- Allowlist tool dihitung sebelum model dipanggil, usulan F3 divalidasi terhadapnya, lalu policy mengevaluasi ulang argumen.
- Idempotency dan audit tetap dimiliki kode workflow. Provider tidak mengubah record, memutuskan replay, atau meniadakan kegagalan audit.
- Status workflow serta bahasa klaim aksi berasal dari ledger/tool outcome aktual. Model tidak dapat menyebut aksi berhasil, kasus dibuat, atau handoff diterima jika status nyata tidak membenarkannya.
- Informasi customer harus grounded pada knowledge yang eligible dan memiliki provenance/citation. Output tidak valid atau tidak bersumber berujung fallback/abstain, bukan fakta rekaan.

## Rancangan pengujian kontrak

Semua kasus di bawah adalah tes yang direncanakan, belum dibuat atau dijalankan. Sesuaikan fixture dengan kontrak §16 final dan versi FRD yang disahkan.

### Tes unit (tanpa jaringan)

1. Stub deterministik: fixture yang sama dan task sama menghasilkan output tervalidasi yang sama; kasus tanpa fixture gagal eksplisit; spy transport memastikan tidak ada akses jaringan atau pembacaan key.
2. Pydantic menerima contoh F1–F4 yang valid; menolak field ekstra, tipe salah, field wajib hilang, string kosong sesuai constraint yang disahkan, dan JSON malformed.
3. F1 menolak intent di luar V-1 enum, confidence_hint non-finite/di luar range jika range disahkan, dan entity key di luar schema; pastikan hint tidak mengubah confidence final, decision, atau mandatory handoff.
4. F2 menolak empat opsi, kode internal yang muncul di teks customer, dan opsi yang tidak berasal dari kandidat; uji fallback deterministik serta batas dua percobaan klarifikasi.
5. F3 menolak nama tool di luar allowlist, argumen field ekstra/salah tipe, argumen yang tidak didukung context, dan output multi-tool. Pastikan tool executor tidak dipanggil pada semua penolakan.
6. F4 menolak claim tanpa reference, reference yang tidak ada di input giliran, source tidak eligible, atau klaim tidak grounded; uji satu strict retry lalu fallback/handoff.
7. Error mapping: respons kosong, JSON/skema invalid, timeout, rate-limit, auth/config error, koneksi gagal, dan provider 5xx menjadi kategori stabil tanpa membocorkan respons mentah.
8. Logging redaction: tangkap log pada jalur sukses dan seluruh error, cari canary API key, bearer credential, PII, pesan uji, dan argumen sensitif; target nol kebocoran.

### Tes kontrak provider (stub dan adapter palsu)

1. Jalankan suite fungsi F1–F4 yang sama terhadap stub referensi dan fake provider; kedua implementasi harus mengembalikan tipe/semantik internal yang sama atau error terklasifikasi.
2. Uji kontrak Pydantic request/response, empty/invalid output, timeout, rate-limit, error upstream, dan no-retry adapter.
3. Provider fake mengembalikan tool tak diizinkan dan argumen lintas tenant; verifikasi policy menolak dan executor tidak berjalan.
4. Provider fake menghasilkan klaim tanpa source; verifikasi grounding mencegah pengiriman dan tidak ada sitasi yang dibuat-buat.
5. Uji batas pemanggilan: pencatatan call hanya mengenali label F1, F2, F3, F4; maksimum empat call logis per giliran. Tes arsitektur/source memastikan tidak ada inference di luar gateway atau fungsi lain; mock gateway memastikan setiap call site yang diaktifkan melewati interface yang sama.
6. Regresi dengan respons provider adversarial: snapshot/asserte bahwa principal, permissions, tenant/owner predicates, idempotency ledger, audit transaction, conversation/case/ticket state transitions, approval, dan tool outcomes sama seperti kontrol deterministik. Provider tidak memiliki akses tulis ke penyimpanan.
7. Kegagalan gateway/policy/audit harus fail closed sesuai aturan yang disetujui; tidak ada jawaban faktual jika guardrail/grounding tidak tersedia.

### Tes integrasi provider nyata (opt-in, terpisah)

1. Jalankan hanya setelah provider, model/version, lokasi pemrosesan, secret handling, biaya/quota, dan persetujuan data disahkan.
2. Memerlukan explicit opt-in flag dan key dari secret store/environment lokal yang tidak tercatat; jika flag tidak aktif/key tidak tersedia, tes dilewati atau gagal dengan pesan aman tanpa mencoba jaringan.
3. Gunakan input sintetis, tidak memuat PII/rahasia, serta gunakan model/version yang dipatok. Tidak ada tes ini di CI deterministik.
4. Verifikasi satu permintaan per fungsi yang diaktifkan, validasi schema, timeout/rate limit/degraded contract yang dapat disimulasikan bila provider test environment mendukungnya, dan redaksi log. Jangan menguji eksekusi tool nyata melalui output model.
5. Catat provider/model, tanggal, hasil schema/latency/error class, dan biaya jika kebijakan menyetujui; jangan menyimpan key, prompt pelanggan, atau output sensitif.

## Keputusan yang memerlukan persetujuan sebelum implementasi

1. FRD v1.0 kanonis dan persetujuan integrasi TRD §16, termasuk kontrak LLM dan fixture bersama.
2. Provider yang disetujui (Gemini, lokal, atau pilihan lain), versi model yang dipatok, endpoint/region, dan dampak privasi/retensi.
3. Nama setting env untuk provider/model/key/timeout, secret store, rotasi, serta nilai timeout/retry/limit yang selaras dengan budget total 20 detik.
4. Skema final dan semantik confidence_hint, entities, is_multi, opsi F2, dan item claim_map F4.
5. Fungsi F1–F4 mana yang benar-benar diaktifkan, kapan dipanggil, aturan jumlah attempt, fallback copy/status, dan metrik/log/audit yang disepakati.
6. Kebijakan biaya, quota, pengiriman konteks minimal, dan apakah tes EVAL/E2E nyata sebagaimana TRD §13.11 diizinkan.

Setelah persetujuan, spesifikasi implementasi/provider dan fixture harus ditinjau sebagai unit kerja tersendiri. Sampai saat itu, konfigurasi stub tidak berubah dan adapter Gemini tidak dibuat.

## Adapter Gemini terisolasi (2026-10-16)

Bagian ini mencatat implementasi adapter offline yang tersedia setelah persiapan kontrak. Pernyataan “adapter Gemini tidak dibuat” di bagian sebelumnya adalah catatan keputusan sebelum tahap ini; adapter sekarang ada tetapi tetap tidak dipanggil oleh aplikasi.

- `app/modules/gemini_provider.py` mengimplementasikan `StructuredGenerationProvider.generate()` dengan Google Gen AI Python SDK, `models.generate_content`, JSON mode, dan schema Pydantic output F1–F4. Prompt mengirim hanya label fungsi dan payload kontrak. Request tidak menyertakan SDK tools atau function executor.
- Dependency dipatok `google-genai==2.31.0` (rilis Google SDK terkini yang diverifikasi pada 2026-10-16; mendukung Python 3.10+). Referensi: https://github.com/googleapis/python-genai/releases dan https://ai.google.dev/gemini-api/docs/generate-content/structured-output.
- Konfigurasi usulan yang kini dipakai adapter: `LLM_PROVIDER` (default `stub`, Gemini hanya bila eksplisit `gemini`), `LLM_MODEL` (wajib diisi model Gemini; `stub-1.0` ditolak), `LLM_API_KEY` (key server-side yang diberikan eksplisit ke client), dan `LLM_TIMEOUT_MS` (default 10000, integer 1–20000). Default model/provider tidak disetel otomatis dari ketersediaan key. Nama `LLM_API_KEY` dipilih agar konsisten dengan template repo yang sudah ada; template kini menandai konfigurasi Gemini opt-in dan hanya berisi placeholder kosong.
- SDK menerima `HttpRetryOptions(attempts=1)` sehingga adapter tidak menambah retry. Timeout per request dalam milidetik. Mapping internal menggunakan hanya tipe exception transport, status HTTP numerik, dan status RPC allowlisted SDK; message, details, body, header, URL, dan prompt tidak diperiksa atau diteruskan. `401`/`UNAUTHENTICATED` → `AUTHENTICATION`; `403`/`PERMISSION_DENIED` → `ACCESS_DENIED`; `404`/`NOT_FOUND` → `RESOURCE_NOT_FOUND`; `429`/`RESOURCE_EXHAUSTED` → `RATE_LIMITED`; timeout/408/504/`DEADLINE_EXCEEDED` → `TIMEOUT`; `400`/`INVALID_ARGUMENT`/`FAILED_PRECONDITION` → `CONFIGURATION`; exception transport `httpx` → `CONNECTION_ERROR`; HTTP 5xx → `PROVIDER_ERROR`; status/exception yang tidak dikenali tetap `UNAVAILABLE`. `RESOURCE_EXHAUSTED` tidak membedakan kuota dari rate limit, dan 404 tidak membuktikan bahwa model saja yang tidak ditemukan. Respons kosong dan schema invalid memakai `EMPTY_RESPONSE`/`OUTPUT_INVALID` dari validasi lokal.
- F3 membatasi `tool_name` pada allowlist input dan tidak memberi tool ke SDK. `generate_validated(..., tool_models=...)` tetap wajib untuk validasi schema dan argumen Pydantic spesifik tool sebelum siapa pun memakai proposal. F4 memastikan schema/claim map/source ID melalui boundary lokal; semantic grounding tetap tanggung jawab guardrail dan belum dipanggil adapter.
- `build_provider()` membaca `LLM_PROVIDER` dengan default `stub`; key yang tersedia saja tidak memilih Gemini. Pemanggil harus mengaktifkan provider secara eksplisit. Factory membuat error aman bila konfigurasi Gemini tidak lengkap.
- Tidak ada call site pada `orchestrator.py`, tidak ada pemanggilan saat startup/chat, dan tidak ada fallback percakapan yang diklaim berfungsi. Degraded/fallback saat adapter kelak diintegrasikan adalah pekerjaan terpisah. Kebijakan pengiriman data, retensi/region, persetujuan provider dan kontrak TRD §16 tetap belum selesai.
- Tes adapter menggunakan fake client dan tidak memerlukan key atau jaringan. Tes live terpisah ada di `tests/test_gemini_live_opt_in.py`, dilewati tanpa opt-in eksplisit, dan memerlukan SDK terpasang. Seluruh output tetap untrusted; tidak ada otoritas autentikasi, RBAC, tenant, approval, ticket/handoff, atau tool execution yang diberikan ke model.

### Pembaruan klasifikasi diagnostik (2026-10-16)

`ProviderErrorCode` mempertahankan semua nilai lama dan menambahkan `AUTHENTICATION`, `ACCESS_DENIED`, `RESOURCE_NOT_FOUND`, `CONNECTION_ERROR`, dan `PROVIDER_ERROR`. SDK `google-genai==2.31.0` mendefinisikan `google.genai.errors.APIError` dengan `code` numerik dan `status` RPC; adapter hanya membaca dua field tersebut dan membandingkan status RPC dengan label tetap. Exception transport `httpx.TimeoutException` dan `httpx.TransportError` ditangani berdasarkan tipe. ProviderError tetap hanya memuat kode kategori, tanpa cause upstream.

Tes offline menggunakan objek `ClientError`, `ServerError`, `APIError` SDK, serta exception transport `httpx`, dengan canary pada message/detail. Kategori baru bersifat additive terhadap kontrak internal, bukan perubahan schema F1–F4 atau payload provider. Status RPC allowlisted didahulukan atas HTTP code jika keduanya tersedia. Pemisahan kuota versus rate limit tidak dilakukan karena status SDK `RESOURCE_EXHAUSTED` saja tidak membuktikan penyebab spesifik; kategori `UNAVAILABLE` tetap fallback untuk data yang tidak dikenali.

## Implementasi fondasi lokal (2026-10-16)

### Yang diimplementasikan

- app/modules/llm_provider.py mendefinisikan StructuredGenerationProvider, LLMFunction tepat F1–F4, ProviderError terklasifikasi tanpa teks upstream, build_provider yang hanya mengonstruksi stub, dan generate_validated sebagai boundary validasi bersama. Timeout opsional hanya menerima integer positif; belum ada nilai default atau timeout transport jaringan.
- Stub memakai fixture sintetis yang dikunci pada hash fungsi+payload, mengembalikan salinan fixture, tidak memiliki transport jaringan, dan gagal eksplisit dengan NO_FIXTURE bila input tidak cocok. Provider selain stub ditolak; tidak ada konfigurasi environment yang dibaca.
- Input/output Pydantic menolak field tambahan. F1 memakai IntentCode dari vocabulary bersama, confidence_hint finite 0–1, dan entity keys terbatas ke slot yang saat ini dikenal (card_last4, reference, date_hint). Batas entity/range adalah pembatasan lokal sementara yang perlu diselaraskan jika kontrak §16 menyetujui schema lain.
- F2 mengharuskan question dan maksimal tiga options, menolak teks kosong serta kode intent internal.
- F3 mengharuskan nama tool berada pada permitted_tools, nama tool/schema set sama, JSON Schema di payload sama dengan schema Pydantic yang dimiliki kode, dan arguments valid terhadap model Pydantic tool. Validasi ini hanya mengembalikan proposal; tidak ada executor/panggilan tool.
- F4 mengharuskan teks jawaban, claim_map tidak kosong untuk teks nonkosong, claim ada dalam teks, source_ids unik dan hanya menunjuk source yang ada di input, serta claim source tidak boleh kosong. Pengecekan semantik bahwa fakta benar-benar didukung sumber masih wajib dilakukan guardrail setelah pemanggilan; tidak ada F4 call site yang mengirim jawaban.
- Respons None/kosong menjadi EMPTY_RESPONSE; skema/JSON invalid menjadi OUTPUT_INVALID; timeout, rate limit, no fixture, provider unavailable, dan konfigurasi memiliki kode error internal. Detail upstream tidak diteruskan atau dicatat oleh modul ini. Tidak ada retry atau adapter provider.

### Batas implementasi dan hasil tes

Modul kontrak belum dipanggil oleh app/modules/orchestrator.py. Orchestrator tetap memakai classifier dan jawaban deterministik, tidak ada titik panggilan model baru, dan konstanta budget 4 yang lama tidak berubah. Karena belum ada call site per giliran, batas budget saat runtime adalah nol panggilan; pemakaian kelak harus mempertahankan budget TRD secara eksplisit.

Tes di tests/test_llm_provider.py: 29 passed. Suite backend: 72 passed, 96 dependency deprecation warnings. Tes mencakup stub deterministik/no-fixture, validasi schema F1–F4, intent tidak dikenal, empat opsi, tool/schema/argumen tidak diizinkan, claim tanpa source yang valid, respons kosong/invalid, parameter timeout, mapping timeout/rate-limit/provider error tanpa bocor ke log, provider eksternal belum tersedia, dan tidak ada call site LLM pada orchestrator. Suite backend juga menjalankan regresi keamanan, tenant, idempotency, audit, serta workflow yang sudah ada.

Belum diimplementasikan: pemilihan provider melalui settings, timeout jaringan nyata, retry provider, fallback orkestrasi berdasarkan error, pengukuran/log provider, semantic grounding lengkap `claim_map`, Pydantic schema tool untuk seluruh registry, integrasi ke call sites F1–F4, adapter Gemini, dan tes provider nyata. Implementasi ini tidak mengubah autentikasi, RBAC, tenant ownership, idempotency, audit, policy, atau status workflow.
