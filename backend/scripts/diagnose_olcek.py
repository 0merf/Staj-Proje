"""Ölçek tanısı — normalize özelliğin ÇÖZÜNÜRLÜK TABANI (P-49).

⭐ NEDEN BU BETİK YAZILDI
------------------------
K8, cam-15 (UBI-Fights) üzerinde tutmadı. Sıradaki üç şüpheli tek tek
elendi (`evaluate_k8_video.py · ALGI TANISI`):

    tespit     : kavgada 6.5 kişi/kare, %96.7 poz başarısı  → sağlam
    takip      : iz ömrü kavgada 7.5 örnek (normalde 7.0)   → kopmuyor
    zamansal   : kişilerin %100'ünde bilek hızı hesaplandı  → veri var
    ⭐ ham özellik: kavga 1.152 · normal 1.192 · oran 0.97   → SİNYAL YOK

Yani modele giren sayının kendisi kavgayı normalden ayırmıyor. Model
suçlanamaz: bozuk bir model değil, **bilgisiz bir girdi** var.

⚠ ŞÜPHE: gövde boyuna normalizasyonun gizli maliyeti
----------------------------------------------------
Bütün hız özellikleri **gövde/saniye** cinsinden (person.py başlığı).
Bu, uzaklık farkını yok etmek için doğru bir tercih — ama bedava değil:

    normalize_hiz = piksel_hiz / govde_boyu_px

Poz kestiricinin eklem hatası kabaca **piksel cinsinden sabittir**
(birkaç piksel). Payda küçüldükçe — yani kişi uzaklaştıkça — aynı hata
normalize uzayda **büyür**:

    gürültü_tabanı ≈ (eklem_hatası_px · √2 / Δt) / govde_boyu_px

⭐ Sonuç: özelliğin bir **geçerlilik alt sınırı** var. Kişi belirli bir
piksel boyunun altına inince gürültü tabanı sinyalin üstüne çıkar ve
özellik ayırt etme gücünü yitirir — model ne kadar iyi olursa olsun.

Bu betik o şüpheyi tek bir karşılaştırmayla sınıyor:

    EĞİTİM alanı (RWF-2000) kişi boyu   ⟷   UYGULAMA alanı (cam-15)

Eğer cam-15'teki kişiler belirgin biçimde küçükse, mekanizma doğrulanmış
olur ve düzeltme model değiştirmek değil **çalışma alanını ilan etmek**
olur (bkz. `ASGARI_KISI_PX`).

⚠ ÖLÇÜM AYNI UZAYDA YAPILIYOR
-----------------------------
İki taraf da 640 letterbox uzayında ölçülüyor — `evaluate_k8_video.py`
ile birebir aynı ön işleme. Farklı uzaylarda ölçmek bu projede daha önce
bir AUC'yi 0.483 gösterdi (P-39); tekrarlanmıyor.

Kullanım:
    uv run python scripts/diagnose_olcek.py --klip 40
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

RWF = PROJECT_ROOT / "data" / "datasets" / "RWF-2000"
VIDEOLAR = PROJECT_ROOT / "data" / "videos"
CIKTI = PROJECT_ROOT / "benchmarks"

IMGSZ = 640
# Her klipten kaç kare örneklensin — boy dağılımı için az örnek yeter,
# kavga tespiti yapmıyoruz.
KARE_BASINA = 6


def _boylar(yol: Path, dedektor: Any, azami_kare: int) -> list[float]:
    """Bir videodaki tespit kutularının piksel yüksekliklerini döndürür."""
    import cv2

    from sentinel.core.preprocess import letterbox

    cap = cv2.VideoCapture(str(yol))
    if not cap.isOpened():
        return []
    toplam = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    adim = max(1, toplam // azami_kare)

    boylar: list[float] = []
    kare_no = 0
    alinan = 0
    while alinan < azami_kare:
        ok, kare = cap.read()
        if not ok:
            break
        if kare_no % adim == 0:
            hazir, _lb = letterbox(kare, IMGSZ)
            for d in dedektor.detect([hazir])[0]:
                boylar.append(float(d.y2 - d.y1))
            alinan += 1
        kare_no += 1
    cap.release()
    return boylar


def _ozet(boylar: list[float]) -> dict[str, float]:
    if not boylar:
        return {}
    s = sorted(boylar)
    return {
        "adet": float(len(s)),
        "p10": s[int(len(s) * 0.10)],
        "medyan": statistics.median(s),
        "p90": s[min(len(s) - 1, int(len(s) * 0.90))],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Kişi ölçeği tanısı (P-49)")
    ap.add_argument("--klip", type=int, default=40, help="RWF'den kaç klip")
    ap.add_argument("--kamera", default="cam-15", help="uygulama videosu")
    ap.add_argument("--tohum", type=int, default=42)
    args = ap.parse_args()

    from sentinel.inference.detector.yolo import UltralyticsDetector

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "backend" / "models" / "yolo26s.pt",
        imgsz=IMGSZ, half=True,
    )
    dedektor.warmup(1)

    # ─── EĞİTİM ALANI: RWF-2000 ───
    havuz = sorted((RWF / "val").rglob("*.avi")) or sorted(RWF.rglob("*.avi"))
    if not havuz:
        print(f"HATA: RWF klibi bulunamadı ({RWF})")
        return 1
    # Tohumlu karıştırma — ölçüm tekrar üretilebilir olsun diye.
    random.Random(args.tohum).shuffle(havuz)  # noqa: S311
    secilen = havuz[: args.klip]

    print(f"EĞİTİM alanı — RWF-2000 · {len(secilen)} klip örnekleniyor…")
    rwf_boylar: list[float] = []
    for i, yol in enumerate(secilen, 1):
        rwf_boylar += _boylar(yol, dedektor, KARE_BASINA)
        if i % 10 == 0:
            print(f"  {i}/{len(secilen)}")

    # ─── UYGULAMA ALANI: cam-15 ───
    video = VIDEOLAR / f"{args.kamera}.mp4"
    if not video.exists():
        print(f"HATA: {video} yok")
        return 1
    print(f"\nUYGULAMA alanı — {args.kamera} örnekleniyor…")
    cam_boylar = _boylar(video, dedektor, args.klip * KARE_BASINA)

    rwf_o, cam_o = _ozet(rwf_boylar), _ozet(cam_boylar)
    if not rwf_o or not cam_o:
        print("HATA: yeterli tespit yok")
        return 1

    print("\n═══ KİŞİ BOYU (piksel · 640 letterbox uzayı) ═══")
    print(f"{'alan':<26} {'adet':>7} {'p10':>8} {'medyan':>8} {'p90':>8}")
    for ad, o in (("EĞİTİM (RWF-2000)", rwf_o), (f"UYGULAMA ({args.kamera})", cam_o)):
        print(f"{ad:<26} {o['adet']:>7.0f} {o['p10']:>8.1f} "
              f"{o['medyan']:>8.1f} {o['p90']:>8.1f}")

    oran = rwf_o["medyan"] / max(cam_o["medyan"], 1e-9)
    print(f"\nmedyan boy oranı (eğitim / uygulama) : {oran:.2f}×")
    print(f"beklenen gürültü tabanı oranı        : {oran:.2f}× "
          "(sabit piksel hatası / gövde boyu)")

    print("\n═══ YORUM ═══")
    if oran >= 1.3:
        print("⭐ MEKANİZMA DOĞRULANDI. Uygulama alanındaki kişiler eğitim")
        print(f"   alanındakinin 1/{oran:.2f}'i boyunda. Sabit piksellik eklem")
        print(f"   hatası, gövde boyuna bölününce burada {oran:.2f} kat")
        print("   büyüyor. Ham bilek hızının kavga (1.152) ve normalde")
        print("   (1.192) AYNI çıkması bununla tutarlı: ikisi de sinyal")
        print("   değil, aynı gürültü tabanı.")
        print("\n   ⚠ Düzeltme model değiştirmek DEĞİL: özelliğin geçerli")
        print("   olduğu ölçek aralığını ilan etmek ve altında skorlamamak.")
    else:
        print(f"❌ MEKANİZMA DOĞRULANMADI (oran {oran:.2f} < 1.3).")
        print("   Ölçek farkı başarısızlığı açıklamıyor — başka sebep aranmalı.")

    CIKTI.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = CIKTI / f"olcek_tanisi_{damga}.json"
    hedef.write_text(json.dumps({
        "tarih": datetime.now(UTC).isoformat(),
        "imgsz": IMGSZ,
        "egitim_alani": {"kaynak": "RWF-2000", "klip": len(secilen), **rwf_o},
        "uygulama_alani": {"kaynak": args.kamera, **cam_o},
        "medyan_boy_orani": round(oran, 3),
        "mekanizma_dogrulandi": bool(oran >= 1.3),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
