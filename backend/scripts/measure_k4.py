"""K4 — dayanıklılık ölçümü (PLAN §1.4, hedef: 2 saat çökmesiz).

Neden bu betik
--------------
K4 bugüne kadar **hiç ölçülmedi** ve ölçmenin yolu "iki saat açık
bırakıp sonra bakmak" değil. Öyle yapılırsa elde tek bir cümle kalır:
*"çökmedi."* O cümle bir kriteri karşılamaz, çünkü:

  · **Çökme tek arıza türü değil.** Bir worker ayakta kalıp iş
    üretmeyi bırakabilir; dışarıdan sağlıklı görünür.
  · **Sızıntı yavaştır.** P-38'de bir çökme paylaşımlı bellek havuzunu
    KALICI olarak küçültüyordu ve arıza SESSİZDİ. Tek bir anlık
    bakış onu göremez — sızıntı ancak ZAMAN SERİSİNDE görünür.
  · **Kanıt gerekiyor.** Rapora "iki saat koştu" yazmak bir iddiadır;
    `benchmarks/k4_*.json` bir bulgudur.

Bu yüzden betik iki saat boyunca beş metrik ucunu düzenli aralıkla
örnekliyor ve **arıza belirtilerini adlandırıyor.**

⚠ AYNI KOŞUDAN K2 VE K3 DE ÇIKIYOR — ve bu bir bonus değil, bir DÜZELTME
CLAUDE.md "gecikme 468 ms, analiz ~2.9 FPS" diyordu ama `benchmarks/`
içinde 17.08'den (Gün 11) sonra tek bir gecikme/verim kaydı yoktu —
o sayılar konsol çıktısından geliyordu. Projenin kendi kuralı
("her yeni ölçüm git'e giren bir JSON üretir") iki kriter için
çiğnenmiş durumdaydı. Sistem zaten iki saat koşacak; K2 ve K3'ü ayrı
bir koşuda tekrar ölçmek hem gereksiz hem de daha az güvenilir olurdu
(iki saatlik pencere, beş dakikalık pencereden iyi bir tahmindir).

⚠ NEDEN PROMETHEUS'A DEĞİL, UÇLARA DOĞRUDAN SORULUYOR
Prometheus 10 saniyede bir kazıyor ve kendi saklama/örnekleme
katmanını araya koyuyor. Ölçümün Prometheus'un ayarlarına bağlı
olmaması gerekir; ayrıca Prometheus'un kendisi bu koşuda ölçülen
sistemin bir parçası. Ölçüm aracını ölçtüğü sistemin içinden seçmek,
bu projede üç kez pahalıya patladı (P-17, P-36, P-39).

⚠ İLK 90 SANİYE ATILIYOR (P-28)
Isınma sırasında gecikme ve verim gerçek rejimi temsil etmiyor.
Örnekler yine de KAYDEDİLİYOR — atılan şey yalnızca özet
hesaplarındaki payları. Ham seriyi saklamak, sonradan "ısınma ne kadar
sürdü" sorusunu cevaplanabilir tutuyor.

Kullanım
--------
    uv run python scripts/measure_k4.py                  # 2 saat
    uv run python scripts/measure_k4.py --sure 600       # 10 dk deneme
    uv run python scripts/measure_k4.py --aralik 15

⚠ KOŞU KOŞULLARI
    · panel KAPALI olmalı (P-24: 20 kutucuk verimi yarıya düşürüyor)
    · koşarken sisteme DOKUNMA — docker restart dâhil (P-36)
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

# Bileşen adı → metrik ucu. Sıra, `start_all.ps1`'deki başlatma
# sırasıyla aynı: okuyan kişi ikisini yan yana koyabilsin.
UCLAR: dict[str, str] = {
    "ingest": "http://127.0.0.1:9101/metrics",
    "inference": "http://127.0.0.1:9110/metrics",
    "analytics": "http://127.0.0.1:9120/metrics",
    "alerting": "http://127.0.0.1:9130/metrics",
    "api": "http://127.0.0.1:8001/metrics",
}

# Isınma penceresi — bu süredeki örnekler özete girmiyor (P-28).
ISINMA_S = 90.0


# ══════════════════════════════════════════════════════════════
#  Metrik okuma
# ══════════════════════════════════════════════════════════════


def _kazi(url: str, zaman_asimi: float = 4.0) -> str | None:
    """Bir metrik ucunu okur. Okunamazsa None — bu bir VERİ NOKTASI.

    ⚠ İstisna YUTULUYOR ve bu bilinçli: bir ucun cevap vermemesi tam
    olarak K4'ün aradığı şey. Betiği durdurmak, ölçümü aradığı arıza
    yüzünden iptal etmek olurdu.
    """
    try:
        with urllib.request.urlopen(url, timeout=zaman_asimi) as yanit:  # noqa: S310
            return str(yanit.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def _ayristir(metin: str) -> dict[str, list[tuple[dict[str, str], float]]]:
    """Prometheus metin biçimini `ad → [(etiketler, değer)]` sözlüğüne çevirir.

    ⚠ `prometheus_client.parser` KULLANILMIYOR, elle ayrıştırılıyor.
    Sebep: o ayrıştırıcı histogram kovalarını `_bucket` örneklerine
    geri döndürmek yerine kendi nesne modeline sarıyor ve `le`
    etiketini kaybetmeden almak zorlaşıyor. Burada ihtiyacımız olan şey
    ham kova sayaçları — en kısa yol satırı olduğu gibi okumak.
    """
    cikti: dict[str, list[tuple[dict[str, str], float]]] = {}
    for satir in metin.splitlines():
        if not satir or satir[0] == "#":
            continue
        try:
            sol, sag = satir.rsplit(" ", 1)
            deger = float(sag)
        except ValueError:
            continue
        if "{" in sol:
            ad, ham_etiket = sol.split("{", 1)
            ham_etiket = ham_etiket.rstrip("}")
            etiketler: dict[str, str] = {}
            # Etiket değerleri virgül içerebilir; ama bizim ürettiğimiz
            # metriklerde içermiyor. Yine de kaba bir ayrıştırma yerine
            # tırnak sınırına bakılıyor.
            for parca in ham_etiket.split('",'):
                if "=" not in parca:
                    continue
                k, _, v = parca.partition("=")
                etiketler[k.strip()] = v.strip().strip('"')
            cikti.setdefault(ad.strip(), []).append((etiketler, deger))
        else:
            cikti.setdefault(sol.strip(), []).append(({}, deger))
    return cikti


def _tek(
    olcumler: dict[str, list[tuple[dict[str, str], float]]], ad: str
) -> float | None:
    """Etiketsiz (ya da tek örnekli) bir metriğin değeri."""
    kayitlar = olcumler.get(ad)
    if not kayitlar:
        return None
    return kayitlar[0][1]


def _toplam(
    olcumler: dict[str, list[tuple[dict[str, str], float]]], ad: str
) -> float:
    """Etiketli bir metriğin tüm örneklerinin toplamı."""
    return sum(d for _e, d in olcumler.get(ad, []))


def _etikete_gore(
    olcumler: dict[str, list[tuple[dict[str, str], float]]], ad: str, etiket: str
) -> dict[str, float]:
    """Bir etikete göre toplulaştırılmış değerler (ör. atılma sebebi)."""
    cikti: dict[str, float] = {}
    for etiketler, deger in olcumler.get(ad, []):
        anahtar = etiketler.get(etiket, "?")
        cikti[anahtar] = cikti.get(anahtar, 0.0) + deger
    return cikti


def _kovalar(
    olcumler: dict[str, list[tuple[dict[str, str], float]]], ad: str
) -> dict[float, float]:
    """Histogramın kümülatif kovaları: `üst sınır → sayaç`."""
    cikti: dict[float, float] = {}
    for etiketler, deger in olcumler.get(f"{ad}_bucket", []):
        ham = etiketler.get("le")
        if ham is None:
            continue
        cikti[float("inf") if ham in ("+Inf", "Inf") else float(ham)] = deger
    return cikti


def _yuzdelik(kovalar: dict[float, float], oran: float) -> float | None:
    """Kümülatif kovalardan yüzdelik — doğrusal ara değerleme ile.

    ⚠ SONUÇ BİR TAHMİN, ölçüm değil. Histogram kovaları ham değerleri
    saklamıyor; yüzdelik ancak kova sınırları arasında ara değerlenerek
    kestirilebilir. Kova sınırları geniş olduğunda hata da büyür ve bu
    raporda böyle yazılmalı — "p95 = 512 ms" değil, "p95 ≈ 512 ms
    (kova ara değerlemesi)".
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
                # Son kovaya düştüyse ara değerleme yapılamaz; bir
                # önceki sınır alt kestirim olarak dönüyor.
                return onceki_sinir
            genislik = sinir - onceki_sinir
            pay = (hedef - onceki_sayac) / max(sayac - onceki_sayac, 1e-9)
            return onceki_sinir + genislik * pay
        onceki_sinir, onceki_sayac = sinir, sayac
    return sirali[-1][0]


