"""YOLO ağırlığını TensorRT motoruna ihraç eder — tekrar üretilebilir biçimde.

⚠ MOTOR DOSYASI GIT'E GİRMEZ, GİREMEZ
-------------------------------------
`.engine` dosyası **bu makineye özeldir**: derlenirken GPU mimarisi
(compute capability), TensorRT sürümü, sürücü sürümü ve seçilen
çekirdek taktikleri gömülür. Başka bir makinede yüklenmez; yüklense
bile ölçüm anlamsız olur.

Bu yüzden `.gitignore`'da. Git'e giren şey **onu üreten bu betik.**
Tekrar üretilebilirlik dosyayı taşımakla değil, üretim reçetesini
saklamakla sağlanır.

⚠ İKİ ENGEL VE NEDEN BU AYARLAR
-------------------------------
**1. TensorRT 11 (cu13) ÇALIŞMIYOR.** `pip install tensorrt` bu makinede
`tensorrt-cu13` getiriyor; torch ise `cu128`. Ayrıca TensorRT 11
"strongly-typed" olduğu için FP16 builder bayrağını kaldırmış ve düşük
hassasiyeti ONNX grafiğine gömmek için ayrıca `nvidia-modelopt`
istiyor. Kullanılan: **`tensorrt-cu12==10.13.*`**

**2. `dynamic=True` KIRILIYOR.** YOLO26'nın dikkat bloğunda:

    Could not find any implementation for node
    ForeignNode[/model.10/m/m.0/attn/Split_82.../attn/Add]

Dinamik şekillerle o füzyon için TensorRT uygun çekirdek bulamıyor.
Bu yüzden **sabit parti** ile ihraç ediliyor.

⚠ SABİT PARTİNİN BEDELİ ÖLÇÜLDÜ
-------------------------------
Motor yalnızca tam parti alır; eksik kareler tekrarla doldurulur ve
maliyet tam parti kadar olur:

    parti   PyTorch   TRT(8'e dolgu)   kazanç
        2     12.30          17.65    -43.4%
        4     19.57          24.74    -26.4%
        6     38.04          29.58    +22.2%
        8     39.25          27.13    +30.9%

Yani motor **ancak partiler doluyorsa** kazandırıyor. Üretime almadan
önce `sentinel_batch_size` histogramına bakılmalı.

Kullanım
--------
    uv pip install "tensorrt-cu12==10.13.*" onnxslim
    uv run python scripts/export_tensorrt.py
    uv run python scripts/export_tensorrt.py --model models/yolo26s-pose.pt --batch 64
    uv run python scripts/benchmark_tensorrt.py      # sonra MUTLAKA ölç
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

BACKEND = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="TensorRT motoru üret")
    ap.add_argument("--model", default="models/yolo26s.pt")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=8, help="SABİT parti boyutu")
    ap.add_argument("--workspace", type=int, default=6, help="GB")
    ap.add_argument("--fp32", action="store_true", help="FP16 yerine FP32")
    args = ap.parse_args()

    try:
        import tensorrt as trt
    except ImportError:
        print(
            'TensorRT kurulu değil:\n  uv pip install "tensorrt-cu12==10.13.*" onnxslim',
            file=sys.stderr,
        )
        return 1

    import torch

    surum = tuple(int(x) for x in trt.__version__.split(".")[:2])
    if surum >= (11, 0):
        print(
            f"⚠ TensorRT {trt.__version__} kurulu. 11.x strongly-typed ve FP16 için\n"
            "  nvidia-modelopt gerektiriyor; ayrıca cu13 derlemesi torch cu128 ile\n"
            '  uyumsuz. Önerilen:  uv pip install "tensorrt-cu12==10.13.*"',
            file=sys.stderr,
        )

    yol = BACKEND / args.model
    if not yol.is_file():
        print(f"Ağırlık yok: {yol}", file=sys.stderr)
        return 1

    from ultralytics import YOLO

    print(
        f"model={yol.name} · imgsz={args.imgsz} · SABİT parti={args.batch} · "
        f"{'FP32' if args.fp32 else 'FP16'} · TensorRT {trt.__version__} · "
        f"GPU {torch.cuda.get_device_name(0)}"
    )
    print("Derleme birkaç dakika sürüyor (taktik ölçümü GPU'da yapılıyor)...", flush=True)

    t0 = time.time()
    hedef = YOLO(str(yol)).export(
        format="engine",
        imgsz=args.imgsz,
        quantize=None if args.fp32 else 16,
        # ⚠ dynamic=False zorunlu — gerekçesi modül başlığında.
        dynamic=False,
        batch=args.batch,
        workspace=args.workspace,
    )
    print(f"\n✓ {hedef}  ({time.time() - t0:.0f} sn)")
    print(
        "\n⚠ Motoru KULLANMADAN ÖNCE ölçün — hız kazancı tespitleri\n"
        "  değiştiriyor olabilir:\n"
        "    uv run python scripts/benchmark_tensorrt.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
