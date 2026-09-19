# SENTINEL — Çok Kameralı Akıllı Gözetim Sistemi

Staj projem olarak geliştirdiğim, 20 kamerayı aynı anda izleyen web tabanlı
bir gözetim sistemi. Her kamera akışında kişi tespiti, takip, poz kestirimi
ve yüz ifadesi sınıflandırması yapıyor. Bunların üzerinden **anomali
tespiti** ve **saldırgan davranışın erken tespiti** yapıp sonuçları canlı bir
panelde gösteriyor.

Projenin asıl zorluğu model seçimi değildi: 20 eşzamanlı akışı tek bir
dizüstü GPU'sunda (RTX 3070 Laptop, 8 GB) gerçek zamanlı işleyebilecek bir
mimari kurmaktı. Kararların çoğu bu kısıttan çıktı.

**Staj dönemi:** 12 Ağustos – Eylül 2026

---

## Ne yapıyor?

| Yetenek | Yaklaşım |
|---|---|
| Anomali tespiti | Her kamera için ayrı öğrenilen "normal" profili + kural tabanlı kontroller (düşme, kalabalık, oyalanma) |
| Yüz ifadesi analizi | YuNet ile yüz tespiti + EmotiEffLib ile ifade sınıflandırması; karara düşük ağırlıkla katılıyor |
| Saldırganlığın erken tespiti | İskelet tabanlı özellikler + eğittiğim LightGBM modeli |
| 20 kamera ölçeği | Kademeli işleme: hareket olmayan kareler daha GPU'ya gitmeden eleniyor |

Beş sinyal (saldırganlık, normal profilden sapma, kurallar, yüz ifadesi,
kalabalık) bir füzyon katmanında tek bir risk skoruna çevriliyor. Alarm bu
skordan üretiliyor.

---

## Mimari

```
20 video dosyası (+ isteğe bağlı webcam) → MediaMTX (RTSP)
   ↓
Alım worker'ı      tek süreç, kamera başına thread
                   çözme, hareket filtresi (kademe 0), ön işleme
   ↓ paylaşımlı bellek (ham kare) + Valkey Stream (yalnızca meta veri)
Çıkarım worker'ı   modeller tek kopya (VRAM için)
                   kademe 1: YOLO26 tespit + BoT-SORT takip
                   kademe 2: poz + yüz/ifade
   ↓ Valkey Stream (JSON sonuçlar)
Analitik worker'ı  özellik pencereleri → anomali + saldırganlık → füzyon
   ↓
Alarm worker'ı     PostgreSQL/TimescaleDB · olay klibi (yerel disk)
   ↓
FastAPI (REST + WebSocket) → React panel
```

Video tarayıcıya WebRTC (WHEP) ile ayrı gidiyor; kutular ve iskeletler
WebSocket üzerinden JSON olarak geliyor ve tarayıcıda çiziliyor. Sunucu
videoyu hiçbir zaman yeniden kodlamıyor.

Her önemli kararın gerekçesini `docs/decisions/` altında karar kaydı (ADR)
olarak yazdım.

---

## Teknoloji yığını

| Katman | Seçim |
|---|---|
| Arka uç | Python 3.13 · FastAPI · PyAV |
| Kuyruk / önbellek | Valkey (Redis uyumlu) |
| Veritabanı | PostgreSQL 17 + TimescaleDB |
| Medya sunucusu | MediaMTX (RTSP → WebRTC, yeniden kodlamasız) |
| Modeller | YOLO26-s (tespit), YOLO26-pose, BoT-SORT, YuNet + EmotiEffLib, LightGBM, PyTorch FP16 |
| Ön yüz | React 19 · TypeScript · Vite 7 · Tailwind CSS 4 · Zustand |
| Gözlem | Prometheus + Grafana |
| TLS (isteğe bağlı) | Caddy |

Planlayıp kullanmadıklarım:

| Teknoloji | Durum | Neden |
|---|---|---|
| TensorRT | Ölçtüm, üretimde değil | Hızlanma var ve tespitler birebir aynı; ama motor sabit parti boyutu istiyor, canlıdaki parti dağılımı buna uymuyor (`docs/decisions/0006-tensorrt.md`) |
| Garage (S3 nesne deposu) | Kullanılmadı | Tek makineli bir kurulumda klipleri yerel diske yazmak yetiyor; nesne deposu burada çözülecek bir sorunu çözmüyordu |
| Alembic | Kullanılmıyor | Şema her açılışta idempotent SQL ile kuruluyor (`db/schema.py`) |

---

## Çalıştırma

### Gereksinimler

