"""Saldırgan davranışın ERKEN tespiti — PLAN.md §6.5.

Projenin özgün katkısı burası
-----------------------------
Literatür "şiddet var/yok" diye sınıflandırır ve doğruluk raporlar.
RWF-2000 üzerinde %90+ doğruluk veren onlarca çalışma var. Ama hepsi
**olay bittikten sonra** karar verir: 5 saniyelik klibi alır, "bu klipte
kavga var" der.

Gözetim sisteminde bunun operasyonel değeri sınırlıdır. Kavga bitmişse
haber vermek geç kalmaktır. Asıl soru şudur:

    **Kaç saniye ÖNCE söyleyebiliyoruz?**

Bu yüzden çıktı bir sınıf değil, **sürekli bir tırmanma skoru.** Skor
zamanla yükselir; eşiği aştığı an ile olayın gerçekten başladığı an
arasındaki fark, ölçtüğümüz **erken uyarı avansıdır** (K8).

Neden iskelet, neden ham video değil
------------------------------------
Ham videoyu 3D-CNN'e (I3D, SlowFast) sokmak GPU'yu bitirir — 20 kamerada
imkânsız. Literatürdeki hafif yaklaşım, YOLO-Pose'un çıkardığı 17 eklem
noktasının zaman serisiyle çalışmaktır (ST-GCN ailesi). İskelet
koordinatları neredeyse sıfır hesaplama yüküyle işlenir.

İkinci fayda **yanlılık**: iskelet ten renginden, kıyafetten ve
görünüşten bağımsızdır (PLAN §12.2).

⚠ NEDEN ÖNCE KURAL TABANLI SKOR, SONRA MODEL
---------------------------------------------
Bu dosya **açıklanabilir, ağırlıklı bir skor** hesaplıyor — eğitilmiş
bir model değil. Üç sebep:

1. **İlk günden çalışır.** Eğitim verisi işlenmeyi beklerken sistem
   ayakta.
2. **Açıklanabilir.** "Skor 0.72 çünkü bilek hızı 3.1, mesafe 0.4 gövde,
   karşılıklı bakıyorlar." Operatör sebebi görmezse alarmı kapatır.
3. **Model için TABAN ÇİZGİSİ.** RWF-2000 üzerinde eğitilecek LightGBM/
   GRU'nun bu skoru geçip geçmediği ölçülebilir. Geçmiyorsa modelin
   kendisi sorgulanır — "model kullandık" demek başarı değildir.

Model geldiğinde bu skor kaybolmayacak: füzyona ikinci bir sinyal olarak
girecek (PLAN §6.6).

⚠ KESİN OLARAK YAPMADIĞIMIZ ŞEY
--------------------------------
Bu modül **kavga tespit etmiyor**, "kavgaya benzeyen fiziksel örüntü"
skoru üretiyor. İkisi aynı şey değil: iki kişinin şakalaşması, dans
etmesi, spor yapması aynı örüntüyü verebilir. Sistem karar vermez,
**dikkat yönlendirir** (PLAN §12.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sentinel.analytics.features.pair import YAKIN_MESAFE, CiftOzellikleri
from sentinel.analytics.features.person import KisiOzellikleri

# ══════════════════════════════════════════════════════════════
#  Bileşen ağırlıkları — PLAN §6.5.3
# ══════════════════════════════════════════════════════════════
#
# ⚠ AĞIRLIKLAR GEREKÇELİ, KEYFİ DEĞİL
# En yüksek ağırlık **yakınlık + karşılıklılık** birleşiminde: kavganın
# olmazsa olmaz ön koşulu iki kişinin birbirine yakın ve dönük olması.
# Hızlı bilek tek başına egzersizdir; yakınlık olmadan anlamı yoktur.
#
# En düşük ağırlık duruşta: geniş duruş ve öne eğilme zayıf işaretler,
# yürüyen herkeste görülür.
A_YAKINLIK = 0.30      # yakın + karşılıklı bakış
A_BILEK = 0.25         # bilek hızı ve sarsıntısı
A_YAKLASMA = 0.20      # hızlı yaklaşma (ERKEN sinyal)
A_ENERJI = 0.15        # genel hareket enerjisi + senkron
A_DURUS = 0.10         # kol yüksekliği, gövde eğimi, duruş genişliği

# ─── Doyum noktaları (bu değerde bileşen 1.0 olur) ───
#
# ⚠ Ölçülen dağılımdan türetildi (benchmarks/speed_20260821.json):
# gövde hızı p99 = 0.94 gövde/sn. Bilek hızı gövdeden hızlıdır (uzuv
# uçları daha çok yol alır); vuruş hareketinde 3-4 gövde/sn bekleniyor.
DOYUM_BILEK_HIZ = 3.0
DOYUM_BILEK_SARSINTI = 2.0
DOYUM_ENERJI = 1.5
DOYUM_YAKLASMA = 1.0   # gövde/sn — bu hızda yaklaşmak koşarak gelmektir

# ─── Histerezis eşikleri (PLAN §6.5.3) ───
# Girme eşiği çıkma eşiğinden yüksek: skor sınırda salınırsa alarm
# açılıp kapanmasın.
ESIK_DIKKAT_GIR, ESIK_DIKKAT_CIK = 0.35, 0.25
ESIK_UYARI_GIR, ESIK_UYARI_CIK = 0.55, 0.40
ESIK_ALARM_GIR, ESIK_ALARM_CIK = 0.75, 0.55

# Zamansal yumuşatma katsayısı (üstel hareketli ortalama).
# ⚠ Düşük değer = kararlı ama geç. 0.4 seçildi çünkü ERKEN UYARI
# hedefimiz var: fazla yumuşatmak avansı doğrudan yer.
EMA_ALFA = 0.4

# Skor bu tamlığın altında hesaplanmıyor.
# Saldırganlık iddiası ciddi; iki örnekten üretilmemeli.
ASGARI_TAMLIK = 0.3


def _doyum(deger: float | None, doyum: float) -> float:
    """Değeri 0-1 aralığına doyurarak eşler."""
    if deger is None:
        return 0.0
    return min(1.0, max(0.0, deger / doyum))


@dataclass(slots=True)
class TirmanmaSkoru:
    """Bir kişi (ve varsa en tehlikeli çifti) için tırmanma değerlendirmesi."""

    track_id: int
    skor: float
    seviye: str  # sakin | dikkat | uyari | alarm
    bilesenler: dict[str, float]
    # Skorun yükselme hızı (birim/saniye). ⚠ ERKEN UYARININ ÖZÜ:
    # yüksek ama SABİT bir skor süregelen bir durumdur; YÜKSELEN skor
    # tırmanmadır. Alarm eşiğine varmadan önce haber verebilmenin tek
    # yolu bu türevi izlemek.
    egim: float
    karsi_taraf: int | None
    tamlik: float

    def to_dict(self) -> dict[str, object]:
        return {
            "track": self.track_id,
            "score": round(self.skor, 3),
            "level": self.seviye,
            "slope": round(self.egim, 3),
            "against": self.karsi_taraf,
            "components": {k: round(v, 3) for k, v in self.bilesenler.items()},
            "completeness": round(self.tamlik, 2),
        }


@dataclass(slots=True)
class _IzDurumu:
    """Bir izin tırmanma geçmişi."""

    ema: float = 0.0
    seviye: str = "sakin"
    gecmis: list[tuple[float, float]] = field(default_factory=list)  # (ts, skor)
    son_gorulme: float = 0.0


class TirmanmaSkorlayici:
    """Kişi + çift özelliklerinden tırmanma skoru üretir."""

    def __init__(self) -> None:
        self._izler: dict[tuple[str, int], _IzDurumu] = {}

    def degerlendir(
        self,
        camera: str,
        kisiler: list[KisiOzellikleri],
        ciftler: list[CiftOzellikleri],
        simdi: float,
    ) -> list[TirmanmaSkoru]:
        """Bir kameranın bir anını değerlendirir.

        ⚠ HER KİŞİ İÇİN EN TEHLİKELİ ÇİFTİ SEÇİLİYOR
        Bir kişi aynı anda birden çok kişiye yakın olabilir (kalabalık).
        Skorunu tüm çiftlerin ortalamasından hesaplamak, tehlikeli tek
        bir etkileşimi kalabalığın içinde sulandırırdı. Tehlike
        maksimumdadır, ortalamada değil.
        """
        # Kişi kimliği → o kişinin dâhil olduğu en tehlikeli çift
        en_yakin: dict[int, CiftOzellikleri] = {}
        for c in ciftler:
            for tid in (c.track_a, c.track_b):
                mevcut = en_yakin.get(tid)
                if mevcut is None or (c.en_yakin_mesafe or 999) < (
                    mevcut.en_yakin_mesafe or 999
                ):
                    en_yakin[tid] = c

        cikti: list[TirmanmaSkoru] = []
        for kisi in kisiler:
            if kisi.track_id < 0 or kisi.tamlik < ASGARI_TAMLIK:
                continue
            cift = en_yakin.get(kisi.track_id)
            sonuc = self._skorla(camera, kisi, cift, simdi)
            if sonuc is not None:
                cikti.append(sonuc)
        return cikti

    # ─── Skor hesabı ─────────────────────────────────────────

    def _skorla(
        self,
        camera: str,
        kisi: KisiOzellikleri,
        cift: CiftOzellikleri | None,
        simdi: float,
    ) -> TirmanmaSkoru | None:
        b: dict[str, float] = {}

        # ── 1. Yakınlık + karşılıklılık (en ağır bileşen) ──
        # ⚠ Çift YOKSA bu bileşen sıfır — ve bu kritik.
        # Yalnız bir kişinin hızlı bilek hareketi egzersizdir.
        # Saldırganlık tanımı gereği etkileşimlidir.
        if cift is not None and cift.en_yakin_mesafe is not None:
            yakinlik = max(0.0, 1.0 - cift.en_yakin_mesafe / (YAKIN_MESAFE * 2))
            bakis = cift.karsilikli_bakis if cift.karsilikli_bakis is not None else 0.0
            # ⚠ BAKIŞ ÇARPAN DEĞİL, GÜÇLENDİRİCİ — test ortaya çıkardı
            # İlk sürüm `yakinlik * bakis` idi. Sorun: 2B iskeletten
            # yönelim her zaman çıkarılamıyor. Kameraya cepheden bakan
            # iki kişinin omuz hattı yatay olur ve dik vektör düşey
            # çıkar; yani "birbirine dönük mü" sorusu cevapsız kalır ve
            # çarpım YAKINLIĞI DA SIFIRLAR.
            #
            # Sonuç: burun buruna duran iki kişi, sırf açı hesaplanamadı
            # diye "yakınlık yok" sayılıyordu.
            #
            # Doğrusu: yakın olmak TEK BAŞINA anlamlıdır (Hall'un
            # kişisel alan mesafesi), karşılıklılık onu güçlendirir.
            # Taban 0.5, karşılıklıysa 1.0'a çıkıyor.
            b["yakinlik"] = yakinlik * (0.5 + 0.5 * bakis)
        else:
            b["yakinlik"] = 0.0

        # ── 2. Bilek dinamiği ──
        hiz = _doyum(kisi.bilek_hizi_azami, DOYUM_BILEK_HIZ)
        sarsinti = _doyum(kisi.bilek_sarsintisi, DOYUM_BILEK_SARSINTI)
        # Sarsıntı hızdan daha ayırt edici: kontrollü bir hareket düzgün
        # hızlanır, vuruş ANİ sıçrar. Bu yüzden daha ağır.
        b["bilek"] = 0.4 * hiz + 0.6 * sarsinti

        # ── 3. Yaklaşma (ERKEN sinyal) ──
        # Negatif yaklaşma hızı = yaklaşıyor. Kavga, iki kişinin
        # birbirine yaklaşmasıyla BAŞLAR — alarm eşiğine varmadan önce
        # görebileceğimiz ilk şey bu.
        if cift is not None and cift.yaklasma_hizi is not None:
            b["yaklasma"] = _doyum(max(0.0, -cift.yaklasma_hizi), DOYUM_YAKLASMA)
        else:
            b["yaklasma"] = 0.0

        # ── 4. Enerji + senkron ──
        enerji = _doyum(kisi.hareket_enerjisi, DOYUM_ENERJI)
        senkron = (cift.senkron_enerji or 0.0) if cift is not None else 0.0
        # ⚠ Senkron TEK BAŞINA kullanılmıyor, enerjiyle ÇARPILIYOR.
        # Yan yana yürüyen iki kişinin hareketleri de korelasyonludur
        # ama enerjileri düşüktür. Yüksek korelasyon ancak yüksek
        # enerjiyle birlikte kavga işaretidir.
        b["enerji"] = enerji * (0.6 + 0.4 * senkron)

        # ── 5. Duruş (en zayıf sinyal) ──
        kol = kisi.kol_yuksekligi_azami or 0.0
        egim = min(1.0, (kisi.govde_egimi or 0.0) / 45.0)
        durus = min(1.0, (kisi.durus_genisligi or 0.0) / 0.5)
        b["durus"] = (kol + egim + durus) / 3.0

        ham = (
            A_YAKINLIK * b["yakinlik"]
            + A_BILEK * b["bilek"]
            + A_YAKLASMA * b["yaklasma"]
            + A_ENERJI * b["enerji"]
            + A_DURUS * b["durus"]
        )

        # ── Zamansal yumuşatma ──
        durum = self._izler.setdefault((camera, kisi.track_id), _IzDurumu())
        durum.son_gorulme = simdi
        durum.ema = EMA_ALFA * ham + (1 - EMA_ALFA) * durum.ema
        durum.gecmis.append((simdi, durum.ema))
        # Yalnızca son 5 saniye tutuluyor — eğim bundan hesaplanıyor
        durum.gecmis = [(t, s) for t, s in durum.gecmis if simdi - t <= 5.0]

        # ── Eğim: tırmanma HIZI ──
        egim_deger = 0.0
        if len(durum.gecmis) >= 2:
            dt = durum.gecmis[-1][0] - durum.gecmis[0][0]
            if dt > 0.5:
                egim_deger = (durum.gecmis[-1][1] - durum.gecmis[0][1]) / dt

        durum.seviye = self._seviye(durum.ema, durum.seviye)

        return TirmanmaSkoru(
            track_id=kisi.track_id,
            skor=durum.ema,
            seviye=durum.seviye,
            bilesenler=b,
            egim=egim_deger,
            karsi_taraf=(
                (cift.track_b if cift.track_a == kisi.track_id else cift.track_a)
                if cift is not None
                else None
            ),
            tamlik=min(kisi.tamlik, cift.tamlik if cift is not None else 1.0),
        )

    @staticmethod
    def _seviye(skor: float, mevcut: str) -> str:
        """Histerezisli seviye kararı (PLAN §6.5.3).

        ⚠ HİSTEREZİS YALNIZCA AŞAĞI YÖNDE — test bunu ortaya çıkardı
        İlk sürüm merdiven gibiydi: "sakin"den yalnızca "dikkat"e
        çıkılabiliyordu, oradan "uyarı"ya, oradan "alarm"a. Yani skor
        bir anda 0.9'a fırlasa bile alarm seviyesine ulaşmak ÜÇ
        değerlendirme turu alıyordu — 4 FPS'te 750 ms gecikme.
        
        Bu, tam da ölçmeye çalıştığımız şeyi yer: **erken uyarı
        avansı** (K8). Sistemin varlık sebebi olayı ERKEN söylemek.

        Doğrusu yangın alarmı mantığı: **duman varsa ANINDA öt, duman
        dağılınca bir süre daha ötmeye devam et.** Yukarı çıkarken
        histerezis yok, aşağı inerken var. Titremeyi önleyen zaten
        aşağı yöndeki gecikme.
        """
        # ── Yukarı: anında, skor hangi seviyeyi gerektiriyorsa ──
        if skor >= ESIK_ALARM_GIR:
            return "alarm"
        if skor >= ESIK_UYARI_GIR:
            return "uyari" if mevcut != "alarm" else "alarm"
        if skor >= ESIK_DIKKAT_GIR and mevcut in ("sakin", "dikkat"):
            return "dikkat"

        # ── Aşağı: çıkma eşiğinin altına inene kadar seviyeyi koru ──
        if mevcut == "alarm":
            return "alarm" if skor >= ESIK_ALARM_CIK else "uyari"
        if mevcut == "uyari":
            return "uyari" if skor >= ESIK_UYARI_CIK else "dikkat"
        if mevcut == "dikkat":
            return "dikkat" if skor >= ESIK_DIKKAT_CIK else "sakin"
        return "sakin"

    def buda(self, simdi: float, max_yas_s: float = 30.0) -> int:
        eskiler = [
            k for k, v in self._izler.items() if simdi - v.son_gorulme > max_yas_s
        ]
        for k in eskiler:
            del self._izler[k]
        return len(eskiler)

    @property
    def aktif_iz(self) -> int:
        return len(self._izler)


__all__ = [
    "ASGARI_TAMLIK",
    "ESIK_ALARM_GIR",
    "ESIK_DIKKAT_GIR",
    "ESIK_UYARI_GIR",
    "TirmanmaSkorlayici",
    "TirmanmaSkoru",
]
