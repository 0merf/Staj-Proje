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

$venv = "D:\Staj Proje\backend\.venv"
$killed = 0

Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.ExecutablePath -like "$venv*" -or
        $_.CommandLine -match 'sentinel\.(ingest|inference|api)' -or
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
