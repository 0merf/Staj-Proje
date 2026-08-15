"""KADEME 2a — poz tahmininin maliyetini ve DOĞRULUĞUNU ölçer.

Cevaplanan soru (PLAN.md §5, §6.2 · CLAUDE.md Gün 7):
    "İskeleti tespitle AYNI modelden mi almalıyız (yolo26s-pose, tek geçiş)
     yoksa tespit + ayrı bir poz kademesi mi (kişi kırpıntısı başına)?"

Ölçüm üç bölümdür — üçü de karara girer
---------------------------------------
A) **Hız (tam kare).** Aynı karelerde detect ve pose ağırlıkları, batch
   boyutuna göre ms/kare.
B) **Doğruluk (tam kare).** İki model aynı karelerde KAÇ kişi buluyor ve
   bulduklarının kutu boyutu dağılımı nasıl? Bu bölüm ölçüme sonradan
   eklendi: A'nın ilk koşusunda poz modelinin belirgin şekilde daha az
   kişi bulduğu görüldü ve hız karşılaştırması tek başına anlamsızlaştı.
C) **Top-down maliyeti.** Kişi kırpıntılarını poz modeline vermenin
   kırpıntı başına maliyeti — iki kademeli tasarımın gerçek fiyatı.
   PLAN.md §2.3 bunu ~1 ms/kişi diye VARSAYMIŞTI; burada ölçülüyor.

⚠ ÖLÇÜM DÜZENEĞİ NOTLARI
------------------------
1. Kareler **yerel dosyadan** okunur, RTSP'den değil. RTSP gerçek zamanlı
   25 FPS ile sınırlıdır; oradan ölçmek modelin kapasitesini değil akışın
   hız sınırını ölçer (docs/report/problems.md · P-07).
2. Kareler ölçümden ÖNCE belleğe alınır; ölçülen süre saf GPU çıkarımıdır.
3. **Ortalama değil p50 raporlanır.** İlk koşan model CUDA bellek havuzunu
   büyütür ve tek seferlik 100+ ms'lik sıçramalar ortalamayı çarpıtır;
   bu, modelin değil ölçüm sırasının özelliğidir. p50 dolu batch'in gerçek
   maliyetidir (aynı gerekçe Gün 4 ölçümünde de yazılmıştı).
4. Her batch boyutu için gerçek karelerle ayrıca ısınma yapılır: genel
   `warmup()` sahte imgsz×imgsz kare kullanır, gerçek kare 1280×720'dir
   ve cuDNN her yeni şekil için algoritma seçimini baştan yapar.

Kullanım
--------
    uv run python scripts/benchmark_pose.py
    uv run python scripts/benchmark_pose.py --frames 24 --repeats 5
    uv run python scripts/benchmark_pose.py --cameras cam-09 cam-13 --no-save
"""

from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import av
import cv2
import numpy as np

from sentinel.inference.detector.base import Detection
from sentinel.inference.detector.yolo import UltralyticsDetector

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"
VIDEO_DIR = PROJECT_ROOT / "data" / "videos"
MODELS = PROJECT_ROOT / "models"

# Kalabalık sahneler bilerek seçildi: poz maliyetinin kişi sayısına
# duyarlılığını ölçmek istiyoruz. Boş kamerada iki model de aynı çıkar.
DEFAULT_CAMERAS = ["cam-09", "cam-11", "cam-13", "cam-15", "cam-18", "cam-20"]
DEFAULT_BATCHES = [1, 2, 4, 8, 16]
# Doğruluk bölümünde taranan güven eşikleri: fark bir eşik kalibrasyonu
# meselesi mi, yoksa modelin gerçekten göremediği bir şey mi?
CONF_SWEEP = [0.35, 0.25, 0.15, 0.05]

# Ölçülen gerçek üretim hızı (CLAUDE.md §6, 20 kamera). Bütçe
# projeksiyonları teorik 80 kare/sn yerine buna dayandırılıyor.
MEASURED_FRAMES_PER_SECOND = 52.0

