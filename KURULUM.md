# SENTINEL — Kurulum ve Çalıştırma

Çok kameralı akıllı gözetim sistemi. Yirmi eşzamanlı kamera akışında kişi
tespiti, takip, poz kestirimi, yüz ifadesi sınıflandırması, anomali tespiti
ve saldırgan davranış kestirimi yapar; sonuçlar web panelinde canlı izlenir.

Bu klasör sistemin **çalışır bir kopyasıdır**: kod, eğitilmiş modeller, yirmi
kameranın videoları ve her kamera için öğrenilmiş "normal" profilleri
içindedir. Model eğitimi ya da veri seti indirmesi **gerekmez**.

---

## 1. Gereksinimler

| | |
|---|---|
| İşletim sistemi | Windows 10 / 11 |
| Ekran kartı | NVIDIA, güncel sürücü (geliştirme: RTX 3070 Laptop, 8 GB) |
| Docker | Docker Desktop, **çalışır durumda** |
| uv | Python paket yöneticisi — kurulumu aşağıda |
| Disk | ~12 GB boş alan (Python bağımlılıkları ~8 GB) |
| İnternet | **Yalnızca ilk kurulumda** (Python paketleri ve Docker imajları) |

`uv` kurulu değilse PowerShell'de:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## 2. Kurulum ve başlatma — tek komut

Bu klasörde PowerShell açıp:

```powershell
powershell -ExecutionPolicy Bypass -File kurulum.ps1
```

Betik sırasıyla şunları yapar ve her adımı doğrular; bir adım başarısız
olursa nedenini yazıp durur:

1. Docker, uv ve NVIDIA ekran kartını denetler
2. Gerekli dosyaların (modeller, videolar, profiller) yerinde olduğunu denetler
3. `.env` ortam dosyasını **rastgele parolalarla** üretir
4. Python bağımlılıklarını kurar (ilk seferde birkaç dakika sürer)
5. Altyapıyı (PostgreSQL, Valkey, MediaMTX, Prometheus, Grafana) başlatır
   ve yönetici kullanıcısını oluşturur
6. Tüm süreçleri başlatır

Yalnızca denetim yapmak için: `kurulum.ps1 -SadeceKontrol`

## 3. Kullanım

| | |
|---|---|
| Panel | http://127.0.0.1:8001/app |
| Giriş | Kullanıcı adı ve parola `GIRIS-BILGILERI.txt` dosyasında |
| Grafana (ölçüm panoları) | http://127.0.0.1:3000 |

Panelde:
- **Izgara**: kutucuğa tıklayınca video açılır; tespit kutuları, takip
  kimlikleri ve iskeletler videonun üzerine çizilir. Sağdaki panelde
  alarmlar ve her alarmın kanıtı listelenir.
- **Zaman Çizelgesi**: kamera × saat ısı haritası ve olay tablosu.
- **Kamera Detayı**: tek kameranın canlı görüntüsü ve olayları.

Sistem açıldıktan sonra analizin oturması ~1-2 dakika sürer.

## 4. Durdurma ve yeniden başlatma

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\stop_all.ps1    # durdur
powershell -ExecutionPolicy Bypass -File backend\scripts\start_all.ps1   # yeniden başlat
```

`kurulum.ps1` tekrar çalıştırılabilir; var olan `.env` dosyasına ve
kullanıcıya dokunmaz.

## 5. Klasörün içeriği

| Klasör | İçerik |
|---|---|
| `backend/` | Python süreçleri: alım, çıkarım, analitik, alarm, API · `tests/` birim testleri · `scripts/` ölçüm ve değerlendirme betikleri |
| `frontend/` | React panelinin kaynak kodu (derlenmiş hâli `backend/src/sentinel/api/static/app/` içinde) |
| `models/` | Tespit ve poz (YOLO26), yüz tespiti (YuNet), ifade (EmotiEffLib), **eğitilmiş** saldırganlık modeli (LightGBM) ve **eğitilmiş** video modeli (R3D-18) |
| `data/videos/` | Yirmi kameranın videoları; sistem bunları sonsuz döngüde canlı kamera gibi yayınlar |
| `data/profiles/` | Her kamera için öğrenilmiş "normal" profili (anomali tespiti) |
| `benchmarks/` | Raporda geçen tüm ölçümlerin ham çıktıları (JSON) |
| `docs/decisions/` | Mimari karar kayıtları |
| `docs/report/problems.md` | Geliştirme günlüğü |
| `infra/` | Docker, MediaMTX, Prometheus, Grafana, Caddy yapılandırmaları |

**Veri setleri** boyutları (~31 GB) ve lisans koşulları nedeniyle bu klasöre
eklenmemiştir; kullanılan veri setlerinin adları staj raporunda verilmiştir.
Kamera videoları bu veri setlerinden derlenmiş kısa kesitlerdir ve sistemin
çalıştırılması için yeterlidir. Veri seti gerektiren yalnızca **ölçümlerin
yeniden üretilmesi**dir (`backend/scripts/evaluate_*.py`).

## 6. Sorun giderme

| Belirti | Çözüm |
|---|---|
| "Docker kurulu ama çalışmıyor" | Docker Desktop'ı açıp tamamen başlamasını bekleyin |
| Port kullanımda hatası | 8001, 5433, 6379, 8554, 8889, 9090, 3000 portlarını kullanan başka bir uygulamayı kapatın |
| Panel açılıyor ama kutu çizilmiyor | 1-2 dakika bekleyin; sürmüyorsa günlükler: `%TEMP%\sentinel\*.log` |
| Kamera 21 (web kamerası) görünmüyor | Beklenen durum; web kamerası isteğe bağlıdır, 20 kamera ondan bağımsız çalışır |
