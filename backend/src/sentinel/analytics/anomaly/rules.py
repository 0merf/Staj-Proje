"""KATMAN B — kural tabanlı anomaliler (PLAN.md §6.4).

Neden kural, neden model değil
------------------------------
Anomali için etiketli veri toplanamaz: tanımı gereği "daha önce
görülmemiş olan"dır. "Kavga" için 2000 klip bulunur ama "anormal" diye
bir sınıf yoktur — otoparkta koşmak anormal, spor salonunda değil.

Bu yüzden PLAN §6.4 iki katmanlı: **Katman A** her kameranın kendi
normalini istatistiksel olarak öğrenir (veri toplama gerektirir),
**Katman B** ise fizikle tanımlanabilen, evrensel olayları yakalar.
Bu dosya Katman B.

Katman B'nin üstünlüğü: **ilk günden çalışır.** Öğrenme süresi
beklemez, açıklanabilir ("kutu oranı tersine döndü, gövde 72° eğildi"),
ve yanlış alarm verdiğinde SEBEBİ görülebilir. Katman A tamamlayıcıdır,
alternatif değil.

⚠ HER KURAL BİR EŞİK DEĞİL, BİR KANIT ZİNCİRİDİR
------------------------------------------------
"Kutu oranı > 1.0 ise düşme" demek yanlış olurdu: eğilip bir şey alan
kişi de o oranı verir. Gerçek düşme üç şeyin BİRLİKTE olmasıdır —
oran tersine döner, gövde eğimi ANİ değişir, sonra hareket durur.

Tek koşullu kural yanlış alarm üretir; yanlış alarm operatörün sisteme
güvenini bitirir ve K7 kriterinin (≤3 alarm/kamera-saat) tamamı bunun
üzerine kuruludur.

⚠ HİSTEREZİS ZORUNLU
--------------------
Tek eşikle skor sınırda salınırsa alarm saniyede birkaç kez açılıp
kapanır. Girme eşiği çıkma eşiğinden yüksektir — bir termostatın
çalışma mantığı (PLAN §6.5.3).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum

from sentinel.analytics.features.person import KisiOzellikleri

# ══════════════════════════════════════════════════════════════
#  Eşikler — hepsi gerekçeli
# ══════════════════════════════════════════════════════════════

# ─── Düşme ───
# Ayakta duran bir kişinin kutusu dar ve uzundur (en/boy ~0.35-0.5).
# Yere uzanınca oran tersine döner. 0.9 seçildi: 1.0 (tam kare) fazla
# geç kalır, 0.7 ise eğilen/çömelen kişiyi yakalar.
DUSME_EN_BOY = 0.9
# Gövdenin dikeyden sapması. 55°: oturan kişi ~30°, eğilen ~45°,
# yere yatan >70°. Aradaki bant bilinçli olarak geniş bırakıldı.
DUSME_EGIM_DERECE = 55.0
# ⚠ ASIL AYIRT EDİCİ: eğimin DEĞİŞİM HIZI.
# Düşme ani bir olaydır; eğilerek çanta almak yavaştır. 40°/sn,
# yarım saniyede 20° değişime denk gelir — kontrollü bir hareket
# bu hıza çıkmaz.
DUSME_EGIM_HIZI = 40.0

# ─── Koşma ───
# Birim: gövde boyu/saniye (ölçek normalize, bkz. features/skeleton.py).
# Yürüyüş ~1.4 m/s, ortalama boy ~1.7 m → ~0.8 gövde/sn.
# Koşu ~3 m/s → ~1.8 gövde/sn.
# 1.5 eşiği hızlı yürüyüş ile koşuyu ayırıyor.
#
# ⚠ Bu MUTLAK bir eşik ve bu bir eksikliktir. PLAN §6.4 "kamera
# normalinin 95. persentili × 1.5" diyor — o Katman A'nın işi ve
# öğrenme süresi ister. Katman A devreye girdiğinde bu eşik kamera
# başına uyarlanacak; şimdilik evrensel bir taban kullanılıyor ve
# sınırlaması raporda belirtilecek.
KOSMA_HIZ = 1.5

# ─── Oyalanma ───
# ⚠ 3 saniyelik pencereden ÇIKARILAMAZ — pencere boyu zaten 3 sn.
# Bu yüzden kural motoru iz başına kümülatif süre tutuyor.
OYALANMA_SANIYE = 45.0
# Kişi bu kadar yer değiştirmediyse "aynı yerde" sayılıyor (gövde boyu).
OYALANMA_YARICAP = 0.6

# ─── Kalabalık ───
# ⚠ Mutlak eşik YOK — kamera başına öğrenilen taban çizgisi kullanılıyor.
# Yoğun caddede 15 kişi normal, boş otoparkta 5 kişi anormal. Sabit bir
# sayı ikisinden birinde daima yanlış olurdu.
KALABALIK_KAT = 2.5  # taban çizgisinin bu katı aşılırsa
KALABALIK_ASGARI = 4  # bu sayının altında hiç alarm yok (gürültü)

# ─── Güvenilirlik ───
# Bu tamlığın altındaki özellik vektörü kural değerlendirmesine
# GİRMEZ. Ölçüm (18.08): izlerin medyan ömrü ~4 kare; iki örnekten
# hesaplanmış bir "eğim değişim hızı" gürültüdür.
ASGARI_TAMLIK = 0.25

# ─── Alarm bastırma (PLAN §6.6) ───
#
# ⚠ HİSTEREZİS TEK BAŞINA YETMEDİ — canlı ölçüm gösterdi
# İlk sürümde yalnızca histerezis vardı. 90 saniyelik koşuda 13 anomali
# çıktı, 9'u kalabalık ve aynı kamera tekrar tekrar alarm verdi:
# kişi sayısı eşiğin altına inip tekrar çıkınca histerezis serbest
# bırakıyor ve alarm yeniden doğuyordu (çırpınma / flapping).
#
# Hesap: 9 alarm / 90 sn / 20 kamera ≈ 18 alarm/kamera-saat.
# K7 kriteri ≤3 diyor. Altı kat aşım.
#
# Histerezis "sınırdaki değer titremesin" diye vardır; SOĞUMA ise
# "aynı olay tekrar tekrar bildirilmesin" diye. Farklı problemler,
# ikisi birden gerekiyor.
SOGUMA_KAMERA_S = 60.0   # aynı kamera + aynı tür
SOGUMA_IZ_S = 120.0      # aynı iz, tür fark etmeksizin

# Kalabalık taban çizgisi bu kadar örnek görmeden karar vermez.
# Soğuk başlangıçta taban ilk gözleme eşit oluyor; henüz "normal"i
# öğrenmemişken alarm üretmek, öğrenilmemiş bir eşikle karar vermektir.
KALABALIK_ISINMA = 200


class AnomaliTuru(StrEnum):
    """PLAN §8.1'deki `event_type` ile aynı değerler."""

    DUSME = "fall"
    KOSMA = "running"
    OYALANMA = "loitering"
    KALABALIK = "crowd"


