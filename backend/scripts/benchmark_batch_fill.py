"""Parti doldurmanın gerçek etkisi — DÖNÜŞÜMLÜ A/B.

Neden bu betik
--------------
`XREADGROUP ... BLOCK` eldeki **ilk** kareyle dönüyor, `COUNT` kadar
birikmesini beklemiyor. Çıkarım worker'ı üretimden hızlı olduğu için
sürekli yarım parti alıyor: ölçülen ortalama 5.52 kare/parti, partilerin
yalnızca %47'si 7-8 aralığında.

`--batch-fill-ms` bunu düzeltmeyi deniyor: parti hedefe ulaşana ya da
süre dolana kadar kare topluyor. Bedeli gecikme, kazancı verim.

⚠ NEDEN "ÖNCE KAPALI ÖLÇ, SONRA AÇIK ÖLÇ" YETMİYOR
--------------------------------------------------
İlk denemede tam bunu yaptım ve sonuç **+%32 verim** çıktı. Sayı fazla
iyiydi ve iki ölçüm arka arkaya alınmıştı — yani aradaki fark ayardan
da gelebilir, GPU sıcaklığından da, o sırada videolarda olan bitenden
de, ısınmanın kalıntısından da.

Bu tuzağa bu projede bir kez düşüldü: Gün 8'de sıralı koşuyla ölçülen
bir kazanç **%-34** çıktı, dönüşümlü ölçülünce **%+43** oldu
(`problems.md` P-17). Aynı hatayı ikinci kez yapmamak için bu betik
ayarları **dönüşümlü** koşturuyor: A, B, A, B.

Eşleştirilmiş karşılaştırma, ortak yönlü sürüklenmeyi (termal kısıtlama,
disk önbelleğinin ısınması, videoların döngü fazı) iki tarafa da eşit
dağıtıyor.

⚠ GECİKME DE ÖLÇÜLÜYOR
----------------------
Parti doldurmak tanımı gereği bekleme ekliyor. "Verim arttı" tek başına
kabul kriteri değil: K3 uçtan uca gecikme için ≤1500 ms diyor. Verimi
gecikmeyi patlatarak almak kazanç değil takas — ve bu takasın kabul
edilip edilmeyeceği ölçülen sayıya bakılarak söylenir.

Kullanım
--------
    uv run python scripts/benchmark_batch_fill.py
    uv run python scripts/benchmark_batch_fill.py --degerler 0 40 80 --tur 2
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND = PROJECT_ROOT / "backend"
BENCHMARKS = PROJECT_ROOT / "benchmarks"
METRIK = "http://127.0.0.1:9110/metrics"

# ⚠ Tam yol: kısmi ad `PATH`e bağlıdır ve ölçüm betiği hangi kabuktan
# çağrıldığına göre farklı davranmamalı.
PWSH = R"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

# Histogram kovaları — worker'daki tanımla aynı olmalı
KOVA = ["1.0", "2.0", "4.0", "6.0", "8.0", "+Inf"]


def _metrikleri_al(zaman_asimi: float = 3.0) -> str:
    with urlopen(METRIK, timeout=zaman_asimi) as r:
        return r.read().decode("utf-8", "replace")


def _ayristir(metin: str) -> dict[str, float]:
    d: dict[str, float] = {}
    for satir in metin.splitlines():
        m = re.match(r'sentinel_batch_size_bucket\{le="([^"]+)"\} ([\d.eE+-]+)', satir)
        if m:
            d["kova_" + m.group(1)] = float(m.group(2))
        m = re.match(r"sentinel_batch_size_(count|sum) ([\d.eE+-]+)", satir)
        if m:
            d["parti_" + m.group(1)] = float(m.group(2))
        m = re.match(r"sentinel_end_to_end_latency_seconds_(count|sum) ([\d.eE+-]+)", satir)
        if m:
            d["gecikme_" + m.group(1)] = float(m.group(2))
        m = re.match(
            r'sentinel_end_to_end_latency_seconds_bucket\{le="([^"]+)"\} ([\d.eE+-]+)',
            satir,
        )
        if m:
            d["gkova_" + m.group(1)] = float(m.group(2))
    return d


def _worker_yeniden_baslat(fill_ms: int) -> None:
    """Çıkarım worker'ını verilen ayarla yeniden başlatır.

    ⚠ Yalnızca ÇIKARIM worker'ı yeniden başlıyor. Alım worker'ı
    paylaşımlı bellek havuzunun sahibi; onu kapatmak havuzu yok eder ve
    ölçüm sıfırlanır (`start_all.ps1` sıra notu).
    """
    # ⚠ S603/S607 bastırıldı: komut tamamen sabit, dışarıdan gelen tek
    # değer `fill_ms` ve o da `int` — kabuk enjeksiyonu yolu yok.
    # Bu bir ÖLÇÜM betiği, üretim yolu değil (mimari kural: shell'e
    # çıkmamak `PyAV` seçiminin gerekçesiydi; orada kullanıcı girdisi
    # vardı, burada yok).
    subprocess.run(  # noqa: S603
        [
            PWSH,
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
            "Where-Object { $_.CommandLine -like '*inference.worker*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }",
        ],
        check=False,
        capture_output=True,
    )
    time.sleep(4)
    subprocess.run(  # noqa: S603
        [
            PWSH,
            "-NoProfile",
            "-Command",
            "Start-Process -FilePath uv -ArgumentList "
            "'run','python','-m','sentinel.inference.worker',"
            f"'--batch-size','8','--batch-fill-ms','{fill_ms}',"
            "'--stats-interval','600' "
            f"-WorkingDirectory '{BACKEND}' -WindowStyle Hidden",
        ],
        check=False,
        capture_output=True,
    )


def _hazir_bekle(saniye: float = 120.0) -> bool:
    bitis = time.time() + saniye
    while time.time() < bitis:
        try:
            if "sentinel_batch_size_count" in _metrikleri_al():
                return True
        except (URLError, OSError, TimeoutError):
            pass
        time.sleep(3)
    return False


def _blok_olc(fill_ms: int, isinma: float, pencere: float) -> dict[str, float]:
    _worker_yeniden_baslat(fill_ms)
    if not _hazir_bekle():
        raise RuntimeError(f"worker açılmadı (fill={fill_ms})")
    # ⚠ P-28: ısınma ~90 sn sürüyor. Bu payı atmadan alınan her sayı
    # kötümser çıkar ve iki blok farklı kadar ısınmışsa kıyas bozulur.
    time.sleep(isinma)
    a = _ayristir(_metrikleri_al())
    time.sleep(pencere)
    b = _ayristir(_metrikleri_al())

    parti = b["parti_count"] - a["parti_count"]
    kare = b["parti_sum"] - a["parti_sum"]
    sonuc = {
        "fill_ms": float(fill_ms),
        "parti": parti,
        "kare": kare,
        "kare_per_parti": kare / parti if parti else 0.0,
        "verim_kare_sn": kare / pencere,
    }
    # Dolu parti oranı (7-8 kovası) — TensorRT'nin kazandığı bölge
    dolu = (b["kova_+Inf"] - a["kova_+Inf"]) - (b["kova_6.0"] - a["kova_6.0"])
    sonuc["dolu_parti_orani"] = dolu / parti if parti else 0.0
    # Gecikme ortalaması (histogram toplamı / sayısı)
    g_n = b.get("gecikme_count", 0) - a.get("gecikme_count", 0)
    g_s = b.get("gecikme_sum", 0) - a.get("gecikme_sum", 0)
    sonuc["gecikme_ort_ms"] = (g_s / g_n * 1000.0) if g_n else float("nan")
    return sonuc


def main() -> int:
    ap = argparse.ArgumentParser(description="parti doldurma dönüşümlü A/B")
    ap.add_argument("--degerler", type=int, nargs="*", default=[0, 60])
    ap.add_argument("--tur", type=int, default=2, help="her ayar kaç kez")
    ap.add_argument("--isinma", type=float, default=120.0)
    ap.add_argument("--pencere", type=float, default=240.0)
    args = ap.parse_args()

    blok_sure = (args.isinma + args.pencere + 15) / 60
    toplam = blok_sure * len(args.degerler) * args.tur
    print(
        f"{len(args.degerler)} ayar × {args.tur} tur = "
        f"{len(args.degerler) * args.tur} blok · ~{toplam:.0f} dakika\n"
        f"⚠ Dönüşümlü koşu: {' → '.join(str(d) for d in args.degerler)} sırası "
        f"{args.tur} kez tekrarlanıyor (P-17)\n",
        flush=True,
    )

    olcumler: list[dict[str, float]] = []
    for tur in range(args.tur):
        for fill in args.degerler:
            print(f"[tur {tur + 1}] fill={fill} ms başlıyor...", flush=True)
            s = _blok_olc(fill, args.isinma, args.pencere)
            s["tur"] = float(tur)
            olcumler.append(s)
            print(
                f"    {s['verim_kare_sn']:.1f} kare/sn · "
                f"{s['kare_per_parti']:.2f} kare/parti · "
                f"dolu %{s['dolu_parti_orani'] * 100:.0f} · "
                f"gecikme {s['gecikme_ort_ms']:.0f} ms",
                flush=True,
            )

    print(f"\n{'fill ms':>8} {'verim':>8} {'kare/parti':>11} {'dolu':>7} {'gecikme':>9}")
    ozet: dict[str, dict[str, float]] = {}
    for fill in args.degerler:
        ilgili = [s for s in olcumler if s["fill_ms"] == fill]
        v = sum(s["verim_kare_sn"] for s in ilgili) / len(ilgili)
        kp = sum(s["kare_per_parti"] for s in ilgili) / len(ilgili)
        dp = sum(s["dolu_parti_orani"] for s in ilgili) / len(ilgili)
        g = sum(s["gecikme_ort_ms"] for s in ilgili) / len(ilgili)
        ozet[str(fill)] = {
            "verim_kare_sn": round(v, 2),
            "kare_per_parti": round(kp, 2),
            "dolu_parti_orani": round(dp, 4),
            "gecikme_ort_ms": round(g, 1),
        }
        print(f"{fill:>8} {v:>8.1f} {kp:>11.2f} {dp:>6.1%} {g:>8.0f}ms")

    taban = args.degerler[0]
    print(f"\nTABAN: fill={taban} ms")
    for fill in args.degerler[1:]:
        dv = ozet[str(fill)]["verim_kare_sn"] / max(ozet[str(taban)]["verim_kare_sn"], 1e-9)
        dg = ozet[str(fill)]["gecikme_ort_ms"] - ozet[str(taban)]["gecikme_ort_ms"]
        print(f"  fill={fill:>3} → verim {(dv - 1) * 100:+.1f}% · gecikme {dg:+.0f} ms")
    print(
        "\n⚠ KABUL KRİTERİ: K3 uçtan uca gecikme ≤1500 ms. Verimi\n"
        "  gecikmeyi patlatarak almak kazanç değil takastır."
    )

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "isinma_s": args.isinma,
        "pencere_s": args.pencere,
        "tur": args.tur,
        "bloklar": olcumler,
        "ozet": ozet,
    }
    BENCHMARKS.mkdir(exist_ok=True)
    hedef = BENCHMARKS / f"batch_fill_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
