# SENTINEL — Çok Kameralı Akıllı Gözetim Sistemi

> 20+ kameranın eşzamanlı izlendiği; **anomali tespiti**, **yüz ifadesi analizi** ve
> **saldırgan davranışın erken tespiti** yapan yapay zekâ destekli web tabanlı gözetim platformu.

**Staj Projesi** · Ağustos 2026

---

## Dokümantasyon

> ℹ️ Aşağıdaki üç doküman **yerel çalışma dosyasıdır** ve bu depoya dahil edilmemiştir.
> Proje kök dizininde bulunurlar.

| Dosya | İçerik |
|---|---|
| `PLAN.md` | Tam teknik plan — mimari, modüller, güvenlik, 25 günlük faz planı |
| `CLAUDE.md` | Proje hafızası — mevcut durum, kararlar, ilerleme |
| `LITERATUR.md` | Kaynak araştırması, literatür notları, karar günlüğü |

---

## Ne yapıyor?

| Yetenek | Yaklaşım |
|---|---|
| **Anomali tespiti** | Kamera başına öğrenilmiş normal davranış profili + kural motoru |
| **Duygu analizi** | Yüz ifadesi sınıflandırma (kalite skorlu, düşük ağırlıklı) |
| **Saldırganlık erken tespiti** | İskelet tabanlı tırmanma skoru — olay *öncesi* uyarı |
| **20 kamera ölçeği** | Kademeli işleme (cascade) + uyarlanabilir kare hızı |

---

## Mimari (özet)

```
Kameralar → MediaMTX → Ingest Worker'ları (hareket filtresi, paylaşımlı bellek)
                            ↓ Valkey Streams
                       GPU Worker (YOLO26 + poz + duygu, tek model kopyası)
                            ↓
                       Analytics (özellik → risk skoru → füzyon)
                            ↓
                    Alarm Motoru → PostgreSQL/TimescaleDB + Garage (klipler)
                            ↓
                    FastAPI (REST + WebSocket) → React SPA
```

Video akışı WebRTC/WHEP ile **ayrı** gider; kutular ve iskeletler WebSocket'ten JSON olarak
gelir ve tarayıcı canvas'ında çizilir. Sunucu hiçbir zaman video yeniden kodlamaz.

Detaylar: PLAN.md §4

---

## Teknoloji Yığını

**Arka uç:** Python 3.13 · FastAPI · PyAV · Valkey · PostgreSQL 17 + TimescaleDB
**YZ:** YOLO26 (tespit + poz) · BoT-SORT · YuNet + EmotiEffLib · PyTorch FP16
**Ön yüz:** React 19 · TypeScript · Vite 7 · Tailwind CSS 4 · Zustand
**Medya:** MediaMTX (RTSP → WebRTC/WHEP, yeniden kodlamasız)
**Altyapı:** Docker Compose · Prometheus · Grafana

Her seçimin gerekçesi: `docs/decisions/` (ADR) ve PLAN.md §3

### ⚠ Planlanıp KULLANILMAYANLAR — dürüstlük notu

Bu liste 03.09.2026'da gerçekle hizalandı. Önceki hâli üç teknolojiyi
kullanılıyormuş gibi sayıyordu:

| Teknoloji | Durum | Gerekçe |
|---|---|---|
| **TensorRT** | ölçüldü, **üretimde değil** | 1.40× hızlanma ölçüldü ve tespitler birebir aynı çıktı; ama motor sabit parti istiyor ve canlı parti dağılımı (ortalama 5.52) buna uymuyor → `docs/decisions/0006-tensorrt.md` |
| **Garage** (S3) | **hiç kullanılmadı** | Klipler yerel diskte (`data/clips/`). Nesne deposu tek makineli bir kurulumda kazandırdığından fazla işletme yükü getiriyordu |
| **Caddy** (TLS) | **kurulmadı** | Açık iş. Her şey `127.0.0.1`'e bağlı olduğu için TLS'siz çalışıyor; tek giriş noktası olmadığı bilinen bir eksik (K9: 14/19) |
| **Alembic** | bağımlılık kurulu, **kullanılmıyor** | Tek tablolu şema + TimescaleDB'ye özgü çağrılar; şema açılışta idempotent SQL ile kuruluyor (`db/schema.py`) |

---

## Kurulum

### Ön koşullar

