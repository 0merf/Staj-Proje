"""Dedektör arayüzü.

Neden soyutluyoruz
------------------
Ultralytics (YOLO26/YOLO11) **AGPL-3.0** lisanslıdır. Staj kapsamında
sorun değil, ancak ürünleşme durumunda Apache-2.0 bir alternatife
(RTMDet, RT-DETRv2) geçmek gerekebilir. Kodun geri kalanı bu protokole
bağlı olduğu sürece geçiş **tek konfigürasyon satırıdır**.

İkinci fayda: Faz 5'teki model kıyaslaması (YOLO26 vs YOLO11 vs RTMDet)
aynı ölçüm koşusuyla yapılabilir — sadece backend değişir.

Toplu (batch) arayüz
--------------------
`detect()` tek kare değil **kare listesi** alır. Sebebi mimaridir:
20 kameradan gelen kareler tek batch'te GPU'ya verilir. GPU çekirdek
başlatma gecikmesi kare başına değil batch başına ödenir; verim
kat kat artar (PLAN.md §4.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

# COCO insan sınıfı. Yalnızca insan tespit ediyoruz — araba, köpek vb.
# kapsam dışı (PLAN.md §1.3).
PERSON_CLASS_ID = 0

# COCO-17 keypoint sırası (YOLO-pose çıktısı bu düzendedir)
KEYPOINT_NAMES = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)


@dataclass(frozen=True, slots=True)
class Detection:
    """Tek bir tespit.

    Koordinatlar **piksel** cinsindendir (kaynak karenin çözünürlüğünde).
    Normalize etme işi sunum katmanına bırakılır — analitik hesapları
    (mesafe, hız) piksel uzayında yapılır.
    """

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int = PERSON_CLASS_ID
    # YOLO-pose gibi modeller aynı geçişte iskelet de verir: (17, 3)
    # her satır (x, y, güven). Sadece tespit yapan modellerde None.
    keypoints: np.ndarray | None = None

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def foot_point(self) -> tuple[float, float]:
        """Kutunun alt orta noktası — kişinin zemindeki konumu.

        Mesafe ve hız hesaplarında merkez yerine bunu kullanmak daha
        doğrudur: kişi kameraya yaklaştıkça kutu büyür ve merkez yukarı
        kayar, ama ayak noktası zemin düzleminde kalır.
        """
        return ((self.x1 + self.x2) / 2.0, self.y2)

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "bbox": [round(self.x1, 1), round(self.y1, 1), round(self.x2, 1), round(self.y2, 1)],
            "conf": round(self.confidence, 3),
            "cls": self.class_id,
        }
        if self.keypoints is not None:
            data["kp"] = [[round(float(v), 1) for v in point] for point in self.keypoints]
        return data


@dataclass(frozen=True, slots=True)
class DetectorInfo:
    """Model künyesi — ölçüm ve raporlama için."""

    backend: str  # "yolo26" | "yolo11" | "rtmdet" …
    model_path: str
    precision: str  # "fp32" | "fp16" | "int8"
    device: str  # "cuda:0" | "cpu"
    input_size: int
    has_pose: bool
    license: str


@runtime_checkable
class Detector(Protocol):
    """Bir dedektörün karşılaması gereken sözleşme."""

    @property
    def info(self) -> DetectorInfo:
        """Model künyesi."""
        ...

    def warmup(self, batch_size: int) -> None:
        """Sahte veriyle birkaç geçiş yapar.

        Neden gerekli: ilk çıkarım CUDA bağlamı kurulumu, çekirdek
        derlemesi ve bellek tahsisi yüzünden 10-100× yavaştır. Ölçüme
        bunu karıştırmamak için önceden ısıtılır.
        """
        ...

    def detect(
        self,
        images: list[np.ndarray],
        *,
        conf_threshold: float | None = None,
    ) -> list[list[Detection]]:
        """Kare listesini işler, kare başına tespit listesi döndürür.

        Dönen listenin uzunluğu `images` ile aynıdır ve sıra korunur.
        """
        ...

    def close(self) -> None:
        """Kaynakları serbest bırakır."""
        ...


__all__ = [
    "KEYPOINT_NAMES",
    "PERSON_CLASS_ID",
    "Detection",
    "Detector",
    "DetectorInfo",
]
