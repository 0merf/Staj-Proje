"""Ultralytics tabanlı dedektör (YOLO26 / YOLO11).

⚠ LİSANS: Ultralytics **AGPL-3.0**'dır. Staj/akademik kullanımda sorun
   yoktur; ürünleşmede Apache-2.0 alternatiflerine geçilmelidir.
   Bu dosya `Detector` protokolünü uyguladığı için geçiş, konfigürasyonda
   `DETECTOR_BACKEND` değerini değiştirmekten ibarettir (base.py).

Aynı sınıf hem `yolo26s.pt` hem `yolo11s.pt` hem de TensorRT'ye ihraç
edilmiş `.engine` dosyalarını yükleyebilir — Ultralytics uzantıya bakıp
doğru çalışma zamanını seçer. Faz 5'teki model kıyaslaması bu sayede
tek koşuda yapılabilecek.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, cast

import numpy as np

from sentinel.inference.detector.base import (
    PERSON_CLASS_ID,
    Detection,
    DetectorInfo,
)
from sentinel.logging import get_logger

log = get_logger(__name__)


class UltralyticsDetector:
    """YOLO26 / YOLO11 sarmalayıcısı.

    Tespit ve poz aynı sınıfla kullanılır: `-pose` ağırlığı verilirse
    `Detection.keypoints` dolu gelir, yoksa None. Böylece Kademe 1 ve
    Kademe 2a tek model çağrısında birleşebilir.
    """

    def __init__(
        self,
        model_path: str | Path,
        *,
        backend_name: str = "yolo26",
        device: str = "cuda:0",
        half: bool = True,
        imgsz: int = 640,
        conf_threshold: float = 0.35,
        classes: tuple[int, ...] = (PERSON_CLASS_ID,),
    ) -> None:
        from ultralytics import YOLO

        path = Path(model_path)
        if not path.is_file():
            # Ultralytics tanınmış isimleri kendisi indirir (yolo26s.pt gibi).
            # ⚠ .pt dosyaları pickle'dır; yalnızca resmi kaynak + checksum
            #   ile kullanılmalı (PLAN.md §11.4). fetch_models.py bunu yapar.
            log.warning("model_dosyasi_yok_indirilecek", path=str(path))

        self._conf = conf_threshold
        self._classes = list(classes)
        self._imgsz = imgsz
        self._device = device
        self._half = half

        started = time.perf_counter()
        self._model = YOLO(str(path))
        # Ağırlığın poz başlığı var mı? (kwarg değil, modelden okunur)
        task = getattr(self._model, "task", "detect")
        self._has_pose = task == "pose"

        self._info = DetectorInfo(
            backend=backend_name,
            model_path=str(path),
            precision="fp16" if half else "fp32",
            device=device,
            input_size=imgsz,
            has_pose=self._has_pose,
            license="AGPL-3.0",
        )
        log.info(
            "dedektor_yuklendi",
            backend=backend_name,
            task=task,
            device=device,
            half=half,
            imgsz=imgsz,
            load_ms=round((time.perf_counter() - started) * 1000),
        )

    # ─── Detector protokolü ──────────────────────────────────

    @property
    def info(self) -> DetectorInfo:
        return self._info

    def warmup(self, batch_size: int) -> None:
        """CUDA bağlamı ve çekirdekleri önceden hazırlar."""
        dummy = [
            np.zeros((self._imgsz, self._imgsz, 3), dtype=np.uint8) for _ in range(batch_size)
        ]
        started = time.perf_counter()
        for _ in range(3):
            self._predict(dummy, self._conf)
        log.info(
            "dedektor_isitildi",
            batch_size=batch_size,
            total_ms=round((time.perf_counter() - started) * 1000),
        )

    def detect(
        self,
        images: list[np.ndarray],
        *,
        conf_threshold: float | None = None,
    ) -> list[list[Detection]]:
        if not images:
            return []
        results = self._predict(images, conf_threshold or self._conf)
        return [self._convert(result) for result in results]

    def close(self) -> None:
        self._model = None  # type: ignore[assignment]

    # ─── İç işler ────────────────────────────────────────────

    def _as_tensor(self, images: list[np.ndarray]) -> Any | None:
        """Kareleri doğrudan GPU tensörüne çevirir — mümkünse.

        ⚠ NEDEN: Ultralytics'e numpy listesi verildiğinde ön işlemeyi
        (yeniden boyutlandırma, renk dönüşümü, eksen değiştirme,
        normalizasyon) **CPU'da** yapar. Gün 8 ölçümü bunun süre
        bütçesinin %53'ünü yediğini, GPU'nun ise %0-5 kullanımda boş
        oturduğunu gösterdi. Hazır tensör verildiğinde Ultralytics bu
        adımı atlıyor ve kare başına maliyet 6.78 → 3.87 ms'e düşüyor
        (%43), üstelik tespitler birebir aynı kalıyor.

        Koşul: kareler zaten model uzayında olmalı (alım tarafında
        letterbox'lanmış, hepsi aynı kare boyutta). Değilse None döner
        ve eski numpy yolu kullanılır — kıyaslama betikleri ham kare
        verdiğinde çalışmaya devam etsin diye.
        """
        if not images:
            return None
        first = images[0].shape
        if first[0] != self._imgsz or first[1] != self._imgsz or first[2] != 3:
            return None
        if any(img.shape != first for img in images):
            return None

        import torch

        # np.stack: bitişik bellekten düz kopya, ucuz.
        batch = np.stack(images)  # (N, H, W, 3) BGR uint8
        tensor = torch.from_numpy(batch).to(self._device, non_blocking=True)
        # Pahalı olan eksen değiştirme ve kanal çevirme GPU'da yapılıyor:
        # BGR→RGB için flip, HWC→CHW için permute. İkisi de burada
        # neredeyse bedava, CPU'da kare başına milisaniyelerce sürüyordu.
        tensor = tensor.permute(0, 3, 1, 2).flip(1).contiguous()
        tensor = tensor.half() if self._half else tensor.float()
        return tensor.div_(255.0)

    def _predict(self, images: list[np.ndarray], conf: float) -> list[Any]:
        source: Any = self._as_tensor(images)
        if source is None:
            source = images

        # cast: Ultralytics predict() birlesik (union) bir tip donduruyor;
        # stream=False oldugu icin pratikte her zaman liste gelir.
        return cast("list[Any]", self._model.predict(
            source,
            imgsz=self._imgsz,
            conf=conf,
            classes=self._classes,
            half=self._half,
            device=self._device,
            verbose=False,
            stream=False,
        ))

    def _convert(self, result: Any) -> list[Detection]:
        """Ultralytics sonucunu bizim Detection listemize çevirir."""
        boxes = getattr(result, "boxes", None)
        if boxes is None or len(boxes) == 0:
            return []

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        classes = boxes.cls.cpu().numpy().astype(int)

        keypoints = None
        kp_obj = getattr(result, "keypoints", None)
        if kp_obj is not None and kp_obj.data is not None and len(kp_obj.data):
            # (N, 17, 3) — x, y, güven
            keypoints = kp_obj.data.cpu().numpy()

        detections: list[Detection] = []
        for index in range(len(xyxy)):
            x1, y1, x2, y2 = (float(v) for v in xyxy[index])
            detections.append(
                Detection(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    confidence=float(confs[index]),
                    class_id=int(classes[index]),
                    keypoints=keypoints[index] if keypoints is not None else None,
                )
            )
        return detections


__all__ = ["UltralyticsDetector"]
