"""ŞÜPHELİ ESKİ ÖLÇÜMLERİ YENİDEN YAPAR — duvar saati VE CPU zamanı (P-59).

⚠⚠ NEDEN BU BETİK VAR
---------------------
P-58'de projenin en pahalı ölçüm hatası bulundu:

> Modelin `predict` çağrısı **0.307 ms** ölçülüyordu ve bu sayı
> DOĞRUYDU. Ama iş 20 iş parçacığına yayıldığı için duvar saati
> küçüktü; **CPU zamanı 20 katıydı** ve asıl maliyet oradaydı.
> Analitik worker 8 çekirdek yiyordu.

⭐ Bu, tek bir ölçümün hatası değil, bir **ÖLÇÜM SINIFININ** hatası:
çok iş parçacıklı çalışan her şeyi "kaç ms sürdü" diye ölçmek
maliyeti sistematik olarak **eksik gösterir**.

Projedeki şu ölçümler bu sınıfa giriyor ve hiçbiri CPU zamanıyla
doğrulanmadı:

    P-30  "ifade 7.4 ms/yüz"        — ONNX Runtime çok iş parçacıklı
    P-07/P-09 "NVDEC daha yavaş"    — çok erken, az yükle, tek ölçüt
    P-18  "ön işleme 6.78 → 3.87 ms" — OpenCV çok iş parçacıklı
    detect "6.3 ms, %53 ileri geçiş" — CUDA olayıyla ölçüldü (bu sağlam)

⚠ KARŞILAŞTIRMA ZEMİNİ YOK — VE BU DÜRÜSTÇE SÖYLENMELİ
Kod, mimari ve kütüphane sürümleri o günden bu yana değişti. Bu
yüzden bu betik "eski sayı yanlıştı" diyemez; yalnızca **bugünün
sayısını doğru yöntemle** üretir. Eski sayılarla fark görülürse
sebebi ölçüm yöntemi de olabilir, kod değişikliği de.

NE ÖLÇÜLÜYOR — VE NEDEN İKİ SAYI
---------------------------------
Her aşama için:

    duvar saati (ms)  — "kullanıcı ne kadar bekledi"
    CPU zamanı (ms)   — "kaç çekirdek-milisaniye harcandı"
    paralellik        — CPU / duvar oranı

⭐ Oran 1.0 ise tek iş parçacıklı. 8.0 ise iş 8 çekirdeğe yayılmış:
duvar saati küçük görünür ama 20 kameralık bir sistemde o 8 çekirdek
gerçek bir kısıttır.

⚠ CPU zamanı `psutil.Process().cpu_times()` farkından alınıyor —
sürecin TAMAMINI kapsar. Bu yüzden ölçüm sırasında başka iş
yapılmamalı ve boru hattı KAPALI olmalı.

Kullanım:
    uv run python scripts/yeniden_olc.py
    uv run python scripts/yeniden_olc.py --tekrar 200 --kamera cam-15
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

# ⚠⚠ THREAD AYARI `sentinel` IMPORT EDİLMEDEN ÖNCE YAPILMALI
#
# `sentinel/__init__.py` BLAS havuzunu tek iş parçacığına sabitliyor
# (P-58) ama yalnızca ortam değişkeni TANIMSIZSA. Burada önce
# tanımlarsak o dokunmuyor ve eski (sınırsız) davranışı ölçebiliyoruz.
#
# ⭐ Bu, ölçümün ta kendisi: "eski sayılar çok iş parçacıklılık
# yüzünden mi düşük görünüyordu?" sorusu ancak İKİ KOŞU kıyaslanınca
# cevaplanır.
_THREAD = None
for _i, _a in enumerate(sys.argv):
    if _a == "--thread" and _i + 1 < len(sys.argv):
        _THREAD = sys.argv[_i + 1]
if _THREAD:
    import os as _os

    for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
               "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        _os.environ[_k] = _THREAD

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIDEOLAR = PROJECT_ROOT / "data" / "videos"
BENCHMARKS = PROJECT_ROOT / "benchmarks"

# Eski iddialar — karşılaştırma için, "doğru cevap" olarak DEĞİL.
ESKI = {
    "on_isleme": {"ms": 3.87, "kayit": "P-18", "not": "6.78 → 3.87 iddiası"},
    "tespit": {"ms": 6.30, "kayit": "P-33", "not": "%53'ü ileri geçiş"},
    "poz": {"ms": None, "kayit": "benchmark_pose", "not": "kayıt yok"},
    "yuz_tespit": {"ms": 1.46, "kayit": "P-30", "not": "YuNet"},
    "ifade": {"ms": 7.40, "kayit": "P-30", "not": "eski iddia 58 ms'ti"},
}


class Olcum:
    """Bir aşamayı hem duvar saati hem CPU zamanıyla ölçer.

    ⚠ CPU zamanı süreç geneli: `cpu_times()` kullanıcı + sistem
    zamanını TÜM iş parçacıkları için toplar. Ölçüm sırasında başka
    iş yapılmamalı.
    """

    def __init__(self) -> None:
        import psutil

        self._p = psutil.Process()

    def __call__(self, ad: str, fn: Any, tekrar: int) -> dict[str, Any]:
        # Isınma — ilk çağrılar tembel yükleme yapıyor.
        for _ in range(min(5, tekrar)):
            fn()

        c0 = self._p.cpu_times()
        t0 = time.perf_counter()
        for _ in range(tekrar):
            fn()
        duvar = (time.perf_counter() - t0) / tekrar * 1000
        c1 = self._p.cpu_times()
        cpu = ((c1.user - c0.user) + (c1.system - c0.system)) / tekrar * 1000
        return {
            "asama": ad,
            "duvar_ms": round(duvar, 3),
            "cpu_ms": round(cpu, 3),
            "paralellik": round(cpu / duvar, 2) if duvar > 1e-9 else 0.0,
            "tekrar": tekrar,
        }


def main() -> int:
    ap = argparse.ArgumentParser(description="Şüpheli ölçümleri yeniden yap")
    ap.add_argument("--kamera", default="cam-15")
    ap.add_argument("--tekrar", type=int, default=120)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--thread", default="",
                    help="BLAS/OpenMP iş parçacığı sayısı (boş = kod "
                         "varsayılanı olan 1). Eski davranışı ölçmek "
                         "için çekirdek sayısını verin.")
    args = ap.parse_args()

    video = VIDEOLAR / f"{args.kamera}.mp4"
    if not video.is_file():
        print(f"❌ Video yok: {video}", file=sys.stderr)
        return 1

    import os as _os

    import cv2
    import psutil

    from sentinel.config import settings
    from sentinel.core.preprocess import letterbox
    print(f"makine: {psutil.cpu_count()} mantıksal çekirdek · "
          f"OMP_NUM_THREADS={_os.environ.get('OMP_NUM_THREADS', '(ayarsız)')}")
    print(f"video : {args.kamera} · tekrar {args.tekrar}\n")

    # Tek kare oku (tüm aşamalar aynı kareyi kullansın — tek değişken).
    cap = cv2.VideoCapture(str(video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 200)
    ok, kare = cap.read()
    cap.release()
    if not ok:
        print("❌ Kare okunamadı", file=sys.stderr)
        return 1

    olc = Olcum()
    sonuc: list[dict[str, Any]] = []

    # ─── 1. Ön işleme (letterbox) — P-18 ───
    sonuc.append(olc("on_isleme", lambda: letterbox(kare, args.imgsz),
                     args.tekrar * 5))

    hazir, _lb = letterbox(kare, args.imgsz)

    # ─── 2. Tespit — P-33 ───
    from sentinel.inference.detector.yolo import UltralyticsDetector

    dedektor = UltralyticsDetector(
        settings.detector_weights, imgsz=args.imgsz, half=True,
    )
    dedektor.warmup(2)
    tespitler = dedektor.detect([hazir])[0]
    print(f"tespit sayısı: {len(tespitler)} kişi\n")
    sonuc.append(olc("tespit", lambda: dedektor.detect([hazir]), args.tekrar))

    # ─── 3. Poz ───
    from sentinel.inference.pose.yolo import YoloPoseEstimator

    poz = YoloPoseEstimator(settings.pose_weights)
    poz.warmup(8)
    sonuc.append(olc("poz", lambda: poz.estimate([hazir], [tespitler]),
                     args.tekrar))

    # ─── 4. Yüz tespiti + ifade — P-30 ───
    try:
        from sentinel.inference.emotion.yunet import (
            EmotiEffExpressionClassifier,
            YuNetFaceDetector,
        )

        yuz = YuNetFaceDetector(settings.face_detector_weights)
        # ⚠ YuNet TÜM KAREDE değil, KİŞİ KIRPINTISINDA yüz arıyor
        # (yunet.py: "Kişi kırpıntısının üst bölgesinde"). Ölçüm de
        # üretimdeki gibi kırpıntıyla yapılmalı — tüm kareyi vermek
        # başka bir işi ölçer ve P-30'un sayısıyla kıyaslanamaz.
        if tespitler:
            d0 = tespitler[0]
            kirpinti = hazir[
                max(0, int(d0.y1)):int(d0.y2), max(0, int(d0.x1)):int(d0.x2)
            ]
        else:
            kirpinti = hazir
        sonuc.append(olc("yuz_tespit", lambda: yuz.detect(kirpinti),
                         args.tekrar))

        kutu = yuz.detect(kirpinti)
        print(f"yüz bulundu: {'evet' if kutu else 'hayır'}\n")
        if kutu is not None:
            sinif = EmotiEffExpressionClassifier()
            yk = kirpinti[
                max(0, int(kutu.y1)):int(kutu.y2),
                max(0, int(kutu.x1)):int(kutu.x2),
            ]
            if yk.size:
                sonuc.append(olc("ifade", lambda: sinif.classify([yk]),
                                 max(20, args.tekrar // 4)))
    except Exception as hata:
        print(f"⚠ yüz/ifade ölçülemedi: {type(hata).__name__}: {hata}\n")

    # ─── 5. Decode — P-07/P-09 ───
    # ⚠ Ayrı ölçülüyor: tek kare değil, akıştan ardışık kare çözme.
    def _decode_n(n: int = 30) -> float:
        c = cv2.VideoCapture(str(video))
        c.set(cv2.CAP_PROP_POS_FRAMES, 100)
        for _ in range(n):
            c.read()
        c.release()
        return 0.0

    c0 = psutil.Process().cpu_times()
    t0 = time.perf_counter()
    _decode_n(150)
    duvar = (time.perf_counter() - t0) / 150 * 1000
    c1 = psutil.Process().cpu_times()
    cpu = ((c1.user - c0.user) + (c1.system - c0.system)) / 150 * 1000
    sonuc.append({
        "asama": "decode_cpu", "duvar_ms": round(duvar, 3),
        "cpu_ms": round(cpu, 3),
        "paralellik": round(cpu / duvar, 2) if duvar > 1e-9 else 0.0,
        "tekrar": 150,
    })

    # ─── Rapor ───
    print("═══ ⭐ DUVAR SAATİ ⟷ CPU ZAMANI ═══")
    print(f"{'aşama':<14} {'duvar ms':>10} {'CPU ms':>10} {'paralellik':>12} "
          f"{'eski iddia':>12}")
    for s in sonuc:
        eski = ESKI.get(s["asama"], {})
        e = eski.get("ms")
        e_str = f"{e:.2f}" if e else "—"
        isaret = ""
        if s["paralellik"] > 2.0:
            isaret = "  ⚠ çok iş parçacıklı"
        print(f"{s['asama']:<14} {s['duvar_ms']:>10.3f} {s['cpu_ms']:>10.3f} "
              f"{s['paralellik']:>12.2f} {e_str:>12}{isaret}")

    print("\n═══ YORUM ═══")
    coklu = [s for s in sonuc if s["paralellik"] > 2.0]
    if coklu:
        print("⚠ Şu aşamalar çok iş parçacıklı çalışıyor — duvar saati")
        print("  maliyetlerini EKSİK gösteriyor:")
        for s in coklu:
            print(f"   {s['asama']:<14} duvar {s['duvar_ms']:.2f} ms ama "
                  f"CPU {s['cpu_ms']:.2f} ms ({s['paralellik']:.1f}×)")
        print("\n  ⭐ 20 kameralı bir sistemde kısıt CPU zamanıdır,")
        print("  duvar saati değil. Eski ölçümler bunu görmüyordu.")
    else:
        print("✅ Hiçbir aşama belirgin biçimde çok iş parçacıklı değil;")
        print("   duvar saati ölçümleri bu aşamalar için geçerli.")

    # 20 kamera bütçesi
    print("\n═══ 20 KAMERA × 2.9 FPS = 58 kare/sn BÜTÇESİ ═══")
    kare_sn = 58.0
    print(f"{'aşama':<14} {'CPU ms/sn':>12} {'çekirdek':>10}")
    toplam_cek = 0.0
    for s in sonuc:
        # ⚠ Decode ALIM hızında koşuyor (3.7 FPS/kam), analiz hızında
        # değil — kareler hareket filtresinden ÖNCE çözülüyor.
        ms_sn = (
            s["cpu_ms"] * 3.7 * 20 if s["asama"] == "decode_cpu"
            else s["cpu_ms"] * kare_sn
        )
        cek = ms_sn / 1000
        toplam_cek += cek
        print(f"{s['asama']:<14} {ms_sn:>12.0f} {cek:>10.2f}")
    print(f"{'TOPLAM':<14} {'':>12} {toplam_cek:>10.2f} çekirdek")
    print(f"\nmakinede {psutil.cpu_count()} çekirdek var → "
          f"doluluk ~%{toplam_cek / psutil.cpu_count() * 100:.0f}")

    BENCHMARKS.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = BENCHMARKS / f"yeniden_olcum_{damga}.json"
    hedef.write_text(json.dumps({
        "olculdu": datetime.now(UTC).isoformat(),
        "yontem": "duvar saati + CPU zamanı (psutil.cpu_times farkı)",
        "cekirdek": psutil.cpu_count(),
        "omp_num_threads": _os.environ.get("OMP_NUM_THREADS"),
        "kamera": args.kamera, "imgsz": args.imgsz,
        "tespit_sayisi": len(tespitler),
        "asamalar": sonuc,
        "eski_iddialar": ESKI,
        "yirmi_kamera_cekirdek": round(toplam_cek, 2),
        "uyari": (
            "Kod ve kütüphaneler eski ölçümlerden bu yana değişti; bu "
            "sayılar 'eski sayı yanlıştı' demez, yalnızca bugünün "
            "doğru yöntemle ölçülmüş hâlidir."
        ),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
