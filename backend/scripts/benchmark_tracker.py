"""Takipçi parametrelerinin kimlik kararlılığına etkisini ölçer.

Cevaplanan soru (PLAN.md §6.1 · CLAUDE.md Gün 12):
    "İzlerin %20'si tek kare yaşayıp ölüyor. Sebep eşleştirme
     parametreleri mi, yoksa sahnenin kendisi mi?"

Neden kontrollü deney şart
--------------------------
Canlı sistemde parametre değiştirip bakmak yanıltıcı: sahne değişiyor,
kalabalık değişiyor, kare hızı değişiyor. Aynı tespit dizisini farklı
ayarlarla aynı takipçiden geçirmek tek dürüst karşılaştırmadır.

Bu yüzden burada tespitler **bir kez** çıkarılıp belleğe alınıyor,
sonra her ayar aynı diziyi işliyor. Tek değişen parametre.

Ölçülen
-------
· iz sayısı            — az olması iyi (aynı kişi tek kimlik almalı)
· medyan iz ömrü       — çok olması iyi
· tek kare yaşayan iz  — az olması iyi
· kare başına iz       — sahnedeki kişi sayısına yakın olmalı

⚠ Gerçek referans (ground truth) YOK, dolayısıyla bu bir "doğruluk"
ölçümü değil **tutarlılık** ölçümüdür. Gerçek ID-switch sayısı için
MOT17 gerekir (PLAN.md §7.2) — Faz 5'e bırakıldı.

Kullanım
--------
    uv run python scripts/benchmark_tracker.py
    uv run python scripts/benchmark_tracker.py --camera cam-09 --frames 300
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

import av
import numpy as np

from sentinel.core import preprocess
from sentinel.inference.detector.base import Detection
from sentinel.inference.detector.yolo import UltralyticsDetector
from sentinel.inference.tracker.botsort import BotSortTracker, default_args

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"
VIDEO_DIR = PROJECT_ROOT / "data" / "videos"

# Kaynak 25 FPS; sistemde 4 FPS örnekliyoruz → her 6. kare.
SAMPLE_EVERY = 6


def collect_detections(
    camera: str, frames: int, detector: UltralyticsDetector
) -> list[list[Detection]]:
    """Tespitleri bir kez çıkarır — tüm ayarlar aynı diziyi kullanacak."""
    path = VIDEO_DIR / f"{camera}.mp4"
    if not path.is_file():
        raise SystemExit(f"Video yok: {path}")

    images: list[np.ndarray] = []
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        for index, frame in enumerate(container.decode(stream)):
            if index % SAMPLE_EVERY:
                continue
            # Canlı sistemle AYNI ön işleme — letterbox 640.
            # Farklı verirsek tespitler de farklı olur ve ölçüm
            # takipçiyi değil ön işlemeyi kıyaslamış olur.
            prepared, _ = preprocess.letterbox(frame.to_ndarray(format="bgr24"))
            images.append(prepared)
            if len(images) >= frames:
                break

    detections: list[list[Detection]] = []
    for start in range(0, len(images), 8):
        detections.extend(detector.detect(images[start : start + 8]))
    return detections


def run_tracker(
    detections: list[list[Detection]], *, fps: int, **kwargs: Any
) -> dict[str, Any]:
    """Tespit dizisini verilen ayarlarla takipçiden geçirir."""
    tracker = BotSortTracker(args=default_args(**kwargs), frame_rate=fps)

    # Kimlik başına kaç karede görüldü
    seen: dict[int, int] = {}
    per_frame: list[int] = []
    with_id = 0
    total_out = 0
    interval = 1.0 / fps

    for index, frame_detections in enumerate(detections):
        tracks = tracker.update("bench", frame_detections, index * interval)
        per_frame.append(len(tracks))
        total_out += len(tracks)
        for track in tracks:
            if track.track_id >= 0:
                with_id += 1
                seen[track.track_id] = seen.get(track.track_id, 0) + 1

    lifetimes = sorted(seen.values())
    if not lifetimes:
        return {"error": "hiç iz oluşmadı"}

    return {
        "tracks": len(lifetimes),
        "median_lifetime": lifetimes[len(lifetimes) // 2],
        "mean_lifetime": round(statistics.fmean(lifetimes), 1),
        "single_frame_pct": round(
            sum(1 for v in lifetimes if v == 1) / len(lifetimes) * 100, 1
        ),
        "short_lived_pct": round(
            sum(1 for v in lifetimes if v <= 3) / len(lifetimes) * 100, 1
        ),
        "long_lived_pct": round(
            sum(1 for v in lifetimes if v > 21) / len(lifetimes) * 100, 1
        ),
        "tracks_per_frame": round(statistics.fmean(per_frame), 2),
        # ⚠ GİZLİ BEDEL: kimlik alan tespitlerin oranı.
        # Parametreleri sıkılaştırmak parçalanmayı düşürebilir ama
        # tespitlerin bir kısmı hiç kimlik alamaz — o kişiler zamansal
        # analizin dışında kalır. Yalnızca parçalanmaya bakmak yanıltıcı.
        "id_coverage_pct": round(with_id / total_out * 100, 1) if total_out else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Takipçi parametre ölçümü")
    parser.add_argument("--camera", default="cam-09")
    parser.add_argument("--frames", type=int, default=250)
    parser.add_argument("--fps", type=int, default=4)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    print(f"Tespitler çıkarılıyor: {args.camera}, {args.frames} kare (~{args.fps} FPS)")
    detector = UltralyticsDetector(
        PROJECT_ROOT / "models" / "yolo26s.pt", device=args.device, half=True, imgsz=640
    )
    detector.warmup(8)
    detections = collect_detections(args.camera, args.frames, detector)
    detector.close()

    total = sum(len(d) for d in detections)
    print(f"{len(detections)} kare · {total} tespit · kare başına {total / len(detections):.1f}\n")

    # Tek değişkenli taramalar: her seferinde YALNIZCA bir parametre değişiyor.
    scenarios: list[tuple[str, dict[str, Any]]] = [
        # ⚠ match_thresh bir MESAFE eşiğidir, benzerlik değil.
        # Ultralytics maliyeti `1 - IoU` diye hesaplıyor ve eşleşmeyi
        # `maliyet < eşik` ise kabul ediyor. Yani:
        #     match_thresh 0.9  →  IoU > 0.1 yeterli  →  GEVŞEK
        #     match_thresh 0.6  →  IoU > 0.4 gerekli  →  SIKI
        # İlk koşuda etiketleri ters yazmıştım; kaynak koda bakınca
        # düzeldi. Sezgiye ters bir isimlendirme, dikkat.
        ("varsayılan (match 0.8 → IoU>0.2)", {}),
        ("SIKI eşleştirme (match 0.6 → IoU>0.4)", {"match_thresh": 0.6}),
        ("GEVŞEK eşleştirme (match 0.9 → IoU>0.1)", {"match_thresh": 0.9}),
        ("new_track_thresh 0.5", {"new_track_thresh": 0.5}),
        ("new_track_thresh 0.7", {"new_track_thresh": 0.7}),
        ("track_buffer 60", {"track_buffer": 60}),
        ("GEVŞEK + new_track 0.5", {"match_thresh": 0.9, "new_track_thresh": 0.5}),
        ("GEVŞEK + new_track 0.7", {"match_thresh": 0.9, "new_track_thresh": 0.7}),
    ]

    header = (
        f"{'AYAR':<38} {'iz':>5} {'medyan':>7} {'tekKare':>8} "
        f"{'kısa':>6} {'uzun':>6} {'kimlik':>8}"
    )
    print(header)
    print("-" * len(header))

    results: list[dict[str, Any]] = []
    for label, kwargs in scenarios:
        out = run_tracker(detections, fps=args.fps, **kwargs)
        out["label"] = label
        out["params"] = kwargs
        results.append(out)
        if "error" in out:
            print(f"{label:<38} {out['error']}")
            continue
        print(
            f"{label:<38} {out['tracks']:>5} {out['median_lifetime']:>7} "
            f"{out['single_frame_pct']:>7.1f}% {out['short_lived_pct']:>5.1f}% "
            f"{out['long_lived_pct']:>5.1f}% {out['id_coverage_pct']:>7.1f}%"
        )

    valid = [r for r in results if "error" not in r]
    best = min(valid, key=lambda r: r["single_frame_pct"]) if valid else None
    if best:
        base = valid[0]
        print(f"\nEn az tek-kare izi üreten ayar: {best['label']}")
        print(
            f"  tek kare  %{base['single_frame_pct']:.1f} → %{best['single_frame_pct']:.1f}"
            f"   ·  medyan ömür {base['median_lifetime']} → {best['median_lifetime']}"
            f"   ·  iz sayısı {base['tracks']} → {best['tracks']}"
        )

    if args.no_save:
        return 0
    BENCHMARKS.mkdir(exist_ok=True)
    out_path = BENCHMARKS / f"tracker_{datetime.now():%Y%m%d-%H%M%S}.json"
    out_path.write_text(
        json.dumps(
            {
                "measured_at": datetime.now().isoformat(timespec="seconds"),
                "phase": "Faz 1 / Gün 12",
                "description": "Takipçi parametrelerinin kimlik kararlılığına etkisi",
                "method": (
                    "Tespitler BİR KEZ çıkarılıp belleğe alındı; her ayar aynı "
                    "diziyi işledi. Tek değişen parametre — sahne, kalabalık ve "
                    "kare hızı sabit."
                ),
                "caveat": (
                    "Gerçek referans (ground truth) yok; bu bir DOĞRULUK değil "
                    "TUTARLILIK ölçümüdür. Gerçek ID-switch için MOT17 gerekir."
                ),
                "config": {
                    "camera": args.camera,
                    "frames": len(detections),
                    "detections": total,
                    "fps": args.fps,
                },
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nKaydedildi: {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