def _kova_farki(
    son: dict[float, float], ilk: dict[float, float]
) -> dict[float, float]:
    """İki kümülatif histogram anlık görüntüsünün farkı.

    ⚠ NEDEN FARK ALINIYOR
    Histogram kümülatif: süreç başından beri her şeyi sayıyor. Doğrudan
    yüzdelik almak, ısınma sırasındaki yüksek gecikmeleri sonsuza dek
    ortalamaya katmak olurdu (P-28). Fark, yalnızca ısınma SONRASI
    pencereyi bırakıyor.
    """
    return {sinir: sayac - ilk.get(sinir, 0.0) for sinir, sayac in son.items()}


# ══════════════════════════════════════════════════════════════
#  Örnekleme
# ══════════════════════════════════════════════════════════════


def _ornek_al() -> dict[str, Any]:
    """Tüm uçlardan tek bir anlık görüntü."""
    ornek: dict[str, Any] = {"t": time.time(), "ayakta": {}, "veri": {}}
    for bilesen, url in UCLAR.items():
        ham = _kazi(url)
        if ham is None:
            # Uç cevap vermedi. Süreç ölmüş, asılmış ya da port
            # kapanmış olabilir — ayırt edemiyoruz ve etmemize gerek
            # de yok: üçü de K4 açısından ARIZA.
            ornek["ayakta"][bilesen] = False
            continue
        olcumler = _ayristir(ham)
        ornek["ayakta"][bilesen] = True

        # `worker_up` gauge'i sürecin KENDİ beyanı. Uç cevap veriyor
        # ama gauge 0 ise: süreç yaşıyor, döngüsü bitmiş demektir.
        # Bu ayrım önemli — "ölmüş" ile "çalışmayı bırakmış" farklı
        # arızalar ve ikincisi çok daha sinsi.
        beyan: dict[str, float] = {}
        for etiketler, deger in olcumler.get("sentinel_worker_up", []):
            beyan[etiketler.get("component", "?")] = deger

        veri: dict[str, Any] = {"worker_up": beyan}

        if bilesen == "ingest":
            veri["kamera_ayakta"] = _toplam(olcumler, "sentinel_camera_up")
            veri["kamera_fps_toplam"] = _toplam(olcumler, "sentinel_camera_fps")
            veri["kare_alindi"] = _toplam(olcumler, "sentinel_frames_received_total")
            veri["kare_yayinlandi"] = _toplam(
                olcumler, "sentinel_frames_published_total"
            )
            veri["atilan"] = _etikete_gore(
                olcumler, "sentinel_frames_dropped_total", "reason"
            )
            veri["bos_slot"] = _tek(olcumler, "sentinel_shm_slots_free")
            veri["kuyruk"] = _etikete_gore(
                olcumler, "sentinel_queue_depth", "queue"
            )
        elif bilesen == "inference":
            veri["bos_slot"] = _tek(olcumler, "sentinel_shm_slots_free")
            # ⭐ KUYRUK DERİNLİĞİ — geri basıncın tek gözlemlenebilir izi.
            #
            # ⚠⚠ Bu metrik Gün 1'den beri yayınlanıyordu ve HİÇBİR ölçüm
            # betiği okumuyordu (P-60). Örnekleme 2.77 FPS iken analiz
            # 1.42 FPS ölçülen koşular var; aradaki kareler `frames_dropped`
            # sayaçlarında GÖRÜNMÜYOR, çünkü kayıp alım tarafında değil,
            # sınırlı akışın (`maxlen`) kuyruk sonunda oluyor.
            #
            # ⭐ P-40'ın kardeşi: orada alet yanlış ölçüyordu, burada alet
            # doğru ölçüyor ama kimse bakmıyordu. Sonuç aynı: körlük.
            veri["kuyruk"] = _etikete_gore(
                olcumler, "sentinel_queue_depth", "queue"
            )
            veri["kapasite_fps"] = _tek(olcumler, "sentinel_pipeline_capacity_fps")
            veri["vram_bayt"] = _tek(olcumler, "sentinel_gpu_memory_used_bytes")
            veri["tespit"] = _toplam(olcumler, "sentinel_detections_total")
            # ⚠ ANALİZ EDİLEN KARE SAYISI — ve buraya iki kez yanlış yazıldı
            #
            # İlk sürüm `sentinel_inference_duration_seconds_count{stage="detect"}`
            # kullanıyordu ve K2'yi **6 kat düşük** ölçtü (0.47 yerine
            # ~2.8 FPS/kamera). Sebep: o histogram parti başına BİR kez
            # gözlemleniyor (`inference/worker.py:544`), gözlemlenen
            # DEĞER kare başına süre olsa da SAYACI parti sayıyor.
            # Ortalama parti 6 kare olduğu için sayaç tam 6 kat eksik.
            #
            # ⚠ Genel ders: bir histogramın `_count` alanı "kaç şey"
            # değil "kaç GÖZLEM" demektir. İkisi ancak gözlem başına bir
            # şey düşüyorsa aynıdır.
            #
            # `end_to_end_latency` ise kare başına gözlemleniyor
            # (`inference/worker.py:624`, mesaj döngüsünün İÇİNDE) —
            # analiz edilen kareyi sayan tek doğru sayaç bu.
            veri["analiz_kare"] = _tek(
                olcumler, "sentinel_end_to_end_latency_seconds_count"
            )
            # Parti sayısı ayrıca tutuluyor: analiz_kare / parti_sayisi
            # ortalama parti boyutunu verir ve iki sayacın tutarlılığını
            # çapraz kontrol eder.
            for etiketler, deger in olcumler.get(
                "sentinel_inference_duration_seconds_count", []
            ):
                if etiketler.get("stage") == "detect":
                    veri["parti_sayisi"] = deger
            veri["gecikme_kova"] = _kovalar(
                olcumler, "sentinel_end_to_end_latency_seconds"
            )
            veri["parti_kova"] = _kovalar(olcumler, "sentinel_batch_size")
        elif bilesen == "analytics":
            veri["anomali"] = _toplam(olcumler, "sentinel_anomalies_total")
        elif bilesen == "alerting":
            veri["olay_yazildi"] = _tek(olcumler, "sentinel_olaylar_yazildi_total")
            veri["klip"] = _tek(olcumler, "sentinel_klipler_uretildi_total")

        ornek["veri"][bilesen] = veri
    return ornek


