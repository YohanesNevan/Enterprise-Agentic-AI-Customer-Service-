# EAICS Current Project Audit

**Tanggal:** 2026-10-20 (Asia/Jakarta)  
**Cakupan:** audit baca-saja repository, OpenAPI lokal, HTTP smoke, backend tests terisolasi, dan build frontend.  
**Batas:** tidak mengubah source aplikasi, dependency, migration, `.env`, atau konfigurasi. Tidak melakukan chat bisnis, transaksi, request Gemini, atau perubahan data produksi. Laporan lama tidak ditimpa.

## 1. Executive Summary

EAICS adalah modular monolith yang sudah berjalan secara lokal: React/Vite mengirim ke FastAPI melalui proxy, FastAPI menggunakan SQLAlchemy/PostgreSQL, dan terdapat modul conversation, intent, knowledge, policy/tool gateway, case/ticket, handoff, SLA, approval, QA, analytics, dan authentication.

- **PARTIAL:** customer chat menyimpan conversation, mengklasifikasi input secara deterministik, mengambil knowledge leksikal, menyimpan citations, dan membuat handoff queue. Customer complaint/case creation dan tracking UI/API belum end-to-end.
- **NOT IMPLEMENTED pada runtime chat:** Gemini adapter/contract ada, tetapi `orchestrator.run_turn()` tidak memanggilnya. Integrasi live Gemini **UNVERIFIED**; tidak ada request live.
- **PARTIAL:** tool gateway dan policy ada, tetapi sebagian executor adalah simulator dengan nilai hardcoded. Hasil simulator bukan bukti corebank, CRM, atau notification nyata.
- **PARTIAL:** bearer JWT, role/tenant/owner checks, dan tes regresi ada; issuer produksi tidak ada. OTP/consent/audit dan state workflow tertentu masih memory-only.
- **PARTIAL:** PostgreSQL lokal tersambung; Redis tidak aktif saat pemeriksaan. pgvector image tersedia tetapi vector search tidak ditemukan.
- **DONE:** UI/API/proxy health smoke HTTP semuanya 200. Vite build lulus (32 modul).
- **DONE untuk test profile deterministik:** 104 passed, 1 skipped, 99 warnings dengan DB sementara dan `LLM_PROVIDER=stub`. Live Gemini test dilewati.

**Kesimpulan:** stack lokal cocok untuk demo sintetis dengan batasan jelas, tetapi belum membuktikan agentic LLM, sistem enterprise integration, kesiapan production, atau seluruh customer/staff journeys. Langkah awal yang disarankan adalah spesifikasi aktif Unit 06 untuk complaint/case customer-owned; jangan memulai dari mengaktifkan Gemini.

## 2. Struktur dan arsitektur project aktual

| Area | Lokasi utama | Isi aktual |
|---|---|---|
| API entry | `app/main.py` | FastAPI B routes, middleware, startup `Base.metadata.create_all()`, registrasi route A. |
| Core | `app/core/` | DB/session, RBAC/JWT, dev auth, errors, correlation, masking, audit in-memory, IDs. |
| Routes/domain A | `app/modules/routes_a.py`, `app/modules/` | Conversation, identity simulation, intent, knowledge, orchestration, tool gateway, simulator, workflows. |
| Routes/domain B | `app/main.py`, `app/modules/` | Ticket/case, evidence, queue/handoff, SLA, approval, QA, analytics, outbox. |
| Models | `app/modules/models_a.py`, `models.py` | SQLAlchemy entities untuk conversation/knowledge/tools dan operations/case/ticket. |
| AI provider | `llm_provider.py`, `gemini_provider.py` | Pydantic F1–F4, deterministic fixture stub, provider factory, adapter Gemini terisolasi. |
| Frontend | `web-workspace/src/` | React 18, Vite 5, History API route map manual, fetch client, in-memory auth provider, CSS. |
| Tests | `tests/` | Pytest untuk auth, tenancy, chat, workflows, queue, provider fake. Frontend test framework tidak ada. |
| Ops | `docker-compose.yml`, `start-local.ps1`, `app/worker_*.py` | Compose Postgres/Redis/MinIO/Mailpit/API/simulator; worker scripts SLA/outbox. |

