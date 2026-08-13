"""Video çözme kapasitesini ölçer: CPU vs NVDEC.

Cevaplanan soru:
    "20 kamerayı beslemek için kaç CPU çekirdeği gerekiyor?
     Donanımsal çözücü (NVDEC) kazandırır mı?"

⚠ ÖLÇÜM DÜZENEĞİ UYARISI
------------------------
Bu betik **yerel dosyadan** ölçer, RTSP akışından DEĞİL. Sebebi önemli:
MediaMTX akışı gerçek zamanlı 25 FPS hızında yayınlar, daha hızlı okumak
mümkün değildir. RTSP'den ölçmek, decode kapasitesini değil akışın hız
sınırını ölçer. Bu hata bir kez yapıldı — bkz. docs/report/problems.md P-07.

Kullanım
--------
    uv run python scripts/benchmark_decode.py
    uv run python scripts/benchmark_decode.py --video ../data/videos/cam-09.mp4
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import av
import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"
DEFAULT_VIDEO = PROJECT_ROOT / "data" / "videos" / "cam-01.mp4"

TARGET_STREAMS = 20
STREAM_FPS = 25


def _decode(
    path: Path,
    *,
    frames: int,
    hwaccel: Any = None,
    threads: str = "NONE",
    convert: bool = True,
) -> float:
    """Verilen ayarlarla çözme hızını (FPS) ölçer."""
    container = av.open(str(path), hwaccel=hwaccel) if hwaccel else av.open(str(path))
    try:
        stream = container.streams.video[0]
        stream.thread_type = threads
        if threads == "NONE":
            stream.codec_context.thread_count = 1

        count = 0
        started = time.perf_counter()
        for frame in container.decode(stream):
            if convert:
                frame.to_ndarray(format="bgr24")
            count += 1
            if count >= frames:
                break
        elapsed = time.perf_counter() - started
    finally:
        container.close()
    return count / elapsed if elapsed > 0 else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Çözme kapasitesi ölçümü")
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--frames", type=int, default=400)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    if not args.video.is_file():
        print(f"Video bulunamadı: {args.video}")
        return 1

    cv2.setNumThreads(1)
    with av.open(str(args.video)) as probe:
        vs = probe.streams.video[0]
        info = f"{vs.codec_context.width}×{vs.codec_context.height} {vs.codec_context.name}"

    print(f"Kaynak : {args.video.name}  ({info})")
    print(f"Kare   : {args.frames}\n")

    results: dict[str, float] = {}
    header = f"{'YÖNTEM':<34} {'ÇÖZME':>10} {'ÇÖZME+BGR':>12}"
    print(header)
    print("-" * len(header))

    for label, threads in [("CPU tek iş parçacığı", "NONE"), ("CPU çoklu iş parçacığı", "AUTO")]:
        raw = _decode(args.video, frames=args.frames, threads=threads, convert=False)
        bgr = _decode(args.video, frames=args.frames, threads=threads, convert=True)
        results[f"{label} (çözme)"] = raw
        results[f"{label} (çözme+bgr)"] = bgr
        print(f"{label:<34} {raw:>9.1f}  {bgr:>11.1f}")

    try:
        from av.codec.hwaccel import HWAccel

        hw = HWAccel(device_type="cuda", allow_software_fallback=False)
        raw = _decode(args.video, frames=args.frames, hwaccel=hw, threads="AUTO", convert=False)
        hw = HWAccel(device_type="cuda", allow_software_fallback=False)
        bgr = _decode(args.video, frames=args.frames, hwaccel=hw, threads="AUTO", convert=True)
        results["NVDEC (çözme)"] = raw
        results["NVDEC (çözme+bgr)"] = bgr
        print(f"{'NVDEC (cuda hwaccel)':<34} {raw:>9.1f}  {bgr:>11.1f}")
    except Exception as exc:
        print(f"{'NVDEC':<34} kullanılamıyor: {type(exc).__name__}")

    single = results.get("CPU tek iş parçacığı (çözme+bgr)", 0.0)
    needed = TARGET_STREAMS * STREAM_FPS
    print()
    print(f"{TARGET_STREAMS} kamera × {STREAM_FPS} FPS = {needed} FPS çözme kapasitesi gerekiyor")
    if single > 0:
        print(f"Tek çekirdek (BGR dahil): {single:.0f} FPS  →  gereken çekirdek: {needed / single:.1f}")
    print()
    print("Not: sürenin büyük kısmı H.264 çözmede değil, YUV→BGR renk")
    print("dönüşümünde geçiyor. Ölçüm yerel dosyadan yapılmıştır (RTSP'den")
    print("ölçmek akışın gerçek zamanlı hız sınırını ölçer, kapasiteyi değil).")

    if not args.no_save:
        BENCHMARKS.mkdir(parents=True, exist_ok=True)
        out = BENCHMARKS / f"decode_{datetime.now():%Y%m%d-%H%M%S}.json"
        out.write_text(
            json.dumps(
                {
                    "measured_at": datetime.now().isoformat(timespec="seconds"),
                    "video": args.video.name,
                    "video_info": info,
                    "frames": args.frames,
                    "fps": {k: round(v, 1) for k, v in results.items()},
                    "cores_needed_for_20_cams": round(needed / single, 2) if single else None,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nKaydedildi: {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
