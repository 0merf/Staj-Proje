"""ReID maliyeti — ÖLÇÜLMEMİŞ BİR GEREKÇEYİ ÖLÇER (P-51).

⚠ NEDEN BU BETİK VAR
--------------------
`botsort.py` şunu yazıyor ve Gün 1'den beri yazıyordu:

    with_reid=False,
    # ReID (görünüm eşleştirme) ayrı bir sinir ağı çalıştırır.
    # 20 kamerada GPU bütçesini aşar; hareket tabanlı eşleştirme
    # sabit kameralarda zaten yeterli. Faz 5'te ölçülüp
    # değerlendirilecek.

Son cümle gerekçenin kendisini çürütüyor: **"Faz 5'te ölçülüp
değerlendirilecek"** = henüz ölçülmedi. Yani "GPU bütçesini aşar"
bir ölçüm değil, bir tahmindi — ve kullanıcıya ölçülmüş gibi
aktarıldı.

⭐ Bu, projede ikinci kez oldu (ilki: "onların modeli 20 kamerada
gerçek zamanlı koşamaz" iddiası, ölçülmeden söylenmiş ve
kaldırılmıştı). Tekrarlanan bir hata dikkatsizlik değil, YÖNTEM
eksikliğidir — ve raporun tezi tam olarak budur.

NE ÖLÇÜLÜYOR
------------
Aynı video, aynı tespitler, iki takipçi ayarı:

    with_reid=False   (üretimdeki hâli)
    with_reid=True    (görünüm eşleştirme açık)

Ölçülen: takip adımının kare başına süresi ve VRAM. Tespit ve poz
maliyeti İKİSİNDE DE AYNI ve dışarıda tutuluyor — kıyaslanması
gereken şey yalnızca takipçinin farkı.

⚠⚠⚠ BU ÖLÇÜM İLK KOŞUDA GEÇERSİZ ÇIKTI — VE SEBEBİ ASIL BULGU
--------------------------------------------------------------
İlk koşu şunu verdi:

    with_reid=False : 0.494 ms/kare
    with_reid=True  : 0.519 ms/kare   → +0.025 ms (1.05×)

"ReID neredeyse bedava" diye okunabilirdi. Ama bir sinir ağı bu kadar
ucuz olamaz; şüphelenip takipçinin içine bakıldı:

    botsort.py · update():
        raw = tracker.update(batch, img=None)   ⬅ GÖRÜNTÜ VERİLMİYOR

⭐ ReID görünüm eşleştirmesi yapar: kişi kırpıntısını alıp gömme
vektörü çıkarır. **Görüntü verilmezse çalışamaz.** `with_reid=True`
bayrağı bir kodlayıcı nesnesi oluşturuyor (`encoder=function`) ama
o kodlayıcı hiç çağrılmıyor.

Yani ölçüm, kapalı ReID ile kapalı ReID'i kıyaslamış oldu. +0.025 ms
ReID'in maliyeti değil, ölçüm gürültüsü.

⭐⭐ ASIL BULGU: `with_reid` bayrağı bu boru hattında **ETKİSİZ**.
Ve koddaki gerekçe ("20 kamerada GPU bütçesini aşar") yalnızca
ölçülmemiş değil, **yanlış sebebi** gösteriyordu. Gerçek sebep
mimari: takipçi arayüzü piksel almıyor — ki bu mimari kural 1'in
(ham kare kuyruktan geçmez) doğrudan sonucu.

ReID'i açmak bir bayrak değişikliği değil, **mimari değişikliktir**:
takipçiye kare referansı taşınmalı. Maliyeti ancak ondan sonra
ölçülebilir.

⚠ 20 KAMERAYA ÇEVİRME
Tek kameradaki fark ölçülüp 20 ile çarpılıyor. Bu bir ÜST SINIR
tahmini: gerçekte tek GPU worker'ı partili çalışıyor ve ReID de
partilenebilir. Rapor bunu böyle söylemeli — ölçüm tek kamerada,
çıkarım 20 kameraya.

Kullanım:
    uv run python scripts/benchmark_reid.py --kamera cam-15 --kare 200
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIDEOLAR = PROJECT_ROOT / "data" / "videos"
BENCHMARKS = PROJECT_ROOT / "benchmarks"

KAMERA_SAYISI = 20
# Analiz hızı — K4'te ölçülen canlı değer.
CANLI_FPS = 2.75


def _vram_mb() -> float | None:
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        return torch.cuda.memory_allocated() / 1024 / 1024
    except Exception:
        return None


def _kos(kareler: list[Any], *, reid: bool, imgsz: int) -> dict[str, Any] | None:
    """Bir takipçi ayarıyla tüm kareleri işler, takip süresini ölçer."""
    from sentinel.inference.tracker.botsort import BotSortTracker, default_args

    args = default_args()
    args.with_reid = reid
    try:
        takipci = BotSortTracker(args=args, frame_rate=int(CANLI_FPS) or 1)
    except Exception as hata:
        print(f"  ⚠ with_reid={reid} başlatılamadı: {type(hata).__name__}: {hata}")
        return None

    sureler: list[float] = []
    iz_sayilari: list[int] = []
    kamera = "bench"
    try:
        for i, (ts, tespitler) in enumerate(kareler):
            t0 = time.perf_counter()
            izler = takipci.update(kamera, tespitler, ts)
            sureler.append((time.perf_counter() - t0) * 1000.0)
            iz_sayilari.append(len(izler))
            if i == 2:  # ilk kareler ısınma — atılıyor
                sureler.clear()
    except Exception as hata:
        print(f"  ⚠ with_reid={reid} koşarken hata: {type(hata).__name__}: {hata}")
        return None

    if not sureler:
        return None
    s = sorted(sureler)
    return {
        "reid": reid,
        "kare": len(sureler),
        "ms_medyan": round(statistics.median(s), 3),
        "ms_p90": round(s[min(len(s) - 1, int(len(s) * 0.9))], 3),
        "ms_ortalama": round(statistics.fmean(s), 3),
        "iz_ortalama": round(statistics.fmean(iz_sayilari), 2),
        "vram_mb": _vram_mb(),
    }


def _reid_gercekten_calisiyor() -> bool:
    """`with_reid=True` gerçekten görünüm eşleştirmesi yapıyor mu?

    ⚠ Bayrağın açık olması yetmez. ReID kişi kırpıntısından gömme
    vektörü çıkarır; bunun için KAREYE ihtiyacı vardır. Boru hattımız
    takipçiye kare vermiyor (`tracker.update(batch, img=None)`), o
    yüzden kodlayıcı oluşuyor ama hiç çağrılmıyor.
    """
    import inspect

    from sentinel.inference.tracker import botsort as bs

    kaynak = inspect.getsource(bs.BotSortTracker.update)
    return "img=None" not in kaynak


def main() -> int:
    ap = argparse.ArgumentParser(description="ReID maliyeti ölçümü")
    ap.add_argument("--kamera", default="cam-15")
    ap.add_argument("--kare", type=int, default=200)
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    video = VIDEOLAR / f"{args.kamera}.mp4"
    if not video.is_file():
        print(f"❌ Video yok: {video}", file=sys.stderr)
        return 1

    import cv2

    from sentinel.core.preprocess import letterbox
    from sentinel.inference.detector.yolo import UltralyticsDetector

    dedektor = UltralyticsDetector(
        PROJECT_ROOT / "backend" / "models" / "yolo26s.pt",
        imgsz=args.imgsz, half=True,
    )
    dedektor.warmup(1)

    # ⚠ TESPİTLER BİR KEZ ÜRETİLİP SAKLANIYOR.
    # İki takipçi ayarı AYNI girdiyi görmeli; yeniden tespit etmek
    # ölçüme model gürültüsü karıştırırdı (P-17'nin dersi: iki koşuyu
    # kıyaslarken tek değişken değişmeli).
    print(f"{args.kamera} · tespitler çıkarılıyor ({args.kare} kare)…")
    cap = cv2.VideoCapture(str(video))
    kaynak_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    adim = max(1, round(kaynak_fps / CANLI_FPS))
    kareler: list[Any] = []
    kare_no = 0
    while len(kareler) < args.kare:
        ok, kare = cap.read()
        if not ok:
            break
        if kare_no % adim == 0:
            hazir, _lb = letterbox(kare, args.imgsz)
            kareler.append((kare_no / kaynak_fps, dedektor.detect([hazir])[0]))
        kare_no += 1
    cap.release()
    print(f"  {len(kareler)} kare · ortalama "
          f"{statistics.fmean(len(d) for _t, d in kareler):.1f} tespit/kare\n")

    # ⭐ ÖNCE GEÇERLİLİK: ReID gerçekten koşuyor mu?
    # Bu kontrol olmadan ölçüm "kapalı ⟷ kapalı" kıyaslar ve
    # "ReID bedava" diye yanlış okunur.
    reid_calisiyor = _reid_gercekten_calisiyor()
    durum = "EVET" if reid_calisiyor else "❌ HAYIR"
    print(f"ReID gerçekten çalışıyor mu: {durum}\n")

    kapali = _kos(kareler, reid=False, imgsz=args.imgsz)
    acik = _kos(kareler, reid=True, imgsz=args.imgsz)

    print("═══ TAKİP ADIMI MALİYETİ (kare başına, ms) ═══")
    print(f"{'ayar':<16} {'medyan':>9} {'p90':>9} {'ortalama':>10} {'iz/kare':>9}")
    for ad, r in (("with_reid=False", kapali), ("with_reid=True", acik)):
        if r is None:
            print(f"{ad:<16} {'ÇALIŞMADI':>9}")
            continue
        print(f"{ad:<16} {r['ms_medyan']:>9.3f} {r['ms_p90']:>9.3f} "
              f"{r['ms_ortalama']:>10.3f} {r['iz_ortalama']:>9.2f}")

    sonuc: dict[str, Any] = {
        "olculdu": datetime.now(UTC).isoformat(),
        "kamera": args.kamera,
        "kare": len(kareler),
        "ornekleme_fps": CANLI_FPS,
        "kapali": kapali,
        "acik": acik,
        "yontem": "aynı tespitler, iki takipçi ayarı; tespit+poz maliyeti hariç",
    }

    if not reid_calisiyor:
        print("\n═══ KARAR ═══")
        print("❌ ÖLÇÜM GEÇERSİZ — ReID hiç çalışmadı.")
        print("   `botsort.py · update()` takipçiye `img=None` veriyor.")
        print("   ReID görünüm eşleştirmesi yapar; görüntü olmadan")
        print("   kodlayıcı oluşur ama HİÇ ÇAĞRILMAZ.")
        print("\n⭐ Yukarıdaki iki satır 'kapalı ReID ⟷ kapalı ReID'dir;")
        print("   aradaki fark ReID'in maliyeti değil, ölçüm gürültüsüdür.")
        print("\n⭐⭐ ASIL BULGU: `with_reid` bayrağı bu boru hattında")
        print("   ETKİSİZ. Koddaki gerekçe ('20 kamerada GPU bütçesini")
        print("   aşar') hem ölçülmemiş hem YANLIŞ SEBEBİ gösteriyordu.")
        print("   Gerçek sebep mimari: takipçi arayüzü piksel almıyor —")
        print("   mimari kural 1'in (ham kare kuyruktan geçmez) sonucu.")
        print("   ReID'i açmak bayrak değil, MİMARİ değişikliktir.")
        sonuc["gecerli"] = False
        sonuc["gecersizlik_sebebi"] = "tracker.update(batch, img=None) — ReID koşamaz"
        sonuc["butceyi_asiyor"] = None
    elif kapali and acik:
        fark = acik["ms_medyan"] - kapali["ms_medyan"]
        kat = acik["ms_medyan"] / max(kapali["ms_medyan"], 1e-9)
        # 20 kamera × canlı analiz hızı
        saniyede_kare = KAMERA_SAYISI * CANLI_FPS
        ek_ms_sn = fark * saniyede_kare
        print(f"\nfark: {fark:+.3f} ms/kare ({kat:.2f}×)")
        print(f"\n20 kamera × {CANLI_FPS} FPS = {saniyede_kare:.0f} kare/sn")
        print(f"ReID'in ek maliyeti: {ek_ms_sn:.1f} ms/saniye "
              f"= tek çekirdeğin %{ek_ms_sn / 10:.1f}'i")
        sonuc["fark_ms"] = round(fark, 3)
        sonuc["kat"] = round(kat, 3)
        sonuc["yirmi_kamera_ek_ms_sn"] = round(ek_ms_sn, 1)
        sonuc["butceyi_asiyor"] = bool(ek_ms_sn > 1000.0)
        print("\n═══ KARAR ═══")
        if ek_ms_sn > 1000.0:
            print("❌ Bütçeyi AŞIYOR (>1000 ms/sn = bir çekirdek tamamen dolu).")
            print("   Koddaki 'GPU bütçesini aşar' gerekçesi DOĞRULANDI.")
        else:
            print("⚠ Bütçeyi AŞMIYOR. Koddaki gerekçe ölçümle DESTEKLENMEDİ.")
            print("   `with_reid=False` kararı yeniden değerlendirilmeli —")
            print("   ama bu ölçüm yalnızca HIZI kapsıyor; ReID ağının VRAM")
            print("   maliyeti ve kimlik kararlılığına katkısı ayrı ölçülmeli.")
    elif acik is None:
        print("\n═══ KARAR ═══")
        print("⚠ with_reid=True bu kurulumda ÇALIŞMADI (ReID ağırlığı yok /")
        print("   ultralytics sürümü desteklemiyor). Yani mevcut kararın")
        print("   gerçek gerekçesi 'pahalı' değil, 'kurulmamış' olabilir.")
        print("   Raporda böyle yazılacak — tahmin, ölçüm diye sunulmayacak.")
        sonuc["butceyi_asiyor"] = None

    BENCHMARKS.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = BENCHMARKS / f"reid_maliyeti_{damga}.json"
    hedef.write_text(json.dumps(sonuc, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