# Her türün taban ciddiyeti. Düşme tıbbi acil olabilir; oyalanma
# yalnızca dikkat çeker. PLAN §6.5.3 seviyeleriyle aynı sözlük.
CIDDIYET: dict[AnomaliTuru, str] = {
    AnomaliTuru.DUSME: "warning",
    AnomaliTuru.KOSMA: "attention",
    AnomaliTuru.OYALANMA: "attention",
    AnomaliTuru.KALABALIK: "attention",
}


@dataclass(slots=True)
class Anomali:
    """Tespit edilen tek bir anomali.

    ⚠ `kanit` alanı zorunlu. Operatöre "anomali var" demek yetmez;
    hangi ölçümün eşiği neden aştığı gösterilmeli. Açıklanabilirlik
    olmadan operatör sisteme güvenmez ve alarmları kapatır — K7'nin
    asıl riski budur (PLAN §8.1 `contributing_signals`).
    """

    camera: str
    tur: AnomaliTuru
    ciddiyet: str
    track_id: int | None
    skor: float  # 0-1, eşiği ne kadar aştığı
    kanit: dict[str, float]
    # Özellik vektörünün tamlığı — düşük tamlıkta üretilmiş bir alarm
    # füzyon katmanında daha az ağırlık almalı.
    tamlik: float

    def to_dict(self) -> dict[str, object]:
        return {
            "cam": self.camera,
            "type": self.tur.value,
            "severity": self.ciddiyet,
            "track": self.track_id,
            "score": round(self.skor, 3),
            "evidence": {k: round(v, 2) for k, v in self.kanit.items()},
            "completeness": round(self.tamlik, 2),
        }


