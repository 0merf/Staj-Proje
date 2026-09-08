"""Öğrenilmiş saldırganlık modeli — ÜRETİM YOLU (P-56).

⭐⭐ NEDEN BU MODÜL VAR — hakem denetiminin en ağır bulgusu
----------------------------------------------------------
`docs/report/denetim-hakem.md` §1.1:

    $ grep -rln "lightgbm|Booster" backend/src/
    (çıktı boş)

Raporlanan bütün model sonuçları — K5 F1 **0.889**, birleşim 0.937 —
yalnızca `backend/scripts/` altındaki **çevrim dışı** betiklerde vardı.
Canlı boru hattı hiçbir öğrenilmiş model çalıştırmıyordu.

Ve bu tek başına bir eksiklik değil, **iki eksikliğin çarpımıydı**:

    fusion.py · A_SALDIRGANLIK = 0.40   ← en yüksek füzyon ağırlığı
    K7 koşusu · aggression alarmı = 0   ← hiç ateşlemedi

Yani füzyonun en ağır sinyali, gerçek görüntüde ayırt etmeyen
(P-52: skorun %90'ı bilgi taşımıyor, oran 1.01) bir kural
kümesinden geliyordu.

Bu modül o boşluğu kapatıyor: eğitilmiş LightGBM modelini **canlı
boru hattında** çalıştırıyor.

NASIL BÖLÜŞÜLÜYOR — model KARAR, kural ATIF
-------------------------------------------
Model **kamera seviyesinde** bir karar veriyor: *"bu kamerada, son 5
saniyede kavga var mı?"* Ölçülmüş başarım bu soru için geçerli
(RWF-2000 val, F1 0.889).

Kural ise **iz seviyesinde**: *"hangi kişi olayın içinde?"* Büyüklüğü
bilgisiz (P-52) ama sıralaması hâlâ anlamlı — yakınlık ve duruş
bileşenleri ateşliyor.

⭐ İkisi rolüne göre kullanılıyor:

    saldirganlik(iz) = model_kamera × pay(iz)
    pay(iz)          = kural(iz) / max(kural)      [ASGARI_PAY, 1.0]

Model *ne kadar* riskli olduğunu, kural *kimin* riskli olduğunu
söylüyor. Alt sınır (`ASGARI_PAY`) bilinçli: kural yolu bu videolarda
düz çıkabiliyor ve o durumda kimseyi sıfırlamamalı — `aggression.py`
içindeki `etkilesim_taban` ile aynı gerekçe.

⚠ BUNUN BİLİNEN SINIRI: kalabalık bir sahnede model "kavga var" derse
ve kural sıralaması düzse, **herkes** yüksek skor alır. Yani atıf
zayıf. Raporda böyle yazılacak; düzeltmesi çift (pair) seviyesinde bir
model ister ve bu kapsam dışı.

⚠⚠ ÖZELLİKLER EĞİTİMLE BİREBİR AYNI OLMAK ZORUNDA
-------------------------------------------------
Model 99 sütunluk bir vektör bekliyor ve sütunların **sırası**
model dosyasıyla birlikte sabitlenmiş. Çevrim içi hesap eğitimden
ayrışırsa hata **SESSİZ** olur: skor üretilir, yalnızca yanlış olur.

Bu yüzden:
  * sütun adları `scripts/train_aggression.py`den okunuyor, kopyalanmıyor
  * özet formülü (azami/p90/ortalama · p75/medyan · aykırılık/sahne)
    orayla birebir aynı
  * `tests/unit/test_model_ozellik.py` iki yolun AYNI girdide AYNI
    vektörü ürettiğini doğruluyor — ayrışma testte patlar

⚠ EKSİK DEĞER `NaN`, SIFIR DEĞİL. Eğitimde de öyleydi; LightGBM
eksikliği veriden öğreniyor. Sıfır yazmak "bu pencerede hareket
yoktu" demek olurdu, oysa gerçek durum "ölçemedik".

Kapatma: `.env` içinde `AGGRESSION_MODEL_ENABLED=false`.
Model dosyası yoksa modül **sessizce devre dışı** kalır ve füzyon
eski kural skoruna döner — çalışmayan bir bağımlılık yüzünden boru
hattı durmaz.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sentinel.logging import get_logger

if TYPE_CHECKING:
    from sentinel.analytics.aggression import TirmanmaSkoru
    from sentinel.analytics.features.person import KisiOzellikleri

log = get_logger(__name__)

# ⚠ Eğitimdeki klip uzunluğuyla AYNI (RWF klipleri 5 sn). Model o
# uzunluktaki özetlerle eğitildi; başka bir pencere, eğitildiğinden
# farklı bir dağılım demek.
PENCERE_S = 5.0

# Kural yolu düz çıkarsa kimseyi sıfırlama (bkz. modül başlığı).
ASGARI_PAY = 0.5

# Bileşen ve ham alan adları — `train_aggression.py` ile AYNI.
# ⚠ Burada kopya duruyor çünkü `src/` bir betikten import edemez
# (betikler pakette değil). Ayrışmayı test yakalıyor.
BILESENLER = ("yakinlik", "bilek", "yaklasma", "enerji", "durus")
HAM_ALANLAR = (
    "bilek_hizi_p75", "bilek_sarsintisi_p75", "bilek_hizi_azami",
    "hareket_enerjisi", "govde_hizi", "kol_yuksekligi_azami",
    "govde_egimi", "govde_egimi_degisimi", "durus_genisligi",
    "en_boy_orani",
)


def _p(sirali: list[float], oran: float) -> float:
    if not sirali:
        return 0.0
    return sirali[min(len(sirali) - 1, int(len(sirali) * oran))]


def _medyan(sirali: list[float]) -> float:
    """Sıralı listenin medyanı — `statistics.median` ile AYNI sonuç.

    ⚠⚠ NEDEN KENDİ UYGULAMAMIZ VAR (P-57)
    `statistics.median` listeyi KENDİ İÇİNDE tekrar sıralıyor ve tip
    dönüşümü yapıyor. Bizim listeler zaten sıralı, dolayısıyla o iş
    tamamen boşa. Ölçüldü: `pencere_ozeti` 24.84 ms sürüyordu ve
    maliyetin neredeyse tamamı bu tür tekrarlardan geliyordu — kare
    bütçesinin (11.10 ms) **iki katından fazlası**.

    ⚠ Çift uzunlukta ortadaki İKİ değerin ortalaması alınıyor —
    `statistics.median` ile birebir aynı davranış. `test_model_ozellik`
    bunu kilitliyor: değer değişseydi eğitim/üretim ayrışırdı.
    """
    n = len(sirali)
    if not n:
        return 0.0
    orta = n // 2
    if n % 2:
        return sirali[orta]
    return (sirali[orta - 1] + sirali[orta]) / 2.0


def pencere_ozeti(
    bilesen_kareleri: list[dict[str, float]],
    ham_kareler: list[list[dict[str, float]]],
) -> dict[str, float]:
    """Pencereyi model girdisi olan özet sözlüğüne çevirir.

    ⚠⚠ BU FONKSİYON `scripts/train_aggression.py · _klip_ozellikleri`
    İLE BİREBİR AYNI ÖZETİ ÜRETMEK ZORUNDA. Ayrışırsa model, eğitildiği
    dağılımdan başka bir dağılımla beslenir ve hata sessiz olur.
    `tests/unit/test_model_ozellik.py` bunu kilitliyor.

    Args:
        bilesen_kareleri: kare başına, o karenin EN RİSKLİ kişisinin
            kural bileşenleri + `skor` + `egim`.
        ham_kareler: kare başına, o karedeki HER kişinin ham özellikleri.
    """
    ozet: dict[str, float] = {}
    if not bilesen_kareleri:
        return ozet

    for alan in (*BILESENLER, "skor"):
        d = sorted(s.get(alan, 0.0) for s in bilesen_kareleri)
        ozet[f"{alan}_azami"] = d[-1]
        ozet[f"{alan}_p90"] = _p(d, 0.90)
        # ⚠ `statistics.fmean` yerine doğrudan toplam/uzunluk: aynı
        # sonuç, çağrı başına ~10× ucuz (P-57).
        ozet[f"{alan}_ortalama"] = sum(d) / len(d)
    ozet["egim_azami"] = max(s.get("egim", 0.0) for s in bilesen_kareleri)

    # Ham özellikler — TÜM kişiler tek havuzda (bantlanmamış, P-48).
    havuz = [k for kare in ham_kareler for k in kare]
    for alan in HAM_ALANLAR:
        d = sorted(s[alan] for s in havuz if alan in s)
        if d:
            ozet[f"ham_{alan}_azami"] = d[-1]
            ozet[f"ham_{alan}_p75"] = _p(d, 0.75)
            ozet[f"ham_{alan}_medyan"] = _medyan(d)

    # ⭐ Sahne-göreli aykırılık (P-49): kare içinde max − medyan.
    # `max` kalabalıkla birlikte tanımı gereği büyüdüğü için tek
    # başına kalabalığı ölçüyordu.
    for alan in HAM_ALANLAR:
        ayk: list[float] = []
        medyanlar: list[float] = []
        for kare in ham_kareler:
            d = sorted(k[alan] for k in kare if alan in k)
            if len(d) < 2:
                continue
            med = _medyan(d)
            ayk.append(d[-1] - med)
            medyanlar.append(med)
        if ayk:
            a = sorted(ayk)
            ozet[f"ayk_{alan}_azami"] = a[-1]
            ozet[f"ayk_{alan}_p75"] = _p(a, 0.75)
            ozet[f"ayk_{alan}_medyan"] = _medyan(a)
            ozet[f"sahne_{alan}_medyan"] = _medyan(sorted(medyanlar))
    return ozet


class SaldirganlikModeli:
    """Eğitilmiş LightGBM modelini canlı boru hattında çalıştırır.

    Kamera başına 5 saniyelik kayan pencere tutuyor ve her çağrıda o
    kameranın kavga olasılığını üretiyor.

    ⚠ Model ya da sütun listesi yoksa `etkin = False` olur ve
    `degerlendir()` `None` döner. Çağıran taraf bunu "model yok, kurala
    dön" diye okur — eksik bir bağımlılık boru hattını durdurmaz.
    """

    __slots__ = ("_bilesen", "_booster", "_ham", "_sutunlar", "etkin")

    def __init__(
        self, model_yolu: Path, sutun_yolu: Path | None = None,
    ) -> None:
        self.etkin = False
        self._booster: Any = None
        self._sutunlar: list[str] = []
        self._bilesen: dict[str, deque[tuple[float, dict[str, float]]]] = {}
        self._ham: dict[str, deque[tuple[float, list[dict[str, float]]]]] = {}

        if not model_yolu.is_file():
            log.warning("saldirganlik_modeli_yok", yol=str(model_yolu))
            return
        sutunlar = self._sutunlari_oku(sutun_yolu)
        if not sutunlar:
            log.warning("saldirganlik_model_sutunlari_yok")
            return
        try:
            import lightgbm as lgb

            self._booster = lgb.Booster(model_file=str(model_yolu))
        except Exception as hata:
            log.warning("saldirganlik_modeli_yuklenemedi", hata=str(hata))
            return

        # ⚠ SÜTUN SAYISI DOĞRULANIYOR. Model dosyası ile sütun listesi
        # ayrı kaynaklardan geliyor; ayrışırlarsa LightGBM sessizce
        # yanlış sütunları okur ve skor bozulur.
        beklenen = self._booster.num_feature()
        if beklenen != len(sutunlar):
            log.error(
                "saldirganlik_model_sutun_uyusmazligi",
                model=beklenen, liste=len(sutunlar),
            )
            return

        self._sutunlar = sutunlar
        self.etkin = True
        log.info("saldirganlik_modeli_yuklendi", ozellik=len(sutunlar))

    @staticmethod
    def _sutunlari_oku(sutun_yolu: Path | None) -> list[str]:
        """Sütun sırasını ölçüm JSON'undan okur.

        ⚠ Sıra model dosyasıyla birlikte sabitlendi; alfabetik yeniden
        üretmek YETMEZ — eğitim `sorted()` kullanıyor ama o sıralamanın
        korunduğunu varsaymak sessiz bir hata kaynağı olurdu.
        """
        if sutun_yolu is not None and sutun_yolu.is_file():
            try:
                return list(
                    json.loads(sutun_yolu.read_text(encoding="utf-8"))["ozellikler"]
                )
            except Exception:
                return []
        return []

    def besle(
        self,
        camera: str,
        kisiler: list[KisiOzellikleri],
        skorlar: list[TirmanmaSkoru],
        ts: float,
    ) -> None:
        """Bu karenin verisini kameranın penceresine ekler."""
        if not self.etkin:
            return

        kare_kisileri = [
            {
                a: float(v)
                for a in HAM_ALANLAR
                if (v := getattr(k, a, None)) is not None
            }
            for k in kisiler if k.track_id >= 0
        ]
        if kare_kisileri:
            self._ham.setdefault(camera, deque()).append((ts, kare_kisileri))

        if skorlar:
            en = max(skorlar, key=lambda s: s.skor)
            satir = dict.fromkeys(BILESENLER, 0.0)
            satir.update({
                k: float(v) for k, v in en.bilesenler.items() if k in BILESENLER
            })
            satir["skor"] = float(en.skor)
            satir["egim"] = float(en.egim)
            self._bilesen.setdefault(camera, deque()).append((ts, satir))

        self._buda(camera, ts)

    def _buda(self, camera: str, ts: float) -> None:
        """Pencereyi süreye göre kırpar.

        ⚠ SINIRSIZ KUYRUK YOK (mimari kural 5). P-44'te füzyon iz
        sözlüğü tam bu yüzden sızdırmıştı: `buda()` yazılmış, hiç
        çağrılmamıştı.
        """
        for depo in (self._bilesen, self._ham):
            d = depo.get(camera)
            while d and ts - d[0][0] > PENCERE_S:
                d.popleft()

    def degerlendir(self, camera: str) -> float | None:
        """Kameranın o andaki kavga olasılığı (0-1), yoksa `None`."""
        if not self.etkin:
            return None
        bilesen = self._bilesen.get(camera)
        if not bilesen:
            return None
        ham = self._ham.get(camera)
        ozet = pencere_ozeti(
            [s for _t, s in bilesen],
            [k for _t, k in ham] if ham else [],
        )
        if not ozet:
            return None
        try:
            import numpy as np

            # ⚠ EKSİK ALAN `NaN` — eğitimle AYNI kural.
            x = np.array([[ozet.get(c, float("nan")) for c in self._sutunlar]])
            return float(self._booster.predict(x)[0])
        except Exception as hata:
            log.warning("saldirganlik_model_tahmin_hatasi", hata=str(hata))
            return None

    def unut(self, camera: str) -> None:
        """Kamera kapandığında pencereyi bırakır."""
        self._bilesen.pop(camera, None)
        self._ham.pop(camera, None)

    def kamera_sayisi(self) -> int:
        return len(self._bilesen)


def iz_paylari(
    skorlar: list[TirmanmaSkoru], asgari: float = ASGARI_PAY,
) -> dict[int, float]:
    """Kural skorlarını [asgari, 1.0] aralığında bir atıf payına çevirir.

    ⚠ Kuralın BÜYÜKLÜĞÜ kullanılmıyor, yalnızca SIRALAMASI. P-52
    kuralın büyüklüğünün bilgi taşımadığını ölçtü (kavga/normal oranı
    1.01) ama yakınlık ve duruş bileşenleri ateşliyor, dolayısıyla
    "kim olayın içinde" sorusuna kısmî cevap veriyor.
    """
    if not skorlar:
        return {}
    azami = max(s.skor for s in skorlar)
    if azami <= 1e-9:
        return {s.track_id: 1.0 for s in skorlar}
    return {
        s.track_id: asgari + (1.0 - asgari) * (s.skor / azami)
        for s in skorlar
    }


__all__ = [
    "ASGARI_PAY",
    "BILESENLER",
    "HAM_ALANLAR",
    "PENCERE_S",
    "SaldirganlikModeli",
    "iz_paylari",
    "pencere_ozeti",
]
