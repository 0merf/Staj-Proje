# SENTINEL — tüm bileşenleri doğru sırada başlatır ve DOĞRULAR.
#
# ⚠ SIRA ÖNEMLİ — keyfi değil, teknik zorunluluk:
#   1. Altyapı (Docker)  — diğer her şey buna bağlı
#   2. Alım worker'ı     — paylaşımlı bellek havuzunu O oluşturur (--owner)
#   3. Çıkarım worker'ı  — havuza BAĞLANIR, önce havuz var olmalı
#   4. Analitik worker'ı — çıkarım sonuçlarından anomali/saldırganlık üretir
#   5. Alarm worker'ı    — olayları TimescaleDB'ye kalıcılaştırır
#   6. API               — sonuç akışını dinler, panele yayınlar
#   7. (opsiyonel) React geliştirme sunucusu
#
# ⚠ 30.08.2026 — ANALİTİK VE ALARM WORKER'LARI EKSİKTİ
# Bu betik 4 adımdı ve analitik worker'ını hiç başlatmıyordu. Sonuç:
# "başlattım" denen sistemde tespit ve takip çalışıyor ama HİÇBİR
# ANOMALİ ÜRETİLMİYORDU — panel kutuları çiziyor, alarm paneli sonsuza
# dek boş kalıyordu. Elle başlatıldığı için günlerce fark edilmedi.
#
# Mimari kural 0: belgelenen başlatma yolu sistemin TAMAMINI ayağa
# kaldırmalı. Kaldırmıyorsa belge yalan söylüyor demektir.
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

# ─── 0. KOPYA SÜREÇ ÖN KONTROLÜ ──────────────────────────────
#
# ⚠⚠ 09.09.2026 — BU KONTROL YOKTU VE İKİ GÜN KAYBETTİRDİ (P-58)
#
# Bu betik hiçbir şey sormadan yeni bir takım worker başlatıyordu.
# Zaten bir takım koşuyorsa sonuç: 40 RTSP akışı, İKİ KOPYA YOLO
# (mimari kural 3 ihlali — "modeller tek süreçte tek kopya"), ve iki
# `--owner` alım worker'ı aynı paylaşımlı bellek havuzu için yarışıyor.
#
# Belirti sinsi: sistem ÇALIŞIYOR görünüyor, yalnızca yavaş. RAM %98.7,
# gecikme iki katı. Suçlu iki gün boyunca modelde arandı.
#
# ⚠ CLAUDE.md bu tuzağı zaten yazıyordu — *"Her `uv run` 2 python.exe
# üretir; 2 normal, 4 = kopya var demektir."* Yazılı bir uyarı, otomatik
# bir kontrolün yerini tutmuyor.
#
# ⚠ NEDEN RSS FİLTRESİ: `uv run` bir rol için birden çok python.exe
# üretiyor (sarmalayıcılar + asıl süreç). Sarmalayıcılar ~5-25 MB,
# asıl süreçler 100 MB - 3 GB. Sarmalayıcıları saymak yanlış alarm
# üretirdi; `measure_canli.py` de aynı ölçütü kullanıyor.
function Test-KopyaSurec {
    $desenler = @{
        "alim"     = "sentinel.ingest.worker"
        "cikarim"  = "sentinel.inference.worker"
        "analitik" = "sentinel.analytics.worker"
        "alarm"    = "sentinel.alerting.worker"
    }
    $bulunan = @{}
    $surecler = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
    foreach ($p in $surecler) {
        if ($p.WorkingSetSize -lt 50MB) { continue }   # sarmalayıcı, asıl değil
        foreach ($rol in $desenler.Keys) {
            if ($p.CommandLine -and $p.CommandLine.Contains($desenler[$rol])) {
                if (-not $bulunan.ContainsKey($rol)) { $bulunan[$rol] = @() }
                $bulunan[$rol] += $p.ProcessId
            }
        }
    }
    return $bulunan
}

