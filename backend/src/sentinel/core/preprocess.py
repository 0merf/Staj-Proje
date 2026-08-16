"""Model girdisi hazırlama — alım ve çıkarım katmanlarının ortak dili.

Neden bu modül var
------------------
Gün 8 ölçümü boru hattının **GPU değil CPU sınırlı** olduğunu gösterdi:
`predict()` süresinin %53'ü Ultralytics'in CPU tarafındaki ön işlemesinde
geçiyordu (yeniden boyutlandırma, renk dönüşümü, normalizasyon, GPU'ya
kopyalama). GPU bu sırada %0-5 kullanımda boş oturuyordu.

Ölçülen üç seçenek (batch 8, aynı kareler, dönüşümlü koşu medyanı):

    A) predict(numpy 1280×720)      6.78 ms/kare   ← eski hâl
    B) predict(numpy 640×640)       6.31 ms/kare
    C) predict(hazır GPU tensörü)   3.87 ms/kare   ← %43 kazanç

Üçü de **aynı tespitleri** veriyor; kazanç doğruluk bedeli olmadan geliyor.

⚠ Kazancın nerede oluştuğu kritik: hazırlık maliyeti (letterbox 1.49 ms +
tensöre çevirme 1.94 ms) *çıkarım worker'ında* ödenirse net kazanç sıfır
olur (3.87 + 3.43 ≈ 6.8 ≈ A). Kazanç ancak hazırlık **20 kamera iş
parçacığına dağıtılırsa** doğuyor.

Peki tek süreçte 20 iş parçacığı GIL yüzünden sıraya girmez mi? Girmez:
`cv2.resize` C kodudur ve çalışırken **GIL'i bırakır**. Yani letterbox
işinin neredeyse tamamı GIL dışında, gerçekten paralel geçer. (Alım
katmanının süreç değil iş parçacığı kullanmasının gerekçesi de bu —
bkz. `ingest/worker.py` modül başlığı.) Çıkarım worker'ı ise TEK
süreçtir; aynı işi orada yapmak seri kalırdı.

Neden BGR saklıyoruz, RGB değil
-------------------------------
Model RGB ister ama poz kademesi kırpıntıları doğrudan bu diziden alıp
OpenCV ile işliyor ve OpenCV BGR bekliyor. Kanal çevirme GPU'da neredeyse
bedava (`flip`), CPU'da ise her kare için ek maliyet. Bu yüzden paylaşımlı
bellekte BGR duruyor, RGB'ye GPU'da geçiliyor.

Neden 640×640 saklamak yeterli — kalite DÜŞMÜYOR
------------------------------------------------
Endişe şuydu: orijinal 1280×720 saklanmazsa poz kırpıntıları düşük
çözünürlükten alınır ve iskelet kalitesi düşer. Ölçüm tersini gösterdi:

    kırpıntı kaynağı      genel başarı
    orijinal 1280×720        %90.7
    640 letterbox            %94.2   ← daha İYİ

Sebep sinyal işleme: 1280'den doğrudan 192'ye inmek örtüşmeye (aliasing)
yol açar. 1280 → 640 → 192 iki kademeli inişte 640 adımı ön filtre görevi
görür. Kademeli küçültme tek adımda büyük atlamadan kalitelidir.

Yan fayda: paylaşımlı bellek slotu 2.76 MB → 1.23 MB (2.2× küçük).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# Modelin gördüğü kare boyutu. Kare (square) olmasının sebebi batch:
# GPU'ya verilen tüm kareler aynı şekilde olmak zorunda, kameralar ise
# farklı çözünürlüklerde (1280×720, 960×720, 900×720).
INPUT_SIZE = 640

# Letterbox dolgu rengi — Ultralytics'in kendi ön işlemesinde kullandığı
# nötr gri. Model bu tonu "içerik değil" olarak görmeye alışkın.
PAD_COLOR = 114


@dataclass(frozen=True, slots=True)
class Letterbox:
    """Bir karenin model uzayına nasıl taşındığının kaydı.

    Kutular model uzayında (640×640) çıkar; operatöre gösterilirken
    kaynak karenin piksel uzayına geri taşınmaları gerekir. Bu dönüşümü
    yapabilmek için gereken her şey burada.
    """

    source_width: int
    source_height: int
    scale: float
    pad_x: int
    pad_y: int

    def to_source_box(
        self, x1: float, y1: float, x2: float, y2: float
    ) -> tuple[float, float, float, float]:
        """Model uzayındaki kutuyu kaynak karenin piksel uzayına taşır.

        Ters dönüşüm: önce dolgu payını çıkar, sonra ölçeği geri al.
        Sonuç kaynak kare sınırlarına kırpılır — model dolgu alanına
        taşan bir kutu üretirse bu negatif koordinat verirdi.
        """
        sx1 = (x1 - self.pad_x) / self.scale
        sy1 = (y1 - self.pad_y) / self.scale
        sx2 = (x2 - self.pad_x) / self.scale
        sy2 = (y2 - self.pad_y) / self.scale
        return (
            max(0.0, min(sx1, self.source_width)),
            max(0.0, min(sy1, self.source_height)),
            max(0.0, min(sx2, self.source_width)),
            max(0.0, min(sy2, self.source_height)),
        )

    def to_source_length(self, value: float) -> float:
        """Uzunluk/hız gibi ölçek bağımlı bir büyüklüğü kaynak uzayına taşır.

        Dolgu payı eklenmez: hız bir FARK olduğu için sabit kayma
        sadeleşir, yalnızca ölçek kalır.
        """
        return value / self.scale

    def to_fields(self) -> dict[str, str]:
        """Valkey Stream alanları düz string olmak zorunda."""
        return {
            "sw": str(self.source_width),
            "sh": str(self.source_height),
            "sc": f"{self.scale:.6f}",
            "px": str(self.pad_x),
            "py": str(self.pad_y),
        }

    @classmethod
    def from_fields(cls, data: dict[str, str]) -> Letterbox | None:
        """Eksik alan varsa None döner — ön işlemesiz eski mesajlar için."""
        if "sc" not in data:
            return None
        return cls(
            source_width=int(data["sw"]),
            source_height=int(data["sh"]),
            scale=float(data["sc"]),
            pad_x=int(data["px"]),
            pad_y=int(data["py"]),
        )


def letterbox(image: np.ndarray, size: int = INPUT_SIZE) -> tuple[np.ndarray, Letterbox]:
    """Kareyi EN-BOY ORANINI KORUYARAK kare tuvale yerleştirir.

    Neden sıkıştırma değil dolgulama: oranı bozmak modelin gördüğü
    insan şeklini bozar. Bu ders poz kademesinde pahalıya öğrenildi —
    kırpıntıları kareye sıkıştırdığımızda iskeletlerin yarısı
    çıkmıyordu (docs/report/problems.md · P-14).

    Dönen dizi **BGR, HWC, uint8** — yani girdiyle aynı düzen, sadece
    küçültülmüş ve dolgulanmış. Böylece kırpıntı alan kod (poz kademesi)
    hiç değişmeden çalışır.
    """
    height, width = image.shape[:2]
    scale = min(size / height, size / width)
    new_h = max(1, round(height * scale))
    new_w = max(1, round(width * scale))

    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), PAD_COLOR, dtype=np.uint8)
    pad_y = (size - new_h) // 2
    pad_x = (size - new_w) // 2
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

    return canvas, Letterbox(
        source_width=width,
        source_height=height,
        scale=scale,
        pad_x=pad_x,
        pad_y=pad_y,
    )


def slot_bytes(size: int = INPUT_SIZE) -> int:
    """Ön işlenmiş bir karenin paylaşımlı bellekte kapladığı yer."""
    return size * size * 3


__all__ = [
    "INPUT_SIZE",
    "PAD_COLOR",
    "Letterbox",
    "letterbox",
    "slot_bytes",
]
