"""MOD A / MOD B — analiz hızı doğruluğu nasıl etkiliyor? (P-55)

⭐ SORU KULLANICININ
-------------------
> *"Bizim analizimiz yavaş olduğu için, yani 2.5 FPS civarında olduğu
> için bilekler vb. hızlı görünüyor olabilir. Eğer saniyede 10-15 FPS
> civarında bir işlem gücü olsa daha detaylı ve derin inceleme şansı
> olacaktır — tabi gürültü de gelecektir ama modelin onu ayırt etmesi
> gerekir."*

Bu aynı zamanda **Mod A / Mod B** çalışmasının çekirdeği:

    MOD A — 20 kamera kısıtı altında ne yapabiliyoruz (2.75 FPS)
    MOD B — tek videoya tüm gücü versek ne olurdu (yüksek FPS)

İKİ ETKİ TERS YÖNDE ÇALIŞIYOR
-----------------------------
1. **Sonlu fark gürültüsü** — hız ardışık konumlardan hesaplanıyor:

       v̂ = (x₂ − x₁) / Δt        gürültü ≈ σ√2 / Δt

   Konum hatası σ sabit; Δt küçüldükçe gürültü BÜYÜR.
       2.75 FPS → Δt 0.364 sn →  3.9σ
       8.25 FPS → Δt 0.121 sn → 11.7σ
      15.0 FPS → Δt 0.067 sn → 21.2σ
   Yani yüksek FPS hız ölçümünü **bozar**.

2. **Zamansal örtüşme (aliasing)** — bir yumruk ~0.2 saniye sürer.
   2.75 FPS'te örnekler arası 0.36 sn; olay iki örnek arasına düşüp
   TAMAMEN kaçabilir. Yani düşük FPS olayı **kaçırır**.

Hangisinin baskın olduğu **ampirik** bir soru ve bu betik onu ölçüyor.

⚠⚠ TEK DEĞİŞKEN KURALI — VE BURADA NEDEN ZOR
--------------------------------------------
İlk denemede 2.75 FPS 482/96 klip, 8.25 FPS 545/108 klip üretti:
yüksek FPS'te daha çok kare → daha çok klip özellik çıkarabiliyor.
İkisini doğrudan kıyaslamak **iki farklı sınavı** kıyaslamak olurdu —
bu projede beş kez yakalanan hatanın aynısı (P-17, P-36, P-41, P-46).

Bu yüzden karşılaştırma **yalnızca ORTAK kliplerde** yapılıyor: her iki
FPS'te de özellik üretebilmiş klipler. Kalan tek değişken FPS.

⚠ Ve ortak kümeye inmenin bir bedeli var: kaybedilen klipler rastgele
değil — düşük FPS'te elenen klipler genellikle KISA ya da AZ KİŞİLİ
olanlar. Bu, ortak kümeyi "kolay" tarafa kaydırabilir; sonuç böyle
okunmalı.

Kullanım:
    uv run python scripts/deney_fps.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TMP = PROJECT_ROOT / "data" / "_tmp"
BENCHMARKS = PROJECT_ROOT / "benchmarks"

# (etiket, dosya adı) — hepsi AYNI klip havuzundan, farklı FPS'te.
KOSULAR = (
    ("2.75 FPS (MOD A · canlı)", "rwf_ozellikler.json"),
    ("4.00 FPS", "rwf_ozellikler_4fps.json"),
    ("8.25 FPS (MOD B)", "rwf_fps825.json"),
)


def _auc_ham(skor: list[float], etiket: list[int]) -> float:
    ciftler = sorted(zip(skor, etiket, strict=True))
    np_, nn = sum(etiket), len(etiket) - sum(etiket)
    if not np_ or not nn:
        return 0.5
    siralar = [0.0] * len(ciftler)
    i = 0
    while i < len(ciftler):
        j = i
        while j + 1 < len(ciftler) and ciftler[j + 1][0] == ciftler[i][0]:
            j += 1
        for k in range(i, j + 1):
            siralar[k] = (i + j) / 2.0 + 1.0
        i = j + 1
    poz = sum(s for s, (_v, e) in zip(siralar, ciftler, strict=True) if e == 1)
    return (poz - np_ * (np_ + 1) / 2) / (np_ * nn)


def _bootstrap(tahminler: dict[str, dict[str, Any]],
               tekrar: int = 2000) -> dict[str, dict[str, float]]:
    """Eşleştirilmiş bootstrap ile ΔAUC güven aralığı."""
    import random as _r

    if len(tahminler) < 2:
        return {}
    adlar = list(tahminler)
    taban = adlar[0]
    # Klip → (tahmin, etiket) eşlemesi; kümeler aynı olmalı.
    haritalar = {
        a: dict(zip(t["klip"], zip(t["tahmin"], t["etiket"], strict=True),
                    strict=True))
        for a, t in tahminler.items()
    }
    ortak_klip = sorted(set.intersection(*(set(h) for h in haritalar.values())))
    if len(ortak_klip) < 20:
        return {}
    # Tohumlu — bootstrap tekrar üretilebilir olmalı.
    rng = _r.Random(42)  # noqa: S311
    cikti: dict[str, dict[str, float]] = {}
    for a in adlar[1:]:
        farklar: list[float] = []
        for _ in range(tekrar):
            ornek = [rng.choice(ortak_klip) for _ in range(len(ortak_klip))]
            e = [haritalar[taban][k][1] for k in ornek]
            if not (0 < sum(e) < len(e)):
                continue
            s1 = [haritalar[taban][k][0] for k in ornek]
            s2 = [haritalar[a][k][0] for k in ornek]
            farklar.append(_auc_ham(s2, e) - _auc_ham(s1, e))
        if not farklar:
            continue
        farklar.sort()
        cikti[f"{a} − {taban}"] = {
            "fark": sum(farklar) / len(farklar),
            "alt": farklar[int(len(farklar) * 0.025)],
            "ust": farklar[int(len(farklar) * 0.975)],
            "p_artı": sum(1 for f in farklar if f > 0) / len(farklar),
        }
    return cikti


def _yukle(ad: str) -> dict[str, Any] | None:
    y = TMP / ad
    if not y.is_file():
        return None
    return json.loads(y.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="FPS deneyi (Mod A/B)")
    ap.parse_args()

    veriler: dict[str, dict[str, Any]] = {}
    for etiket, ad in KOSULAR:
        d = _yukle(ad)
        if d is None:
            print(f"⚠ {ad} yok — '{etiket}' atlanıyor")
            continue
        veriler[etiket] = d

    if len(veriler) < 2:
        print("❌ En az iki FPS koşusu gerekli.", file=sys.stderr)
        return 1

    print("═══ HAM KOŞULAR (ortak kümeye İNMEDEN) ═══")
    print(f"{'koşul':<26} {'train':>7} {'val':>6}")
    for etiket, d in veriler.items():
        print(f"{etiket:<26} {len(d['train']):>7} {len(d['val']):>6}")

    # ─── ORTAK KLİP KÜMESİ ───
    ortak: dict[str, set[str]] = {}
    for bolum in ("train", "val"):
        kumeler = [
            {str(k["klip"]) for k in d[bolum]} for d in veriler.values()
        ]
        ortak[bolum] = set.intersection(*kumeler)
    print(f"\n⭐ ORTAK: train {len(ortak['train'])} · val {len(ortak['val'])}")
    print("  (her iki/üç FPS'te de özellik üretebilmiş klipler)\n")

    if len(ortak["val"]) < 30:
        print("⚠ Ortak val kümesi çok küçük — sonuç gürültülü okunmalı.")

    # ─── Filtrelenmiş dosyaları yaz ve eğit ───
    sonuc: dict[str, Any] = {}
    tahminler: dict[str, dict[str, Any]] = {}
    print("═══ AYNI KLİPLER, TEK DEĞİŞKEN: FPS ═══")
    print(f"{'koşul':<26} {'AUC':>7} {'F1':>7} {'kesinlik':>9} {'duyarlılık':>11}")
    for etiket, d in veriler.items():
        filtreli = {
            bolum: [k for k in d[bolum] if str(k["klip"]) in ortak[bolum]]
            for bolum in ("train", "val")
        }
        ad = f"_fps_deney_{abs(hash(etiket)) % 100000}.json"
        (TMP / ad).write_text(json.dumps(filtreli, ensure_ascii=False),
                              encoding="utf-8")
        # ⚠ Eğitim ALT SÜREÇTE koşuluyor: aynı betiğin içinden LightGBM'i
        # tekrar tekrar çağırmak durum sızdırabilir (rastgele tohum,
        # global ayar). Ayrı süreç, temiz zemin.
        tahmin_ad = f"_fps_tahmin_{abs(hash(etiket)) % 100000}.json"
        cikti = subprocess.run(  # noqa: S603
            [sys.executable, str(Path(__file__).parent / "train_aggression.py"),
             "--egit", "--ozellik-dosyasi", ad,
             "--tahmin-cikti", tahmin_ad],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(Path(__file__).parents[1]), check=False,
        )
        satir = next(
            (s for s in cikti.stdout.splitlines() if "MODEL (LightGBM)" in s), ""
        )
        if not satir:
            print(f"{etiket:<26} {'BAŞARISIZ':>7}")
            print((cikti.stderr or cikti.stdout)[-400:])
            continue
        p = satir.split()
        auc, f1, duy, kes = (float(p[2]), float(p[3]), float(p[4]), float(p[5]))
        print(f"{etiket:<26} {auc:>7.3f} {f1:>7.3f} {kes:>9.3f} {duy:>11.3f}")
        sonuc[etiket] = {"auc": auc, "f1": f1, "kesinlik": kes,
                         "duyarlilik": duy,
                         "train": len(filtreli["train"]),
                         "val": len(filtreli["val"])}
        ty = TMP / tahmin_ad
        if ty.is_file():
            tahminler[etiket] = json.loads(ty.read_text(encoding="utf-8"))
            ty.unlink(missing_ok=True)
        (TMP / ad).unlink(missing_ok=True)

    # ─── ⭐ EŞLEŞTİRİLMİŞ BOOTSTRAP ───
    # ⚠ Determinizm ANLAMLILIK DEĞİLDİR. Eğitim birebir tekrarlanabilir
    # (iki koşuda da 0.906 / 0.903 / 0.936 çıktı) ama 96 kliplik bir
    # doğrulama kümesinde 0.030'luk bir AUC farkı yine de örnekleme
    # gürültüsü olabilir.
    #
    # Eşleştirilmiş bootstrap: val kliplerini yeniden örnekle, HER İKİ
    # ayarın AUC'sini AYNI örneklemde hesapla, farkın dağılımına bak.
    # Eşleştirme, kliplerin zorluk farkından gelen varyansı düşürüyor —
    # eşleştirilmemiş bir test bu farkı bulamayacak kadar geniş bir
    # aralık verirdi.
    bs = _bootstrap(tahminler)
    if bs:
        print("\n═══ EŞLEŞTİRİLMİŞ BOOTSTRAP (2000 tekrar) ═══")
        print(f"{'karşılaştırma':<36} {'ΔAUC':>8} {'%95 GA':>20} {'P(>0)':>7}")
        for ad_, d in bs.items():
            ga = f"[{d['alt']:+.3f}, {d['ust']:+.3f}]"
            print(f"{ad_:<36} {d['fark']:>+8.3f} {ga:>20} {d['p_artı']:>6.0%}")

    print("\n═══ YORUM ═══")
    if len(sonuc) >= 2:
        sirali = sorted(sonuc.items(), key=lambda kv: kv[1]["auc"], reverse=True)
        en_iyi = sirali[0]
        print(f"En yüksek AUC: {en_iyi[0]} ({en_iyi[1]['auc']:.3f})")
        aralik = max(v["auc"] for v in sonuc.values()) - min(
            v["auc"] for v in sonuc.values())
        print(f"AUC aralığı  : {aralik:.3f}")
        if aralik < 0.03:
            print("\n⭐ FPS'in etkisi GÜRÜLTÜ İÇİNDE. Analiz hızını artırmak")
            print("   doğruluğu belirgin biçimde değiştirmiyor.")
            print("   → MOD B'nin (tek videoya tüm güç) doğruluk gerekçesi YOK.")
            print("   → 20 kamera kısıtı bir doğruluk bedeli ödetmİYOR.")
        elif en_iyi[0].startswith("2.75"):
            print("\n⭐ DÜŞÜK FPS DAHA İYİ. Sonlu fark gürültüsü (σ√2/Δt)")
            print("   örtüşme kaybına baskın geliyor — hız temelli")
            print("   özelliklerde daha sık örneklemek zarar veriyor.")
        else:
            print("\n⭐ YÜKSEK FPS DAHA İYİ. Örtüşme kaybı gürültüye baskın:")
            print("   daha sık örnekleme kısa süreli olayları yakalıyor.")
            print("   → MOD B'nin doğruluk gerekçesi VAR; maliyeti ölçülmeli.")

    print("\n⚠ Ortak kümeye inmenin yanlılığı: düşük FPS'te elenen klipler")
    print("  rastgele değil (kısa / az kişili olanlar). Ortak küme bir")
    print("  miktar 'kolay' tarafa kaymış olabilir.")

    BENCHMARKS.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = BENCHMARKS / f"fps_deneyi_{damga}.json"
    hedef.write_text(json.dumps({
        "olculdu": datetime.now(UTC).isoformat(),
        "yontem": "aynı klipler (ortak küme), tek değişken FPS",
        "ortak_train": len(ortak["train"]), "ortak_val": len(ortak["val"]),
        "ham_klip_sayilari": {e: {"train": len(d["train"]), "val": len(d["val"])}
                              for e, d in veriler.items()},
        "sonuclar": sonuc,
        "bootstrap": bs,
        "gurultu_modeli": {
            "formul": "hız gürültüsü ≈ σ√2/Δt",
            "2.75_fps": 3.9, "8.25_fps": 11.7, "15_fps": 21.2,
            "birim": "σ katı",
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