| | |
|---|---|
| İşletim sistemi | Windows 10 / 11 (geliştirme ve test ortamı) |
| Ekran kartı | NVIDIA, CUDA 12 uyumlu sürücü, 8 GB VRAM yeterli |
| Docker Desktop | Çalışır durumda |
| uv | Python paket yöneticisi; Python 3.13'ü de kendisi kuruyor |
| Node.js 22+ | Yalnızca arayüzü derlemek için |
| Disk | ~12 GB (Python bağımlılıklarının çoğu PyTorch) |

`uv` kurulu değilse:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Modeller, videolar ve profiller

Bunlar boyut ve lisans nedeniyle depoda yok:

- **Model ağırlıkları** (`models/`):
  - YOLO26 tespit ve poz: `uv run python scripts/fetch_models.py` resmi
    kaynaktan indirip SHA256'larını `models/checksums.json` ile doğruluyor.
  - YuNet yüz tespiti: OpenCV Zoo'daki `.onnx` dosyası `models/yunet.onnx`
    olarak konmalı.
  - İfade modeli: EmotiEffLib ilk kullanımda kendisi indiriyor. İnternet
    yoksa `models/emotieff_enet_b0_8_vgaf.onnx` dosyası
    `%USERPROFILE%\.emotiefflib\enet_b0_8_best_vgaf.onnx` olarak kopyalanabilir.
  - Kendi eğittiğim saldırganlık modeli (`models/saldirganlik_lgbm.txt`)
    depoda var.
- **Kamera videoları** (`data/videos/cam-01.mp4` … `cam-20.mp4`): kullandığım
  veri setlerinden `scripts/build_camera_farm.py` ile üretiliyor. Hangi
  veri setinin nereden indirildiği ve lisansı `data/**/SOURCE.md`
  dosyalarında.
- **Kamera profilleri** (`data/profiles/`): yoksa sistem ilk dakikalarda
  kendisi öğreniyor.

Komisyona teslim ettiğim kopyada bu üçü hazır olarak klasörün içinde.

### Adımlar

Proje klasöründe PowerShell açıp sırayla:

```powershell
# 1. Ortam dosyası: .env.example'ı kopyala, CHANGE_ME değerlerini değiştir
Copy-Item .env.example .env
notepad .env

# 2. Altyapı (PostgreSQL, Valkey, MediaMTX, Prometheus, Grafana)
docker compose up -d

# 3. Python bağımlılıkları (GPU paketleri "gpu" ek grubunda)
cd backend
uv sync --extra gpu

# 4. Yönetici kullanıcısı: parola ekrana bir kez yazılıyor, not alın
uv run python scripts/kullanici_ekle.py admin --rol admin --uret

# 5. Arayüzü derle (yalnızca ilk seferde)
cd ..\frontend
npm install
npm run build

# 6. Tüm süreçleri doğru sırayla başlat
cd ..
powershell -ExecutionPolicy Bypass -File backend\scripts\start_all.ps1
```

Panel: **http://127.0.0.1:8001/app**. Grafana panoları:
http://127.0.0.1:3000.

Sistem açıldıktan sonra analizin oturması 1-2 dakika sürüyor. Durdurmak
için:

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\stop_all.ps1
```

Birkaç not:

- Adres çubuğuna `localhost` değil **`127.0.0.1`** yazılmalı. Tarayıcı
  ikisini ayrı köken sayıyor ve WebSocket köken denetimine takılıyor.
- `start_all.ps1` süreçleri belirli bir sırayla başlatıyor: paylaşımlı
  bellek havuzunu alım worker'ı kuruyor, çıkarım worker'ı ona bağlanıyor.
  Her adımda sürecin gerçekten ayağa kalktığını denetliyor; bir süreç
  açılmazsa günlüğünü gösterip hata koduyla çıkıyor.
- Docker konteynerleri bilgisayar açılınca kendiliğinden geliyor, Python
  süreçleri gelmiyor. Her seferinde `start_all.ps1` çalıştırılmalı.
- TLS ile tek giriş noktası isteğe bağlı: `docker compose --profile tls up -d caddy`
  → https://127.0.0.1:8443/app

### Portlar

Tüm portlar yalnızca `127.0.0.1`'e bağlı, dış ağa kapalı.

| Servis | Port |
|---|---|
| API + panel | 8001 |
| PostgreSQL | 5433 |
| Valkey | 6379 |
| MediaMTX | 8554 (RTSP) · 8889 (WebRTC) |
| Grafana / Prometheus | 3000 / 9090 |

API'yi 8000'de değil 8001'de, PostgreSQL'i 5432'de değil 5433'te
çalıştırıyorum; aynı makinede başka bir projem o portları kullanıyor.

### Testler

```powershell
cd backend
uv run pytest tests/unit          # birim testleri (altyapı gerektirmez)
uv run ruff check . ; uv run mypy src

