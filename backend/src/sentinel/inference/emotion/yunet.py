"""YuNet yüz tespiti + EmotiEffLib ifade sınıflandırma.

Neden YuNet
-----------
OpenCV'nin içinde geliyor (`cv2.FaceDetectorYN`), 230 KB, CPU'da bile
gerçek zamanlı. Bizim kullanımımızda girdi zaten küçük: tüm kareyi
değil, **kişi kutusunun üst kısmını** tarıyoruz. Yüz orada olmak
zorunda; tüm kareyi taramak boşa iş olurdu.

Neden EmotiEffLib
-----------------
AffectNet üzerinde eğitilmiş, hazır ağırlıklı, 8 sınıflı. Sıfırdan
eğitmek bu projenin kapsamı değil (PLAN.md §3.4).

Ölçülen maliyetler (18.08.2026, `scripts/benchmark_expression.py`):

    YuNet yüz tespiti   1.46 ms / kırpıntı
    EmotiEffLib ifade   7.41 ms / yüz  (cpu)  ·  7.51 ms  (cuda)

⚠ Bu dosya uzun süre "~58 ms/yüz, GPU sağlayıcısı etkinleşmedi"
diyordu. **İkisi de yanlıştı:** maliyet ~8 kat düşük ve CUDA sağlayıcısı
artık yükleniyor (P-30). Ama GPU kazandırmıyor, çünkü emotiefflib toplu
çağrı yapmıyor — ayrıntı ve ölçüm `emotion/base.py` modül başlığında.

Çağıran kod yine de **seyreltiyor**: kapı bedava çalışıyor ve bütçe
koruması kalabalık bir kameranın çıkarım döngüsünü bloklamasını
engelliyor (stage.py).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from sentinel.inference.emotion.base import (
    EXPRESSION_TR,
    MIN_FACE_PX,
    FaceBox,
)
from sentinel.logging import get_logger

log = get_logger(__name__)

# Yüz, kişi kutusunun üst kısmındadır. Tamamını taramak hem yavaş hem
# yanıltıcı olurdu (arka plandaki başka yüzler yakalanabilir).
HEAD_REGION = 0.45

# YuNet'e verilen kırpıntının en küçük kenarı. Altında model anlamlı
# çalışmıyor; zaten bu boyutta yüz de bulunmaz.
MIN_INPUT_PX = 48


class YuNetFaceDetector:
    """Kişi kırpıntısının üst bölgesinde yüz arar."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        conf_threshold: float = 0.6,
        nms_threshold: float = 0.3,
    ) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"YuNet modeli yok: {path}\n"
                "  uv run python scripts/fetch_models.py --faces"
            )
        started = time.perf_counter()
        self._detector = cv2.FaceDetectorYN.create(
            str(path), "", (320, 320), conf_threshold, nms_threshold, 5000
        )
        self.faces_found = 0
        self.crops_scanned = 0
        log.info(
            "yuz_dedektoru_yuklendi",
            path=path.name,
            load_ms=round((time.perf_counter() - started) * 1000),
        )

    def detect(self, person_crop: np.ndarray) -> FaceBox | None:
        """Kişi kırpıntısının üst %45'inde en belirgin yüzü arar."""
        self.crops_scanned += 1
        height = person_crop.shape[0]
        head_h = max(1, int(height * HEAD_REGION))
        head = person_crop[:head_h, :]

        if head.shape[0] < MIN_INPUT_PX or head.shape[1] < MIN_INPUT_PX:
            return None

        # ⚠ setInputSize her çağrıda gerekli: kırpıntılar farklı
        # boyutlarda geliyor ve YuNet girdi boyutunu önceden bilmek
        # istiyor. Atlanırsa sessizce yanlış ölçekte tarar.
        self._detector.setInputSize((head.shape[1], head.shape[0]))
        _, faces = self._detector.detect(head)
        if faces is None or len(faces) == 0:
            return None

        # En yüksek güvenli yüz. Kırpıntı tek kişinin kutusundan
        # geldiği için birden fazla yüz varsa komşudur.
        best = max(faces, key=lambda f: float(f[14]))
        x, y, w, h = (float(v) for v in best[:4])
        if min(w, h) < MIN_FACE_PX:
            return None

        self.faces_found += 1
        return FaceBox(x1=x, y1=y, x2=x + w, y2=y + h, confidence=float(best[14]))

    def close(self) -> None:
        self._detector = None  # type: ignore[assignment]

    @property
    def hit_rate(self) -> float:
        return self.faces_found / self.crops_scanned if self.crops_scanned else 0.0