### Simulasi, placeholder, dan dokumentasi

- `corebank.py` dan `orchestrator._exec_tool()` menjalankan simulator/hardcoded result, bukan core banking.
- `notification_send` pada jalur orchestrator dapat menghasilkan `sent=True`; jawaban berpotensi menyatakan rekening koran terkirim tanpa provider delivery. Evidence upload-link mengembalikan `/v1/attachments`, tetapi route attachment/storage tidak ditemukan.
- Copilot suggestion lokal bukan Gemini. Beberapa operational UI menampilkan JSON mentah.
- `context/architecture.md`, `context/audit-report.md`, dan traceability menyimpan histori yang sudah superseded. Addendum 2026-10-16 menyatakan Gemini adapter sekarang ada tetapi tetap tidak dipanggil. Source terkini menjadi acuan.
- PDF yang diperiksa: FRD v0.9 draft (148 hlm), TRD v0.9 draft (87 hlm). TRD merujuk FRD v1.0 yang disahkan; salinan signed FRD v1.0 dan bukti approval TRD §16 tidak tersedia. Requirement di laporan ini adalah working baseline, bukan approval final.
- Alembic tidak memiliki `alembic/env.py`; `0001_init_b.py` menjalankan `metadata.create_all()` dan downgrade no-op. Ini bukan migration lifecycle yang terbukti siap rollout.
- pgvector hanya ada pada image Docker; vector column/index/query tidak ditemukan. Redis, MinIO, Mailpit tidak terhubung penuh ke alur produk.

## 3. Endpoint FastAPI beserta status implementasi

OpenAPI lokal: `EAICS-B` 0.3.0, 52 path. Route dictionary body banyak dipakai dan response model umumnya tidak didefinisikan. OpenAPI tidak menyertakan bearer `securitySchemes` atau deklarasi security global/operation meski route memakai auth dependency.

