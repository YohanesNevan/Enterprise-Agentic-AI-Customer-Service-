# EAICS — Enterprise Agentic AI Customer Service

EAICS adalah aplikasi layanan pelanggan berbantuan AI untuk data sintetis. Proyek menggunakan backend FastAPI, database PostgreSQL, dan frontend React/Vite. Integrasi seperti LLM, core banking, CRM, notifikasi, dan kanal eksternal dapat berupa stub atau simulator; jangan gunakan data pelanggan nyata atau menganggap semua integrasi aktif.

## Isi repository

- `app/` — API FastAPI, otorisasi, layanan domain, dan persistence.
- `web-workspace/` — aplikasi web React/Vite.
- `tests/` — tes backend dan frontend.
- `context/` — arsitektur, spesifikasi unit, keputusan, dan status implementasi.
- `docker-compose.yml` — PostgreSQL dan layanan pendukung; juga menyediakan opsi API dalam container.

## Prasyarat

Untuk cara lokal yang direkomendasikan:

- Docker Desktop dengan Docker Engine berstatus **Running**.
- Python 3.12 atau lebih baru.
- Node.js versi LTS dan npm.
- Git.

Docker menjalankan database, sedangkan cara lokal menjalankan API dengan Python dan UI dengan Node.js. Jika hanya ingin menjalankan API di Docker, lihat bagian [Menjalankan API di Docker](#menjalankan-api-di-docker).

## Menjalankan secara lokal di Windows

Jalankan perintah berikut di PowerShell dari folder root repository:

```powershell
cd D:\CapstoneProjec_v3

# Buat konfigurasi lokal jika belum ada. Jangan commit file .env.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# Siapkan environment Python dan dependensi backend.
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Pasang dependensi frontend.
Set-Location web-workspace
npm install
Set-Location ..

# Jalankan PostgreSQL. Perintah ini membuat container/volume proyek bila belum ada.
docker compose up -d postgres

# Jalankan PostgreSQL, API, dan frontend.
.\start-local.ps1
```

Skrip `start-local.ps1` akan memastikan Docker dan PostgreSQL siap, lalu menjalankan API di port `8000` dan frontend di port `5173`. Skrip mengandalkan dependensi Python dan frontend sudah terpasang.

Buka:

- Frontend: <http://127.0.0.1:5173>
- Dokumentasi API: <http://127.0.0.1:8000/docs>
- Status API/database: <http://127.0.0.1:8000/readyz>

Skrip start membuat proses API dan frontend di latar belakang. PID proses ditampilkan di terminal dan log tersedia di `api-local.log`, `api-local-error.log`, `frontend-local.log`, serta `frontend-local-error.log`. Untuk menghentikan proses lokal, hentikan PID yang ditampilkan setelah memastikan PID tersebut memang milik EAICS. PostgreSQL dapat dihentikan dengan:

```powershell
docker compose stop postgres
```

Perintah tersebut menghentikan container, tetapi tidak menghapus data database.

## Menjalankan API di Docker

Alternatif ini menjalankan PostgreSQL, Redis, MinIO, Mailpit, API, dan simulator CRM melalui Compose. Frontend tetap dijalankan di komputer host, sehingga Node.js/npm tetap diperlukan.

Pastikan `.env` sudah dibuat seperti langkah lokal, lalu:

```powershell
cd D:\CapstoneProjec_v3
docker compose up -d --build
docker compose ps
docker compose logs -f api
```

Di terminal PowerShell kedua, jalankan frontend:

```powershell
cd D:\CapstoneProjec_v3\web-workspace
npm install
npm run dev
```

Buka <http://127.0.0.1:5173>. Vite meneruskan request API ke port `8000`.

Pilih **satu cara untuk menjalankan API**: `start-local.ps1` atau service `api` di Docker Compose. Jangan jalankan keduanya bersamaan karena sama-sama memakai port `8000`. Untuk menghentikan layanan Compose tanpa menghapus volume:

```powershell
docker compose down
```

`docker compose down` mempertahankan volume database. Jangan tambahkan `-v` kecuali memang ingin menghapus data database dan volume terkait.

## Konfigurasi lokal dan login development

- `.env.example` adalah template; `.env` adalah konfigurasi pribadi/mesin lokal dan tidak boleh dimasukkan ke Git.
- Ganti placeholder `JWT_SIGNING_KEY` dengan nilai acak minimal 32 karakter. Jangan gunakan kunci contoh atau membagikan secret lewat chat, screenshot, issue, atau commit.
- Provider LLM default adalah `stub`. Gemini hanya digunakan jika dipilih secara eksplisit dan konfigurasi/kredensial provider yang sesuai tersedia.
- Login development pelanggan dan staf **nonaktif secara default**. Jika dibutuhkan untuk menguji halaman terlindungi, aktifkan hanya di lingkungan lokal `ENVIRONMENT=development`, isi akun development sesuai template, dan aktifkan flag UI terkait di `web-workspace/.env.local` (salin dari `web-workspace/.env.example` terlebih dahulu).
- Jangan aktifkan login development pada deployment bersama/produksi. Jangan menaruh API key atau password di source code, README, atau konfigurasi yang di-commit.
- Gunakan data sintetis saja.

Token/role dari browser bukan pengganti autentikasi backend. Endpoint terlindungi membutuhkan bearer token yang valid; memilih role di UI tidak memberikan hak akses.

## Menjalankan verifikasi

Backend, dari root dengan virtual environment aktif:

```powershell
python -m pytest -q -p no:cacheprovider
```

Frontend:

```powershell
Set-Location web-workspace
npm run test:workspace
npm run build
```

Laporkan hasil perintah yang benar-benar dijalankan; keberhasilan build tidak membuktikan alur browser atau integrasi eksternal telah diuji.

## Troubleshooting

### Port PostgreSQL `5432` sudah digunakan

PostgreSQL EAICS memetakan port host `5432`. Periksa container yang menggunakannya:

```powershell
docker ps --filter "publish=5432" --format "table {{.Names}}\t{{.Ports}}"
```

Jika container dari proyek lain sedang memakai port tersebut, jangan hentikan atau hapus sebelum memastikan proyek itu tidak sedang digunakan. Dua database tidak dapat menerbitkan port host `5432` secara bersamaan. Pilih menghentikan sementara database proyek lain atau mengatur port berbeda secara konsisten pada Compose dan `DATABASE_URL`.

### API gagal terhubung ke PostgreSQL

Periksa status dan log database:

```powershell
docker compose ps postgres
docker compose logs --tail 100 postgres
Test-NetConnection 127.0.0.1 -Port 5432
```

Untuk cara lokal, `DATABASE_URL` di `.env` harus menunjuk ke database `eaics` pada `localhost:5432` dengan kredensial yang sesuai dengan service `postgres` di `docker-compose.yml`. Jangan membagikan nilai `.env`; hapus atau sensor informasi kredensial sebelum membagikan log.

Detail startup API dapat dilihat di `api-local-error.log`. Jika API berjalan di Docker, gunakan `docker compose logs --tail 100 api`.

### Port API `8000` atau frontend `5173` sudah digunakan

Tutup proses EAICS lama yang memakai port tersebut atau hentikan service terkait sebelum menjalankan ulang. Jangan menghentikan PID yang belum dikenali.

### Docker CLI tidak dapat terhubung ke Engine

Buka Docker Desktop dan tunggu sampai status **Engine running**, lalu cek:

```powershell
docker info
```

## Data dan batasan keselamatan

Compose menyimpan data PostgreSQL pada volume `pgdata` dan data MinIO pada `miniodata`. `docker compose down` menghentikan/menghapus container jaringan Compose tanpa menghapus volume. `docker compose down -v` menghapus volume juga dan dapat menghilangkan data lokal.

Gunakan layanan dan credential Compose hanya untuk development lokal dengan data sintetis. Sebelum deployment, tinjau konfigurasi keamanan, identitas, penyimpanan, migrasi database, dan provider eksternal.

## Dokumentasi tambahan

- [Rencana build dan unit implementasi](context/specs/00-build-plan.md)
- [Progress tracker](context/progress-tracker.md)
- [Traceability kebutuhan](context/requirements-traceability.md)
- [Panduan deployment cloud](DEPLOY_CLOUD.md)
- [Panduan deploy frontend ke Vercel](web-workspace/VERCEL_DEPLOY.md)