class EmotiEffExpressionClassifier:
    """EmotiEffLib ile yüz ifadesi sınıflandırma.

    ⚠ Çıktı bir DUYGU İDDİASI değildir (base.py modül başlığı).
    """

    def __init__(
        self,
        *,
        model_name: str = "enet_b0_8_best_vgaf",
        device: str = "cpu",
        thread: int = 1,
    ) -> None:
        """
        Args:
            thread: ONNX Runtime iş parçacığı sayısı. ⚠ Varsayılan 1 —
                gerekçesi aşağıda.
        """
        import onnxruntime as ort
        from emotiefflib.facial_analysis import EmotiEffLibRecognizer

        started = time.perf_counter()

        # ⚠⚠⚠ ONNX OTURUMUNA İŞ PARÇACIĞI SINIRI ENJEKTE EDİLİYOR (P-60)
        #
        # `emotiefflib` oturumu şöyle kuruyor ve dışarıdan ayar
        # almıyor:
        #     ort.InferenceSession(model_bytes, providers=["CPU..."])
        #
        # `SessionOptions` verilmediği için ONNX Runtime kendi
        # varsayılanını kullanıyor: **çekirdek sayısı kadar** iş
        # parçacığı (bu makinede 20) ve havuz işler arasında meşgul
        # bekliyor.
        #
        # Ölçüldü (P-59, `yeniden_olc.py`):
        #     ifade  duvar 6.25 ms · CPU 86.72 ms · paralellik 13.88×
        #     20 kamera bütçesinde TEK BAŞINA 5.03 ÇEKİRDEK
        #
        # ⚠ `OMP_NUM_THREADS=1` (P-58) BURAYA İŞLEMİYOR: ONNX Runtime
        # kendi iş parçacığı havuzunu kullanıyor, OpenMP'yi değil.
        # Bu yüzden ayrı bir müdahale gerekiyor.
        #
        # ⭐ ÖLÇÜLDÜ (40 tahmin, 96×96 yüz, bu makine 20 çekirdek):
        #
        #     thread   duvar ms   CPU ms   paralellik
        #        1       13.44     13.28      0.99     ⬅ varsayılan
        #        2        8.96     17.97      2.00
        #        4        6.68     26.56      3.98
        #       20        9.15    175.39     19.17     ⬅ ESKİ davranış
        #
        # ⭐⭐ Eski varsayılan HER AÇIDAN kötüydü: duvar saatinde bile
        # thread=4'ten yavaş (9.15 ⟷ 6.68) ama CPU'da **13 kat** pahalı.
        # Klasik aşırı paralelleştirme — küçük bir modelde iş parçacığı
        # eşgüdüm maliyeti işin kendisini geçiyor.
        #
        # `thread=1` seçildi çünkü 20 kameralı sistemde kısıt CPU, duvar
        # saati değil: ifade kademesi zaten seyreltilmiş çalışıyor ve
        # +7 ms gecikme karşılığında ~0.8 çekirdek kazanılıyor.
        #
        # ⭐ YÖNTEM: `InferenceSession` yalnızca BU kurulum boyunca
        # sarmalanıyor ve hemen geri alınıyor. Kütüphaneyi kalıcı
        # olarak yamamak, aynı süreçteki başka ONNX kullanıcılarını
        # (YuNet, TensorRT dışa aktarımı) da etkilerdi.
        orijinal = ort.InferenceSession

        def _sinirli(*a: Any, **kw: Any) -> Any:
            if "sess_options" not in kw and len(a) < 2:
                secenek = ort.SessionOptions()
                secenek.intra_op_num_threads = thread
                secenek.inter_op_num_threads = thread
                kw["sess_options"] = secenek
            return orijinal(*a, **kw)

        ort.InferenceSession = _sinirli
        try:
            self._recognizer = EmotiEffLibRecognizer(
                engine="onnx", model_name=model_name, device=device
            )
        finally:
            # ⚠ `finally`: kurulum patlasa bile kütüphane eski hâline
            # dönmeli. Yamalı bırakmak sessiz bir yan etki olurdu.
            ort.InferenceSession = orijinal
        self.classified = 0
        log.info(
            "ifade_modeli_yuklendi",
            model=model_name,
            device=device,
            thread=thread,
            load_ms=round((time.perf_counter() - started) * 1000),
        )

    def classify(self, face_crops: list[np.ndarray]) -> list[tuple[str, float]]:
        """Yüz listesini sınıflandırır: [(etiket, güven), ...]"""
        if not face_crops:
            return []
        labels, scores = self._recognizer.predict_emotions(face_crops, logits=False)
        self.classified += len(face_crops)

        out: list[tuple[str, float]] = []
        matrix = np.asarray(scores)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        for index, label in enumerate(labels):
            confidence = float(matrix[index].max()) if index < len(matrix) else 0.0
            out.append((str(label), confidence))
        return out

    def close(self) -> None:
        self._recognizer = None


def to_turkish(label: str) -> str:
    """İngilizce sınıf adını panelde gösterilecek Türkçeye çevirir."""
    return EXPRESSION_TR.get(label, label.lower())


__all__ = [
    "EmotiEffExpressionClassifier",
    "YuNetFaceDetector",
    "to_turkish",
]