| Method | Path | Status | Catatan implementasi |
|---|---|---|---|
| GET | `/` | DONE | Service metadata. |
| GET | `/healthz` | DONE | Public liveness; HTTP 200 teruji. |
| GET | `/readyz` | PARTIAL | Cek DB, tetapi mensyaratkan `sla.read`; script start memanggil tanpa bearer. |
| POST | `/v1/dev-auth/customer/login` | PARTIAL | Fixed-account, loopback, development opt-in; bukan IdP produksi. |
| POST | `/v1/dev-auth/staff/login` | PARTIAL | Server allowlist, loopback, development opt-in; bukan staff lifecycle produksi. |
| POST | `/v1/auth/refresh` | PARTIAL | Redis one-time JTI rotation; Redis live tidak tersedia, test memakai mock. |
| POST | `/v1/channels/{channel}/inbound` | PARTIAL | Ingest dan principal/tenant; channel masih simulator. |
| POST | `/v1/chat/messages` | DONE (prototype scope) | Auth customer, validation, idempotency ledger, persist, orchestrator; tes tenant/history/handoff. LLM tidak dipanggil. |
| GET | `/v1/customer/conversations` | DONE (prototype scope) | Owner/tenant scoped cursor list; dites. |
| GET | `/v1/conversations/{conv_id}/read-model` | DONE (prototype scope) | Customer-safe read projection; tes ownership tersedia. |
| POST | `/v1/auth/identify` | PARTIAL | Simulasi: identifier non-kosong diperlakukan match; bukan directory verification nyata. |
| POST | `/v1/auth/challenge` | PARTIAL | Challenge/OTP disimpan in-memory; tidak ada delivery provider. |
| POST | `/v1/auth/verify` | PARTIAL | Mengubah assurance; challenge memory-only. |
| POST | `/v1/auth/consent` | PARTIAL | Consent memory-only, bukan durable record. |
| POST | `/v1/knowledge/articles` | PARTIAL | Create article; review/publish lifecycle penuh tidak ditemukan. |
| GET | `/v1/knowledge/search` | DONE (lexical prototype) | Filter tenant/status/access/dates dan citation; bukan vector RAG. |
| GET | `/v1/tools/registry` | PARTIAL | Registry statis, bukan external tool discovery. |
| POST | `/v1/tools/invoke` | PARTIAL | Policy + simulator tertentu; fallback tool lain `{ok:true}`, state idempotency memory. |
| GET, PATCH | `/v1/tickets/{tid}` | PARTIAL | GET projection scoped; PATCH menerima status bebas tanpa transition/schema kuat. |
| GET | `/v1/cases/{cid}` | PARTIAL | Status projection scoped; customer list/create journey belum lengkap. |
| POST | `/v1/evidence/upload-link` | NOT IMPLEMENTED (real storage) | Mengembalikan URL path placeholder, route upload tidak ada. |
| GET | `/v1/status/{reference}` | PARTIAL | Status minimal; lookup awal tidak memfilter tenant, collision perlu ditinjau. |
| POST | `/internal/sim-profile` | PARTIAL | Ubah simulator global in-memory, supervisor/admin only. |
| POST | `/v1/tickets` | PARTIAL | Ticket DB create; tes success/failure, belum customer UI end-to-end. |
| POST | `/v1/cases` | PARTIAL | Case DB create dan rule tests; customer journey belum ada. |
| POST | `/v1/cases/{case_id}/evidence-requests` | PARTIAL | Evidence metadata request, bukan file upload. |
| POST | `/v1/sla/calculate` | PARTIAL | Kalkulasi internal domain. |
| POST | `/v1/handoffs` | PARTIAL | Persist handoff; context package tidak lengkap. |
| POST | `/v1/notifications` | PARTIAL | Outbox/local status; provider delivery belum dibuktikan. |
| POST | `/v1/cases/{case_id}/close` | PARTIAL | Checklist/business rules, UI belum ada. |
| POST | `/v1/cases/{case_id}/reopen` | PARTIAL | Service/permission tersedia; UI journey parsial. |
| GET, POST | `/v1/approvals` | PARTIAL | Persisted approval/list; coverage dan UI parsial. |
| POST | `/v1/approvals/{aid}/decide` | PARTIAL | Decision/self-approval check; coverage selected. |
| GET | `/v1/analytics/operational` | PARTIAL | Tenant query, aggregate boundary perlu trace. |
| GET | `/v1/analytics/driver-tree` | PARTIAL | Aggregate DB report. |
| GET | `/v1/analytics/resolution` | PARTIAL | Aggregate DB report. |
| GET | `/v1/analytics/handoff` | PARTIAL | Aggregate DB report. |
| GET | `/v1/analytics/qa` | PARTIAL | Aggregate DB report. |
| GET | `/v1/analytics/export.csv` | PARTIAL | CSV export terproteksi; masking/retention belum E2E diverifikasi. |
| GET | `/v1/approvals/{aid}` | PARTIAL | Tenant-scoped record lookup. |
| POST | `/v1/qa/sample` | PARTIAL | Sampling tersedia; full criteria/consent trace perlu review. |
| POST | `/v1/qa/reviews` | PARTIAL | Persist review, UI subset. |
| POST | `/v1/qa/findings` | PARTIAL | Persist finding. |
| POST | `/v1/copilot/suggest` | PARTIAL | Deterministic/local suggestion, bukan LLM. |
| GET | `/v1/audit/trail/{correlation_id}` | PARTIAL | Reason/permission/tenant filter; underlying audit volatile memory. |
| POST | `/internal/sla-tick` | PARTIAL | Worker/service ada; deployment isolation belum diverifikasi. |
| GET | `/internal/outbox-status` | PARTIAL | Tenant query. |
| POST | `/internal/outbox-drain` | PARTIAL | Local drain, CRM delivery bukan live. |
| POST | `/v1/workspace/queue/enqueue` | PARTIAL | Queue persisted; body cukup longgar. |
| GET | `/v1/workspace/queue` | PARTIAL | Tenant-filtered; assignment-level access belum dimodelkan. |
| POST | `/v1/workspace/handoffs/{hid}/accept` | PARTIAL | Queue transition, service tests parsial. |
| POST | `/v1/workspace/handoffs/{hid}/transfer` | PARTIAL | Ada note/reason check; memakai `case.update`, mapping permission perlu konfirmasi. |
| GET | `/v1/workspace/conversations/{conv_id}` | PARTIAL | Read model menyebut dirinya stub; assignment scoping tidak ada. |

