"""YOLO26-pose ile kırpıntı tabanlı (top-down) poz tahmini.

⚠ LİSANS: Ultralytics **AGPL-3.0**. `PoseEstimator` protokolü arkasında
   durduğu için RTMPose (Apache-2.0) geçişi tek sınıf değişimidir.

Boru hattı
----------
    tespit kutusu
      → %15 dolgu ile kırp
      → EN-BOY ORANI KORUNARAK 192×192'ye letterbox
      → tüm kameraların tüm kırpıntıları tek havuzda, 64'lük batch'ler
      → YOLO26-pose
      → keypoint'leri kaynak karenin piksel uzayına geri taşı

Neden letterbox, neden düz `resize` değil
-----------------------------------------
Bu satır ölçülerek öğrenildi (docs/report/problems.md · P-14). İlk
sürüm kırpıntıyı doğrudan kareye sıkıştırıyordu; kırpıntıların yalnızca
%47'sinden iskelet çıkıyordu ve başarısızlık küçük kutularda
yoğunlaşıyordu, yani "çözünürlük sınırı" gibi görünüyordu.

Gerçek sebep en-boy oranıydı: uzaktaki bir kişi İNCE ve UZUN bir kutu
verir (örn. 40×130 px). Kareye sıkıştırmak onu en çok bozan işlemdir —
model artık insan şekli görmez. Oran korununca:

    genel başarı        %47.4 → %88.2
    küçük kutular (<3k) %18.1 → %94.4
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np

from sentinel.inference.detector.base import Detection
from sentinel.inference.pose.base import (
    CROP_PADDING,
    CROP_SIZE,
    PAD_COLOR,
    PoseResult,
)
from sentinel.logging import get_logger

log = get_logger(__name__)

# Kırpıntı havuzunun tek seferde GPU'ya verilecek en büyük parçası.
#
# İzole ölçüm kırpıntı başına maliyeti şöyle verdi: batch 8 → 2.84 ms,
# 16 → 1.80 ms, 32 → 1.30 ms. Buradan 32 seçilmişti. Ama boru hattında
# 32 YANLIŞ çıktı:
#
#   8 kare × ~4.4 kişi ≈ 35 kırpıntı  →  32 + 3  →  İKİ GPU çağrısı
#
# 3 kırpıntılık kuyruk çağrısı, 32'lik çağrıyla neredeyse aynı sabit
# maliyeti ödetiyor. Sınırı 64'e çıkarıp tipik yükü TEK çağrıya sığdırmak
# poz maliyetini 12.5 → 9.1 ms/kare düşürdü (%27).
#
# Ders: doğru batch boyutu modelin değil, ÜRETİLEN İŞ MİKTARININ
# fonksiyonudur. İzole ölçüm bunu gösteremez.
CROP_BATCH = 64

# Bu boyutun altındaki kutular için poz denenmez. 0 = kapalı.
# Ölçümde küçük kutular bile letterbox sayesinde %94 başarıyla
# çalışıyor, bu yüzden varsayılan kapalı; GPU sıkışırsa ilk kısılacak yer.
MIN_BOX_HEIGHT_PX = 0


@dataclass(slots=True)
class _CropRef:
    """Bir kırpıntının nereden geldiğinin kaydı.

    Keypoint'leri kaynak kareye geri taşımak için gereken her şey:
    kırpıntının sol-üst köşesi, ölçek ve letterbox dolgu payları.
    """

    frame_index: int
    detection_index: int
    origin_x: int
    origin_y: int
    scale: float
    pad_left: int
    pad_top: int


class YoloPoseEstimator:
    """Kişi kırpıntılarından COCO-17 iskeleti çıkarır."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        device: str = "cuda:0",
        half: bool = True,
        crop_size: int = CROP_SIZE,
        crop_batch: int = CROP_BATCH,
        conf_threshold: float = 0.25,
        min_box_height: int = MIN_BOX_HEIGHT_PX,
    ) -> None:
        from ultralytics import YOLO

        path = Path(model_path)
        if not path.is_file():
            log.warning("poz_modeli_yok_indirilecek", path=str(path))

        self._crop_size = crop_size
        self._crop_batch = crop_batch
        self._conf = conf_threshold
        self._device = device
        self._half = half
        self._min_box_height = min_box_height

        started = time.perf_counter()
        self._model = YOLO(str(path))
        task = getattr(self._model, "task", "detect")
        if task != "pose":
            raise ValueError(
                f"Poz ağırlığı bekleniyordu, '{task}' geldi: {path}. "
                "models/yolo26s-pose.pt kullanın."
            )

        # Teşhis sayaçları — kaç kırpıntıdan iskelet çıktığı, boru
        # hattının sağlığını gösteren en doğrudan sinyal.
        self.crops_total = 0
        self.crops_with_skeleton = 0
        self.crops_skipped_small = 0

        log.info(
            "poz_modeli_yuklendi",
            path=path.name,
            device=device,
            half=half,
            crop_size=crop_size,
            crop_batch=crop_batch,
            load_ms=round((time.perf_counter() - started) * 1000),
        )

    # ─── PoseEstimator protokolü ─────────────────────────────

    def warmup(self, batch_size: int) -> None:
        dummy = [
            np.zeros((self._crop_size, self._crop_size, 3), dtype=np.uint8)
            for _ in range(max(1, batch_size))
        ]
        started = time.perf_counter()
        for _ in range(3):
            self._predict(dummy)
        log.info(
            "poz_isitildi",
            batch_size=batch_size,
            total_ms=round((time.perf_counter() - started) * 1000),
        )

    def estimate(
        self,
        frames: list[np.ndarray],
        detections: list[list[Detection]],
    ) -> list[list[PoseResult | None]]:
        output: list[list[PoseResult | None]] = [[None] * len(d) for d in detections]

        crops, refs = self._collect_crops(frames, detections)
        if not crops:
            return output

        self.crops_total += len(crops)
        for start in range(0, len(crops), self._crop_batch):
            chunk = crops[start : start + self._crop_batch]
            results = self._predict(chunk)
            for offset, result in enumerate(results):
                ref = refs[start + offset]
                keypoints = self._extract(result)
                if keypoints is None:
                    continue
                self.crops_with_skeleton += 1
                output[ref.frame_index][ref.detection_index] = PoseResult(
                    keypoints=self._to_frame_space(keypoints, ref)
                )
        return output

    def close(self) -> None:
        self._model = None  # type: ignore[assignment]

    @property
    def stats(self) -> dict[str, Any]:
        rate = self.crops_with_skeleton / self.crops_total if self.crops_total else 0.0
        return {
            "crops_total": self.crops_total,
            "crops_with_skeleton": self.crops_with_skeleton,
            "skeleton_hit_rate": round(rate, 3),
            "crops_skipped_small": self.crops_skipped_small,
        }

    # ─── İç işler ────────────────────────────────────────────

    def _collect_crops(
        self,
        frames: list[np.ndarray],
        detections: list[list[Detection]],
    ) -> tuple[list[np.ndarray], list[_CropRef]]:
        """Tüm karelerin tüm kişilerini tek kırpıntı havuzunda toplar."""
        crops: list[np.ndarray] = []
        refs: list[_CropRef] = []

        for frame_index, (frame, frame_detections) in enumerate(
            zip(frames, detections, strict=True)
        ):
            height, width = frame.shape[:2]
            for detection_index, detection in enumerate(frame_detections):
                if self._min_box_height and detection.height < self._min_box_height:
                    self.crops_skipped_small += 1
                    continue

                pad_x = detection.width * CROP_PADDING
                pad_y = detection.height * CROP_PADDING
                x1 = max(0, int(detection.x1 - pad_x))
                y1 = max(0, int(detection.y1 - pad_y))
                x2 = min(width, int(detection.x2 + pad_x))
                y2 = min(height, int(detection.y2 + pad_y))
                if x2 - x1 < 8 or y2 - y1 < 8:
                    continue

                crop, scale, pad_left, pad_top = self._letterbox(frame[y1:y2, x1:x2])
                crops.append(crop)
                refs.append(
                    _CropRef(
                        frame_index=frame_index,
                        detection_index=detection_index,
                        origin_x=x1,
                        origin_y=y1,
                        scale=scale,
                        pad_left=pad_left,
                        pad_top=pad_top,
                    )
                )
        return crops, refs

    def _letterbox(self, crop: np.ndarray) -> tuple[np.ndarray, float, int, int]:
        """En-boy oranını koruyarak kareye dolgular (bkz. modül başlığı)."""
        size = self._crop_size
        height, width = crop.shape[:2]
        scale = size / max(height, width)
        new_h = max(1, round(height * scale))
        new_w = max(1, round(width * scale))
        resized = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        canvas = np.full((size, size, 3), PAD_COLOR, dtype=np.uint8)
        pad_top = (size - new_h) // 2
        pad_left = (size - new_w) // 2
        canvas[pad_top : pad_top + new_h, pad_left : pad_left + new_w] = resized
        return canvas, scale, pad_left, pad_top

    def _predict(self, crops: list[np.ndarray]) -> list[Any]:
        # cast: Ultralytics predict() birlesik (union) bir tip donduruyor;
        # stream=False oldugu icin pratikte her zaman liste gelir.
        return cast("list[Any]", self._model.predict(
            crops,
            imgsz=self._crop_size,
            conf=self._conf,
            half=self._half,
            device=self._device,
            verbose=False,
            stream=False,
        ))

    def _extract(self, result: Any) -> np.ndarray | None:
        """Kırpıntıdaki HEDEF kişinin keypoint'lerini seçer.

        Kırpıntı, dolgu yüzünden komşu bir kişiyi de içerebilir. Hedef,
        kırpıntının merkezine en yakın olandır: kırpıntıyı zaten hedefin
        kutusunu merkeze alacak şekilde ürettik.
        """
        kp_obj = getattr(result, "keypoints", None)
        if kp_obj is None or kp_obj.data is None or not len(kp_obj.data):
            return None
        data = kp_obj.data.cpu().numpy()  # (N, 17, 3)
        if data.shape[0] == 1:
            return data[0]  # type: ignore[no-any-return]

        boxes = getattr(result, "boxes", None)
        if boxes is None or len(boxes) != data.shape[0]:
            return data[0]  # type: ignore[no-any-return]

        center = self._crop_size / 2.0
        xyxy = boxes.xyxy.cpu().numpy()
        centers_x = (xyxy[:, 0] + xyxy[:, 2]) / 2.0
        centers_y = (xyxy[:, 1] + xyxy[:, 3]) / 2.0
        distances = np.hypot(centers_x - center, centers_y - center)
        return data[int(np.argmin(distances))]  # type: ignore[no-any-return]

    @staticmethod
    def _to_frame_space(keypoints: np.ndarray, ref: _CropRef) -> np.ndarray:
        """Keypoint'leri letterbox uzayından kaynak kareye taşır.

        Ters dönüşüm: önce dolgu payını çıkar, sonra ölçeği geri al,
        sonra kırpıntının kare içindeki köşesini ekle. Güven sütununa
        (indeks 2) dokunulmaz.
        """
        mapped = keypoints.astype(np.float32, copy=True)
        mapped[:, 0] = (mapped[:, 0] - ref.pad_left) / ref.scale + ref.origin_x
        mapped[:, 1] = (mapped[:, 1] - ref.pad_top) / ref.scale + ref.origin_y
        return mapped


__all__ = ["CROP_BATCH", "YoloPoseEstimator"]
