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

**Arka uç:** Python 3.13 · FastAPI · PyAV · Valkey · PostgreSQL 17 + TimescaleDB · Garage
**YZ:** YOLO26 (tespit + poz) · BoT-SORT · YuNet + EmotiEffLib · TensorRT FP16
**Ön yüz:** React 19 · TypeScript · Vite 7 · Tailwind CSS 4 · shadcn/ui · Zustand
**Medya:** MediaMTX (RTSP → WebRTC/WHEP, yeniden kodlamasız)
**Altyapı:** Docker Compose · Caddy · Prometheus · Grafana

Her seçimin gerekçesi: PLAN.md §3

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
uv run alembic upgrade head
uv run uvicorn sentinel.api.main:app --reload

# 4. Ön yüz (yeni terminal)
cd frontend
npm install
npm run dev                # http://localhost:5173
```

### Kamera çiftliği (20 sahte kamera)

```powershell
# Kaynak videoları data/videos/ içine koy, sonra:
uv run python backend/scripts/prepare_videos.py    # 720p'ye normalize et
docker compose restart mediamtx
# Doğrula:  rtsp://localhost:8554/cam-01
```

---

## ⚠️ Güvenlik Notları

- `.env` dosyası **asla** commit edilmez
- Üretimde Valkey / PostgreSQL / Garage portları host'a **açılmaz**
- Yüz görüntüleri **saklanmaz** — yalnızca etiket ve güven skoru
- Tüm kamera görüntüleme ve klip dışa aktarma işlemleri **denetim kaydına** yazılır

Tam güvenlik planı: PLAN.md §11
KVKK ve etik: PLAN.md §12

---

## Proje Durumu

Güncel ilerleme ve sıradaki adım için: CLAUDE.md §6-7
