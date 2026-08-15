"""BoT-SORT takipçisi — kamera başına bir örnek.

BoT-SORT nasıl çalışıyor
------------------------
İki aşamalı eşleştirme yapar:

1. **Tahmin.** Her iz için Kalman filtresi "bu nesne bir sonraki karede
   nerede olacak" diye tahmin üretir.
2. **Eşleştirme.** Yeni tespitlerle tahminler, IoU (kutu örtüşmesi)
   benzerliğine göre Macar algoritmasıyla eşleştirilir.
3. **İkinci tur.** Eşleşmeyen izler, **düşük güvenli** tespitlerle
   tekrar denenir. ByteTrack'in ana fikri budur: kısmen kapanmış bir
   kişinin güven skoru düşer ama tespit yine de oradadır; onu atmak
   yerine ikinci turda kullanmak kimlik kaybını belirgin azaltır.
4. **Kamera hareketi telafisi (CMC).** Kamera sarsılırsa tüm kutular
   birlikte kayar; BoT-SORT bunu global hareket olarak ölçüp düzeltir.
   Sabit kameralarda maliyeti boşuna olduğu için kapatıyoruz.

Neden kamera başına ayrı örnek
------------------------------
Takipçi durum tutar (aktif izler, Kalman filtreleri, kimlik sayacı).
Tek örneğe 20 kameranın tespitlerini vermek, farklı sahnelerdeki
kişileri birbirine eşleştirmeye çalışırdı. Her kamera kendi dünyası.

Bellek maliyeti önemsiz: iz başına birkaç yüz bayt.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np

from sentinel import metrics
from sentinel.inference.detector.base import Detection
from sentinel.inference.tracker.base import (
    MAX_VELOCITY_GAP_S,
    VELOCITY_ALPHA,
    DetectionBatch,
    Track,
    _History,
)
from sentinel.logging import get_logger

log = get_logger(__name__)

# Bu kadar az karede görülüp terk edilen iz "parça" (fragment) sayılır.
# Gerçek bir kişi kadrajda kalır; 1-3 karelik izler ya yanlış pozitiftir
# ya da aynı kişinin kimliğini kaybedip yenisini almasıdır. İkincisi
# tam olarak ölçmek istediğimiz şey (PLAN.md §6.1).
SHORT_TRACK_FRAMES = 3


def default_args(
    *,
    track_high_thresh: float = 0.25,
    track_low_thresh: float = 0.1,
    new_track_thresh: float = 0.25,
    track_buffer: int = 30,
    match_thresh: float = 0.8,
    fuse_score: bool = True,
) -> SimpleNamespace:
    """BoT-SORT konfigürasyonu.

    Değerler Ultralytics varsayılanlarıdır; sapılan yerler yorumlandı.
    """
    return SimpleNamespace(
        tracker_type="botsort",
        track_high_thresh=track_high_thresh,
        track_low_thresh=track_low_thresh,
        new_track_thresh=new_track_thresh,
        # track_buffer: kaybolan iz kaç kare hafızada tutulsun.
        # Bizde tespit ~3 FPS olduğu için 30 kare ≈ 10 saniye eder —
        # bir kişinin ağacın arkasından geçmesine fazlasıyla yeter.
        track_buffer=track_buffer,
        match_thresh=match_thresh,
        fuse_score=fuse_score,
        # ─── Kapatılanlar ve gerekçeleri ───
        # Kameralarımız SABİT. Kamera hareketi telafisi her karede
        # global hizalama hesaplar; sabit kamerada bedava maliyet.
        gmc_method="none",
        # ReID (görünüm eşleştirme) ayrı bir sinir ağı çalıştırır.
        # 20 kamerada GPU bütçesini aşar; hareket tabanlı eşleştirme
        # sabit kameralarda zaten yeterli. Faz 5'te ölçülüp
        # değerlendirilecek.
        with_reid=False,
        proximity_thresh=0.5,
        appearance_thresh=0.25,
        model="auto",
    )


class BotSortTracker:
    """Kamera başına BoT-SORT örneği yöneten takipçi."""

    def __init__(self, *, args: SimpleNamespace | None = None, frame_rate: int = 4) -> None:
        from ultralytics.trackers import BOTSORT

        self._cls = BOTSORT
        self._args = args or default_args()
        self._frame_rate = frame_rate
        self._trackers: dict[str, Any] = {}
        self._history: dict[str, dict[int, _History]] = {}
        self._total_tracks = 0
        self._id_switches = 0
        self._unconfirmed = 0
        self._seen_ids: dict[str, set[int]] = {}
        self._lifetimes: list[int] = []
        # Geçmişin, iz çıktı vermedikten sonra ne kadar bekletileceği.
        # Takipçinin kendi hafızasıyla (track_buffer kare) eşitliyoruz;
        # kısa tutarsak geri dönen izi "yeni" sanıp kararsızlığı olduğundan
        # yüksek ölçerdik.
        self._grace_s = self._args.track_buffer / max(1, frame_rate)

    # ─── Tracker protokolü ───────────────────────────────────

    def update(
        self, camera: str, detections: list[Detection], timestamp: float
    ) -> list[Track]:
        tracker = self._trackers.get(camera)
        if tracker is None:
            # ⚠ Ultralytics 8.4'te BOTSORT yalnızca `args` alıyor; eski
            #   sürümlerdeki `frame_rate` kwarg'ı kaldırılmış. Kare hızı
            #   bilgisi `track_buffer` üzerinden dolaylı veriliyor.
            tracker = self._cls(self._args)
            self._trackers[camera] = tracker
            self._history[camera] = {}
            self._seen_ids[camera] = set()
            log.info("takipci_olusturuldu", camera=camera)

        batch = DetectionBatch.from_detections(detections)
        # BoT-SORT (N, 8) döndürür: x1 y1 x2 y2 track_id conf cls det_idx
        raw = tracker.update(batch, img=None)

        tracks: list[Track] = []
        history = self._history[camera]
        seen = self._seen_ids[camera]
        matched_indices: set[int] = set()

        rows = np.asarray(raw) if raw is not None and len(raw) else np.empty((0, 8))
        for row in rows:
            x1, y1, x2, y2 = (float(v) for v in row[:4])
            track_id = int(row[4])
            confidence = float(row[5])
            class_id = int(row[6])
            det_index = int(row[7]) if len(row) > 7 else -1

            if track_id not in seen:
                seen.add(track_id)
                self._total_tracks += 1
                metrics.tracks_started.labels(cam=camera).inc()

            # Keypoint'leri kaynak tespitten taşı: takipçi onları bilmez,
            # ama det_idx sayesinde hangi tespitten geldiğini biliyoruz.
            keypoints = None
            if 0 <= det_index < len(detections):
                keypoints = detections[det_index].keypoints
                matched_indices.add(det_index)

            vx, vy = self._update_velocity(history, track_id, (x1, y1, x2, y2), timestamp)

            tracks.append(
                Track(
                    track_id=track_id,
                    detection=Detection(
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                        confidence=confidence,
                        class_id=class_id,
                        keypoints=keypoints,
                    ),
                    velocity_x=vx,
                    velocity_y=vy,
                    age=history[track_id].samples,
                )
            )

        # ─── ONAYLANMAMIŞ TESPİTLERİ KAYBETME ────────────────
        # BoT-SORT yeni bir izi hemen çıktı vermez: iz "onaylanmış"
        # sayılması için İKİNCİ bir karede tekrar eşleşmesi gerekir.
        # Tespit ~3 FPS olduğu için bu ~330 ms gecikme demek; kısa süre
        # görünen kişiler ise hiç görünmez.
        #
        # Bu kabul edilemez: takip, tespiti ZENGİNLEŞTİRMELİ, filtrelememeli.
        # Eşleşmemiş tespitleri kimliksiz (id=None) olarak geçiriyoruz.
        # Kutu anında görünüyor, kimlik bir sonraki karede geliyor.
        # (docs/report/problems.md · P-13)
        for index, detection in enumerate(detections):
            if index in matched_indices:
                continue
            tracks.append(Track(track_id=-1, detection=detection))
            self._unconfirmed += 1

        self._prune(camera, history, timestamp)
        return tracks

    def reset(self, camera: str | None = None) -> None:
        if camera is None:
            self._trackers.clear()
            self._history.clear()
            self._seen_ids.clear()
        else:
            self._trackers.pop(camera, None)
            self._history.pop(camera, None)
            self._seen_ids.pop(camera, None)

    @property
    def stats(self) -> dict[str, Any]:
        finished = len(self._lifetimes)
        return {
            "cameras": len(self._trackers),
            "total_tracks": self._total_tracks,
            "active_tracks": sum(len(h) for h in self._history.values()),
            "unconfirmed_passthrough": self._unconfirmed,
            # Kimlik kararlılığı (PLAN.md §6.1). "Biten izlerin yüzde
            # kaçı kısa ömürlüydü" — düşük olması iyi.
            "finished_tracks": finished,
            "short_lived_tracks": self._id_switches,
            "fragmentation_rate": round(self._id_switches / finished, 3) if finished else 0.0,
            "median_lifetime_frames": (
                sorted(self._lifetimes)[finished // 2] if finished else 0
            ),
        }

    # ─── Hız hesabı ──────────────────────────────────────────

    def _update_velocity(
        self,
        history: dict[int, _History],
        track_id: int,
        bbox: tuple[float, float, float, float],
        timestamp: float,
    ) -> tuple[float, float]:
        """Ardışık konumlardan piksel/saniye hız üretir.

        Kalman filtresinin iç hız durumunu okumak yerine kendimiz
        hesaplıyoruz. Sebep: bu yöntem takipçiden bağımsız çalışır
        (BoostTrack'e geçersek kod değişmez) ve birimi net —
        piksel/saniye, tarayıcının doğrudan kullanabileceği biçim.
        """
        x1, _y1, x2, y2 = bbox
        # Ayak noktası: kişinin zemindeki konumu. Merkez yerine bunu
        # kullanmak daha doğru — kişi kameraya yaklaşınca kutu büyür ve
        # merkez yukarı kayar, ama ayak noktası zemin düzleminde kalır.
        center = ((x1 + x2) / 2.0, y2)

        entry = history.get(track_id)
        if entry is None:
            entry = _History()
            history[track_id] = entry

        if entry.last_center is not None and entry.last_time is not None:
            dt = timestamp - entry.last_time
            if 0 < dt <= MAX_VELOCITY_GAP_S:
                raw_vx = (center[0] - entry.last_center[0]) / dt
                raw_vy = (center[1] - entry.last_center[1]) / dt
                # Üstel yumuşatma: tek karelik sıçramalar sönsün
                old_vx, old_vy = entry.velocity
                entry.velocity = (
                    VELOCITY_ALPHA * raw_vx + (1 - VELOCITY_ALPHA) * old_vx,
                    VELOCITY_ALPHA * raw_vy + (1 - VELOCITY_ALPHA) * old_vy,
                )
            elif dt > MAX_VELOCITY_GAP_S:
                # Uzun boşluktan sonra eski hız anlamsız
                entry.velocity = (0.0, 0.0)

        entry.last_center = center
        entry.last_time = timestamp
        entry.samples += 1
        return entry.velocity

    def _prune(self, camera: str, history: dict[int, _History], now: float) -> None:
        """Gerçekten biten izlerin geçmişini temizler ve ömrünü kaydeder.

        ⚠ Bu fonksiyonun ilk hâli, o karede çıktı vermeyen HER izin
        geçmişini siliyordu. Yanlıştı: BoT-SORT kısa süre kapanan
        (occluded) bir izi çıktı vermez ama `track_buffer` boyunca
        hafızasında tutar ve kişi göründüğünde AYNI kimlikle geri verir.
        Biz ise geçmişi çoktan silmiş oluyorduk — hız sıfırlanıyor, yaş
        baştan başlıyordu.

        Şimdi geçmiş, takipçinin kendi hafıza süresi kadar (track_buffer
        / kare hızı) bekletiliyor. Bu süre dolduğunda iz gerçekten
        bitmiştir; ömrü histograma yazılır ve kısa ömürlüyse kimlik
        kararsızlığı sayacına eklenir.
        """
        expired = [
            track_id
            for track_id, entry in history.items()
            if entry.last_time is not None and now - entry.last_time > self._grace_s
        ]
        for track_id in expired:
            entry = history.pop(track_id)
            metrics.track_lifetime.observe(entry.samples)
            self._lifetimes.append(entry.samples)
            if entry.samples <= SHORT_TRACK_FRAMES:
                self._id_switches += 1
                metrics.track_switches.labels(cam=camera).inc()


__all__ = ["BotSortTracker", "default_args"]
