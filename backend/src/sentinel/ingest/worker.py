"""Alım (ingest) worker'ı.

Sorumluluğu
-----------
Atanan kameraları RTSP'den okur, Kademe 0 hareket filtresinden geçirir,
geçen kareleri paylaşımlı belleğe yazar ve Valkey'e **yalnızca meta veri**
yayınlar. Ham kare asla kuyruktan geçmez (PLAN.md §4.2).

Neden iş parçacığı (thread), süreç (process) değil
--------------------------------------------------
Python'da CPU-yoğun iş için genelde süreç önerilir çünkü GIL paralelliği
engeller. Ama burada durum farklı: **PyAV ve OpenCV, C kodunda çalışırken
GIL'i bırakır.** Kare çözme ve renk dönüşümü süresinin neredeyse tamamı
GIL dışında geçiyor. Bu yüzden iş parçacıkları gerçekten paralel koşar.

İş parçacığı seçmenin somut faydası: `FramePool` nesnesi tek bir kez
oluşturulup tüm kameralarca paylaşılabiliyor. Süreç kullansaydık her
süreç havuza ayrı bağlanacak, slot sahipliği karmaşıklaşacaktı.

Ölçüm bu kararı doğruladı mı? `--stats` çıktısındaki toplam FPS ile
kamera sayısını karşılaştır: ölçekleniyorsa karar doğru.

Kullanım
--------
    uv run python -m sentinel.ingest.worker --cameras cam-01 cam-02
    uv run python -m sentinel.ingest.worker --all --duration 60
    uv run python -m sentinel.ingest.worker --all --owner --metrics-port 9101
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from types import FrameType

from sentinel import metrics
from sentinel.bus.shm import FramePool, FramePoolError
from sentinel.bus.streams import (
    FrameMessage,
    FrameStream,
    SlotAllocator,
    connect,
    get_pipeline_capacity,
    get_watched_cameras,
)
from sentinel.config import settings
from sentinel.core import preprocess
from sentinel.ingest.decoder import RtspDecoder, StreamClosedError, rtsp_url
from sentinel.ingest.motion_gate import GateReason, MotionGate
from sentinel.logging import configure_logging, get_logger

log = get_logger(__name__)

_shutdown = threading.Event()

# Uyarlanabilir FPS'te "gerçek hareket" sayılan kararlar.
# REFRESH kasten DIŞARIDA: o, hareketsiz duran birini kaybetmemek için
# 5 saniyede bir yapılan periyodik yoklamadır. Hareket sayılsaydı hiçbir
# kamera boşta moduna geçemezdi.
_MOTION_REASONS = frozenset({GateReason.MOTION, GateReason.WARMUP})

# Tüketici kapasitesinin ne kadarı hedeflensin.
# Tam kapasiteyi hedeflemek kuyruğu DOLU tutar ve dolu kuyruk dengede
# bile gecikme üretir (P-25'in ana dersi). %15 pay bırakmak kuyruğun
# boşalmasını sağlıyor: üretim tüketimin biraz altında kalınca birikim
# eriyor ve gecikme kuyruk beklemesi yerine yalnızca işleme süresi olur.
CAPACITY_SAFETY = 0.85


def _handle_signal(_sig: int, _frame: FrameType | None) -> None:
    log.info("kapatma_sinyali_alindi")
    _shutdown.set()


@dataclass(slots=True)
class CameraStats:
    """Tek kameranın çalışma istatistikleri."""

    camera: str
    received: int = 0
    published: int = 0
    dropped_gate: int = 0
    dropped_no_slot: int = 0
    reconnects: int = 0
    started_at: float = field(default_factory=time.monotonic)
    recent_gate: deque[bool] = field(default_factory=lambda: deque(maxlen=100))

    @property
    def fps(self) -> float:
        elapsed = time.monotonic() - self.started_at
        return self.received / elapsed if elapsed > 0 else 0.0

    @property
    def pass_ratio(self) -> float:
        if not self.recent_gate:
            return 0.0
        return sum(self.recent_gate) / len(self.recent_gate)


class CameraTask:
    """Tek bir kamerayı okuyan iş parçacığı gövdesi."""

    def __init__(
        self,
        camera: str,
        pool: FramePool,
        allocator: SlotAllocator,
        stream: FrameStream,
        *,
        target_fps: float,
        reconnect_delay: float = 3.0,
    ) -> None:
        self.camera = camera
        self.stats = CameraStats(camera=camera)
        self._pool = pool
        self._allocator = allocator
        self._stream = stream
        self._target_fps = target_fps
        self._reconnect_delay = reconnect_delay
        self._gate = MotionGate(
            threshold=settings.motion_threshold,
            refresh_interval_s=float(settings.motion_refresh_interval_s),
        )
        self._url = rtsp_url(settings.mediamtx_host, settings.mediamtx_rtsp_port, camera)
        # Uyarlanabilir FPS durumu: açılışta hareket varmış say, yoksa
        # sistem daha ilk kareden boşta moduna düşerdi.
        # ⚠ Duvar saati: `frame.timestamp` ile karşılaştırılıyor ve o
        # da duvar saati (bkz. ingest/decoder.py · DecodedFrame).
        # Karıştırmak `idle_for` değerini anlamsız yapardı.
        self._last_motion_at = time.time()
        # Operatör bu kamerayı panelde açtı mı ve payına kaç FPS düştü?
        # Worker düzenli günceller (IngestWorker.refresh_watched).
        self.watched = False
        self.watched_fps = 0.0
        # Tüketici kapasitesinden gelen kamera başına TAVAN hız.
        # None = kapasite bilinmiyor (çıkarım worker'ı yok), tabana düş.
        self.capacity_fps: float | None = None

    def run(self) -> None:
        """Kamera düşerse yeniden bağlanarak sonsuza dek okur."""
        while not _shutdown.is_set():
            try:
                metrics.camera_up.labels(cam=self.camera).set(1)
                self._read_stream()
            except StreamClosedError as exc:
                log.warning("akis_koptu", camera=self.camera, error=str(exc))
            except Exception as exc:
                log.error("kamera_hatasi", camera=self.camera, error=f"{type(exc).__name__}: {exc}")

            metrics.camera_up.labels(cam=self.camera).set(0)
            if _shutdown.is_set():
                break

            self.stats.reconnects += 1
            log.info("yeniden_baglaniliyor", camera=self.camera, delay=self._reconnect_delay)
            _shutdown.wait(self._reconnect_delay)

    def _read_stream(self) -> None:
        with RtspDecoder(self._url, camera_id=self.camera, target_fps=self._target_fps) as decoder:
            last = time.perf_counter()
            for frame in decoder.frames():
                if _shutdown.is_set():
                    return

                now = time.perf_counter()
                metrics.decode_duration.labels(cam=self.camera).observe(now - last)
                self.stats.received += 1
                metrics.frames_received.labels(cam=self.camera).inc()

                self._process(frame)
                self._adapt_rate(decoder, frame.timestamp)  # type: ignore[attr-defined]

                metrics.camera_fps.labels(cam=self.camera).set(self.stats.fps)
                metrics.motion_gate_ratio.labels(cam=self.camera).set(self.stats.pass_ratio)
                last = time.perf_counter()

    def _adapt_rate(self, decoder: RtspDecoder, now: float) -> None:
        """Kamerada uzun süredir hareket yoksa örnekleme hızını düşürür.

        PLAN.md §5.2. Mantık basit: hareketsiz bir kameradan 4 FPS
        örneklemek boşa iş — kareler zaten Kademe 0'da eleniyor ama
        renk dönüşümü maliyeti çoktan ödenmiş oluyor. Ölçüm bunu
        doğruluyor: cam-06 örneklenen karelerin **%94'ünü** eliyordu.

        ⚠ REFRESH kararı hareket SAYILMAZ. Hareket filtresi 5 saniyede
        bir zorunlu "yenileme karesi" geçirir (hareketsiz duran birini
        kaybetmemek için). Bunu hareket sayarsak hiçbir kamera asla
        boşta moduna geçemezdi — sessiz bir hata olurdu.

        Hareket dönünce hız ANINDA tam değere çıkar: geç kalmak
        olayın başlangıcını kaçırmak demektir, asıl önemsediğimiz an
        tam da o.
        """
        if not settings.adaptive_fps_enabled:
            return

        # ⚠ KAPASİTE TAVANI HER ŞEYİN ÜSTÜNDE
        # Hareket ve "operatör bakıyor" sinyalleri bütçenin NASIL
        # dağıtılacağını söyler; kapasite bütçenin NE KADAR olduğunu.
        # Sırayı ters çevirirsek (önce hareket, sonra tavan) izlenen bir
        # kamera 10 FPS isteyip tüketici 6 kare/sn'deyken sistemi yine
        # boğardı — tam da düzeltmeye çalıştığımız şey.
        tavan = self.capacity_fps

        idle_for = now - self._last_motion_at
        if idle_for >= settings.adaptive_idle_after_s:
            # Uzun süredir hareket yok — kimse izlemiyorsa iyice kıs.
            # İzleniyorsa taban hızın altına inme: operatör baktığı
            # kamerada donuk kutu görmemeli.
            target = float(settings.target_fps if self.watched else settings.target_fps_idle)
        elif self.watched:
            # ⚠ OPERATÖRÜN BAKTIĞI KAMERAYA ÖNCELİK (PLAN.md §5.2)
            # Panelde 7 kutucuk açıkken 20 kamerayı eşit hızda analiz
            # etmek bütçeyi kimsenin bakmadığı yere harcamaktı.
            # Açık kameralar daha sık analiz edilince ekrandaki kutular
            # gözle görülür şekilde düzeliyor; kapalı olanlar taban
            # hızda kalıp alarm üretmeye devam ediyor.
            target = self.watched_fps or float(settings.target_fps_watched)
        else:
            target = self._target_fps

        # Tavan uygulanıyor. Taban hızın altına inilmiyor: sıfıra
        # yaklaşan bir kamera kördür (bkz. _refresh_capacity).
        if tavan is not None:
            target = max(float(settings.target_fps_idle), min(target, tavan))

        if abs(decoder.target_fps - target) > 0.01:
            decoder.set_target_fps(target)
            log.info(
                "ornekleme_hizi_degisti",
                camera=self.camera,
                fps=target,
                idle_s=round(idle_for, 1),
            )
        metrics.camera_target_fps.labels(cam=self.camera).set(target)

    def _process(self, frame: object) -> None:
        image = frame.image  # type: ignore[attr-defined]
        decision = self._gate.evaluate(image, frame.timestamp)  # type: ignore[attr-defined]
        metrics.gate_duration.labels(cam=self.camera).observe(decision.elapsed_ms / 1000.0)
        metrics.gate_decisions.labels(cam=self.camera, reason=decision.reason.value).inc()
        self.stats.recent_gate.append(decision.process)

        # Uyarlanabilir FPS için "son gerçek hareket" zamanı.
        # REFRESH bilinçli olarak sayılmıyor — o periyodik bir yoklama,
        # sahnede bir şey olduğunun kanıtı değil (bkz. _adapt_rate).
        if decision.reason in _MOTION_REASONS:
            self._last_motion_at = frame.timestamp  # type: ignore[attr-defined]

        if not decision.process:
            self.stats.dropped_gate += 1
            metrics.frames_dropped.labels(cam=self.camera, reason="gate_idle").inc()
            return

        # Geri basınç: boş slot yoksa kareyi AT, bekleme.
        slot = self._allocator.acquire()
        if slot is None:
            self.stats.dropped_no_slot += 1
            metrics.frames_dropped.labels(cam=self.camera, reason="no_slot").inc()
            return

        try:
            # ─── MODEL GİRDİSİ HAZIRLIĞI ────────────────────
            # Kare paylaşımlı belleğe HAM değil, model uzayında yazılır
            # (640×640 letterbox). Bu iş bilinçli olarak BURADA yapılıyor:
            # burası 20 kamera iş parçacığına dağılıyor ve `cv2.resize`
            # GIL'i bıraktığı için gerçekten paralel koşuyor. Aynı işi
            # TEK süreç olan çıkarım worker'ında yapmak seri kalır ve
            # hiçbir şey kazandırmaz (ölçüldü: net kazanç ~0).
            # Ölçüm ve gerekçe: core/preprocess.py modül başlığı.
            prepared, box = preprocess.letterbox(image)
            ref = self._pool.write(slot, prepared)
            self._stream.publish(
                FrameMessage(
                    message_id="",
                    camera=self.camera,
                    sequence=frame.sequence,  # type: ignore[attr-defined]
                    captured_at=frame.timestamp,  # type: ignore[attr-defined]
                    pts=frame.pts_seconds,  # type: ignore[attr-defined]
                    ref=ref,
                    motion_ratio=decision.foreground_ratio,
                    gate_reason=decision.reason.value,
                    letterbox=box,
                )
            )
        except Exception:
            # Yayınlayamadıysak slotu geri ver, yoksa havuz sızar
            self._allocator.release(slot)
            self.stats.dropped_no_slot += 1
            metrics.frames_dropped.labels(cam=self.camera, reason="publish_error").inc()
            raise
        else:
            self.stats.published += 1
            metrics.frames_published.labels(cam=self.camera).inc()


class IngestWorker:
    """Bir grup kamerayı yöneten worker."""

    def __init__(
        self,
        cameras: list[str],
        *,
        worker_id: str = "ingest-0",
        own_pool: bool = False,
        target_fps: float | None = None,
    ) -> None:
        self.cameras = cameras
        self.worker_id = worker_id
        self._own_pool = own_pool
        self._target_fps = target_fps if target_fps is not None else float(settings.target_fps)
        self._client = connect()
        self._allocator = SlotAllocator(self._client, settings.shm_slot_count)
        self._stream = FrameStream(self._client)
        self._tasks: list[CameraTask] = []
        self._watched_cache: set[str] = set()
        # Son uygulanan kapasite tavanı — yalnızca değişince loglamak için
        self._capacity_cap: float | None = None
        self._threads: list[threading.Thread] = []

        try:
            self._pool = FramePool(
                slot_count=settings.shm_slot_count,
                slot_bytes=preprocess.slot_bytes(),
                create=own_pool,
            )
        except FramePoolError:
            if own_pool:
                raise
            log.info("havuz_yok_olusturuluyor")
            self._pool = FramePool(
                slot_count=settings.shm_slot_count,
                slot_bytes=preprocess.slot_bytes(),
                create=True,
            )
            self._own_pool = True

        if self._own_pool:
            # SIRA ÖNEMLİ: önce akışı temizle, sonra slotları dağıt.
            # Ters sırada, eski mesajları okuyan bir tüketici slotları
            # ikinci kez serbest bırakır ve havuz bozulur (P-10).
            self._stream.reset()
            self._allocator.reset()

    def start(self) -> None:
        log.info(
            "ingest_worker_basliyor",
            worker=self.worker_id,
            cameras=len(self.cameras),
            target_fps=self._target_fps,
            pool_mb=round(self._pool.total_bytes / 1024**2, 1),
            slots=self._pool.slot_count,
        )
        metrics.worker_up.labels(component="ingest", worker_id=self.worker_id).set(1)

        for camera in self.cameras:
            task = CameraTask(
                camera,
                self._pool,
                self._allocator,
                self._stream,
                target_fps=self._target_fps,
            )
            thread = threading.Thread(target=task.run, name=f"cam:{camera}", daemon=True)
            self._tasks.append(task)
            self._threads.append(thread)
            thread.start()

    def refresh_watched(self) -> None:
        """İzlenen kamera listesini ve TÜKETİCİ KAPASİTESİNİ tazeler.

        Panel hangi kutucukları açtığını bildiriyor (WS `watching`
        mesajı). Liste TTL'li: panel kapanırsa kendiliğinden silinir ve
        tüm kameralar taban hıza döner.

        Bütçe koruması: izlenen kamera sayısı arttıkça kamera başına
        pay düşer. Aksi hâlde 20 kutucuk birden açıldığında üretim
        tüketimi ikiye katlar, kuyruk dolar ve gecikme geri gelirdi
        (P-16 / P-25 ile aynı tuzak).
        """
        try:
            watched = get_watched_cameras(self._client)
        except Exception:
            return

        self._refresh_capacity()

        budget = float(settings.watched_fps_budget)
        per_camera = (
            min(float(settings.target_fps_watched), budget / len(watched))
            if watched
            else 0.0
        )
        for task in self._tasks:
            task.watched = task.camera in watched
            task.watched_fps = per_camera

        if watched != self._watched_cache:
            log.info(
                "izlenen_kameralar_degisti",
                sayi=len(watched),
                kamera_basina_fps=round(per_camera, 1),
            )
            self._watched_cache = watched

    def _refresh_capacity(self) -> None:
        """Tüketici kapasitesini okuyup kamera başına tavan hıza çevirir.

        ⚠ NEDEN — ÖLÇÜLEN İSRAF
        -----------------------
        18.08.2026: alım 80 kare/sn üretiyor, çıkarım ~6 kare/sn
        tüketiyor, **karelerin %89'u atılıyor.** Atmak gecikmeyi
        sınırlıyor (P-25, doğru karar) ama israfı çözmüyor: atılan her
        kare için decode + BGR dönüşümü + letterbox CPU'su ZATEN
        ödenmiş oluyor. BGR dönüşümü alım maliyetinin %77'si (P-09).

        Ve o CPU boşa gitmiyor sadece — aynı çekirdekleri paylaşan
        çıkarım sürecinden ÇALINIYOR. Poz'un izole ölçümde 2.77 ms,
        boru hattında 99.8 ms sürmesinin sebebi bu çekişme.

        Yani üretimi kısmak tüketimi HIZLANDIRIYOR. Alışılmadık ama
        mekanizma net: daha az kare → daha az alım CPU'su → çıkarıma
        daha çok çekirdek → kare başına daha hızlı işleme.

        ⚠ GÜVENLİK PAYI (%85)
        Tam kapasiteyi hedeflemek kuyruğu dolu tutar; dolu kuyruk
        dengede bile gecikme üretir (P-25'in ana dersi). Hedefi
        kapasitenin biraz altına koymak kuyruğun BOŞALMASINI sağlıyor.

        ⚠ TABAN HIZ
        Kapasite ne kadar düşerse düşsün kamera başına hız
        `target_fps_idle`ın (1 FPS) altına inmiyor. Sıfıra yaklaşan bir
        kamera kördür; gözetim sisteminde bu kabul edilemez. Kapasite
        gerçekten yetmiyorsa doğru cevap kamerayı köreltmek değil,
        raporda "bu donanım N kamera kaldırıyor" demektir (R2).
        """
        kapasite = get_pipeline_capacity(self._client)
        if kapasite is None or kapasite <= 0:
            # Çıkarım worker'ı yok ya da henüz ölçmedi — yapılandırılmış
            # taban hızlarla devam. Kısıtlamamak, yanlış kısıtlamaktan iyi.
            if self._capacity_cap is not None:
                log.info("kapasite_bilgisi_kayboldu_taban_hiza_donuluyor")
                self._capacity_cap = None
                for task in self._tasks:
                    task.capacity_fps = None
            return

        kullanilabilir = kapasite * CAPACITY_SAFETY
        kamera_basina = max(
            float(settings.target_fps_idle),
            min(float(settings.target_fps), kullanilabilir / max(1, len(self._tasks))),
        )

        for task in self._tasks:
            task.capacity_fps = kamera_basina

        # Yalnızca anlamlı değişimde logla — 5 saniyede bir satır basmak
        # gerçek olayları log içinde boğar.
        onceki = self._capacity_cap
        if onceki is None or abs(kamera_basina - onceki) >= 0.2:
            log.info(
                "kapasite_butcesi_guncellendi",
                tuketici_fps=round(kapasite, 1),
                kamera_basina_tavan=round(kamera_basina, 2),
                kamera=len(self._tasks),
            )
            self._capacity_cap = kamera_basina

    def stop(self) -> None:
        _shutdown.set()
        for thread in self._threads:
            thread.join(timeout=5.0)
        metrics.worker_up.labels(component="ingest", worker_id=self.worker_id).set(0)
        self._pool.close()
        self._client.close()
        log.info("ingest_worker_durdu", worker=self.worker_id)

    def update_pipeline_metrics(self) -> None:
        metrics.shm_slots_free.set(self._allocator.available)
        metrics.queue_depth.labels(queue=self._stream.name).set(self._stream.depth)

    def summary(self) -> str:
        total_recv = sum(t.stats.received for t in self._tasks)
        total_pub = sum(t.stats.published for t in self._tasks)
        total_gate = sum(t.stats.dropped_gate for t in self._tasks)
        total_slot = sum(t.stats.dropped_no_slot for t in self._tasks)
        total_fps = sum(t.stats.fps for t in self._tasks)
        alive = sum(1 for t in self._threads if t.is_alive())
        return (
            f"{alive}/{len(self._tasks)} kamera · "
            f"{total_fps:5.1f} FPS toplam · "
            f"alınan {total_recv} · yayınlanan {total_pub} · "
            f"elenen {total_gate} · slot yok {total_slot} · "
            f"boş slot {self._allocator.available}/{settings.shm_slot_count} · "
            f"kuyruk {self._stream.depth}"
            + (
                f" · tavan {self._capacity_cap:.1f} FPS/kam"
                if self._capacity_cap is not None
                else " · tavan yok"
            )
        )

    def per_camera_table(self) -> str:
        lines = [f"{'KAMERA':<16} {'FPS':>6} {'ALINAN':>8} {'YAYIN':>8} {'ELENEN':>8} {'GEÇEN%':>7}"]
        lines.append("-" * len(lines[0]))
        for task in sorted(self._tasks, key=lambda t: t.camera):
            s = task.stats
            lines.append(
                f"{s.camera:<16} {s.fps:>6.2f} {s.received:>8} {s.published:>8} "
                f"{s.dropped_gate:>8} {s.pass_ratio * 100:>6.1f}%"
            )
        return "\n".join(lines)


# ─── CLI ──────────────────────────────────────────────────────


def _resolve_cameras(args: argparse.Namespace) -> list[str]:
    if args.all:
        return [f"cam-{i:02d}" for i in range(1, settings.camera_count + 1)]
    if args.cameras:
        return list(args.cameras)
    return ["cam-test-motion"]


def main() -> int:
    parser = argparse.ArgumentParser(description="SENTINEL alım worker'ı")
    parser.add_argument("--cameras", nargs="*", help="Okunacak kameralar")
    parser.add_argument("--all", action="store_true", help=f"cam-01..cam-{settings.camera_count}")
    parser.add_argument("--worker-id", default="ingest-0")
    parser.add_argument("--owner", action="store_true", help="Paylaşımlı bellek havuzunu bu worker oluştursun")
    parser.add_argument("--fps", type=float, default=None, help="Hedef örnekleme FPS'i")
    parser.add_argument("--metrics-port", type=int, default=9101)
    parser.add_argument("--duration", type=float, default=None, help="N saniye sonra dur (test)")
    parser.add_argument("--stats-interval", type=float, default=5.0)
    args = parser.parse_args()

    configure_logging(settings.log_level)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    cameras = _resolve_cameras(args)
    metrics.serve_metrics(args.metrics_port)
    log.info("metrik_sunucusu", port=args.metrics_port)

    worker = IngestWorker(
        cameras,
        worker_id=args.worker_id,
        own_pool=args.owner,
        target_fps=args.fps,
    )
    worker.start()

    deadline = time.monotonic() + args.duration if args.duration else None
    try:
        # ⚠ İki farklı ritim: izlenen kamera listesi HIZLI tazelenmeli
        # (operatör kutucuk açınca birkaç saniyede etkisini görmeli),
        # istatistik raporu ise seyrek basılır. Tek bir uzun bekleme
        # kullansaydık panel değişikliği 5 dakika sonra etki ederdi.
        watch_tick_s = 5.0
        next_stats = time.monotonic() + args.stats_interval
        while not _shutdown.is_set():
            _shutdown.wait(watch_tick_s)
            if _shutdown.is_set():
                break
            worker.refresh_watched()

            now = time.monotonic()
            if now >= next_stats:
                worker.update_pipeline_metrics()
                print(f"  {worker.summary()}", flush=True)
                next_stats = now + args.stats_interval
            if deadline and now >= deadline:
                break
    finally:
        print()
        print(worker.per_camera_table())
        print()
        print(f"  {worker.summary()}")
        worker.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
