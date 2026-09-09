# =====================================================================
# demo-recover.ps1  --  tombol panik saat demo
#
# Pakai kalau SUMO nyangkut: "Koneksi SUMO terputus", tombol
# "Starting..." mentok, atau simulasi Digital Twin/Dashboard tidak
# jalan-jalan. Membunuh SEMUA proses SUMO + backend, lalu start backend
# lagi. Worker (scenario_worker.py) TIDAK disentuh -- restart sendiri di
# terminalnya kalau perlu.
#
# Setelah script selesai:
#   1. Refresh tab dashboard  (Ctrl+Shift+R)
#   2. Refresh tab digital twin
#   3. SUMO start ulang otomatis; kalau tidak, klik "Start Simulation"
#
# Pakai:
#   .\demo-recover.ps1
# =====================================================================

$ErrorActionPreference = "SilentlyContinue"
$repo = $PSScriptRoot

function Get-PortListeners($p) {
    try { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction Stop } catch { @() }
}

# Backend DULU -- selama backend hidup dia terus mencoba spawn SUMO baru,
# jadi kalau SUMO dibunuh duluan langsung muncul lagi.
Write-Host "[1/4] Bunuh backend (uvicorn) di port 8000 ..." -ForegroundColor Cyan
$conns = Get-PortListeners 8000
foreach ($c in $conns) {
    Write-Host "      kill $($c.OwningProcess)"
    Stop-Process -Id $c.OwningProcess -Force
}
if (-not $conns) { Write-Host "      (tidak ada)" }
Start-Sleep -Milliseconds 700

Write-Host "[2/4] Bunuh semua SUMO (2x sapuan) ..." -ForegroundColor Cyan
foreach ($pass in 1..2) {
    $sumo = Get-Process -Name "sumo", "sumo-gui" -ErrorAction SilentlyContinue
    $wrap = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -like "*sumo*" -and $_.Name -like "pythonw*"
    }
    $n = 0
    $sumo | ForEach-Object { Stop-Process -Id $_.Id -Force; $n++ }
    $wrap | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; $n++ }
    Write-Host "      sapuan $pass : $n proses"
    Start-Sleep -Milliseconds 500
}

Write-Host "[3/4] Verifikasi ..." -ForegroundColor Cyan
$stillSumo = Get-Process -Name "sumo", "sumo-gui" -ErrorAction SilentlyContinue
$stillPort = Get-PortListeners 8000
if ($stillSumo) { Write-Host "      PERINGATAN: masih ada SUMO -> $($stillSumo.Id -join ',')" -ForegroundColor Yellow }
else { Write-Host "      SUMO bersih." -ForegroundColor Green }
if ($stillPort) { Write-Host "      PERINGATAN: port 8000 masih dipakai." -ForegroundColor Yellow }
else { Write-Host "      port 8000 bebas." -ForegroundColor Green }

Write-Host "[4/4] Start backend ..." -ForegroundColor Cyan
$sumoHome = Join-Path $repo "venv\Lib\site-packages\sumo"
if (Test-Path $sumoHome) { $env:SUMO_HOME = $sumoHome }
Set-Location (Join-Path $repo "backend")
Write-Host ""
Write-Host ">>> Backend jalan. Sekarang: refresh tab browser (Ctrl+Shift+R) <<<" -ForegroundColor Green
Write-Host ""
& (Join-Path $repo "venv\Scripts\python.exe") -m uvicorn app.main:app --timeout-graceful-shutdown 10
