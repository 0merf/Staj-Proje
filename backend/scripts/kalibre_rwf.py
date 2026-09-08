"""RWF-2000 için ölü bölge eşiklerini KENDİ verisinden kalibre eder.

Neden bu betik — teşhisin sonucu
---------------------------------
`evaluate_kaskad.py` + `diagnose_iskelet.py` şu zinciri ortaya çıkardı:

  1. Kural kapısı kavga kliplerinin %52'sini eliyor
  2. Sebep `bilek` bileşeninin sıfır olması
  3. Ama poz tahmini ÇALIŞIYOR (%89.6 başarı, bilek %100 görünür)
  4. Yani sorun poz değil, **eşikler**

`aggression.py` ölü bölge tabanlarını sabit tutuyor:

    taban_bilek_hiz      = 1.80   ← gövde boyu / saniye
    taban_bilek_sarsinti = 1.40

Bu sayılar **kamera çiftliğinde** ölçüldü (`benchmark_features.py`;
Oxford caddesi + PETS, 720p, 4 FPS). RWF-2000 başka bir dünya: farklı
çözünürlük, farklı kişi ölçeği, farklı çekim mesafesi.

Ölçülen sonuç: RWF kavga karelerinin **%90'ında `bilek` tam sıfır**,
sıfır olmayanların medyanı 0.089 — kapı eşiği 0.15'in altında. Modül
bu veri setinde pratikte **sağır.**

⚠⚠ BU, KENDİ MİMARİ KURALIMIZIN İHLALİ
Mimari kural 7: *"Her kameranın normali ayrı öğrenilir."* Katman A bunu
uyguluyor (kamera başına profil). Saldırganlık modülü uygulamıyor —
çiftlik geneli tek taban kullanıyor. Kod bunu itiraf da ediyor:

    # şimdilik çiftlik geneli tek taban,
    # kamera başına taban Faz 5 işi.

Faz 5 gelmedi. Bu betik o borcu kapatıyor.

Yöntem
------
⚠ TABANLAR YALNIZCA `nonfight` KLİPLERİNDEN ölçülüyor.

Ölü bölgenin tanımı *"normal davranışın üstü"*. Tabanı kavga
kliplerini de içeren bir dağılımdan hesaplamak, ölçmek istediğimiz
olayı normalin tanımına karıştırmak olurdu — sınıflandırıcıya
etiket sızdırmanın (label leakage) ders kitabı örneği.

    taban = normal davranışın p90
    doyum = normal davranışın p99'unun üstü (p99 × 1.5)

Bu, `aggression.py`'nin özgün gerekçesiyle AYNI kural — yalnızca
başka bir veri kümesine uygulanmış hâli.

⚠ ÖLÇÜM KOŞULU: boru hattı KAPALI (GPU paylaşılmamalı).

Kullanım
--------
    uv run python scripts/kalibre_rwf.py --klip 120
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"
RWF = PROJECT_ROOT / "data" / "datasets" / "RWF-2000"
CIKTI = PROJECT_ROOT / "data" / "_tmp" / "rwf_esikler.json"
CIFTLIK = PROJECT_ROOT / "data" / "videos"
CIFTLIK_CIKTI = PROJECT_ROOT / "data" / "_tmp" / "ciftlik_esikler.json"

TOHUM = 42

# ─── FİZİKSEL MAKULİYET SINIRI ───
#
# ⚠⚠ Bu sınır olmadan kalibrasyon GÜRÜLTÜYÜ kalibre ediyordu.
#
# Çiftlik ölçümünde p99 = 24.2 gövde/sn çıktı. Bir insanın bileği
# saniyede 24 gövde boyu yol alamaz: profesyonel bir boksörün yumruğu
# ~9 m/s, ortalama gövde boyu ~1.7 m → ~5.3 gövde/sn. Üstelik o bir
# ANLIK tepe; pencere içindeki p75 değeri hiçbir zaman oraya varmaz.
#
# Yani 24.2 hareket değil, **eklem tahmini hatası**: poz modeli bir
# karede bileği yanlış yere koyuyor, iki kare arasındaki "hız"
# fırlıyor.
#
# ⚠ Sınırın üstü ATILIYOR, kırpılmıyor. Kırpmak (clip) o örneği
# sınırda bir gözlem gibi sayardı; oysa o bir gözlem değil, bir
# ölçüm hatası. Atmak, "bu veriyi ölçemedim" demek — ve bu projenin
# tekrarlayan ilkesi (`person.py`: eksik ≠ sıfır).
#
# 8.0 seçildi: boksör tepesinin (~5.3) belirgin üstünde, yani gerçek
# bir uç hareketi elemez; ama 24'ün çok altında.
MAKUL_UST_SINIR = 8.0

# Ham (bantlanmamış) toplanacak büyüklükler → `Esikler` alan adları.
# ⚠ 07.09.2026 — p75 ALANLARINA GEÇİLDİ (P-47)
# `aggression.py` artık `bilek_hizi_p75` okuyor. Eşikleri hâlâ `azami`
# dağılımından türetmek, skorlanan büyüklükten BAŞKA bir büyüklüğün
# istatistiğini kullanmak olurdu — ve p75 değerleri azaminin ~%26'sı
# olduğu için ölü bölge her şeyi yutardı (modül sessizce sağırlaşır).
ALANLAR = {
    "bilek_hizi_p75": ("taban_bilek_hiz", "doyum_bilek_hiz"),
    "bilek_sarsintisi_p75": ("taban_bilek_sarsinti", "doyum_bilek_sarsinti"),
    "hareket_enerjisi": ("taban_enerji", "doyum_enerji"),
}


def _ham_topla(
    yol: Path, *, dedektor: Any, poz: Any, ornek_fps: float, imgsz: int
) -> dict[str, list[float]]:
    """Bir klipten HAM (bantlanmamış) özellik değerlerini toplar.

    ⚠ `aggression.py` çağrılmıyor — o zaten bantlıyor. Buradaki amaç
    bantlamadan ÖNCEKİ dağılımı görmek; bantlanmış değerden taban
    türetmek, ölçmek istediğimiz şeyi ölçtüğümüz aracın içinden
    okumak olurdu.
    """
    import cv2

    from sentinel.analytics.features import skeleton as sk
    from sentinel.analytics.features.person import cikar
    from sentinel.analytics.features.window import Ornek, PencereDeposu
    from sentinel.core.preprocess import letterbox
    from sentinel.inference.tracker.botsort import BotSortTracker

    cap = cv2.VideoCapture(str(yol))
    kaynak_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    adim = max(1, round(kaynak_fps / ornek_fps))
    takipci = BotSortTracker(frame_rate=int(max(1, ornek_fps)))
    depo = PencereDeposu()

    toplanan: dict[str, list[float]] = {a: [] for a in ALANLAR}
    kare_no = 0
    kamera = yol.stem
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
                bbox = (d.x1, d.y1, d.x2, d.y2)
                kp = p.keypoints if p is not None and p.found else None
                depo.ekle(
                    kamera, iz.track_id,
                    Ornek(
                        ts=ts, bbox=bbox, kp=kp,
                        olcek=sk.govde_boyu(kp, bbox) if kp is not None else None,
                        ayak=sk.ayak_noktasi(bbox),
                    ),
                )
            for iz in izler:
                oz = cikar(depo.al(kamera, iz.track_id))  # type: ignore[arg-type]
                for alan in ALANLAR:
                    v = getattr(oz, alan, None)
                    # ⚠ `None` ATLANIYOR, sıfır sayılmıyor. "Ölçemedim"
                    # ile "sıfır ölçtüm" farklı şeyler; ikincisi
                    # dağılımı aşağı çeker ve tabanı yapay olarak
                    # düşürürdü (person.py modül başlığındaki ilke).
                    if v is not None:
                        toplanan[alan].append(float(v))
        kare_no += 1

    cap.release()
    return toplanan


def main() -> int:
    ap = argparse.ArgumentParser(description="RWF için ölü bölge kalibrasyonu")
    ap.add_argument("--klip", type=int, default=120, help="kaç NORMAL klip/kamera")
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--ciftlik", action="store_true",
                    help="⚠ ÇİFTLİK MODU: RWF yerine data/videos/ altındaki 20 kamera "
                         "videosunu kalibre eder. Canlı sistemin eşikleri buradan "
                         "gelir — mimari kural 7'nin ('her kameranın normali ayrı "
                         "öğrenilir') saldırganlık modülündeki karşılığı.")
    ap.add_argument("--kavga", action="store_true",
                    help="⚠ TANI MODU: kavga kliplerini de ölçüp karşılaştırır. "
                         "Eşik türetmek için KULLANILMAZ (etiket sızıntısı) — "
                         "yalnızca 'bu özellik ayırt ediyor mu' sorusu için.")
    args = ap.parse_args()

    from sentinel.inference.detector.yolo import UltralyticsDetector
    from sentinel.inference.pose.yolo import YoloPoseEstimator

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "models" / "yolo26s.pt",
        imgsz=args.imgsz, half=True,
    )
    poz = YoloPoseEstimator(PROJECT_ROOT / "models" / "yolo26s-pose.pt")
    dedektor.warmup(1)
    poz.warmup(8)

    # ⚠ YALNIZCA EĞİTİM BÖLÜMÜNÜN `nonfight` KLİPLERİ
    # `val` dokunulmuyor: eşikler val'dan türetilirse, val üzerinde
    # bildirilen skor kendi kalibrasyonundan beslenmiş olur. Bu,
    # ADR-0007'nin kaydettiği eşik-yanlılığının daha kötü bir hâli
    # olurdu — orada eşik test kümesinde ARANIYORDU, burada test
    # kümesinden TÜRETİLMİŞ olurdu.
    if args.ciftlik:
        # ⚠ ÇİFTLİK VİDEOLARI "NORMAL" SAYILIYOR — ve bu bir VARSAYIM.
        # Kaynaklar (Oxford yaya caddesi, PETS meydanı, VIRAT) tanımı
        # gereği normal davranış içeriyor. İstisna cam-16 (UR Fall,
        # düşme) ve cam-17 (RWF kavga) — ikisi de KASTEN olay içeriyor
        # ve tabanı yukarı çekerlerdi.
        haric = {"cam-16", "cam-17"}
        klipler = [
            y for y in sorted(CIFTLIK.glob("*.mp4")) if y.stem not in haric
        ][: args.klip]
        print(f"{len(klipler)} çiftlik kamerası (cam-16/17 hariç — olay içeriyorlar)"
              f" · {args.fps} FPS örnekleme")
    else:
        sinif = "fight" if args.kavga else "nonfight"
        klipler = sorted((RWF / "train" / sinif).glob("*.avi"))
        random.Random(TOHUM).shuffle(klipler)  # noqa: S311 — kripto değil
        klipler = klipler[: args.klip]
        print(f"{len(klipler)} klip (train/{sinif}) · {args.fps} FPS örnekleme")

    havuz: dict[str, list[float]] = {a: [] for a in ALANLAR}
    t0 = time.time()
    for i, yol in enumerate(klipler, 1):
        for alan, degerler in _ham_topla(
            yol, dedektor=dedektor, poz=poz,
            ornek_fps=args.fps, imgsz=args.imgsz,
        ).items():
            havuz[alan].extend(degerler)
        print(f"\r  {i}/{len(klipler)} ({time.time() - t0:.0f} sn)", end="", flush=True)
    print()

    from sentinel.analytics.aggression import VARSAYILAN

    print(f"\n{'BÜYÜKLÜK':<20} {'n':>7} {'p50':>8} {'p90':>8} {'p99':>8}"
          f" | {'ESKİ taban':>10} {'YENİ taban':>10}")
    yeni: dict[str, float] = {}
    ozet: dict[str, Any] = {}
    for alan, (taban_ad, doyum_ad) in ALANLAR.items():
        ham = havuz[alan]
        d = sorted(v for v in ham if v <= MAKUL_UST_SINIR)
        # ⚠ Atılan oran bir GÜRÜLTÜ ÖLÇÜSÜ — raporlanıyor, gizlenmiyor.
        # Yüksekse poz tahmini o veri setinde güvenilmez demektir.
        atilan = len(ham) - len(d)
        atilan_oran = atilan / max(len(ham), 1)
        if len(d) < 50:
            print(f"{alan:<20} {len(d):>7}  ⚠ yetersiz örnek, atlanıyor")
            continue
        p50 = statistics.median(d)
        p90 = d[int(len(d) * 0.90)]
        p99 = d[int(len(d) * 0.99)]
        eski_taban = getattr(VARSAYILAN, taban_ad)
        yeni[taban_ad] = round(p90, 3)
        # ⚠ Doyum p99'un 1.5 KATI. p99 hâlâ NORMAL davranış; doyum
        # (bileşenin 1.0 olduğu nokta) ancak normali açıkça aşan
        # harekete ayrılmalı. `aggression.py`'deki özgün gerekçe aynı.
        # ⚠ DOYUM p99'DAN DEĞİL p90'IN KATINDAN
        # p99, fiziksel sınır uygulandıktan sonra bile uzun kuyruklu
        # (gürültünün bir kısmı sınırın altında kalıyor). p90 sağlam
        # bir üst çeyrek göstergesi; doyumu onun 2 katına koymak
        # "normalin belirgin üstü" tanımını koruyor ve gürültüye
        # dayanıklı.
        yeni[doyum_ad] = round(p90 * 2.0, 3)
        ozet[alan] = {"n": len(d), "p50": round(p50, 3), "p90": round(p90, 3),
                      "p99": round(p99, 3), "eski_taban": eski_taban,
                      "yeni_taban": yeni[taban_ad], "yeni_doyum": yeni[doyum_ad],
                      "makul_disi_atilan": atilan,
                      "makul_disi_oran": round(atilan_oran, 4)}
        print(f"{alan:<20} {len(d):>7} {p50:>8.3f} {p90:>8.3f} {p99:>8.3f}"
              f" | {eski_taban:>10.2f} {yeni[taban_ad]:>10.2f} {atilan_oran:>9.2%}")

    print("\n⭐ YORUM")
    for alan, o in ozet.items():
        oran = o["eski_taban"] / max(o["yeni_taban"], 1e-9)
        if oran > 1.5:
            print(f"  {alan}: eski taban YENİDEN {oran:.1f} KAT büyük →")
            print("     bu veri setinde bileşen neredeyse hep sıfır üretiyordu.")
        elif oran < 0.67:
            print(f"  {alan}: eski taban yeniden {1 / oran:.1f} kat KÜÇÜK →")
            print("     bileşen bu veri setinde fazla duyarlıydı.")
        else:
            print(f"  {alan}: eski taban makul (×{oran:.2f}) — bu bileşen taşınabilir.")

    hedef_dosya = CIFTLIK_CIKTI if args.ciftlik else CIKTI
    hedef_dosya.parent.mkdir(parents=True, exist_ok=True)
    hedef_dosya.write_text(json.dumps(yeni, ensure_ascii=False, indent=1), encoding="utf-8")

    kayit = {
        "olculdu": datetime.now(UTC).isoformat(),
        "deney": "RWF-2000 ölü bölge kalibrasyonu",
        "kaynak": "RWF-2000 train/nonfight (val'a DOKUNULMADI)",
        "klip": len(klipler),
        "ornekleme_fps": args.fps,
        "yontem": ("taban = normal p90 · doyum = p90 × 2.0 · "
                   f"fiziksel makuliyet sınırı {MAKUL_UST_SINIR} gövde/sn üstü ATILDI"),
        "makul_ust_sinir": MAKUL_UST_SINIR,
        "dagilim": ozet,
        "yeni_esikler": yeni,
        "gerekce": (
            "Eşikler kamera çiftliğinde ölçülmüştü ve RWF-2000'e taşınmıyor. "
            "Mimari kural 7 ('her kameranın normali ayrı öğrenilir') "
            "saldırganlık modülünde uygulanmamıştı."
        ),
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"kalibrasyon_rwf_{datetime.now():%Y%m%d-%H%M%S}.json"
    hedef.write_text(json.dumps(kayit, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    print(f"eşikler: {hedef_dosya.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
