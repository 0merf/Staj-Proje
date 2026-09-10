"""KADEME 2b tanısı — duygu analizi neden yalnızca bir kamerada çalışıyor?

⭐ NEDEN BU BETİK
----------------
Canlı ölçüm (09-10.09) şunu gösterdi:

    sinyal          sıfırdan farklı
    saldırganlık    16/16 kamera
    anomali         16/16 kamera
    ifade            1/16 kamera   ⬅ yalnızca cam-20

"Duygu analizi" şartnamedeki ÜÇ yetenekten biri. Bu tabloyu raporda
savunabilmek için "neden bir kamerada" sorusunun **sayısal** cevabı
gerekiyor — "yüzler küçük" bir tahmin, dağılım bir ölçüm.

⚠ Kapı `expression_min_person_px = 180`: kişi kutusu ÇIKARIM UZAYINDA
(640×640 letterbox) bu yükseklikten küçükse yüz hiç aranmıyor. Bu betik
her kameradaki kişi kutusu yüksekliklerinin dağılımını çıkarıyor ve
kaçının kapıyı geçtiğini sayıyor.

⚠ NE ÖLÇÜLMÜYOR: yüzün kendi piksel boyutu. Kapı kişi kutusuna bakıyor;
yüz o kutunun ~%10-15'i. Buradaki sayılar "yüz aranmaya değer mi"
kapısını ölçüyor, "yüz tanınabilir mi" sorusunu değil.

Kullanım:
    uv run python scripts/diagnose_ifade.py --kare 40
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIZINI = PROJECT_ROOT / "data" / "videos"
BENCHMARKS = PROJECT_ROOT / "benchmarks"


def main() -> int:
    ap = argparse.ArgumentParser(description="KADEME 2b kapı tanısı")
    ap.add_argument("--kare", type=int, default=40, help="kamera başına kare")
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    import cv2

    from sentinel.config import settings
    from sentinel.core.preprocess import letterbox
    from sentinel.inference.detector.yolo import UltralyticsDetector

    esik = int(settings.expression_min_person_px)
    dedektor = UltralyticsDetector(
        str(settings.detector_weights),
        backend_name="yolo26",
        device="cuda:0",
        half=True,
        imgsz=args.imgsz,
        conf_threshold=float(settings.detector_conf_threshold),
    )

    videolar = sorted(VIDEO_DIZINI.glob("cam-*.mp4"))
    if not videolar:
        print("video yok", file=sys.stderr)
        return 1

    print(f"kapı: kişi kutusu yüksekliği ≥ {esik} px (çıkarım uzayı {args.imgsz})")
    print(f"{'kamera':<10}{'kişi':>7}{'medyan':>9}{'p90':>8}{'azami':>8}"
          f"{'kapıyı geçen':>14}")

    sonuc: dict[str, Any] = {}
    for yol in videolar:
        cap = cv2.VideoCapture(str(yol))
        if not cap.isOpened():
            continue
        toplam = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        adim = max(1, toplam // max(args.kare, 1))
        yukseklikler: list[float] = []
        okunan = 0
        try:
            for i in range(args.kare):
                cap.set(cv2.CAP_PROP_POS_FRAMES, min(i * adim, toplam - 1))
                ok, kare = cap.read()
                if not ok:
                    break
                okunan += 1
                hazir, _lb = letterbox(kare, args.imgsz)
                for d in dedektor.detect([hazir])[0]:
                    yukseklikler.append(float(d.y2 - d.y1))
        finally:
            cap.release()

        if not yukseklikler:
            print(f"{yol.stem:<10}{0:>7}{'—':>9}{'—':>8}{'—':>8}{'—':>14}")
            sonuc[yol.stem] = {"kisi": 0}
            continue

        s = sorted(yukseklikler)
        gecen = sum(1 for h in s if h >= esik)
        oran = gecen / len(s)
        print(f"{yol.stem:<10}{len(s):>7}{statistics.median(s):>9.0f}"
              f"{s[int(len(s) * 0.9)]:>8.0f}{s[-1]:>8.0f}"
              f"{f'{gecen} (%{100 * oran:.0f})':>14}")
        sonuc[yol.stem] = {
            "kisi": len(s),
            "kare": okunan,
            "medyan_px": round(statistics.median(s), 1),
            "p90_px": round(s[int(len(s) * 0.9)], 1),
            "azami_px": round(s[-1], 1),
            "kapiyi_gecen": gecen,
            "kapiyi_gecen_oran": round(oran, 4),
        }

    # ─── ⭐ İKİNCİ AŞAMA: kapıyı geçen kırpıntılarda YÜZ BULUNUYOR MU ───
    #
    # ⚠ İlk ölçüm bir varsayımı çürüttü. Kodun docstring'i "yüzler ~15 px,
    # kademe aday bulamayacak" diyordu; ölçüm 8 kameranın kişi kapısını
    # GEÇTİĞİNİ gösterdi. Ama canlıda yalnızca cam-20 ifade üretiyor.
    # Demek ki bağlayıcı kısıt kişi boyutu değil, bir SONRAKİ aşama.
    #
    # Bu bölüm onu ölçüyor: kapıyı geçen kırpıntılara YuNet uygulanıp
    # kaçında yüz bulunduğu sayılıyor.
    print(f"\n{'─' * 62}")
    print("⭐ İKİNCİ AŞAMA — kapıyı geçen kırpıntılarda YuNet yüz buluyor mu")
    print(f"{'kamera':<10}{'kırpıntı':>10}{'yüz bulundu':>13}{'oran':>8}{'medyan yüz px':>15}")

    from sentinel.inference.emotion.yunet import YuNetFaceDetector

    yuz_dedektor = YuNetFaceDetector(str(settings.face_detector_weights))
    yuz_ozet: dict[str, Any] = {}
    for yol in videolar:
        bilgi = sonuc.get(yol.stem, {})
        if not bilgi.get("kapiyi_gecen"):
            continue
        cap = cv2.VideoCapture(str(yol))
        if not cap.isOpened():
            continue
        toplam = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        adim = max(1, toplam // max(args.kare, 1))
        kirpinti = 0
        bulunan = 0
        yuz_px: list[float] = []
        try:
            for i in range(args.kare):
                cap.set(cv2.CAP_PROP_POS_FRAMES, min(i * adim, toplam - 1))
                ok, kare = cap.read()
                if not ok:
                    break
                hazir, _lb = letterbox(kare, args.imgsz)
                for d in dedektor.detect([hazir])[0]:
                    if (d.y2 - d.y1) < esik:
                        continue
                    x1, y1 = max(int(d.x1), 0), max(int(d.y1), 0)
                    x2, y2 = int(d.x2), int(d.y2)
                    kirp = hazir[y1:y2, x1:x2]
                    if kirp.size == 0:
                        continue
                    kirpinti += 1
                    # ⚠ `detect` tek bir `FaceBox | None` döndürüyor —
                    # kırpıntının üst %45'indeki EN BELİRGİN yüz.
                    yuz = yuz_dedektor.detect(kirp)
                    if yuz is not None:
                        bulunan += 1
                        yuz_px.append(float(yuz.height))
        finally:
            cap.release()
        if not kirpinti:
            continue
        oran = bulunan / kirpinti
        medyan = statistics.median(yuz_px) if yuz_px else 0.0
        print(f"{yol.stem:<10}{kirpinti:>10}{bulunan:>13}"
              f"{f'%{100 * oran:.0f}':>8}{medyan:>15.0f}")
        yuz_ozet[yol.stem] = {
            "kirpinti": kirpinti, "yuz_bulundu": bulunan,
            "oran": round(oran, 4), "medyan_yuz_px": round(medyan, 1),
        }

    gecen_kamera = [k for k, v in sonuc.items() if v.get("kapiyi_gecen", 0) > 0]
    print(f"\n⭐ Kapıyı en az bir kez geçen kamera: {len(gecen_kamera)}/{len(sonuc)}"
          f" → {', '.join(gecen_kamera) or 'HİÇBİRİ'}")
    print("\n⚠ Bu bir HATA DEĞİL, tasarım sonucu: gözetim kamerasında insan"
          "\n  görüntüde küçüktür. 180 px'lik kapı, yüzü ~20-27 px'ten küçük"
          "\n  olan kırpıntıya pahalı bir model çağırmayı engelliyor —"
          "\n  o boyutta üretilen etiket bilgi değil gürültü olurdu.")

    BENCHMARKS.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = BENCHMARKS / f"ifade_kapi_{damga}.json"
    hedef.write_text(json.dumps({
        "olculdu": datetime.now(UTC).isoformat(),
        "kapi_px": esik,
        "imgsz": args.imgsz,
        "kare_basina_kamera": args.kare,
        "kameralar": sonuc,
        "kapiyi_gecen_kamera": gecen_kamera,
        "yuz_tespiti": yuz_ozet,
        "not": "kapı KİŞİ kutusuna bakıyor; yüz o kutunun ~%10-15'i",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
