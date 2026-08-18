"""Boru hattında süre nereye gidiyor — CPU mu, GPU mu?

Neden bu ölçüm ÖNCE yapılıyor
-----------------------------
Boru hattı paralelleştirmesinin tüm iddiası şu: aşamalar seri
çalıştığı için toplam süre `CPU + GPU`, oysa örtüştürülürse
`max(CPU, GPU)` olur. Kazancın büyüklüğü **doğrudan bu ikisinin
oranına** bağlı:

    CPU %50 / GPU %50  →  2.0× kazanç  (paralelleştirmeye değer)
    CPU %80 / GPU %20  →  1.25× kazanç (zahmete değmez, başka yere bak)

P-18'in dersi tam buydu: "GPU darboğaz" varsayılmıştı, ölçüm GPU'nun
%0-5'te boş oturduğunu gösterdi ve iş tamamen başka yere yönlendi.
Aynı hatayı tersinden yapmamak için önce ölçüyoruz.

Ölçüm yöntemi — `cuda.synchronize()`
------------------------------------
CUDA çağrıları **asenkron**: `model(x)` hemen döner, GPU arka planda
çalışmaya devam eder. Bu yüzden normal bir `perf_counter` ölçümü
GPU süresini göremez — yalnızca çağrının kuyruğa girme süresini ölçer.

    t0 = perf_counter()
    cikti = model(x)          # hemen döner, GPU hâlâ çalışıyor
    t1 = perf_counter()       # ← GPU süresi buraya YANSIMAZ

`torch.cuda.synchronize()` GPU işi bitene kadar bekler. İki ölçümün
farkı gerçek GPU süresini verir.

Kullanım
--------
    uv run python scripts/benchmark_pipeline_split.py
    uv run python scripts/benchmark_pipeline_split.py --batch 8 --rounds 30
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import av
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

for _akis in (sys.stdout, sys.stderr):
    if hasattr(_akis, "reconfigure"):
        _akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from sentinel.config import settings  # noqa: E402
from sentinel.core.preprocess import letterbox  # noqa: E402
from sentinel.inference.tracker.botsort import BotSortTracker  # noqa: E402
from sentinel.inference.worker import build_detector, build_pose_estimator  # noqa: E402


def kareler_yukle(kameralar: list[str], adet: int) -> list[np.ndarray]:
    """Gerçek kamera karelerini model uzayında hazırlar.

    ⚠ Sentetik gürültü KULLANILMIYOR. Poz kademesinin maliyeti kadrajdaki
    KİŞİ SAYISINA bağlı; rastgele piksellerde kişi bulunmaz ve poz
    neredeyse bedava görünür. Ölçüm gerçek yükü yansıtmalı (P-15 dersi:
    izole ölçüm bileşenin kendi eğrisini verir, sistemdeki davranışını
    vermez).
    """
    cikti: list[np.ndarray] = []
    for kamera in kameralar:
        yol = PROJECT_ROOT / "data" / "videos" / f"{kamera}.mp4"
        if not yol.is_file():
            continue
        kap = av.open(str(yol))
        akis = kap.streams.video[0]
        for i, kare in enumerate(kap.decode(akis)):
            if len(cikti) >= adet:
                break
            if i % 13:  # dağıtık örnekleme
                continue
            hazir, _kutu = letterbox(kare.to_ndarray(format="bgr24"))
            cikti.append(hazir)
        kap.close()
        if len(cikti) >= adet:
            break
    return cikti


def olc(
    kareler: list[np.ndarray],
    batch: int,
    tur: int,
) -> dict[str, object]:
    """Her aşamada CPU ve GPU süresini ayrı ölçer."""
    import torch

    dedektor = build_detector(
        str(settings.detector_weights),
        backend=settings.detector_backend,
        device="cuda:0",
        half=True,
        imgsz=640,
        conf=settings.detector_conf_threshold,
    )
    poz = build_pose_estimator(str(settings.pose_weights), device="cuda:0", half=True)
    takipci = BotSortTracker(frame_rate=int(settings.target_fps))

    dedektor.warmup(batch)
    poz.warmup(settings.pose_crop_batch)

    olcumler: dict[str, list[float]] = {
        "tespit_cagri": [],
        "tespit_toplam": [],
        "poz_cagri": [],
        "poz_toplam": [],
        "takip": [],
    }
    kisi_sayilari: list[int] = []

    for t in range(tur):
        grup = [kareler[(t * batch + i) % len(kareler)] for i in range(batch)]

        # ── TESPİT ──
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        sonuclar = dedektor.detect(grup)
        t_cagri = time.perf_counter()  # çağrı döndü, GPU devam ediyor olabilir
        torch.cuda.synchronize()
        t_bitti = time.perf_counter()  # GPU gerçekten bitti

        olcumler["tespit_cagri"].append((t_cagri - t0) * 1000.0)
        olcumler["tespit_toplam"].append((t_bitti - t0) * 1000.0)
        kisi_sayilari.append(sum(len(s) for s in sonuclar))

        # ── POZ ──
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        poz.estimate(grup, sonuclar)
        t_cagri = time.perf_counter()
        torch.cuda.synchronize()
        t_bitti = time.perf_counter()

        olcumler["poz_cagri"].append((t_cagri - t0) * 1000.0)
        olcumler["poz_toplam"].append((t_bitti - t0) * 1000.0)

        # ── TAKİP (saf CPU) ──
        t0 = time.perf_counter()
        for i, tespitler in enumerate(sonuclar):
            takipci.update(f"cam-{i % 20 + 1:02d}", tespitler, time.time())
        olcumler["takip"].append((time.perf_counter() - t0) * 1000.0)

    poz.close()
    dedektor.close()

    def p50(ad: str) -> float:
        return round(statistics.median(olcumler[ad]), 2) if olcumler[ad] else 0.0

    tespit_toplam, poz_toplam = p50("tespit_toplam"), p50("poz_toplam")
    takip = p50("takip")

    # `synchronize` sonrası ölçülen süre GPU'nun bitmesini de kapsıyor.
    # Çağrının kendisi döndükten sonra kalan kısım = SAF GPU beklemesi.
    tespit_gpu = max(0.0, tespit_toplam - p50("tespit_cagri"))
    poz_gpu = max(0.0, poz_toplam - p50("poz_cagri"))

    toplam = tespit_toplam + poz_toplam + takip
    gpu = tespit_gpu + poz_gpu
    cpu = toplam - gpu

    return {
        "batch": batch,
        "tur": tur,
        "kare_basina_kisi": round(statistics.mean(kisi_sayilari) / batch, 2),
        "asamalar_ms": {
            "tespit": {
                "toplam": tespit_toplam,
                "gpu_beklemesi": round(tespit_gpu, 2),
                "cpu": round(tespit_toplam - tespit_gpu, 2),
            },
            "poz": {
                "toplam": poz_toplam,
                "gpu_beklemesi": round(poz_gpu, 2),
                "cpu": round(poz_toplam - poz_gpu, 2),
            },
            "takip": {"toplam": takip, "gpu_beklemesi": 0.0, "cpu": takip},
        },
        "batch_basina_ms": {
            "toplam": round(toplam, 2),
            "gpu": round(gpu, 2),
            "cpu": round(cpu, 2),
            "gpu_payi": round(gpu / toplam, 3) if toplam else 0.0,
        },
        "paralellestirme_tahmini": {
            "aciklama": (
                "Seri: CPU+GPU. Örtüşürse: max(CPU,GPU). "
                "Kazanç = (CPU+GPU) / max(CPU,GPU)"
            ),
            "simdiki_kare_basina_ms": round(toplam / batch, 2),
            "paralel_kare_basina_ms": round(max(cpu, gpu) / batch, 2),
            "beklenen_kazanc": round(toplam / max(cpu, gpu), 2) if max(cpu, gpu) else 0.0,
            "simdiki_tavan_fps": round(1000.0 / (toplam / batch), 1) if toplam else 0.0,
            "paralel_tavan_fps": (
                round(1000.0 / (max(cpu, gpu) / batch), 1) if max(cpu, gpu) else 0.0
            ),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="CPU/GPU süre payı ölçümü")
    ap.add_argument("--batch", type=int, nargs="*", default=[4, 8])
    ap.add_argument("--rounds", type=int, default=25)
    ap.add_argument(
        "--cameras", nargs="*", default=["cam-09", "cam-10", "cam-14", "cam-01"]
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    print("BORU HATTI CPU/GPU PAYI")
    print("=" * 64)
    print("Kareler yükleniyor (gerçek kamera görüntüsü)...")
    kareler = kareler_yukle(args.cameras, max(args.batch) * 4)
    if not kareler:
        print("HATA: kare bulunamadı", file=sys.stderr)
        return 1
    print(f"  {len(kareler)} kare hazır\n")

    rapor: dict[str, object] = {
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "phase": "Faz 1 / Gün 15",
        "description": "Paralelleştirme kararı için CPU/GPU süre payı",
        "cameras": args.cameras,
        "olcumler": [],
    }

    for batch in args.batch:
        print(f"[batch {batch}] ölçülüyor...")
        sonuc = olc(kareler, batch, args.rounds)
        rapor["olcumler"].append(sonuc)  # type: ignore[union-attr]

        b = sonuc["batch_basina_ms"]  # type: ignore[index]
        p = sonuc["paralellestirme_tahmini"]  # type: ignore[index]
        print(f"  kare başına ~{sonuc['kare_basina_kisi']} kişi")  # type: ignore[index]
        for ad, v in sonuc["asamalar_ms"].items():  # type: ignore[union-attr,index]
            print(
                f"    {ad:8} toplam {v['toplam']:7.2f} ms  ·  "
                f"GPU {v['gpu_beklemesi']:7.2f}  ·  CPU {v['cpu']:7.2f}"
            )
        print(
            f"    {'TOPLAM':8} {b['toplam']:7.2f} ms  ·  "
            f"GPU {b['gpu']:7.2f}  ·  CPU {b['cpu']:7.2f}"
            f"   (GPU payı %{b['gpu_payi'] * 100:.0f})"
        )
        print(
            f"    tavan: {p['simdiki_tavan_fps']} FPS  →  "
            f"paralel {p['paralel_tavan_fps']} FPS "
            f"({p['beklenen_kazanc']}× beklenen kazanç)\n"
        )

    cikti = (
        args.out or PROJECT_ROOT / "benchmarks" / f"pipeline_split_{datetime.now():%Y%m%d}.json"
    ).resolve()
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Kaydedildi: {cikti}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
