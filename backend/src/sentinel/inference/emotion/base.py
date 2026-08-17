"""KADEME 2b — yüz tespiti ve yüz ifadesi sınıflandırma.

⚠ ÖNCE BİLİMSEL DÜRÜSTLÜK NOTU (PLAN.md §6.3)
----------------------------------------------
Bu modülün adı bilinçli olarak **"duygu tanıma" değil, "yüz ifadesi
sınıflandırma"**. Fark önemli:

Yüz hareketlerinden içsel duygu durumu çıkarmak bilimsel olarak
tartışmalıdır. Barrett ve arkadaşlarının 2019 tarihli kapsamlı
derlemesi, yüz ifadeleriyle duygu kategorileri arasında güvenilir ve
kültürler arası tutarlı bir eşleme bulunmadığını göstermiştir. Model
"üzgün" dediğinde kanıtladığı tek şey, görüntünün eğitim setindeki
"üzgün" etiketli yüzlere benzediğidir — kişinin gerçekten üzgün
olduğu değil.

Gözetim görüntüsü bu belirsizliği ayrıca büyütüyor: yüzler küçük,
açılı, düşük çözünürlüklü ve çoğu zaman hiç görünmüyor.

Bu yüzden tasarım kararları:

· Her çıktı bir **kalite skoru** taşır (yüz boyutu, bulanıklık).
· **"Yüz yeterince net değil"** ayrı ve NORMAL bir sonuçtur.
· Bu modül **tek başına asla alarm üretmez**; yalnızca tırmanma
  skoruna düşük ağırlıkla katkı verir (0.10 — PLAN.md §6.6).
· Yüz görüntüsü **saklanmaz** (KVKK m.6 biyometrik veri; config.py
  içinde `store_face_crops` doğrulayıcısıyla kod düzeyinde yasaklı).

Neden yine de var: literatürde saldırganlık tırmanmasının bileşenleri
arasında yüz ifadesi sayılıyor ve şartname "duygu analizi" istiyor.
Doğru yaklaşım, yeteneği sunup **sınırlarını dürüstçe raporlamaktır.**

KADEME 2b nerede duruyor
------------------------
    Kademe 1  : tespit           → her hareketli karede
    Kademe 2a : poz (iskelet)    → tespit edilen her kişide
    Kademe 2b : yüz + ifade      → SEYREK (aşağıya bakınız)

Seyrek olması zorunlu, çünkü ifade modeli bu ortamda **CPU'da**
koşuyor: yüz başına ~58 ms. Her kişiyi her karede sınıflandırmak
imkânsız. Kapı iki kademeli:

  1. Yüz kutusu yeterince büyük mü (küçük yüzde tahmin gürültüdür)
  2. Bu iz için son sınıflandırmadan bu yana yeterli süre geçti mi
     (duygu 100 ms'de değişmez; 2 saniyede bir yeterli)

⚠ ONNX GPU sağlayıcısı bu ortamda etkinleştirilemedi (onnxruntime-gpu
kurulu ama CUDA sağlayıcısı yüklenmiyor — beklediği cuDNN sürümü yok).
Model CPU'da koşuyor ve bu, seyreltmeyi opsiyonel olmaktan çıkarıp
zorunlu kılıyor. Faz 5'te tekrar denenecek.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

# AffectNet 8 sınıfı — modelin eğitildiği etiket kümesi.
# Türkçeleri panelde gösterilmek için; İngilizce anahtarlar modelden
# geldiği gibi korunuyor ki eşleme hatası sessizce oluşmasın.
EXPRESSION_TR = {
    "Anger": "öfke",
    "Contempt": "küçümseme",
    "Disgust": "tiksinti",
    "Fear": "korku",
    "Happiness": "mutluluk",
    "Neutral": "nötr",
    "Sadness": "üzüntü",
    "Surprise": "şaşkınlık",
}

# Bu boyutun altındaki yüzlerde sınıflandırma yapılmaz.
# PLAN.md §6.3: yüz kutusu ≥ 60×60 piksel. Altında model girdisi
# (224×224) neredeyse tamamen büyütmeden ibaret olur ve çıktı gürültüdür.
MIN_FACE_PX = 60

# Aynı iz için iki sınıflandırma arasındaki en kısa süre.
# Duygu 100 ms'de değişmez; 2 saniye hem yeterli hem bütçeye uygun.
MIN_INTERVAL_S = 2.0

# Bulanıklık eşiği (Laplace varyansı). Altındaki yüzler "net değil"
# sayılır. Hareket bulanıklığı olan yüzde ifade tahmini güvenilmez.
MIN_SHARPNESS = 25.0


@dataclass(frozen=True, slots=True)
class FaceBox:
    """Kişi kutusu içinde bulunmuş bir yüz. Koordinatlar KAYNAK karede."""

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1


@dataclass(frozen=True, slots=True)
class ExpressionResult:
    """Bir yüzün ifade sınıflandırması.

    ⚠ `label` bir DUYGU İDDİASI DEĞİL, bir görüntü benzerlik etiketidir.
    Panelde ve raporda "üzgün görünüyor" diye sunulur, "üzgün" diye
    değil — aradaki fark bilimsel dürüstlüktür (modül başlığı).
    """

    label: str
    label_tr: str
    confidence: float
    # Yüz ne kadar güvenilir bir girdiydi: boyut ve netlikten türetilir.
    # Düşükse etiket gösterilmemeli.
    quality: float
    face: FaceBox

    @property
    def usable(self) -> bool:
        """Bu sonuç operatöre gösterilecek kadar güvenilir mi?"""
        return self.quality >= 0.5 and self.confidence >= 0.4

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "tr": self.label_tr,
            "conf": round(self.confidence, 3),
            "q": round(self.quality, 2),
        }


def face_quality(face_crop: np.ndarray, face: FaceBox) -> float:
    """Yüzün sınıflandırma için ne kadar uygun olduğunu 0-1 arası puanlar.

    İki bileşen:
      · **boyut** — 60 px eşiğinden 160 px'e kadar doğrusal artıyor
      · **netlik** — Laplace varyansı; hareket bulanıklığını yakalar

    Neden gerekli: model her girdiye bir etiket verir, girdinin anlamlı
    olup olmadığını söylemez. 20×20 bulanık bir lekeye "öfke" demesi
    teknik olarak bir çıktıdır ama bilgi değildir. Kalite skoru bu
    ayrımı çıktıya taşıyor.
    """
    import cv2

    size = min(face.width, face.height)
    size_score = float(np.clip((size - MIN_FACE_PX) / (160.0 - MIN_FACE_PX), 0.0, 1.0))

    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY) if face_crop.ndim == 3 else face_crop
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sharp_score = float(np.clip(sharpness / (MIN_SHARPNESS * 4), 0.0, 1.0))

    # Geometrik ortalama: iki bileşenden biri kötüyse sonuç kötü olsun.
    # Aritmetik ortalama, büyük ama bulanık bir yüze iyi puan verirdi.
    return float(np.sqrt(size_score * sharp_score))


@runtime_checkable
class FaceDetector(Protocol):
    """Kişi kırpıntısında yüz arayan bileşen."""

    def detect(self, person_crop: np.ndarray) -> FaceBox | None:
        """En belirgin yüzü döndürür (yoksa None).

        Kırpıntı başına tek yüz yeterli: kırpıntı zaten tek kişinin
        kutusundan alınıyor.
        """
        ...

    def close(self) -> None: ...


@runtime_checkable
class ExpressionClassifier(Protocol):
    """Yüz kırpıntısını ifade sınıfına eşleyen bileşen."""

    def classify(self, face_crops: list[np.ndarray]) -> list[tuple[str, float]]:
        """Yüz listesi alır, (etiket, güven) listesi döndürür."""
        ...

    def close(self) -> None: ...


__all__ = [
    "EXPRESSION_TR",
    "MIN_FACE_PX",
    "MIN_INTERVAL_S",
    "MIN_SHARPNESS",
    "ExpressionClassifier",
    "ExpressionResult",
    "FaceBox",
    "FaceDetector",
    "face_quality",
]