$mevcut = Test-KopyaSurec
if ($mevcut.Count -gt 0) {
    Write-Host ""
    Write-Host "⚠⚠ ZATEN ÇALIŞAN WORKER VAR — BAŞLATILMADI" -ForegroundColor Red
    Write-Host "═══════════════════════════════════════════" -ForegroundColor Red
    foreach ($rol in ($mevcut.Keys | Sort-Object)) {
        Write-Host ("   {0,-10} pid: {1}" -f $rol, ($mevcut[$rol] -join ", "))
    }
    Write-Host ""
    Write-Host "Üstüne ikinci takım başlatmak sistemi bozar (P-58):" -ForegroundColor Yellow
    Write-Host "  · iki kopya YOLO -> VRAM (mimari kural 3 ihlali)"
    Write-Host "  · iki --owner alım worker'ı aynı shm havuzu icin yarışır"
    Write-Host "  · sistem ÇALIŞIYOR görünür, sadece iki kat yavaş olur"
    Write-Host ""
    Write-Host "Önce durdurun:  pwsh backend/scripts/stop_all.ps1" -ForegroundColor Cyan
    exit 1
}

Write-Host ""
Write-Host "SENTINEL başlatılıyor" -ForegroundColor Cyan
Write-Host "═════════════════════"
Write-Host "  ✓ kopya süreç kontrolü temiz" -ForegroundColor Green

# ─── 1. Altyapı ───────────────────────────────────────────────
if (-not $SkipDocker) {
    Write-Host "`n[1/7] Docker altyapısı (Valkey, PostgreSQL, MediaMTX, Prometheus, Grafana)"
    Push-Location $root
    docker compose up -d | Out-Null
    Pop-Location
    $up = (docker compose --project-directory $root ps --format "{{.Service}}" | Measure-Object).Count
    Write-Host "  ✓ $up servis ayakta" -ForegroundColor Green
} else {
    Write-Host "`n[1/7] Docker atlandı (-SkipDocker)"
}

# ─── 2. Alım worker'ı (havuz sahibi) ─────────────────────────
# ⚠ 14.09.2026 — açılmayan bileşen olsa da betik ÇIKIŞ KODU 0 döndürüyordu.
# Temiz kopyada kurulum testinde çıkarım süreci çöktü (eksik paket) ama
# betik başarıyla bitti ve kurulum "SENTINEL çalışıyor" dedi. Devam etme
# davranışı korunuyor (hata ayıklarken diğer günlükler de oluşsun) ama sonda
# açılmayan varsa özet basılıp 1 ile çıkılıyor.
$acilmayan = @()

Write-Host "`n[2/7] Alım worker'ı — paylaşımlı bellek havuzunu O oluşturur"
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
Write-Host "`n[3/7] GPU çıkarım worker'ı (TEK KOPYA — VRAM için zorunlu)"
Start-Component -Name "inference" -Exe "uv" -ArgList @(
    "run", "python", "-m", "sentinel.inference.worker",
    "--batch-size", "$BatchSize", "--stats-interval", "300"
) -Cwd $backend
# Model yükleme + ısınma: soğuk başlangıçta 40 sn'yi bulabiliyor.
if (-not (Wait-Url -Url "http://127.0.0.1:9110/metrics" -Label "çıkarım worker'ı" -LogName "inference" -TimeoutSec 120)) {
    $acilmayan += "cikarim"
}

# ─── 4. Analitik worker'ı ────────────────────────────────────
# Çıkarım sonuçlarını okur, özellik pencerelerini besler, Katman A/B
# anomalilerini ve tırmanma skorunu üretir.
# ⚠ Çıkarım worker'ından SONRA: `inference.results` akışı olmadan
# tüketici grubu kuracak bir şey yok.
Write-Host "`n[4/7] Analitik worker'ı — anomali + saldırganlık"
Start-Component -Name "analytics" -Exe "uv" -ArgList @(
    "run", "python", "-m", "sentinel.analytics.worker", "--stats-interval", "300"
) -Cwd $backend
if (-not (Wait-Url -Url "http://127.0.0.1:9120/metrics" -Label "analitik worker'i" -LogName "analytics" -TimeoutSec 60)) {
    Write-Host "  ! analitik worker'i acilmadi — HIC ANOMALI URETILMEYECEK" -ForegroundColor Yellow
    $acilmayan += "analitik"
}

