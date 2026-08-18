"""KADEME 2b ölçümü — yüz tespiti + ifade sınıflandırma.

Neden bu betik var
------------------
Gün 13'te KADEME 2b ölçülmüş ve `benchmarks/expression_20260817-gun13.json`
yazılmıştı — ama **ölçümü üreten betik commit edilmemişti.** Diğer dört
kademede (`benchmark_decode`, `motion_gate`, `pose`, `tracker`) betik
var, bunda yoktu. Yani sayı vardı, tekrar üretilemiyordu.

Ayrıca o ölçümdeki **"CPU'da ~58 ms/yüz" rakamı yanlış çıktı.** Bu betik
ölçümü yeniden yapıyor ve sapmanın sebebini de kaydediyor.

Cevaplanan üç soru
------------------
1. **Model ne kadar sürüyor?** CPU vs CUDA, batch ölçeklenmesiyle.
   (Gün 13'ün "58 ms" iddiası burada doğrulanıyor ya da çürütülüyor.)

2. **Kamera çiftliği bu kademeyi besliyor mu?** Gerçek karelerden kişi
   boyu dağılımı ve yüz tespiti isabet oranı.

3. ⭐ **Gün 8'in 640 küçültmesi 2b'ye ne kadar zarar veriyor?**
   Boru hattı artık ham 1280×720 saklamıyor; kırpıntılar 640×640
   letterbox'tan alınıyor, yani yüzler kaynağa göre YARI boyutta.
   Aynı kareler her iki uzayda da ölçülüp karşılaştırılıyor. Bu soru
   şimdiye kadar hiç sayıya bağlanmamıştı.

Kullanım
--------
    uv run python scripts/benchmark_expression.py
    uv run python scripts/benchmark_expression.py --frames 60 --cameras cam-17 cam-19
    uv run python scripts/benchmark_expression.py --no-model-bench   (sadece girdi analizi)
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import av
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

# ⚠ Windows konsolu Türkçe yerelde cp1254 kullanıyor ve "→", "⭐" gibi
# karakterleri basamıyor — `UnicodeEncodeError` ile betiği ÖLDÜRÜYOR.
# Ölçüm bittikten sonra sırf yazdırma yüzünden sonuç kaybetmek anlamsız.
# `errors="replace"`: kodlanamayan karakter betiği düşürmek yerine "?"
# olarak basılır. JSON çıktısı zaten ayrıca UTF-8 yazılıyor.
for _akis in (sys.stdout, sys.stderr):
    if hasattr(_akis, "reconfigure"):
        _akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from sentinel.config import settings  # noqa: E402
from sentinel.core.preprocess import letterbox  # noqa: E402
from sentinel.inference.detector.base import Detection  # noqa: E402
from sentinel.inference.emotion.base import face_quality  # noqa: E402
from sentinel.inference.emotion.yunet import (  # noqa: E402
    EmotiEffExpressionClassifier,
    YuNetFaceDetector,
)
from sentinel.inference.worker import build_detector  # noqa: E402

# Yüz ≈ gövde boyu / 8 (antropometrik kaba kural, Gün 13'te de kullanıldı)
FACE_RATIO = 8.0


# ══════════════════════════════════════════════════════════════
#  1. MODEL MALİYETİ
# ══════════════════════════════════════════════════════════════


def olc_model(tekrar: int = 15) -> dict[str, object]:
    """İfade modelinin cihaz ve batch'e göre maliyeti.

    ⚠ ISINMA AYRI TUTULUYOR (P-28)
    Isınma karesi sayılmazsa ilk çağrının CUDA bağlam kurulumu ve
    çekirdek derlemesi ortalamayı kalıcı olarak yukarı çeker. Gün 13'ün
    "58 ms" rakamının muhtemel sebebi tam olarak bu.
    """
    sonuc: dict[str, object] = {}
    goruntuler = [
        np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8) for _ in range(8)
    ]

    for cihaz in ("cuda", "cpu"):
        try:
            sinif = EmotiEffExpressionClassifier(
                model_name=settings.expression_model_name, device=cihaz
            )
        except Exception as exc:
            sonuc[cihaz] = {"hata": f"{type(exc).__name__}: {exc}"}
            continue

        # Isınma — ÖLÇÜME DAHİL DEĞİL
        t_isinma = time.perf_counter()
        sinif.classify(goruntuler[:1])
        sinif.classify(goruntuler)
        isinma_ms = (time.perf_counter() - t_isinma) * 1000.0

        olcumler: dict[str, float] = {}
        for n in (1, 2, 4, 8):
            sureler = []
            for _ in range(tekrar):
                t0 = time.perf_counter()
                sinif.classify(goruntuler[:n])
                sureler.append((time.perf_counter() - t0) * 1000.0)
            olcumler[f"batch_{n}"] = round(statistics.median(sureler), 2)

        sinif.close()
        yuz_basina = olcumler["batch_8"] / 8
        sonuc[cihaz] = {
            "isinma_ms": round(isinma_ms, 1),
            "toplam_ms": olcumler,
            "yuz_basina_ms_batch8": round(yuz_basina, 2),
            # Toplu çağrı gerçekten yapılıyor mu? Doğrusalsa YAPILMIYOR.
            "olcek_dogrusal_mi": round(olcumler["batch_8"] / olcumler["batch_1"], 2),
        }

    return sonuc


def olc_yuz_tespiti(kirpintilar: list[np.ndarray], tekrar: int = 5) -> dict[str, float]:
    """YuNet'in kırpıntı başına maliyeti."""
    if not kirpintilar:
        return {}
    dedektor = YuNetFaceDetector(str(settings.face_detector_weights))
    for k in kirpintilar[:5]:  # ısınma
        dedektor.detect(k)

    sureler = []
    for _ in range(tekrar):
        t0 = time.perf_counter()
        for k in kirpintilar:
            dedektor.detect(k)
        sureler.append((time.perf_counter() - t0) / len(kirpintilar) * 1000.0)
    dedektor.close()
    return {"kirpinti_basina_ms": round(statistics.median(sureler), 3)}