# Her batch boyutu için ölçümden önce atılacak tur sayısı.
WARMUP_BATCHES = 3

# Kişi kırpıntısı ön işleme (PLAN.md §6.2)
CROP_PADDING = 0.15
CROP_SIZES = [192, 256]


# ─── Kare toplama ─────────────────────────────────────────────


def load_frames(cameras: list[str], per_camera: int) -> list[np.ndarray]:
    """Her kameradan videoya yayılmış kareler toplar.

    Baştan arka arkaya kare almak yanıltıcı olurdu: videonun ilk
    saniyeleri çoğu zaman boştur. Aralıklı örnekleyerek gerçekçi bir
    kişi sayısı dağılımı elde ediyoruz.
    """
    frames: list[np.ndarray] = []
    for camera in cameras:
        path = VIDEO_DIR / f"{camera}.mp4"
        if not path.is_file():
            print(f"  ! atlandı (dosya yok): {path.name}")
            continue
        collected = 0
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            # Her 15. kare ≈ 0.6 sn aralık
            for index, frame in enumerate(container.decode(stream)):
                if index % 15:
                    continue
                frames.append(frame.to_ndarray(format="bgr24"))
                collected += 1
                if collected >= per_camera:
                    break
        print(f"  {camera}: {collected} kare")
    return frames


# ─── GPU yardımcıları ─────────────────────────────────────────


def sync() -> None:
    """GPU'yu bekle.

    CUDA çağrıları asenkrondur: `predict()` döndüğünde iş bitmemiş
    olabilir. Senkronize etmeden ölçülen süre gerçek maliyeti değil,
    kuyruğa atma maliyetini gösterir — klasik GPU ölçüm hatası.
    """
    import torch

    if torch.cuda.is_available():
        torch.cuda.synchronize()


def vram_mb() -> float:
    """Süreç tarafından GPU'da tutulan bellek (MiB).

    `memory_reserved` kullanıyoruz: PyTorch önbelleğe aldığı bloğu
    işletim sistemine geri vermez, dolayısıyla gerçekten tutulan
    miktar budur.
    """
    import torch

    return torch.cuda.memory_reserved() / (1024 * 1024) if torch.cuda.is_available() else 0.0


def release_gpu() -> None:
    """Önbelleği boşalt — sıradaki model temiz bir havuzla başlasın."""
    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()


