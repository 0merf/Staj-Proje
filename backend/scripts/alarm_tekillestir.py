"""Alarmları DÖNGÜDEKİ KONUMA göre tekilleştirip kesinliği yeniden hesaplar.

⚠ NEDEN GEREKLİ (P-77 / P-79)
Kaynak videolar sonsuz döngüde. cam-16'nın videosu 5 saniye: içindeki
TEK düşme olayı saatte 720 kez yeniden alarm üretiyor. Ham alarm
sayısı bu yüzden sistemin davranışını değil, test videolarının uzunluk
dağılımını ölçüyor.

Tekilleştirme: (kamera, tür, döngüdeki konum) üçlüsü. Konum
`video_pts % video_süresi` ile bulunuyor; birbirine `TOLERANS`
saniyeden yakın olanlar AYNI olay sayılıyor.
"""
import csv
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CSV = r"D:/Staj Proje/data/_tmp/alarm_klipleri/etiket_sablonu.csv"
SURE = r"D:/Staj Proje/benchmarks/kamera_video_sureleri.json"
TOLERANS = 6.0  # klip penceresi ±3 sn → 6 sn içindekiler aynı olay

sureler = json.load(open(SURE, encoding="utf-8"))


def sure_al(kamera: str) -> float | None:
    v = sureler.get(kamera)
    if v is None:
        return None
    if isinstance(v, dict):
        for k in ("sure_sn", "sure_s", "sure", "duration", "saniye"):
            if k in v:
                return float(v[k])
        return None
    return float(v)


with open(CSV, encoding="utf-8") as f:
    satirlar = [s for s in csv.DictReader(f) if (s.get("dogru") or "").strip() != ""]

# (kamera, tur) -> [(konum, dogru)]
gruplar: dict[tuple[str, str], list[tuple[float, int]]] = {}
sure_yok = set()
for s in satirlar:
    kam, tur = s["kamera"], s["tur"]
    sure = sure_al(kam)
    pts = float(s["video_pts"])
    if sure and sure > 0:
        konum = pts % sure
    else:
        sure_yok.add(kam)
        konum = pts  # süre bilinmiyorsa tekilleştirme yapılamaz
    gruplar.setdefault((kam, tur), []).append((konum, int(s["dogru"])))

bagimsiz: list[tuple[str, str, float, int]] = []
for (kam, tur), kayitlar in sorted(gruplar.items()):
    for konum, dogru in sorted(kayitlar):
        # Aynı kamera+tür içinde TOLERANS'tan yakın bir olay var mı?
        # ⚠ Döngüsel yakınlık: 0 ile süre-1 saniyeleri de komşudur.
        sure = sure_al(kam) or 0.0
        yeni = True
        for _k, _t, k2, _d in bagimsiz:
            if _k != kam or _t != tur:
                continue
            fark = abs(konum - k2)
            if sure:
                fark = min(fark, sure - fark)
            if fark <= TOLERANS:
                yeni = False
                break
        if yeni:
            bagimsiz.append((kam, tur, konum, dogru))

ham_d = sum(1 for s in satirlar if s["dogru"] == "1")
ham_n = len(satirlar)
bag_d = sum(1 for *_x, d in bagimsiz if d == 1)
bag_n = len(bagimsiz)

print("═" * 62)
print("ALARM KESİNLİĞİ — ham ve TEKİLLEŞTİRİLMİŞ")
print("═" * 62)
print(f"ham etiketli alarm      : {ham_n}  · doğru {ham_d}  → kesinlik {ham_d/ham_n:.3f}")
print(f"BAĞIMSIZ olay           : {bag_n}  · doğru {bag_d}  → kesinlik {bag_d/bag_n:.3f}")
print()
print("tür bazında (bağımsız):")
turler: dict[str, list[int]] = {}
for _k, t, _p, d in bagimsiz:
    turler.setdefault(t, []).append(d)
for t, ds in sorted(turler.items()):
    print(f"  {t:10s} n={len(ds):2d}  doğru={sum(ds):2d}  kesinlik={sum(ds)/len(ds):.2f}")
print()
print("bağımsız olayların listesi (kamera · tür · döngüdeki konum · doğru):")
for k, t, p, d in sorted(bagimsiz):
    print(f"  {k:8s} {t:10s} {p:8.2f} sn  {'✓' if d else '✗'}")
if sure_yok:
    print(f"\n⚠ süresi bilinmeyen kamera (tekilleştirilemedi): {sorted(sure_yok)}")

json.dump(
    {
        "ham_alarm": ham_n,
        "ham_dogru": ham_d,
        "ham_kesinlik": round(ham_d / ham_n, 4),
        "bagimsiz_olay": bag_n,
        "bagimsiz_dogru": bag_d,
        "bagimsiz_kesinlik": round(bag_d / bag_n, 4),
        "tolerans_s": TOLERANS,
        "tur_bazinda": {t: {"n": len(ds), "dogru": sum(ds)} for t, ds in turler.items()},
        "not": (
            "Kesinlik ölçüsüdür, duyarlılık DEĞİL. Kaynak videolar döngüde "
            "olduğu için ham sayı şişkindir; bağımsız olay sayısı "
            "(kamera, tür, döngüdeki konum) üçlüsüne göre tekilleştirilmiştir."
        ),
    },
    open(r"D:/Staj Proje/benchmarks/alarm_kesinlik_20260910.json", "w", encoding="utf-8"),
    ensure_ascii=False,
    indent=2,
)
print("\nyazıldı: benchmarks/alarm_kesinlik_20260910.json")
