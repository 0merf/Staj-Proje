# SENTINEL — tüm bileşenleri doğru sırada başlatır ve DOĞRULAR.
#
# ⚠ SIRA ÖNEMLİ — keyfi değil, teknik zorunluluk:
#   1. Altyapı (Docker)  — diğer her şey buna bağlı
#   2. Alım worker'ı     — paylaşımlı bellek havuzunu O oluşturur (--owner)
#   3. Çıkarım worker'ı  — havuza BAĞLANIR, önce havuz var olmalı
#   4. API               — sonuç akışını dinler, panele yayınlar
#   5. (opsiyonel) React geliştirme sunucusu
#
# Bu betik kör beklemek yerine her adımı DOĞRULAR: bir bileşen
# gerçekten ayağa kalkmadan sonrakine geçmez. Böylece "başlattım ama
# çalışmıyor" durumu sessiz kalmaz.
#
# Kullanım:
#   pwsh backend/scripts/start_all.ps1
#   pwsh backend/scripts/start_all.ps1 -Cameras 5    # yalnızca ilk 5 kamera
#   pwsh backend/scripts/start_all.ps1 -Dev          # React dev sunucusu da açılsın
#   pwsh backend/scripts/stop_all.ps1                # durdurmak için

param(
    [int]$Cameras = 0,          # 0 = tümü
    [int]$BatchSize = 8,
    [switch]$SkipDocker,
    [switch]$Dev                # React geliştirme sunucusunu da başlat
)

$ErrorActionPreference = "Continue"
$root    = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$backend = Join-Path $root "backend"
$logs    = Join-Path $env:TEMP "sentinel"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Start-Component {
    param([string]$Name, [string]$Exe, [string[]]$ArgList, [string]$Cwd)
    $out = Join-Path $logs "$Name.log"
    $err = Join-Path $logs "$Name.err"
    Start-Process -FilePath $Exe -ArgumentList $ArgList `
        -WorkingDirectory $Cwd -WindowStyle Hidden `
        -RedirectStandardOutput $out -RedirectStandardError $err | Out-Null
}

# Bir adres cevap verene kadar bekler. Kör Start-Sleep yerine bunu
# kullanıyoruz: model yükleme bazen 10 sn, bazen 40 sn sürüyor.
function Wait-Url {
    param([string]$Url, [int]$TimeoutSec = 90, [string]$Label, [string]$LogName)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
                $secs = [int]($TimeoutSec - ($deadline - (Get-Date)).TotalSeconds)
                Write-Host ("  ✓ {0} hazır ({1} sn)" -f $Label, $secs) -ForegroundColor Green
                return $true
            }
        } catch { Start-Sleep -Milliseconds 1500 }
    }
    $file = if ($LogName) { $LogName } else { $Label }
    Write-Host ("  ✗ {0} YANIT VERMEDİ" -f $Label) -ForegroundColor Red
    Write-Host ("    log: {0}\{1}.err" -f $logs, $file) -ForegroundColor Red
    $errPath = Join-Path $logs "$file.err"
    if (Test-Path $errPath) {
        Get-Content $errPath -Tail 4 | ForEach-Object { Write-Host ("    | " + $_) -ForegroundColor DarkGray }
    }
    return $false
}

Write-Host ""
Write-Host "SENTINEL başlatılıyor" -ForegroundColor Cyan
Write-Host "═════════════════════"

# ─── 1. Altyapı ───────────────────────────────────────────────
if (-not $SkipDocker) {
    Write-Host "`n[1/5] Docker altyapısı (Valkey, PostgreSQL, MediaMTX, Prometheus, Grafana)"
    Push-Location $root
    docker compose up -d | Out-Null
    Pop-Location
    $up = (docker compose --project-directory $root ps --format "{{.Service}}" | Measure-Object).Count
    Write-Host "  ✓ $up servis ayakta" -ForegroundColor Green
} else {
    Write-Host "`n[1/5] Docker atlandı (-SkipDocker)"
}

# ─── 2. Alım worker'ı (havuz sahibi) ─────────────────────────
Write-Host "`n[2/5] Alım worker'ı — paylaşımlı bellek havuzunu O oluşturur"
$ingest = @("run", "python", "-m", "sentinel.ingest.worker", "--owner",
            "--metrics-port", "9101", "--stats-interval", "300")
if ($Cameras -gt 0) {
    $names = 1..$Cameras | ForEach-Object { "cam-{0:d2}" -f $_ }
    $ingest += @("--cameras") + $names
} else {
    $ingest += "--all"
}
Start-Component -Name "ingest" -Exe "uv" -ArgList $ingest -Cwd $backend
if (-not (Wait-Url -Url "http://127.0.0.1:9101/metrics" -Label "alım worker'ı" -LogName "ingest" -TimeoutSec 90)) {
    Write-Host "`nAlım worker'ı açılmadı — sonraki adımlar anlamsız. Durduruldu." -ForegroundColor Red
    exit 1
}

# ─── 3. Çıkarım worker'ı ─────────────────────────────────────
Write-Host "`n[3/5] GPU çıkarım worker'ı (TEK KOPYA — VRAM için zorunlu)"
Start-Component -Name "inference" -Exe "uv" -ArgList @(
    "run", "python", "-m", "sentinel.inference.worker",
    "--batch-size", "$BatchSize", "--stats-interval", "300"
) -Cwd $backend
# Model yükleme + ısınma: soğuk başlangıçta 40 sn'yi bulabiliyor.
Wait-Url -Url "http://127.0.0.1:9110/metrics" -Label "çıkarım worker'ı" -LogName "inference" -TimeoutSec 120 | Out-Null

# ─── 4. API ───────────────────────────────────────────────────
Write-Host "`n[4/5] API + panel"
Start-Component -Name "api" -Exe "uv" -ArgList @(
    "run", "uvicorn", "sentinel.api.main:app", "--host", "127.0.0.1", "--port", "8001"
) -Cwd $backend
Wait-Url -Url "http://127.0.0.1:8001/api/v1/system/live" -Label "API" -LogName "api" -TimeoutSec 60 | Out-Null

# ─── 5. React geliştirme sunucusu (opsiyonel) ────────────────
if ($Dev) {
    Write-Host "`n[5/5] React geliştirme sunucusu"
    $frontend = Join-Path $root "frontend"
    if (Test-Path (Join-Path $frontend "node_modules")) {
        Start-Component -Name "vite" -Exe "npm" -ArgList @("run", "dev") -Cwd $frontend
        Wait-Url -Url "http://127.0.0.1:5173/" -Label "Vite" -LogName "vite" -TimeoutSec 60 | Out-Null
    } else {
        Write-Host "  ! node_modules yok — önce: cd frontend; npm install" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n[5/5] React dev sunucusu atlandı (-Dev ile açılır)"
    Write-Host "      Derlenmiş arayüz zaten http://127.0.0.1:8001/app adresinde"
}

Write-Host ""
Write-Host "─────────────────────────────────────────────" -ForegroundColor Cyan
Write-Host "  React arayüz : http://127.0.0.1:8001/app"
if ($Dev) { Write-Host "  React (dev)  : http://127.0.0.1:5173" }
Write-Host "  Eski panel   : http://127.0.0.1:8001"
Write-Host "  Grafana      : http://127.0.0.1:3000"
Write-Host "  Loglar       : $logs"
Write-Host "  Durdur       : pwsh backend/scripts/stop_all.ps1"
Write-Host "─────────────────────────────────────────────" -ForegroundColor Cyan
Write-Host ""
