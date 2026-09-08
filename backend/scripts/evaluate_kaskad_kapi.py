"""KADEMELİ KOŞULLU FÜZYON — hangi kapı doğru kapı? (P-53)

⭐ FİKİR KİMİN
-------------
Kullanıcının önerisi:

> *"Katmanlı bir eleme süreci olacak: önce kural tabanlılar bakacak,
> kutulara bakacak aradaki mesafe ne, temas gerçekleşti mi — o zaman
> LightGBM'e hızlıdan veririz, o ekstra bir analiz yapar. Yani çift
> katmanlı olur ve yanlış alarmları da engellemiş oluruz."*

İlk kaskad denemesi (`evaluate_kaskad.py`) bunu **tam saldırganlık
skoruyla** kapıladı ve battı: F1 0.829 → 0.411, kavgaların %73'ü
elendi. O zaman "kaskad işe yaramıyor" diye kapatılmıştı.

⚠ O sonuç doğruydu ama ÇIKARIM yanlıştı. `diagnose_kural.py` daha
sonra kapının neden bu kadar çok kavgayı elediğini gösterdi:

    RWF kavga kliplerinde bileşen ateşleme oranı
        yakinlik  92%      ⬅ canlı
        durus     84%      ⬅ canlı
        bilek     17%      ⬅ ÖLÜ
        enerji    10%      ⬅ ÖLÜ
        yaklasma   6%      ⬅ ÖLÜ

Tam skor, ağırlığının %60'ını ölü bileşenlerden alıyor. Onunla
kapılamak, kapıyı **gürültüyle** kapatmak demekti.

⭐⭐ Kaskad fikri yanlış değildi; SEÇİLEN KAPI yanlıştı.

Bu betik dört kapıyı yan yana ölçüyor:

    tam_skor     — eski deneme (tırmanma skorunun tamamı)
    yakinlik     — "iki kişi yakın mı" (kullanıcının önerisi)
    etkilesim    — max(yakinlik, yaklasma) = "yakın YA DA yaklaşıyor"
    durus        — tek başına ayırt eden bileşen

NE ÖLÇÜLÜYOR — VE NEDEN İKİ AYRI ŞEY
------------------------------------
Bir kaskadın iki gerekçesi olabilir ve BİRBİRİNDEN BAĞIMSIZDIR:

  1. HIZ    — pahalı aşama daha az çağrılır
  2. DOĞRULUK — kapı, modelin yanıldığı yerleri eler

⚠ Bu boru hattında (1) zaten ölçüldü ve GEÇERSİZ: LightGBM çıkarımı
kare başına 0.0004 ms; toplam 11.10 ms'nin %0.004'ü. Modeli kapılamak
yanlış aşamayı kapılamaktır — pahalı olan tespit + poz.

Dolayısıyla kaskadın tek savunulabilir gerekçesi (2). Bu betik onu
ölçüyor: kapı, model-tek-başına'ya göre F1'i **artırıyor mu**?

⚠ AYRIK TUTULMUŞ VERİ: eşik araması `train`de, rapor `val`de.

Kullanım:
    uv run python scripts/evaluate_kaskad_kapi.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OZELLIKLER = PROJECT_ROOT / "data" / "_tmp" / "rwf_ozellikler.json"
MODEL_DOSYASI = PROJECT_ROOT / "models" / "saldirganlik_lgbm.txt"
BENCHMARKS = PROJECT_ROOT / "benchmarks"

sys.path.insert(0, str(Path(__file__).resolve().parent))

KAPILAR = ("tam_skor", "yakinlik", "etkilesim", "durus")


def _kapi_degeri(seri: list[dict[str, float]], kapi: str) -> float:
    """Klibin kapı değeri — kare değerlerinin p90'ı.

    ⚠ p90, `max` DEĞİL (P-47): tek bir bozuk kare tüm klibi geçirmesin.
    Ama medyan da değil — kapı YÜKSEK DUYARLILIKLI olmalı, olayın
    yalnızca bir kısmında görünen bir işaret klibi geçirmeye yeter.
    """
    if not seri:
        return 0.0
    if kapi == "tam_skor":
        v = [k.get("skor", 0.0) for k in seri]
    elif kapi == "etkilesim":
        v = [max(k.get("yakinlik", 0.0), k.get("yaklasma", 0.0)) for k in seri]
    else:
        v = [k.get(kapi, 0.0) for k in seri]
    s = sorted(v)
    return s[min(len(s) - 1, int(len(s) * 0.90))]


def _f1_detay(
    skorlar: list[float], etiketler: list[int], esik: float,
) -> dict[str, float]:
    tp = sum(1 for s, e in zip(skorlar, etiketler, strict=True) if s >= esik and e == 1)
    fp = sum(1 for s, e in zip(skorlar, etiketler, strict=True) if s >= esik and e == 0)
    fn = sum(1 for s, e in zip(skorlar, etiketler, strict=True) if s < esik and e == 1)
    kesinlik = tp / (tp + fp) if tp + fp else 0.0
    duyarlilik = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * kesinlik * duyarlilik / (kesinlik + duyarlilik)
          if kesinlik + duyarlilik else 0.0)
    return {"f1": f1, "kesinlik": kesinlik, "duyarlilik": duyarlilik}


def _en_iyi_esik(skorlar: list[float], etiketler: list[int]) -> float:
    en_iyi = (0.0, 0.5)
    for i in range(101):
        e = i / 100
        f = _f1_detay(skorlar, etiketler, e)["f1"]
        if f > en_iyi[0]:
            en_iyi = (f, e)
    return en_iyi[1]


def main() -> int:
    ap = argparse.ArgumentParser(description="Kaskad kapı karşılaştırması")
    ap.parse_args()

    if not OZELLIKLER.is_file() or not MODEL_DOSYASI.is_file():
        print("❌ Özellik dosyası ya da model yok.", file=sys.stderr)
        return 1

    import lightgbm as lgb
    import numpy as np

    veri = json.loads(OZELLIKLER.read_text(encoding="utf-8"))
    train, val = veri["train"], veri["val"]
    booster = lgb.Booster(model_file=str(MODEL_DOSYASI))

    kayitlar = sorted(BENCHMARKS.glob("saldirganlik_model_*.json"))
    sutunlar = json.loads(kayitlar[-1].read_text(encoding="utf-8"))["ozellikler"]

    def _hazirla(bolum: list[dict[str, Any]]) -> dict[str, Any]:
        satirlar = [k for k in bolum if k.get("seri")]
        x = np.array([[k.get(c, float("nan")) for c in sutunlar] for k in satirlar])
        return {
            "etiket": [int(k["etiket"]) for k in satirlar],
            "model": [float(v) for v in booster.predict(x)],
            "kapi": {
                kapi: [_kapi_degeri(k["seri"], kapi) for k in satirlar]
                for kapi in KAPILAR
            },
        }

    tr, va = _hazirla(train), _hazirla(val)
    print(f"train {len(tr['etiket'])} · val {len(va['etiket'])} klip\n")

    # ─── Model tek başına (referans) ───
    m_esik = _en_iyi_esik(tr["model"], tr["etiket"])
    m_val = _f1_detay(va["model"], va["etiket"], m_esik)
    print("═══ REFERANS: MODEL TEK BAŞINA ═══")
    print(f"  eşik {m_esik:.2f} (train'de seçildi) → val F1 {m_val['f1']:.3f} · "
          f"kesinlik {m_val['kesinlik']:.3f} · duyarlılık {m_val['duyarlilik']:.3f}\n")

    print("═══ KAPI KARŞILAŞTIRMASI (val) ═══")
    print(f"{'kapı':<12} {'eşik':>6} {'geçen%':>8} {'kavga kaybı':>12} "
          f"{'F1':>7} {'kesinlik':>9} {'duyarlılık':>11}")
    sonuc: dict[str, Any] = {}
    for kapi in KAPILAR:
        # Kapı eşiği train'de aranıyor: kaskadın F1'ini en iyileyen eşik.
        en_iyi = (0.0, 0.0)
        for i in range(101):
            ke = i / 100
            kaskad_tr = [
                m if k >= ke else 0.0
                for m, k in zip(tr["model"], tr["kapi"][kapi], strict=True)
            ]
            f = _f1_detay(kaskad_tr, tr["etiket"], m_esik)["f1"]
            if f > en_iyi[0]:
                en_iyi = (f, ke)
        ke = en_iyi[1]

        kapi_v = va["kapi"][kapi]
        gecen = sum(1 for k in kapi_v if k >= ke) / len(kapi_v)
        # ⭐ KAPININ ASIL RİSKİ: kaç GERÇEK kavga daha modele varmadan elendi
        kavga_toplam = sum(va["etiket"])
        kavga_gecen = sum(
            1 for k, e in zip(kapi_v, va["etiket"], strict=True) if k >= ke and e == 1
        )
        kayip = 1 - (kavga_gecen / kavga_toplam if kavga_toplam else 1.0)

        kaskad = [
            m if k >= ke else 0.0
            for m, k in zip(va["model"], kapi_v, strict=True)
        ]
        d = _f1_detay(kaskad, va["etiket"], m_esik)
        print(f"{kapi:<12} {ke:>6.2f} {gecen:>7.0%} {kayip:>11.0%} "
              f"{d['f1']:>7.3f} {d['kesinlik']:>9.3f} {d['duyarlilik']:>11.3f}")
        sonuc[kapi] = {"esik": ke, "gecen_oran": round(gecen, 4),
                       "kavga_kaybi": round(kayip, 4), **{
                           k: round(v, 4) for k, v in d.items()}}

    print(f"\n{'model (kapısız)':<12} {'—':>6} {'100%':>8} {'0%':>12} "
          f"{m_val['f1']:>7.3f} {m_val['kesinlik']:>9.3f} "
          f"{m_val['duyarlilik']:>11.3f}")

    # ⭐ TAKAS EĞRİSİ — "en iyi eşik 0.00" tek başına az şey söylüyor.
    # Kapı sıkıldıkça ne oluyor, görülmeli: kaybedilen kavga ⟷ kazanılan
    # kesinlik. Eğri düz düşüyorsa kapının kazandıracağı bir bölge yok.
    print("\n═══ TAKAS EĞRİSİ — kapı sıkıldıkça (val) ═══")
    egri: dict[str, list[dict[str, float]]] = {}
    for kapi in ("yakinlik", "etkilesim"):
        print(f"\n  {kapi}:")
        print(f"  {'eşik':>6} {'geçen%':>8} {'kavga kaybı':>12} {'F1':>7} "
              f"{'kesinlik':>9} {'duyarlılık':>11}")
        kapi_v = va["kapi"][kapi]
        kavga_toplam = sum(va["etiket"])
        satirlar = []
        for ke in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6):
            gecen = sum(1 for k in kapi_v if k >= ke) / len(kapi_v)
            kg = sum(1 for k, e in zip(kapi_v, va["etiket"], strict=True)
                     if k >= ke and e == 1)
            kayip = 1 - (kg / kavga_toplam if kavga_toplam else 1.0)
            kask = [m if k >= ke else 0.0
                    for m, k in zip(va["model"], kapi_v, strict=True)]
            d = _f1_detay(kask, va["etiket"], m_esik)
            print(f"  {ke:>6.2f} {gecen:>7.0%} {kayip:>11.0%} {d['f1']:>7.3f} "
                  f"{d['kesinlik']:>9.3f} {d['duyarlilik']:>11.3f}")
            satirlar.append({"esik": ke, "gecen": round(gecen, 4),
                             "kavga_kaybi": round(kayip, 4),
                             **{k: round(v, 4) for k, v in d.items()}})
        egri[kapi] = satirlar

    en_iyi_kapi = max(KAPILAR, key=lambda k: sonuc[k]["f1"])
    kazanc = sonuc[en_iyi_kapi]["f1"] - m_val["f1"]

    print("\n═══ KARAR ═══")
    if kazanc > 0.01:
        print(f"⭐ KASKAD KAZANDIRIYOR: '{en_iyi_kapi}' kapısı F1'i "
              f"{m_val['f1']:.3f} → {sonuc[en_iyi_kapi]['f1']:.3f} "
              f"({kazanc:+.3f}) çıkarıyor.")
        print(f"   Kapı, kliplerin %{sonuc[en_iyi_kapi]['gecen_oran'] * 100:.0f}'ini "
              f"geçiriyor ve kavgaların "
              f"%{sonuc[en_iyi_kapi]['kavga_kaybi'] * 100:.0f}'ini kaybediyor.")
    else:
        print(f"❌ KASKAD KAZANDIRMIYOR. En iyi kapı ('{en_iyi_kapi}') "
              f"F1'i {kazanc:+.3f} değiştiriyor.")
        print("   ⚠ Hız gerekçesi de yok: LightGBM 11.10 ms'lik boru hattının")
        print("   0.0004 ms'si (%0.004). Kapı yanlış aşamayı kapılıyor —")
        print("   pahalı olan tespit + poz ve onlar kapının ÖNCESİNDE koşuyor.")
        print("\n   ⭐ Ama bu 'kaskad kötü bir fikir' demek DEĞİL: kapı ancak")
        print("   pahalı aşamanın ÖNÜNE konabilirse tasarruf eder. Bizim")
        print("   mimaride o yer KADEME 0 (hareket filtresi) ve orada")
        print("   zaten var — karelerin %70'ini eliyor.")

    BENCHMARKS.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = BENCHMARKS / f"kaskad_kapi_{damga}.json"
    hedef.write_text(json.dumps({
        "olculdu": datetime.now(UTC).isoformat(),
        "yontem": "kapı eşiği train'de arandı, rapor val'de",
        "model_tek_basina": {"esik": m_esik, **{k: round(v, 4)
                                                for k, v in m_val.items()}},
        "kapilar": sonuc,
        "takas_egrisi": egri,
        "en_iyi_kapi": en_iyi_kapi,
        "f1_kazanci": round(kazanc, 4),
        "hiz_gerekcesi_gecerli": False,
        "hiz_notu": "LightGBM 0.0004 ms / 11.10 ms kare = %0.004",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
