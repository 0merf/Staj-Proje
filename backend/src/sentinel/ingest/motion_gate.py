"""KADEME 0 — hareket filtresi.

Mimarinin en kritik parçası. 20 kamerayı tek GPU'da döndürebilmemizin
sebebi bu: gerçek gözetim görüntüsünde karelerin büyük bölümünde hiçbir
şey olmaz. O kareleri pahalı modellere hiç göndermeyiz.

Neden ucuz
----------
1. Kare 320×180'e küçültülür. Hareketin *varlığını* anlamak için
   yüksek çözünürlük gerekmez; 720p'de 3 ms süren işlem burada ~0.3 ms.
2. MOG2 arka plan çıkarma modeli piksel başına Gauss karışımı tutar;
   OpenCV uygulaması C++ ve SIMD hızlandırmalı.
3. Gölge tespiti kapalı — bize gölge lazım değil, sadece hareket.

Neden "zorunlu yenileme karesi" var
-----------------------------------
Kadrajda hareketsiz duran bir kişi (oturuyor, bekliyor) arka plana
karışır ve filtre onu eler. Takip kimliği kaybolur, kişi "yok olur".
Bu yüzden hareket olmasa bile N saniyede bir tam analiz zorlanır.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import cv2
import numpy as np


class GateReason(StrEnum):
    """Kararın gerekçesi — metrik etiketlemede ve hata ayıklamada kullanılır."""

    WARMUP = "warmup"  # arka plan modeli henüz öğrenmedi, geçir
    MOTION = "motion"  # hareket eşiği aşıldı
    REFRESH = "refresh"  # zorunlu periyodik tam analiz
    IDLE = "idle"  # hareket yok, kare atlandı


@dataclass(frozen=True, slots=True)
class GateDecision:
    """Tek bir kare için filtre kararı."""

    process: bool
    reason: GateReason
    foreground_ratio: float
    elapsed_ms: float


class MotionGate:
    """Kamera başına bir örnek. İç durum taşır — paylaşılamaz."""

    __slots__ = ("_bg", "_frames_seen", "_kernel", "_last_pass_ts", "_refresh_s", "_size", "_threshold", "_warmup")

    def __init__(
        self,
        *,
        threshold: float = 0.005,
        work_size: tuple[int, int] = (320, 180),
        refresh_interval_s: float = 5.0,
        warmup_frames: int = 30,
        history: int = 500,
    ) -> None:
        """
        Args:
            threshold: Ön plan piksel oranı eşiği. 0.005 = karenin %0.5'i.
            work_size: Hareket tespitinin yapılacağı küçültülmüş boyut.
            refresh_interval_s: Hareket olmasa da zorla geçirme aralığı.
            warmup_frames: Arka plan modeli oturana kadar geçirilecek kare.
            history: MOG2'nin arka plan öğrenme penceresi (kare sayısı).
        """
        self._threshold = threshold
        self._size = work_size
        self._refresh_s = refresh_interval_s
        self._warmup = warmup_frames
        self._frames_seen = 0
        self._last_pass_ts: float | None = None
        self._bg = cv2.createBackgroundSubtractorMOG2(
            history=history,
            varThreshold=16,
            detectShadows=False,  # gölge tespiti ~%40 daha yavaş, işimize yaramıyor
        )
        # 3×3 açma (erode+dilate) — tekil gürültü piksellerini siler.
        # 320×180'de maliyeti ihmal edilebilir, yanlış pozitifi belirgin azaltır.
        self._kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

    def evaluate(self, frame_bgr: np.ndarray, timestamp: float) -> GateDecision:
        """Bu kare pahalı modellere gönderilmeli mi?

        Args:
            frame_bgr: BGR kare (herhangi bir çözünürlük).
            timestamp: Karenin monotonik zaman damgası (saniye).
        """
        started = cv2.getTickCount()

        small = cv2.resize(frame_bgr, self._size, interpolation=cv2.INTER_AREA)
        mask = self._bg.apply(small)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel)
        ratio = float(cv2.countNonZero(mask)) / mask.size

        self._frames_seen += 1
        elapsed_ms = (cv2.getTickCount() - started) / cv2.getTickFrequency() * 1000.0

        reason = self._decide(ratio, timestamp)
        process = reason is not GateReason.IDLE
        if process:
            self._last_pass_ts = timestamp

        return GateDecision(
            process=process,
            reason=reason,
            foreground_ratio=ratio,
            elapsed_ms=elapsed_ms,
        )

    def _decide(self, ratio: float, timestamp: float) -> GateReason:
        if self._frames_seen <= self._warmup:
            return GateReason.WARMUP
        if ratio >= self._threshold:
            return GateReason.MOTION
        if self._last_pass_ts is None or (timestamp - self._last_pass_ts) >= self._refresh_s:
            return GateReason.REFRESH
        return GateReason.IDLE

    @property
    def frames_seen(self) -> int:
        return self._frames_seen


__all__ = ["GateDecision", "GateReason", "MotionGate"]
