"""K8 — erken uyarı avansı (PLAN §1.4, hedef ≥ 2 saniye).

⭐ PROJENİN ÖZGÜN KATKISI
------------------------
Şiddet tespiti literatürü neredeyse tümüyle tek bir soruyu soruyor:
*"bu klipte şiddet var mı?"* ve doğruluk/F1 raporluyor. RWF-2000'in
kendi etiketi de klip seviyesinde ve bu soruya göre tasarlanmış.

Bu proje ikinci bir soru soruyor: **"kaç saniye ÖNCE söyleyebildik?"**

Fark bir gözetim sisteminde belirleyici:

    olaydan SONRA doğru sınıflandırma  → adli kayıt
    olaydan ÖNCE  uyarı                 → müdahale imkânı

Sistemin saldırganlık modülü bunun için tasarlandı: eşiği geçen bir
skor değil, **yükselen** bir skor arıyor (`aggression.py ·
tirmanma_egimi`). K8 o tasarımın karşılığını verip vermediğini ölçen
tek sayı.

Nasıl ölçülüyor
---------------
Her etiketli kavga klibi için:

    avans = (olayın başladığı an) − (skorun eşiği İLK geçtiği an)

    avans > 0  → sistem olaydan ÖNCE uyardı  ✅
    avans = 0  → tam olay anında
    avans < 0  → GEÇ kaldı (olay başladıktan sonra fark etti)
    avans yok  → hiç eşiği geçmedi (kaçırma)

⚠ AZAMİ SKOR DEĞİL, SKOR GEÇMİŞİ
`evaluate_rwf.py` (K5) her klipten yalnızca **azami** skoru alıyor —
"bu klipte en yüksek ne kadar riskliydi". K8 için bu yetmez: azami
skorun ne zaman oluştuğu kaybolmuş oluyor. Bu betik skorun **tüm
zaman serisini** tutuyor ve eşiği ilk geçtiği ANI arıyor.

⚠ EŞİK SEÇİMİ K8'İN EN KRİTİK YERİ — ve tek başına raporlanamaz
Eşiği düşürmek avansı büyütür: sistem daha erken bağırır. Ama aynı
eşik normal kliplerde de bağırır, yani **yanlış alarm artar.** Bu
yüzden betik tek bir avans sayısı değil, birden çok eşik için
**avans ↔ yanlış alarm** eğrisini üretiyor.

Bir gözetim sisteminde bu takas gizlenemez: "3 saniye önceden haber
veriyoruz" cümlesi, yanında yanlış alarm oranı olmadan anlamsızdır.

⚠ NORMAL KLİPLER DE SKORLANIYOR — yanlış alarm payı için
`nonfight` bölümünden aynı sayıda klip skorlanıp her eşikte kaçının
alarm verdiği sayılıyor. Bu, K7 ile aynı ruhta ama klip bazlı.

Ön koşul
--------
`data/annotations/rwf_k8.json` — `scripts/etiketle_k8.py` ile elle
üretiliyor (~1 saat). Etiket yoksa bu betik çalışmaz ve **çalışmaması
doğrudur**: yer gerçeği olmadan "avans" diye bir sayı üretmek,
ölçmediğimiz bir şeyi ölçtük demek olurdu.

⚠ ÖLÇÜM KOŞULU: boru hattı KAPALI olmalı — GPU paylaşılmamalı (P-36).

Kullanım
--------
    uv run python scripts/evaluate_k8.py
    uv run python scripts/evaluate_k8.py --normal 30
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
RWF = PROJECT_ROOT / "data" / "datasets" / "RWF-2000" / "val"
ETIKET = PROJECT_ROOT / "data" / "annotations" / "rwf_k8.json"

# Denenecek eşikler. `aggression.py`'deki üretim eşiğini (uyarı girişi)
# içine alacak şekilde geniş tutuluyor: tek bir eşikte ölçmek, o eşiğin
# şanslı ya da şanssız olduğunu gizlerdi.
ESIKLER = (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50)

TOHUM = 42  # `etiketle_k8.py` ve `evaluate_rwf.py` ile AYNI


def _bootstrap_medyan(
    degerler: list[float], *, tekrar: int = 5000, tohum: int = 20260910,
) -> list[float] | None:
    """Medyanın %95 güven aralığı (yerine koyarak yeniden örnekleme).

    ⚠ Klipler bağımsız birim: her klip bir olay. Kare seviyesinde
    bir bağımlılık yok, bu yüzden basit bootstrap doğru (K6'daki küme
    bootstrap'ı orada gerekiyordu çünkü orada birim KARE değil KLİPTİ).

    `None` = örneklem yok ya da tek gözlem; aralık hesaplanamaz.
    ⚠ `None` "aralık sıfır" demek DEĞİL, "ölçemedim" demek.
    """
    import random

    if len(degerler) < 2:
        return None
    # ⚠ S311: istatistik örneklemesi, kriptografi değil.
    rng = random.Random(tohum)  # noqa: S311
    n = len(degerler)
    medyanlar = sorted(
        statistics.median([degerler[rng.randrange(n)] for _ in range(n)])
        for _ in range(tekrar)
    )

    def _y(oran: float) -> float:
        i = (len(medyanlar) - 1) * oran
        alt, ust = int(i), min(int(i) + 1, len(medyanlar) - 1)
        return medyanlar[alt] + (medyanlar[ust] - medyanlar[alt]) * (i - alt)

    return [round(_y(0.025), 3), round(_y(0.975), 3)]


def _skor_serisi(
    yol: Path, *, dedektor: Any, poz: Any, ornek_fps: float, imgsz: int
) -> list[tuple[float, float]]:
    """Klibi boru hattından geçirir, `(zaman, tırmanma_skoru)` serisi döndürür.

    ⚠ `evaluate_rwf.py · _klip_skorla` ile AYNI boru hattı, tek fark:
    orası azamiyi tutuyor, burası SERİYİ. İki betiğin aynı sonucu
    üretmesi gerekiyor (K5 ile K8 aynı modülü ölçüyor); ön işleme ya
    da örnekleme farkı ikisini kıyaslanamaz kılardı.

    ⚠ Kare başına AZAMİ iz skoru alınıyor: kavga iki kişilik bir olay
    ve bir karede birinin skoru yüksekse o kare risklidir.
    """
    import cv2

    from sentinel.analytics.aggression import TirmanmaSkorlayici
    from sentinel.analytics.features import pair
    from sentinel.analytics.features import skeleton as sk
    from sentinel.analytics.features.person import cikar
    from sentinel.analytics.features.window import Ornek, PencereDeposu
    from sentinel.core.preprocess import letterbox
    from sentinel.inference.tracker.botsort import BotSortTracker

    cap = cv2.VideoCapture(str(yol))
    kaynak_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    adim = max(1, round(kaynak_fps / ornek_fps))

    takipci = BotSortTracker(frame_rate=int(ornek_fps))
    depo = PencereDeposu()
    skorlayici = TirmanmaSkorlayici()
    seri: list[tuple[float, float]] = []

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

        azami = 0.0
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
            kisiler = [cikar(depo.al(kamera, t.track_id)) for t in izler]  # type: ignore[arg-type]
            ciftler = pair.kamera_ciftleri(depo.kamera_pencereleri(kamera))
            for sonuc in skorlayici.degerlendir(kamera, kisiler, ciftler, ts):
                azami = max(azami, sonuc.skor)
        seri.append((ts, azami))
        kare_no += 1

    cap.release()
    return seri


def _ilk_gecis(seri: list[tuple[float, float]], esik: float) -> float | None:
    """Skorun eşiği İLK geçtiği an. Hiç geçmezse None.

    ⚠ İLK geçiş, azami değil. Bir sistemin "ne zaman fark ettiği"
    sorusunun cevabı, en yüksek skoru aldığı an değil, eşiği aştığı
    andır — alarm o an çalar.
    """
    for ts, skor in seri:
        if skor >= esik:
            return ts
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="K8 — erken uyarı avansı")
    ap.add_argument("--normal", type=int, default=30,
                    help="yanlış alarm payı için kaç normal klip")
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    if not ETIKET.is_file():
        print(
            f"❌ Yer gerçeği yok: {ETIKET}\n"
            "   Önce elle etiketleme: uv run python scripts/etiketle_k8.py\n"
            "\n"
            "   ⚠ Etiket olmadan 'avans' hesaplanamaz. RWF etiketi klip\n"
            "     seviyesinde ('kavga var') ve kavganın kaçıncı saniyede\n"
            "     başladığını söylemiyor — K8 tam olarak o bilgiyi soruyor.",
            file=sys.stderr,
        )
        return 1

    etiket_verisi = json.loads(ETIKET.read_text(encoding="utf-8"))
    etiketler: dict[str, Any] = etiket_verisi.get("etiketler", {})
    if not etiketler:
        print("❌ Etiket dosyası boş.", file=sys.stderr)
        return 1

    from sentinel.inference.detector.yolo import UltralyticsDetector
    from sentinel.inference.pose.yolo import YoloPoseEstimator

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "models" / "yolo26s.pt",
        imgsz=args.imgsz, half=True,
    )
    poz = YoloPoseEstimator(PROJECT_ROOT / "models" / "yolo26s-pose.pt")
    dedektor.warmup(1)
    poz.warmup(8)

    t0 = time.time()

    # ─── Kavga klipleri: skor serisi + avans ───
    print(f"{len(etiketler)} etiketli kavga klibi skorlanıyor…")
    kavga_serileri: dict[str, list[tuple[float, float]]] = {}
    for i, ad in enumerate(sorted(etiketler), 1):
        yol = RWF / "fight" / ad
        if not yol.is_file():
            print(f"\n  ⚠ {ad} bulunamadı, atlanıyor")
            continue
        kavga_serileri[ad] = _skor_serisi(
            yol, dedektor=dedektor, poz=poz, ornek_fps=args.fps, imgsz=args.imgsz
        )
        print(f"\r  {i}/{len(etiketler)} {ad}", end="", flush=True)
    print()

    # ─── Normal klipler: yanlış alarm payı ───
    normaller = sorted((RWF / "nonfight").glob("*.avi"))
    random.Random(TOHUM).shuffle(  # noqa: S311 — kripto değil, tekrarlanabilir sıra
        normaller)
    normaller = normaller[: args.normal]
    print(f"{len(normaller)} normal klip skorlanıyor (yanlış alarm payı)…")
    normal_serileri: list[list[tuple[float, float]]] = []
    for i, yol in enumerate(normaller, 1):
        normal_serileri.append(
            _skor_serisi(yol, dedektor=dedektor, poz=poz,
                         ornek_fps=args.fps, imgsz=args.imgsz)
        )
        print(f"\r  {i}/{len(normaller)}", end="", flush=True)
    print()

    # ─── Her eşik için avans ve yanlış alarm ───
    sonuclar: list[dict[str, Any]] = []
    for esik in ESIKLER:
        avanslar: list[float] = []
        kacirilan = 0
        gec_kalan = 0
        for ad, seri in kavga_serileri.items():
            olay_ani = float(etiketler[ad]["baslangic_s"])
            gecis = _ilk_gecis(seri, esik)
            if gecis is None:
                # ⚠ KAÇIRMA AVANSA DÂHİL EDİLMİYOR ama SAYILIYOR.
                # Kaçırılan klipleri hesaptan atıp yalnızca yakalananların
                # avansını raporlamak, sayıyı sistematik olarak
                # güzelleştirir: sistem zor klipleri kaçırır, kolayları
                # erken yakalar. Kaçırma oranı avansın YANINDA
                # raporlanmadan avans okunamaz.
                kacirilan += 1
                continue
            avans = olay_ani - gecis
            avanslar.append(avans)
            if avans < 0:
                gec_kalan += 1

        yanlis_alarm = sum(
            1 for seri in normal_serileri if _ilk_gecis(seri, esik) is not None
        )
        sonuclar.append({
            "esik": esik,
            "yakalanan": len(avanslar),
            "kacirilan": kacirilan,
            "gec_kalan": gec_kalan,
            "avans_medyan_s": round(statistics.median(avanslar), 3) if avanslar else None,
            "avans_ort_s": round(statistics.fmean(avanslar), 3) if avanslar else None,
            "avans_p25_s": (
                round(sorted(avanslar)[len(avanslar) // 4], 3) if avanslar else None
            ),
            "yanlis_alarm_klip": yanlis_alarm,
            "yanlis_alarm_orani": (
                round(yanlis_alarm / len(normal_serileri), 3) if normal_serileri else None
            ),
            # ⭐⭐ MEDYAN AVANSIN GÜVEN ARALIĞI
            #
            # ⚠ NEDEN GEREKLİ: K8 "❌ tutmuyor" diye raporlanıyor. Ama
            # bu sonucun KESİN mi yoksa örneklem gürültüsü mü olduğu
            # bilinmiyordu. Az sayıda klip üzerinden hesaplanmış bir
            # medyan, birkaç klip değişseydi başka çıkabilirdi.
            #
            # Bir kriterin TUTMADIĞINI iddia etmek de bir iddiadır ve
            # belirsizliği raporlanmalıdır — "tutuyor" iddiası kadar.
            # Aralık 2.0'ı içeriyorsa "tutmuyor" değil "kararsız"
            # demek gerekir.
            "avans_medyan_ga": _bootstrap_medyan(avanslar),
        })

    sure = time.time() - t0

    # ─── Rapor ───
    print(f"\n{len(kavga_serileri)} kavga + {len(normal_serileri)} normal klip · {sure:.0f} sn")
    print("\n⚠ AVANS TEK BAŞINA OKUNAMAZ — yanlış alarmla birlikte bakılmalı.")
    print("  Eşiği düşürmek avansı büyütür VE yanlış alarmı artırır.\n")
    print(f"{'eşik':>6} {'yakala':>7} {'kaçır':>6} {'geç':>5} "
          f"{'medyan avans':>13} {'%95 GA':>18} {'y.alarm':>9}")
    for s in sonuclar:
        med = f"{s['avans_medyan_s']:+.2f} sn" if s["avans_medyan_s"] is not None else "—"
        # ⭐ p25 yerine GÜVEN ARALIĞI gösteriliyor: p25 dağılımın bir
        # noktası, GA ise MEDYANIN ne kadar güvenilir olduğunu söylüyor.
        # "Tutmuyor" kararı medyana dayandığı için asıl gereken bu.
        ga = s.get("avans_medyan_ga")
        ga_str = f"[{ga[0]:+.2f}, {ga[1]:+.2f}]" if ga else "—"
        print(
            f"{s['esik']:>6.2f} {s['yakalanan']:>7} {s['kacirilan']:>6} "
            f"{s['gec_kalan']:>5} {med:>13} {ga_str:>18} "
            f"{s['yanlis_alarm_orani']:>8.0%}"
        )

    # ⚠ "K8 TUTUYOR" demek için TEK BİR eşikte ≥2 sn yetmiyor: o eşikte
    # yanlış alarm oranı da kabul edilebilir olmalı. Kabul sınırı
    # burada %30 seçildi ve KEYFİ olduğu yazılıyor — K7'nin
    # kamera-saat tabanlı ölçütü klip tabanlı bir sete doğrudan
    # çevrilemiyor. Rapor bu sınırı açıkça tartışacak.
    yanlis_alarm_siniri = 0.30
    uygun = [
        s for s in sonuclar
        if s["avans_medyan_s"] is not None
        and s["avans_medyan_s"] >= 2.0
        and (s["yanlis_alarm_orani"] or 1.0) <= yanlis_alarm_siniri
    ]
    print(f"\nK8 HEDEFİ: medyan avans ≥ 2.0 sn (yanlış alarm ≤ %{yanlis_alarm_siniri:.0%} ile)")
    if uygun:
        en_iyi = max(uygun, key=lambda s: s["avans_medyan_s"])
        print(f"  ✅ TUTUYOR — eşik {en_iyi['esik']:.2f}'te medyan avans "
              f"{en_iyi['avans_medyan_s']:+.2f} sn, yanlış alarm "
              f"%{en_iyi['yanlis_alarm_orani']:.0%}")
    else:
        print("  ❌ TUTMUYOR — hiçbir eşikte 'yeterli avans + kabul edilebilir")
        print("     yanlış alarm' birlikte sağlanmıyor. Bu bir başarısızlık")
        print("     değil bir BULGU: K5 (F1 = 0.712) zaten skorun kendi")
        print("     sınırını gösteriyordu; K8 aynı sınırın zaman eksenindeki")
        print("     karşılığı. Eğitilmiş bir model bu tabanı yükseltmeli.")

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "kriter": "K8",
        "hedef_avans_s": 2.0,
        "yanlis_alarm_siniri": yanlis_alarm_siniri,
        "yanlis_alarm_siniri_gerekcesi": (
            "keyfi; K7'nin kamera-saat ölçütü klip tabanlı bir sete "
            "doğrudan çevrilemiyor — raporda tartışılacak"
        ),
        "veri_seti": "RWF-2000 val",
        "etiket_dosyasi": str(ETIKET.relative_to(PROJECT_ROOT)),
        "etiket_yontemi": etiket_verisi.get("yontem"),
        "etiket_bilinen_sinir": etiket_verisi.get("bilinen_sinir"),
        "kavga_klip": len(kavga_serileri),
        "normal_klip": len(normal_serileri),
        "ornekleme_fps": args.fps,
        "sure_s": round(sure, 1),
        "esik_tablosu": sonuclar,
        # ⚠ HAM SERİLER DE YAZILIYOR: avans hesabı bir yorum, seri veri.
        # Eşik değiştiğinde yeniden koşmaya gerek kalmıyor ve rapor için
        # skor-zaman grafiği buradan çizilebiliyor.
        "seriler": {
            ad: {
                "olay_ani_s": float(etiketler[ad]["baslangic_s"]),
                "skorlar": [[round(t, 3), round(s, 4)] for t, s in seri],
            }
            for ad, seri in kavga_serileri.items()
        },
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"k8_{datetime.now():%Y%m%d-%H%M%S}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
