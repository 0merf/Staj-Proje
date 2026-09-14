# SENTINEL — yeni bir bilgisayarda TEK KOMUTLA kurulum ve başlatma.
#
# Kullanım (proje klasöründe, PowerShell):
#   powershell -ExecutionPolicy Bypass -File kurulum.ps1
#   powershell -ExecutionPolicy Bypass -File kurulum.ps1 -SadeceKontrol
#
# Ne yapar (her adım doğrulanır, bir adım başarısızsa DURUR):
#   1. Ön koşullar: Docker çalışıyor mu, uv var mı, NVIDIA GPU görünüyor mu
#   2. Çalışma için gereken dosyalar yerinde mi (modeller, kamera videoları,
#      öğrenilmiş profiller, derlenmiş panel)
#   3. .env yoksa .env.example'dan üretir; parolaları RASTGELE üretir
#   4. Python bağımlılıkları (uv sync)
#   5. Altyapı (Docker) + ilk yönetici kullanıcısı
#   6. Tüm süreçleri başlatır (backend/scripts/start_all.ps1)
#
# Tekrar çalıştırmak güvenlidir: var olan .env ve kullanıcıya dokunmaz.

param([switch]$SadeceKontrol)

# ⚠ "Stop" DEĞİL: PowerShell 5.1'de docker/uv gibi yerel programların stderr
# çıktısı "Stop" altında betiği SONLANDIRIYOR (uv sync ilerlemeyi stderr'e
# yazar). Her adım bunun yerine $LASTEXITCODE ile açıkça denetleniyor.
$ErrorActionPreference = "Continue"
$kok = $PSScriptRoot
Set-Location $kok

function Adim([string]$m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Tamam([string]$m) { Write-Host "   [tamam] $m" -ForegroundColor Green }
function Uyari([string]$m) { Write-Host "   [uyari] $m" -ForegroundColor Yellow }
function Dur([string]$m) { Write-Host "   [HATA] $m" -ForegroundColor Red; exit 1 }

# ─── 1. Ön koşullar ─────────────────────────────────────────────────────
Adim "1/6 On kosullar"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Dur "Docker bulunamadi. Docker Desktop kurun ve baslatin."
}
$null = docker info --format "{{.ServerVersion}}" 2>$null
if ($LASTEXITCODE -ne 0) { Dur "Docker kurulu ama calismiyor. Docker Desktop'i baslatin." }
Tamam "Docker calisiyor"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Dur ("uv bulunamadi. Kurmak icin: " +
         "powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`"")
}
Tamam "uv var"

if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $gpu = (nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1)
    Tamam "NVIDIA GPU: $gpu"
} else {
    Uyari "NVIDIA GPU gorunmuyor. Sistem GPU icin tasarlandi; GPU olmadan cok yavas calisir."
}

# ─── 2. Gerekli dosyalar ────────────────────────────────────────────────
Adim "2/6 Gerekli dosyalar"
$gerekli = @(
    "models\yolo26s.pt", "models\yolo26s-pose.pt", "models\yunet.onnx",
    "models\saldirganlik_lgbm.txt",
    "data\videos\manifest.json",
    "backend\src\sentinel\api\static\app\index.html"
)
1..20 | ForEach-Object { $gerekli += ("data\videos\cam-{0:D2}.mp4" -f $_) }
$eksik = @($gerekli | Where-Object { -not (Test-Path (Join-Path $kok $_)) })
if ($eksik.Count -gt 0) {
    Dur ("Eksik dosyalar:`n     " + ($eksik -join "`n     "))
}
Tamam "$($gerekli.Count) dosya yerinde"
$profil = @(Get-ChildItem (Join-Path $kok "data\profiles") -Filter "cam-*.json" -ErrorAction SilentlyContinue).Count
if ($profil -ge 20) { Tamam "ogrenilmis kamera profilleri: $profil" }
else { Uyari "ogrenilmis profil $profil/20 — anomali katmani ilk dakikalarda kendini isitacak" }

if ($SadeceKontrol) { Write-Host "`nKontrol tamam (-SadeceKontrol)." -ForegroundColor Green; exit 0 }

# ─── 3. .env ────────────────────────────────────────────────────────────
Adim "3/6 Ortam dosyasi (.env)"
$envYol = Join-Path $kok ".env"
if (Test-Path $envYol) {
    Tamam ".env zaten var, dokunulmadi"
} else {
    function Rastgele([int]$uzunluk) {
        $bayt = New-Object byte[] $uzunluk
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bayt)
        # Yalnız harf ve rakam: URL ve bağlantı dizelerinde kaçış gerektirmesin
        (([Convert]::ToBase64String($bayt)) -replace "[^A-Za-z0-9]", "").Substring(0, $uzunluk)
    }
    $metin = [IO.File]::ReadAllText((Join-Path $kok ".env.example"))
    $degis = @{
        "CHANGE_ME_strong_password_here"                   = (Rastgele 32)
        "CHANGE_ME_valkey_password"                        = (Rastgele 32)
        "CHANGE_ME_generate_with_secrets_token_urlsafe_64" = (Rastgele 64)
        "CHANGE_ME_grafana_password"                       = (Rastgele 24)
    }
    foreach ($k in $degis.Keys) { $metin = $metin.Replace($k, $degis[$k]) }
    [IO.File]::WriteAllText($envYol, $metin, (New-Object System.Text.UTF8Encoding($false)))
    Tamam ".env uretildi (parolalar rastgele)"
}

