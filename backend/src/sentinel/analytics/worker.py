"""Analitik worker'ı — iskeletten ANLAMA giden katman.

Mimarideki yeri
---------------
    çıkarım worker'ı  →  inference.results  (kutular + iskelet + kimlik)
                              ↓
                      ANALİTİK WORKER  (bu dosya)
                        · pencereleri besle
                        · özellik çıkar      (analytics/features/)
                        · kuralları uygula   (analytics/anomaly/rules.py)
                              ↓
                        analytics.events  →  API  →  panel

Neden AYRI bir süreç
--------------------
Çıkarım worker'ının tek işi GPU'yu doyurmak. Oraya analitik eklemek iki
şeyi birden bozardı: GPU boşta beklerken CPU analitik yapar (kare
gecikir) ve analitikte bir hata GPU boru hattını düşürür.

Ayrıca bu worker **GPU'ya hiç dokunmuyor** — tamamen CPU ve hafif.
Gerekirse ayrı bir makineye taşınabilir; çıkarım worker'ı taşınamaz.

⚠ NEDEN KADEME 0 BURAYA DA UYGULANMIYOR
---------------------------------------
Hareket filtresi alım tarafında. Buraya gelen her sonuç zaten filtreyi
geçmiş bir kareye ait, yani "bir şey oluyor" demek. Burada ikinci bir
eleme yapmak gerçek olayları kaçırma riski taşır ve kazanç getirmez:
bu katmanın maliyeti aritmetik, model çağrısı yok.

Kullanım
--------
    uv run python -m sentinel.analytics.worker
    uv run python -m sentinel.analytics.worker --duration 60
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from collections import Counter
from types import FrameType
from typing import Any

import numpy as np

from sentinel import metrics
from sentinel.analytics.anomaly.rules import Anomali, KuralMotoru
from sentinel.analytics.features import skeleton as sk
from sentinel.analytics.features.person import cikar
from sentinel.analytics.features.window import Ornek, PencereDeposu
from sentinel.bus.streams import connect
from sentinel.config import settings
from sentinel.logging import configure_logging, get_logger

log = get_logger(__name__)

GROUP = "analytics"
EVENT_STREAM = "analytics.events"
_stop = False


def _handle_signal(_sig: int, _frame: FrameType | None) -> None:
    global _stop
    _stop = True
    log.info("kapatma_sinyali_alindi")


class AnalyticsWorker:
    """`inference.results` akışını tüketip anomali üretir."""

    def __init__(self, *, worker_id: str = "analytics-0", block_ms: int = 500) -> None:
        self._worker_id = worker_id
        self._block_ms = block_ms
        self._client = connect()
        self._pencereler = PencereDeposu()
        self._kurallar = KuralMotoru()
        # Kamera başına son değerlendirme anı — oyalanma birikimi için
        # gereken `dt`. Kameralar farklı hızlarda analiz edildiği için
        # (uyarlanabilir FPS) sabit adım kullanmak yanlış olurdu.
        self._son_degerlendirme: dict[str, float] = {}

        self.islenen = 0
        self.anomaliler = 0
        self.by_camera: Counter[str] = Counter()
        self._ensure_group()

    def _ensure_group(self) -> None:
        """Tüketici grubunu kurar (varsa sessizce geçer).

        ⚠ `id="$"` bilinçli — çıkarım worker'ının aksine.
        Orada `"0"` gerekiyordu çünkü akıştaki her mesaj işlenmemiş bir
        SLOT taşıyor ve okunmazsa havuz kilitleniyor (P-10). Burada öyle
        bir kaynak yok: analitik geç açıldıysa geçmişteki sonuçları
        işlemenin değeri de yok — gerçek zamanlı bir sistemde 10 dakika
        önceki anomaliyi şimdi bildirmek yanlış olur.
        """
        from redis.exceptions import ResponseError

        try:
            self._client.xgroup_create(
                settings.stream_results, GROUP, id="$", mkstream=True
            )
            log.info("tuketici_grubu_olusturuldu", stream=settings.stream_results)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    # ─── Ana döngü ───────────────────────────────────────────

    def run(self, *, duration: float | None = None, stats_interval: float = 10.0) -> None:
        log.info("analitik_worker_basliyor", worker=self._worker_id)
        metrics.worker_up.labels(component="analytics", worker_id=self._worker_id).set(1)

        started = time.monotonic()
        last_report = started
        last_prune = started
        deadline = started + duration if duration else None

        while not _stop:
            try:
                yanit = self._client.xreadgroup(
                    GROUP,
                    self._worker_id,
                    {settings.stream_results: ">"},
                    count=64,
                    block=self._block_ms,
                )
            except Exception as exc:
                if "NOGROUP" in str(exc):
                    # Çıkarım worker'ı akışı sıfırladı — grubu yeniden kur
                    # ve devam et. Bir bileşenin yeniden başlaması bunu
                    # düşürmemeli (P-20 ile aynı ders).
                    log.warning("grup_kayboldu_yeniden_kuruluyor")
                    self._ensure_group()
                    continue
                log.error("okuma_hatasi", error=f"{type(exc).__name__}: {exc}")
                time.sleep(1.0)
                continue

            if yanit:
                self._isle(yanit)

            now = time.monotonic()
            if now - last_prune >= 30.0:
                self._pencereler.buda(time.time())
                self._kurallar.buda(time.time())
                last_prune = now
            if now - last_report >= stats_interval:
                self._rapor(now - started)
                last_report = now
            if deadline and now >= deadline:
                break

        self._bitir(time.monotonic() - started)

    def _isle(self, yanit: Any) -> None:
        """⚠ `Any` bilinçli: `redis-py`'nin `xreadgroup` dönüş tipi,
        `decode_responses` ayarına göre değişen çok kollu bir birleşim
        (union) ve statik olarak daraltılamıyor. Tipi burada zorlamak
        okunmayan bir `cast` yığını üretirdi; yapı zaten aşağıda
        açılırken doğrulanıyor ve bozuk mesaj yakalanıyor."""
        ids: list[str] = []
        for _akis, girdiler in yanit:
            for message_id, alanlar in girdiler:
                ids.append(message_id)
                try:
                    self._kare_isle(alanlar)
                except Exception as exc:
                    # Tek bir bozuk mesaj worker'ı düşürmemeli.
                    log.warning("kare_islenemedi", error=f"{type(exc).__name__}: {exc}")
        if ids:
            self._client.xack(settings.stream_results, GROUP, *ids)

    def _kare_isle(self, alanlar: dict[str, str]) -> None:
        camera = alanlar.get("cam", "")
        if not camera:
            return
        veri = json.loads(alanlar.get("data", "{}"))
        tespitler = veri.get("detections", [])
        ts = float(alanlar.get("ts", 0.0)) or time.time()

        self.islenen += 1

        # ─── Pencereleri besle ───
        ozellikler = []
        for d in tespitler:
            track_id = d.get("id")
            if track_id is None:
                continue  # kimliksiz izde zamansal analiz yapılamaz (P-13)

            bbox = tuple(float(v) for v in d["bbox"])
            kp = d.get("kp")
            kp_dizi = np.asarray(kp, dtype=np.float64) if kp else None

            pencere = self._pencereler.ekle(
                camera,
                int(track_id),
                Ornek(
                    ts=ts,
                    bbox=bbox,  # type: ignore[arg-type]
                    kp=kp_dizi,
                    olcek=sk.govde_boyu(kp_dizi, bbox) if kp_dizi is not None else None,  # type: ignore[arg-type]
                    ayak=sk.ayak_noktasi(bbox),  # type: ignore[arg-type]
                ),
            )
            ozellikler.append(cikar(pencere))

        # ─── Kuralları uygula ───
        onceki = self._son_degerlendirme.get(camera, ts)
        dt = max(0.0, min(5.0, ts - onceki))  # sıçramalara karşı sınırlı
        self._son_degerlendirme[camera] = ts

        bulgular = self._kurallar.degerlendir(camera, ozellikler, ts, dt)
        for bulgu in bulgular:
            self._yayinla(bulgu, ts)

    def _yayinla(self, anomali: Anomali, ts: float) -> None:
        """Anomaliyi akışa yazar — API oradan okuyup panele iletecek."""
        self._client.xadd(
            EVENT_STREAM,
            {
                "cam": anomali.camera,
                "type": anomali.tur.value,
                "ts": f"{ts:.6f}",
                "data": json.dumps(anomali.to_dict(), separators=(",", ":")),
            },
            maxlen=1000,
            approximate=True,
        )
        self.anomaliler += 1
        self.by_camera[anomali.camera] += 1
        metrics.anomalies_total.labels(
            cam=anomali.camera, type=anomali.tur.value, severity=anomali.ciddiyet
        ).inc()
        log.info(
            "anomali",
            cam=anomali.camera,
            tur=anomali.tur.value,
            iz=anomali.track_id,
            skor=round(anomali.skor, 2),
            kanit=anomali.kanit,
        )

    # ─── Raporlama ───────────────────────────────────────────

    def _rapor(self, elapsed: float) -> None:
        hiz = self.islenen / elapsed if elapsed > 0 else 0.0
        print(
            f"  {self.islenen:>6} sonuç · {hiz:5.1f}/sn · "
            f"{self._pencereler.aktif_iz_sayisi:>3} aktif pencere · "
            f"{self.anomaliler:>3} anomali · {self._kurallar.stats}",
            flush=True,
        )

    def _bitir(self, elapsed: float) -> None:
        print()
        print(f"  İşlenen sonuç : {self.islenen} ({self.islenen / max(elapsed, 1):.1f}/sn)")
        print(f"  Anomali       : {self.anomaliler}")
        for tur, sayi in self._kurallar.stats.items():
            if sayi:
                print(f"    {tur:<12} {sayi}")
        if self.by_camera:
            print("  Kamera bazında:")
            for cam, n in self.by_camera.most_common(10):
                print(f"    {cam:<14} {n}")
        metrics.worker_up.labels(component="analytics", worker_id=self._worker_id).set(0)
        self._client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="SENTINEL analitik worker'ı")
    parser.add_argument("--worker-id", default="analytics-0")
    parser.add_argument("--metrics-port", type=int, default=9120)
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--stats-interval", type=float, default=10.0)
    args = parser.parse_args()

    configure_logging(settings.log_level)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    metrics.serve_metrics(args.metrics_port)

    worker = AnalyticsWorker(worker_id=args.worker_id)
    worker.run(duration=args.duration, stats_interval=args.stats_interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
