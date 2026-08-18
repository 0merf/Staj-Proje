"""KADEME 2b kapısı — hangi kişiye ne zaman yüz analizi yapılacak.

Bu dosyanın tamamı **iş yapmamak** üzerine. Sebebi ölçüm: ifade modeli
bu ortamda CPU'da koşuyor ve yüz başına ~58 ms alıyor. 20 kamerada
kare başına ~4.5 kişi varsa, hepsini her karede sınıflandırmak
saniyede onlarca saniyelik iş demek — imkânsız.

Üç kademeli kapı (ucuzdan pahalıya)
-----------------------------------
    1. Kutu yeterince büyük mü?        → bedava (aritmetik)
    2. Bu iz için süre doldu mu?       → bedava (sözlük araması)
    3. Bütçe kaldı mı?                 → bedava (sayaç)
    ─────────────────────────────────
    ancak hepsi geçilirse: yüz tespiti (~1 ms) → ifade (~58 ms)

Kademeli işlemenin aynı mantığı: pahalı adıma gelmeden önce ucuz
kontrollerle mümkün olduğunca ele.

⚠ Bütçe neden şart: kapı olmadan kalabalık bir kamera tek başına tüm
CPU'yu yiyebilir ve KADEME 1 (tespit) aç kalır. Tespit kaybetmek,
ifade kazanmaktan çok daha pahalıdır — ifade füzyonda 0.10 ağırlıklı,
tespit ise her şeyin temeli.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from sentinel import metrics
from sentinel.inference.detector.base import Detection
from sentinel.inference.emotion.base import (
    MIN_FACE_PX,
    MIN_INTERVAL_S,
    ExpressionResult,
    FaceBox,
    face_quality,
)
from sentinel.inference.emotion.yunet import (
    EmotiEffExpressionClassifier,
    YuNetFaceDetector,
    to_turkish,
)
from sentinel.logging import get_logger

log = get_logger(__name__)

# Kişi kutusunun yüz aranmaya değecek en küçük yüksekliği.
# Yüz, gövdenin kabaca sekizde biri; 60 px yüz için ~200 px gövde gerekir.
MIN_PERSON_HEIGHT = 180

# Tek turda en fazla kaç yüz sınıflandırılsın. 58 ms/yüz olduğu için
# 4 yüz ≈ 230 ms — çıkarım döngüsünü bloklamayacak bir üst sınır.
MAX_FACES_PER_ROUND = 4


@dataclass
class TrackExpression:
    """Bir izin ifade geçmişi.

    Neden geçmiş tutuluyor: tek karelik sınıflandırma gürültülüdür.
    PLAN.md §6.3 kayan ortalama istiyor — yumuşatılmış etiket, tek
    ölçümden çok daha kararlı.
    """

    last_at: float = 0.0
    # Son N sınıflandırmanın etiketleri (yumuşatma için)
    recent: list[str] = field(default_factory=list)
    last_result: ExpressionResult | None = None

    def smoothed_label(self) -> str | None:
        """Son ölçümlerin çoğunluk etiketi."""
        if not self.recent:
            return None
        return max(set(self.recent), key=self.recent.count)


class ExpressionStage:
    """KADEME 2b: yüz tespiti + ifade sınıflandırma, seyreltilmiş."""

    def __init__(
        self,
        face_model: str,
        *,
        expression_model: str = "enet_b0_8_best_vgaf",
        device: str = "cpu",
        min_interval_s: float = MIN_INTERVAL_S,
        max_faces_per_round: int = MAX_FACES_PER_ROUND,
        min_person_px: int = MIN_PERSON_HEIGHT,
    ) -> None:
        self._faces = YuNetFaceDetector(face_model)
        self._classifier = EmotiEffExpressionClassifier(
            model_name=expression_model, device=device
        )
        self._min_interval = min_interval_s
        self._budget = max_faces_per_round
        self._min_person_px = min_person_px
        # Kamera + iz kimliği → geçmiş
        self._state: dict[tuple[str, int], TrackExpression] = {}

        self.considered = 0
        self.gated_small = 0
        self.gated_recent = 0
        self.gated_budget = 0
        self.no_face = 0
        self.low_quality = 0
        self.classified = 0

    # ─── Ana giriş ───────────────────────────────────────────

    def process(
        self,
        camera: str,
        frame: np.ndarray,
        detections: list[Detection],
        track_ids: list[int | None],
        now: float,
    ) -> dict[int, ExpressionResult]:
        """Bir karenin kişilerini kapıdan geçirip ifade sınıflandırır.

        Dönen sözlük: iz kimliği → ifade sonucu. Yalnızca bu turda
        SINIFLANDIRILAN izler var; diğerleri için çağıran taraf
        `last_for()` ile son bilinen sonucu alabilir.
        """
        candidates: list[tuple[int, np.ndarray, FaceBox]] = []
        budget = self._budget

        for detection, track_id in zip(detections, track_ids, strict=True):
            if track_id is None or track_id < 0:
                continue  # kimliksiz izde zamansal yumuşatma yapılamaz
            self.considered += 1

            # ── Kapı 1: kutu yeterince büyük mü (bedava) ──
            if detection.height < self._min_person_px:
                self.gated_small += 1
                continue

            # ── Kapı 2: bu iz için süre doldu mu (bedava) ──
            state = self._state.setdefault((camera, track_id), TrackExpression())
            if now - state.last_at < self._min_interval:
                self.gated_recent += 1
                continue

            # ── Kapı 3: bütçe (bedava) ──
            if budget <= 0:
                self.gated_budget += 1
                continue

            # ── Yüz tespiti (~1 ms) ──
            crop = self._person_crop(frame, detection)
            if crop is None:
                continue
            face = self._faces.detect(crop)
            if face is None:
                self.no_face += 1
                # Yüz bulunamaması da bir sonuçtur: zamanlayıcıyı
                # ilerletiyoruz ki her karede tekrar denenmesin.
                state.last_at = now
                continue

            face_crop = self._face_crop(crop, face)
            if face_crop is None:
                continue

            quality = face_quality(face_crop, face)
            if quality < 0.35:
                self.low_quality += 1
                state.last_at = now
                continue

            candidates.append((track_id, face_crop, face))
            budget -= 1

        if not candidates:
            return {}

        # ── Pahalı adım: toplu sınıflandırma ──
        crops = [c for _, c, _ in candidates]
        predictions = self._classifier.classify(crops)

        results: dict[int, ExpressionResult] = {}
        for (track_id, face_crop, face), (label, confidence) in zip(
            candidates, predictions, strict=True
        ):
            state = self._state[(camera, track_id)]
            state.last_at = now
            state.recent.append(label)
            if len(state.recent) > 5:
                state.recent.pop(0)

            # Yumuşatılmış etiket kullanılıyor: tek karelik sınıflandırma
            # gürültülüdür, çoğunluk oyu belirgin şekilde kararlı
            # (PLAN.md §6.3).
            smoothed = state.smoothed_label() or label
            result = ExpressionResult(
                label=smoothed,
                label_tr=to_turkish(smoothed),
                confidence=confidence,
                quality=face_quality(face_crop, face),
                face=face,
            )
            state.last_result = result
            results[track_id] = result
            self.classified += 1
            metrics.expressions_classified.labels(
                cam=camera, label=smoothed, usable=str(result.usable).lower()
            ).inc()

        return results

    def last_for(self, camera: str, track_id: int) -> ExpressionResult | None:
        """Bu iz için son bilinen ifade (yeni sınıflandırma olmasa da)."""
        state = self._state.get((camera, track_id))
        return state.last_result if state else None

    def prune(self, max_age_s: float = 60.0) -> None:
        """Uzun süredir görülmeyen izlerin durumunu temizler.

        ⚠ SAAT TUTARLILIĞI
        `process()` çağrısına karenin `captured_at` damgası geliyor ve o
        bir DUVAR saati (ingest/decoder.py · DecodedFrame.timestamp).
        Burada `time.monotonic()` kullanılıyordu — iki farklı zaman
        ekseni. Monotonik değer duvar saatinden çok küçük olduğu için
        `now - v.last_at` daima büyük negatif çıkıyor, hiçbir kayıt asla
        eskimiyor ve sözlük sınırsız büyüyordu. Sessiz bir bellek
        sızıntısı: hata vermez, sadece saatler içinde şişer.
        """
        now = time.time()
        stale = [k for k, v in self._state.items() if now - v.last_at > max_age_s]
        for key in stale:
            del self._state[key]

    def close(self) -> None:
        self._faces.close()
        self._classifier.close()

    @property
    def stats(self) -> dict[str, float]:
        """Kapının nerede eleme yaptığının dökümü.

        Dönüş tipi `object` değil `float`: çağıran taraf bu sayıları
        doğrudan biçimlendiriyor ve `object` her kullanımda elle tip
        daraltması gerektiriyordu. Sayaçlar int, oranlar float — ikisi
        de `float` ile uyumlu.
        """
        return {
            "considered": self.considered,
            "classified": self.classified,
            "gated_small": self.gated_small,
            "gated_recent": self.gated_recent,
            "gated_budget": self.gated_budget,
            "no_face": self.no_face,
            "low_quality": self.low_quality,
            "face_hit_rate": round(self._faces.hit_rate, 3),
            "classify_ratio": (
                round(self.classified / self.considered, 4) if self.considered else 0.0
            ),
        }

    # ─── Kırpma yardımcıları ─────────────────────────────────

    @staticmethod
    def _person_crop(frame: np.ndarray, detection: Detection) -> np.ndarray | None:
        height, width = frame.shape[:2]
        x1 = max(0, int(detection.x1))
        y1 = max(0, int(detection.y1))
        x2 = min(width, int(detection.x2))
        y2 = min(height, int(detection.y2))
        if x2 - x1 < 16 or y2 - y1 < 16:
            return None
        return frame[y1:y2, x1:x2]

    @staticmethod
    def _face_crop(person_crop: np.ndarray, face: FaceBox) -> np.ndarray | None:
        """Yüz kutusunu %10 dolguyla kırpar.

        Dolgu bilinçli: ifade modelleri çene ve alın hattını da görmek
        istiyor, sıfır dolguda yüz kadraja sıkışıyor.
        """
        height, width = person_crop.shape[:2]
        pad_x = face.width * 0.10
        pad_y = face.height * 0.10
        x1 = max(0, int(face.x1 - pad_x))
        y1 = max(0, int(face.y1 - pad_y))
        x2 = min(width, int(face.x2 + pad_x))
        y2 = min(height, int(face.y2 + pad_y))
        if x2 - x1 < MIN_FACE_PX // 2 or y2 - y1 < MIN_FACE_PX // 2:
            return None
        return person_crop[y1:y2, x1:x2]


__all__ = ["MAX_FACES_PER_ROUND", "MIN_PERSON_HEIGHT", "ExpressionStage", "TrackExpression"]