@dataclass(slots=True)
class _IzDurumu:
    """Bir izin kural motorundaki kalıcı durumu.

    3 saniyelik pencere bazı kurallar için yetmiyor: oyalanma dakikalar
    sürer. Bu yüzden pencere DIŞINDA da durum tutuluyor.
    """

    # Kümülatif oyalanma — pencereler arası birikir
    oyalanma_s: float = 0.0
    son_gorulme: float = 0.0
    # Histerezis: şu an hangi anomaliler AKTİF?
    # Aktif bir anomali, çıkma eşiğinin altına inene kadar yeniden
    # alarm üretmez — yoksa saniyede birkaç kez tekrarlanırdı.
    aktif: set[AnomaliTuru] = field(default_factory=set)
    # Bu iz için en son NE ZAMAN alarm üretildi (tür fark etmeksizin).
    # ⚠ `None` = hiç alarm olmadı. `0.0` sentinel olarak KULLANILMAZ:
    # soğuma `simdi - son < 60` diye hesaplanıyor ve `simdi` küçükken
    # (test, sentetik veri, sıfırlanmış saat) `0 - 0 = 0 < 60` çıkıp
    # İLK alarmı bile bastırıyordu. Gerçek kullanımda duvar saati büyük
    # olduğu için görünmezdi — sessiz ve yalnızca belirli koşullarda
    # ortaya çıkan bir hata.
    son_alarm: float | None = None


