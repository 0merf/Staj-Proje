"""K7 ölçümü — yanlış alarm oranı ve anomali yakalama başarısı.

Neden bu betik
--------------
K7 kriteri: **kamera-saat başına ≤3 yanlış alarm** (PLAN §1.4).
Şimdiye kadar bu sayıyı elle hesaplıyorduk ve "yanlış" olup olmadığını
gözle değerlendiriyorduk. Artık gerekmiyor.

⚠ KONTROLLÜ DENEY — çiftlikteki iki kamera bunun için var
    cam-18  Avenue NORMAL   → burada çıkan HER alarm YANLIŞTIR
    cam-19  Avenue ANOMALİ  → 39 segmentlik kare seviyeli yer gerçeği

İkisi aynı sahne, aynı kamera açısı. Tek başına "anomali kamerasında
alarm çıktı" bir şey kanıtlamaz — sistem her şeye alarm veriyor olabilir.
Aynı sahnenin normal hâlinde SESSİZ kalması asıl kanıttır.

Ne ölçüyor
----------
1. **Yanlış alarm oranı** (kamera-saat başına) — hem cam-18'de hem
   tüm çiftlikte
2. **Yakalama (recall)** — cam-19'daki yer gerçeği segmentlerinin kaçı
   en az bir alarmla örtüşüyor
3. **Kesinlik (precision)** — cam-19'daki alarmların kaçı gerçek bir
   segmentle örtüşüyor
4. **Tür bazında döküm** — hangi kural ne kadar gürültü üretiyor

⚠ EŞLEŞTİRME TOLERANSI
Alarm, bir olayın TAM ortasında çıkmak zorunda değil: analiz 3 saniyelik
pencereyle çalışıyor ve olay bittikten kısa süre sonra da tetiklenebilir.
Bu yüzden ±TOLERANS_S saniyelik pay veriliyor. Pay olmadan gerçek
yakalamalar "kaçırılmış" sayılırdı.

Kullanım
--------
    uv run python scripts/benchmark_k7.py --duration 300
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

for _akis in (sys.stdout, sys.stderr):
    if hasattr(_akis, "reconfigure"):
        _akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from sentinel.bus.streams import connect  # noqa: E402

EVENT_STREAM = "analytics.events"

# Alarmın yer gerçeği segmentiyle örtüşmüş sayılması için izin verilen
# zaman payı.
#
# ⚠ İLK DEĞER 4.0 SANİYEYDİ VE ÖLÇÜMÜ ANLAMSIZLAŞTIRIYORDU
# Avenue segmentleri kısa: ortalama 1.92 saniye. ±4 sn pay verince
# toleranslı pencereler birleşiyor ve zaman çizgisinin **%63.6'sı**
# "anomali" sayılıyor. O koşulda rastgele atılan bir alarm bile 0.64
# kesinlik alır — ve ilk ölçümde çıkan "precision 1.00" tam da bu
# yüzden anlamsızdı.
#
# ±1 sn'de kapsam %35.9'a iniyor. Hâlâ yüksek ama ayırt edici.
# Bu yüzden rapor artık **şans seviyesini de** yazıyor: kesinlik tek
# başına değil, şansa göre NE KADAR İYİ olduğuyla birlikte okunmalı.
TOLERANS_S = 1.0

# Kontrollü deneyin iki ucu
KONTROL = "cam-18"   # normal — her alarm yanlış
DENEY = "cam-19"     # anomalili — yer gerçeği var


def yer_gercegi_yukle() -> list[tuple[float, float]]:
    """cam-19'un anomali aralıklarını okur.

    ⚠ Video DÖNGÜDE oynuyor: kaynak 345 saniye ama kamera sonsuza dek
    yayın yapıyor. Bu yüzden alarm zamanı da video içindeki konuma
    (modulo süre) çevrilmek zorunda — yoksa 400. saniyedeki alarm hiçbir
    segmentle eşleşmezdi.
    """
    yol = PROJECT_ROOT / "data" / "annotations" / f"{DENEY}.truth.json"
    if not yol.is_file():
        return []
    d = json.loads(yol.read_text(encoding="utf-8"))
    return [(float(s["start_s"]), float(s["end_s"])) for s in d["segments"]]


def video_suresi() -> float:
    yol = PROJECT_ROOT / "data" / "annotations" / f"{DENEY}.truth.json"
    if not yol.is_file():
        return 0.0
    return float(json.loads(yol.read_text(encoding="utf-8"))["total_duration_s"])


def main() -> int:
    ap = argparse.ArgumentParser(description="K7 yanlış alarm ölçümü")
    ap.add_argument("--duration", type=float, default=300.0)
    ap.add_argument("--cameras", type=int, default=20)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    gercek = yer_gercegi_yukle()
    sure = video_suresi()

    print("K7 ÖLÇÜMÜ — yanlış alarm oranı ve yakalama")
    print("=" * 66)
    print(f"  kontrol : {KONTROL} (normal — her alarm yanlış)")
    print(f"  deney   : {DENEY} ({len(gercek)} yer gerçeği segmenti, {sure:.0f} sn döngü)")
    print(f"  süre    : {args.duration:.0f} sn dinleniyor...\n")

    client = connect()
    son_id = "$"
    bitis = time.monotonic() + args.duration
    basla_wall = time.time()

    alarmlar: list[dict[str, object]] = []
    tur_sayaci: Counter[str] = Counter()
    kamera_sayaci: Counter[str] = Counter()
    tur_kamera: defaultdict[str, Counter[str]] = defaultdict(Counter)

    while time.monotonic() < bitis:
        yanit = client.xread({EVENT_STREAM: son_id}, count=64, block=1000)
        if not yanit:
            continue
        for _akis, girdiler in yanit:  # type: ignore[union-attr]
            for mid, alanlar in girdiler:
                son_id = mid
                cam = alanlar.get("cam", "")
                tur = alanlar.get("type", "")
                ts = float(alanlar.get("ts", 0.0))
                alarmlar.append({"cam": cam, "tur": tur, "ts": ts})
                tur_sayaci[tur] += 1
                kamera_sayaci[cam] += 1
                tur_kamera[tur][cam] += 1

    client.close()
    gecen_saat = (time.time() - basla_wall) / 3600.0
    if gecen_saat <= 0:
        print("HATA: süre sıfır", file=sys.stderr)
        return 1

    # ── 1. Genel yanlış alarm oranı ──
    kamera_saat = gecen_saat * args.cameras
    genel_oran = len(alarmlar) / kamera_saat if kamera_saat else 0.0

    # ── 2. Kontrol kamerası: her alarm YANLIŞ ──
    kontrol_alarm = kamera_sayaci.get(KONTROL, 0)
    kontrol_oran = kontrol_alarm / gecen_saat if gecen_saat else 0.0

    # ── 3. Deney kamerası: yakalama ve kesinlik ──
    deney_alarmlar = [a for a in alarmlar if a["cam"] == DENEY]
    yakalanan = 0
    isabetli_alarm = 0
    if gercek and sure > 0:
        # Alarm zamanını video içindeki konuma çevir (döngü!)
        konumlar = [float(a["ts"]) % sure for a in deney_alarmlar]
        for bas, bit in gercek:
            if any(bas - TOLERANS_S <= k <= bit + TOLERANS_S for k in konumlar):
                yakalanan += 1
        for k in konumlar:
            if any(bas - TOLERANS_S <= k <= bit + TOLERANS_S for bas, bit in gercek):
                isabetli_alarm += 1

    recall = yakalanan / len(gercek) if gercek else 0.0
    precision = isabetli_alarm / len(deney_alarmlar) if deney_alarmlar else 0.0

    # ⚠ ŞANS SEVİYESİ — kesinliğin tek başına anlamı yok
    # Toleranslı pencereler zaman çizgisinin ne kadarını kaplıyorsa,
    # rastgele atılan bir alarmın "isabet" sayılma olasılığı odur.
    # Kesinlik bunun ÜSTÜNDE değilse sistem şanstan iyi değil demektir.
    sans = 0.0
    if gercek and sure > 0:
        genis = sorted(
            (max(0.0, a - TOLERANS_S), min(sure, b + TOLERANS_S)) for a, b in gercek
        )
        birlesik: list[tuple[float, float]] = []
        for a, b in genis:
            if birlesik and a <= birlesik[-1][1]:
                birlesik[-1] = (birlesik[-1][0], max(birlesik[-1][1], b))
            else:
                birlesik.append((a, b))
        sans = sum(b - a for a, b in birlesik) / sure
    f1 = (
        2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    )

    # ── Rapor ──
    print(f"{'TÜR':<14}{'toplam':>8}{'kontrol':>9}{'deney':>8}   en çok üreten kamera")
    print("-" * 66)
    for tur, n in tur_sayaci.most_common():
        enc = tur_kamera[tur].most_common(1)
        print(
            f"{tur:<14}{n:>8}{tur_kamera[tur].get(KONTROL, 0):>9}"
            f"{tur_kamera[tur].get(DENEY, 0):>8}   "
            f"{enc[0][0] if enc else '-'} ({enc[0][1] if enc else 0})"
        )
    print("-" * 66)
    print(f"{'TOPLAM':<14}{len(alarmlar):>8}{kontrol_alarm:>9}{len(deney_alarmlar):>8}")

    print()
    print("⭐ K7 — YANLIŞ ALARM ORANI")
    print(f"   genel   : {genel_oran:6.1f} alarm/kamera-saat   (hedef ≤3)")
    print(
        f"   kontrol : {kontrol_oran:6.1f} alarm/saat  ({KONTROL}, "
        f"her biri KESİN yanlış)"
    )
    print(f"   durum   : {'✅ TUTUYOR' if genel_oran <= 3 else '❌ TUTMUYOR'}")

    print()
    print(f"⭐ ANOMALİ YAKALAMA — {DENEY} (yer gerçekli)")
    print(f"   yakalanan segment : {yakalanan}/{len(gercek)}   (recall {recall:.2f})")
    print(f"   isabetli alarm    : {isabetli_alarm}/{len(deney_alarmlar)}   (precision {precision:.2f})")
    print(f"   F1                : {f1:.2f}")
    print(f"   ŞANS SEVİYESİ     : {sans:.2f}   ← rastgele alarm bu kesinliği alır")
    if deney_alarmlar:
        kazanc = precision - sans
        print(
            f"   şansa göre kazanç : {kazanc:+.2f}   "
            f"{'anlamli' if kazanc > 0.15 else 'ZAYIF — sanstan ayirt edilemiyor'}"
        )

    print()
    print("   ⚠ Yer gerçeği yalnızca cam-19'da var; diğer 19 kameranın")
    print("     alarmları 'yanlış mı doğru mu' bilinmiyor. Genel oran bu")
    print("     yüzden ÜST SINIR: gerçek yanlış alarm oranı bundan düşük.")

    rapor = {
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "phase": "Faz 1 / Gün 16",
        "description": "K7 yanlış alarm oranı + Avenue yer gerçeğiyle yakalama",
        "duration_s": round(gecen_saat * 3600, 1),
        "kamera_sayisi": args.cameras,
        "tolerans_s": TOLERANS_S,
        "k7": {
            "genel_alarm_kamera_saat": round(genel_oran, 2),
            "kontrol_kamerasi": KONTROL,
            "kontrol_alarm_saat": round(kontrol_oran, 2),
            "hedef": 3.0,
            "tutuyor_mu": genel_oran <= 3.0,
        },
        "yakalama": {
            "deney_kamerasi": DENEY,
            "yer_gercegi_segment": len(gercek),
            "yakalanan": yakalanan,
            "recall": round(recall, 3),
            "precision": round(precision, 3),
            "f1": round(f1, 3),
            "sans_seviyesi": round(sans, 3),
            "sansa_gore_kazanc": round(precision - sans, 3),
        },
        "tur_bazinda": dict(tur_sayaci),
        "kamera_bazinda": dict(kamera_sayaci),
        "tur_kamera": {t: dict(c) for t, c in tur_kamera.items()},
    }
    cikti = (
        args.out or PROJECT_ROOT / "benchmarks" / f"k7_{datetime.now():%Y%m%d-%H%M}.json"
    ).resolve()
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nKaydedildi: {cikti.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
