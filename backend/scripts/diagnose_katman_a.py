"""KATMAN A neden susuyor? — profilin içine bakan tanı betiği.

Neden bu betik
--------------
K6 ölçümü dört kez koşturuldu ve Katman A her seferinde neredeyse hiç
skor üretmedi: sıfırdan farklı oran %5.3 → **%2.8** (daha fazla veriyle
DAHA AZ). AUC 0.493, yani tam şans seviyesi.

Üç hipotez denendi ve üçü de yanlış çıktı:
  1. "Profil hazır değil"      → hazır (16 751 gözlem)
  2. "Yeterli veri yok"        → 7× veriyle sonuç değişmedi
  3. "Isıtma yanlış ölçekte"   → aşağıda sınanıyor

Tahmin etmeyi bırakıp profilin İÇİNE bakmak gerekiyor. Bu betik üç
soruyu cevaplıyor:

  · Kaç hücre hız istatistiği yapacak kadar (≥30) gözlem gördü?
  · O hücrelerde ölçülen sapma ne kadar?
  · Test verisindeki hızlar profilin öğrendiği hızlarla aynı ÖLÇEKTE mi?

⚠ ÜÇÜNCÜ SORU KRİTİK ve benim kendi eklediğim bir risk
Yalın ısıtma yolu hızı `kutu yüksekliği` ile normalize ediyor;
değerlendirme yolu `özellik penceresi` üzerinden `govde_boyu()`
kullanıyor (iskelet varsa omuz-kalça × 3). İkisi farklı ölçekteyse
profil öğrendiği şeyden başka bir şeyle karşılaştırılıyor demektir —
ve o durumda z-skorlar anlamsız olur.

Kullanım
--------
    uv run python scripts/diagnose_katman_a.py
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AVENUE = PROJECT_ROOT / "data" / "archive" / "Avenue_Dataset" / "Avenue Dataset"

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    from evaluate_k6 import _PROFIL, _klip_skorla, _profili_isit

    from sentinel.analytics.anomaly import normalcy
    from sentinel.inference.detector.yolo import UltralyticsDetector
    from sentinel.inference.pose.yolo import YoloPoseEstimator

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "backend" / "models" / "yolo26s.pt", imgsz=640, half=True
    )
    poz = YoloPoseEstimator(PROJECT_ROOT / "backend" / "models" / "yolo26s-pose.pt")
    dedektor.warmup(1)
    poz.warmup(8)

    egitim = sorted((AVENUE / "training_videos").glob("*.avi"))[:8]
    print(f"profil ısıtılıyor: {len(egitim)} klip @ 25 FPS...")
    for i, yol in enumerate(egitim, 1):
        _profili_isit(yol, dedektor=dedektor, poz=poz, ornek_fps=25.0, imgsz=640)
        print(f"\r  {i}/{len(egitim)}", end="", flush=True)
    print()

    profil = _PROFIL["avenue"]
    print(f"\ntoplam gözlem: {profil.toplam_ornek} · hazır: {profil.hazir}")

    # ─── 1. Hücre doluluğu ───
    ziyaret = profil.ziyaret
    dolu = int((ziyaret > 0).sum())
    yeterli = int((ziyaret >= normalcy.HUCRE_ASGARI_ORNEK).sum())
    print(
        f"\nHÜCRE DOLULUĞU ({normalcy.IZGARA_Y}×{normalcy.IZGARA_X} = "
        f"{ziyaret.size} hücre)"
    )
    print(f"  ziyaret edilen           : {dolu} (%{dolu / ziyaret.size * 100:.0f})")
    print(
        f"  hız istatistiği yapabilen: {yeterli} "
        f"(≥{normalcy.HUCRE_ASGARI_ORNEK} gözlem)"
    )
    print(f"  nadir hücre eşiği        : <{profil.toplam_ornek * normalcy.NADIR_HUCRE_ORAN:.1f} ziyaret")
    if yeterli:
        print(f"  en yoğun hücre           : {int(ziyaret.max())} ziyaret")

    # ─── 2. Öğrenilen hız dağılımı ───
    hizlar = [(w.ortalama, w.sapma, w.n) for w in profil.hiz.values() if w.n >= 5]
    if hizlar:
        ortalamalar = [h[0] for h in hizlar]
        sapmalar = [h[1] for h in hizlar]
        print(f"\nÖĞRENİLEN HIZ ({len(hizlar)} hücre, ≥5 gözlem)")
        print(
            f"  hücre ortalaması : p50 {statistics.median(ortalamalar):.3f} · "
            f"azami {max(ortalamalar):.3f} gövde/sn"
        )
        print(
            f"  hücre sapması    : p50 {statistics.median(sapmalar):.3f} · "
            f"taban {normalcy.TABAN_SAPMA_HIZ}"
        )
        # ⚠ Sapma tabandan küçükse z-skor tabana bölünüyor demektir.
        taban_alti = sum(1 for s in sapmalar if s < normalcy.TABAN_SAPMA_HIZ)
        print(
            f"  sapması tabandan küçük: {taban_alti}/{len(sapmalar)} "
            f"(%{taban_alti / len(sapmalar) * 100:.0f}) — bunlarda z, tabana bölünüyor"
        )

    # ─── 3. ÖLÇEK KARŞILAŞTIRMASI — asıl şüpheli ───
    print("\nÖLÇEK DENETİMİ — ısıtma ile değerlendirme aynı birimde mi?")
    test = sorted((AVENUE / "testing_videos").glob("*.avi"))[:2]
    kareler = []
    for yol in test:
        kareler.extend(
            _klip_skorla(yol, dedektor=dedektor, poz=poz, ornek_fps=4.0, imgsz=640)
        )
    # `_klip_skorla` Katman A skorunu döndürüyor; hızları ayrıca ölçmek
    # için profile sorulan değerlerin dağılımına bakmak gerekiyor.
    a_skorlari = [k[2] for k in kareler]
    sifirdan_farkli = [v for v in a_skorlari if v > 0]
    print(f"  test karesi              : {len(a_skorlari)}")
    print(
        f"  Katman A sıfırdan farklı : {len(sifirdan_farkli)} "
        f"(%{len(sifirdan_farkli) / max(len(a_skorlari), 1) * 100:.1f})"
    )
    if sifirdan_farkli:
        print(f"  sıfırdan farklıların p50 : {statistics.median(sifirdan_farkli):.3f}")

    # Öğrenilen hız ortalamalarının medyanı ile canlı hızları kıyasla
    if hizlar:
        ogrenilen_p50 = statistics.median(ortalamalar)
        print(
            f"\n  öğrenilen hız p50 (ısıtma yolu) : {ogrenilen_p50:.3f} gövde/sn"
        )
        print(
            "  ⚠ Canlı ölçümde gövde hızı p50 = 0.30 gövde/sn "
            "(benchmarks/features_20260826-175748.json)"
        )
        oran = ogrenilen_p50 / 0.30 if ogrenilen_p50 else 0.0
        print(f"  oran: {oran:.2f}×")
        if oran < 0.5 or oran > 2.0:
            print(
                "  ❌ ÖLÇEK UYUŞMUYOR — profil, değerlendirmede kullanılandan\n"
                "     farklı birimde öğrenmiş. z-skorlar anlamsız."
            )
        else:
            print("  ✅ ölçek makul aralıkta")

    # ─── 4. Yön histogramı ───
    yon_dolu = sum(1 for h in profil.yon.values() if int(np.sum(h)) >= normalcy.HUCRE_ASGARI_ORNEK)
    print(
        f"\nYÖN İSTATİSTİĞİ: {yon_dolu} hücre yeterli gözlem gördü\n"
        "  ⚠ Değerlendirme yolunda `yon=None` geçiliyor — yön testi HİÇ\n"
        "    çalışmıyor. Katman A'nın üç kolundan biri ölü."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
