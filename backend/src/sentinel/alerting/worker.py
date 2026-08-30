"""Alarm worker'ı — olayları kalıcılaştırır.

Zincirdeki yeri
---------------
    Analytics worker  →  Valkey `analytics.events`  →  [BU WORKER]  →  PostgreSQL
                                     ↓
                              WebSocket → panel (canlı)

⚠ NEDEN AYRI BİR SÜREÇ, NEDEN ANALYTICS'İN İÇİNDE DEĞİL
Analytics worker saniyede onlarca kare işliyor ve gecikme bütçesi
(K3 ≤1500 ms) onun üstünde. Veritabanına yazmak ağ turu + disk fsync
demek; bunu analiz döngüsünün içine koymak iki şeyi birden bozardı:

  · gecikme doğrudan artar
  · **veritabanı yavaşlarsa ANALİZ yavaşlar** — yardımcı bir bileşenin
    arızası ana boru hattını durduramaz (PLAN §4.2)

Ayrı süreç bu bağı koparıyor: veritabanı tümden çökse bile tespit,
takip, anomali ve panel çalışmaya devam ediyor. Kaybedilen şey alarm
GEÇMİŞİ, alarmın kendisi değil.

⚠ TÜKETİCİ GRUBU KULLANILIYOR — "$" DEĞİL
Analytics worker canlı akışı `$` ile okuyor (geçmişi umursamıyor,
gerçek zamanlı olan önemli). Alarm worker'ı **tam tersini** istiyor:
hiçbir olayı kaçırmamalı, yeniden başlarsa kaldığı yerden devam
etmeli. Tüketici grubu tam olarak bunu veriyor — okunmamış kayıtlar
grupta bekliyor.

⚠ KUYRUK YİNE DE SINIRLI (mimari kural 5)
`analytics.events` akışı `maxlen=1000`. Bu worker günlerce kapalı
kalırsa eski alarmlar akıştan düşer ve yazılamaz. Sınırsız kuyruk
alternatifi RAM patlamasıydı; bilinçli takas.

Kullanım
--------
    uv run python -m sentinel.alerting.worker
    uv run python -m sentinel.alerting.worker --duration 60
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
import time
from types import FrameType
from typing import cast

from sentinel import metrics
from sentinel.bus.streams import connect
from sentinel.config import get_settings
from sentinel.db import olaylar as olay_deposu
from sentinel.db.engine import kapat as motoru_kapat
from sentinel.db.engine import motor
from sentinel.db.schema import semayi_kur
from sentinel.logging import configure_logging, get_logger

log = get_logger(__name__)

AKIS = "analytics.events"
GRUP = "alarm"

_dur = False


def _sinyal(_sig: int, _frame: FrameType | None) -> None:
    global _dur
    _dur = True
    log.info("kapanis_sinyali")


class AlarmWorker:
    """Olay akışını okuyup veritabanına yazar."""

    def __init__(
        self,
        *,
        worker_id: str = "alarm-0",
        block_ms: int = 1000,
        batch: int = 50,
    ) -> None:
        self._client = connect()
        self._worker_id = worker_id
        self._block_ms = block_ms
        self._batch = batch
        self.yazilan = 0
        self.atlanan = 0
        self.basarisiz = 0

    def _grubu_kur(self) -> None:
        """Tüketici grubunu kurar — yoksa akışı da yaratır.

        ⚠ `mkstream=True`: alarm worker'ı analytics worker'dan önce
        açılabilir ve o durumda akış henüz yoktur. Sıra bağımlılığı
        kurmamak, başlatma betiğini basit tutuyor.
        """
        try:
            self._client.xgroup_create(AKIS, GRUP, id="0", mkstream=True)
            log.info("tuketici_grubu_kuruldu", akis=AKIS, grup=GRUP)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def calistir(self, sure: float | None = None) -> None:
        # ⚠ Şema her açılışta kuruluyor (idempotent). Elle migration
        # gerektiren bir sistem, bir bileşen yeniden başladığında
        # sessizce çalışmaz duruma gelir.
        async with motor().begin() as baglanti:
            await semayi_kur(baglanti)
        log.info("sema_hazir")

        self._grubu_kur()
        basladi = time.monotonic()
        son_rapor = basladi

        while not _dur:
            # ⚠ `cast`: redis-py bu çağrı için çok geniş bir birleşik
            # tip döndürüyor (bayt/str, tüketici grubu/normal okuma tüm
            # varyantları). `decode_responses=True` ile bağlandığımız
            # için pratikte her zaman `list[(str, list[(str, dict)])]`.
            kayitlar = cast(
                "list[tuple[str, list[tuple[str, dict[str, str]]]]]",
                self._client.xreadgroup(
                    GRUP, self._worker_id, {AKIS: ">"},
                    count=self._batch, block=self._block_ms,
                ),
            )
            if kayitlar:
                await self._isle(kayitlar)

            simdi = time.monotonic()
            if simdi - son_rapor >= 60.0:
                log.info(
                    "alarm_worker",
                    yazilan=self.yazilan,
                    atlanan=self.atlanan,
                    basarisiz=self.basarisiz,
                )
                son_rapor = simdi
            if sure and simdi - basladi >= sure:
                break

        await motoru_kapat()
        log.info(
            "alarm_worker_bitti",
            yazilan=self.yazilan,
            atlanan=self.atlanan,
            basarisiz=self.basarisiz,
        )

    async def _isle(
        self, kayitlar: list[tuple[str, list[tuple[str, dict[str, str]]]]]
    ) -> None:
        toplu: list[olay_deposu.Olay] = []
        kimlikler: list[str] = []
        for _akis, girisler in kayitlar:
            for kimlik, alanlar in girisler:
                olay = olay_deposu.Olay.akistan(alanlar)
                if olay is None:
                    self.atlanan += 1
                    # ⚠ Bozuk kayıt yine de ACK'leniyor: aksi hâlde
                    # sonsuza dek yeniden teslim edilir ve worker o tek
                    # kayda takılıp kalır (zehirli mesaj sorunu).
                    kimlikler.append(kimlik)
                    continue
                toplu.append(olay)
                kimlikler.append(kimlik)

        if toplu:
            yazilan = await olay_deposu.yaz(toplu)
            if yazilan == 0:
                # ⚠ ACK YOK: yazılamadıysa kayıt grupta bekliyor ve
                # bir sonraki turda yeniden denenecek. Yazamadığımız
                # bir alarmı "işlendi" saymak, sessiz veri kaybıdır.
                self.basarisiz += len(toplu)
                return
            self.yazilan += yazilan
            metrics.olaylar_yazildi.inc(yazilan)

        if kimlikler:
            self._client.xack(AKIS, GRUP, *kimlikler)


def main() -> int:
    ap = argparse.ArgumentParser(description="Alarm worker'ı — olayları kalıcılaştırır")
    ap.add_argument("--worker-id", default="alarm-0")
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--duration", type=float, default=None)
    # ⚠ 9130 — 9120 ANALİTİK worker'ında kullanılıyor.
    # İlk sürümde ikisi de 9120 idi; ikinci açılan sessizce metrik
    # sunucusunu kaybediyordu. Port çakışmaları bu projede daha önce
    # de yaşandı (P-01) ve hep aynı biçimde: bileşen çalışır görünür,
    # yalnızca gözlemlenemez olur.
    ap.add_argument("--metrics-port", type=int, default=9130)
    args = ap.parse_args()

    configure_logging(get_settings().log_level)
    signal.signal(signal.SIGINT, _sinyal)
    signal.signal(signal.SIGTERM, _sinyal)
    metrics.serve_metrics(args.metrics_port)

    worker = AlarmWorker(worker_id=args.worker_id, batch=args.batch)
    asyncio.run(worker.calistir(sure=args.duration))
    return 0


if __name__ == "__main__":
    sys.exit(main())
