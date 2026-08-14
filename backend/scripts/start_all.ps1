# SENTINEL — tüm bileşenleri doğru sırada başlatır.
#
# ⚠ SIRA ÖNEMLİ
#   1. Altyapı (Docker) — diğer her şey buna bağlı
#   2. Alım worker'ı    — paylaşımlı bellek havuzunu O oluşturur (--owner)
#   3. Çıkarım worker'ı — havuza BAĞLANIR, önce havuz var olmalı
#   4. API              — WebSocket yayıncısı sonuç akışını dinler
#
# Worker'lar SÜRESİZ çalışır. Test için süre sınırı istiyorsan
# doğrudan `--duration N` ile elle başlat.
#
# Kullanım:
#   pwsh backend/scripts/start_all.ps1
#   pwsh backend/scripts/start_all.ps1 -Cameras 5     # ilk 5 kamera
#   pwsh backend/scripts/stop_all.ps1                 # durdurmak için

param(
    [int]$Cameras = 0,          # 0 = tümü
    [int]$BatchSize = 8,
    [switch]$SkipDocker
)

$ErrorActionPreference = "Continue"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$backend = Join-Path $root "backend"
$logs = Join-Path $env:TEMP "sentinel"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Start-Component {
    param([string]$Name, [string[]]$ArgList)
    $out = Join-Path $logs "$Name.log"
    $err = Join-Path $logs "$Name.err"
    Start-Process -FilePath "py" -ArgumentList (@("-3.13", "-m", "uv", "run") + $ArgList) `
        -WorkingDirectory $backend -WindowStyle Hidden `
        -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
    Write-Host ("  başlatıldı  {0,-12} log: {1}" -f $Name, $out)
}

# ─── 1. Altyapı ───────────────────────────────────────────────
if (-not $SkipDocker) {
    Write-Host "`n[1/4] Docker altyapısı"
    Push-Location $root
    docker compose up -d | Out-Null
    Pop-Location
    $up = (docker compose --project-directory $root ps --format "{{.Service}}" 2>$null | Measure-Object).Count
    Write-Host "  $up servis ayakta"
}

# ─── 2. Alım worker'ı (havuz sahibi) ─────────────────────────
Write-Host "`n[2/4] Alım worker'ı (paylaşımlı bellek havuzunu oluşturur)"
$ingest = @("python", "-m", "sentinel.ingest.worker", "--owner",
            "--metrics-port", "9101", "--stats-interval", "60")
if ($Cameras -gt 0) {
    $names = 1..$Cameras | ForEach-Object { "cam-{0:d2}" -f $_ }
    $ingest += @("--cameras") + $names
} else {
    $ingest += "--all"
}
Start-Component -Name "ingest" -ArgList $ingest
Start-Sleep -Seconds 8

# ─── 3. Çıkarım worker'ı ─────────────────────────────────────
Write-Host "`n[3/4] GPU çıkarım worker'ı (TEK KOPYA — VRAM için)"
Start-Component -Name "inference" -ArgList @(
    "python", "-m", "sentinel.inference.worker",
    "--batch-size", "$BatchSize", "--stats-interval", "60"
)
Start-Sleep -Seconds 15   # model yükleme + ısınma

# ─── 4. API ───────────────────────────────────────────────────
Write-Host "`n[4/4] API + panel"
Start-Component -Name "api" -ArgList @(
    "uvicorn", "sentinel.api.main:app", "--host", "127.0.0.1", "--port", "8001"
)
Start-Sleep -Seconds 8

Write-Host "`n─────────────────────────────────────────────"
Write-Host "  Panel   : http://127.0.0.1:8001"
Write-Host "  Grafana : http://127.0.0.1:3000"
Write-Host "  Loglar  : $logs"
Write-Host "  Durdur  : pwsh backend/scripts/stop_all.ps1"
Write-Host "─────────────────────────────────────────────`n"
