"""Kural ağırlıklarını ÖLÇEREK yeniden belirler (P-52).

⭐ NEDEN
-------
`diagnose_kural.py` cam-15'te kural yolunun neden çöktüğünü gösterdi:

    bileşen    ağırlık   normal   kavga   oran   ateşleme(kavga)
    yakinlik     0.30    0.3956  0.3956   1.00        99%   ⬅ DOYMUŞ
    bilek        0.25    0.0000  0.0000    —          20%   ⬅ ÖLÜ
    yaklasma     0.20    0.0000  0.0000    —          12%   ⬅ ÖLÜ
    enerji       0.15    0.0000  0.0000    —          13%   ⬅ ÖLÜ
    durus        0.10    0.0564  0.0900   1.60        91%   ⬅ TEK AYIRT EDEN

Ayırt eden tek bileşen EN DÜŞÜK ağırlığa sahip. Ve bu tesadüf değil:
elle yazılan ağırlıklar bir **halk teorisini** kodluyordu — "kavga =
hızlı yumruk". Gerçek gözetim görüntüsündeki şiddet çoğunlukla
boğuşma, tutma, itme: **kollar yavaş, duruş bozuk.**

⭐⭐ Aynı sonucu LightGBM bağımsız olarak söyledi. Öğrenilen modelin
en etkili 10 özelliğinin 10'u da gövde/duruş:

    ham_govde_hizi_medyan            48
    ham_durus_genisligi_p75          45
    ham_govde_egimi_degisimi_medyan  26
    ham_durus_genisligi_azami        22
    ham_en_boy_orani_p75             22
    ...
    sahne_bilek_hizi_p75_medyan      20   ⬅ bilek ancak 11. sırada

Kural 0.40 ağırlığı uzuv hızına, 0.10'u duruşa veriyordu. Model tam
tersini öğrendi.

⚠ AMA BU BİR HİPOTEZ, SONUÇ DEĞİL
---------------------------------
"Model duruşa bakıyor, öyleyse kural da baksın" mantıklı görünüyor ama
ölçülmeden yazılamaz — bu projede tam olarak bu tür makul görünen
çıkarımlar defalarca çürüdü. Bu betik hipotezi sınıyor.

YÖNTEM
------
`data/_tmp/rwf_ozellikler.json` her klibin KARE SERİSİNİ saklıyor
(bileşen değerleri). Ağırlıkları değiştirip skoru yeniden hesaplamak
GPU gerektirmiyor — aynı bileşenler, farklı ağırlıklı toplam.

⚠⚠ AŞIRI UYUM KORUMASI: arama YALNIZCA `train` bölümünde yapılıyor,
sonuç YALNIZCA `val` bölümünde raporlanıyor. Aynı kümede arayıp aynı
kümede raporlamak K5'te zaten bilinen bir yanlılıktı (CLAUDE.md:
*"en_iyi_esik, F1'in hesaplandığı aynı 120 klip üzerinde aranıyor"*);
burada tekrarlanmıyor.

Kullanım:
    uv run python scripts/optimize_kural.py
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OZELLIKLER = PROJECT_ROOT / "data" / "_tmp" / "rwf_ozellikler.json"
BENCHMARKS = PROJECT_ROOT / "benchmarks"

BILESENLER = ("yakinlik", "bilek", "yaklasma", "enerji", "durus")

# Etkileşim kapısı — `aggression.py` ile AYNI formül.
# ⚠ Kopyalanmış bir sabit değil, aynı davranışın çevrim dışı ikizi.
# Ayrışırsa burada bulunan ağırlıklar canlıda başka bir skor üretir.
ETKILESIM_TABAN = 0.15


def _auc(skorlar: list[float], etiketler: list[int]) -> float:
    """ROC AUC — sıra istatistiğiyle (sklearn'e bağımlılık yok)."""
    ciftler = sorted(zip(skorlar, etiketler, strict=True))
    n_poz = sum(etiketler)
    n_neg = len(etiketler) - n_poz
    if n_poz == 0 or n_neg == 0:
        return 0.5
    # Ortalama sıra yöntemi (eşit değerler için düzeltmeli)
    siralar: list[float] = [0.0] * len(ciftler)
    i = 0
    while i < len(ciftler):
        j = i
        while j + 1 < len(ciftler) and ciftler[j + 1][0] == ciftler[i][0]:
            j += 1
        ort = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            siralar[k] = ort
        i = j + 1
    poz_sira = sum(s for s, (_v, e) in zip(siralar, ciftler, strict=True) if e == 1)
    return (poz_sira - n_poz * (n_poz + 1) / 2) / (n_poz * n_neg)


def _f1(skorlar: list[float], etiketler: list[int]) -> tuple[float, float]:
    """En iyi F1 ve onu veren eşik."""
    en_iyi = (0.0, 0.0)
    for esik in [i / 200 for i in range(201)]:
        tp = sum(1 for s, e in zip(skorlar, etiketler, strict=True) if s >= esik and e == 1)
        fp = sum(1 for s, e in zip(skorlar, etiketler, strict=True) if s >= esik and e == 0)
        fn = sum(1 for s, e in zip(skorlar, etiketler, strict=True) if s < esik and e == 1)
        if tp == 0:
            continue
        kesinlik = tp / (tp + fp)
        duyarlilik = tp / (tp + fn)
        f1 = 2 * kesinlik * duyarlilik / (kesinlik + duyarlilik)
        if f1 > en_iyi[0]:
            en_iyi = (f1, esik)
    return en_iyi


def _klip_skoru(seri: list[dict[str, float]], agirlik: dict[str, float]) -> float:
    """Bir klibin skoru: kare skorlarının p90'ı.

    ⚠ p90, `max` DEĞİL — P-47'nin dersi: `max` tek bir bozuk kareyi
    tüm klibin skoru yapar.
    """
    kare_skorlari: list[float] = []
    for k in seri:
        siddet = sum(agirlik[b] * k.get(b, 0.0) for b in BILESENLER)
        kapi = max(ETKILESIM_TABAN, k.get("yakinlik", 0.0), k.get("yaklasma", 0.0))
        kare_skorlari.append(kapi * siddet)
    if not kare_skorlari:
        return 0.0
    s = sorted(kare_skorlari)
    return s[min(len(s) - 1, int(len(s) * 0.90))]


def _degerlendir(
    bolum: list[dict[str, Any]], agirlik: dict[str, float],
) -> tuple[float, float, float]:
    skorlar, etiketler = [], []
    for klip in bolum:
        seri = klip.get("seri")
        if not seri:
            continue
        skorlar.append(_klip_skoru(seri, agirlik))
        etiketler.append(int(klip["etiket"]))
    if not skorlar:
        return 0.5, 0.0, 0.0
    auc = _auc(skorlar, etiketler)
    f1, esik = _f1(skorlar, etiketler)
    return auc, f1, esik


def main() -> int:
    ap = argparse.ArgumentParser(description="Kural ağırlığı araması")
    ap.add_argument("--adim", type=float, default=0.05,
                    help="ağırlık ızgarası adımı")
    args = ap.parse_args()

    if not OZELLIKLER.is_file():
        print(f"❌ Özellik dosyası yok: {OZELLIKLER}\n"
              "   Önce: uv run python scripts/train_aggression.py --cikar",
              file=sys.stderr)
        return 1

    veri = json.loads(OZELLIKLER.read_text(encoding="utf-8"))
    train, val = veri["train"], veri["val"]
    print(f"train {len(train)} klip · val {len(val)} klip\n")

    from sentinel.analytics.aggression import VARSAYILAN

    mevcut = {b: float(getattr(VARSAYILAN, f"a_{b}")) for b in BILESENLER}

    m_tr = _degerlendir(train, mevcut)
    m_val = _degerlendir(val, mevcut)
    print("═══ MEVCUT AĞIRLIKLAR ═══")
    print("  " + " · ".join(f"{b} {mevcut[b]:.2f}" for b in BILESENLER))
    print(f"  train AUC {m_tr[0]:.3f} F1 {m_tr[1]:.3f} | "
          f"val AUC {m_val[0]:.3f} F1 {m_val[1]:.3f}\n")

    # ─── Izgara araması — YALNIZCA train üzerinde ───
    # Ağırlıklar 0.05 adımlarla, toplamı 1.0. Beş bileşen için
    # kombinasyon sayısı yönetilebilir (~10 bin).
    adim = args.adim
    n = round(1.0 / adim)
    print(f"ızgara araması (adım {adim}, toplam 1.0)…")
    en_iyi: tuple[float, dict[str, float]] = (0.0, mevcut)
    denenen = 0
    for kombin in itertools.product(range(n + 1), repeat=len(BILESENLER) - 1):
        if sum(kombin) > n:
            continue
        paylar = (*kombin, n - sum(kombin))
        agirlik = {b: p * adim for b, p in zip(BILESENLER, paylar, strict=True)}
        denenen += 1
        auc, _f, _e = _degerlendir(train, agirlik)
        if auc > en_iyi[0]:
            en_iyi = (auc, agirlik)
    print(f"  {denenen} kombinasyon denendi\n")

    a = en_iyi[1]
    o_tr = _degerlendir(train, a)
    o_val = _degerlendir(val, a)

    print("═══ ARAMANIN BULDUĞU AĞIRLIKLAR ═══")
    print("  " + " · ".join(f"{b} {a[b]:.2f}" for b in BILESENLER))
    print(f"  train AUC {o_tr[0]:.3f} F1 {o_tr[1]:.3f} | "
          f"val AUC {o_val[0]:.3f} F1 {o_val[1]:.3f}\n")

    print("═══ AYRIK TUTULMUŞ (val) KARŞILAŞTIRMASI ═══")
    print(f"{'ayar':<22} {'AUC':>7} {'F1':>7} {'eşik':>7}")
    print(f"{'mevcut (elle)':<22} {m_val[0]:>7.3f} {m_val[1]:>7.3f} {m_val[2]:>7.2f}")
    print(f"{'aranan (ölçülmüş)':<22} {o_val[0]:>7.3f} {o_val[1]:>7.3f} {o_val[2]:>7.2f}")
    fark = o_val[0] - m_val[0]
    print(f"\nfark: AUC {fark:+.3f} · F1 {o_val[1] - m_val[1]:+.3f}")

    print("\n═══ YORUM ═══")
    uzuv_eski = mevcut["bilek"] + mevcut["enerji"]
    uzuv_yeni = a["bilek"] + a["enerji"]
    print(f"uzuv hızı ağırlığı (bilek+enerji): {uzuv_eski:.2f} → {uzuv_yeni:.2f}")
    print(f"duruş ağırlığı                   : {mevcut['durus']:.2f} → {a['durus']:.2f}")
    if fark > 0.02:
        print("\n⭐ Hipotez DOĞRULANDI: ağırlıklar yanlış dağıtılmıştı.")
    elif fark > -0.02:
        print("\n⚠ Fark gürültü içinde. Ağırlıklar sorunun ANA kaynağı değil —")
        print("   ölü bölge ve doymuş yakınlık daha baskın (bkz. P-52).")
    else:
        print("\n❌ Arama daha kötü genelledi — aşırı uyum işareti.")

    BENCHMARKS.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = BENCHMARKS / f"kural_agirlik_{damga}.json"
    hedef.write_text(json.dumps({
        "olculdu": datetime.now(UTC).isoformat(),
        "yontem": "ızgara araması train'de, rapor val'de (aşırı uyum koruması)",
        "adim": adim, "denenen": denenen,
        "train_klip": len(train), "val_klip": len(val),
        "mevcut": {"agirlik": mevcut, "train": {"auc": m_tr[0], "f1": m_tr[1]},
                   "val": {"auc": m_val[0], "f1": m_val[1], "esik": m_val[2]}},
        "aranan": {"agirlik": a, "train": {"auc": o_tr[0], "f1": o_tr[1]},
                   "val": {"auc": o_val[0], "f1": o_val[1], "esik": o_val[2]}},
        "val_auc_farki": round(fark, 4),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")

    # Bilgi: ortalama bileşen değerleri — hangi bileşen hiç ateşlemiyor
    print("\n═══ RWF'de BİLEŞEN AKTİFLİĞİ (kavga klipleri) ═══")
    print(f"{'bileşen':<12} {'medyan':>9} {'ateşleme%':>11}")
    for b in BILESENLER:
        v = [k.get(b, 0.0) for klip in train + val if klip["etiket"] == 1
             for k in klip.get("seri", [])]
        if v:
            print(f"{b:<12} {statistics.median(v):>9.4f} "
                  f"{sum(1 for x in v if x > 1e-9) / len(v):>10.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