# ══════════════════════════════════════════════════════════════
#  2. GİRDİ ANALİZİ — kamera çiftliği bu kademeyi besliyor mu?
# ══════════════════════════════════════════════════════════════


@dataclass
class UzayIstatistigi:
    """Tek bir görüntü uzayında (kaynak ya da 640) toplanan sayılar."""

    ad: str
    kisi_boylari: list[float] = field(default_factory=list)
    yuz_bulunan: int = 0
    yuz_aranan: int = 0
    yuz_boyutlari: list[float] = field(default_factory=list)
    kaliteler: list[float] = field(default_factory=list)

    def ozet(self) -> dict[str, object]:
        boylar = sorted(self.kisi_boylari)
        yuzler = sorted(self.yuz_boyutlari)

        def p(veri: list[float], yuzde: float) -> float:
            if not veri:
                return 0.0
            return round(veri[min(len(veri) - 1, int(len(veri) * yuzde))], 1)

        return {
            "kisi_sayisi": len(boylar),
            "kisi_boyu_px": {
                "p50": p(boylar, 0.50),
                "p90": p(boylar, 0.90),
                "azami": round(boylar[-1], 1) if boylar else 0.0,
            },
            "tahmini_yuz_px_p50": round(p(boylar, 0.50) / FACE_RATIO, 1),
            "esik_ustu_kisi_yuzdesi": round(
                100.0
                * sum(1 for b in boylar if b >= settings.expression_min_person_px)
                / max(1, len(boylar)),
                1,
            ),
            "yuz_aranan": self.yuz_aranan,
            "yuz_bulunan": self.yuz_bulunan,
            "yuz_isabet_yuzdesi": round(
                100.0 * self.yuz_bulunan / max(1, self.yuz_aranan), 1
            ),
            "bulunan_yuz_px_p50": p(yuzler, 0.50),
            "kalite_p50": round(statistics.median(self.kaliteler), 2)
            if self.kaliteler
            else 0.0,
            "kullanilabilir_yuz": sum(1 for k in self.kaliteler if k >= 0.5),
        }


def _kisi_kirp(kare: np.ndarray, d: Detection) -> np.ndarray | None:
    h, w = kare.shape[:2]
    x1, y1 = max(0, int(d.x1)), max(0, int(d.y1))
    x2, y2 = min(w, int(d.x2)), min(h, int(d.y2))
    if x2 - x1 < 16 or y2 - y1 < 16:
        return None
    return kare[y1:y2, x1:x2]


