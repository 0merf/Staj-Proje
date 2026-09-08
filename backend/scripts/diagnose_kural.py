"""Kural yolu tanısı — skor neden her dönemde SABİT? (P-52)

⭐ NEDEN BU BETİK
----------------
K8 ölçümlerinde kural yolu iki farklı videoda da kavgayı normalden
ayırt etmedi:

    cam-15  (sabit CCTV, 3.0 kişi/kare) : oran 1.01
    cam-15h (elde telefon, 6.5 kişi)    : oran 1.00

Ve skor her dönemde neredeyse aynı çıkıyor:

    normal 0.064 · tırmanma 0.059 · kavga 0.067

Bir skorun kavgada normalle aynı olması "kavgayı göremiyor" demek
değil zorunlu olarak — skor SABİT de olabilir, yani hiçbir şeye tepki
vermiyor olabilir. İkisi farklı arızalar ve farklı çözümleri var:

    "görüyor ama ayıramıyor"  → eşik/ağırlık sorunu
    "hiç tepki vermiyor"      → bileşenler ÖLÜ, eşik değiştirmek boşuna

Bu betik hangisi olduğunu söyler: skoru beş bileşenine ayırıp her
birinin dönem bazında dağılımını, ham girdisini ve ölü bölge tabanını
yan yana basar.

⚠ ÖLÇÜM DEĞİL TANI
------------------
Buradan çıkan sayılar bir başarı ölçütü değil; hangi kutunun boş
olduğunu gösteren bir röntgen. Karar `evaluate_k8_video.py`de veriliyor.

Kullanım:
    uv run python scripts/diagnose_kural.py --kamera cam-15
    uv run python scripts/diagnose_kural.py --kamera cam-15h
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIDEOLAR = PROJECT_ROOT / "data" / "videos"
ETIKETLER = PROJECT_ROOT / "data" / "annotations"
BENCHMARKS = PROJECT_ROOT / "benchmarks"

BILESEN_ADLARI = ("yakinlik", "bilek", "yaklasma", "enerji", "durus")

# Ham girdiler ve karşılık gelen ölü bölge tabanları — "bileşen neden
# sıfır" sorusunu ancak ikisi yan yana konunca cevaplayabiliyoruz.
HAM_TABAN = (
    ("bilek_hizi_p75", "taban_bilek_hiz"),
    ("bilek_sarsintisi_p75", "taban_bilek_sarsinti"),
    ("hareket_enerjisi", "taban_enerji"),
)


def _seri(
    yol: Path, *, ornek_fps: float, imgsz: int,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Her karede en riskli kişinin bileşen kırılımını üretir."""
    import cv2

    from sentinel.analytics.aggression import TirmanmaSkorlayici
    from sentinel.analytics.features import pair
    from sentinel.analytics.features import skeleton as sk
    from sentinel.analytics.features.person import cikar
    from sentinel.analytics.features.window import Ornek, PencereDeposu
    from sentinel.core.preprocess import letterbox
    from sentinel.inference.detector.yolo import UltralyticsDetector
    from sentinel.inference.pose.yolo import YoloPoseEstimator
    from sentinel.inference.tracker.botsort import BotSortTracker

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "models" / "yolo26s.pt",
        imgsz=imgsz, half=True,
    )
    poz = YoloPoseEstimator(PROJECT_ROOT / "models" / "yolo26s-pose.pt")
    dedektor.warmup(1)
    poz.warmup(8)

    depo = PencereDeposu()
    takipci = BotSortTracker(frame_rate=int(max(1, ornek_fps)))
    skorlayici = TirmanmaSkorlayici()

    cap = cv2.VideoCapture(str(yol))
    kaynak_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    adim = max(1, round(kaynak_fps / ornek_fps))
    kamera = yol.stem

    cikti: list[dict[str, Any]] = []
    kare_no = 0
    while True:
        ok, kare = cap.read()
        if not ok:
            break
        if kare_no % adim:
            kare_no += 1
            continue
        hazir, _lb = letterbox(kare, imgsz)
        ts = kare_no / kaynak_fps

        izler = takipci.update(kamera, dedektor.detect([hazir])[0], ts)
        if izler:
            pozlar = poz.estimate([hazir], [[t.detection for t in izler]])[0]
            for iz, p in zip(izler, pozlar, strict=False):
                d = iz.detection
                kp = p.keypoints if p is not None and p.found else None
                depo.ekle(
                    kamera, iz.track_id,
                    Ornek(
                        ts=ts, bbox=(d.x1, d.y1, d.x2, d.y2), kp=kp,
                        olcek=sk.govde_boyu(kp, (d.x1, d.y1, d.x2, d.y2))
                        if kp is not None else None,
                        ayak=sk.ayak_noktasi((d.x1, d.y1, d.x2, d.y2)),
                    ),
                )
            kisiler = [cikar(depo.al(kamera, t.track_id)) for t in izler]  # type: ignore[arg-type]
            ciftler = pair.kamera_ciftleri(depo.kamera_pencereleri(kamera))
            skorlar = skorlayici.degerlendir(kamera, kisiler, ciftler, ts)

            satir: dict[str, Any] = {"ts": ts, "kisi": float(len(kisiler))}
            if skorlar:
                en = max(skorlar, key=lambda s: s.skor)
                satir["skor"] = float(en.skor)
                for b in BILESEN_ADLARI:
                    satir[b] = float(en.bilesenler.get(b, 0.0))
                # Ham girdiler: hangi kişiden geldiğini de bilelim
                hedef = next(
                    (k for k in kisiler if k.track_id == en.track_id), None
                )
                if hedef is not None:
                    for alan, _t in HAM_TABAN:
                        v = getattr(hedef, alan, None)
                        if v is not None:
                            satir[f"ham_{alan}"] = float(v)
            # ⭐ SAHNEDEKİ AZAMİ — "kural doğru kişiyi mi seçiyor?"
            # `en riskli kişi` toplam skora göre seçiliyor ve o skorun
            # en ağır bileşeni `yakinlik` (0.30). Yakınlık dar bir
            # mekânda doyuma ulaşıyorsa, seçilen kişi EN YAKIN olan
            # oluyor — en hareketli olan değil.
            hepsi = [
                k.bilek_hizi_p75 for k in kisiler
                if k.track_id >= 0 and k.bilek_hizi_p75 is not None
            ]
            if hepsi:
                satir["ham_sahne_azami_bilek"] = float(max(hepsi))

            # Çift mesafesi — yakınlık bileşeninin ham girdisi
            mesafeler = [
                c.en_yakin_mesafe for c in ciftler if c.en_yakin_mesafe is not None
            ]
            if mesafeler:
                satir["ham_en_yakin_mesafe"] = float(min(mesafeler))
            cikti.append(satir)
        kare_no += 1

    cap.release()
    # ⚠ ETKİN TABANI DÖNDÜR — tahmin etmeyelim. Uyarlanabilir taban
    # (P-52) kameranın kendi dağılımından türüyor; hangi değere
    # oturduğunu görmeden "işe yaradı/yaramadı" denemez.
    etkin = {
        alan: skorlayici.kamera_tabani(kamera, alan)
        for alan in ("bilek_hizi_p75", "bilek_sarsintisi_p75", "hareket_enerjisi")
    }
    return cikti, etkin


