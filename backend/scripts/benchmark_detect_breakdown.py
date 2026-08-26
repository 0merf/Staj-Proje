"""KADEME 1'in 6.4 ms'i NEREDE geçiyor? — TensorRT kararının ön koşulu.

Neden bu betik
--------------
Elimizde iki ölçüm var ve ikisi birbiriyle çelişiyor gibi duruyor:

  · `detect()` çağrısı kare başına ~6.4 ms sürüyor
  · GPU koşu boyunca **%0-5 kullanımda**, kısıtlama sebebi `GpuIdle`

Eğer GPU boşsa, 6.4 ms'in çoğu GPU'da GEÇMİYOR demektir. Ama bugüne kadar
bu "çoğu" hiç ölçülmedi — tahmin edildi.

Bu ayrım TensorRT kararını tek başına belirliyor. TensorRT **yalnızca**
modelin ileri geçişini (forward pass) hızlandırır; tensör hazırlama,
NMS, sonuç nesnesi kurma ve GPU→CPU aktarımı aynen kalır. Yani:

    kazanç tavanı = ileri geçiş süresi × (1 − 1/hızlanma)

İleri geçiş 6.4 ms'in 1 ms'iyse, TensorRT mükemmel çalışsa bile kazanç
%13'ü geçemez — 2 GB'lık kurulum ve ayrı bir model ihraç zinciri buna
değmez. 5 ms'iyse değer. Ölçmeden bilinmez.

Amdahl yasasının en somut hâli: bir sistemin ancak dokunduğun kısmı
kadarını hızlandırabilirsin.

Nasıl ölçer
-----------
`detect()` dört aşamaya ayrılıp ayrı ayrı zamanlanır:

  1. TENSOR   : numpy yığma + H2D kopya + permute/flip/half/div  (_as_tensor)
  2. FORWARD  : saf model ileri geçişi                            ⬅ TensorRT'nin alanı
  3. ARTIK    : predict() toplamı − forward  (NMS + Results kurma)
  4. CONVERT  : GPU→CPU aktarım + Detection listesi               (_convert)

⚠ FORWARD **CUDA olayı** ile ölçülür, `time.perf_counter()` ile değil.
CUDA çağrıları eşzamansızdır: Python satırı biter, GPU hâlâ çalışıyordur.
Duvar saati ölçümü kuyruğa atma süresini ölçer, işin kendisini değil.
`torch.cuda.Event` GPU'nun kendi zaman çizgisinde ölçer.

⚠ ÖLÇÜM KOŞULU: boru hattı KAPALI olmalı. Çıkarım worker'ı açıkken
GPU'da çekişme olur ve tam da ölçmek istediğimiz aşama şişer.

Kullanım
--------
    uv run python scripts/benchmark_detect_breakdown.py
    uv run python scripts/benchmark_detect_breakdown.py --batch 8 --tekrar 200
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


def _sentetik_kareler(sayi: int, imgsz: int, tohum: int = 7) -> list[np.ndarray]:
    """Gerçekçi doluluk üreten sahte kareler.

    ⚠ Tamamen siyah kare KULLANILMAZ: dedektör hiçbir şey bulamaz, NMS
    boş listeyle çalışır ve 3. aşama ("ARTIK") yapay olarak sıfıra iner.
    Gürültü + birkaç dikdörtgen, NMS'e gerçekçi sayıda aday verir.
    """
    rng = np.random.default_rng(tohum)
    kareler = []
    for _ in range(sayi):
        kare = rng.integers(40, 90, size=(imgsz, imgsz, 3), dtype=np.uint8)
        for _ in range(rng.integers(3, 9)):
            x, y = rng.integers(0, imgsz - 90, size=2)
            w, h = rng.integers(30, 60), rng.integers(70, 90)
            kare[y : y + h, x : x + w] = rng.integers(120, 220, size=3, dtype=np.uint8)
        kareler.append(np.ascontiguousarray(kare))
    return kareler


def _ozet(sureler: list[float]) -> dict[str, float]:
    s = sorted(sureler)
    return {
        "p50": round(statistics.median(s), 3),
        "p95": round(s[int(len(s) * 0.95)], 3),
        "ort": round(statistics.fmean(s), 3),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="detect() aşama kırılımı")
    ap.add_argument("--model", default="models/yolo26s.pt")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--tekrar", type=int, default=120)
    ap.add_argument("--isinma", type=int, default=25)
    args = ap.parse_args()

    import torch

    if not torch.cuda.is_available():
        print("CUDA yok — bu ölçüm anlamsız", file=sys.stderr)
        return 1

    from sentinel.inference.detector.yolo import UltralyticsDetector

    yol = PROJECT_ROOT / "backend" / args.model
    if not yol.is_file():
        yol = PROJECT_ROOT / args.model
    det = UltralyticsDetector(yol, imgsz=args.imgsz, half=True)

    kareler = _sentetik_kareler(args.batch, args.imgsz)

    print(f"model={yol.name} batch={args.batch} imgsz={args.imgsz} tekrar={args.tekrar}")
    print("ısınıyor...", flush=True)
    det.warmup(args.batch)
    for _ in range(args.isinma):
        det.detect(kareler)
    torch.cuda.synchronize()

    t_tensor: list[float] = []
    t_forward: list[float] = []
    t_predict: list[float] = []
    t_convert: list[float] = []
    tespit_sayisi = 0

    ev0, ev1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)

    for _ in range(args.tekrar):
        # 1 · TENSOR — CPU tarafı bittiğinde GPU kopyası da bitsin diye senkron
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        tensor = det._as_tensor(kareler)
        torch.cuda.synchronize()
        t_tensor.append((time.perf_counter() - t0) * 1000)
        assert tensor is not None, "kareler model uzayında değil — ölçüm geçersiz"

        # 2 · FORWARD — saf ileri geçiş, CUDA olayıyla
        with torch.inference_mode():
            ev0.record()
            det._model.model(tensor)
            ev1.record()
        torch.cuda.synchronize()
        t_forward.append(ev0.elapsed_time(ev1))

        # 3 · PREDICT toplamı (forward + NMS + Results)
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        sonuc = det._predict(kareler, 0.35)
        torch.cuda.synchronize()
        t_predict.append((time.perf_counter() - t0) * 1000)

        # 4 · CONVERT — GPU→CPU aktarımı burada gerçekleşiyor
        t0 = time.perf_counter()
        for r in sonuc:
            tespit_sayisi += len(det._convert(r))
        t_convert.append((time.perf_counter() - t0) * 1000)

    n = args.batch
    tensor_o, forward_o = _ozet(t_tensor), _ozet(t_forward)
    predict_o, convert_o = _ozet(t_predict), _ozet(t_convert)
    artik = round(predict_o["p50"] - forward_o["p50"], 3)
    toplam = round(tensor_o["p50"] + predict_o["p50"] + convert_o["p50"], 3)

    print(f"\nbatch başına p50 (ms) · kare başına = ÷{n}\n")
    print(f"{'AŞAMA':<10} {'batch ms':>9} {'kare ms':>8} {'pay':>6}")
    satirlar = [
        ("TENSOR", tensor_o["p50"]),
        ("FORWARD", forward_o["p50"]),
        ("ARTIK", artik),
        ("CONVERT", convert_o["p50"]),
    ]
    for ad, ms in satirlar:
        print(f"{ad:<10} {ms:>9.3f} {ms / n:>8.3f} {ms / toplam:>5.0%}")
    print(f"{'TOPLAM':<10} {toplam:>9.3f} {toplam / n:>8.3f}")

    # ⬇ Asıl cevap: TensorRT'nin dokunabileceği pay ne kadar?
    pay = forward_o["p50"] / toplam
    print(f"\nTensorRT'nin dokunabildiği pay: %{pay * 100:.0f} (FORWARD)")
    for hiz in (2.0, 3.0, 5.0):
        kazanc = pay * (1 - 1 / hiz)
        print(f"  forward {hiz:.0f}× hızlansa → toplam kazanç %{kazanc * 100:.1f}")
    print(
        "\nKARAR EŞİĞİ: 3× hızlanmada kazanç %15'in altındaysa TensorRT'nin\n"
        "kurulum + ihraç + sürüm bağımlılığı maliyeti karşılığını vermez."
    )

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "model": yol.name,
        "batch": args.batch,
        "imgsz": args.imgsz,
        "tekrar": args.tekrar,
        "tespit_ort": round(tespit_sayisi / args.tekrar / n, 2),
        "asama_ms_batch": {
            "tensor": tensor_o,
            "forward": forward_o,
            "predict_toplam": predict_o,
            "artik_nms_results": artik,
            "convert": convert_o,
        },
        "toplam_ms_batch": toplam,
        "toplam_ms_kare": round(toplam / n, 3),
        "forward_payi": round(pay, 4),
        "tensorrt_kazanc_tavani": {
            f"{h:.0f}x": round(pay * (1 - 1 / h), 4) for h in (2.0, 3.0, 5.0)
        },
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"detect_breakdown_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
