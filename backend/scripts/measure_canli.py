"""CANLI DOĞRULAMA — model üretimde gerçekten konuşuyor mu? (P-56)

⭐ NEDEN BU BETİK
----------------
Hakem denetimi iki ölümcül bulgu çıkardı:

  §1.1  Hiçbir öğrenilmiş model canlı boru hattında değildi
  §1.2  Saldırganlık sinyali (füzyon ağırlığı 0.40) HİÇ ateşlemiyordu
        — K7 koşusundaki 39 alarmın sıfırı saldırganlıktandı

Model artık entegre (`analytics/model.py`). Ama **entegre etmek
çalıştığını göstermez.** Bu, projede defalarca yakalanan hatanın ta
kendisi olurdu:

    P-43  ifade sınıflandırılıyordu, karara HİÇ ulaşmıyordu
    P-44  `buda()` yazılmıştı, hiç ÇAĞRILMIYORDU
    P-45  klipler kesiliyordu, kimse GÖREMİYORDU

> ⭐ *"Her parçası tek tek çalışan bir sistem uçtan uca çalışmayabilir
> ve parça testleri bunu asla göstermez."* (CLAUDE.md · ikinci tez)

Bu betik uçtan uca soruyor: **model canlıda skor üretiyor mu, o skor
alarma dönüşüyor mu, ve bunun bedeli ne?**

NE ÖLÇÜLÜYOR
------------
1. **Model canlı mı** — `sentinel_aggression_model_score` gauge'ı
   kaç kamerada sıfırdan farklı? Hep 0 ise model yüklü ama besleme
   kopuk demektir.
2. **Alarm türü kırılımı** — `aggression` türü ARTIK görünüyor mu?
3. **Gecikme** — p50/p95. Referans: K4'te p50 205 ms · p95 463 ms.
   Model kare başına ek maliyet getiriyor; bedeli görünmeli.
4. **Analiz hızı** — kamera başına FPS. Referans: 2.75.
5. **Kaynak** — süreç başına CPU/RAM (psutil) + GPU kullanımı/VRAM.

⚠ ÖLÇÜM KOŞULU
--------------
Boru hattı AYAKTA, panel KAPALI (P-24: panel açıkken verim yarıya
düşüyor), ölçüm sırasında sisteme DOKUNULMAZ (P-36).

⚠ İlk `--isinma` saniyesi atılıyor (P-28): profiller ısınmadan
üretilen sayı ölçüm değil.

Kullanım:
    uv run python scripts/measure_canli.py --sure 600
    uv run python scripts/measure_canli.py --sure 300 --aralik 15
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = PROJECT_ROOT / "benchmarks"

# worker → metrik portu (CLAUDE.md §5 · Servis portları)
PORTLAR = {
    "alim": 9101,
    "cikarim": 9110,
    "analitik": 9120,
    "alarm": 9130,
}
KAMERA_SAYISI = 20

# K4'te ölçülen referanslar — model ENTEGRE EDİLMEDEN önce.
# ⚠ Karşılaştırma zemini: aynı donanım, aynı kamera sayısı, panel kapalı.
REFERANS = {
    "gecikme_p50_ms": 205.0,
    "gecikme_p95_ms": 463.0,
    "analiz_fps": 2.75,
    "ornekleme_fps": 3.64,
}


def _kazi(port: int, zaman_asimi: float = 4.0) -> str | None:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/metrics", timeout=zaman_asimi,
        ) as yanit:
            return yanit.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def _ayristir(metin: str) -> list[tuple[str, dict[str, str], float]]:
    """Prometheus metin formatını (ad, etiketler, değer) üçlülerine çevirir."""
    cikti: list[tuple[str, dict[str, str], float]] = []
    for satir in metin.splitlines():
        if not satir or satir.startswith("#"):
            continue
        try:
            sol, deger = satir.rsplit(" ", 1)
            v = float(deger)
        except ValueError:
            continue
        if "{" in sol:
            ad, kalan = sol.split("{", 1)
            etiketler = {}
            for parca in kalan.rstrip("}").split(","):
                if "=" in parca:
                    k, d = parca.split("=", 1)
                    etiketler[k.strip()] = d.strip().strip('"')
            cikti.append((ad.strip(), etiketler, v))
        else:
            cikti.append((sol.strip(), {}, v))
    return cikti


def _sec(
    olcumler: list[tuple[str, dict[str, str], float]], ad: str,
) -> list[tuple[dict[str, str], float]]:
    return [(e, v) for a, e, v in olcumler if a == ad]


def _kovalar(
    olcumler: list[tuple[str, dict[str, str], float]], ad: str,
) -> dict[float, float]:
    kovalar: dict[float, float] = {}
    for etiketler, deger in _sec(olcumler, f"{ad}_bucket"):
        le = etiketler.get("le")
        if le is None:
            continue
        try:
            kovalar[float("inf") if le == "+Inf" else float(le)] = deger
        except ValueError:
            continue
    return kovalar


def _yuzdelik(kovalar: dict[float, float], oran: float) -> float | None:
    """Kümülatif histogramdan yüzdelik — ARA DEĞERLEME, kesin değil.

    ⚠ Histogram ham değerleri saklamıyor; kova sınırları arasında
    doğrusal ara değerleme yapılıyor. Sonuç bir TAHMİN ve raporda
    böyle yazılmalı (measure_k4.py ile aynı yöntem, aynı uyarı).
    """
    if not kovalar:
        return None
    sirali = sorted(kovalar.items())
    toplam = sirali[-1][1]
    if toplam <= 0:
        return None
    hedef = toplam * oran
    onceki_sinir, onceki_sayac = 0.0, 0.0
    for sinir, sayac in sirali:
        if sayac >= hedef:
            if sinir == float("inf"):
                return onceki_sinir
            pay = (hedef - onceki_sayac) / max(sayac - onceki_sayac, 1e-9)
            return onceki_sinir + pay * (sinir - onceki_sinir)
        onceki_sinir, onceki_sayac = sinir, sayac
    return sirali[-1][0]


def _kaynak() -> dict[str, Any]:
    """Süreç başına CPU/RAM ve GPU kullanımı."""
    cikti: dict[str, Any] = {"surecler": [], "toplam_ram_mb": 0.0,
                             "toplam_cpu": 0.0}
    try:
        import psutil
    except ImportError:
        cikti["not"] = "psutil kurulu değil — CPU/RAM ölçülemedi"
        return cikti

    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or [])
            if "sentinel." not in cmd:
                continue
            # ⚠ `uv run` iki süreç üretir (sarmalayıcı + asıl);
            # sarmalayıcının RAM'i asılınkine dâhil değil ve
            # ikisini toplamak çift saymak olmaz (CLAUDE.md tuzaklar).
            for anahtar, etiket in (
                ("ingest.worker", "alim"),
                ("inference.worker", "cikarim"),
                ("analytics.worker", "analitik"),
                ("alerting.worker", "alarm"),
                ("api.main", "api"),
            ):
                if anahtar in cmd:
                    with p.oneshot():
                        ram = p.memory_info().rss / 1024 / 1024
                        cpu = p.cpu_percent(interval=None)
                    cikti["surecler"].append(
                        {"rol": etiket, "pid": p.info["pid"],
                         "ram_mb": round(ram, 1), "cpu_yuzde": round(cpu, 1)}
                    )
                    cikti["toplam_ram_mb"] += ram
                    cikti["toplam_cpu"] += cpu
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    cikti["toplam_ram_mb"] = round(cikti["toplam_ram_mb"], 1)
    cikti["toplam_cpu"] = round(cikti["toplam_cpu"], 1)
    cikti["sistem_ram_yuzde"] = psutil.virtual_memory().percent
    return cikti


def _gpu() -> dict[str, Any]:
    try:
        import torch

        if not torch.cuda.is_available():
            return {"not": "CUDA yok"}
        return {
            "ad": torch.cuda.get_device_name(0),
            "toplam_vram_mb": round(
                torch.cuda.get_device_properties(0).total_memory / 1024 / 1024, 0
            ),
        }
    except Exception as hata:
        return {"not": f"okunamadı: {hata}"}


def _ornek_al() -> dict[str, Any]:
    veri: dict[str, Any] = {"ts": time.time()}
    for rol, port in PORTLAR.items():
        metin = _kazi(port)
        if metin is None:
            veri[f"{rol}_ayakta"] = False
            continue
        veri[f"{rol}_ayakta"] = True
        o = _ayristir(metin)

        if rol == "analitik":
            # ⭐ MODEL CANLI MI — asıl soru bu.
            skorlar = _sec(o, "sentinel_aggression_model_score")
            veri["model_skorlari"] = {
                e.get("cam", "?"): v for e, v in skorlar
            }
            veri["risk_skorlari"] = {
                e.get("cam", "?"): v
                for e, v in _sec(o, "sentinel_risk_score")
            }
            # ⚠⚠ ALARM SAYACI ANALİTİK WORKER'DA, ALARM WORKER'DA DEĞİL.
            # İlk sürüm `sentinel_events_written_total`ı 9130'dan
            # kazıyordu ve HİÇBİR ŞEY BULAMIYORDU — "alarm yok" diye
            # rapor ediyordu. Oysa alarm worker'ı yalnızca
            # `sentinel_worker_up` yayınlıyor; anomaliler analitikte
            # sayılıyor.
            #
            # ⭐ Bu, ölçüm aracının sessizce yanlış yere bakmasının bir
            # örneği daha (P-40: panel kare yerine kişi sayıyordu).
            # "Sonuç yok" ile "yanlış yere baktım" aynı görünür.
            turler: dict[str, float] = {}
            for e, v in _sec(o, "sentinel_anomalies_total"):
                turler[e.get("type", "?")] = turler.get(e.get("type", "?"), 0.0) + v
            veri["alarm_turleri"] = turler

        if rol == "cikarim":
            k = _kovalar(o, "sentinel_end_to_end_latency_seconds")
            veri["gecikme_p50_ms"] = (
                (_yuzdelik(k, 0.50) or 0) * 1000 if k else None
            )
            veri["gecikme_p95_ms"] = (
                (_yuzdelik(k, 0.95) or 0) * 1000 if k else None
            )
            sayac = _sec(o, "sentinel_end_to_end_latency_seconds_count")
            veri["analiz_kare"] = sum(v for _e, v in sayac)
        if rol == "alim":
            veri["kare_yayinlandi"] = sum(
                v for _e, v in _sec(o, "sentinel_frames_published_total")
            )
            veri["kare_atildi"] = {
                e.get("reason", "?"): v
                for e, v in _sec(o, "sentinel_frames_dropped_total")
            }
    return veri


def main() -> int:
    ap = argparse.ArgumentParser(description="Canlı doğrulama (P-56)")
    ap.add_argument("--sure", type=int, default=600, help="ölçüm süresi (sn)")
    ap.add_argument("--aralik", type=int, default=15, help="örnekleme (sn)")
    ap.add_argument("--isinma", type=int, default=90,
                    help="atılacak ilk saniye (P-28)")
    args = ap.parse_args()

    ilk = _ornek_al()
    ayakta = [r for r in PORTLAR if ilk.get(f"{r}_ayakta")]
    if len(ayakta) < len(PORTLAR):
        eksik = set(PORTLAR) - set(ayakta)
        print(f"❌ Ayakta olmayan worker: {', '.join(sorted(eksik))}",
              file=sys.stderr)
        print("   pwsh backend/scripts/start_all.ps1", file=sys.stderr)
        return 1

    gpu = _gpu()
    print(f"GPU: {gpu.get('ad', '?')} · {gpu.get('toplam_vram_mb', '?')} MB")
    print(f"Ölçüm: {args.sure} sn · örnek {args.aralik} sn · "
          f"ısınma {args.isinma} sn atılıyor\n")

    ornekler: list[dict[str, Any]] = []
    kaynaklar: list[dict[str, Any]] = []
    t0 = time.time()
    while time.time() - t0 < args.sure:
        o = _ornek_al()
        gecen = o["ts"] - t0
        if gecen >= args.isinma:
            ornekler.append(o)
            kaynaklar.append(_kaynak())
        canli = sum(1 for v in (o.get("model_skorlari") or {}).values() if v > 0)
        print(f"  {gecen:5.0f} sn · model skoru>0 olan kamera: {canli:2d}/"
              f"{KAMERA_SAYISI} · gecikme p95 "
              f"{o.get('gecikme_p95_ms') or 0:.0f} ms", flush=True)
        time.sleep(args.aralik)

    if not ornekler:
        print("❌ Isınmadan sonra örnek yok — süreyi artırın.", file=sys.stderr)
        return 1

    son = ornekler[-1]
    ilk_o = ornekler[0]
    sure = son["ts"] - ilk_o["ts"]

    # ─── ⭐ MODEL CANLI MI ───
    print("\n═══ ⭐ MODEL CANLIDA KONUŞUYOR MU ═══")
    tum_skorlar = [
        v for o in ornekler for v in (o.get("model_skorlari") or {}).values()
    ]
    kameralar = set()
    for o in ornekler:
        kameralar |= {k for k, v in (o.get("model_skorlari") or {}).items() if v > 0}
    if not tum_skorlar:
        print("❌ `sentinel_aggression_model_score` metriği HİÇ görülmedi.")
        print("   Model yüklenmemiş ya da besleme kopuk.")
    else:
        s = sorted(tum_skorlar)
        print(f"  örnek           : {len(s)}")
        print(f"  skor>0 kamera   : {len(kameralar)}/{KAMERA_SAYISI}")
        print(f"  medyan          : {statistics.median(s):.4f}")
        print(f"  p90             : {s[min(len(s) - 1, int(len(s) * 0.9))]:.4f}")
        print(f"  azami           : {s[-1]:.4f}")
        if s[-1] <= 1e-9:
            print("  ❌ TÜM SKORLAR SIFIR — model yüklü ama besleme kopuk.")
        elif len(kameralar) < 3:
            print("  ⚠ Çok az kamerada skor var; besleme kısmi olabilir.")
        else:
            print("  ✅ Model canlıda skor üretiyor.")

    # ─── Alarm türleri ───
    print("\n═══ ALARM TÜRLERİ (kümülatif) ═══")
    turler = son.get("alarm_turleri") or {}
    if not turler:
        print("  (alarm yok ya da metrik boş)")
    for tur, sayi in sorted(turler.items(), key=lambda kv: -kv[1]):
        isaret = "  ⬅ ⭐ ARTIK ATEŞLİYOR" if tur == "aggression" and sayi else ""
        print(f"  {tur:<14} {sayi:>6.0f}{isaret}")
    if "aggression" not in turler or not turler.get("aggression"):
        print("  ⚠ `aggression` alarmı YOK — model skor üretse bile füzyon")
        print("    eşiğini aşmıyor olabilir. Bu ayrı bir bulgu.")

    # ─── Gecikme ve verim ───
    print("\n═══ GECİKME VE VERİM (referans: model ENTEGRE DEĞİLKEN) ═══")
    print(f"{'ölçüt':<22} {'şimdi':>10} {'referans':>10} {'fark':>10}")
    p50 = [o["gecikme_p50_ms"] for o in ornekler if o.get("gecikme_p50_ms")]
    p95 = [o["gecikme_p95_ms"] for o in ornekler if o.get("gecikme_p95_ms")]
    kare_farki = (son.get("analiz_kare") or 0) - (ilk_o.get("analiz_kare") or 0)
    analiz_fps = kare_farki / max(sure, 1e-9) / KAMERA_SAYISI
    yayin_farki = (son.get("kare_yayinlandi") or 0) - (
        ilk_o.get("kare_yayinlandi") or 0)
    ornekleme_fps = yayin_farki / max(sure, 1e-9) / KAMERA_SAYISI

    satirlar = [
        ("gecikme p50 (ms)", statistics.median(p50) if p50 else 0,
         REFERANS["gecikme_p50_ms"]),
        ("gecikme p95 (ms)", statistics.median(p95) if p95 else 0,
         REFERANS["gecikme_p95_ms"]),
        ("analiz FPS/kamera", analiz_fps, REFERANS["analiz_fps"]),
        ("örnekleme FPS/kam", ornekleme_fps, REFERANS["ornekleme_fps"]),
    ]
    for ad, simdi, ref in satirlar:
        fark = simdi - ref
        print(f"{ad:<22} {simdi:>10.2f} {ref:>10.2f} {fark:>+10.2f}")

    # ─── Kaynak ───
    print("\n═══ KAYNAK KULLANIMI ═══")
    if kaynaklar and kaynaklar[-1].get("surecler"):
        print(f"{'rol':<12} {'RAM (MB)':>10} {'CPU %':>8}")
        # Süreç başına medyan — anlık değer dalgalanıyor.
        roller: dict[str, list[tuple[float, float]]] = {}
        for k in kaynaklar:
            for s_ in k["surecler"]:
                roller.setdefault(s_["rol"], []).append(
                    (s_["ram_mb"], s_["cpu_yuzde"]))
        for rol, degerler in sorted(roller.items()):
            ram = statistics.median(d[0] for d in degerler)
            cpu = statistics.median(d[1] for d in degerler)
            print(f"{rol:<12} {ram:>10.1f} {cpu:>8.1f}")
        print(f"{'TOPLAM':<12} "
              f"{statistics.median(k['toplam_ram_mb'] for k in kaynaklar):>10.1f} "
              f"{statistics.median(k['toplam_cpu'] for k in kaynaklar):>8.1f}")
        print(f"\nsistem RAM: %"
              f"{statistics.median(k.get('sistem_ram_yuzde', 0) for k in kaynaklar):.0f}")
    else:
        print("  ⚠ psutil yok ya da süreç bulunamadı")

    atilan = son.get("kare_atildi") or {}
    if atilan:
        print("\n═══ ATILAN KARELER (kümülatif) ═══")
        for sebep, sayi in sorted(atilan.items(), key=lambda kv: -kv[1]):
            print(f"  {sebep:<14} {sayi:>10.0f}")

    BENCHMARKS.mkdir(exist_ok=True)
    damga = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    hedef = BENCHMARKS / f"canli_dogrulama_{damga}.json"
    hedef.write_text(json.dumps({
        "olculdu": datetime.now(UTC).isoformat(),
        "sure_s": round(sure, 1), "ornek": len(ornekler),
        "isinma_s": args.isinma,
        "gpu": gpu,
        "referans": REFERANS,
        "model": {
            "skor_ureten_kamera": len(kameralar),
            "medyan": round(statistics.median(tum_skorlar), 4) if tum_skorlar else None,
            "azami": round(max(tum_skorlar), 4) if tum_skorlar else None,
        },
        "alarm_turleri": turler,
        "gecikme": {
            "p50_ms": round(statistics.median(p50), 1) if p50 else None,
            "p95_ms": round(statistics.median(p95), 1) if p95 else None,
            "yontem": "histogram kova ara değerlemesi — kesin değer değil",
        },
        "verim": {"analiz_fps": round(analiz_fps, 3),
                  "ornekleme_fps": round(ornekleme_fps, 3)},
        "kaynak": kaynaklar[-1] if kaynaklar else {},
        "atilan_kare": atilan,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
