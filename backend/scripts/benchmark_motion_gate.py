"""KADEME 0 hareket filtresinin etkinliğini ölçer.

Cevaplanan soru (PLAN.md §5.1, LITERATUR.md §O / S03):
    "Hareket filtresi gerçekten yükün yüzde kaçını eliyor?"

Bu, mimarinin temel varsayımıdır. Doğrulanmazsa 20 kamera hedefi
gerçekçi değildir. Çıktı `benchmarks/` altına JSON olarak yazılır —
staj raporunun ölçüm bölümüne doğrudan girecek.

Kullanım
--------
    uv run python scripts/benchmark_motion_gate.py                    # test kameraları
    uv run python scripts/benchmark_motion_gate.py --cameras cam-01 cam-09
    uv run python scripts/benchmark_motion_gate.py --all --frames 200
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from sentinel.config import settings
from sentinel.ingest.decoder import RtspDecoder, StreamClosedError, rtsp_url
from sentinel.ingest.motion_gate import GateReason, MotionGate

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"

# Sentetik kameralar: filtrenin uç davranışını doğrular
TEST_CAMERAS = ["cam-test-motion", "cam-test-chaos", "cam-test-static"]
FARM_CAMERAS = [f"cam-{i:02d}" for i in range(1, 21)]


def benchmark_camera(camera: str, frame_count: int, target_fps: float) -> dict[str, object]:
    """Tek kamerada filtreyi ölçer."""
    url = rtsp_url(settings.mediamtx_host, settings.mediamtx_rtsp_port, camera)
    gate = MotionGate(
        threshold=settings.motion_threshold,
        refresh_interval_s=float(settings.motion_refresh_interval_s),
    )

    reasons: Counter[str] = Counter()
    gate_times: list[float] = []
    ratios: list[float] = []
    decode_times: list[float] = []

    started = time.monotonic()
    last_tick = started

    try:
        with RtspDecoder(url, camera_id=camera, target_fps=target_fps) as decoder:
            for frame in decoder.frames(max_frames=frame_count):
                now = time.monotonic()
                decode_times.append((now - last_tick) * 1000.0)

                decision = gate.evaluate(frame.image, frame.timestamp)
                reasons[decision.reason.value] += 1
                gate_times.append(decision.elapsed_ms)
                ratios.append(decision.foreground_ratio)

                last_tick = time.monotonic()
            decoded_total = decoder.decoded_count
            emitted_total = decoder.emitted_count
    except StreamClosedError as exc:
        return {"camera": camera, "error": str(exc)}
    except Exception as exc:
        return {"camera": camera, "error": f"{type(exc).__name__}: {exc}"}

    total = sum(reasons.values())
    if total == 0:
        return {"camera": camera, "error": "hiç kare alınamadı"}

    # Isınma karelerini hariç tutarak gerçek eleme oranını hesapla
    scored = total - reasons[GateReason.WARMUP.value]
    idle = reasons[GateReason.IDLE.value]
    filtered_pct = (idle / scored * 100.0) if scored > 0 else 0.0

    wall = time.monotonic() - started
    return {
        "camera": camera,
        "frames_sampled": total,
        "frames_decoded": decoded_total,
        "decode_amplification": round(decoded_total / max(emitted_total, 1), 2),
        "wall_seconds": round(wall, 2),
        "effective_fps": round(total / wall, 2) if wall > 0 else 0,
        "reasons": dict(reasons),
        "filtered_pct": round(filtered_pct, 1),
        "passed_pct": round(100.0 - filtered_pct, 1),
        "gate_ms": {
            "mean": round(statistics.fmean(gate_times), 3),
            "p95": round(sorted(gate_times)[int(len(gate_times) * 0.95) - 1], 3),
            "max": round(max(gate_times), 3),
        },
        "foreground_ratio": {
            "mean": round(statistics.fmean(ratios), 5),
            "max": round(max(ratios), 5),
        },
        "loop_ms_mean": round(statistics.fmean(decode_times), 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Kademe 0 hareket filtresi ölçümü")
    parser.add_argument("--cameras", nargs="*", help="Ölçülecek kameralar")
    parser.add_argument("--all", action="store_true", help="20 kameralık çiftliğin tamamı")
    parser.add_argument("--frames", type=int, default=120, help="Kamera başına örneklenecek kare")
    parser.add_argument("--fps", type=float, default=None, help="Hedef örnekleme FPS'i")
    parser.add_argument("--no-save", action="store_true", help="JSON çıktısı yazma")
    args = parser.parse_args()

    if args.cameras:
        cameras = args.cameras
    elif args.all:
        cameras = TEST_CAMERAS + FARM_CAMERAS
    else:
        cameras = TEST_CAMERAS

    target_fps = args.fps if args.fps is not None else float(settings.target_fps)

    print(f"Kademe 0 ölçümü — {len(cameras)} kamera × {args.frames} kare @ {target_fps} FPS")
    print(f"Eşik: %{settings.motion_threshold * 100:.2f} ön plan · "
          f"yenileme: {settings.motion_refresh_interval_s} sn")
    print()
    header = f"{'KAMERA':<17} {'ELENEN':>8} {'GEÇEN':>7} {'FİLTRE ms':>10} {'FPS':>7}  GEREKÇE DAĞILIMI"
    print(header)
    print("-" * len(header))

    results: list[dict[str, object]] = []
    for camera in cameras:
        result = benchmark_camera(camera, args.frames, target_fps)
        results.append(result)

        if "error" in result:
            print(f"{camera:<17} {'HATA':>8}  {str(result['error'])[:60]}")
            continue

        reasons = result["reasons"]
        assert isinstance(reasons, dict)
        breakdown = " ".join(f"{k}={v}" for k, v in sorted(reasons.items()))
        gate_ms = result["gate_ms"]
        assert isinstance(gate_ms, dict)
        print(
            f"{camera:<17} {result['filtered_pct']:>7}% {result['passed_pct']:>6}% "
            f"{gate_ms['mean']:>10} {result['effective_fps']:>7}  {breakdown}"
        )

    ok = [r for r in results if "error" not in r]
    if ok:
        avg_filtered = statistics.fmean(float(r["filtered_pct"]) for r in ok)  # type: ignore[arg-type]
        avg_gate = statistics.fmean(float(r["gate_ms"]["mean"]) for r in ok)  # type: ignore[index]
        print()
        print(f"Ortalama eleme oranı : %{avg_filtered:.1f}")
        print(f"Ortalama filtre süresi: {avg_gate:.3f} ms/kare")
        print()
        print("Yorum: Kademe 1 (YOLO) maliyeti bu oranda azalır. "
              f"20 kamera × {target_fps:.0f} FPS = {20 * target_fps:.0f} kare/sn yerine "
              f"~{20 * target_fps * (1 - avg_filtered / 100):.0f} kare/sn tespit yükü.")

    if not args.no_save:
        BENCHMARKS.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = BENCHMARKS / f"motion_gate_{stamp}.json"
        out.write_text(
            json.dumps(
                {
                    "measured_at": datetime.now().isoformat(timespec="seconds"),
                    "config": {
                        "threshold": settings.motion_threshold,
                        "refresh_interval_s": settings.motion_refresh_interval_s,
                        "target_fps": target_fps,
                        "frames_per_camera": args.frames,
                    },
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nKaydedildi: {out.relative_to(PROJECT_ROOT)}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