def main() -> int:
    ap = argparse.ArgumentParser(description="Kural yolu bileşen tanısı")
    ap.add_argument("--kamera", default="cam-15")
    ap.add_argument("--fps", type=float, default=2.75)
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    video = VIDEOLAR / f"{args.kamera}.mp4"
    truth = ETIKETLER / f"{args.kamera}.gorsel.json"
    if not video.is_file() or not truth.is_file():
        print(f"❌ Video ya da yer gerçeği yok: {video} / {truth}", file=sys.stderr)
        return 1

    yg = json.loads(truth.read_text(encoding="utf-8"))
    segmentler = [(float(s["start_s"]), float(s["end_s"])) for s in yg["segments"]]
    dogru_normal = [
        (float(a), float(b)) for a, b in yg.get("dogrulanmis_normal", [])
    ]

    from sentinel.analytics.aggression import VARSAYILAN

    print(f"{args.kamera} · {args.fps} FPS · tanı koşuyor…")
    t0 = time.time()
    seri, etkin_taban = _seri(video, ornek_fps=args.fps, imgsz=args.imgsz)
    # Isınma: özellik penceresi dolmadan üretilen skorlar atılıyor.
    seri = [s for s in seri if s["ts"] >= 6.0]
    print(f"{len(seri)} kare · {time.time() - t0:.0f} sn\n")

    def _donem(ts: float) -> str:
        if any(b <= ts <= e for b, e in segmentler):
            return "kavga"
        if dogru_normal:
            return ("normal" if any(a <= ts <= b for a, b in dogru_normal)
                    else "haric")
        return "normal"

    def _med(alan: str, d: str) -> float | None:
        v = [s[alan] for s in seri if alan in s and _donem(s["ts"]) == d]
        return statistics.median(v) if v else None

    def _oran(alan: str, d: str) -> float:
        """O dönemde bileşenin SIFIR OLMADIĞI karelerin oranı."""
        v = [s.get(alan, 0.0) for s in seri if _donem(s["ts"]) == d]
        return sum(1 for x in v if x > 1e-9) / len(v) if v else 0.0

    print("═══ BİLEŞEN KIRILIMI (medyan · ateşleme oranı) ═══")
    print(f"{'bileşen':<12} {'ağırlık':>8} {'normal':>9} {'kavga':>9} "
          f"{'oran':>7} | {'ateşleme% N':>12} {'ateşleme% K':>12}")
    tani: dict[str, Any] = {}
    for b in BILESEN_ADLARI:
        n, k = _med(b, "normal"), _med(b, "kavga")
        agirlik = getattr(VARSAYILAN, f"a_{b}")
        oran = (k / n) if (n and n > 1e-9 and k is not None) else float("nan")
        an, ak = _oran(b, "normal"), _oran(b, "kavga")
        print(f"{b:<12} {agirlik:>8.2f} {n if n is not None else 0.0:>9.4f} "
              f"{k if k is not None else 0.0:>9.4f} {oran:>7.2f} | "
              f"{an:>11.0%} {ak:>11.0%}")
        tani[b] = {"agirlik": agirlik, "normal_p50": n, "kavga_p50": k,
                   "atesleme_normal": round(an, 4), "atesleme_kavga": round(ak, 4)}

    s_n, s_k = _med("skor", "normal"), _med("skor", "kavga")
    print(f"\n{'SKOR':<12} {'':>8} {s_n or 0:>9.4f} {s_k or 0:>9.4f} "
          f"{(s_k / s_n) if s_n else 0:>7.2f}")

    print("\n═══ HAM GİRDİ ⟷ ÖLÜ BÖLGE TABANI ═══")
    print(f"{'büyüklük':<24} {'ETKİN':>8} {'normal p50':>11} {'kavga p50':>10} "
          f"{'kavga/taban':>12}")
    for alan, taban_adi in HAM_TABAN:
        sabit = getattr(VARSAYILAN, taban_adi)
        taban = etkin_taban.get(alan, sabit)
        n, k = _med(f"ham_{alan}", "normal"), _med(f"ham_{alan}", "kavga")
        if k is None:
            continue
        print(f"{alan:<24} {taban:>8.3f} {n if n else 0:>11.3f} {k:>10.3f} "
              f"{k / taban:>12.2f}   (sabit {sabit:.3f})")
        tani[f"ham_{alan}"] = {"taban": taban, "normal_p50": n, "kavga_p50": k,
                               "kavga_taban_orani": round(k / taban, 3)}

    sn, sk_ = _med("ham_sahne_azami_bilek", "normal"), _med("ham_sahne_azami_bilek", "kavga")
    if sk_ is not None:
        secilen_k = _med("ham_bilek_hizi_p75", "kavga") or 0.0
        print(f"{'⭐ sahne AZAMİ bilek':<24} {'—':>8} {sn if sn else 0:>11.3f} "
              f"{sk_:>10.3f}   (kuralın seçtiği: {secilen_k:.3f})")
        tani["ham_sahne_azami_bilek"] = {"normal_p50": sn, "kavga_p50": sk_}

    m_n, m_k = _med("ham_en_yakin_mesafe", "normal"), _med("ham_en_yakin_mesafe", "kavga")
    if m_k is not None:
        print(f"{'en_yakin_mesafe (gövde)':<24} {'—':>8} "
              f"{m_n if m_n else 0:>11.3f} {m_k:>10.3f}")
        tani["ham_en_yakin_mesafe"] = {"normal_p50": m_n, "kavga_p50": m_k}

    print("\n═══ TEŞHİS ═══")
    olu = [b for b in BILESEN_ADLARI if tani[b]["atesleme_kavga"] < 0.05]
    zayif = [
        b for b in BILESEN_ADLARI
        if b not in olu and (tani[b]["kavga_p50"] or 0) <= (tani[b]["normal_p50"] or 0)
    ]
    olu_agirlik = sum(tani[b]["agirlik"] for b in olu)
    if olu:
        print(f"❌ ÖLÜ bileşenler (kavgada bile <%5 ateşliyor): {', '.join(olu)}")
        print(f"   Toplam ağırlıkları: {olu_agirlik:.2f} / 1.00 "
              f"→ skorun %{olu_agirlik * 100:.0f}'i HİÇ KULLANILMIYOR")
    if zayif:
        print(f"⚠ AYIRT ETMEYEN bileşenler (kavga ≤ normal): {', '.join(zayif)}")
    if not olu and not zayif:
        print("✅ Bileşenler ateşliyor ve ayırt ediyor — sorun eşik/ağırlıkta.")

    BENCHMARKS.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = BENCHMARKS / f"kural_tanisi_{args.kamera}_{damga}.json"
    hedef.write_text(json.dumps({
        "olculdu": datetime.now(UTC).isoformat(),
        "kamera": args.kamera, "fps": args.fps, "kare": len(seri),
        "skor": {"normal_p50": s_n, "kavga_p50": s_k},
        "bilesenler": tani,
        "olu_bilesenler": olu,
        "olu_agirlik": round(olu_agirlik, 3),
        "etkin_taban": {k: round(v, 4) for k, v in etkin_taban.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