# ══════════════════════════════════════════════════════════════
#  Değerlendirme
# ══════════════════════════════════════════════════════════════


def _degerlendir(ornekler: list[dict[str, Any]], sure: float) -> dict[str, Any]:
    """Ham örnek serisinden K4/K2/K3 sonuçlarını çıkarır."""
    if len(ornekler) < 2:
        return {"hata": "yeterli örnek yok"}

    t0 = ornekler[0]["t"]
    isinma_sonrasi = [o for o in ornekler if o["t"] - t0 >= ISINMA_S]
    if len(isinma_sonrasi) < 2:
        isinma_sonrasi = ornekler

    ilk, son = isinma_sonrasi[0], isinma_sonrasi[-1]
    pencere_s = son["t"] - ilk["t"]

    # ─── K4: kesinti var mı ───
    kesintiler: list[dict[str, Any]] = []
    for o in ornekler:
        gecen = round(o["t"] - t0, 1)
        for bilesen, ayakta in o["ayakta"].items():
            if not ayakta:
                kesintiler.append(
                    {"t_s": gecen, "bilesen": bilesen, "tur": "uc_cevap_vermedi"}
                )
            else:
                beyan = o["veri"].get(bilesen, {}).get("worker_up", {})
                for ad, deger in beyan.items():
                    if deger < 1:
                        kesintiler.append(
                            {
                                "t_s": gecen,
                                "bilesen": bilesen,
                                "tur": "worker_up=0",
                                "beyan_eden": ad,
                            }
                        )

    # ─── Slot sızıntısı (P-38'in asıl sınavı) ───
    #
    # ⚠ ANLIK BOŞ SLOT SAYISI DALGALANIR — sızıntı DEĞİLDİR.
    # Havuz sürekli alınıp bırakılıyor; bir anlık düşük değer normal.
    #
    # ⚠⚠ 03.09.2026 — İLK SÜRÜM YANLIŞ ALARM ÜRETTİ (P-46)
    # İlk sürüm pencereyi ikiye bölüp AZAMİ değerleri kıyaslıyordu:
    #
    #     ilk yarı azami 46  →  son yarı azami 41   ⇒ "SIZINTI ŞÜPHELİ"
    #
    # Verdikt YANLIŞTI. İki uç değeri karşılaştırmak, iki örneklemli bir
    # test yapmak demek — ve serinin standart sapması 5.9 slot iken 5
    # slotluk bir fark tam olarak GÜRÜLTÜ. 20 dakikalık pencerelerde
    # azami şöyleydi: 35 → 46 → 43 → 41 → 37 → 41. Yani ilk pencere
    # zaten en düşüğüydü; monoton bir düşüş yok.
    #
    # ⭐ Sızıntının imzası "son değer ilkinden küçük" değil, **zamanla
    # düşen bir EĞİLİM.** Doğru araç en küçük kareler eğimi ve o eğimin
    # serinin kendi dalgalanmasıyla kıyaslanması. Tek bir uç değer,
    # kaç örnek olursa olsun bir eğilim göstermez.
    #
    # ⚠ Bu, projenin merkezî hatasının BEŞİNCİ örneği: ölçüm aracına,
    # ölçtüğü şeye gösterilen şüpheyi göstermemek. Fark şu ki bu kez
    # araç ölçümden ÖNCE değil SONRA sorgulandı ve yanlış alarm
    # yakalandı — ham seri JSON'a yazıldığı için mümkün oldu.
    slot_serisi = [
        (o["t"] - t0, o["veri"]["ingest"]["bos_slot"])
        for o in isinma_sonrasi
        if o["veri"].get("ingest", {}).get("bos_slot") is not None
    ]
    slot: dict[str, Any] = {"olculdu": False}
    if len(slot_serisi) >= 10:
        degerler = [v for _t, v in slot_serisi]
        n = len(slot_serisi)
        ort_t = sum(t for t, _v in slot_serisi) / n
        ort_v = sum(degerler) / n
        payda = sum((t - ort_t) ** 2 for t, _v in slot_serisi)
        egim_sn = (
            sum((t - ort_t) * (v - ort_v) for t, v in slot_serisi) / payda
            if payda > 0
            else 0.0
        )
        sapma = statistics.stdev(degerler) if n > 1 else 0.0
        toplam_degisim = egim_sn * (slot_serisi[-1][0] - slot_serisi[0][0])
        # ⚠ ÖLÇÜT: koşu boyunca eğimin öngördüğü toplam düşüş, serinin
        # kendi standart sapmasını AŞIYOR MU. Aşmıyorsa gözlenen düşüş
        # dalgalanmanın içinde kalıyor demektir ve "sızıntı var"
        # denemez. Bu eşik keyfi ama gerekçeli: bir eğilimin gürültüden
        # ayırt edilebilmesi için en az onun mertebesinde olması gerekir.
        supheli = toplam_degisim < -sapma
        slot = {
            "olculdu": True,
            "egim_slot_saat": round(egim_sn * 3600, 2),
            "kosu_boyunca_degisim": round(toplam_degisim, 1),
            "seri_std_sapma": round(sapma, 1),
            "en_dusuk": min(degerler),
            "en_yuksek": max(degerler),
            "sizinti_supheli": bool(supheli),
            "yontem": (
                "en küçük kareler eğimi; toplam değişim serinin standart "
                "sapmasını aşarsa şüpheli. İki uç değeri kıyaslamak "
                "yanlış alarm üretiyordu (P-46)."
            ),
        }

    # ─── K2: analiz kare hızı ───
    ilk_inf = ilk["veri"].get("inference", {})
    son_inf = son["veri"].get("inference", {})
    ilk_ing = ilk["veri"].get("ingest", {})
    son_ing = son["veri"].get("ingest", {})

    k2: dict[str, Any] = {"olculdu": False}
    analiz_ilk = ilk_inf.get("analiz_kare")
    analiz_son = son_inf.get("analiz_kare")
    kamera_sayisi = max(son_ing.get("kamera_ayakta", 0) or 0, 1)
    if analiz_ilk is not None and analiz_son is not None and pencere_s > 0:
        analiz_fps = (analiz_son - analiz_ilk) / pencere_s
        ornekleme_fps = (
            (son_ing.get("kare_alindi", 0) - ilk_ing.get("kare_alindi", 0))
            / pencere_s
        )
        k2 = {
            "olculdu": True,
            "hedef_fps_kamera": 4.0,
            "kamera_sayisi": kamera_sayisi,
            "analiz_fps_toplam": round(analiz_fps, 2),
            "analiz_fps_kamera": round(analiz_fps / kamera_sayisi, 2),
            "ornekleme_fps_toplam": round(ornekleme_fps, 2),
            "ornekleme_fps_kamera": round(ornekleme_fps / kamera_sayisi, 2),
            "tutuyor": bool(analiz_fps / kamera_sayisi >= 4.0),
        }

    # ─── K3: uçtan uca gecikme ───
    k3: dict[str, Any] = {"olculdu": False}
    fark = _kova_farki(
        son_inf.get("gecikme_kova", {}) or {}, ilk_inf.get("gecikme_kova", {}) or {}
    )
    if fark:
        p50 = _yuzdelik(fark, 0.50)
        p95 = _yuzdelik(fark, 0.95)
        toplam = max(fark.values()) if fark else 0
        k3 = {
            "olculdu": True,
            "hedef_ms": 1500,
            "ornek_sayisi": int(toplam),
            "p50_ms": round(p50 * 1000, 1) if p50 is not None else None,
            "p95_ms": round(p95 * 1000, 1) if p95 is not None else None,
            "yontem": "histogram kova ara değerlemesi — kesin değer değil",
            "tutuyor": bool(p95 is not None and p95 * 1000 <= 1500),
        }

    # ─── Parti dolgunluğu ve atılan kareler ───
    parti_fark = _kova_farki(
        son_inf.get("parti_kova", {}) or {}, ilk_inf.get("parti_kova", {}) or {}
    )
    parti_p50 = _yuzdelik(parti_fark, 0.50) if parti_fark else None

    atilan_fark: dict[str, float] = {}
    for sebep, deger in (son_ing.get("atilan") or {}).items():
        atilan_fark[sebep] = deger - (ilk_ing.get("atilan") or {}).get(sebep, 0.0)

    return {
        "K4": {
            "hedef": "2 saat (7200 sn) çökmesiz",
            "gercek_sure_s": round(sure, 1),
            "ornek_sayisi": len(ornekler),
            "isinma_atlandi_s": ISINMA_S,
            "kesinti_sayisi": len(kesintiler),
            "kesintiler": kesintiler[:50],
            "tutuyor": bool(not kesintiler and sure >= 7200),
        },
        "slot_sizintisi": slot,
        "K2": k2,
        "K3": k3,
        "boru_hatti": {
            "kamera_ayakta": son_ing.get("kamera_ayakta"),
            "parti_p50": round(parti_p50, 2) if parti_p50 is not None else None,
            "kapasite_fps": son_inf.get("kapasite_fps"),
            "vram_mb": (
                round((son_inf.get("vram_bayt") or 0) / 1024 / 1024, 1)
                if son_inf.get("vram_bayt")
                else None
            ),
            "atilan_kare": {k: round(v) for k, v in atilan_fark.items()},
            # ⭐ KARE MUHASEBESİ (P-60) — yayınlanan ile analiz edilen
            # arasındaki fark hiçbir sayaçta görünmüyor; sınırlı akıştan
            # düşen kareler burada ortaya çıkıyor.
            "kare_yayinlandi": round(
                (son_ing.get("kare_yayinlandi") or 0)
                - (ilk_ing.get("kare_yayinlandi") or 0)
            ),
            "kare_analiz_edildi": round(
                (son_inf.get("analiz_kare") or 0)
                - (ilk_inf.get("analiz_kare") or 0)
            ),
            # ⚠ Gauge — fark alınmaz, son anlık değer okunur.
            "kuyruk_derinligi": {
                **(son_ing.get("kuyruk") or {}),
                **(son_inf.get("kuyruk") or {}),
            },
            "anomali_uretildi": round(
                son["veri"].get("analytics", {}).get("anomali", 0)
                - ilk["veri"].get("analytics", {}).get("anomali", 0)
            ),
            "olay_yazildi": (
                (son["veri"].get("alerting", {}).get("olay_yazildi") or 0)
                - (ilk["veri"].get("alerting", {}).get("olay_yazildi") or 0)
            ),
            "klip_uretildi": son["veri"].get("alerting", {}).get("klip"),
        },
    }