# İfade modeli ağırlığı: kütüphane ilk kullanımda internetten indiriyor.
# Pakette varsa önbelleğe kopyalanır; internet olmadan da çalışsın.
$emoKaynak = Join-Path $kok "models\emotieff_enet_b0_8_vgaf.onnx"
$emoHedefDizin = Join-Path $env:USERPROFILE ".emotiefflib"
$emoHedef = Join-Path $emoHedefDizin "enet_b0_8_best_vgaf.onnx"
if ((Test-Path $emoKaynak) -and -not (Test-Path $emoHedef)) {
    New-Item -ItemType Directory -Force -Path $emoHedefDizin | Out-Null
    Copy-Item $emoKaynak $emoHedef
    Tamam "ifade modeli agirligi onbellege kopyalandi"
}

# ─── 4. Python bağımlılıkları ───────────────────────────────────────────
Adim "4/6 Python bagimliliklari (ilk seferde birkac dakika surer)"
Push-Location (Join-Path $kok "backend")
# ⚠ `--extra gpu` ŞART: torch, ultralytics, onnxruntime-gpu, emotiefflib ve
# lightgbm bu ek grupta. İlk sürümde düz `uv sync` vardı; temiz kopyada
# yapılan kurulum testinde yalnız 95 temel paket kuruldu ve çıkarım süreci
# başlayamadı.
uv sync --extra gpu
$kod = $LASTEXITCODE
Pop-Location
if ($kod -ne 0) { Dur "uv sync basarisiz" }
Tamam "bagimliliklar kuruldu"
# "Kuruldu" demek GPU'yu gördüğü anlamına gelmiyor: yanlış torch yapısı
# (CPU-only) sessizce kurulabilir ve sistem çok yavaş çalışır.
Push-Location (Join-Path $kok "backend")
$cuda = (uv run python -c "import torch, ultralytics, onnxruntime, lightgbm, emotiefflib; print(torch.cuda.is_available())" 2>$null | Select-Object -Last 1)
$kod = $LASTEXITCODE
Pop-Location
if ($kod -ne 0) { Dur "yapay zeka kutuphaneleri yuklenemedi (torch/ultralytics/onnxruntime/lightgbm/emotiefflib)" }
if ("$cuda".Trim() -eq "True") { Tamam "torch CUDA ile GPU'yu goruyor" }
else { Uyari "torch GPU'yu gormuyor — NVIDIA surucusunu kontrol edin; sistem CPU'da cok yavas calisir" }

# ─── 5. Altyapı + yönetici kullanıcısı ──────────────────────────────────
Adim "5/6 Altyapi (Docker) ve yonetici kullanicisi"
docker compose up -d
if ($LASTEXITCODE -ne 0) { Dur "docker compose up basarisiz" }
$hazir = $false
foreach ($i in 1..60) {
    docker compose exec -T postgres pg_isready -U sentinel *> $null
    if ($LASTEXITCODE -eq 0) { $hazir = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $hazir) { Dur "PostgreSQL 120 sn icinde hazir olmadi" }
Tamam "altyapi ayakta"

$giris = Join-Path $kok "GIRIS-BILGILERI.txt"
if (Test-Path $giris) {
    Tamam "yonetici kullanicisi daha once olusturulmus (GIRIS-BILGILERI.txt)"
} else {
    Push-Location (Join-Path $kok "backend")
    $env:PYTHONIOENCODING = "utf-8"
    $cikti = (uv run python scripts/kullanici_ekle.py admin --rol admin --uret) -join "`n"
    $kod = $LASTEXITCODE
    Pop-Location
    $m = [regex]::Match($cikti, "parola:\s*(\S+)")
    if ($kod -ne 0 -or -not $m.Success) { Dur "yonetici kullanicisi olusturulamadi:`n$cikti" }
    $icerik = "SENTINEL giris bilgileri`r`nAdres     : http://127.0.0.1:8001/app`r`nKullanici : admin`r`nParola    : $($m.Groups[1].Value)`r`n"
    [IO.File]::WriteAllText($giris, $icerik, (New-Object System.Text.UTF8Encoding($false)))
    Tamam "yonetici kullanicisi olusturuldu -> GIRIS-BILGILERI.txt"
}

# ─── 6. Başlat ──────────────────────────────────────────────────────────
Adim "6/6 Sistem baslatiliyor"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $kok "backend\scripts\start_all.ps1")
if ($LASTEXITCODE -ne 0) { Dur "start_all.ps1 basarisiz (loglar: $env:TEMP\sentinel)" }

Write-Host "`n==============================================" -ForegroundColor Green
Write-Host " SENTINEL calisiyor" -ForegroundColor Green
Write-Host " Panel  : http://127.0.0.1:8001/app"
Write-Host " Giris  : GIRIS-BILGILERI.txt"
Write-Host " Durdur : powershell -ExecutionPolicy Bypass -File backend\scripts\stop_all.ps1"
Write-Host "==============================================" -ForegroundColor Green