Endpoint tidak ditemukan: customer feedback submission (padahal role permission tersedia), customer complaint/case list/create terpisah lengkap, attachment upload, production account provisioning.

## 4. Status integrasi frontend–backend

- Vite mem-proxy `/v1`, `/internal`, `/healthz`, `/readyz` ke port 8000. `api.js` menggunakan bearer token; source tidak memakai caller role/actor headers.
- Dev customer/staff login tersambung jika flag frontend/backend sama-sama aktif. Access token hanya memori; refresh halaman menghilangkan sesi dan tidak ada refresh-token UI flow.
- `/customer/chat` mengirim idempotency key, memuat conversation/history, citation dan handoff state dari API; authenticated browser journey tidak dijalankan.
- Customer `/requests/new`, `/requests`, `/account`, staff `/complaints`, `/knowledge`, `/admin` adalah halaman placeholder, bukan workflow terhubung.
- Queue/conversation/case, supervisor approvals/SLA/audit, QA, analytics memiliki sebagian halaman API-connected; tidak ada frontend tests dan tidak diverifikasi browser di audit ini.
- Landing/starter prompts berupa konten statis; beberapa operational responses dirender sebagai JSON mentah. Tidak ditemukan UI feedback/case journey.
- Error network pada `fetch()` tidak selalu dinormalisasi menjadi `ApiError`; UX di beberapa komponen dapat berbeda ketika koneksi gagal.

## 5. Status integrasi Gemini

| Item | Status | Temuan |
|---|---|---|
| Provider abstraction | PARTIAL | Kontrak Pydantic F1–F4, `generate_validated`, safe typed errors, fixture stub. |
| Gemini adapter | PARTIAL | SDK Google Gen AI, JSON schema, bounded per-request timeout, retry satu attempt, safe error categories; fake-client tests. |
| Config/factory | PARTIAL | `LLM_PROVIDER` eksplisit, default stub di code; Gemini memerlukan key/model. Pemilihan provider bukan bukti chat menggunakannya. |
| Chat call-site | NOT IMPLEMENTED | Tidak ada factory/generate call di orchestrator. |
| Tool proposal safety | PARTIAL | F3 validator memeriksa allowlist/schema/args yang diberikan; belum terhubung. Jika dipasang harus `Gw.evaluate()` ulang sebelum executor. |
| Grounding | PARTIAL | F4 source ID/claim structural check, bukan semantic entailment; chat memakai jawaban deterministik/guardrail. |
| Timeout/quota | PARTIAL | Adapter mapping dites fake; tidak ada total call budget/deadline runtime, fallback call-site atau retry F4. 429 tidak membedakan quota/rate limit. |
| Live integration | UNVERIFIED | Tidak ada Gemini request/key test; live opt-in test dilewati. |
| Provider approval | UNVERIFIED | Signed FRD v1.0/TRD §16, minimisasi/region/retention/data processing/model-cost decisions belum terkonfirmasi. |

Adapter offline tidak membuktikan akses akun, live compatibility, latency, quota, ataupun kualitas generasi.

## 6. Database, Redis, autentikasi, dan session

