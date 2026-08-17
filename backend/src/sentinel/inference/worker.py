"""GPU çıkarım worker'ı — KADEME 1.

Mimarideki yeri
---------------
Alım worker'larının paylaşımlı belleğe yazdığı kareleri okur, **kameralar
arası toplu (batch)** olarak modele verir, sonuçları JSON olarak
`inference.results` akışına yazar ve slotu havuza geri verir.

⚠ TEK KOPYA KURALI
------------------
Sistemde **yalnızca bir** çıkarım süreci çalışır. Sebep VRAM: her süreç
model ağırlıklarının kendi kopyasını yükler. 4 süreç × ~4.6 GB = 18 GB,
elimizde 8 GB var (PLAN.md §2.2). Ayrıca tek süreç, 20 kameradan gelen
kareleri tek batch'te işleyerek GPU verimini kat kat artırır.

Toplu işlemenin önemi
---------------------
GPU'da her çekirdek başlatmanın sabit bir maliyeti vardır. 8 kareyi tek
seferde vermek, 8 kez tek kare vermekten çok daha ucuzdur. Batch,
Valkey tüketici grubundan doğal olarak gelir: `XREADGROUP COUNT=N`.

Kullanım
--------
    uv run python -m sentinel.inference.worker
    uv run python -m sentinel.inference.worker --batch-size 8 --duration 60
    uv run python -m sentinel.inference.worker --model models/yolo26s-pose.pt
"""

from __future__ import annotations

import argparse
import json
import signal
import statistics
import sys
import time
from collections import Counter, deque
from dataclasses import replace
from types import FrameType

from sentinel import metrics
from sentinel.bus.shm import FramePool, FramePoolError
from sentinel.bus.streams import FrameStream, ResultStream, SlotAllocator, connect
from sentinel.config import settings
from sentinel.core import preprocess
from sentinel.core.preprocess import Letterbox
from sentinel.inference.detector.base import Detection, Detector
from sentinel.inference.pose.base import PoseEstimator
from sentinel.inference.tracker.base import Track
from sentinel.inference.tracker.botsort import BotSortTracker
from sentinel.logging import configure_logging, get_logger

log = get_logger(__name__)

GROUP = "inference"
_stop = False


def _handle_signal(_sig: int, _frame: FrameType | None) -> None:
    global _stop
    _stop = True
    log.info("kapatma_sinyali_alindi")


def build_detector(
    model_path: str,
    *,
    backend: str,
    device: str,
    half: bool,
    imgsz: int,
    conf: float,
) -> Detector:
    """Konfigürasyona göre dedektör örneği üretir.

    Yeni bir arka uç eklemek (RTMDet, RT-DETR) yalnızca buraya bir dal
    eklemek demektir; çağıran kod `Detector` protokolüne bağlıdır.
    """
    if backend in {"yolo26", "yolo11", "yolo"}:
        from sentinel.inference.detector.yolo import UltralyticsDetector

        return UltralyticsDetector(
            model_path,
            backend_name=backend,
            device=device,
            half=half,
            imgsz=imgsz,
            conf_threshold=conf,
        )
    raise ValueError(f"Bilinmeyen dedektör arka ucu: {backend}")


def build_pose_estimator(model_path: str, *, device: str, half: bool) -> PoseEstimator:
    """KADEME 2a poz tahmincisini kurar.

    Neden dedektörden ayrı bir model: poz ağırlığı tek başına
    kullanıldığında tespit modelinin bulduğu kişilerin yalnızca %43'ünü
    buluyor (küçük/uzak kutuları kaçırıyor). Ölçüm ve karar:
    `inference/pose/base.py` · benchmarks/pose_20260815-153539.json
    """
    from sentinel.inference.pose.yolo import YoloPoseEstimator

    return YoloPoseEstimator(
        model_path,
        device=device,
        half=half,
        crop_size=settings.pose_crop_size,
        crop_batch=settings.pose_crop_batch,
        conf_threshold=settings.pose_conf_threshold,
    )


