"""KATMAN A — kamera başına normal davranış profili (PLAN.md §6.4).

Mimari kural 7'nin uygulaması
-----------------------------
    "Her kameranın normali AYRI öğrenilir.
     Koridorda koşmak anomali, spor salonunda değil."

Katman B (rules.py) fizikle tanımlanabilen olayları yakalar: düşme,
koşma, oyalanma. Ama "olağandışı" olmak fizikten çıkmaz — bağlamdan
çıkar. Otoparkta çimenin ortasında duran biri tuhaftır; meydanda değil.
Yoğun caddede 15 kişi normaldir; boş depoda 3 kişi değildir.

Bu dosya o bağlamı **öğreniyor.**

Ne öğreniliyor
--------------
Kare, 32×18'lik bir ızgaraya bölünüyor ve her hücre için:

    ziyaret sayısı   → burada insan olur mu?
    hız dağılımı     → burada ne hızda hareket edilir?
    yön dağılımı     → burada hangi yöne gidilir?     (8 yön)

Artı kamera geneli için kişi sayısı dağılımı.

⚠ NEDEN IZGARA, NEDEN HAM KOORDİNAT DEĞİL
-----------------------------------------
Ham piksel koordinatı ile öğrenmek iki şeyi birden bozar:
  · **Genelleme yok.** (412, 380) noktasında hiç kimse görülmediyse
    oradan geçen ilk kişi "anomali" olur — oysa 5 piksel yanında
    yüzlerce geçiş olmuş olabilir.
  · **Bellek.** 1280×720 = 921 600 hücre × kamera × istatistik.

32×18 = 576 hücre, kare başına ~40×40 piksel. Bir insan gövdesi
kabaca bir hücre kaplıyor — doğal bir çözünürlük.

⚠ NEDEN WELFORD
---------------
Ortalama ve varyans **çevrimiçi** hesaplanıyor: tüm gözlemleri saklamak
20 kamera × 576 hücre × saatlerce veri demekti. Welford algoritması tek
geçişte, sayısal olarak kararlı biçimde ikisini birden veriyor.

Naif yol (`Σx²/n − (Σx/n)²`) büyük sayılarda katastrofik iptal
(catastrophic cancellation) üretir ve varyans **negatif** çıkabilir.

⚠ NEDEN KALICILIK
-----------------
Profil diske yazılmazsa her yeniden başlatmada sistem **kör** olur:
öğrenme sıfırlanır ve saatlerce hiçbir şeyi olağandışı sayamaz. Gözetim
sisteminde bu kabul edilemez — bakım için yapılan bir yeniden başlatma
sistemi savunmasız bırakmamalı.

⚠ SINIRLAMA — dürüstçe raporlanacak
-----------------------------------
Profil "gördüğünü normal sayar". Öğrenme penceresinde gerçek bir olay
olduysa onu da normal öğrenir (kirlenme / poisoning). Üretimde çözümü
denetimli bir öğrenme dönemidir: operatör "bu dönem temizdi" diye
onaylar. Bu proje kapsamında öğrenme denetimsiz ve bu bir kısıttır.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# Izgara çözünürlüğü. 32×18, 16:9 en-boy oranını koruyor.
IZGARA_X = 32
IZGARA_Y = 18

# Yön histogramı kova sayısı. 8 yön = 45°'lik dilimler; insan
# hareketini tarif etmek için yeterli, 16 kova gürültüyü böler.
YON_KOVA = 8

# Bir hücre bu kadar gözlem görmeden o hücre hakkında karar VERİLMEZ.
# Tek gözlemden "burada hız normalde 0.4'tür" demek istatistik değil
# tahmin olur.
HUCRE_ASGARI_ORNEK = 30

# Kamera profili bu kadar örnek görmeden HİÇBİR skor üretmez.
# Soğuk başlangıçta her şey "olağandışı" görünür — henüz normal
# öğrenilmemiştir. Bu koruma olmadan sistem açılışta alarm yağdırır.
PROFIL_ASGARI_ORNEK = 2000

# Standart sapmanın kaç katı "olağandışı" sayılsın.
# 3σ, normal dağılımda örneklerin ~%0.3'üne denk gelir.
SIGMA_ESIK = 3.0

# ─── Ayırt edilebilirlik tabanları (z-skorun bölemeyeceği en küçük sapma) ───
#
# ⚠ Bunlar istatistik değil ÖLÇÜM HASSASİYETİ sayıları. Bir hücrede
# gözlenen sapma bu değerin altındaysa, "değişkenlik yok" demiyoruz —
# "değişkenliği ölçemiyoruz" diyoruz (bkz. `_Welford.z_skor`).
#
# Hız tabanı ölçümden geldi (benchmarks/features_20260826-175748.json):
#   gövde hızı  p50 = 0.30 · p90 = 0.66 · p99 = 0.94 gövde/sn
# 3 FPS örneklemede tek bir keypoint sıçraması ~0.1 gövde/sn'lik sahte
# hız üretiyor. 0.15 seçildi: medyanın yarısı — bundan yakın iki hızı
# ayırt ettiğimizi iddia edemeyiz.
TABAN_SAPMA_HIZ = 0.15

# Kişi sayısı tam sayı; 1 kişilik fark ölçülebilir en küçük fark.
# Sapması 0.3 çıkan bir kamerada 2 kişi fazlası 6 sigma olurdu.
TABAN_SAPMA_KISI = 1.0

# Nadir hücre eşiği: toplam ziyaretin bu oranından az alan hücre
# "buraya pek gidilmez" sayılıyor.
NADIR_HUCRE_ORAN = 0.0005


@dataclass(slots=True)
class _Welford:
    """Çevrimiçi ortalama ve varyans — sayısal olarak kararlı.

    Naif formül (`Σx²/n − ortalama²`) büyük sayılarda iki yakın değeri
    çıkardığı için hassasiyet kaybediyor ve varyans negatif çıkabiliyor.
    Welford her adımda ortalamadan sapmayla çalıştığı için bu sorunu
    yaşamıyor.
    """

    n: int = 0
    ortalama: float = 0.0
    m2: float = 0.0  # sapma karelerinin toplamı

    def ekle(self, x: float) -> None:
        self.n += 1
        delta = x - self.ortalama
        self.ortalama += delta / self.n
        self.m2 += delta * (x - self.ortalama)

    @property
    def varyans(self) -> float:
        return self.m2 / (self.n - 1) if self.n > 1 else 0.0

    @property
    def sapma(self) -> float:
        return math.sqrt(max(0.0, self.varyans))

    def z_skor(self, x: float, taban_sapma: float = 1e-3) -> float:
        """Bu değer ortalamadan kaç standart sapma uzakta?

        ⚠ `taban_sapma` MATEMATİKSEL DEĞİL FİZİKSEL BİR TABAN
        ---------------------------------------------------
        Önceki sürüm sabit `1e-3` kullanıyordu; amacı yalnızca sıfıra
        bölmeyi engellemekti. Ama bu, ölçüm gürültüsünü istatistiksel
        kanıta çeviriyordu.

        Canlı örnek (26.08.2026):

            cam-17 · unusual · skor 0.898
            hiz_sapmasi_sigma = 5.39 · bolge_normal_hiz = 0.06

        O hücrede insanlar neredeyse hiç hareket etmiyor: ortalama 0.06
        gövde/sn, sapma belki 0.02. Normal hızda yürüyen biri (0.17)
        oraya girince z = 5.4 çıkıyor ve "olağandışı" ilan ediliyor.

        İstatistik doğru, fizik yanlış: 0.06 ile 0.17 gövde/sn arasındaki
        fark **bizim ölçme hassasiyetimizin altında.** 3 FPS'te, ~100 px
        boyundaki bir insanda, tek bir keypoint sıçraması bu kadar fark
        yaratıyor. Yani sapması küçük çıkan hücre "burada hiç değişkenlik
        yok" demiyor, "burada yeterince örnek yok / hareket ölçülemeyecek
        kadar küçük" diyor.

        Çözüm: her büyüklüğün kendi **ayırt edilebilirlik eşiği** var ve
        z-skor bunun altına inemez. Sapma tabanı, "bu iki değeri
        birbirinden ayırt edemeyiz" sınırıdır.

        ⚠ Varsayılan hâlâ 1e-3: bu fonksiyon genel amaçlı, tabanı bilen
        taraf ÇAĞIRAN. Sessizce bir fizik varsayımı gömmek, sorunun
        kendisiydi.
        """
        if self.n < 2:
            return 0.0
        return abs(x - self.ortalama) / max(self.sapma, taban_sapma)

    def to_dict(self) -> dict[str, float]:
        return {"n": self.n, "ort": self.ortalama, "m2": self.m2}

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> _Welford:
        return cls(n=int(d["n"]), ortalama=d["ort"], m2=d["m2"])


@dataclass
class KameraNormali:
    """Tek bir kameranın öğrenilmiş normal davranış profili."""

    camera: str
    # Hücre başına ziyaret sayısı — mekânsal doluluk haritası
    ziyaret: np.ndarray = field(
        default_factory=lambda: np.zeros((IZGARA_Y, IZGARA_X), dtype=np.int64)
    )
    # Hücre başına hız istatistiği (yalnızca ziyaret edilen hücreler için)
    hiz: dict[tuple[int, int], _Welford] = field(default_factory=dict)
    # Hücre başına yön histogramı
    yon: dict[tuple[int, int], np.ndarray] = field(default_factory=dict)
    # Kamera geneli kişi sayısı
    kisi_sayisi: _Welford = field(default_factory=_Welford)
    toplam_ornek: int = 0
    guncelleme: float = field(default_factory=time.time)

    # ─── Öğrenme ─────────────────────────────────────────────

    def ogren(
        self,
        ayak_x: float,
        ayak_y: float,
        kare_w: float,
        kare_h: float,
        hiz: float | None,
        yon_rad: float | None,
    ) -> None:
        """Tek bir kişi gözlemini profile işler.

        ⚠ Ayak noktası kullanılıyor, kutu merkezi değil. Kişi kameraya
        yaklaştıkça kutu büyür ve merkez yukarı kayar; ayak noktası
        zemin düzleminde kalır. Mekânsal profil zemine ait olmalı.
        """
        hx, hy = self._hucre(ayak_x, ayak_y, kare_w, kare_h)
        if hx < 0:
            return

        self.ziyaret[hy, hx] += 1
        self.toplam_ornek += 1

        if hiz is not None:
            self.hiz.setdefault((hy, hx), _Welford()).ekle(hiz)

        if yon_rad is not None:
            kova = int((yon_rad + math.pi) / (2 * math.pi) * YON_KOVA) % YON_KOVA
            h = self.yon.setdefault((hy, hx), np.zeros(YON_KOVA, dtype=np.int64))
            h[kova] += 1

    def kare_ogren(self, kisi: int) -> None:
        """Kare seviyesindeki gözlem — kişi sayısı."""
        self.kisi_sayisi.ekle(float(kisi))

    # ─── Skorlama ────────────────────────────────────────────

    @property
    def hazir(self) -> bool:
        """Profil karar verecek kadar öğrendi mi?

        ⚠ Bu kontrol olmadan sistem AÇILIŞTA alarm yağdırır: hiçbir şey
        öğrenilmemişken her gözlem "hiç görülmemiş" olur.
        """
        return self.toplam_ornek >= PROFIL_ASGARI_ORNEK

    def skorla(
        self,
        ayak_x: float,
        ayak_y: float,
        kare_w: float,
        kare_h: float,
        hiz: float | None,
        yon_rad: float | None,
    ) -> tuple[float, dict[str, float]]:
        """Bu gözlem bu kameranın normaline göre ne kadar olağandışı?

        Dönen: (0-1 skor, kanıt sözlüğü)

        ⚠ Üç bağımsız sinyalin EN YÜKSEĞİ alınıyor, ortalaması değil.
        Ortalama alsaydık "doğru yerde, doğru yönde ama üç kat hızlı"
        bir kişi sulanıp kaybolurdu. Anomali doğası gereği TEK bir
        boyutta sıra dışılıktır.
        """
        if not self.hazir:
            return 0.0, {}

        hx, hy = self._hucre(ayak_x, ayak_y, kare_w, kare_h)
        if hx < 0:
            return 0.0, {}

        kanit: dict[str, float] = {}
        skorlar: list[float] = []

        # ── 1. Mekânsal: buraya hiç/nadiren gidilir mi? ──
        ziyaret = int(self.ziyaret[hy, hx])
        beklenen = self.toplam_ornek * NADIR_HUCRE_ORAN
        if ziyaret < beklenen:
            # Hiç görülmemiş hücre en yüksek skor; nadir hücre orantılı
            mekan = 1.0 - (ziyaret / beklenen if beklenen > 0 else 0.0)
            skorlar.append(mekan)
            kanit["nadir_bolge"] = round(mekan, 3)
            kanit["bolge_ziyaret"] = float(ziyaret)

        # ── 2. Hız: bu hücrede bu hız olağan mı? ──
        w = self.hiz.get((hy, hx))
        if hiz is not None and w is not None and w.n >= HUCRE_ASGARI_ORNEK:
            z = w.z_skor(hiz, TABAN_SAPMA_HIZ)
            if z > SIGMA_ESIK:
                skorlar.append(min(1.0, z / (SIGMA_ESIK * 2)))
                kanit["hiz_sapmasi_sigma"] = round(z, 2)
                kanit["bolge_normal_hiz"] = round(w.ortalama, 3)

        # ── 3. Yön: bu hücrede bu yöne gidilir mi? ──
        # "Ters yön" kuralı (PLAN §6.4) burada doğal olarak çıkıyor:
        # koridorda herkes bir yöne gidiyorsa ters yön nadir kovadır.
        h = self.yon.get((hy, hx))
        if yon_rad is not None and h is not None and int(h.sum()) >= HUCRE_ASGARI_ORNEK:
            kova = int((yon_rad + math.pi) / (2 * math.pi) * YON_KOVA) % YON_KOVA
            oran = float(h[kova]) / float(h.sum())
            if oran < 0.02:  # bu yöne gidenlerin %2'den azı
                skorlar.append(min(1.0, (0.02 - oran) / 0.02))
                kanit["yon_orani"] = round(oran, 4)

        if not skorlar:
            return 0.0, {}
        return max(skorlar), kanit

    def kisi_skoru(self, kisi: int) -> tuple[float, dict[str, float]]:
        """Kişi sayısı bu kamera için olağandışı mı?"""
        if not self.hazir or self.kisi_sayisi.n < PROFIL_ASGARI_ORNEK // 10:
            return 0.0, {}
        z = self.kisi_sayisi.z_skor(float(kisi), TABAN_SAPMA_KISI)
        if z <= SIGMA_ESIK:
            return 0.0, {}
        return min(1.0, z / (SIGMA_ESIK * 2)), {
            "kisi_sapmasi_sigma": round(z, 2),
            "kamera_normal_kisi": round(self.kisi_sayisi.ortalama, 2),
        }

    # ─── Yardımcı ────────────────────────────────────────────

    @staticmethod
    def _hucre(x: float, y: float, w: float, h: float) -> tuple[int, int]:
        """Piksel konumunu ızgara hücresine çevirir. Kadraj dışı → (-1,-1)."""
        if w <= 0 or h <= 0:
            return -1, -1
        hx = int(x / w * IZGARA_X)
        hy = int(y / h * IZGARA_Y)
        if not (0 <= hx < IZGARA_X and 0 <= hy < IZGARA_Y):
            return -1, -1
        return hx, hy

    # ─── Kalıcılık ───────────────────────────────────────────

    def to_dict(self) -> dict[str, object]:
        return {
            "camera": self.camera,
            "izgara": [IZGARA_Y, IZGARA_X],
            "toplam_ornek": self.toplam_ornek,
            "guncelleme": self.guncelleme,
            "ziyaret": self.ziyaret.tolist(),
            "kisi_sayisi": self.kisi_sayisi.to_dict(),
            # Sözlük anahtarları JSON'da string olmak zorunda
            "hiz": {f"{k[0]},{k[1]}": v.to_dict() for k, v in self.hiz.items()},
            "yon": {f"{k[0]},{k[1]}": v.tolist() for k, v in self.yon.items()},
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> KameraNormali:
        """Diskten yüklenen sözlükten profil kurar.

        ⚠ `Any` bilinçli: JSON çözümlemesinin çıktısı iç içe ve
        heterojen (liste, sözlük, sayı). `object` ile yazıp her erişimde
        daraltma yapmak, okunmayan bir `cast` yığını üretiyordu.
        Yapı zaten `_yukle` içinde try/except ile korunuyor — bozuk
        profil sistemi durdurmuyor, sıfırdan öğreniyor.
        """
        p = cls(camera=str(d["camera"]))
        p.toplam_ornek = int(d["toplam_ornek"])
        p.guncelleme = float(d.get("guncelleme", time.time()))
        p.ziyaret = np.asarray(d["ziyaret"], dtype=np.int64)
        p.kisi_sayisi = _Welford.from_dict(d["kisi_sayisi"])
        for anahtar, veri in d.get("hiz", {}).items():
            y, x = (int(v) for v in anahtar.split(","))
            p.hiz[(y, x)] = _Welford.from_dict(veri)
        for anahtar, veri in d.get("yon", {}).items():
            y, x = (int(v) for v in anahtar.split(","))
            p.yon[(y, x)] = np.asarray(veri, dtype=np.int64)
        return p


class NormalProfilDeposu:
    """Kamera profillerini tutar ve diske yazar.

    ⚠ Profil kaybı = sistem körlüğü. Yeniden başlatmada profil
    yüklenmezse öğrenme sıfırlanır ve sistem saatlerce hiçbir şeyi
    olağandışı sayamaz. Bakım için yapılan bir restart, gözetim
    sistemini savunmasız bırakmamalı.
    """

    def __init__(self, dizin: Path) -> None:
        self._dizin = dizin
        self._dizin.mkdir(parents=True, exist_ok=True)
        self._profiller: dict[str, KameraNormali] = {}
        self._son_kayit = time.time()

    def al(self, camera: str) -> KameraNormali:
        profil = self._profiller.get(camera)
        if profil is None:
            profil = self._yukle(camera) or KameraNormali(camera=camera)
            self._profiller[camera] = profil
        return profil

    def _yukle(self, camera: str) -> KameraNormali | None:
        yol = self._dizin / f"{camera}.json"
        if not yol.is_file():
            return None
        try:
            return KameraNormali.from_dict(json.loads(yol.read_text(encoding="utf-8")))
        except Exception:
            # Bozuk profil sistemi durdurmamalı — sıfırdan öğrenir.
            return None

    def kaydet(self, aralik_s: float = 60.0) -> int:
        """Profilleri diske yazar (en fazla `aralik_s` sıklığında).

        Her karede yazmak diski boşuna yorar; profil yavaş değişen bir
        şeydir. Dakikada bir yeterli.
        """
        if time.time() - self._son_kayit < aralik_s:
            return 0
        self._son_kayit = time.time()
        n = 0
        for camera, profil in self._profiller.items():
            profil.guncelleme = time.time()
            try:
                (self._dizin / f"{camera}.json").write_text(
                    json.dumps(profil.to_dict(), ensure_ascii=False),
                    encoding="utf-8",
                )
                n += 1
            except OSError:
                continue
        return n

    @property
    def stats(self) -> dict[str, object]:
        return {
            "kamera": len(self._profiller),
            "hazir": sum(1 for p in self._profiller.values() if p.hazir),
            "toplam_ornek": sum(p.toplam_ornek for p in self._profiller.values()),
        }


__all__ = [
    "HUCRE_ASGARI_ORNEK",
    "IZGARA_X",
    "IZGARA_Y",
    "PROFIL_ASGARI_ORNEK",
    "SIGMA_ESIK",
    "KameraNormali",
    "NormalProfilDeposu",
]