def analiz_et(
    kameralar: list[str],
    kare_sayisi: int,
    dedektor: object,
) -> tuple[UzayIstatistigi, UzayIstatistigi, list[np.ndarray]]:
    """Aynı kareleri İKİ uzayda birden analiz eder.

    ⭐ Betiğin asıl katkısı burası. Boru hattı 640×640 letterbox
    kullanıyor; kaynak 1280×720. Aynı kişi, aynı an, iki farklı
    çözünürlük — tek değişen ölçek. Kontrollü karşılaştırma (P-27
    deseni).
    """
    kaynak = UzayIstatistigi("kaynak_1280x720")
    model = UzayIstatistigi("model_640x640")
    ornek_kirpintilar: list[np.ndarray] = []

    yuz_dedektoru = YuNetFaceDetector(str(settings.face_detector_weights))

    for kamera in kameralar:
        yol = PROJECT_ROOT / "data" / "videos" / f"{kamera}.mp4"
        if not yol.is_file():
            print(f"  ⚠ {kamera}: video yok, atlanıyor")
            continue

        kap = av.open(str(yol))
        akis = kap.streams.video[0]
        alinan = 0

        for i, kare in enumerate(kap.decode(akis)):
            if alinan >= kare_sayisi:
                break
            if i % 25:  # saniyede bir kare — çeşitlilik için
                continue
            alinan += 1

            ham = kare.to_ndarray(format="bgr24")
            kucuk, _kutu = letterbox(ham)

            for uzay, goruntu in ((kaynak, ham), (model, kucuk)):
                tespitler = dedektor.detect([goruntu])[0]  # type: ignore[attr-defined]
                for d in tespitler:
                    uzay.kisi_boylari.append(d.height)
                    if d.height < settings.expression_min_person_px:
                        continue

                    kirpinti = _kisi_kirp(goruntu, d)
                    if kirpinti is None:
                        continue
                    uzay.yuz_aranan += 1
                    if len(ornek_kirpintilar) < 40:
                        ornek_kirpintilar.append(kirpinti)

                    yuz = yuz_dedektoru.detect(kirpinti)
                    if yuz is None:
                        continue
                    uzay.yuz_bulunan += 1
                    uzay.yuz_boyutlari.append(min(yuz.width, yuz.height))

                    ky1, ky2 = max(0, int(yuz.y1)), int(yuz.y2)
                    kx1, kx2 = max(0, int(yuz.x1)), int(yuz.x2)
                    yuz_kirpinti = kirpinti[ky1:ky2, kx1:kx2]
                    if yuz_kirpinti.size:
                        uzay.kaliteler.append(face_quality(yuz_kirpinti, yuz))

        kap.close()

    yuz_dedektoru.close()
    return kaynak, model, ornek_kirpintilar


# ══════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════