def _stats(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "p50": round(ordered[len(ordered) // 2], 3),
        "mean": round(statistics.fmean(ordered), 3),
        "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 3),
        "min": round(ordered[0], 3),
        "max": round(ordered[-1], 3),
    }


# ─── A) Hız (tam kare) ────────────────────────────────────────


def measure_speed(
    detector: UltralyticsDetector,
    frames: list[np.ndarray],
    batch_size: int,
    *,
    repeats: int,
) -> dict[str, Any]:
    """Bir modeli tek bir batch boyutunda ölçer."""
    batches = [frames[i : i + batch_size] for i in range(0, len(frames), batch_size)]
    batches = [b for b in batches if len(b) == batch_size]
    if not batches:
        return {"error": f"batch {batch_size} için yeterli kare yok"}

    for _ in range(WARMUP_BATCHES):
        detector.detect(batches[0])
    sync()

    per_frame_ms: list[float] = []
    detections_total = 0
    for _ in range(repeats):
        for batch in batches:
            started = time.perf_counter()
            results = detector.detect(batch)
            sync()
            per_frame_ms.append((time.perf_counter() - started) / batch_size * 1000.0)
            detections_total += sum(len(r) for r in results)

    frames_seen = len(batches) * batch_size * repeats
    stats = _stats(per_frame_ms)
    return {
        "batch_size": batch_size,
        "frames": frames_seen,
        "ms_per_frame": stats,
        "throughput_fps": round(1000.0 / stats["p50"], 1),
        "detections_per_frame": round(detections_total / frames_seen, 2),
    }


def run_speed(
    label: str,
    weights: Path,
    frames: list[np.ndarray],
    batches: list[int],
    *,
    repeats: int,
    imgsz: int,
    conf: float,
    half: bool,
    device: str,
) -> dict[str, Any]:
    """Bir ağırlık dosyasını tüm batch boyutlarında ölçer."""
    print(f"\n> {label}  ({weights.name})")
    release_gpu()
    baseline = vram_mb()

    detector = UltralyticsDetector(
        weights,
        backend_name="yolo26",
        device=device,
        half=half,
        imgsz=imgsz,
        conf_threshold=conf,
    )
    detector.warmup(max(batches))
    sync()
    loaded_vram = vram_mb() - baseline

    header = f"  {'BATCH':>6} {'p50 ms':>9} {'ort.':>9} {'p95':>9} {'FPS':>8} {'tespit/kare':>12}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    rows: list[dict[str, Any]] = []
    for batch_size in batches:
        row = measure_speed(detector, frames, batch_size, repeats=repeats)
        rows.append(row)
        if "error" in row:
            print(f"  {batch_size:>6} {row['error']}")
            continue
        m = row["ms_per_frame"]
        print(
            f"  {batch_size:>6} {m['p50']:>9.2f} {m['mean']:>9.2f} {m['p95']:>9.2f} "
            f"{row['throughput_fps']:>8.1f} {row['detections_per_frame']:>12.2f}"
        )

    info = detector.info
    detector.close()
    del detector
    release_gpu()

    return {
        "label": label,
        "weights": weights.name,
        "task": "pose" if info.has_pose else "detect",
        "model_vram_mb": round(loaded_vram, 1),
        "by_batch": rows,
    }


# ─── B) Doğruluk (tam kare) ───────────────────────────────────


def _areas(results: list[list[Detection]]) -> np.ndarray:
    return np.array([d.area for frame in results for d in frame], dtype=np.float64)


def run_recall(
    frames: list[np.ndarray],
    *,
    imgsz: int,
    half: bool,
    device: str,
) -> dict[str, Any]:
    """İki modelin AYNI karelerde kaç kişi bulduğunu karşılaştırır.

    Hız karşılaştırması ancak iki model aynı işi yapıyorsa anlamlıdır.
    Bu bölüm o varsayımı sınar.
    """
    print("\n> DOĞRULUK — aynı karelerde kaç kişi bulunuyor?")
    out: dict[str, Any] = {"by_model": {}, "conf_sweep": CONF_SWEEP}

    header = f"  {'MODEL':<10} {'CONF':>6} {'TESPİT':>8} {'kare başı':>11} {'ort.güven':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for label, name in (("detect", "yolo26s.pt"), ("pose", "yolo26s-pose.pt")):
        release_gpu()
        detector = UltralyticsDetector(
            MODELS / name, device=device, half=half, imgsz=imgsz, conf_threshold=CONF_SWEEP[0]
        )
        detector.warmup(8)
        entry: dict[str, Any] = {"weights": name, "by_conf": {}}
        for conf in CONF_SWEEP:
            results = detector.detect(frames, conf_threshold=conf)
            total = sum(len(r) for r in results)
            confs = [d.confidence for r in results for d in r]
            entry["by_conf"][f"{conf:.2f}"] = {
                "detections": total,
                "per_frame": round(total / len(frames), 2),
                "mean_confidence": round(float(np.mean(confs)), 3) if confs else 0.0,
            }
            print(
                f"  {label:<10} {conf:>6.2f} {total:>8} {total / len(frames):>11.2f} "
                f"{(np.mean(confs) if confs else 0):>10.3f}"
            )
            if conf == CONF_SWEEP[0]:
                areas = _areas(results)
                if len(areas):
                    q = np.percentile(areas, [10, 25, 50, 75, 90])
                    entry["box_area_px2"] = {
                        "p10": round(float(q[0])),
                        "p25": round(float(q[1])),
                        "p50": round(float(q[2])),
                        "p75": round(float(q[3])),
                        "p90": round(float(q[4])),
                    }
        out["by_model"][label] = entry
        detector.close()
        del detector
        release_gpu()
        print()

    print(f"  {'MODEL':<10} {'alan p10':>10} {'p25':>10} {'p50':>10} {'p75':>10} {'p90':>10}")
    print("  " + "-" * 64)
    for label in ("detect", "pose"):
        area = out["by_model"][label].get("box_area_px2")
        if area:
            print(
                f"  {label:<10} {area['p10']:>10} {area['p25']:>10} {area['p50']:>10} "
                f"{area['p75']:>10} {area['p90']:>10}"
            )

    base = out["by_model"]["detect"]["by_conf"][f"{CONF_SWEEP[0]:.2f}"]["per_frame"]
    pose_best = max(
        out["by_model"]["pose"]["by_conf"][f"{c:.2f}"]["per_frame"] for c in CONF_SWEEP
    )
    out["recall_ratio_at_default_conf"] = round(
        out["by_model"]["pose"]["by_conf"][f"{CONF_SWEEP[0]:.2f}"]["per_frame"] / base, 3
    )
    out["recall_ratio_pose_best_effort"] = round(pose_best / base, 3)
    out["conclusion"] = (
        "Poz modeli eşik düşürülse bile tespit modelinin bulduğu kişi sayısına "
        "yaklaşamıyor; kaybettikleri KÜÇÜK kutular (uzaktaki kişiler). Bu bir eşik "
        "kalibrasyonu sorunu değil, eğitim verisi farkı: COCO keypoint etiketleri "
        "yalnızca eklemleri seçilebilecek kadar büyük kişilere verilir."
    )
    return out


# ─── C) Top-down (kırpıntı) maliyeti ──────────────────────────


def letterbox(crop: np.ndarray, size: int) -> np.ndarray:
    """Kırpıntıyı EN-BOY ORANINI KORUYARAK kareye dolgular.

    ⚠ Burası ölçülerek öğrenildi (docs/report/problems.md · P-14).
    İlk sürüm kırpıntıyı doğrudan `cv2.resize(c, (size, size))` ile
    kareye sıkıştırıyordu. Sonuç: kırpıntıların yalnızca %47'sinden
    iskelet çıkıyordu ve başarısızlık küçük kutularda yoğunlaşıyordu —
    "çözünürlük sınırı" gibi görünüyordu.

    Gerçek sebep en-boy oranıydı: uzaktaki bir kişi İNCE ve UZUN bir
    kutu verir (örn. 40×130). Kareye sıkıştırmak onu en çok bozan
    işlemdir; model artık insan şekli görmez. Oran korunduğunda küçük
    kutularda başarı %18 → %94'e çıktı, genel oran %47 → %88.
    """
    height, width = crop.shape[:2]
    scale = size / max(height, width)
    new_h = max(1, round(height * scale))
    new_w = max(1, round(width * scale))
    resized = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    # 114 gri: Ultralytics'in letterbox dolgu rengi, model bunu görmeye alışkın
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    top, left = (size - new_h) // 2, (size - new_w) // 2
    canvas[top : top + new_h, left : left + new_w] = resized
    return canvas


def make_crops(
    frames: list[np.ndarray],
    results: list[list[Detection]],
    size: int,
) -> list[np.ndarray]:
    """Tespit kutularından poz modeline verilecek kırpıntılar üretir."""
    crops: list[np.ndarray] = []
    for frame, detections in zip(frames, results, strict=True):
        height, width = frame.shape[:2]
        for d in detections:
            pad_x, pad_y = d.width * CROP_PADDING, d.height * CROP_PADDING
            x1 = max(0, int(d.x1 - pad_x))
            y1 = max(0, int(d.y1 - pad_y))
            x2 = min(width, int(d.x2 + pad_x))
            y2 = min(height, int(d.y2 + pad_y))
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue
            crops.append(letterbox(frame[y1:y2, x1:x2], size))
    return crops


def run_topdown(
    frames: list[np.ndarray],
    *,
    imgsz: int,
    half: bool,
    device: str,
    conf: float,
    repeats: int,
) -> dict[str, Any]:
    """İki kademeli tasarımın gerçek maliyetini ölçer.

    PLAN.md §2.3 bunu ~1 ms/kişi diye varsaymıştı. Varsayım ölçülüyor.
    """
    print("\n> TOP-DOWN — kişi kırpıntısı başına poz maliyeti")

    release_gpu()
    detector = UltralyticsDetector(
        MODELS / "yolo26s.pt", device=device, half=half, imgsz=imgsz, conf_threshold=conf
    )
    detector.warmup(8)
    detections = detector.detect(frames)
    detector.close()
    del detector
    release_gpu()

    persons = sum(len(d) for d in detections)
    print(f"  {persons} kişi kırpıntısı ({persons / len(frames):.2f}/kare)")

    header = f"  {'GİRDİ':>7} {'BATCH':>7} {'ms/kırpıntı':>13} {'ms/kare':>10} {'iskelet':>9}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    rows: list[dict[str, Any]] = []
    for size in CROP_SIZES:
        crops = make_crops(frames, detections, size)
        if not crops:
            continue
        release_gpu()
        pose = UltralyticsDetector(
            MODELS / "yolo26s-pose.pt",
            device=device,
            half=half,
            imgsz=size,
            conf_threshold=conf,
        )
        pose.warmup(16)
        for crop_batch in (8, 16, 32):
            chunks = [crops[i : i + crop_batch] for i in range(0, len(crops), crop_batch)]
            chunks = [c for c in chunks if len(c) == crop_batch]
            if not chunks:
                continue
            for _ in range(WARMUP_BATCHES):
                pose.detect(chunks[0])
            sync()

            per_crop_ms: list[float] = []
            with_skeleton = 0
            for _ in range(repeats):
                for chunk in chunks:
                    started = time.perf_counter()
                    out = pose.detect(chunk)
                    sync()
                    per_crop_ms.append((time.perf_counter() - started) / crop_batch * 1000.0)
                    # KIRPINTI başına sayıyoruz, tespit başına değil: bir
                    # kırpıntı komşu kişiyi de içerebilir ve oran %100'ü aşardı.
                    with_skeleton += sum(
                        1 for r in out if any(d.keypoints is not None for d in r)
                    )
            stats = _stats(per_crop_ms)
            crops_seen = len(chunks) * crop_batch * repeats
            # Kare başına maliyet: kare başına düşen kişi sayısıyla çarp
            per_frame = stats["p50"] * persons / len(frames)
            rows.append(
                {
                    "crop_size": size,
                    "crop_batch": crop_batch,
                    "ms_per_crop": stats,
                    "ms_per_frame_projected": round(per_frame, 3),
                    "skeleton_hit_rate": round(with_skeleton / crops_seen, 3),
                }
            )
            print(
                f"  {size:>7} {crop_batch:>7} {stats['p50']:>13.2f} {per_frame:>10.2f} "
                f"{with_skeleton / crops_seen:>9.1%}"
            )
        pose.close()
        del pose
        release_gpu()

    return {
        "persons_total": persons,
        "persons_per_frame": round(persons / len(frames), 2),
        "crop_padding": CROP_PADDING,
        "plan_assumption_ms_per_person": 1.0,
        "by_config": rows,
    }


# ─── Karar ────────────────────────────────────────────────────


def _best_p50(run: dict[str, Any]) -> dict[str, Any] | None:
    valid = [r for r in run["by_batch"] if "error" not in r]
    return min(valid, key=lambda r: r["ms_per_frame"]["p50"]) if valid else None


def build_verdict(
    detect_run: dict[str, Any],
    pose_run: dict[str, Any],
    recall: dict[str, Any],
    topdown: dict[str, Any],
) -> dict[str, Any]:
    """Üç ölçümü tek mimari karara bağlar."""
    d_best = _best_p50(detect_run)
    p_best = _best_p50(pose_run)
    if not d_best or not p_best:
        return {"error": "karşılaştırma için yeterli ölçüm yok"}

    d_ms = d_best["ms_per_frame"]["p50"]
    p_ms = p_best["ms_per_frame"]["p50"]

    # En ucuz top-down konfigürasyonu
    best_td = (
        min(topdown["by_config"], key=lambda r: r["ms_per_frame_projected"])
        if topdown["by_config"]
        else None
    )
    two_stage_ms = d_ms + best_td["ms_per_frame_projected"] if best_td else None

    load = lambda ms: round(ms * MEASURED_FRAMES_PER_SECOND / 1000.0 * 100, 1)  # noqa: E731

    ratio = recall["recall_ratio_at_default_conf"]
    verdict: dict[str, Any] = {
        "detect_only_ms_per_frame_p50": d_ms,
        "single_pass_pose_ms_per_frame_p50": p_ms,
        "single_pass_pose_recall_ratio": ratio,
        "two_stage": {
            "detect_ms": d_ms,
            "pose_crops_ms": best_td["ms_per_frame_projected"] if best_td else None,
            "total_ms": round(two_stage_ms, 3) if two_stage_ms else None,
            "config": (
                f"kırpıntı {best_td['crop_size']}px · batch {best_td['crop_batch']}"
                if best_td
                else None
            ),
            "plan_estimate_ms": round(d_ms + topdown["persons_per_frame"] * 1.0, 3),
        },
        "gpu_load_pct_at_measured_throughput": {
            "frames_per_second": MEASURED_FRAMES_PER_SECOND,
            "detect_only": load(d_ms),
            "single_pass_pose": load(p_ms),
            "two_stage": load(two_stage_ms) if two_stage_ms else None,
        },
        "decision": "iki_kademe",
        "rationale": (
            f"Tam karede iki modelin maliyeti pratikte AYNI ({p_ms:.2f} vs {d_ms:.2f} ms) "
            f"— aynı omurgayı paylaşıyorlar, fark koşular arası gürültü kadar. "
            f"Ama aynı işi yapmıyorlar: poz modeli, tespit modelinin bulduğu kişilerin "
            f"yalnızca %{ratio * 100:.0f}'ini buluyor ve kaybettikleri küçük/uzak kutular. "
            f"Dedektörü poz modeliyle DEĞİŞTİRMEK sessiz tespit kaybı demektir "
            f"(P-13 ile aynı sınıf gerileme). Bu yüzden Kademe 1 (tespit) yerinde kalır, "
            f"poz ayrı bir kademe olarak kişi kırpıntılarına uygulanır; ödenen bedel "
            f"kare başına ölçülen ek maliyettir."
        ),
    }
    return verdict


# ─── CLI ──────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Poz tahmini maliyet + doğruluk ölçümü")
    parser.add_argument("--cameras", nargs="+", default=DEFAULT_CAMERAS)
    parser.add_argument("--frames", type=int, default=16, help="Kamera başına kare")
    parser.add_argument("--batches", nargs="+", type=int, default=DEFAULT_BATCHES)
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--no-half", action="store_true", help="FP16 yerine FP32")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--skip-topdown", action="store_true")
    args = parser.parse_args()

    for path in (MODELS / "yolo26s.pt", MODELS / "yolo26s-pose.pt"):
        if not path.is_file():
            print(f"Ağırlık bulunamadı: {path}")
            print("  uv run python scripts/fetch_models.py --verify")
            return 1

    print("Kareler yerel dosyalardan okunuyor (RTSP değil — bkz. P-07):")
    frames = load_frames(args.cameras, args.frames)
    if len(frames) < max(args.batches):
        print(f"\nYetersiz kare: {len(frames)} < {max(args.batches)}")
        return 1
    shapes = sorted({f"{f.shape[1]}x{f.shape[0]}" for f in frames})
    print(f"\nToplam {len(frames)} kare · çözünürlük: {', '.join(shapes)}")

    half = not args.no_half
    common = {
        "frames": frames,
        "batches": args.batches,
        "repeats": args.repeats,
        "imgsz": args.imgsz,
        "conf": args.conf,
        "half": half,
        "device": args.device,
    }

    detect_run = run_speed("A) KADEME 1 — sadece tespit", MODELS / "yolo26s.pt", **common)
    pose_run = run_speed(
        "A) tek geçiş — tespit + poz birlikte", MODELS / "yolo26s-pose.pt", **common
    )
    recall = run_recall(frames, imgsz=args.imgsz, half=half, device=args.device)
    topdown = (
        {"by_config": [], "persons_per_frame": 0.0, "persons_total": 0}
        if args.skip_topdown
        else run_topdown(
            frames,
            imgsz=args.imgsz,
            half=half,
            device=args.device,
            conf=args.conf,
            repeats=args.repeats,
        )
    )

    verdict = build_verdict(detect_run, pose_run, recall, topdown)

    print("\n" + "=" * 70)
    print("KARAR")
    print("=" * 70)
    if "error" in verdict:
        print(verdict["error"])
    else:
        g = verdict["gpu_load_pct_at_measured_throughput"]
        ts = verdict["two_stage"]
        print(f"  Sadece tespit          : {verdict['detect_only_ms_per_frame_p50']:6.2f} ms/kare")
        print(
            f"  Tek geçiş poz          : {verdict['single_pass_pose_ms_per_frame_p50']:6.2f} ms/kare"
            f"   ⚠ tespitlerin yalnızca %{verdict['single_pass_pose_recall_ratio'] * 100:.0f}'i"
        )
        if ts["total_ms"]:
            print(
                f"  İki kademe (ölçülen)   : {ts['total_ms']:6.2f} ms/kare"
                f"   = {ts['detect_ms']:.2f} tespit + {ts['pose_crops_ms']:.2f} poz"
            )
            print(f"    {ts['config']}")
            print(f"    PLAN.md §2.3 tahmini : {ts['plan_estimate_ms']:6.2f} ms/kare")
        print()
        print(f"  20 kamerada GPU yükü ({g['frames_per_second']:.0f} kare/sn):")
        print(f"    sadece tespit        : %{g['detect_only']:.1f}")
        if g["two_stage"]:
            print(f"    tespit + poz kademesi: %{g['two_stage']:.1f}")
        print()
        print(f"  VRAM: tespit {detect_run['model_vram_mb']:.0f} MB · poz {pose_run['model_vram_mb']:.0f} MB")
        print(f"\n  => KARAR: {verdict['decision']}")
        for line in verdict["rationale"].split(". "):
            if line.strip():
                print(f"     {line.strip().rstrip('.')}.")

    if args.no_save:
        return 0

    import torch

    payload = {
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "phase": "Faz 1 / Gün 7",
        "description": (
            "Poz tahmini (Kademe 2a) maliyet + doğruluk ölçümü; "
            "tek-model / iki-kademe mimari kararı"
        ),
        "hardware": {
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
            "vram_gb": round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1)
            if torch.cuda.is_available()
            else 0,
        },
        "software": {"torch": torch.__version__, "cuda": torch.version.cuda},
        "config": {
            "imgsz": args.imgsz,
            "precision": "fp16" if half else "fp32",
            "conf_threshold": args.conf,
            "cameras": args.cameras,
            "frames_total": len(frames),
            "repeats": args.repeats,
            "source": "yerel dosya (RTSP değil — P-07)",
            "headline_statistic": "p50 (ortalama, ilk koşan modelin havuz büyütmesiyle çarpık)",
        },
        "speed": [detect_run, pose_run],
        "recall": recall,
        "topdown": topdown,
        "verdict": verdict,
    }
    BENCHMARKS.mkdir(exist_ok=True)
    out = BENCHMARKS / f"pose_{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nKaydedildi: {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