def _to_source_space(data: dict[str, object], box: Letterbox) -> dict[str, object]:
    """Bir tespitin koordinatlarını model uzayından kaynak kareye taşır.

    ⚠ Bu adım atlanırsa kutular tarayıcıda YANLIŞ YERE çizilir ve hata
    sessizdir: koordinatlar geçerli sayılardır, sadece 640×640 uzayına
    aittir. Kaynak kare 1280×720 olduğu için kutular sol üst köşeye
    toplanmış ve küçülmüş görünür.

    Taşınması gereken üç şey var: kutu köşeleri, iskelet noktaları ve
    hız vektörü. Hız bir FARK olduğu için dolgu payı eklenmez, yalnızca
    ölçek uygulanır (bkz. Letterbox.to_source_length).
    """
    bbox = data.get("bbox")
    if isinstance(bbox, list) and len(bbox) == 4:
        x1, y1, x2, y2 = box.to_source_box(*(float(v) for v in bbox))
        data["bbox"] = [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)]

    keypoints = data.get("kp")
    if isinstance(keypoints, list):
        data["kp"] = [
            [
                round((float(point[0]) - box.pad_x) / box.scale, 1),
                round((float(point[1]) - box.pad_y) / box.scale, 1),
                point[2],
            ]
            for point in keypoints
        ]

    velocity = data.get("v")
    if isinstance(velocity, list) and len(velocity) == 2:
        data["v"] = [
            round(box.to_source_length(float(velocity[0]))),
            round(box.to_source_length(float(velocity[1]))),
        ]
    return data


def _serialize(
    tracks: list[Track],
    *,
    motion: float,
    gate: str,
    width: int,
    height: int,
    letterbox: Letterbox | None = None,
    latency_ms: float = 0.0,
) -> str:
    """Sonucu JSON'a çevirir.

    Kaynak kare boyutu (`w`, `h`) mutlaka gönderilir: kutular piksel
    koordinatındadır ve tarayıcı bunları kendi görüntü alanına
    ölçeklemek zorundadır. Kameralar farklı çözünürlükte olabilir
    (örn. cam-12 960×720), sabit bir varsayım yanlış çizime yol açar.

    Her iz kimliği (`id`) ve hız vektörü (`v`) taşır — tarayıcı iki
    tespit arasında kutunun konumunu bunlarla tahmin eder.

    ⚠ Kareler alım tarafında model uzayına (640×640 letterbox)
    taşındığı için tespitler de o uzayda çıkar. Tarayıcıya gitmeden
    önce kaynak piksel uzayına geri çevriliyorlar.
    """
    detections = [t.to_dict() for t in tracks]
    if letterbox is not None:
        detections = [_to_source_space(d, letterbox) for d in detections]

    return json.dumps(
        {
            "w": width,
            "h": height,
            "motion": round(motion, 5),
            "gate": gate,
            "count": len(tracks),
            # Bu karenin ANALİZ YOLUNDA harcadığı süre (ms). Tarayıcı
            # bunu videonun kendi gecikmesiyle karşılaştırıp kutuları
            # ne kadar geriden çizmesi gerektiğini HESAPLAYABİLİYOR —
            # kullanıcının gözüyle tahmin etmesine gerek kalmıyor.
            "lat": round(latency_ms),
            "detections": detections,
        },
        separators=(",", ":"),
    )


