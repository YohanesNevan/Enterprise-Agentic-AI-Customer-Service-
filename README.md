# EAICS — Produk Bersama A+B (FRD/TRD compliant)

Target: TRD §14.5 Minggu 1-5, profil LOCAL. Stack: FastAPI + Postgres/pgvector + Redis + MinIO.

## Struktur (ADR-01 monolit modular)
- `app/core/`: ids (§16.1), audit (§16.7), errors (§16.6), rbac (FRD §4.2), correlation (FR-SEC-005), masking
- `app/contracts/vocabularies.py`: §16.2 V-1..V-18 frozen
- `app/modules/`: `cases.py` (FR-CASE), `evidence.py` (FR-EV), `handoff.py` (§16.4), `sla_engine.py` (ADR-12), `escalation.py`, `approvals.py` (RBAC-02 + hash), `qa.py`, `analytics_copilot.py`
- `app/main.py`: tool B untuk A — `create_crm_ticket`, `create_case`, `evidence_request`, `sla_calculate`, `handoff_request`, `notification_send`
- `synthetic/run.py`: SD-02 seed deterministik + checksum
- `tests/test_b_skeleton.py`: 6 uji E2E-11/12 + kontrak
oke
## Aturan FRD/TRD yang ditegakkan di kode
- BR-CASE-09: AI usul HIGH/CRITICAL → `severity_confirmed=null`
- BR-CASE-05: close ditolak + sebutkan butir kurang
- BR-EV-01: deskripsi bukti generik → E_VALIDATION
- BR-HO-01/06: paket tak lengkap tetap jalan + `package_complete=false` + defect audit
- RBAC-02: self-approval diblokir; BR-ORC-07: hash argumen dicek
- SLA jam kerja Asia/Jakarta, Jumat 16:30 → Senin (US-SLA-01)
- Audit append-only + hash-chain, trail per correlation_id (US-SEC-01)

## Jalankan (Windows PowerShell)

Profil LOCAL memakai PostgreSQL melalui Docker Compose (TRD §14.5 Minggu 1-5):
```powershell
Copy-Item .env.example .env          # sekali saja
python -m pip install -r requirements.txt
docker compose up -d postgres
python -m pytest tests/ -v           # 11 uji hijau (E2E-11/12 + kontrak §16)
python scripts/smoke_e2e.py          # verifikasi 6 aturan FRD/TRD
python -m uvicorn app.main:app --port 8000
# atau sekali jalan backend+frontend:
.\start-local.ps1
```
- OpenAPI: http://localhost:8000/docs — protected API calls require a signed bearer token from the configured trusted issuer. `X-Role`, `X-Actor-Id`, and `X-Assurance` are not credentials. No interactive login/issuer is included in this repository; configure the trusted issuer and signing keys before using protected routes.
- Frontend workspace (TRD §4.13): `cd web-workspace; npm install; npm run dev` → http://localhost:5173 (proxy `/v1` ke `:8000`).
- Data sintetis SD-02: `python synthetic/run.py --seed 42` (checksum stabil).

Profil Docker penuh (Postgres/pgvector + Redis + MinIO + Mailpit, TRD §5):
```powershell
pip install -r requirements-full.txt  # bila perlu ML/observability di host
docker compose up -d --build          # postgres, redis, minio, mailpit + api :8000
docker compose logs -f api
```
`DATABASE_URL` di `.env` otomatis dipakai. PostgreSQL wajib aktif; aplikasi berhenti dengan pesan koneksi yang jelas bila database tidak tersedia. SQLite hanya dipakai oleh rangkaian tes yang mengatur URL sendiri.

## Deploy demo cloud
Panduan profil cloud Docker Compose dengan HTTPS, akses demo bersandi, dan database privat: [DEPLOY_CLOUD.md](DEPLOY_CLOUD.md). Profil ini ditujukan untuk data sintetis sesuai FRD/TRD.

Frontend juga dapat dipublikasikan terpisah di Vercel; API dan PostgreSQL tetap harus di-host terpisah agar fitur bekerja. Lihat [web-workspace/VERCEL_DEPLOY.md](web-workspace/VERCEL_DEPLOY.md).

## Troubleshooting 404
- URL yang benar: backend `http://localhost:8000/` (landing info), `http://localhost:8000/docs`, `http://localhost:8000/healthz`;
  UI workspace `http://localhost:5173/`. The current development UI still needs the planned authenticated client integration before it can call protected API routes.
- UI menampilkan `404 ...`: pastikan backend `:8000` sudah jalan — proxy Vite (`vite.config.js`) meneruskan `/v1` dan `/internal` ke `:8000`.
- `npm run dev` langsung exit: gunakan script `dev` bawaan (`vite --port 5173`); flag CLI tak dikenal membuat Vite menolak start.
- Port dipakai: `netstat -ano | findstr "8000 5173"` lalu hentikan proses lama.

## Next (sesuai TRD §14.5)
- Minggu 6-7: antrean prioritas + workspace React + OTP/Auth read-model (butuh A)
- Minggu 8-9: SLA tick Beat + outbox CRM worker + approval UI
- Minggu 11-13: QA sampling penuh + eval + dasbor driver-tree 2 tingkat