# ══════════════════════════════════════════════════════════════
#  Ana akış
# ══════════════════════════════════════════════════════════════


def main() -> int:
    ap = argparse.ArgumentParser(description="K4 — dayanıklılık ölçümü")
    ap.add_argument("--sure", type=float, default=7200.0, help="saniye (varsayılan 2 saat)")
    ap.add_argument("--aralik", type=float, default=30.0, help="örnekleme aralığı (sn)")
    ap.add_argument("--etiket", default="", help="dosya adına eklenecek not")
    args = ap.parse_args()

    print("K4 — DAYANIKLILIK ÖLÇÜMÜ")
    print("═" * 60)
    print(f"süre {args.sure:.0f} sn · örnekleme {args.aralik:.0f} sn · "
          f"ısınma {ISINMA_S:.0f} sn atılacak")
    print("⚠ panel KAPALI olmalı (P-24) · koşarken sisteme DOKUNMA (P-36)\n")

    # İlk örnek: sistem gerçekten ayakta mı? Ayakta değilse iki saat
    # beklemenin anlamı yok — arızayı BAŞTA söylemek, sonunda
    # söylemekten iyidir.
    ilk = _ornek_al()
    eksik = [b for b, a in ilk["ayakta"].items() if not a]
    if eksik:
        print(f"⚠ ŞU BİLEŞENLER CEVAP VERMİYOR: {', '.join(eksik)}", file=sys.stderr)
        print("  Ölçüm yine de başlıyor — eksik bileşen bir BULGUDUR.\n", file=sys.stderr)

    ornekler: list[dict[str, Any]] = [ilk]
    basladi = ilk["t"]
    son_yazi = basladi

    try:
        while True:
            gecen = time.time() - basladi
            if gecen >= args.sure:
                break
            time.sleep(min(args.aralik, max(args.sure - gecen, 0.1)))
            ornekler.append(_ornek_al())

            simdi = time.time()
            if simdi - son_yazi >= 300:  # 5 dakikada bir durum satırı
                son = ornekler[-1]
                olu = [b for b, a in son["ayakta"].items() if not a]
                inf = son["veri"].get("inference", {})
                ing = son["veri"].get("ingest", {})
                print(
                    f"  [{(simdi - basladi) / 60:5.1f} dk] "
                    f"kamera {ing.get('kamera_ayakta', 0):.0f} · "
                    f"boş slot {ing.get('bos_slot')} · "
                    f"kapasite {inf.get('kapasite_fps') or 0:.1f} f/s"
                    + (f" · ⚠ ÖLÜ: {','.join(olu)}" if olu else "")
                )
                son_yazi = simdi
    except KeyboardInterrupt:
        print("\n⚠ elle durduruldu — o ana kadarki veri yazılıyor", file=sys.stderr)

    sure = ornekler[-1]["t"] - basladi
    sonuc = _degerlendir(ornekler, sure)

    # ─── Özet ───
    print("\n" + "═" * 60)
    k4 = sonuc["K4"]
    print(f"K4 · {k4['gercek_sure_s'] / 60:.1f} dakika · "
          f"{k4['ornek_sayisi']} örnek · {k4['kesinti_sayisi']} kesinti")
    print("  " + ("✅ TUTUYOR" if k4["tutuyor"] else "❌ TUTMUYOR"))
    for k in k4["kesintiler"][:10]:
        print(f"    ! {k['t_s']:.0f} sn · {k['bilesen']} · {k['tur']}")

    s = sonuc["slot_sizintisi"]
    if s.get("olculdu"):
        print(f"\nSLOT SIZINTISI · eğim {s['egim_slot_saat']:+.2f} slot/saat · "
              f"koşu boyunca {s['kosu_boyunca_degisim']:+.1f} slot · "
              f"seri sapması {s['seri_std_sapma']:.1f}")
        print(f"  aralık: {s['en_dusuk']:.0f}–{s['en_yuksek']:.0f} slot")
        print("  " + (
            "⚠ ŞÜPHELİ — düşüş eğilimi gürültüyü aşıyor"
            if s["sizinti_supheli"]
            else "✅ sızıntı yok — düşüş eğilimi serinin dalgalanmasının içinde"
        ))

    k2 = sonuc["K2"]
    if k2.get("olculdu"):
        print(f"\nK2 · analiz {k2['analiz_fps_kamera']:.2f} FPS/kamera "
              f"(hedef ≥4) · örnekleme {k2['ornekleme_fps_kamera']:.2f} FPS/kamera")
        print("  " + ("✅ TUTUYOR" if k2["tutuyor"] else "🟡 TUTMUYOR — gerekçe raporda"))

    k3 = sonuc["K3"]
    if k3.get("olculdu"):
        print(f"\nK3 · gecikme p50 ≈ {k3['p50_ms']} ms · p95 ≈ {k3['p95_ms']} ms "
              f"(hedef ≤1500) · {k3['ornek_sayisi']} örnek")
        print("  " + ("✅ TUTUYOR" if k3["tutuyor"] else "❌ TUTMUYOR"))

    b = sonuc["boru_hatti"]
    print(f"\nboru hattı · {b['kamera_ayakta']:.0f} kamera · parti p50 {b['parti_p50']} · "
          f"VRAM {b['vram_mb']} MB · {b['anomali_uretildi']} anomali · "
          f"{b['olay_yazildi']:.0f} olay yazıldı")
    if b["atilan_kare"]:
        print(f"  atılan kare: {b['atilan_kare']}")

    # ⭐ KARE MUHASEBESİ (P-60)
    yay, anl = b["kare_yayinlandi"], b["kare_analiz_edildi"]
    kayip = yay - anl
    print(f"  kare muhasebesi: yayın {yay} → analiz {anl} · "
          f"izlenmeyen fark {kayip} (%{100 * kayip / max(yay, 1):.1f})")
    if kayip > 0.05 * max(yay, 1):
        print("    ⚠ >%5 kare analiz edilmedi ve hiçbir sayaç bunu görmüyor →")
        print("      kayıp sınırlı akışın (maxlen) kuyruk sonunda oluyor.")
    if b["kuyruk_derinligi"]:
        print(f"  kuyruk derinliği: {b['kuyruk_derinligi']}")

    cikti = {
        "olculdu": datetime.now(UTC).isoformat(),
        "kriterler": ["K4", "K2", "K3"],
        "kosulllar": {
            "panel": "kapalı (P-24)",
            "isinma_atlandi_s": ISINMA_S,
            "ornekleme_araligi_s": args.aralik,
        },
        "sonuc": sonuc,
        # ⚠ HAM SERİ DE YAZILIYOR. Özet bir yorumdur; ham seri veridir.
        # "Isınma ne kadar sürdü", "sızıntı ne zaman başladı" gibi
        # sorular ancak seriden cevaplanabilir ve o soruları şimdi
        # tahmin edemiyoruz.
        "seri": [
            {
                "t_s": round(o["t"] - basladi, 1),
                "ayakta": o["ayakta"],
                "bos_slot": o["veri"].get("ingest", {}).get("bos_slot"),
                "kamera_ayakta": o["veri"].get("ingest", {}).get("kamera_ayakta"),
                "kapasite_fps": o["veri"].get("inference", {}).get("kapasite_fps"),
                "vram_bayt": o["veri"].get("inference", {}).get("vram_bayt"),
                "kare_alindi": o["veri"].get("ingest", {}).get("kare_alindi"),
                "analiz_kare": o["veri"].get("inference", {}).get("analiz_kare"),
                "anomali": o["veri"].get("analytics", {}).get("anomali"),
                "olay_yazildi": o["veri"].get("alerting", {}).get("olay_yazildi"),
            }
            for o in ornekler
        ],
    }

    BENCHMARKS.mkdir(exist_ok=True)
    ek = f"-{args.etiket}" if args.etiket else ""
    hedef = BENCHMARKS / f"k4_dayaniklilik_{datetime.now():%Y%m%d-%H%M%S}{ek}.json"
    hedef.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nyazıldı: {hedef.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
