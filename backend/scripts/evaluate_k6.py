"""K6 — anomali tespiti ROC-AUC ölçümü (PLAN §1.4, hedef ≥0.75).

Neden bu betik
--------------
K6 bugüne kadar **hiç ölçülmedi.** Oysa PLAN'ın kendi sözü şu:

> *"Hedefi tutturamamak başarısızlık değildir; ÖLÇMEMEK
> başarısızlıktır."*

Ölçüm için gereken iki şey de elimizde:
  · **yer gerçeği** — CUHK Avenue test bölümü, kare seviyesinde piksel
    maskesi (39 anomali segmenti, `data/annotations/cam-19.truth.json`)
  · **sürekli skor** — füzyon katmanının risk skoru
    (`analytics/fusion.py`)

⚠ NEDEN FÜZYON SKORU, KATMAN A SKORU DEĞİL
Katman A tek başına bir sapma sinyali; K6 "sistem anomaliyi ayırt
edebiliyor mu" diye soruyor ve sistemin cevabı füzyondur. Katman A'yı
tek başına ölçmek, sistemin bir parçasını sistem sanmak olurdu.

Yine de **her iki skor da** raporlanıyor: füzyonun tek tek
bileşenlerinden daha iyi olup olmadığı, füzyonun kendisini haklı
çıkaran ya da çürüten sayıdır. Bileşeninden kötü bir füzyon,
karmaşıklığı boşuna eklemiş demektir.

⚠ NEDEN ROC-AUC, DOĞRULUK DEĞİL
Avenue'da anomali kareleri azınlıkta. "Hiçbir şey anomali değil"
diyen bir sistem yüksek doğruluk alır ve hiçbir işe yaramaz. AUC
eşikten bağımsız: "rastgele bir anomali karesi, rastgele bir normal
kareden yüksek skor alma olasılığı".

Ne yapar
--------
Avenue test kliplerini canlı boru hattının aynısından geçirir:

    kare → YOLO26 tespit → BoT-SORT → poz → özellikler
         → Katman A + Katman B + saldırganlık → FÜZYON

Her kare için o karedeki izlerin **azami** risk skorunu alır (bir
karede birinin riskli olması o kareyi riskli yapar), yer gerçeğiyle
karşılaştırır.

⚠ NEDEN AZAMİ, ORTALAMA DEĞİL
Kalabalık bir karede tek bir kişi anormal davranıyorsa, ortalama onu
kalabalığın içinde söndürürdü. Anomali tanımı gereği azınlıktadır.

⚠ ÖLÇÜM KOŞULU: boru hattı KAPALI olmalı — GPU paylaşılmamalı.

Kullanım
--------
    uv run python scripts/evaluate_k6.py
    uv run python scripts/evaluate_k6.py --klip 6 --fps 4
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"
AVENUE = PROJECT_ROOT / "data" / "archive" / "Avenue_Dataset" / "Avenue Dataset"
TRUTH = PROJECT_ROOT / "data" / "annotations" / "cam-19.truth.json"


def _roc_auc(pozitif: list[float], negatif: list[float]) -> float:
    """Mann-Whitney U ile ROC eğrisi altındaki alan.

    ⚠ Eşitlikler 0.5 sayılıyor. Skorların çoğu tam 0.0 olduğunda
    (hiçbir sinyal yok) bu fark yaratıyor: eşitliği 1 saymak AUC'yi
    yapay olarak yükseltirdi.
    """
    if not pozitif or not negatif:
        return float("nan")
    n = sorted(negatif)
    toplam = 0.0
    for p in pozitif:
        # Kaç negatif p'den küçük / eşit — ikili arama ile
        import bisect

        kucuk = bisect.bisect_left(n, p)
        esit = bisect.bisect_right(n, p) - kucuk
        toplam += kucuk + 0.5 * esit
    return toplam / (len(pozitif) * len(negatif))


def _segment_haritasi() -> dict[str, list[tuple[float, float]]]:
    """Klip adı → anomali aralıkları."""
    d = json.loads(TRUTH.read_text(encoding="utf-8"))
    harita: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for s in d["segments"]:
        harita[str(s["clip"])].append((float(s["start_s"]), float(s["end_s"])))
    return harita


def _anomali_mi(araliklar: list[tuple[float, float]], t: float) -> bool:
    return any(bas <= t <= bit for bas, bit in araliklar)


def _klip_skorla(
    yol: Path,
    *,
    dedektor: Any,
    poz: Any,
    ornek_fps: float,
    imgsz: int,
    kamera: str = "avenue",
) -> list[tuple[float, float, float, float, float]]:
    """Bir klibi boru hattından geçirir.

    Dönen: her örneklenen kare için
    `(zaman, füzyon_riski, katman_a, saldırganlık, kural)`.

    ⚠ Bileşenler de dönüyor: füzyonun bileşenlerinden daha iyi olup
    olmadığını görmeden füzyonu savunmak mümkün değil.
    """
    import cv2

    from sentinel.analytics import fusion
    from sentinel.analytics.aggression import TirmanmaSkorlayici
    from sentinel.analytics.anomaly.normalcy import KameraNormali
    from sentinel.analytics.anomaly.rules import KuralMotoru
    from sentinel.analytics.features import pair
    from sentinel.analytics.features import skeleton as sk
    from sentinel.analytics.features.person import cikar
    from sentinel.analytics.features.window import Ornek, PencereDeposu
    from sentinel.core.preprocess import letterbox
    from sentinel.inference.tracker.botsort import BotSortTracker

    cap = cv2.VideoCapture(str(yol))
    kaynak_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    adim = max(1, round(kaynak_fps / ornek_fps))

    takipci = BotSortTracker(frame_rate=int(ornek_fps))
    depo = PencereDeposu()
    kurallar = KuralMotoru()
    tirmanma = TirmanmaSkorlayici()
    fuzyon = fusion.RiskFuzyonu()
    # ⚠ HER KLİP İÇİN TAZE PROFİL DEĞİL — Avenue'nun tüm test klipleri
    # AYNI sahne. Profili klip başına sıfırlamak, kameranın normalini
    # her seferinde yeniden öğrenmek olurdu ve ilk saniyeler hep
    # "anomali" çıkardı. Profil dışarıdan veriliyor.
    # ⚠ Profil KLİP başına değil KAMERA başına. Avenue'nun tüm
    # klipleri aynı sahne ve "her kameranın normali ayrı öğrenilir"
    # ilkesi kamera düzeyinde tanımlı (mimari kural 7). Klip başına
    # sıfırlamak, her klibin ilk saniyelerini yapay anomali yapardı.
    profil = _PROFIL.setdefault(kamera, KameraNormali(camera=kamera))

    cikti: list[tuple[float, float, float, float, float]] = []
    kare_no = 0
    onceki_ts = 0.0
    while True:
        ok, kare = cap.read()
        if not ok:
            break
        if kare_no % adim:
            kare_no += 1
            continue
        hazir, _lb = letterbox(kare, imgsz)
        ts = kare_no / kaynak_fps
        dt = max(0.0, min(5.0, ts - onceki_ts))
        onceki_ts = ts

        tespitler = dedektor.detect([hazir])[0]
        izler = takipci.update(kamera, tespitler, ts)

        risk_azami = a_azami = s_azami = k_azami = 0.0
        if izler:
            pozlar = poz.estimate([hazir], [[t.detection for t in izler]])[0]
            for iz, p in zip(izler, pozlar, strict=False):
                d = iz.detection
                bbox = (d.x1, d.y1, d.x2, d.y2)
                kp = p.keypoints if p is not None and p.found else None
                depo.ekle(
                    kamera,
                    iz.track_id,
                    Ornek(
                        ts=ts, bbox=bbox, kp=kp,
                        olcek=sk.govde_boyu(kp, bbox) if kp is not None else None,
                        ayak=sk.ayak_noktasi(bbox),
                    ),
                )
            kisiler = [cikar(depo.al(kamera, t.track_id)) for t in izler]  # type: ignore[arg-type]
            ciftler = pair.kamera_ciftleri(depo.kamera_pencereleri(kamera))
            skorlar = tirmanma.degerlendir(kamera, kisiler, ciftler, ts)
            bulgular = kurallar.degerlendir(kamera, kisiler, ts, dt)

            tirmanma_map = {s.track_id: s.skor for s in skorlar}
            kural_map: dict[int, float] = {}
            for b in bulgular:
                if b.track_id is not None and b.track_id >= 0:
                    kural_map[b.track_id] = max(kural_map.get(b.track_id, 0.0), b.skor)

            kare_h, kare_w = kare.shape[:2]
            for iz, ozellik in zip(izler, kisiler, strict=False):
                bbox = (
                    iz.detection.x1, iz.detection.y1,
                    iz.detection.x2, iz.detection.y2,
                )
                ayak_x = (bbox[0] + bbox[2]) / 2.0
                anomali_skor, _kanit = profil.skorla(
                    ayak_x, bbox[3], float(kare_w), float(kare_h),
                    ozellik.govde_hizi, None,
                )
                profil.ogren(
                    ayak_x, bbox[3], float(kare_w), float(kare_h),
                    ozellik.govde_hizi, None,
                    duragan=ozellik.oyalanma_s > 0.0,
                )
                sinyaller = fusion.Sinyaller(
                    saldirganlik=tirmanma_map.get(iz.track_id, 0.0),
                    anomali=anomali_skor,
                    kural=kural_map.get(iz.track_id, 0.0),
                )
                sonuc = fuzyon.degerlendir(
                    kamera, iz.track_id, sinyaller, ozellik.tamlik, ts
                )
                if sonuc is not None:
                    risk_azami = max(risk_azami, sonuc.risk)
                a_azami = max(a_azami, anomali_skor)
                s_azami = max(s_azami, tirmanma_map.get(iz.track_id, 0.0))
                k_azami = max(k_azami, kural_map.get(iz.track_id, 0.0))
            profil.kare_ogren(len(izler))

        cikti.append((ts, risk_azami, a_azami, s_azami, k_azami))
        kare_no += 1

    cap.release()
    return cikti


# Klip başına değil KAMERA başına profil: Avenue'nun tüm klipleri aynı
# sahne, ve "her kameranın normali ayrı öğrenilir" ilkesi kamera
# düzeyinde tanımlı (mimari kural 7).
_PROFIL: dict[str, Any] = {}


def main() -> int:
    ap = argparse.ArgumentParser(description="K6 — anomali ROC-AUC")
    ap.add_argument("--klip", type=int, default=99, help="kaç test klibi (yer gerçeği olanlardan)")
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument(
        "--isinma-fps",
        type=float,
        default=25.0,
        help="profil ısıtmasında örnekleme hızı. ⚠ ANALİZ hızından "
             "yüksek olması KASITLI — gerekçe kodda.",
    )
    ap.add_argument(
        "--isinma-klip",
        type=int,
        default=16,
        help="profili ısıtmak için kaç EĞİTİM klibi (0 = ısıtma yok). "
             "⚠ Profil 2000 gözlem görmeden hiçbir skor üretmiyor; "
             "6 klip 1368'de kaldı, hepsini kullanmak gerekiyor.",
    )
    args = ap.parse_args()

    videolar_dizini = AVENUE / "testing_videos"
    if not videolar_dizini.is_dir():
        print(f"Avenue test videoları yok: {videolar_dizini}", file=sys.stderr)
        return 1
    if not TRUTH.is_file():
        print(f"Yer gerçeği yok: {TRUTH}", file=sys.stderr)
        return 1

    from sentinel.inference.detector.yolo import UltralyticsDetector
    from sentinel.inference.pose.yolo import YoloPoseEstimator

    harita = _segment_haritasi()

    # ⚠ YALNIZCA YER GERÇEĞİ OLAN KLİPLER
    #
    # İlk ölçümde tüm test klipleri kullanıldı ve `10.avi` "0 anomali
    # segmenti" diye işlendi. Ama Avenue'nun TEST bölümündeki her klip
    # tanımı gereği anomali içerir — bizim yer gerçeği dosyamız yalnızca
    # 01-09'u kapsıyor (`build_avenue` o kadarını üretmiş).
    #
    # Yer gerçeği olmayan bir klibi ölçüme katmak, içindeki GERÇEK
    # anomalileri "normal" diye etiketlemek demek: sistem onları doğru
    # bulduğunda ceza alır. Ölçüm, ölçtüğü şeyi cezalandırır hâle gelir.
    #
    # Kapsam dışı bırakmak bir kayıp değil dürüstlüktür: "9 klipte
    # ölçtük" demek, "21 klipte ölçtük ama 12'sinin etiketi yoktu"
    # demekten iyidir.
    tumu = sorted(videolar_dizini.glob("*.avi"))
    klipler = [y for y in tumu if y.name in harita][: args.klip]
    atlanan = [y.name for y in tumu if y.name not in harita]
    if not klipler:
        print("yer gerçeği olan test klibi bulunamadı", file=sys.stderr)
        return 1
    if atlanan:
        print(
            f"⚠ {len(atlanan)} klip ÖLÇÜM DIŞI (yer gerçeği yok): "
            f"{', '.join(atlanan[:5])}{'…' if len(atlanan) > 5 else ''}"
        )
    print(f"{len(klipler)} klip · örnekleme {args.fps} FPS · yer gerçeği: {TRUTH.name}")

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "backend" / "models" / "yolo26s.pt",
        imgsz=args.imgsz, half=True,
    )
    poz = YoloPoseEstimator(PROJECT_ROOT / "backend" / "models" / "yolo26s-pose.pt")
    dedektor.warmup(1)
    poz.warmup(8)

    # ─── PROFİL ISITMA — metodolojik olarak zorunlu ───
    #
    # ⚠ İLK ÖLÇÜM BUNSUZ YAPILDI VE KATMAN A HİÇ SKOR ÜRETMEDİ
    # `PROFIL_ASGARI_ORNEK = 2000`: profil bu kadar gözlem görmeden
    # hiçbir şeyi olağandışı saymıyor (soğuk başlangıçta her şey
    # "hiç görülmemiş" olur diye konmuş bir koruma). 2 test klibinde
    # o eşiğe ulaşılmadı; `katman_a` skorlarının %100'ü sıfır çıktı ve
    # AUC tam 0.500 (yani ölçüm hiçbir şey ölçmedi).
    #
    # ⚠ AMA ASIL MESELE EŞİK DEĞİL, DENEY TASARIMI
    # Modülün tanımı "önce normali öğren, sonra sapmayı bul". Profili
    # test verisiyle ısıtmak iki hata birden olurdu:
    #   · test verisinde öğrenmek (anomaliyi de normal öğrenir)
    #   · ilk kareler profilsiz kalır ve ölçümü aşağı çeker
    #
    # Avenue'nun EĞİTİM bölümü tam bu iş için var: tanımı gereği
    # yalnızca normal davranış. Sistem sahada da böyle kurulur —
    # temiz bir dönem izlenir, sonra izlemeye geçilir.
    #
    # ⚠ ISITMA ANALİZDEN HIZLI ÖRNEKLENİYOR — ve bu kasıtlı
    # İkinci ölçümde profil "hazır" oldu (2314 gözlem) ama Katman A
    # yine neredeyse sustu: skorların yalnızca %5.3'ü sıfırdan farklı.
    # Aritmetik açık:
    #
    #     2314 gözlem ÷ 576 hücre (32×18) = hücre başına 4 örnek
    #     HUCRE_ASGARI_ORNEK = 30
    #
    # Yani hiçbir hücre hız/yön istatistiği yapacak kadar veri
    # görmemiş; profil "hazır" ama içi boş.
    #
    # Çözüm eşiği düşürmek DEĞİL — 4 örnekten çıkan bir sapma ölçüsü
    # zaten gürültü olurdu. Çözüm daha çok veri, ve o veri elimizde:
    # analiz 4 FPS'te yapılıyor çünkü GPU bütçesi öyle gerektiriyor,
    # ama PROFİL yalnızca konum ve hız öğreniyor ve bunlar her karede
    # zaten mevcut.
    #
    # ⚠ Gerçek bir kurulumda bu ayrım daha da belirgin: profil
    # GÜNLERCE öğrenir, analiz saniyede birkaç kare yapar. Öğrenme
    # hızını analiz hızına eşitlemek, sistemin sahadaki davranışını
    # değil ölçüm betiğinin kısıtını modellemek olurdu.
    if args.isinma_klip > 0:
        egitim = sorted((AVENUE / "training_videos").glob("*.avi"))[: args.isinma_klip]
        print(
            f"profil ısıtılıyor: {len(egitim)} eğitim klibi (tümü normal) · "
            f"{args.isinma_fps:.0f} FPS örnekleme"
        )
        for i, yol in enumerate(egitim, 1):
            _klip_skorla(
                yol, dedektor=dedektor, poz=poz,
                ornek_fps=args.isinma_fps, imgsz=args.imgsz,
                kamera="avenue",
            )
            print(f"\r  {i}/{len(egitim)}", end="", flush=True)
        profil = _PROFIL.get("avenue")
        ornek = getattr(profil, "toplam_ornek", 0)
        hazir = getattr(profil, "hazir", False)
        print(f"\n  profil: {ornek} gözlem · hazır={hazir}")
        if not hazir:
            print(
                "  ⚠ PROFİL HÂLÂ HAZIR DEĞİL — Katman A yine sıfır üretecek.\n"
                "    --isinma-klip değerini artırın.",
                file=sys.stderr,
            )

    # skor adı → (anomali kareleri, normal kareler)
    seriler: dict[str, tuple[list[float], list[float]]] = {
        ad: ([], []) for ad in ("fuzyon", "katman_a", "saldirganlik", "kural")
    }
    t0 = time.time()
    kapsanan = 0
    for i, yol in enumerate(klipler, 1):
        araliklar = harita.get(yol.name, [])
        kareler = _klip_skorla(
            yol, dedektor=dedektor, poz=poz, ornek_fps=args.fps,
            imgsz=args.imgsz, kamera="avenue",
        )
        for ts, risk, a, s, k in kareler:
            hedef = 0 if _anomali_mi(araliklar, ts) else 1
            kapsanan += 1 - hedef
            for ad, deger in (
                ("fuzyon", risk), ("katman_a", a),
                ("saldirganlik", s), ("kural", k),
            ):
                seriler[ad][hedef].append(deger)
        print(
            f"\r  {i}/{len(klipler)} {yol.name} · {len(kareler)} kare · "
            f"{len(araliklar)} anomali segmenti",
            end="", flush=True,
        )
    print()

    sure = time.time() - t0
    poz_n = len(seriler["fuzyon"][0])
    neg_n = len(seriler["fuzyon"][1])
    print(
        f"\n{poz_n + neg_n} kare · {poz_n} anomali ({poz_n / (poz_n + neg_n):.1%}) · "
        f"{neg_n} normal · {sure:.0f} sn"
    )

    if poz_n == 0:
        print(
            "\n⚠ HİÇ ANOMALİ KARESİ YOK — ölçüm yapılamaz.\n"
            "  Yer gerçeği zaman damgaları klip zamanıyla eşleşmiyor olabilir.",
            file=sys.stderr,
        )
        return 1

    print(f"\n{'SKOR':<14} {'AUC':>7} {'anomali p50':>12} {'normal p50':>11} {'anomali p90':>12}")
    ozet: dict[str, Any] = {}
    for ad, (poz, neg) in seriler.items():
        auc = _roc_auc(poz, neg)
        p_med = statistics.median(poz) if poz else 0.0
        n_med = statistics.median(neg) if neg else 0.0
        p90 = sorted(poz)[int(len(poz) * 0.9)] if poz else 0.0
        ozet[ad] = {
            "auc": round(auc, 4),
            "anomali_p50": round(p_med, 4),
            "normal_p50": round(n_med, 4),
            "anomali_p90": round(p90, 4),
            "sifir_olmayan_oran": round(
                sum(1 for v in poz + neg if v > 0) / max(len(poz) + len(neg), 1), 4
            ),
        }
        print(f"{ad:<14} {auc:>7.3f} {p_med:>12.3f} {n_med:>11.3f} {p90:>12.3f}")

    fuzyon_auc = ozet["fuzyon"]["auc"]
    en_iyi_bilesen = max(
        (ad for ad in seriler if ad != "fuzyon"), key=lambda a: ozet[a]["auc"]
    )
    print(f"\nK6 HEDEFİ: AUC ≥ 0.75 · ölçülen (füzyon): {fuzyon_auc:.3f}")
    print("  " + ("✅ TUTUYOR" if fuzyon_auc >= 0.75 else "❌ TUTMUYOR"))
    print(
        f"\n⚠ FÜZYON KENDİNİ HAKLI ÇIKARIYOR MU?\n"
        f"  en iyi tek bileşen: {en_iyi_bilesen} = {ozet[en_iyi_bilesen]['auc']:.3f}\n"
        f"  füzyon            : {fuzyon_auc:.3f}\n"
        "  " + (
            "füzyon bileşenlerinden İYİ — birleştirme kazandırıyor"
            if fuzyon_auc > ozet[en_iyi_bilesen]["auc"]
            else "⚠ füzyon en iyi bileşeninden İYİ DEĞİL — karmaşıklık "
                 "karşılığını vermiyor, ağırlıklar gözden geçirilmeli"
        )
    )

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "kriter": "K6",
        "hedef_auc": 0.75,
        "veri_seti": "CUHK Avenue (testing)",
        "klip_sayisi": len(klipler),
        "ornekleme_fps": args.fps,
        "isinma_fps": args.isinma_fps,
        "isinma_klip": args.isinma_klip,
        "profil_gozlem": getattr(_PROFIL.get("avenue"), "toplam_ornek", 0),
        "kare_toplam": poz_n + neg_n,
        "kare_anomali": poz_n,
        "kare_normal": neg_n,
        "sure_s": round(sure, 1),
        "sonuc": ozet,
        "k6_tutuyor": bool(fuzyon_auc >= 0.75),
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"k6_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
