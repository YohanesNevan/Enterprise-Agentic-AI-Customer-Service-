# Start PostgreSQL, API, and the React workspace for local development.
param(
  [switch]$BackendOnly,
  [switch]$RunTests
)
$ErrorActionPreference = "Continue"

$root = (Get-Location).Path
$dockerCandidates = @(
  (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe"),
  (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin\docker.exe"),
  (Get-Command docker -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
)
$docker = $dockerCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

$desktopCandidates = @(
  (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
  (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\Docker Desktop.exe")
)
$desktop = $desktopCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "[ok] .env dibuat dari .env.example"
}
if (-not $docker -or -not (Test-Path $docker)) { throw "Docker Desktop belum terpasang. Pasang Docker Desktop lalu jalankan ulang." }
if (-not $desktop -or -not (Test-Path $desktop)) { throw "Docker Desktop tidak ditemukan di sistem." }

& $docker info --format "{{.ServerVersion}}" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Menyalakan Docker Desktop..."
  Start-Process -FilePath $desktop -WindowStyle Hidden | Out-Null
  $daemonReady = $false
  for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Seconds 2
    & $docker info --format "{{.ServerVersion}}" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $daemonReady = $true; break }
  }
  if (-not $daemonReady) { throw "Docker Engine belum siap. Buka Docker Desktop, tunggu sampai Running, lalu ulangi." }
}

python -c "import psycopg" 2>$null
if ($LASTEXITCODE -ne 0) { throw "Driver PostgreSQL belum terpasang. Jalankan: python -m pip install -r requirements.txt" }

Write-Host "Menyalakan PostgreSQL..."
& $docker compose up -d postgres
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL gagal dinyalakan lewat Docker Compose." }
$dbReady = $false
for ($i = 0; $i -lt 45; $i++) {
  $containerId = (& $docker compose ps --status running -q postgres).Trim()
  if ($containerId) {
    & $docker exec $containerId pg_isready -U eaics -d eaics 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $dbReady = $true; break }
  }
  Start-Sleep -Seconds 2
}
if (-not $dbReady) { throw "PostgreSQL belum siap menerima koneksi pada port 5432." }
Write-Host "[ok] PostgreSQL siap"

if ($RunTests) {
  Write-Host "Menjalankan tes backend..."
  python -m pytest tests/ -q
  if ($LASTEXITCODE -ne 0) { throw "Tes backend gagal." }
}

Write-Host "Menjalankan API pada port 8000..."
$logOut = Join-Path $root "api-local.log"
$logErr = Join-Path $root "api-local-error.log"
$be = Start-Process -FilePath "python" -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $root -RedirectStandardOutput $logOut -RedirectStandardError $logErr -WindowStyle Hidden -PassThru
$apiReady = $false
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 2
  Write-Host -NoNewline "."
  try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/readyz" -TimeoutSec 3
    if (($health.api -eq "up" -and $health.db -eq "up") -or $health.status -eq "ok") { $apiReady = $true; break }
  } catch { }
  if ($be.HasExited) {
    Write-Host ""
    if (Test-Path $logErr) { Get-Content $logErr | Select-Object -Last 20 | Write-Host }
    throw "API berhenti saat startup. Cek port 8000 atau DATABASE_URL."
  }
}
Write-Host ""
if (-not $apiReady) {
  if (Test-Path $logErr) { Get-Content $logErr | Select-Object -Last 20 | Write-Host }
  Stop-Process -Id $be.Id -Force -ErrorAction SilentlyContinue
  throw "API atau database tidak siap dalam 60 detik."
}
Write-Host "[ok] API terhubung ke PostgreSQL (PID $($be.Id))"
if ($BackendOnly) { exit 0 }

Write-Host "Menjalankan frontend pada port 5173..."
$web = Join-Path $root "web-workspace"
$npm = (Get-Command npm.cmd -ErrorAction Stop).Source
$feLogOut = Join-Path $root "frontend-local.log"
$feLogErr = Join-Path $root "frontend-local-error.log"
$fe = Start-Process -FilePath $npm -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") -WorkingDirectory $web -RedirectStandardOutput $feLogOut -RedirectStandardError $feLogErr -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 2
Write-Host "[ok] UI http://127.0.0.1:5173 | API http://127.0.0.1:8000/docs"
Write-Host "Proses API PID $($be.Id), frontend PID $($fe.Id). Data Postgres disimpan di volume Docker capstoneproject_pgdata."