class InferenceWorker:
    """Kare akışını tüketip tespit sonucu üreten worker."""

    def __init__(
        self,
        detector: Detector,
        *,
        pose: PoseEstimator | None = None,
        worker_id: str = "inference-0",
        batch_size: int = 8,
        block_ms: int = 500,
        max_age_ms: int = 0,
    ) -> None:
        self._detector = detector
        self._pose = pose
        self._worker_id = worker_id
        self._batch_size = batch_size
        self._block_ms = block_ms
        self._max_age_s = max_age_ms / 1000.0 if max_age_ms > 0 else 0.0
        # Kamera başına ayrı takipçi durumu (bkz. tracker/botsort.py)
        self._tracker = BotSortTracker(frame_rate=int(settings.target_fps))

        self._client = connect()
        self._frames = FrameStream(self._client)
        self._results = ResultStream(self._client)
        self._allocator = SlotAllocator(self._client, settings.shm_slot_count)
        self._frames.ensure_group(GROUP)

        try:
            self._pool = FramePool(
                slot_count=settings.shm_slot_count, slot_bytes=preprocess.slot_bytes()
            )
        except FramePoolError as exc:
            raise SystemExit(f"HATA: {exc}") from exc

        # İstatistik
        self.processed = 0
        self.dropped_stale = 0
        self.detections_total = 0
        self.batches = 0
        self.by_camera: Counter[str] = Counter()
        self.batch_sizes: deque[int] = deque(maxlen=200)
        self.infer_ms: deque[float] = deque(maxlen=500)
        self.pose_ms: deque[float] = deque(maxlen=500)
        self.track_ms: deque[float] = deque(maxlen=500)
        self.e2e_ms: deque[float] = deque(maxlen=500)
        # Boru hattı muhasebesi: batch başına toplam süre nereye gidiyor?
        self.wait_ms: deque[float] = deque(maxlen=500)
        self.read_ms: deque[float] = deque(maxlen=500)
        self.publish_ms: deque[float] = deque(maxlen=500)
        self.release_ms: deque[float] = deque(maxlen=500)
        # Aralık hızı için pencere durumu (bkz. summary)
        self._window_started = 0.0
        self._window_processed = 0

    def warmup(self) -> None:
        self._detector.warmup(self._batch_size)
        if self._pose is not None:
            self._pose.warmup(settings.pose_crop_batch)

    def run(self, *, duration: float | None = None, stats_interval: float = 5.0) -> None:
        info = self._detector.info
        log.info(
            "cikarim_worker_basliyor",
            worker=self._worker_id,
            backend=info.backend,
            device=info.device,
            precision=info.precision,
            pose=self._pose is not None,
            batch_size=self._batch_size,
        )
        metrics.worker_up.labels(component="inference", worker_id=self._worker_id).set(1)

        started = time.monotonic()
        last_report = started
        self._window_started = started
        self._window_processed = 0
        deadline = started + duration if duration else None

        while not _stop:
            # ⚠ BEKLEME SÜRESİ AYRI ÖLÇÜLÜYOR
            # "Kare başına 16 ms harcıyoruz ama 62 değil 25 FPS alıyoruz"
            # açığını kapatmak için: döngünün ne kadarı iş, ne kadarı
            # kare beklemek? İkisi karışırsa hangi tarafı iyileştireceğimizi
            # bilemeyiz (üretici mi yavaş, tüketici mi).
            t_wait = time.perf_counter()
            batch = list(
                self._frames.consume(
                    GROUP, self._worker_id, count=self._batch_size, block_ms=self._block_ms
                )
            )
            self.wait_ms.append((time.perf_counter() - t_wait) * 1000.0)
            if batch:
                batch = self._drop_stale(batch)
            if batch:
                self._run_batch(batch)

            now = time.monotonic()
            if now - last_report >= stats_interval:
                self._report(now, now - started)
                last_report = now
            if deadline and now >= deadline:
                break

        self._finish(time.monotonic() - started)

    # ─── İç işler ────────────────────────────────────────────

    def _run_batch(self, batch: list) -> None:  # type: ignore[type-arg]
        # Kareleri paylaşımlı bellekten oku — kopyalama yok
        t_read = time.perf_counter()
        images = [self._pool.read(message.ref) for message in batch]
        self.read_ms.append((time.perf_counter() - t_read) * 1000.0)

        t0 = time.perf_counter()
        try:
            results = self._detector.detect(images)
        except Exception as exc:
            log.error("cikarim_hatasi", error=f"{type(exc).__name__}: {exc}", batch=len(batch))
            self._release(batch)
            return
        infer_s = time.perf_counter() - t0

        self.batches += 1
        self.batch_sizes.append(len(batch))
        per_frame_ms = infer_s / len(batch) * 1000.0
        self.infer_ms.append(per_frame_ms)
        metrics.inference_duration.labels(stage="detect").observe(infer_s / len(batch))
        metrics.batch_size.observe(len(batch))

        # ─── KADEME 2a: poz ─────────────────────────────────
        # Takipten ÖNCE çalışır. Sebep: takipçi keypoint'leri kaynak
        # tespitten `det_idx` üzerinden taşıyor (botsort.py); iskeleti
        # tespite şimdi yazarsak kimlikle birlikte kendiliğinden gidiyor.
        #
        # Kırpıntılar tüm kameralardan tek havuzda toplanıp birlikte
        # GPU'ya verilir — batch 8'de kırpıntı başına 2.84 ms, batch
        # 32'de 1.30 ms (ölçüm: benchmarks/pose_20260815-153539.json).
        if self._pose is not None and any(results):
            t_pose = time.perf_counter()
            try:
                poses = self._pose.estimate(images, results)
            except Exception as exc:
                log.error("poz_hatasi", error=f"{type(exc).__name__}: {exc}")
            else:
                results = [
                    self._attach_keypoints(detections, frame_poses)
                    for detections, frame_poses in zip(results, poses, strict=True)
                ]
                pose_s = time.perf_counter() - t_pose
                metrics.inference_duration.labels(stage="pose").observe(pose_s / len(batch))
                self.pose_ms.append(pose_s / len(batch) * 1000.0)

        # ─── KADEME 1b: takip ───────────────────────────────
        # Tespitler kimliksizdir. Takipçi her kişiye kalıcı bir kimlik
        # ve hız vektörü verir. Kamera bazlı sıralı işlenmeli — batch
        # içindeki mesajlar zaten akış sırasında geliyor.
        t1 = time.perf_counter()
        tracked: list[list[Track]] = [
            self._tracker.update(m.camera, d, m.captured_at)
            for m, d in zip(batch, results, strict=True)
        ]
        track_s = time.perf_counter() - t1
        metrics.inference_duration.labels(stage="track").observe(track_s / len(batch))
        self.track_ms.append(track_s / len(batch) * 1000.0)

        now_monotonic = time.monotonic()
        t_publish = time.perf_counter()
        for message, detections in zip(batch, tracked, strict=True):
            source_w, source_h = message.source_size
            latency = (now_monotonic - message.captured_at) * 1000.0
            payload = _serialize(
                detections,
                motion=message.motion_ratio,
                gate=message.gate_reason,
                width=source_w,
                height=source_h,
                letterbox=message.letterbox,
                latency_ms=latency,
            )
            self._results.publish(
                message.camera,
                payload,
                sequence=message.sequence,
                captured_at=message.captured_at,
            )
            self.processed += 1
            self.detections_total += len(detections)
            self.by_camera[message.camera] += 1
            metrics.detections_found.labels(cam=message.camera).inc(len(detections))
            # Uçtan uca gecikme: kare yakalandığından sonuç yazılana kadar
            self.e2e_ms.append(latency)
            metrics.end_to_end_latency.observe(latency / 1000.0)
        self.publish_ms.append((time.perf_counter() - t_publish) * 1000.0)

        t_release = time.perf_counter()
        self._release(batch)
        self.release_ms.append((time.perf_counter() - t_release) * 1000.0)

    @staticmethod
    def _attach_keypoints(
        detections: list[Detection], poses: list  # type: ignore[type-arg]
    ) -> list[Detection]:
        """İskeleti tespit kaydına yazar.

        `Detection` dondurulmuş (frozen) bir dataclass — yerinde
        değiştirilemez, `replace` ile yeni kayıt üretiliyor. Bu bilinçli:
        tespit sonucu boru hattında paylaşılıyor ve kazara mutasyon
        hata ayıklaması zor sorunlar üretir.
        """
        out: list[Detection] = []
        for detection, pose in zip(detections, poses, strict=True):
            if pose is None:
                out.append(detection)
                metrics.pose_crops.labels(result="empty").inc()
            else:
                out.append(replace(detection, keypoints=pose.keypoints))
                metrics.pose_crops.labels(result="skeleton").inc()
        return out

    def _drop_stale(self, batch: list) -> list:  # type: ignore[type-arg]
        """Çok eskimiş kareleri İŞLEMEDEN atar.

        ⚠ BU, GECİKMEYİ SINIRLAYAN TEK MEKANİZMA
        ----------------------------------------
        "Eski kare değersizdir" ilkesini P-12'den beri söylüyoruz ama
        şimdiye kadar yalnızca ÜRETİCİ tarafında uyguluyorduk (slot
        yoksa at). Tüketici tarafında hiç uygulanmıyordu: kuyruğa giren
        kare, ne kadar beklerse beklesin sonunda işleniyordu.

        Sonucu şuydu: sistem yüklendiğinde kuyruk doluyor ve her kare
        sırasını beklerken eskiyor. 48 slot ÷ 29 kare/sn ≈ 1.65 sn.
        Ölçülen gecikme 1212 ms — kutular videodan 2-3 adım geriden
        geliyordu.

        Eski kareyi işlemek iki kez zarar veriyor: (1) sonucu zaten
        değersiz, (2) o sırada TAZE kare işlenemiyor. Atmak her iki
        sorunu da çözüyor ve sistem kendi kendini toparlıyor —
        birikim ne kadar büyükse o kadar hızlı eritiliyor.

        Bu bir "kare kaybı" değil, gecikme bütçesinin korunmasıdır.
        Atılan kareler `sentinel_frames_dropped_total{reason="stale"}`
        ile sayılıyor; sürekli artıyorsa sistem gerçekten yetişemiyor
        demektir ve bu bilgi gizlenmemeli.
        """
        if self._max_age_s <= 0:
            return batch

        now = time.monotonic()
        fresh = [m for m in batch if now - m.captured_at <= self._max_age_s]
        stale = [m for m in batch if now - m.captured_at > self._max_age_s]
        if stale:
            self._release(stale)
            self.dropped_stale += len(stale)
            for message in stale:
                metrics.frames_dropped.labels(cam=message.camera, reason="stale").inc()
        return fresh

    def _release(self, batch: list) -> None:  # type: ignore[type-arg]
        """Slotları havuza geri ver ve mesajları onayla.

        Bu ikisi ATLANIRSA sistem kilitlenir: üretici boş slot bulamaz.
        Hata yolunda bile çağrılmalı (P-10).
        """
        self._allocator.release_many([m.ref.slot for m in batch])
        self._frames.ack(GROUP, *[m.message_id for m in batch])

    def budget(self) -> str:
        """Batch başına sürenin nereye gittiğinin dökümü.

        "Kare başına 16 ms harcıyoruz ama 62 değil 25 FPS alıyoruz"
        açığını bu tablo kapatır: GPU dışındaki her adım da zaman yiyor
        ve tek tek küçük görünen maliyetler batch başına toplanınca
        modelin maliyetini geçebiliyor.
        """
        b = statistics.fmean(self.batch_sizes) if self.batch_sizes else 1.0
        rows = [
            ("bekleme (kare yok)", self._p50(self.wait_ms)),
            ("shm okuma", self._p50(self.read_ms)),
            ("tespit", self._p50(self.infer_ms) * b),
            ("poz", self._p50(self.pose_ms) * b),
            ("takip", self._p50(self.track_ms) * b),
            ("yayınlama (Valkey)", self._p50(self.publish_ms)),
            ("slot iadesi + ack", self._p50(self.release_ms)),
        ]
        total = sum(v for _, v in rows)
        lines = [f"  {'ADIM':<22} {'ms/batch':>9} {'pay':>7} {'ms/kare':>9}", "  " + "-" * 50]
        for name, value in rows:
            share = value / total * 100 if total else 0
            lines.append(f"  {name:<22} {value:>9.2f} {share:>6.1f}% {value / b:>9.2f}")
        lines.append("  " + "-" * 50)
        lines.append(f"  {'TOPLAM':<22} {total:>9.2f} {100.0:>6.1f}% {total / b:>9.2f}")
        if total:
            lines.append(f"  Teorik tavan: {1000.0 / (total / b):.1f} FPS (batch {b:.1f})")
        return "\n".join(lines)

    def _report(self, now: float, elapsed: float) -> None:
        metrics.shm_slots_free.set(self._allocator.available)
        metrics.queue_depth.labels(queue=self._frames.name).set(self._frames.depth)
        metrics.queue_depth.labels(queue=self._results.name).set(self._results.depth)
        print(f"  {self.summary(elapsed, since=now)}", flush=True)

    @staticmethod
    def _p50(samples: deque[float]) -> float:
        """Medyan.

        ⚠ Kasıtlı olarak ortalama DEĞİL. Worker her başladığında kuyrukta
        birikmiş kareleri bulur ve ilk saniyelerde hem soğuk çekirdeklerle
        hem birikimle boğuşur; bu tek seferlik sıçramalar ortalamayı
        kalıcı olarak yukarı çeker ve sistem sanki yavaşmış gibi görünür.
        Aynı gerekçe Gün 4 ölçümünde de yazılmıştı.
        """
        if not samples:
            return 0.0
        ordered = sorted(samples)
        return ordered[len(ordered) // 2]

    def summary(self, elapsed: float, *, since: float | None = None) -> str:
        """Özet satırı.

        `since` verilirse FPS **son aralık** için hesaplanır. Kümülatif
        FPS yanıltıcıdır: başlangıçtaki birikim kapatılırken düşük olan
        hız, sistem toparlansa bile ortalamayı saatlerce aşağıda tutar.
        Gerçek soru "şu anda kaç kare işliyoruz" olduğu için aralık hızı
        raporlanıyor.
        """
        if since is not None:
            window = since - self._window_started
            fps = (self.processed - self._window_processed) / window if window > 0 else 0.0
            self._window_started, self._window_processed = since, self.processed
        else:
            fps = self.processed / elapsed if elapsed > 0 else 0.0

        avg_batch = statistics.fmean(self.batch_sizes) if self.batch_sizes else 0
        active = self._tracker.stats["active_tracks"]
        pose_part = f"poz {self._p50(self.pose_ms):5.1f} ms · " if self.pose_ms else ""
        return (
            f"{self.processed:>6} kare · {fps:5.1f} FPS · "
            f"tespit {self._p50(self.infer_ms):5.1f} ms · {pose_part}"
            f"takip {self._p50(self.track_ms):4.2f} ms · "
            f"batch {avg_batch:4.1f} · {active:>3} aktif iz · "
            f"gecikme {self._p50(self.e2e_ms):5.0f} ms · "
            f"boş slot {self._allocator.available}/{settings.shm_slot_count}"
            + (f" · eski atılan {self.dropped_stale}" if self.dropped_stale else "")
        )

    def _finish(self, elapsed: float) -> None:
        info = self._detector.info
        print()
        print(f"{'KAMERA':<16} {'KARE':>7} {'TESPİT':>8} {'FPS':>7}")
        print("-" * 42)
        for camera, count in sorted(self.by_camera.items()):
            print(f"{camera:<16} {count:>7} {'':>8} {count / elapsed:>7.2f}")
        print()
        print(f"  {self.summary(elapsed)}")
        if self.infer_ms:
            ordered = sorted(self.infer_ms)
            print(
                f"  Çıkarım ms/kare — ortalama {statistics.fmean(ordered):.2f} · "
                f"p50 {ordered[len(ordered) // 2]:.2f} · "
                f"p95 {ordered[int(len(ordered) * 0.95) - 1]:.2f}"
            )
        print()
        print("SÜRE BÜTÇESİ (batch başına, p50)")
        print(self.budget())
        print()
        print(f"  Model: {info.backend} · {info.precision} · {info.device}")
        if self._pose is not None:
            stats = getattr(self._pose, "stats", None)
            if stats:
                print(
                    f"  Poz  : {stats['crops_total']} kırpıntı · "
                    f"iskelet çıkan %{stats['skeleton_hit_rate'] * 100:.1f}"
                )

        # Kimlik kararlılığı (PLAN.md §6.1): zamansal analizin tamamı
        # buna dayanıyor. Parçalanma oranı yüksekse "bu kişi 3 saniyedir
        # hızlanıyor" cümlesi kurulamaz.
        t = self._tracker.stats
        if t["finished_tracks"]:
            print(
                f"  Takip: {t['total_tracks']} iz · biten {t['finished_tracks']} · "
                f"parçalanma %{t['fragmentation_rate'] * 100:.1f} · "
                f"medyan ömür {t['median_lifetime_frames']} kare"
            )

        metrics.worker_up.labels(component="inference", worker_id=self._worker_id).set(0)
        if self._pose is not None:
            self._pose.close()
        self._detector.close()
        self._pool.close()
        self._client.close()


# ─── CLI ──────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="SENTINEL GPU çıkarım worker'ı")
    parser.add_argument("--model", default=None, help="Ağırlık dosyası")
    parser.add_argument("--backend", default=None, help="yolo26 | yolo11")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=None)
    parser.add_argument("--no-half", action="store_true", help="FP16 yerine FP32")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument(
        "--no-pose",
        action="store_true",
        help="KADEME 2a'yı kapat (GPU bütçesi sıkışırsa ilk kısılacak yer)",
    )
    parser.add_argument("--pose-model", default=None, help="Poz ağırlığı")
    parser.add_argument(
        "--max-frame-age-ms",
        type=int,
        default=None,
        help="Bu yaştan eski kareler İŞLENMEDEN atılır (0 = kapalı). "
             "Gecikmeyi sınırlayan mekanizma budur.",
    )
    parser.add_argument("--worker-id", default="inference-0")
    parser.add_argument("--metrics-port", type=int, default=9110)
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--stats-interval", type=float, default=5.0)
    args = parser.parse_args()

    configure_logging(settings.log_level)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    metrics.serve_metrics(args.metrics_port)

    detector = build_detector(
        args.model or str(settings.detector_weights),
        backend=args.backend or settings.detector_backend,
        device=args.device,
        half=not args.no_half,
        imgsz=args.imgsz,
        conf=args.conf if args.conf is not None else settings.detector_conf_threshold,
    )

    pose: PoseEstimator | None = None
    if settings.pose_enabled and not args.no_pose:
        pose = build_pose_estimator(
            args.pose_model or str(settings.pose_weights),
            device=args.device,
            half=not args.no_half,
        )

    worker = InferenceWorker(
        detector,
        pose=pose,
        worker_id=args.worker_id,
        batch_size=args.batch_size,
        max_age_ms=(
            args.max_frame_age_ms
            if args.max_frame_age_ms is not None
            else settings.max_frame_age_ms
        ),
    )
    worker.warmup()
    worker.run(duration=args.duration, stats_interval=args.stats_interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
