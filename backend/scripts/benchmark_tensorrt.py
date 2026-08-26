"""PyTorch FP16 vs TensorRT — A/B ölçümü ve TESPİT EŞDEĞERLİĞİ.

Neden bu betik
--------------
`benchmark_detect_breakdown.py` TensorRT'nin dokunabildiği payı ölçtü:
ileri geçiş, `detect` bütçesinin %53'ü (3.37 ms/kare). Amdahl'a göre
3× hızlanma → %35.6 toplam kazanç. Bu bir TAHMİN; bu betik gerçeği
ölçüyor.

⚠ İKİ SORU, İKİSİ DE SORULMALI
------------------------------
1. **Daha hızlı mı?**  → süre karşılaştırması
2. **Aynı şeyi mi buluyor?** → tespit karşılaştırması

İkincisi olmadan birincisi anlamsız. FP16 dönüşümü, katman füzyonu ve
farklı çekirdek seçimleri sonucu değiştirebilir. "3× hızlandı" diye
raporlanan bir kazanç, aslında modelin daha az insan bulmasıysa kazanç
değil kayıptır — ve bu SESSİZ bir hatadır, hız grafiğinde görünmez.

⚠ DÖNÜŞÜMLÜ KOŞU — P-17'nin dersi
---------------------------------
İki yapılandırma arka arkaya değil, **dönüşümlü** ölçülüyor
(A,B,A,B,...). Sıralı koşuda GPU sıcaklığı, saat frekansı ve termal
kısıtlama ikinciyi sistematik olarak cezalandırıyor. Gün 8'de tam bu
yüzden bir kazanç önce %-34 ölçülüp sonra %+43 çıkmıştı.

⚠ SABİT PARTİ BOYUTU
--------------------
Motor `dynamic=False` ile derlendi. Dinamik şekiller YOLO26'nın dikkat
bloğunda kırılıyor:

    Could not find any implementation for node
    ForeignNode[/model.10/m/m.0/attn/Split_82...]

Sabit parti işlevsel bir kısıt: canlı worker'da parti boyutu değişken
(o an kaç kare hazırsa). Motor kullanılacaksa partinin **doldurulması**
gerekiyor — eksik kareler tekrarla tamamlanır. Bu betik gerçek maliyeti
görebilmek için tam parti ölçüyor; kısmi parti maliyeti ayrı bir konu
ve karar notunda yazılı.

⚠ ÖLÇÜM KOŞULU: boru hattı KAPALI.

Kullanım
--------
    uv run python scripts/benchmark_tensorrt.py --batch 8 --tur 30
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"


def _gercek_kareler(sayi: int, imgsz: int) -> list[np.ndarray]:
    """Kamera çiftliğinden GERÇEK kareler — sentetik gürültü değil.

    ⚠ Tespit eşdeğerliği sentetik kareyle sınanamaz: rastgele
    dikdörtgenlerde model zaten insan bulmaz, iki yapılandırma da
    "0 tespit" der ve eşdeğerlik sahte biçimde doğrulanmış olur.
    """
    import cv2

    from sentinel.core.preprocess import letterbox

    kareler: list[np.ndarray] = []
    videolar = sorted((PROJECT_ROOT / "data" / "videos").glob("cam-*.mp4"))
    if not videolar:
        raise FileNotFoundError("data/videos altında kamera videosu yok")
    for yol in videolar:
        cap = cv2.VideoCapture(str(yol))
        # Başlangıçtan biraz ileri: ilk kareler çoğu videoda boş sahne
        cap.set(cv2.CAP_PROP_POS_FRAMES, 250)
        ok, kare = cap.read()
        cap.release()
        if ok:
            hazir, _ = letterbox(kare, imgsz)
            kareler.append(np.ascontiguousarray(hazir))
        if len(kareler) >= sayi:
            break
    while len(kareler) < sayi:  # video sayısı yetmezse tekrarla
        kareler.append(kareler[len(kareler) % max(1, len(kareler))])
    return kareler[:sayi]


def _ozet(v: list[float]) -> dict[str, float]:
    s = sorted(v)
    return {
        "p50": round(statistics.median(s), 3),
        "p90": round(s[int(len(s) * 0.90)], 3),
        "ort": round(statistics.fmean(s), 3),
    }


def _tespitleri_kiyasla(a: list, b: list, tol_px: float = 5.0) -> dict[str, object]:
    """İki tespit kümesi aynı mı? Kutu bazında eşleştirerek bakar."""
    esles = kayip = fazla = 0
    iou_ler: list[float] = []
    for ta, tb in zip(a, b, strict=False):
        kullanilan: set[int] = set()
        for da in ta:
            en_iyi, en_iyi_i = 0.0, -1
            for i, db in enumerate(tb):
                if i in kullanilan:
                    continue
                x1 = max(da.x1, db.x1)
                y1 = max(da.y1, db.y1)
                x2 = min(da.x2, db.x2)
                y2 = min(da.y2, db.y2)
                kesisim = max(0.0, x2 - x1) * max(0.0, y2 - y1)
                birlesim = (
                    (da.x2 - da.x1) * (da.y2 - da.y1) + (db.x2 - db.x1) * (db.y2 - db.y1) - kesisim
                )
                iou = kesisim / birlesim if birlesim > 0 else 0.0
                if iou > en_iyi:
                    en_iyi, en_iyi_i = iou, i
            if en_iyi >= 0.5:
                esles += 1
                iou_ler.append(en_iyi)
                kullanilan.add(en_iyi_i)
            else:
                kayip += 1
        fazla += len(tb) - len(kullanilan)
    return {
        "eslesen": esles,
        "pytorch_da_var_trt_de_yok": kayip,
        "trt_de_var_pytorch_da_yok": fazla,
        "ortalama_iou": round(statistics.fmean(iou_ler), 4) if iou_ler else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="PyTorch vs TensorRT A/B")
    ap.add_argument("--pt", default="models/yolo26s.pt")
    ap.add_argument("--engine", default="models/yolo26s.engine")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--tur", type=int, default=30, help="dönüşümlü tur sayısı")
    ap.add_argument("--olcum", type=int, default=10, help="tur başına ölçüm")
    args = ap.parse_args()

    import torch

    from sentinel.inference.detector.yolo import UltralyticsDetector

    pt_yol = PROJECT_ROOT / "backend" / args.pt
    trt_yol = PROJECT_ROOT / "backend" / args.engine
    if not trt_yol.is_file():
        print(f"Motor yok: {trt_yol}\nÖnce ihraç edin (README'ye bakın).", file=sys.stderr)
        return 1

    kareler = _gercek_kareler(args.batch, args.imgsz)
    print(f"{len(kareler)} gerçek kare · batch={args.batch} · {args.tur} dönüşümlü tur")

    modeller = {
        "pytorch": UltralyticsDetector(pt_yol, imgsz=args.imgsz, half=True),
        "tensorrt": UltralyticsDetector(trt_yol, imgsz=args.imgsz, half=True),
    }
    for ad, m in modeller.items():
        print(f"  {ad} ısıtılıyor...", flush=True)
        m.warmup(args.batch)
        for _ in range(15):
            m.detect(kareler)
    torch.cuda.synchronize()

    sureler: dict[str, list[float]] = {ad: [] for ad in modeller}
    # ⚠ DÖNÜŞÜMLÜ: her turda ikisi de ölçülüyor
    for _ in range(args.tur):
        for ad, m in modeller.items():
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            for _ in range(args.olcum):
                m.detect(kareler)
            torch.cuda.synchronize()
            gecen = (time.perf_counter() - t0) * 1000 / args.olcum
            sureler[ad].append(gecen)

    n = args.batch
    pt, trt = _ozet(sureler["pytorch"]), _ozet(sureler["tensorrt"])
    hizlanma = pt["p50"] / trt["p50"]

    print(f"\n{'MOTOR':<10} {'batch ms':>9} {'kare ms':>8} {'p90':>8}")
    print(f"{'PyTorch':<10} {pt['p50']:>9.3f} {pt['p50'] / n:>8.3f} {pt['p90']:>8.3f}")
    print(f"{'TensorRT':<10} {trt['p50']:>9.3f} {trt['p50'] / n:>8.3f} {trt['p90']:>8.3f}")
    print(f"\nHIZLANMA: {hizlanma:.2f}×  ({(1 - trt['p50'] / pt['p50']) * 100:+.1f}% süre)")

    # ─── Tespit eşdeğerliği ───
    print("\nTESPİT EŞDEĞERLİĞİ — hız kazancı doğru sonuçla mı geliyor?")
    a = modeller["pytorch"].detect(kareler)
    b = modeller["tensorrt"].detect(kareler)
    kiyas = _tespitleri_kiyasla(a, b)
    toplam_a = sum(len(x) for x in a)
    toplam_b = sum(len(x) for x in b)
    print(f"  PyTorch tespit  : {toplam_a}")
    print(f"  TensorRT tespit : {toplam_b}")
    for k, v in kiyas.items():
        print(f"  {k:<28}: {v}")
    if toplam_a and kiyas["eslesen"] / toplam_a < 0.98:  # type: ignore[operator]
        print("\n⚠ TESPİTLER AYRIŞIYOR — hız kazancı doğruluk pahasına geliyor olabilir.")

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "batch": args.batch,
        "imgsz": args.imgsz,
        "tur": args.tur,
        "olcum_per_tur": args.olcum,
        "pytorch_ms_batch": pt,
        "tensorrt_ms_batch": trt,
        "pytorch_ms_kare": round(pt["p50"] / n, 3),
        "tensorrt_ms_kare": round(trt["p50"] / n, 3),
        "hizlanma": round(hizlanma, 3),
        "tespit_pytorch": toplam_a,
        "tespit_tensorrt": toplam_b,
        "esdegerlik": kiyas,
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"tensorrt_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