| Area | Status | Temuan |
|---|---|---|
| PostgreSQL | DONE (local connection only) | Container lokal aktif pada sesi proyek sebelumnya; API berhasil start dan `/healthz` 200. Tidak ada operasi bisnis dijalankan. |
| Schema lifecycle | PARTIAL | `create_all()` saat import; Alembic env.py absent; migration tunggal create_all/no-op downgrade. |
| pgvector | NOT IMPLEMENTED | Tidak ada vector query/index/schema yang ditemukan. |
| Redis | UNVERIFIED/unavailable | Port 6379 tidak menerima koneksi; source hanya memakai Redis di refresh rotation. |
| JWT/RBAC | PARTIAL | HS256, issuer/audience/expiry/use checks, deny by default, role permission, service scope intersection. Production issuer/provisioning tidak ada. |
| Dev login | PARTIAL | Fixed customer dan staff allowlist opt-in loopback; tidak dicoba audit ini. |
| Session assurance | PARTIAL | `ChannelSession` DB; OTP challenge/consent state in-memory; tidak ada OTP delivery nyata. |
| Ownership/tenant | PARTIAL | Chat, read model, ticket/case penting memiliki owner/tenant filters; tenant schema tidak seragam dan assignment scope tidak ada. |
| Idempotency | PARTIAL | Customer chat ledger persistent; tool dedupe/circuit breaker memory-only. |
| Audit | PARTIAL | Hash chain/event in-memory, tidak durable atau transactionally coupled; hilang saat restart/multiworker berbeda. |

## 7. Fitur Agentic AI dan keamanan

| Kapabilitas | Status | Temuan aktual |
|---|---|---|
| Intent/refinement | PARTIAL | Rule/keyword closed taxonomy, thresholds, slots, sentiment, vulnerability; tidak ada F1 call. Context/repeat counters memory-only. |
| Clarification | PARTIAL | Template lokal dengan max options; tidak ada F2 call. |
| Tool registry | PARTIAL | Registry statis risk/AL metadata; lifecycle/schema per tool tidak lengkap. |
| Schema/semantic args | PARTIAL | Provider F3 validator ada; runtime args berasal dari hardcoded `_need_tool`; validasi semantic facts tidak ada. |
| Policy gateway | PARTIAL | Assurance, deny list, policy checks, audit hooks; executor simulator dan state idempotency/circuit volatile. |
| LLM access to DB | DONE (boundary only) | Provider contract tidak memegang DB/principal/executor; Gemini request tidak memasang SDK tools. Belum dipakai chat. |
| RAG/grounded response | PARTIAL | Lexical retrieval, filter published/current/access/tenant, citation version/body/score; no vector/indexing/section anchor. |
| Human handoff | PARTIAL | Handoff queue persisted dan state wording dibedakan; `package_complete=false`, workspace context belum lengkap. |
| Guardrails | PARTIAL | Injection, grounding, output policy, action-state checks. `action_state_check()` mendapat boolean `bool(tool_results)`, bukan bukti tool/result spesifik; hasil simulator `sent=True` berisiko diklaim sukses. |
| Audit/idempotency | PARTIAL | Customer chat idempotency persistent; audit dan tool ledger non-durable. |
| Real financial action | NOT IMPLEMENTED | Tidak ada transfer/reversal/refund real; aksi sensitif dilarang. Hasil data simulasi tidak boleh disebut sebagai data bank. |

## 8. Status UI/UX

- **PARTIAL:** route shell customer/staff terpisah, URL navigation, responsive CSS, loading/error/empty state dan sebagian keyboard behavior.
- **PARTIAL:** customer chat/history/citation/handoff ada; complaint, tracking, feedback, account management belum berfungsi.
- **PARTIAL:** staff/supervisor/QA/management pages sebagian tersambung API; beberapa role masih placeholder dan beberapa view mentah.
- **UNVERIFIED:** browser run pada sesi audit, authenticated journey, semua breakpoint, screen reader, WCAG AA penuh.
- Build frontend tidak membuktikan behavior/API page selain smoke GET.

## 9. Test dan build yang benar-benar dijalankan

