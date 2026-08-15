"""Nesne takibi arayüzü.

Neden takip şart
----------------
Tespit her kareyi bağımsız görür: "burada bir insan var". Takip ise
"bu, önceki karedeki AYNI insan" der ve ona kalıcı bir kimlik verir.

Bu kimlik olmadan zamansal hiçbir şey hesaplanamaz:
  · "bu kişi 3 saniyedir hızlanıyor"        → kimlik gerekir
  · "bu iki kişi birbirine yaklaşıyor"      → kimlik gerekir
  · "bu kişi 2 dakikadır burada bekliyor"   → kimlik gerekir

Yani saldırganlık ve anomali modüllerinin tamamı takibin üstünde duruyor
(PLAN.md §6.1).

İkinci fayda: kutu interpolasyonu
---------------------------------
Video 25 FPS akıyor ama tespit kamera başına ~3 FPS yapılıyor (kademeli
işleme gereği). Aradaki ~330 ms boyunca kutu donuk kalıyor ve yürüyen
kişi kutudan çıkıyor. Takip her nesneye bir **hız vektörü** verince
tarayıcı aradaki kareleri tahmin edebiliyor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import numpy as np

from sentinel.inference.detector.base import Detection


@dataclass(slots=True)
class Track:
    """Kimliği olan, zaman içinde izlenen bir nesne."""

    track_id: int
    detection: Detection
    # Piksel/saniye cinsinden hız. Tarayıcı bunu kullanarak iki tespit
    # arasında kutunun nerede olacağını tahmin eder.
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    age: int = 0  # kaç kare boyunca görüldü
    time_since_update: int = 0

    @property
    def speed(self) -> float:
        """Hızın büyüklüğü (piksel/saniye) — koşma tespitinde kullanılacak."""
        return float(np.hypot(self.velocity_x, self.velocity_y))

    def to_dict(self) -> dict[str, Any]:
        data = self.detection.to_dict()
        data["id"] = self.track_id
        # Hızı tam sayıya yuvarlıyoruz: mesaj boyutu 20 kamerada önemli
        data["v"] = [round(self.velocity_x), round(self.velocity_y)]
        data["age"] = self.age
        return data


@dataclass(slots=True)
class DetectionBatch:
    """Takipçiye verilen girdi.

    Ultralytics takipçileri "Results benzeri" bir nesne bekliyor:
    `xywh`, `conf`, `cls` dizileri, `len()` ve boolean indeksleme.
    Bu adaptör o sözleşmeyi bizim `Detection` tipimizden karşılıyor.

    Neden Ultralytics'in kendi `Boxes` nesnesini geçirmiyoruz: takip
    katmanı dedektörden bağımsız kalmalı. RTMDet'e geçtiğimizde
    (AGPL'den kaçış senaryosu) burası değişmeyecek.
    """

    xywh: np.ndarray  # (N, 4) merkez-x, merkez-y, genişlik, yükseklik
    conf: np.ndarray  # (N,)
    cls: np.ndarray  # (N,)

    def __len__(self) -> int:
        return int(self.xywh.shape[0])

    def __getitem__(self, mask: np.ndarray) -> DetectionBatch:
        return DetectionBatch(xywh=self.xywh[mask], conf=self.conf[mask], cls=self.cls[mask])

    @classmethod
    def from_detections(cls, detections: list[Detection]) -> DetectionBatch:
        if not detections:
            empty = np.empty((0, 4), dtype=np.float32)
            return cls(xywh=empty, conf=np.empty(0, np.float32), cls=np.empty(0, np.float32))
        xywh = np.array(
            [
                [
                    (d.x1 + d.x2) / 2.0,
                    (d.y1 + d.y2) / 2.0,
                    d.x2 - d.x1,
                    d.y2 - d.y1,
                ]
                for d in detections
            ],
            dtype=np.float32,
        )
        return cls(
            xywh=xywh,
            conf=np.array([d.confidence for d in detections], dtype=np.float32),
            cls=np.array([d.class_id for d in detections], dtype=np.float32),
        )


@dataclass(slots=True)
class _History:
    """Hız hesabı için tutulan kısa geçmiş."""

    last_center: tuple[float, float] | None = None
    last_time: float | None = None
    velocity: tuple[float, float] = (0.0, 0.0)
    samples: int = 0


@runtime_checkable
class Tracker(Protocol):
    """Bir takipçinin karşılaması gereken sözleşme."""

    def update(
        self, camera: str, detections: list[Detection], timestamp: float
    ) -> list[Track]:
        """Bir kameranın tespitlerini işler, kimlikli izleri döndürür.

        `camera` parametresi kritik: her kameranın **kendi takipçi
        durumu** vardır. Tek bir takipçiye 20 kameranın tespitlerini
        vermek, farklı sahnelerdeki kişileri birbirine karıştırırdı.
        """
        ...

    def reset(self, camera: str | None = None) -> None:
        """Takipçi durumunu sıfırlar (kamera bazlı veya tümü)."""
        ...

    @property
    def stats(self) -> dict[str, Any]:
        """Metrik/teşhis bilgisi."""
        ...


# Hız yumuşatma katsayısı. Üstel hareketli ortalama:
#   v = ALPHA * yeni + (1 - ALPHA) * eski
# Düşük değer = daha kararlı ama daha geç tepki veren hız tahmini.
# 0.5 deneysel olarak iyi bir denge: tek karelik gürültüyü söndürüyor,
# yön değişimine bir-iki karede uyum sağlıyor.
VELOCITY_ALPHA = 0.5

# Hız tahmininin geçerli sayılacağı en büyük zaman aralığı. Bundan uzun
# bir boşluktan sonra (kişi kayboldu, sonra geri geldi) eski hız
# anlamsızdır; sıfırlanır.
MAX_VELOCITY_GAP_S = 1.5


__all__ = [
    "MAX_VELOCITY_GAP_S",
    "VELOCITY_ALPHA",
    "DetectionBatch",
    "Track",
    "Tracker",
    "_History",
]
