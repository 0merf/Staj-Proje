# SENTINEL — arka uç + YZ worker'ları + derlenmiş React arayüzü
#
# ⚠ NEDEN TEK İMAJ, BEŞ SERVİS
# API, alım, çıkarım, analitik ve alarm worker'ları AYNI kod tabanını
# ve AYNI modelleri kullanıyor. Beş ayrı imaj, beş kez ~6 GB'lık
# PyTorch+CUDA katmanı demekti. Tek imaj, farklı `command` — servis
# ayrımı çalışma zamanında yapılıyor, derleme zamanında değil.
#
# ⚠ NEDEN CUDA TABAN İMAJI
# Çıkarım worker'ı GPU'ya ihtiyaç duyuyor. API duymuyor ama aynı imajı
# paylaşıyor; ayrı bir "ince API imajı" üretmek ikinci bir bağımlılık
# ağacı bakımı demekti ve kazandırdığından fazla iş getiriyordu.
#
# ⚠ DOCKER'DA GPU — ÖLÇÜLDÜ, ÇALIŞIYOR (03.09.2026)
# `CLAUDE.md` "Windows+Docker+GPU = WSL2 karmaşası" diyordu ve tam
# konteynerleştirme bu gerekçeyle son haftaya ertelenmişti. Sınandı:
#
#     docker run --rm --gpus all nvidia/cuda:12.8.0-base nvidia-smi
#     → NVIDIA GeForce RTX 3070 Laptop GPU, 8192 MiB
#
# `nvidia` çalışma zamanı Docker'a kayıtlı. Varsayım çürüdü.

# ══════════════════════════════════════════════════════════════
#  1. AŞAMA — React arayüzünü derle
# ══════════════════════════════════════════════════════════════
#
# ⚠ Ön yüz derlemesi ÇALIŞMA ZAMANI imajına girmiyor: Node, npm ve
# node_modules (~200 MB) yalnızca derleme için gerekli. Çok aşamalı
# derleme sayesinde son imaja yalnızca `dist` çıktısı kopyalanıyor.
FROM node:22-alpine AS frontend

WORKDIR /frontend
# ⚠ Önce yalnızca manifest kopyalanıyor: kaynak dosya değiştiğinde
# `npm ci` katmanı önbellekten geliyor. Her kod değişikliğinde
# bağımlılıkları yeniden indirmek derlemeyi dakikalarca uzatırdı.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# ⚠ `vite.config.ts` çıktıyı `../backend/src/...` altına yazıyor
# (yerel geliştirmede FastAPI oradan servis ediyor). Derleme
# aşamasında o yol imajın içinde yok, bu yüzden açıkça veriliyor.
RUN npx vite build --outDir /frontend/dist --emptyOutDir


# ══════════════════════════════════════════════════════════════
#  2. AŞAMA — çalışma zamanı
# ══════════════════════════════════════════════════════════════
FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/python

# ⚠ `libgl1` + `libglib2.0-0`: OpenCV'nin (`opencv-python`) çalışma
# zamanı bağımlılıkları. Bunlar olmadan `import cv2` şu hatayı verir:
# "libGL.so.1: cannot open shared object file" — ve hata mesajı
# OpenCV'yi değil Python'u işaret ettiği için teşhisi zordur.
#
# ⚠ `ffmpeg` DEĞİL: PyAV kendi ffmpeg kütüphanelerini tekerlekle
# getiriyor ve sistem ffmpeg'i shell'den çağırmıyoruz (G09 — komut
# enjeksiyonu yüzeyi yok).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# uv — pip değil (CLAUDE.md §3). Python 3.13'ü de o kuruyor:
# Ubuntu 22.04 deposunda 3.10 var ve projenin gereksinimi >=3.13.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# ⚠ Bağımlılıklar KAYNAK KODDAN ÖNCE kuruluyor. Kod her değiştiğinde
# ~6 GB'lık PyTorch katmanını yeniden indirmemek için: Docker katman
# önbelleği yalnızca değişen adımdan sonrasını yeniden çalıştırıyor.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --extra gpu

# Kaynak kod
COPY backend/src ./src
COPY backend/scripts ./scripts
RUN uv sync --frozen --extra gpu

# Derlenmiş React arayüzü — FastAPI `/app` altında servis ediyor
COPY --from=frontend /frontend/dist ./src/sentinel/api/static/app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src

# ⚠ ROOT OLMAYAN KULLANICI (PLAN §11.1 · G22)
# Konteyner ele geçirilirse saldırganın host üzerindeki etki alanını
# daraltıyor. ⚠ `/dev/shm` ve model dizini bu kullanıcı tarafından
# okunabilir olmalı — `--chown` ile veriliyor.
RUN useradd --create-home --uid 10001 sentinel \
    && chown -R sentinel:sentinel /app
USER sentinel

# ⚠ Sağlık kontrolü YALNIZCA API servisinde anlamlı; worker'lar HTTP
# sunmuyor (metrik ucu hariç). Compose'da servis bazında
# geçersiz kılınıyor.
HEALTHCHECK NONE

CMD ["uvicorn", "sentinel.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
