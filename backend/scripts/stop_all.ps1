# SENTINEL — tüm worker ve API süreçlerini durdurur.
#
# Neden gerekli: worker'lar `uv run python -m sentinel...` ile başlatılıyor.
# Bu bir sarmalayıcı süreç yaratıyor; komut satırı eşleştirmesi yalnızca
# sarmalayıcıyı yakalıyor, asıl python.exe çocuğu hayatta kalıyor. Zamanla
# kopya worker'lar birikiyor ve ölçümleri bozuyor (aynı tüketici grubunda
# yarışıyorlar).
#
# Bu betik proje venv'inden çalışan HER python sürecini durdurur.
#
# Kullanım:  pwsh backend/scripts/stop_all.ps1

# ⚠ Sabit "D:\Staj Proje\..." yolu vardı; proje başka klasöre/bilgisayara
# kopyalanınca venv eşleşmesi boşa düşüyordu. Betiğin kendi konumundan çözülüyor.
$venv = Join-Path (Split-Path $PSScriptRoot -Parent) ".venv"
$killed = 0

Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
        # ⚠ Birinci koşul (venv yolu) pratikte hepsini yakalıyor;
        # ikincisi bir GÜVENLİK AĞI, çünkü bir worker venv dışından
        # (ör. elle `python -m ...`) başlatılmış olabilir.
        #
        # ⚠ Liste TAM olmalı. 30.08.2026'ya kadar yalnızca
        # ingest|inference|api yazıyordu; analytics ve alerting
        # eksikti ve yalnızca venv koşulu sayesinde kapanıyorlardı.
        # Eksik bir listeyi "zaten çalışıyor" diye bırakmak, ilk
        # koşul değiştiği gün sessizce bozulacak bir bağımlılık
        # yaratır.
        $_.ExecutablePath -like "$venv*" -or
        $_.CommandLine -match 'sentinel\.(ingest|inference|analytics|alerting|api)' -or
        $_.CommandLine -match 'uvicorn.*sentinel'
    } |
    ForEach-Object {
        $label = if ($_.CommandLine -match '-m\s+(sentinel\.\S+)') { $matches[1] }
                 elseif ($_.CommandLine -match 'uvicorn') { 'api' }
                 else { 'python' }
        Write-Host ("  durduruldu  PID {0,-6} {1}" -f $_.ProcessId, $label)
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $script:killed++
    }

# Paylaşımlı bellek bloğu, onu tutan son süreç kapanınca Windows tarafından
# serbest bırakılır. Ayrıca unlink gerekmez.
Start-Sleep -Seconds 2

if ($killed -eq 0) { Write-Host "  çalışan SENTINEL süreci yok" }
else { Write-Host "`n  toplam $killed süreç durduruldu" }


# ─── HAM KAYITLARI TEMİZLE ────────────────────────────────────────
#
# NEDEN GEREKLİ
# Kaynak videolar `-stream_loop -1` ile SONSUZ döngüde yayınlanıyor,
# yani kayıt açıkken disk durmadan yazılır (ölçülen: ~14 GB/saat,
# 20 kamera). MediaMTX'in kendi `recordDeleteAfter: 1h` temizliği bunu
# çalışırken sınırlıyor — ama YALNIZCA MediaMTX çalışırken.
#
# Açık tam olarak burası: geliştirme oturumunu bitirip konteynerleri
# durdurunca son bir saatin kayıtları (~14 GB) diskte öylece kalıyor
# ve bir dahaki açılışa kadar kimse silmiyor. Haftalarca dokunulmazsa
# öylece durur.
#
# Ham kayıt zaten GEÇİCİ bir aratabandır: değeri, alarm anında ondan
# kesilen klipte. Klipler Garage'a yükleniyor ve KVKK saklama süresi
# (30 gün) onlara işliyor. Oturum bitince ham kaydı tutmanın hiçbir
# faydası yok.
#
# ⚠ `data/clips/` SİLİNMEZ — orası kesilmiş olay klipleri, yani
# ürünün çıktısı. Yalnızca `data/recordings/` (ham aratabant) siliniyor.
$recordings = Join-Path $PSScriptRoot "..\..\data\recordings"
if (Test-Path $recordings) {
    $before = Get-ChildItem $recordings -Recurse -File -Filter *.mp4 -ErrorAction SilentlyContinue
    if ($before) {
        $mb = [math]::Round(($before | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
        # Yalnızca kamera alt dizinleri siliniyor; .gitkeep korunuyor ki
        # dizin yapısı bozulmasın (.gitignore `!**/.gitkeep` bekliyor).
        Get-ChildItem $recordings -Directory -ErrorAction SilentlyContinue |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host ("  ham kayıtlar silindi: {0} dosya, {1} MB" -f $before.Count, $mb)
    }
    else {
        Write-Host "  ham kayıt yok (kayıt kapalı ya da zaten temiz)"
    }
}