| Pemeriksaan | Hasil |
|---|---|
| GET `http://127.0.0.1:5173/` | HTTP 200. |
| GET `http://127.0.0.1:8000/healthz` | HTTP 200. |
| GET `http://127.0.0.1:5173/healthz` | HTTP 200 melalui Vite proxy. |
| Pytest awal, DB sementara, dari root | **2 failed, 102 passed, 1 skipped, 99 warnings.** Error asli: `test_default_provider_is_fixture_stub_and_repeats_without_network` menerima `GeminiStructuredGenerationProvider` alih-alih `DeterministicStubProvider`; `test_stub_without_matching_fixture_fails_closed` menerima `CONNECTION_ERROR` alih-alih `NO_FIXTURE`. Tidak ada request Gemini. Runtime environment memengaruhi factory; isi `.env` tidak diperiksa. |
| Pytest dari temp CWD | **1 failed, 103 passed, 1 skipped, 99 warnings.** Error asli: `FileNotFoundError: app\\modules\\orchestrator.py` di `tests/test_llm_provider.py:261`, karena test membaca path relatif current directory. |
| Pytest final: `LLM_PROVIDER=stub`, `DATABASE_URL=sqlite:///` file unik `%TEMP%`, dari root | **104 passed, 1 skipped, 99 warnings** dalam 11.61s. Skip adalah `tests/test_gemini_live_opt_in.py`; tidak ada live request. DB PostgreSQL lokal tidak digunakan oleh test. Warnings: Starlette/httpx, AnyIO BlockingPortal, dan python-jose `datetime.utcnow()`. |
| `npm.cmd run build` dalam `web-workspace` | Lulus; Vite 5.4.21, 32 modules; JS 201.83 kB / gzip 61.22 kB. |
| GET `/openapi.json` | Berhasil; 52 path dibaca. Tidak ada bearer scheme/global security. |
| Redis TCP 127.0.0.1:6379 | Gagal konek (socket error 10035); Redis live tidak terverifikasi aktif. |
| Gemini live, authenticated browser, migration upgrade | Tidak dijalankan. Gemini opt-in dilewati; browser automation tidak tersedia; migration dapat mengubah schema. |

Vite build menghasilkan `web-workspace/dist/`. Tidak ada source/config/dependency/migration yang diubah.

## 10. Matriks FRD/TRD versus implementasi

| Requirement baseline | Aktual | Status |
|---|---|---|
| FRD §4.2 RBAC-01/02/03/05; TRD §7 | Principal, permission map, self-approval, admin separation, assurance/policy tools; role/assignment matrix belum semua dibuktikan. | PARTIAL |
| FR-AUTH-001..010; FRD §6.3 | JWT local dev, assurance simulation, OTP/consent memory, issuer/delivery produksi absent. | PARTIAL |
| FR-CONV-001/003/004/007; TRD §7 | Message/history/cursor/idempotency ada; attachment storage/UI incomplete. | PARTIAL |
| FR-INT-001..009; FRD §6.4 | Rule classifier, threshold, slots, sentiment, vulnerability; memory context dan no F1 integration. | PARTIAL |
| FR-KM-003/004; FRD §6.5 | Published/version/access/tenant filter, citations; lexical retrieval, lifecycle/vector/anchor incomplete. | PARTIAL |
| FR-ORC-001..009; TRD §8 | State path, policy, simulator, guardrail/handoff; no F1–F4 calls, runtime LLM budget/fallback absent. | PARTIAL |
| TRD §8 F1–F4, §8.2 | Contract + isolated adapter; no call site, live tests, or approved retry/budget integration. | PARTIAL |
| FR-TOOL-001..009; TRD §4.9 | Registry, policy decisions, simulator; schemas/integrations/durable idempotency incomplete. | PARTIAL |
| FR-WS-001..006; FRD §7.2 | Queue/accept/transfer APIs; handoff package `false`, assignment/read model/UI incomplete. | PARTIAL |
| FR-CASE-001..010 | Persisted B case/ticket and business rule tests; customer-owned complaint journey incomplete. | PARTIAL |
| FR-EV; TRD storage | Evidence request metadata; upload URL placeholder and no storage route. | PARTIAL |
| FR-SEC-004; TRD §16.7 | Correlated in-memory hash-chain audit; durable append-only audit absent. | PARTIAL |
| SLA/QA/approval/analytics requirements | Modules/API dan selected tests; complete role/provenance/UI review outstanding. | PARTIAL |
| TRD §14 runtime/migration | Local UI/API/Postgres; Redis/service adapters/migration lifecycle incomplete. | PARTIAL |
| Canonical approved FRD/TRD | FRD v0.9 draft vs TRD reference to FRD v1.0, signatures unavailable. | UNVERIFIED |

