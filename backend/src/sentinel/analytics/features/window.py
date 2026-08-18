"""Kayan pencere — zamansal özelliklerin taşıyıcısı.

Neden gerekli
-------------
"Bu kişi 3 saniyedir hızlanıyor" cümlesini kurabilmek için o kişinin
son 3 saniyesini tutmak gerekiyor. Tek kare hiçbir zamansal bilgi
taşımaz; saldırganlık ve anomalinin tamamı zamansaldır (PLAN §6.5.2).

⚠ TASARIMI BELİRLEYEN ÖLÇÜM (18.08.2026)
----------------------------------------
Kimlik kararlılığı ölçüldü ve tablo şu çıktı:

    20 kamera (doygun)  parçalanma %72.2 · medyan iz ömrü 2 kare
     6 kamera (rahat)   parçalanma %45.1 · medyan iz ömrü 4 kare

4 FPS'te 4 kare = **1 saniye.** PLAN §6.5.2 ise 3 saniyelik pencere
istiyor (12 örnek). Yani izlerin yarısından fazlası "tam pencere"ye
hiç ulaşmıyor.

Bunun iki tasarım sonucu var ve ikisi de bu dosyada:

1. **Kısmi pencereyle de hesap yapılır.** "12 örnek yoksa hiç
   hesaplama" densaydı modül izlerin çoğunda susardı ve saldırganlık
   tespiti pratikte çalışmazdı.

2. **Her sonuç bir TAMLIK skoru taşır.** 2 örnekten çıkan "bilek hızı"
   ile 12 örnekten çıkan aynı sayı aynı güvene sahip değildir. Füzyon
   katmanı bu farkı görmek zorunda; görmezse gürültüyü kanıt sanar.

Parçalanmanın sebebi takipçi ayarı değil **kare kaybı** (sistem doygunken
kareler atılıyor → her kamerada boşluk → izler kopuyor). Yani Gün 16'daki
boru hattı paralelleştirmesi doğrudan kimlik kararlılığını artıracak —
bu, verim çalışmasının ikinci ve daha az bilinen gerekçesi.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

# Zamansal pencere uzunluğu (saniye). PLAN §6.5.3.
PENCERE_S = 3.0

# Anlamlı bir hesap için gereken EN AZ örnek sayısı.
# 2 seçildi çünkü hız/ivme bir FARK: iki nokta olmadan hesaplanamaz.
# Daha yüksek bir eşik (örn. 6) izlerin yarısını dışarıda bırakırdı.
MIN_ORNEK = 2

# Tamlık skorunun 1.0 sayılacağı örnek sayısı: 3 sn × 4 FPS.
TAM_ORNEK = 12

# İki örnek arası bu süreden uzunsa aradaki fark hız sayılmaz.
# Kare atlandığında (stale drop) kişi gerçekte yavaş hareket etmiş olsa
# bile büyük bir konum farkı görünür ve sahte bir "hızlanma" üretir.
MAX_BOSLUK_S = 1.0


@dataclass(slots=True)
class Ornek:
    """Bir izin tek bir andaki durumu."""

    ts: float
    bbox: tuple[float, float, float, float]
    kp: np.ndarray | None
    # Ölçek normalizasyonu için gövde boyu (piksel). None ise bu örnek
    # normalize edilmiş özelliklere katılamaz.
    olcek: float | None
    ayak: np.ndarray


@dataclass(slots=True)
class IzPenceresi:
    """Tek bir takip kimliğinin son PENCERE_S saniyesi.

    `deque` kullanılıyor: baştan silme O(1). Liste olsaydı her karede
    `pop(0)` ile O(n) kayma olurdu ve 20 kamerada ~100 aktif iz var.
    """

    track_id: int
    ornekler: deque[Ornek] = field(default_factory=lambda: deque(maxlen=64))

    def ekle(self, ornek: Ornek) -> None:
        self.ornekler.append(ornek)
        self._buda(ornek.ts)

    def _buda(self, simdi: float) -> None:
        while self.ornekler and simdi - self.ornekler[0].ts > PENCERE_S:
            self.ornekler.popleft()

    # ─── Sorgular ────────────────────────────────────────────

    @property
    def son(self) -> Ornek | None:
        return self.ornekler[-1] if self.ornekler else None

    @property
    def sayi(self) -> int:
        return len(self.ornekler)

    @property
    def sure_s(self) -> float:
        """Penceredeki ilk ve son örnek arasındaki gerçek süre."""
        if len(self.ornekler) < 2:
            return 0.0
        return self.ornekler[-1].ts - self.ornekler[0].ts

    @property
    def hazir(self) -> bool:
        """Herhangi bir zamansal hesap yapılabilir mi?"""
        return self.sayi >= MIN_ORNEK

    @property
    def tamlik(self) -> float:
        """0-1: bu pencere ne kadar dolu?

        ⚠ FÜZYONA GİRMESİ GEREKEN SAYI BUDUR.
        İki örnekten hesaplanmış bir "bilek hızı" ile on iki örnekten
        hesaplanmış aynı değer aynı şey değildir. Bu skor olmadan
        füzyon katmanı ikisini eşit ağırlıkta değerlendirir ve az
        veriden çıkan gürültüyü kanıt sanar.

        Ölçüm (18.08.2026) izlerin medyan ömrünün 4 kare olduğunu
        gösterdi, yani pratikte bu skor çoğu zaman 1.0'ın ALTINDA
        olacak. Bu bir kusur değil, ölçülmüş gerçeğin çıktıya
        taşınması.
        """
        return min(1.0, self.sayi / TAM_ORNEK)

    def gecerli_ciftler(self) -> list[tuple[Ornek, Ornek]]:
        """Ardışık örnek çiftleri — aralarında büyük boşluk OLMAYANLAR.

        Kare atlandığında (geri basınç, eski kare atma) iki örnek
        arasında 1 saniyeden uzun boşluk olabiliyor. O aralıktan hız
        hesaplamak kişiyi olduğundan çok daha hızlı gösterir: aradaki
        yolu bir anda almış gibi görünür.

        Sistem doygunken karelerin %70'i atılıyor (ölçüldü), yani bu
        filtre teorik bir tedbir değil, sık işleyen bir koruma.
        """
        cikti: list[tuple[Ornek, Ornek]] = []
        for onceki, sonraki in zip(self.ornekler, list(self.ornekler)[1:], strict=False):
            dt = sonraki.ts - onceki.ts
            if 0 < dt <= MAX_BOSLUK_S:
                cikti.append((onceki, sonraki))
        return cikti

    def olcek(self) -> float | None:
        """Penceredeki temsili gövde boyu (medyan).

        Tek karenin ölçeği gürültülü: keypoint güveni dalgalanınca
        omuz-kalça mesafesi zıplıyor. Medyan bunu söndürüyor ve
        normalize edilmiş bütün özelliklerin ortak paydası olduğu için
        kararlı olması kritik.
        """
        olcekler = [o.olcek for o in self.ornekler if o.olcek is not None]
        if not olcekler:
            return None
        return float(np.median(olcekler))


class PencereDeposu:
    """Kamera × iz kimliği → pencere.

    ⚠ Kamera bazlı ayrım şart: takipçi kimlikleri kamera içinde
    benzersiz, kameralar arasında DEĞİL. cam-01'deki 7 numaralı iz ile
    cam-09'daki 7 numaralı iz farklı kişiler (tracker/botsort.py).
    """

    def __init__(self, *, unut_s: float = 10.0) -> None:
        self._pencereler: dict[tuple[str, int], IzPenceresi] = {}
        # Bu süre boyunca görülmeyen iz silinir. Takipçinin kendi
        # hafızasından (track_buffer / kare hızı ≈ 7.5 sn) uzun
        # tutuluyor: takipçi izi geri getirebiliyorsa geçmişi de
        # duruyor olmalı, yoksa dönen kişi sıfırdan başlar.
        self._unut_s = unut_s

    def ekle(
        self,
        camera: str,
        track_id: int,
        ornek: Ornek,
    ) -> IzPenceresi:
        anahtar = (camera, track_id)
        pencere = self._pencereler.get(anahtar)
        if pencere is None:
            pencere = IzPenceresi(track_id=track_id)
            self._pencereler[anahtar] = pencere
        pencere.ekle(ornek)
        return pencere

    def al(self, camera: str, track_id: int) -> IzPenceresi | None:
        return self._pencereler.get((camera, track_id))

    def kamera_pencereleri(self, camera: str) -> dict[int, IzPenceresi]:
        """Bir kameranın tüm aktif izleri — çift ve grup özellikleri için."""
        return {
            tid: p for (cam, tid), p in self._pencereler.items() if cam == camera
        }

    def buda(self, simdi: float) -> int:
        """Kadrajdan çıkmış izleri unutur. Silinen sayısını döndürür.

        Çağrılmazsa sözlük sınırsız büyür: 20 kamera × saatte yüzlerce
        yeni kimlik. Kimlik parçalanması yüksek olduğu için (ölçülen
        %45-72) bu birikim hızlıdır — takipçi sürekli yeni kimlik
        üretiyor.
        """
        eskiler = [
            anahtar
            for anahtar, pencere in self._pencereler.items()
            if pencere.son is None or simdi - pencere.son.ts > self._unut_s
        ]
        for anahtar in eskiler:
            del self._pencereler[anahtar]
        return len(eskiler)

    @property
    def aktif_iz_sayisi(self) -> int:
        return len(self._pencereler)


__all__ = [
    "MAX_BOSLUK_S",
    "MIN_ORNEK",
    "PENCERE_S",
    "TAM_ORNEK",
    "IzPenceresi",
    "Ornek",
    "PencereDeposu",
]