| Yazılım | Sürüm |
|---|---|
| Python | 3.13+ |
| Node.js | 24 LTS |
| Docker Desktop | 29+ |
| NVIDIA GPU | CUDA 12 uyumlu, ≥ 8 GB VRAM |
| uv | son sürüm |

### Adımlar

```powershell
# 1. Ortam değişkenleri
cp .env.example .env
# .env dosyasını aç, CHANGE_ME değerlerini doldur

# 2. Altyapıyı başlat
docker compose up -d
docker compose ps          # tümü healthy olmalı

# 3. Arka uç
cd backend
uv sync
# ⚠ Şema için ayrı bir migration adımı YOK: tablolar, hypertable ve
#   politikalar her açılışta idempotent olarak kuruluyor
#   (db/schema.py · db/kullanicilar.py). Alembic kullanılmıyor.

# ⚠ PORT 8001 — 8000 DEĞİL. Aynı makinede başka bir proje 8000'i
#   kullanıyor (P-01). Portu yazmadan başlatmak sessizce çakışır.
uv run uvicorn sentinel.api.main:app --port 8001 --reload

# 4. İlk admin kullanıcıyı oluştur (parola bir kez ekrana yazılır)
uv run python scripts/kullanici_ekle.py admin --rol admin --uret

# 5. Ön yüz (yeni terminal)
cd frontend
npm install
npm run dev                # http://127.0.0.1:5173
```

⚠ **`localhost` değil `127.0.0.1` yazın.** İkisi tarayıcı için AYRI
kökendir; `localhost` üzerinden açılan panel, `127.0.0.1`'e kurulmuş
WebSocket köken doğrulamasına takılır (P-11 ve P-21 — aynı hata iki
kez yaşandı).

### Tüm sistemi tek komutla başlatmak

```powershell
pwsh backend/scripts/start_all.ps1   # 7 adım, her adım doğrulanıyor
pwsh backend/scripts/stop_all.ps1
```

⚠ Docker konteynerleri bilgisayar açılınca kendiliğinden gelir,
**Python bileşenleri gelmez.**

### Kamera çiftliği (20 sahte kamera)

```powershell
# Kaynak videoları data/videos/ içine koy, sonra:
uv run python backend/scripts/prepare_videos.py    # 720p'ye normalize et
docker compose restart mediamtx
# Doğrula:  rtsp://localhost:8554/cam-01
```

---

## ⚠️ Güvenlik Notları

**Yapılanlar:**
- `.env` dosyası **asla** commit edilmez (`.gitignore`)
- Kimlik doğrulama: Argon2id parola + JWT (15 dk erişim / 7 gün yenileme),
  token `httpOnly` çerezde — `localStorage` hiç kullanılmıyor
- Rol tabanlı yetki: `viewer` < `operator` < `admin`
- Giriş hız sınırı + hesap kilitleme, kullanıcı adı sızdırmayan hata mesajı
- WebSocket `Origin` doğrulaması + çerezden kimlik + kullanıcı başına
  bağlantı sınırı
- Yüz görüntüleri **saklanmaz** — yalnızca etiket ve güven skoru
  (`STORE_FACE_CROPS=true` yapılırsa uygulama açılmıyor)
- Denetim izi PostgreSQL'de ve **sadece-ekleme** (DB trigger UPDATE /
  DELETE / TRUNCATE engelliyor)

**Yapılmayanlar — açıkça:**
- ❌ TLS / Caddy ters proxy yok. Her şey `127.0.0.1`'e bağlı; bu bir
  savunma değil bir kurulum tesadüfü
- ❌ Kamera bazlı yetki yok: doğrulanmış her kullanıcı tüm kameraları
  görebiliyor (`user_camera_access` tablosu yazılmadı)
- ❌ Altyapı portları (5433, 6379) host'a bağlı — dış ağa kapalı ama açık
- 🟡 Denetim izi **giriş/çıkış, webcam açma-kapatma ve klip
  görüntülemeyi** kapsıyor; canlı ızgarada kamera izlemeyi kapsamıyor
- ⬜ Yüz bulanıklaştırma **kapsam dışı** (ticari kurulum değil)

Tam güvenlik planı: PLAN.md §11 · Ölçülen durum: K9 = 14/19
KVKK ve etik: PLAN.md §12

---

## Proje Durumu

Güncel ilerleme ve sıradaki adım için: CLAUDE.md §6-7