## 11. Bugs dan risiko

Tidak ada P0 yang terbukti. Prioritas menggambarkan dampak bila dipakai di luar demo lokal.

### P1

1. **Chat bukan Gemini/agentic runtime:** classifier/answer deterministik, provider adapter tidak dipanggil. File: `app/modules/orchestrator.py`, `llm_provider.py`, `gemini_provider.py`.
2. **Klaim simulator dapat terlihat sebagai delivery nyata:** statement `sent=True` lokal berpotensi menghasilkan pesan “terkirim”; corebank data juga sintetis. File: `app/modules/orchestrator.py`, `corebank.py`, `routes_a.py`.
3. **Complaint customer tidak menjadi case:** fallback chat tidak membuat case/ticket; UI requests placeholder. File: `orchestrator.py`, `routes_a.py`, `store.py`, `web-workspace/src/App.jsx`.
4. **Auth/audit/session state volatile:** OTP, consent, audit trail, intent context, tool idempotency/circuit hilang saat restart dan berbeda lintas worker. File: `auth.py`, `intent.py`, `tool_gateway.py`, `app/core/audit.py`.
5. **Migration tidak siap rollout:** startup `create_all`, `env.py` tidak ditemukan, satu migration no-op downgrade. File: `app/main.py`, `alembic/versions/0001_init_b.py`, `alembic.ini`.
6. **Identity/OTP simulasi:** identifier bukan verifikasi directory dan tidak ada OTP delivery; bukan autentikasi nasabah nyata. File: `app/modules/auth.py`, `routes_a.py`.

### P2

1. **Test provider dipengaruhi environment:** run awal dua provider test gagal sampai `LLM_PROVIDER=stub` dipastikan. File: `llm_provider.py`, `tests/test_llm_provider.py`, `app/core/db.py` dotenv loader.
2. **Local startup readiness mismatch:** `start-local.ps1` menunggu `/readyz` tanpa token; route mensyaratkan `sla.read`. Source-level finding, script tidak dieksekusi. File: `start-local.ps1`, `app/main.py`.
3. **OpenAPI auth/schema kurang ekspresif:** tidak mengiklankan bearer auth; body dict/response contracts lemah. File: `main.py`, `routes_a.py`, `rbac.py`.
4. **Redis tidak aktif:** refresh gagal-closed; access token/chat biasa tidak memerlukan Redis. File: `rbac.py`, `docker-compose.yml`.
5. **Evidence upload-link tidak punya target route/storage.** File: `routes_a.py`, `docker-compose.yml`.
6. **Tool idempotency/circuit memory-only lintas worker.** File: `tool_gateway.py`.
7. **Action-state check tidak mengikat klaim ke tool spesifik:** memakai `bool(tool_results)`. File: `orchestrator.py`, `guardrail.py`.
8. **Status reference perlu uji collision/uniqueness tenant:** query pertama tidak menyaring tenant. File: `routes_a.py`, `models.py`.

### P3

1. Customer request/account/complaint, knowledge, admin UI masih placeholder. File: `web-workspace/src/App.jsx`.
2. Tidak ada frontend test/E2E; accessibility dan authenticated UI journey belum diverifikasi. File: `web-workspace/package.json`, `App.jsx`, `app.css`.
3. Sebagian UI menampilkan JSON mentah/tidak memiliki layar khusus. File: `App.jsx`.
4. Catatan arsitektur/progress historis bertentangan; konsolidasi dokumen sebaiknya setelah laporan ini ditinjau. File: `context/architecture.md`, `audit-report.md`, `requirements-traceability.md`, `progress-tracker.md`.

## 12. Rekomendasi urutan pengerjaan

