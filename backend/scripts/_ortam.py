"""Ölçümün yapıldığı ortamın anlık görüntüsü.

Neden gerekiyor
---------------
10.09 ve 23.09'daki iki koşu, aynı ölçütte iki kat farklı gecikme
verdi. Farkın kaynağını aramak günler sonra mümkün oldu, çünkü hiçbir
koşu **hangi yapılandırmayla** çalıştığını kaydetmemişti. Kodun aynı
olduğu git geçmişinden gösterilebildi; ayarların aynı olduğu
gösterilemedi, çünkü `.env` sürüm kontrolünde değil (parola taşıyor)
ve ölçüm çıktısına da yazılmıyordu.

Bir ölçüm, tekrar üretilebilmesi için gereken her şeyi kendi içinde
taşımalı. Bu modül, her ölçüm çıktısına giren `ortam` bloğunu üretir:
kod sürümü, ölçümü etkileyen ayarlar, kütüphane sürümleri ve model
ağırlıklarının özetleri.

Parola ve gizli anahtar taşıyan alanlar dışarıda bırakılır; buraya
yalnızca başarımı etkileyen ayarlar girer.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

KOK = Path(__file__).resolve().parents[2]

# Başarımı etkilediği ölçülmüş ya da etkilemesi beklenen ayarlar.
# Liste bilinçli olarak kısa: her alan "bu değişirse sonuç değişir mi"
# sorusuna evet cevabı verdiği için burada.
ETKILI_AYARLAR = (
    "camera_count",
    "target_fps",
    "target_fps_high_risk",
    "target_fps_idle",
    "adaptive_fps_enabled",
    "adaptive_idle_after_s",
    "shm_slot_count",
    "stream_frames_maxlen",
    "stream_results_maxlen",
    "inference_shards",
    "ingest_worker_count",
    "capacity_backpressure_enabled",
)


def _git(*argv: str) -> str:
    try:
        # Argümanlar bu modülde sabit; kabuk kullanılmıyor.
        ck = subprocess.run(  # noqa: S603
            ["git", *argv],  # noqa: S607 — git PATH'ten çözülüyor
            cwd=KOK, capture_output=True, text=True, check=True,
        )
        return ck.stdout.strip()
    except Exception:
        return "bilinmiyor"


def _ozet(yol: Path) -> str | None:
    """Dosyanın SHA-256 özeti; yoksa None."""
    if not yol.is_file():
        return None
    h = hashlib.sha256()
    with yol.open("rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()[:16]


def ortam_ozeti() -> dict[str, Any]:
    """Ölçüm çıktısına gömülecek ortam bloğu."""
    bilgi: dict[str, Any] = {
        "git_commit": _git("rev-parse", "--short", "HEAD"),
        # Kirli ağaç, çıktının bir commit'e bağlanamadığı anlamına gelir:
        # ölçümü tekrar üretmek isteyen kişi aynı koda ulaşamaz.
        "git_kirli": bool(_git("status", "--porcelain")),
    }

    try:
        from sentinel.config import get_settings

        a = get_settings()
        bilgi["ayarlar"] = {ad: getattr(a, ad, None) for ad in ETKILI_AYARLAR}
    except Exception as e:  # ölçüm, ortam okunamadı diye durmamalı
        bilgi["ayarlar"] = f"okunamadı: {e}"

    surumler: dict[str, str] = {}
    for paket in ("torch", "ultralytics", "numpy", "lightgbm", "onnxruntime"):
        try:
            modul = __import__(paket)
            surumler[paket] = getattr(modul, "__version__", "?")
        except Exception:
            surumler[paket] = "yok"
    try:
        import torch

        surumler["cuda"] = torch.version.cuda or "yok"
        if torch.cuda.is_available():
            surumler["gpu"] = torch.cuda.get_device_name(0)
    except Exception as e:
        surumler["cuda"] = f"okunamadı: {e}"
    bilgi["surumler"] = surumler

    agirliklar = {}
    for ad in ("yolo26s.pt", "yolo26s-pose.pt"):
        o = _ozet(KOK / "models" / ad)
        if o:
            agirliklar[ad] = o
    if agirliklar:
        bilgi["model_ozetleri"] = agirliklar

    return bilgi