# ─── 5. Alarm worker'ı ───────────────────────────────────────
# Olayları TimescaleDB'ye yazar. ⚠ Bu bileşen olmadan sistem çalışır
# ama alarm GEÇMİŞİ tutulmaz: panel kapandığında olay kaybolur.
Write-Host "`n[5/7] Alarm worker'i — olaylari veritabanina yazar"
Start-Component -Name "alerting" -Exe "uv" -ArgList @(
    "run", "python", "-m", "sentinel.alerting.worker"
) -Cwd $backend
if (-not (Wait-Url -Url "http://127.0.0.1:9130/metrics" -Label "alarm worker'i" -LogName "alerting" -TimeoutSec 60)) {
    Write-Host "  ! alarm worker'i acilmadi — olaylar KALICI OLMAYACAK" -ForegroundColor Yellow
    $acilmayan += "alarm"
}

# ─── 6. API ───────────────────────────────────────────────────
Write-Host "`n[6/7] API + panel"
Start-Component -Name "api" -Exe "uv" -ArgList @(
    "run", "uvicorn", "sentinel.api.main:app", "--host", "127.0.0.1", "--port", "8001"
) -Cwd $backend
if (-not (Wait-Url -Url "http://127.0.0.1:8001/api/v1/system/live" -Label "API" -LogName "api" -TimeoutSec 60)) {
    $acilmayan += "api"
}

# ─── 5. React geliştirme sunucusu (opsiyonel) ────────────────
if ($Dev) {
    Write-Host "`n[7/7] React geliştirme sunucusu"
    $frontend = Join-Path $root "frontend"
    if (Test-Path (Join-Path $frontend "node_modules")) {
        Start-Component -Name "vite" -Exe "npm" -ArgList @("run", "dev") -Cwd $frontend
        Wait-Url -Url "http://127.0.0.1:5173/" -Label "Vite" -LogName "vite" -TimeoutSec 60 | Out-Null
    } else {
        Write-Host "  ! node_modules yok — önce: cd frontend; npm install" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n[7/7] React dev sunucusu atlandı (-Dev ile açılır)"
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

# ─── SON YOKLAMA ─────────────────────────────────────────────
# ⚠ 14.09.2026 — "hazır" kontrolü süreç ölçüm portunu açınca geçiyordu.
# Analitik süreci portu açıp 1 sn sonra model dosyasını okurken ÇÖKTÜ;
# betik "hazır" demişti. Bu yüzden her şey açıldıktan sonra bekleyip
# hepsi YENİDEN yoklanıyor: hâlâ cevap vermeyen, açılmamış sayılır.
Write-Host "`nSon yoklama (15 sn sonra, çöken süreç var mı)..."
Start-Sleep -Seconds 15
$yoklama = [ordered]@{ "alim" = 9101; "cikarim" = 9110; "analitik" = 9120; "alarm" = 9130 }
foreach ($ad in $yoklama.Keys) {
    try { $null = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}/metrics" -f $yoklama[$ad]) -TimeoutSec 3 -UseBasicParsing }
    catch { if ($acilmayan -notcontains $ad) { $acilmayan += $ad }; Write-Host ("  ✗ {0} başladıktan sonra DÜŞTÜ" -f $ad) -ForegroundColor Red }
}
try { $null = Invoke-WebRequest -Uri "http://127.0.0.1:8001/api/v1/system/live" -TimeoutSec 3 -UseBasicParsing }
catch { if ($acilmayan -notcontains "api") { $acilmayan += "api" }; Write-Host "  ✗ API başladıktan sonra DÜŞTÜ" -ForegroundColor Red }
if ($acilmayan.Count -eq 0) { Write-Host "  ✓ tüm süreçler hâlâ ayakta" -ForegroundColor Green }

if ($acilmayan.Count -gt 0) {
    Write-Host ("  ✗ ACILMAYAN BILESEN: {0}  (loglar: {1})" -f ($acilmayan -join ", "), $logs) -ForegroundColor Red
    exit 1
}
exit 0