1. Tinjau laporan dan konfirmasi baseline FRD/TRD, simulasi vs live, privacy/data-processing, serta approval TRD §16.
2. Siapkan spesifikasi aktif Unit 06 (belum ditemukan di `context/specs/`) untuk customer-owned complaint/case: payload, idempotency, tenant/owner, customer-visible statuses, evidence, audit, error contract. Review sebelum coding.
3. Walking skeleton sintetis “transaksi gagal”: customer mengirim message → backend persist + idempotency → intent deterministik/clarification jika kurang → customer mengonfirmasi complaint fields → backend owner/policy check dan membuat case sintetis satu kali → UI menampilkan hanya case reference/status yang sudah commit → handoff manusia jika diperlukan. Tidak melakukan refund/reversal/transfer.
4. Lengkapi workspace handoff context dan assignment access; jalankan browser/API role matrix setelah spesifikasi disetujui.
5. Beri label/provenance simulator agar delivery dan saldo sintetis tidak tampak sebagai hasil enterprise nyata.
6. Setelah approval provider/privacy, integrasikan F1/F2/F4 bertahap; F3 hanya jika perlu, evaluasi policy ulang di gateway, runtime budget/deadline/fallback dan semantic grounding wajib lebih dulu. Live smoke hanya atas izin eksplisit dan data sintetis.
7. Tangani migration lifecycle sebagai unit khusus yang aman dan direview; jangan menjadikan `create_all()` deployment policy.

**Langkah pertama yang direkomendasikan:** tulis dan review spec aktif Unit 06 customer-owned complaint/case API/UI. Ini membuka skenario transaksi gagal end-to-end tanpa mengarang data atau mengklaim reversal; Gemini bukan dependency pertama karena saat ini tidak ada call site chat.

## Addendum pemeriksaan kontras Unit 05 (2026-10-20)

- Pemeriksaan ulang `web-workspace/src/app.css` dan `App.jsx` menemukan remediation kontras yang sudah dicatat pada audit Unit 05 masih ada di source aktif. Placeholder/counter memakai warna teks sekunder; fokus chat memakai warna gelap yang scoped ke chat; state disabled/sending mempunyai warna eksplisit. Tidak ada perubahan source aplikasi yang diperlukan.
- `npm.cmd run build` dijalankan ulang dari `web-workspace`: **PASS**, Vite 5.4.21, 32 modul, 769 ms. Tidak tersedia skrip tes frontend atau framework browser automation.
- Edge headless merender `/customer/chat` pada 1440×1000 dan menampilkan gate autentikasi. Tanpa sesi customer, komposer dan state fokus/loading/error tidak dapat diperiksa secara runtime. Tidak ada klaim uji keyboard, contrast sampling, atau browser console.
- Requirements traceability memetakan draft FRD §17.1 NFR-09 ke target desain WCAG 2.1 AA; signed FRD v1.0 belum tersedia. Angka rasio dalam audit kontras memakai WCAG 2.2 AA sebagai referensi teknis dan belum disetujui terpisah sebagai ambang proyek. Reviewer perlu mengonfirmasi baseline yang berlaku saat menilai bukti.
- Unit 05 tetap **IN PROGRESS; BLOCKED FOR CLOSURE** hingga state chat diperiksa secara runtime dan reviewer memberi disposisi. Unit 06 belum dimulai.

## 13. File kunci

- Requirement/spec: FRD/TRD PDF, `context/requirements-traceability.md`, `context/specs/00-build-plan.md`.
- Customer chat: `app/modules/routes_a.py`, `conversation.py`, `models_a.py`, `orchestrator.py`, `tests/test_customer_conversations.py`.
- Case/ticket: `app/modules/cases.py`, `store.py`, `models.py`, `app/main.py`, `tests/test_b_skeleton.py`.
- Frontend: `web-workspace/src/App.jsx`, `api.js`, `app.css`.
- Security/audit: `app/core/rbac.py`, `dev_auth.py`, `audit.py`, `app/modules/auth.py`, `tests/test_security_auth.py`.
- Provider (setelah approval): `app/modules/llm_provider.py`, `gemini_provider.py`, `tests/test_llm_provider.py`, `test_gemini_provider.py`, `test_gemini_live_opt_in.py`.