cd ..\frontend
npm test                          # Vitest
npm run typecheck ; npm run lint
npm run e2e                       # Playwright (sistem ayaktayken)
```

---

## Başarı kriterleri ve ölçülen sonuçlar

Proje başında on başarı kriteri belirledim. Belgelerdeki K1…K10
numaraları bunlar. Ham ölçüm çıktıları `benchmarks/` altında.

| # | Kriter | Hedef | Ölçülen | Durum |
|---|---|---|---|---|
| K1 | Eşzamanlı kamera | ≥20 | 20/20 | Tuttu |
| K2 | Kamera başına analiz hızı | ≥4 FPS | 2.34 FPS | Tutmadı; sebep ölçüldü: çıkarım döngüsü tek çekirdekte doyuyor (P-65) |
| K3 | Gecikme (kareden çıkarım sonucuna) | ≤1500 ms | p50 378 ms · p95 652 ms | Tuttu |
| K4 | Çökmeden çalışma | 2 saat | 120 dk, 0 kesinti, bellek sızıntısı yok | Tuttu |
| K5 | Şiddet tespiti F1 (RWF-2000) | ≥0.85 | Canlıdaki LightGBM 0.889 · video modeliyle birleşim 0.916 (çevrim dışı, eşik yanlılığı düzeltilmiş) | Tuttu |
| K6 | Anomali tespiti AUC (Avenue) | ≥0.75 | 0.867 | Tuttu |
| K7 | Yanlış alarm | ≤3 / kamera-saat | Alarmları elle etiketledim: kesinlik 0.895 (19 bağımsız olay) | Kısmen; oran yerine kesinlik ölçülebildi (P-85) |
| K8 | Erken uyarı | ≥2 sn önce | −1.10 sn | Tutmadı; bu veri setinde ölçütün tavanı zaten hedefin altında (P-84) |
| K9 | Güvenlik maddeleri | 19/19 | 18/19 | Kamera bazlı yetki yok (G05) |
| K10 | Arayüz akıcılığı | ≥30 FPS | Medyan 30.00 FPS | Sınırda (P-87) |

Tutmayan kriterleri gizlemedim; her birinin sebebini ölçüp yazdım.
P-xx numaraları `docs/report/problems.md` içindeki kayıtlar.

---

## Güvenlik

Yapılanlar:

- Argon2id ile parola saklama, JWT (15 dk erişim / 7 gün yenileme),
  token'lar `httpOnly` çerezde; `localStorage` hiç kullanılmıyor
- Rol tabanlı yetki: `viewer` < `operator` < `admin`
- Giriş hız sınırı ve hesap kilitleme; kullanıcı adı sızdırmayan tek tip
  hata mesajı
- WebSocket'te `Origin` denetimi, çerezden kimlik doğrulama, kullanıcı
  başına bağlantı sınırı
- Yüz görüntüleri saklanmıyor, yalnızca etiket ve güven skoru
- Denetim izi PostgreSQL'de ve yalnızca ekleme yapılabiliyor (UPDATE /
  DELETE / TRUNCATE tetikleyiciyle engelli)
- Caddy ile TLS ve tek giriş noktası: video akışı da kimlik
  doğrulamasından geçiyor (`--profile tls`)
- `.env` hiçbir zaman depoya girmiyor

Yapmadıklarım:

- Kamera bazlı yetki: giriş yapmış her kullanıcı tüm kameraları görebiliyor
- Yüz bulanıklaştırma: ticari bir kurulum olmadığı için kapsam dışı bıraktım

---

## Klasörler

| Klasör | İçerik |
|---|---|
| `backend/src/sentinel/` | Alım, çıkarım, analitik, alarm ve API süreçleri |
| `backend/scripts/` | Başlatma/durdurma betikleri, ölçüm ve değerlendirme betikleri |
| `backend/tests/` | Birim ve entegrasyon testleri |
| `frontend/` | React paneli ve Playwright testleri |
| `infra/` | MediaMTX, Prometheus, Grafana, Caddy, Valkey yapılandırmaları |
| `models/` | Model künyeleri, checksum kaydı ve eğittiğim saldırganlık modeli |
| `data/annotations/` | Yer gerçeği ve alarm etiketleri |
| `benchmarks/` | Tüm ölçümlerin ham çıktıları (JSON) |
| `docs/decisions/` | Mimari karar kayıtları |
| `docs/report/problems.md` | Geliştirme günlüğüm: karşılaştığım her problem, sebebi ve çözümü |
| `docs/report/` | Denetim notları, diyagramlar ve ekran görüntüleri |

Projenin en çok şey öğrendiğim kısmı `problems.md`. Doğru bildiğim pek
çok şey ölçünce yanlış çıktı; o kayıtlar bunları ve nasıl fark ettiğimi
anlatıyor.
