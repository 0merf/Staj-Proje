"""Füzyon katmanı — beş sinyal, tek risk skoru (PLAN.md §6.6).

Neden bu katman var
-------------------
Beş modül birbirinden bağımsız çalışıyor ve her biri kendi eşiğine
göre alarm üretiyordu. İki sorun doğurdu:

**1. Zayıf sinyaller tek başına alarm veriyordu.**
Katman A ("bu kişi bu bölge için 3σ hızlı") istatistiksel bir sapma,
fiziksel bir olay değil. Tek başına operatörü rahatsız etmeye değmez.
Canlı ölçümde eşik 0.5 iken 63 alarmın 49'u (%78) buradan geliyordu ve
kontrol kamerasında saatte 90 alarm çıkıyordu (K7 hedefi ≤3).

Çözüm olarak eşik 0.85'e çekilmişti ve `worker.py` içinde açıkça
"geçici bir kısıtlama, kalıcı çözüm füzyon" diye yazılmıştı. Bu dosya
o kalıcı çözüm.

**2. Birlikte anlam kazanan sinyaller birleşmiyordu.**
"3σ hızlı" tek başına gürültü; "3σ hızlı **ve** yanındakine hızla
yaklaşıyor **ve** bileği sarsılıyor" bir olaydır. Ayrı ayrı hiçbiri
eşiği aşmaz, birlikte aşmalıdır.

⚠ FÜZYON HER SİNYALİ YUTMAZ — ve bu ayrım kritik
------------------------------------------------
Bir düşme, başka hiçbir sinyal olmasa bile alarmdır. Onu ağırlıklı
toplamın içinde eritmek, tıbbi acil olabilecek bir olayı "diğer
göstergeler sakin" diye bastırmak olurdu.

    DOĞRUDAN ALARM (fiziksel gözlem, kanıt zinciri var)
      düşme · koşma · kalabalık · saldırganlık(alarm seviyesi)

    FÜZYONA GİREN (istatistiksel ipucu, tek başına yetersiz)
      Katman A olağandışılık · oyalanma · saldırganlık(uyarı) · ifade

Kural şu: **gözlem doğrudan konuşur, ipucu ancak toplulukta konuşur.**

⚠ AĞIRLIKLAR PLAN'DAN, KEYFİ DEĞİL
----------------------------------
PLAN §6.6'daki başlangıç ağırlıkları aynen alındı. En yüksek ağırlık
saldırganlıkta çünkü en spesifik sinyal; en düşük ifadede çünkü
bilimsel dayanağı en tartışmalı olan o (LITERATUR §2.4 — Barrett
ve arkadaşlarının yüz ifadesi–duygu eşlemesine yönelik eleştirisi).

⚠ İFADE AĞIRLIĞI ŞU AN ÖLÜ SERMAYE
Kamera çiftliğinde yüzler ~15 piksel; KADEME 2b çalışıyor ama
sınıflandırma üretmiyor (ölçüldü: 2700 aday → 0 sınıflandırma).
Ağırlık yerinde duruyor ki modül gerçek bir kurulumda beslendiğinde
kod değişikliği gerekmesin — ama raporda "bu bileşen bu veri setinde
sıfır katkı verdi" diye yazılacak.
"""

from __future__ import annotations

from dataclasses import dataclass

# ══════════════════════════════════════════════════════════════
#  Ağırlıklar ve eşikler
# ══════════════════════════════════════════════════════════════

# PLAN §6.6 başlangıç ağırlıkları. Toplamı 1.00.
A_SALDIRGANLIK = 0.40  # en spesifik sinyal
A_ANOMALI = 0.25  # Katman A — öğrenilmiş profile göre sapma
A_KURAL = 0.20  # Katman B — fiziksel kural ihlalleri
A_IFADE = 0.10  # ⚠ bilimsel belirsizlik nedeniyle düşük
A_KALABALIK = 0.05

# Zamansal yumuşatma. Saldırganlık modülündekiyle aynı gerekçe:
# düşük değer kararlı ama geç, ve erken uyarı hedefimiz var.
EMA_ALFA = 0.4

# ⚠ EŞİKLER ÖLÇÜMDEN TÜRETİLECEK, ŞİMDİLİK TÜREV
# Katman A'nın tek başına 0.85'te sustuğu biliniyor. Füzyon skoru
# ağırlıklı toplam olduğu için tek bir sinyalin 0.85'i, füzyonda
# 0.25 × 0.85 = 0.21 eder. Yani "yalnızca bir sinyal bağırıyor"
# durumu füzyon eşiğini aşmamalı; "iki sinyal birden orta seviyede"
# aşmalı.
#
#   tek sinyal (anomali 0.9)            → 0.225
#   iki sinyal (anomali 0.7 + sald 0.5) → 0.175 + 0.200 = 0.375
#
# 0.35 tam bu ayrımın üstünde duruyor. K6 ölçümünden sonra
# doğrulanacak (scripts/evaluate_k6.py).
ESIK_UYARI_GIR, ESIK_UYARI_CIK = 0.35, 0.25
ESIK_ALARM_GIR, ESIK_ALARM_CIK = 0.55, 0.40

# Bu tamlığın altındaki özellik vektöründen risk hesaplanmıyor.
ASGARI_TAMLIK = 0.3


