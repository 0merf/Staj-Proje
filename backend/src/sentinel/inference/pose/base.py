"""Poz tahmini arayüzü — KADEME 2a.

Neden ayrı bir kademe (ölçümle verilmiş karar)
----------------------------------------------
İlk plan "tespit ve pozu tek modelde birleştir" idi: `yolo26s-pose.pt`
kutu ve iskeleti tek ileri geçişte üretiyor, dolayısıyla bedava gibi
görünüyordu. Gün 7 ölçümü bunu çürüttü
(`benchmarks/pose_20260815-153539.json`):

| | tespit/kare | kutu alanı p10 |
|---|---|---|
| `yolo26s.pt` (tespit) | 4.46 | 2 490 px² |
| `yolo26s-pose.pt` | 1.93 | 8 185 px² |

Poz modeli, tespit modelinin bulduğu kişilerin yalnızca **%43'ünü**
buluyor ve kaybettikleri küçük/uzak kutular. Güven eşiğini 0.35'ten
0.05'e indirmek bile açığı kapatmıyor (%43 → %63), yani bu bir eşik
kalibrasyonu sorunu değil: COCO keypoint etiketleri yalnızca eklemleri
seçilebilecek kadar büyük kişilere verilir, model küçük hedefleri
"insan değil" öğrenmiştir.

Gözetimde uzaktaki kişi tam da önemli olandır (koridorun ucundaki
kavga). Dedektörü poz modeliyle değiştirmek sessiz bir tespit kaybı
olurdu — P-13 ile aynı sınıf gerileme.

**Karar:** Kademe 1 (tespit) yerinde kalır. Poz, tespit edilen kişilerin
kırpıntılarına ayrı bir kademe olarak uygulanır. Kırpıntı büyütüldüğü
için model artık "büyük insan" görür ve küçük kutularda bile çalışır.

Maliyet (ölçülen, RTX 3070 Laptop · FP16 · 192 px kırpıntı · batch 32):
    tespit             4.49 ms/kare
    + poz kademesi     5.80 ms/kare  (1.30 ms/kişi × 4.46 kişi/kare)
    ────────────────────────────────
    toplam            10.29 ms/kare  → 20 kamerada ~%53 GPU

PLAN.md §2.3 bunu 8.95 ms diye tahmin etmişti (kişi başına 1.0 ms
varsayımıyla); ölçülen 1.30 ms/kişi ile tahmin doğrulandı.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

from sentinel.inference.detector.base import Detection

# Kişi kutusuna eklenen dolgu oranı. Tespit kutusu bazen uzuvları
# kırpar (uzanan kol, kaldırılan ayak); %15 dolgu bunları kırpıntıya
# geri sokar. Saldırganlık modülü tam da bilek konumuna bakacak
# (PLAN.md §6.5.2), yani kırpılan kol doğrudan sinyal kaybıdır.
CROP_PADDING = 0.15

# Kırpıntının modele verildiği kare boyut. Ölçümde 192 ve 256
# karşılaştırıldı: 256 iskelet başarısını %88.2 → %91.3 çıkarıyor ama
# maliyeti %12 artırıyor. 192 seçildi; 256 konfigürasyonla açılabilir.
CROP_SIZE = 192

# Letterbox dolgu rengi — Ultralytics'in kendi ön işlemesinde kullandığı
# nötr gri. Model bu tonu "içerik değil" olarak görmeye alışkın.
PAD_COLOR = 114


@dataclass(frozen=True, slots=True)
class PoseResult:
    """Bir kişiye ait iskelet.

    `keypoints` (17, 3) — COCO-17 sırasında (x, y, güven).
    Koordinatlar **kaynak karenin piksel uzayındadır**, kırpıntının
    değil: çağıran kod kırpıntıyı hiç görmemeli.
    """

    keypoints: np.ndarray
    # Kırpıntıda kişi bulunamadıysa False. Ölçümde kırpıntıların
    # ~%12'si bu durumda (bulanık, aşırı kapanmış, yarı kadraj dışı).
    found: bool = True


@runtime_checkable
class PoseEstimator(Protocol):
    """Bir poz tahmincisinin karşılaması gereken sözleşme.

    `Detector` ile aynı gerekçeyle soyutlandı: Ultralytics AGPL-3.0'dır,
    ürünleşmede RTMPose'a (Apache-2.0) geçmek gerekebilir. O geçiş bu
    protokolü uygulayan yeni bir sınıf yazmaktan ibaret olmalı.
    """

    def estimate(
        self,
        frames: list[np.ndarray],
        detections: list[list[Detection]],
    ) -> list[list[PoseResult | None]]:
        """Kare listesi + kare başına tespit listesi alır, iskelet döndürür.

        Dönen yapı `detections` ile birebir hizalıdır: `out[i][j]`,
        `detections[i][j]` kişisinin iskeletidir (bulunamazsa None).

        Toplu arayüz olmasının sebebi mimaridir: tüm karelerin tüm
        kırpıntıları TEK havuzda toplanıp GPU'ya birlikte verilir.
        Ölçüm bunun ne kadar önemli olduğunu gösteriyor — kırpıntı
        başına maliyet batch 8'de 2.84 ms, batch 32'de 1.30 ms.
        """
        ...

    def warmup(self, batch_size: int) -> None:
        """Sahte kırpıntılarla birkaç geçiş yapar."""
        ...

    def close(self) -> None:
        """Kaynakları serbest bırakır."""
        ...


__all__ = [
    "CROP_PADDING",
    "CROP_SIZE",
    "PAD_COLOR",
    "PoseEstimator",
    "PoseResult",
]
