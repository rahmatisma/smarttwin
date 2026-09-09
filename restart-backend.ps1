# =====================================================================
# restart-backend.ps1
#
# Matiin backend + semua SUMO yang nyangkut, lalu (opsional) start lagi.
# Dipakai kalau Ctrl+C di terminal uvicorn tidak mempan -- itu terjadi
# karena handler shutdown FastAPI nunggu thread loop SUMO / soket TraCI
# yang lagi macet.
#
# Pakai:
#   .\restart-backend.ps1            # kill + start ulang backend
#   .\restart-backend.ps1 -KillOnly  # cuma kill, tidak start
#
# Setelah backend hidup lagi: buka dashboard, tekan "Start Simulation".
# =====================================================================

param(
    [switch]$KillOnly,
    [int]$Port = 8000
)

$ErrorActionPreference = "SilentlyContinue"
$repo = $PSScriptRoot

function Get-PortListeners($p) {
    try { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction Stop }
    catch { @() }
}

Write-Host "[1/3] Matiin proses di port $Port ..." -ForegroundColor Cyan
$conns = Get-PortListeners $Port
foreach ($c in $conns) {
    $procId = $c.OwningProcess
    $name = (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName
    Write-Host "      kill PID $procId ($name)"
    Stop-Process -Id $procId -Force
}
if (-not $conns) { Write-Host "      (tidak ada)" }

Write-Host "[2/3] Matiin SUMO yang tertinggal ..." -ForegroundColor Cyan
$sumo = Get-Process -Name "sumo", "sumo-gui" -ErrorAction SilentlyContinue
if ($sumo) {
    $sumo | ForEach-Object { Write-Host "      kill PID $($_.Id) ($($_.ProcessName))" }
    $sumo | Stop-Process -Force
} else {
    Write-Host "      (tidak ada)"
}

Start-Sleep -Milliseconds 700

# Verifikasi port sudah bebas
$still = Get-PortListeners $Port
if ($still) {
    Write-Host "PERINGATAN: port $Port masih dipakai PID $($still.OwningProcess)." -ForegroundColor Yellow
} else {
    Write-Host "      port $Port bebas." -ForegroundColor Green
}

if ($KillOnly) {
    Write-Host "[3/3] -KillOnly: selesai, backend tidak di-start." -ForegroundColor Cyan
    return
}

Write-Host "[3/3] Start backend ..." -ForegroundColor Cyan
Set-Location (Join-Path $repo "backend")

# --timeout-graceful-shutdown 10: kalau shutdown handler (stop SUMO) nyangkut,
# uvicorn tetap keluar paksa setelah 10 detik -- port 8000 selalu balik bebas.
& (Join-Path $repo "venv\Scripts\python.exe") -m uvicorn app.main:app --timeout-graceful-shutdown 10