@dataclass(frozen=True, slots=True)
class Sinyaller:
    """Bir iz için o andaki beş sinyal. Hepsi 0-1 aralığında.

    ⚠ `None` DEĞİL, 0.0 kullanılıyor ve bu bilinçli bir kayıp.
    Diğer modüllerde "eksik bilgi" ile "sıfır" özenle ayrılıyor
    (person.py). Burada ayrılmıyor çünkü füzyon ağırlıklı bir
    toplam: eksik bir sinyali "bilinmiyor" saymak, kalan sinyalleri
    yeniden ölçeklendirmeyi gerektirirdi ve o da az sinyalli anları
    yapay olarak yükseltirdi.

    Bunun bedeli: bir modül kapalıysa (ör. poz çalışmıyorsa) risk
    skoru sistematik olarak düşük çıkar. Raporda yazılacak.
    """

    saldirganlik: float = 0.0
    anomali: float = 0.0
    kural: float = 0.0
    ifade: float = 0.0
    kalabalik: float = 0.0

    def ham_risk(self) -> float:
        return (
            A_SALDIRGANLIK * self.saldirganlik
            + A_ANOMALI * self.anomali
            + A_KURAL * self.kural
            + A_IFADE * self.ifade
            + A_KALABALIK * self.kalabalik
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "s_saldirganlik": round(self.saldirganlik, 3),
            "s_anomali": round(self.anomali, 3),
            "s_kural": round(self.kural, 3),
            "s_ifade": round(self.ifade, 3),
            "s_kalabalik": round(self.kalabalik, 3),
        }


@dataclass(frozen=True, slots=True)
class RiskSonucu:
    """Bir izin füzyon sonucu."""

    track_id: int
    risk: float
    seviye: str  # sakin | uyari | alarm
    sinyaller: Sinyaller
    # ⚠ Kaç sinyalin katkı verdiği. Tek sinyalli bir 0.4 ile üç
    # sinyalli bir 0.4 aynı şey değil: ikincisi çok daha ikna edici.
    # Operatöre ve rapora bu ayrım gösterilmeli.
    katkida_bulunan: int
    tamlik: float

    def to_dict(self) -> dict[str, object]:
        return {
            "track": self.track_id,
            "risk": round(self.risk, 3),
            "level": self.seviye,
            "katkida_bulunan": self.katkida_bulunan,
            "completeness": round(self.tamlik, 2),
            **self.sinyaller.to_dict(),
        }


@dataclass(slots=True)
class _IzDurumu:
    ema: float = 0.0
    seviye: str = "sakin"
    son_gorulme: float = 0.0


class RiskFuzyonu:
    """Beş sinyali tek risk skorunda birleştirir."""

    # Bir sinyalin "katkıda bulundu" sayılması için gereken en düşük
    # değer. Bunun altı gürültü; saymak, tek gerçek sinyalli bir anı
    # "üç sinyal birden" gibi göstermek olurdu.
    KATKI_ESIGI = 0.15

    def __init__(self) -> None:
        self._izler: dict[tuple[str, int], _IzDurumu] = {}

    def degerlendir(
        self,
        camera: str,
        track_id: int,
        sinyaller: Sinyaller,
        tamlik: float,
        simdi: float,
    ) -> RiskSonucu | None:
        """Bir izin o andaki riskini hesaplar.

        ⚠ SKOR HER ZAMAN HESAPLANIYOR, alarm eşiği yalnızca BİLDİRİM
        kapısı. K6 (anomali AUC) ve K8 (erken uyarı avansı) ölçümleri
        eşiğin altındaki skor geçmişini kullanacak; eşiği ölçüm kapısı
        yapmak o iki kriteri ölçülemez kılardı.
        """
        if tamlik < ASGARI_TAMLIK or track_id < 0:
            return None

        ham = sinyaller.ham_risk()
        durum = self._izler.setdefault((camera, track_id), _IzDurumu())
        durum.son_gorulme = simdi
        durum.ema = EMA_ALFA * ham + (1 - EMA_ALFA) * durum.ema
        durum.seviye = self._seviye(durum.ema, durum.seviye)

        katki = sum(
            1
            for v in (
                sinyaller.saldirganlik,
                sinyaller.anomali,
                sinyaller.kural,
                sinyaller.ifade,
                sinyaller.kalabalik,
            )
            if v >= self.KATKI_ESIGI
        )
        return RiskSonucu(
            track_id=track_id,
            risk=durum.ema,
            seviye=durum.seviye,
            sinyaller=sinyaller,
            katkida_bulunan=katki,
            tamlik=tamlik,
        )

    @staticmethod
    def _seviye(risk: float, mevcut: str) -> str:
        """Histerezisli seviye kararı.

        ⚠ Yukarı yönde histerezis YOK — saldırganlık modülüyle aynı
        gerekçe (yangın alarmı mantığı): duman varsa anında öt, duman
        dağılınca bir süre daha ötmeye devam et. Merdiven gibi çıkmak
        erken uyarı avansını doğrudan yer.
        """
        if risk >= ESIK_ALARM_GIR:
            return "alarm"
        if risk >= ESIK_UYARI_GIR:
            return "uyari" if mevcut != "alarm" else "alarm"
        if mevcut == "alarm":
            return "alarm" if risk >= ESIK_ALARM_CIK else "uyari"
        if mevcut == "uyari":
            return "uyari" if risk >= ESIK_UYARI_CIK else "sakin"
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
    "ESIK_ALARM_GIR",
    "ESIK_UYARI_GIR",
    "RiskFuzyonu",
    "RiskSonucu",
    "Sinyaller",
]
