"""KASKAD DENEYİ — ucuz kural kapısı → pahalı sınıflandırıcı.

Araştırma sorusu
----------------
Kural tabanlı bir ÖN ELEME, öğrenilmiş sınıflandırıcının önüne
konursa ne olur?

    A. Yalnız kural         (elle konmuş ağırlıklar)
    B. Yalnız LightGBM      (öğrenilmiş ağırlıklar)
    C. KASKAD: kural kapısı → geçerse LightGBM

⚠ HİPOTEZ AÇIKÇA YAZILIYOR — sonuç ne çıkarsa çıksın raporlanacak
Kaskadın ikinci aşamanın **ayırt etme gücünü artırması beklenmiyor.**
Bir kapı sınıflandırıcı değildir; yalnızca filtreler. Beklenen kazanç:

    ✅ kesinlik (precision) ↑   — bariz olmayanlar kapıda eleniyor
    ✅ hesap maliyeti ↓          — LightGBM her karede çağrılmıyor
    ❌ duyarlılık (recall) ↓      — kapı bir gerçek olayı elerse
                                   ikinci aşama onu HİÇ göremez

⭐ VE ASIL ÖLÇÜLEN ŞEY BU PROJENİN MERKEZÎ KISITI
Bu sistemin problemi doğruluk değil, **20 eşzamanlı kamerayı tek orta
seviye GPU'da gerçek zamanlı işlemek** (PLAN §1.2). Kaskadı "daha
doğru" diye değil, **"aynı doğrulukta, daha az hesapla"** diye
savunuyoruz — ve o savunmanın sayısı `lgbm_cagri_orani`.

Kaskad neden bu mimariye uyuyor
-------------------------------
Sistem zaten kademeli (PLAN §4, mimari kural 4):

    KADEME 0  hareket filtresi   → karelerin %85'i burada eleniyor
    KADEME 1  tespit + takip
    KADEME 2  poz + yüz
    KADEME 3  (bu betik) davranış sınıflandırma

Kaskad, aynı ilkenin bir kademe aşağısı: **ucuz olan önce baksın,
pahalı olan yalnızca gerektiğinde çalışsın.**

⚠ KAPI NEYE BAKIYOR — ve neden bunlara
Saldırganlık tanımı gereği **etkileşimli** bir olay. Kapı bu tanımı
doğrudan uyguluyor:

  · yakınlık   — iki kişi birbirine yeterince yakın mı
                 (kişisel alan ihlali; uzaktaki iki kişi kavga edemez)
  · etkileşim  — karşılıklı duruş / yaklaşma var mı
  · uzuv       — bilek etkinliği normalin üstünde mi
                 (kavga uzuv hareketi olmadan olmaz)

Üçü de **iskeletten** geliyor: ten rengi, kıyafet ve görünüşten
bağımsız (PLAN §12.2 — yanlılık azaltma gerekçesi).

⚠ KAPI "VEYA" DEĞİL "VE" — gerekçesi
Herhangi biri yeterli olsaydı kapı neredeyse hiç kapanmazdı: kalabalık
bir sahnede yakınlık daima yüksek. Kavga ÜÇÜNÜN AYNI ANDA olmasıdır.

Literatür
---------
Kaskad mimarisi bu alanda yeni değil ve öyle olduğu iddia edilmiyor:
  · Viola & Jones (2001) — kaskad sınıflandırıcının kanonik örneği
  · İskelet tabanlı çok kişili aksiyon tanıma (Eng. Appl. AI, 2025)
  · İki aşamalı poz tabanlı şiddet tespiti (arXiv:2308.16325)
  · Hesap kısıtlı senaryolarda kaskad (Electronics 15(6):1227)

Bizim katkımız kaskadın kendisi değil, **20 kameralık gerçek zamanlı
bir kısıt altında ölçülmüş ablasyonu** ve kapının açıklanabilir
iskelet geometrisiyle kurulması.

Kullanım
--------
    uv run python scripts/evaluate_kaskad.py
    uv run python scripts/evaluate_kaskad.py --izgara   # eşik taraması
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"
OZELLIK_DOSYASI = PROJECT_ROOT / "data" / "_tmp" / "rwf_ozellikler.json"
MODEL_DOSYASI = PROJECT_ROOT / "backend" / "models" / "saldirganlik_lgbm.txt"

TOHUM = 42

# ─── KURAL KAPISI EŞİKLERİ ───
#
# ⚠ Bu değerler `benchmark_features.py` ile ölçülen CANLI dağılımdan
# türetildi, keyfi seçilmedi. 20 kamera / 200 sn / 40 bin özellik
# vektöründe normal davranışın p90'ı:
#
#     bilek_hizi_azami  p90 = 1.80   (doyum 3.0)
#     yakinlik          p90 ≈ 0.35
#
# Kapı, normal davranışın ÜSTÜNDE bir yerde durmalı ama gerçek
# olayları elememeli. Aşağıdaki değerler o aralığın alt ucunda —
# yani kapı BOL tutuluyor. Gerekçe: bir kapının en kötü hatası
# gerçek olayı elemektir; hesap tasarrufu bunun karşılığında feda
# edilebilir, doğru pozitif edilemez.
KAPI_YAKINLIK = 0.15
KAPI_ETKILESIM = 0.15
KAPI_UZUV = 0.15


def _auc(poz: list[float], neg: list[float]) -> float:
    """Mann-Whitney U ile ROC-AUC. Eşitlikler 0.5 sayılıyor."""
    if not poz or not neg:
        return float("nan")
    n = sorted(neg)
    toplam = 0.0
    for p in poz:
        k = bisect.bisect_left(n, p)
        e = bisect.bisect_right(n, p) - k
        toplam += k + 0.5 * e
    return toplam / (len(poz) * len(neg))


def _en_iyi_f1(poz: list[float], neg: list[float]) -> tuple[float, float, float, float]:
    """Eşik taraması ile en iyi F1.

    ⚠ EŞİK TEST KÜMESİNDE ARANIYOR — bilinen yanlılık, ADR-0007 ile
    AYNI yöntem. Kasten aynı: üç yapılandırma (kural / LightGBM /
    kaskad) aynı optimistik yöntemle ölçülüyor ki KARŞILAŞTIRMA adil
    olsun. Mutlak sayılar hepsinde şişkin; aralarındaki fark anlamlı.
    """
    en_iyi = (0.0, 0.0, 0.0, 0.0)
    for i in range(1, 100):
        esik = i / 100
        tp = sum(1 for p in poz if p >= esik)
        fp = sum(1 for p in neg if p >= esik)
        fn = len(poz) - tp
        if tp == 0:
            continue
        kesinlik = tp / (tp + fp)
        duyarlilik = tp / (tp + fn)
        f1 = 2 * kesinlik * duyarlilik / (kesinlik + duyarlilik)
        if f1 > en_iyi[1]:
            en_iyi = (esik, f1, duyarlilik, kesinlik)
    return en_iyi


def _kapi_gecti_mi(kare: dict[str, float]) -> bool:
    """Bir KARE kural kapısını geçiyor mu.

    ⚠ "VE" mantığı: üçü birden. Gerekçe modül başlığında.
    """
    return (
        kare.get("yakinlik", 0.0) >= KAPI_YAKINLIK
        and max(kare.get("etkilesim", 0.0), kare.get("yaklasma", 0.0)) >= KAPI_ETKILESIM
        and kare.get("bilek", 0.0) >= KAPI_UZUV
    )


def _kapi_istatistigi(klip: dict[str, Any]) -> tuple[int, int]:
    """Klipte kaç kare kapıyı geçti / toplam kare."""
    seri = klip.get("seri") or []
    return sum(1 for k in seri if _kapi_gecti_mi(k)), len(seri)


def main() -> int:
    ap = argparse.ArgumentParser(description="Kaskad ablasyonu")
    ap.add_argument("--izgara", action="store_true", help="kapı eşiği taraması")
    args = ap.parse_args()

    import numpy as np

    if not OZELLIK_DOSYASI.is_file():
        print(f"❌ Özellik dosyası yok: {OZELLIK_DOSYASI}\n"
              "   Önce: uv run python scripts/train_aggression.py --cikar",
              file=sys.stderr)
        return 1
    if not MODEL_DOSYASI.is_file():
        print(f"❌ Model yok: {MODEL_DOSYASI}\n"
              "   Önce: uv run python scripts/train_aggression.py --egit",
              file=sys.stderr)
        return 1

    veri = json.loads(OZELLIK_DOSYASI.read_text(encoding="utf-8"))
    val = veri["val"]
    if not val or "seri" not in val[0]:
        print("❌ Kare serisi yok. `--cikar` adımını GÜNCEL betikle yeniden koşun.",
              file=sys.stderr)
        return 1

    import lightgbm as lgb

    booster = lgb.Booster(model_file=str(MODEL_DOSYASI))

    # ⚠ SÜTUN SIRASI MODELDEN DEĞİL, ÖLÇÜM JSON'UNDAN OKUNUYOR
    #
    # Model bir numpy dizisiyle eğitildiği için LightGBM sütunlara
    # kendi adlarını verdi: `Column_0`, `Column_1`, … Yani modelin
    # kendisi hangi sütunun "durus_azami" olduğunu BİLMİYOR.
    #
    # ⚠ Bu sessiz bir felaket kaynağı: sütunları alfabetik sırayla
    # yeniden üretsek ve bir gün yeni bir özellik eklensek, sıra
    # kayar ve model YANLIŞ sütunları okur — hata vermeden, sadece
    # yanlış skor üreterek. (Aynı sınıf tuzak: `analytics/ifade.py`
    # etiket kümesi, `train_aggression.py` BILESENLER listesi.)
    #
    # Eğitim betiği sırayı JSON'a yazıyor; tek doğru kaynak orası.
    kayitlar = sorted(BENCHMARKS.glob("saldirganlik_model_*.json"))
    if not kayitlar:
        print("❌ Model ölçüm JSON'u yok — `--egit` adımını koşun.", file=sys.stderr)
        return 1
    sutunlar = json.loads(kayitlar[-1].read_text(encoding="utf-8"))["ozellikler"]
    if booster.num_feature() != len(sutunlar):
        print(f"❌ Sütun sayısı uyuşmuyor: model {booster.num_feature()}, "
              f"JSON {len(sutunlar)}. Model ve ölçüm dosyası AYNI koşudan olmalı.",
              file=sys.stderr)
        return 1

    def _matris(satirlar: list[dict[str, Any]]) -> Any:
        # ⚠ EKSİK DEĞER `NaN` — `train_aggression.py` ile AYNI kural.
        # Ham özellikler `None` ise klip sözlüğüne hiç yazılmıyor;
        # sıfır koymak modele "ölçtüm ve sıfırdı" demek olurdu.
        # Eğitimde NaN kullanılıp çıkarımda sıfır kullanmak, modeli
        # eğitildiğinden BAŞKA bir dağılımla beslemek demektir.
        return np.array([
            [float(s[c]) if c in s else float("nan") for c in sutunlar]
            for s in satirlar
        ])

    y = np.array([int(s["etiket"]) for s in val])
    lgbm_olasilik = booster.predict(_matris(val))
    # Kural tabanlı skor: klip içindeki azami tırmanma skoru
    # (`evaluate_rwf.py` · K5 ile AYNI toplulaştırma).
    kural_skor = np.array([float(s["skor_azami"]) for s in val])

    # ─── Kapı istatistiği ───
    gecen_kare = 0
    toplam_kare = 0
    kapi_acildi: list[bool] = []
    for s in val:
        g, t = _kapi_istatistigi(s)
        gecen_kare += g
        toplam_kare += t
        # Klip seviyesinde karar: kapı EN AZ BİR karede açıldıysa
        # ikinci aşama o klip için çağrılmış sayılıyor.
        kapi_acildi.append(g > 0)

    # ─── C: KASKAD skoru ───
    # ⚠ Kapı kapalıysa skor 0.0 — yani "olay yok" deniyor.
    # Bu, kaskadın TANIMI: ikinci aşama çağrılmadıysa çıktı da yok.
    kaskad_skor = np.array([
        float(p) if acik else 0.0
        for p, acik in zip(lgbm_olasilik, kapi_acildi, strict=True)
    ])

    def _olc(skor: Any, ad: str) -> dict[str, Any]:
        poz = [float(v) for v, e in zip(skor, y, strict=True) if e == 1]
        neg = [float(v) for v, e in zip(skor, y, strict=True) if e == 0]
        auc = _auc(poz, neg)
        esik, f1, duyarlilik, kesinlik = _en_iyi_f1(poz, neg)
        return {
            "ad": ad, "auc": round(auc, 4), "f1": round(f1, 4),
            "duyarlilik": round(duyarlilik, 4), "kesinlik": round(kesinlik, 4),
            "en_iyi_esik": esik,
        }

    a = _olc(kural_skor, "A · yalnız kural")
    b = _olc(lgbm_olasilik, "B · yalnız LightGBM")
    c = _olc(kaskad_skor, "C · KASKAD (kural→LGBM)")

    # ─── Kapının kaçırdığı gerçek olaylar ───
    kacan = sum(1 for acik, e in zip(kapi_acildi, y, strict=True) if not acik and e == 1)
    elenen_normal = sum(
        1 for acik, e in zip(kapi_acildi, y, strict=True) if not acik and e == 0
    )
    kavga_sayisi = int(y.sum())
    normal_sayisi = len(y) - kavga_sayisi
    kare_cagri_orani = gecen_kare / max(toplam_kare, 1)

    # ─── Rapor ───
    print(f"\ndoğrulama: {len(val)} klip ({kavga_sayisi} kavga / {normal_sayisi} normal)"
          f" · {toplam_kare} kare\n")
    print(f"{'YAPILANDIRMA':<26} {'AUC':>7} {'F1':>7} {'duyarlılık':>11} {'kesinlik':>9}")
    for m in (a, b, c):
        print(f"{m['ad']:<26} {m['auc']:>7.3f} {m['f1']:>7.3f} "
              f"{m['duyarlilik']:>11.3f} {m['kesinlik']:>9.3f}")

    print("\n⭐ HESAP MALİYETİ — kaskadın ASIL GEREKÇESİ")
    print(f"  LightGBM çağrılan kare oranı : %{kare_cagri_orani:.1%}".replace("%%", "%"))
    print(f"  yani tasarruf                : {1 / max(kare_cagri_orani, 1e-9):.2f}× daha az çağrı")

    print("\n⚠ KAPININ BEDELİ")
    print(f"  kapıda elenen KAVGA klibi   : {kacan}/{kavga_sayisi}"
          f"  ({kacan / max(kavga_sayisi, 1):.1%} kayıp)")
    print(f"  kapıda elenen NORMAL klip   : {elenen_normal}/{normal_sayisi}"
          f"  ({elenen_normal / max(normal_sayisi, 1):.1%} kazanç)")

    print("\nSONUÇ")
    if c["f1"] >= b["f1"] - 0.02 and kare_cagri_orani < 0.7:
        print("  ✅ Kaskad KARŞILIĞINI VERİYOR: doğruluk korunuyor,")
        print(f"     hesap {1 / kare_cagri_orani:.1f} kat azalıyor.")
    elif c["f1"] < b["f1"] - 0.02:
        print("  ⚠ Kapı DOĞRULUĞA ZARAR VERİYOR — gerçek olayları eliyor.")
        print("     Eşikler gevşetilmeli ya da kaskad terk edilmeli.")
    else:
        print("  ⚠ Kapı yeterince ELEMİYOR — hesap tasarrufu anlamsız,")
        print("     kaskadın karmaşıklığı karşılığını vermiyor.")

    # ─── Eşik taraması (isteğe bağlı) ───
    izgara: list[dict[str, Any]] = []
    if args.izgara:
        print(f"\n{'kapı eşiği':>11} {'çağrı %':>9} {'F1':>7} {'kaçan kavga':>12}")
        global KAPI_YAKINLIK, KAPI_ETKILESIM, KAPI_UZUV
        for e in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40):
            KAPI_YAKINLIK = KAPI_ETKILESIM = KAPI_UZUV = e
            g = t = 0
            acik: list[bool] = []
            for s in val:
                gk, tk = _kapi_istatistigi(s)
                g += gk
                t += tk
                acik.append(gk > 0)
            sk = np.array([
                float(p) if o else 0.0
                for p, o in zip(lgbm_olasilik, acik, strict=True)
            ])
            m = _olc(sk, f"kapı={e}")
            kc = sum(1 for o, lbl in zip(acik, y, strict=True) if not o and lbl == 1)
            oran = g / max(t, 1)
            print(f"{e:>11.2f} {oran:>8.1%} {m['f1']:>7.3f} {kc:>9}/{kavga_sayisi}")
            izgara.append({"esik": e, "cagri_orani": round(oran, 4),
                           "f1": m["f1"], "auc": m["auc"], "kacan_kavga": kc})
        KAPI_YAKINLIK = KAPI_ETKILESIM = KAPI_UZUV = 0.15  # varsayılana dön

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "deney": "kaskad ablasyonu (kural kapısı → LightGBM)",
        "veri_seti": "RWF-2000 val",
        "klip_sayisi": len(val),
        "kare_sayisi": toplam_kare,
        "kapi_esikleri": {
            "yakinlik": KAPI_YAKINLIK,
            "etkilesim": KAPI_ETKILESIM,
            "uzuv": KAPI_UZUV,
            "mantik": "VE (üçü birden)",
        },
        "yapilandirmalar": [a, b, c],
        "hesap": {
            "lgbm_cagrilan_kare_orani": round(kare_cagri_orani, 4),
            "tasarruf_kat": round(1 / max(kare_cagri_orani, 1e-9), 2),
        },
        "kapi_bedeli": {
            "elenen_kavga": kacan,
            "kavga_toplam": kavga_sayisi,
            "elenen_normal": elenen_normal,
            "normal_toplam": normal_sayisi,
        },
        "esik_taramasi": izgara,
        "bilinen_yanlilik": (
            "en_iyi_esik üç yapılandırmada da aynı val kümesinde aranıyor "
            "(ADR-0007 ile aynı yöntem). Mutlak F1'ler optimistik; "
            "karşılaştırma adil."
        ),
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"kaskad_{datetime.now():%Y%m%d-%H%M%S}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