def main() -> int:
    ap = argparse.ArgumentParser(description="KADEME 2b ölçümü")
    ap.add_argument(
        "--cameras",
        nargs="*",
        # Gün 13 kamera dağılımı: 17-18 boş sahne, 19-20 yakın plan yüz.
        # Yüz içeren kameralar + bir kalabalık sahne.
        default=["cam-17", "cam-19", "cam-20", "cam-09"],
    )
    ap.add_argument("--frames", type=int, default=25, help="Kamera başına kare")
    ap.add_argument("--no-model-bench", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    print("KADEME 2b ÖLÇÜMÜ")
    print("=" * 62)

    rapor: dict[str, object] = {
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "phase": "Faz 1 / Gün 14",
        "description": "KADEME 2b yeniden ölçüm — Gün 13'ün '58 ms/yüz' rakamı doğrulanıyor",
        "cameras": args.cameras,
        "frames_per_camera": args.frames,
    }

    # ── 1. Model maliyeti ────────────────────────────────────
    if not args.no_model_bench:
        print("\n[1/3] İfade modeli maliyeti (cihaz × batch)...")
        model_olcum = olc_model()
        rapor["expression_model"] = model_olcum
        for cihaz, veri in model_olcum.items():
            if "hata" in veri:  # type: ignore[operator]
                print(f"  {cihaz:5} HATA: {veri['hata']}")  # type: ignore[index]
                continue
            v = veri  # type: ignore[assignment]
            print(
                f"  {cihaz:5} yüz başına {v['yuz_basina_ms_batch8']:6.2f} ms"  # type: ignore[index]
                f"  ·  ölçek 1→8: {v['olcek_dogrusal_mi']}×"  # type: ignore[index]
                f"  ·  ısınma {v['isinma_ms']:.0f} ms"  # type: ignore[index]
            )

    # ── 2. Girdi analizi ─────────────────────────────────────
    print("\n[2/3] Girdi analizi — kamera çiftliği bu kademeyi besliyor mu?")
    dedektor = build_detector(
        str(settings.detector_weights),
        backend=settings.detector_backend,
        device="cuda:0",
        half=True,
        imgsz=640,
        conf=settings.detector_conf_threshold,
    )
    dedektor.warmup(1)

    kaynak, model_uzayi, kirpintilar = analiz_et(args.cameras, args.frames, dedektor)
    dedektor.close()

    rapor["input_analysis"] = {
        "kaynak_uzayi": kaynak.ozet(),
        "model_uzayi_640": model_uzayi.ozet(),
    }

    for uzay in (kaynak, model_uzayi):
        o = uzay.ozet()
        print(f"\n  {uzay.ad}")
        print(
            f"    kişi boyu p50 {o['kisi_boyu_px']['p50']:>6} px"  # type: ignore[index]
            f"  ·  tahmini yüz {o['tahmini_yuz_px_p50']:>5} px"
            f"  ·  eşik üstü %{o['esik_ustu_kisi_yuzdesi']}"
        )
        print(
            f"    yüz arandı {o['yuz_aranan']:>4}"
            f"  ·  bulundu {o['yuz_bulunan']:>4}"
            f"  (%{o['yuz_isabet_yuzdesi']})"
            f"  ·  kullanılabilir {o['kullanilabilir_yuz']}"
        )

    # ── 3. Yüz tespiti maliyeti ──────────────────────────────
    print("\n[3/3] YuNet maliyeti...")
    rapor["face_detection"] = olc_yuz_tespiti(kirpintilar)
    if rapor["face_detection"]:
        print(f"  kırpıntı başına {rapor['face_detection']['kirpinti_basina_ms']} ms")  # type: ignore[index]

    # ── Karşılaştırma ────────────────────────────────────────
    k, m = kaynak.ozet(), model_uzayi.ozet()
    rapor["gun8_kucultmesinin_bedeli"] = {
        "soru": "Ön işlemenin alım katmanına taşınması (640×640) KADEME 2b'yi ne kadar zayıflattı?",
        "kaynak_yuz_isabet": k["yuz_isabet_yuzdesi"],
        "model_640_yuz_isabet": m["yuz_isabet_yuzdesi"],
        "kaynak_kullanilabilir_yuz": k["kullanilabilir_yuz"],
        "model_640_kullanilabilir_yuz": m["kullanilabilir_yuz"],
    }

    print("\n" + "=" * 62)
    print("⭐ GÜN 8 KÜÇÜLTMESİNİN KADEME 2b'YE BEDELİ")
    print(
        f"  yüz isabet oranı : kaynak %{k['yuz_isabet_yuzdesi']}"
        f"  →  640 uzayı %{m['yuz_isabet_yuzdesi']}"
    )
    print(
        f"  kullanılabilir   : kaynak {k['kullanilabilir_yuz']}"
        f"  →  640 uzayı {m['kullanilabilir_yuz']}"
    )

    # ── Kaydet ───────────────────────────────────────────────
    cikti = args.out or (
        PROJECT_ROOT / "benchmarks" / f"expression_{datetime.now():%Y%m%d}-gun14.json"
    )
    cikti = cikti.resolve()
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    # `--out` göreli verilmiş olabilir; proje kökü dışındaysa mutlak yaz.
    try:
        gosterilecek = cikti.relative_to(PROJECT_ROOT)
    except ValueError:
        gosterilecek = cikti
    print(f"\nKaydedildi: {gosterilecek}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