class KuralMotoru:
    """Katman B — kural tabanlı anomali tespiti.

    Kamera başına durum tutar (mimari kural 7: her kameranın normali
    ayrıdır). Kalabalık kuralı için kamera başına hareketli bir taban
    çizgisi öğreniyor — Katman A'nın basitleştirilmiş bir habercisi.
    """

    def __init__(self) -> None:
        self._izler: dict[tuple[str, int], _IzDurumu] = {}
        # Kamera başına kişi sayısı taban çizgisi (üstel hareketli ort.)
        self._kalabalik_taban: dict[str, float] = {}
        self._kalabalik_ornek: Counter[str] = Counter()
        self._kalabalik_aktif: set[str] = set()
        # (kamera, tür) -> son alarm anı. PLAN §6.6 soğuma kuralı.
        self._son_alarm: dict[tuple[str, AnomaliTuru], float] = {}
        self.bastirilan = 0
        self.toplam: dict[AnomaliTuru, int] = dict.fromkeys(AnomaliTuru, 0)

    # ─── Ana giriş ───────────────────────────────────────────

    def degerlendir(
        self,
        camera: str,
        ozellikler: list[KisiOzellikleri],
        simdi: float,
        dt: float,
    ) -> list[Anomali]:
        """Bir kameranın bir anına ait özellik vektörlerini değerlendirir.

        Args:
            dt: Bu kameranın son değerlendirmesinden bu yana geçen süre.
                Oyalanma birikimi buna göre yapılıyor — kameralar farklı
                hızlarda analiz edildiği için sabit bir adım kullanmak
                yanlış olurdu (uyarlanabilir FPS, PLAN §5.2).
        """
        bulgular: list[Anomali] = []

        for ozellik in ozellikler:
            if ozellik.track_id < 0:
                continue  # kimliksiz izde zamansal kural uygulanamaz
            durum = self._izler.setdefault((camera, ozellik.track_id), _IzDurumu())
            durum.son_gorulme = simdi

            # ⚠ Güvenilirlik kapısı: az örnekten çıkan sayı gürültüdür
            if ozellik.tamlik < ASGARI_TAMLIK:
                continue

            self._oyalanma_biriktir(durum, ozellik, dt)

            for bulgu in (
                self._dusme(camera, ozellik, durum),
                self._kosma(camera, ozellik, durum),
                self._oyalanma(camera, ozellik, durum),
            ):
                if bulgu is None:
                    continue
                # ⚠ Soğuma histerezisin YERİNE değil, ÜSTÜNE.
                # Histerezis sınırdaki titremeyi keser; soğuma aynı
                # olayın tekrar tekrar bildirilmesini keser.
                if self._sogumada_mi(camera, bulgu.tur, durum, simdi):
                    continue
                self._alarm_kaydet(camera, bulgu.tur, durum, simdi)
                bulgular.append(bulgu)
                self.toplam[bulgu.tur] += 1

        kalabalik = self._kalabalik(camera, len(ozellikler))
        if kalabalik is not None and not self._sogumada_mi(
            camera, kalabalik.tur, None, simdi
        ):
            self._alarm_kaydet(camera, kalabalik.tur, None, simdi)
            bulgular.append(kalabalik)
            self.toplam[kalabalik.tur] += 1

        return bulgular

    def _sogumada_mi(
        self, camera: str, tur: AnomaliTuru, durum: _IzDurumu | None, simdi: float
    ) -> bool:
        """Bu alarm yakın zamanda zaten bildirildi mi? (PLAN §6.6)

        İki ayrı soğuma var ve ikisi farklı şeyi koruyor:

          · KAMERA+TÜR : aynı kamerada aynı olay 60 sn'de bir kez.
            Kalabalık gibi kamera seviyesi olaylar için tek koruma bu.

          · İZ : aynı kişi 120 sn'de bir kez, TÜRDEN BAĞIMSIZ. Düşen
            biri yerde kalırken hem "düşme" hem "oyalanma" üretebilir;
            operatöre aynı kişi için art arda iki alarm göndermek
            dikkat dağıtır.

        ⚠ Bastırılan alarm SAYILIYOR. Gizlenmiş bir alarm kaybolmuş
        sayılmamalı: bastırma oranı yükseliyorsa eşikler yanlış demektir
        ve bu bilgi raporda K7'nin yanında durmalı.
        """
        son = self._son_alarm.get((camera, tur))
        if son is not None and simdi - son < SOGUMA_KAMERA_S:
            self.bastirilan += 1
            return True
        if (
            durum is not None
            and durum.son_alarm is not None
            and simdi - durum.son_alarm < SOGUMA_IZ_S
        ):
            self.bastirilan += 1
            return True
        return False

    def _alarm_kaydet(
        self, camera: str, tur: AnomaliTuru, durum: _IzDurumu | None, simdi: float
    ) -> None:
        self._son_alarm[(camera, tur)] = simdi
        if durum is not None:
            durum.son_alarm = simdi

    # ─── Kurallar ────────────────────────────────────────────

    def _dusme(
        self, camera: str, o: KisiOzellikleri, durum: _IzDurumu
    ) -> Anomali | None:
        """Düşme — ÜÇ kanıtın birlikte olması gerekiyor.

        Tek başına hiçbiri yeterli değil:
          · kutu oranı tersine döndü      → eğilen kişi de bunu yapar
          · gövde yatay                   → oturan/yatan kişi de öyle
          · eğim ANİ değişti              → asıl ayırt edici

        Üçü birlikteyse düşmedir. Bu, "kanıt zinciri" tasarımının en
        net örneği: yanlış alarmı önleyen şey eşiğin sıkılığı değil,
        birbirini destekleyen bağımsız sinyaller.
        """
        if o.en_boy_orani is None or o.govde_egimi is None:
            return None

        genis = o.en_boy_orani >= DUSME_EN_BOY
        yatay = o.govde_egimi >= DUSME_EGIM_DERECE
        ani = (o.govde_egimi_degisimi or 0.0) >= DUSME_EGIM_HIZI

        if not (genis and yatay and ani):
            # Histerezis çıkışı: üç koşuldan İKİSİ birden düştüyse
            # anomali bitmiş sayılıyor. Tek koşulun düşmesiyle
            # kapatmak, sınırdaki bir değerde alarmı titretirdi.
            if durum.aktif and sum((genis, yatay, ani)) <= 1:
                durum.aktif.discard(AnomaliTuru.DUSME)
            return None

        if AnomaliTuru.DUSME in durum.aktif:
            return None  # zaten bildirildi, tekrar etme
        durum.aktif.add(AnomaliTuru.DUSME)

        # Skor: eşikleri ne kadar aştığının ortalaması, 0-1'e sıkıştırılmış
        skor = min(
            1.0,
            (
                o.en_boy_orani / DUSME_EN_BOY
                + o.govde_egimi / 90.0
                + (o.govde_egimi_degisimi or 0.0) / (DUSME_EGIM_HIZI * 2)
            )
            / 3.0,
        )
        return Anomali(
            camera=camera,
            tur=AnomaliTuru.DUSME,
            ciddiyet=CIDDIYET[AnomaliTuru.DUSME],
            track_id=o.track_id,
            skor=skor,
            kanit={
                "en_boy_orani": o.en_boy_orani,
                "govde_egimi_derece": o.govde_egimi,
                "egim_degisim_hizi": o.govde_egimi_degisimi or 0.0,
            },
            tamlik=o.tamlik,
        )

    def _kosma(
        self, camera: str, o: KisiOzellikleri, durum: _IzDurumu
    ) -> Anomali | None:
        """Koşma — hız gövde boyuna normalize edilmiş.

        ⚠ Birim kritik: piksel/sn kullansaydık kameraya yakın herkes
        "koşuyor" sayılırdı. Gövde/sn ile 3 metredeki kişi ile 20
        metredeki kişi aynı ölçüye vuruluyor.
        """
        if o.govde_hizi is None:
            return None

        if o.govde_hizi < KOSMA_HIZ:
            # Histerezis: çıkma eşiği girme eşiğinin %75'i.
            # Tek eşikle sınırda salınan bir hız alarmı titretirdi.
            if o.govde_hizi < KOSMA_HIZ * 0.75:
                durum.aktif.discard(AnomaliTuru.KOSMA)
            return None

        if AnomaliTuru.KOSMA in durum.aktif:
            return None
        durum.aktif.add(AnomaliTuru.KOSMA)

        return Anomali(
            camera=camera,
            tur=AnomaliTuru.KOSMA,
            ciddiyet=CIDDIYET[AnomaliTuru.KOSMA],
            track_id=o.track_id,
            skor=min(1.0, o.govde_hizi / (KOSMA_HIZ * 2)),
            kanit={"govde_hizi_govde_sn": o.govde_hizi, "esik": KOSMA_HIZ},
            tamlik=o.tamlik,
        )

    def _oyalanma_biriktir(
        self, durum: _IzDurumu, o: KisiOzellikleri, dt: float
    ) -> None:
        """Kümülatif oyalanma sayacı.

        ⚠ Pencere içinden okunamaz: pencere 3 saniye, oyalanma
        dakikalar sürer. Kişi yer değiştirmediği sürece sayaç birikiyor,
        hareket edince sıfırlanıyor.
        """
        if o.oyalanma_s > 0.0:
            durum.oyalanma_s += dt
        else:
            durum.oyalanma_s = 0.0

    def _oyalanma(
        self, camera: str, o: KisiOzellikleri, durum: _IzDurumu
    ) -> Anomali | None:
        if durum.oyalanma_s < OYALANMA_SANIYE:
            if durum.oyalanma_s == 0.0:
                durum.aktif.discard(AnomaliTuru.OYALANMA)
            return None

        if AnomaliTuru.OYALANMA in durum.aktif:
            return None
        durum.aktif.add(AnomaliTuru.OYALANMA)

        return Anomali(
            camera=camera,
            tur=AnomaliTuru.OYALANMA,
            ciddiyet=CIDDIYET[AnomaliTuru.OYALANMA],
            track_id=o.track_id,
            skor=min(1.0, durum.oyalanma_s / (OYALANMA_SANIYE * 3)),
            kanit={"oyalanma_saniye": durum.oyalanma_s, "esik": OYALANMA_SANIYE},
            tamlik=o.tamlik,
        )

    def _kalabalik(self, camera: str, kisi_sayisi: int) -> Anomali | None:
        """Aşırı kalabalık — KAMERA BAŞINA öğrenilen taban çizgisine göre.

        ⚠ Mimari kural 7'nin en somut uygulaması. Yoğun caddede
        (cam-09) 15 kişi normal; boş otoparkta (cam-07) 5 kişi anormal.
        Sabit bir eşik ikisinden birinde daima yanlış olurdu.

        Taban çizgisi üstel hareketli ortalamayla öğreniliyor. Bu,
        Katman A'nın (IsolationForest + ızgara histogramları) basit bir
        habercisi — aynı ilke, çok daha ucuz.

        ⚠ α küçük (0.02) çünkü taban çizgisi YAVAŞ değişmeli: kalabalık
        anı tabanı da yukarı çekerse kural kendi kendini körleştirir.
        """
        taban = self._kalabalik_taban.get(camera)
        if taban is None:
            self._kalabalik_taban[camera] = float(kisi_sayisi)
            self._kalabalik_ornek[camera] = 1
            return None
        self._kalabalik_taban[camera] = 0.02 * kisi_sayisi + 0.98 * taban
        self._kalabalik_ornek[camera] += 1

        # ⚠ ISINMA KORUMASI — öğrenilmemiş eşikle karar verme
        # Taban çizgisi ilk gözleme eşitleniyor ve α=0.02 ile yavaş
        # yakınsıyor. İlk saniyelerde "normal" henüz bilinmiyor; o
        # sırada alarm üretmek, olmayan bir referansa göre karar
        # vermektir. Canlı koşuda kalabalık alarmlarının çoğu tam da
        # bu ısınma penceresinde çıkmıştı.
        if self._kalabalik_ornek[camera] < KALABALIK_ISINMA:
            return None

        esik = max(float(KALABALIK_ASGARI), taban * KALABALIK_KAT)
        if kisi_sayisi < esik:
            if kisi_sayisi < esik * 0.75:
                self._kalabalik_aktif.discard(camera)
            return None

        if camera in self._kalabalik_aktif:
            return None
        self._kalabalik_aktif.add(camera)

        return Anomali(
            camera=camera,
            tur=AnomaliTuru.KALABALIK,
            ciddiyet=CIDDIYET[AnomaliTuru.KALABALIK],
            track_id=None,  # kamera seviyesinde, kişiye bağlı değil
            skor=min(1.0, kisi_sayisi / (esik * 2)),
            kanit={"kisi": float(kisi_sayisi), "taban": taban, "esik": esik},
            tamlik=1.0,  # kişi sayımı iskelete bağlı değil, hep güvenilir
        )

    # ─── Bakım ───────────────────────────────────────────────

    def buda(self, simdi: float, max_yas_s: float = 30.0) -> int:
        """Kadrajdan çıkmış izlerin durumunu unutur."""
        eskiler = [
            k for k, v in self._izler.items() if simdi - v.son_gorulme > max_yas_s
        ]
        for k in eskiler:
            del self._izler[k]
        return len(eskiler)

    @property
    def stats(self) -> dict[str, int]:
        cikti = {t.value: n for t, n in self.toplam.items()}
        # ⚠ Bastırılan alarm gizlenmiş bir bilgi DEĞİL, raporlanan bir
        # sayı. Oran yükseliyorsa eşikler yanlış demektir ve bu, K7'nin
        # yanında durması gereken bir teşhis sinyali.
        cikti["bastirilan"] = self.bastirilan
        return cikti


__all__ = [
    "ASGARI_TAMLIK",
    "DUSME_EGIM_DERECE",
    "DUSME_EGIM_HIZI",
    "DUSME_EN_BOY",
    "KOSMA_HIZ",
    "OYALANMA_SANIYE",
    "Anomali",
    "AnomaliTuru",
    "KuralMotoru",
]
