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
#  Eşikler — ÖLÇÜLEN normal davranış dağılımından türetilir
# ══════════════════════════════════════════════════════════════
#
# ⚠ 26.08.2026 — ÖLÜ BÖLGE EKLENDİ, SEBEBİ ÖLÇÜM
#
# İlk sürümde her bileşen `deger / doyum` ile 0-1'e eşleniyordu. Bunun
# sessiz bir sonucu vardı: **sıfır noktası yoktu.** Hiçbir şey yapmayan
# bir insan bile sıfırdan büyük bir skor alıyordu, çünkü yürüyen bir
# insanın bileği de hareket eder.
#
# `benchmarks/features_20260826-175748.json` — 20 kamera, 200 sn,
# 40 bin özellik vektörü (kavganın olmadığı sahneler dâhil):
#
#     ÖZELLİK              p50     p90     p99   eski doyum
#     bilek_hizi_azami    0.87    1.80    4.01     3.0
#     bilek_sarsintisi    0.54    1.39    3.24     2.0
#     hareket_enerjisi    0.45    0.85    1.39     1.5
#     govde_hizi          0.30    0.66    0.94       —
#
# Normal davranışın p90'ı doyumun %56-69'unda. Yani sıradan bir yaya
# bileşenlerin çoğunu YARIDAN FAZLA dolduruyor. Toplama girdiğinde:
#
#     bilek 0.66×0.25 + enerji 0.41×0.15 + duruş 0.25×0.10
#     + yakınlık 0.38×0.30 + yaklaşma 1.00×0.20  =  0.563
#
# 0.563 > 0.55 → yan yana geçen iki yabancı "uyarı" veriyordu. Ölçülen
# yanlış alarm hızı **26.4/kamera-saat**, hedef ≤3 (K7).
#
# ⚠ Ayrıca DOYUM_YAKLASMA = 1.0 yanlıştı ve yorumu ölçümle çelişiyordu:
# "bu hızda yaklaşmak koşarak gelmektir" yazıyordu, oysa gövde hızı
# p99 = 0.94 — iki kişi NORMAL yürüyüşle karşılıklı gelince kapanma
# hızı zaten 1.0'ı aşıyor. Bileşen sürekli doygundu.
#
# Çözüm: her bileşene **taban** kondu. Taban = ölçülen normal p90.
# Bileşen tabanın altında SIFIR üretir, tabandan doyuma doğrusal çıkar:
#
#     bilesen = clamp((deger − taban) / (doyum − taban), 0, 1)
#
# Bu, "her kameranın normali ayrı öğrenilir" ilkesinin (mimari kural 7)
# saldırganlık modülündeki karşılığı — şimdilik çiftlik geneli tek taban,
# kamera başına taban Faz 5 işi.


@dataclass(frozen=True, slots=True)
class Esikler:
    """Tırmanma skorunun tüm ayarlanabilir sayıları.

    ⚠ NEDEN SABİT DEĞİL DE NESNE
    Bu sayılar modül sabiti olduğu sürece "değiştir–çalıştır–bak"
    dışında bir kalibrasyon yolu yoktu: aynı veri üzerinde iki farklı
    ayarı YAN YANA koşturmak imkânsızdı. `scripts/calibrate_aggression.py`
    tam olarak bunu yapıyor — tek akıştan besleyip N ayarı aynı anda
    skorluyor. Ölçüm zemini ortak olmadan iki sayı kıyaslanamaz (P-17).
    """

    # ─── Bileşen ağırlıkları (PLAN §6.5.3) ───
    #
    # ⚠ AĞIRLIKLAR GEREKÇELİ, KEYFİ DEĞİL
    # En yüksek ağırlık yakınlık + karşılıklılık birleşiminde: kavganın
    # olmazsa olmaz ön koşulu iki kişinin birbirine yakın ve dönük
    # olması. Hızlı bilek tek başına egzersizdir.
    #
    # En düşük ağırlık duruşta: geniş duruş ve öne eğilme zayıf
    # işaretler, yürüyen herkeste görülür.
    a_yakinlik: float = 0.30
    a_bilek: float = 0.25
    a_yaklasma: float = 0.20
    a_enerji: float = 0.15
    a_durus: float = 0.10

    # ─── Ölü bölge tabanları (ölçülen normal p90) ───
    #
    # ⚠⚠ 07.09.2026 — YENİDEN KALİBRE EDİLDİ (P-47/P-48)
    #
    # Eski değerler `bilek_hizi_azami` (pencere AZAMİSİ) için ölçülmüştü.
    # Modül artık p75 okuyor (P-47: `azami` eklem gürültüsünü ölçüyordu,
    # AUC 0.558 → p75 ile 0.677). Farklı bir büyüklüğü eski büyüklüğün
    # eşiğiyle bantlamak, ölçtüğünden başka bir şeyin istatistiğini
    # kullanmak olurdu.
    #
    # Yeni değerler `kalibre_rwf.py --ciftlik` ile ÇİFTLİK videolarından
    # ölçüldü (18 kamera, cam-16/17 hariç — onlar kasten olay içeriyor;
    # 37 862 örnek, canlı analiz hızında 2.75 FPS):
    #
    #     büyüklük              p50     p90    ESKİ    YENİ
    #     bilek_hizi_p75       0.556   1.529   1.80    1.53
    #     bilek_sarsintisi_p75 0.274   1.259   1.40    1.26
    #     hareket_enerjisi     0.528   1.209   0.85    1.21
    #
    # ⚠ FİZİKSEL MAKULİYET SINIRI UYGULANDI (8.0 gövde/sn üstü atıldı)
    # Sınırsız ölçümde p99 = 24.2 çıkıyordu. Bir boksörün yumruğu ~9 m/s
    # ≈ 5.3 gövde/sn; 24.2 hareket değil eklem hatası. Sınır olmadan
    # doyum p99'dan türetiliyordu ve 36.3 gibi anlamsız bir değer
    # veriyordu — bileşen hiçbir zaman 1.0'a varamazdı.
    #
    # ⭐ Atılan oran bir BULGU: iskeletten türeyen ölçümlerin
    # **%4-6'sı fiziksel olarak imkânsız.** Poz tahmini gürültüsünün
    # doğrudan ölçüsü ve raporda bu şekilde yer alacak.
    #
    # ⚠ HÂLÂ ÇİFTLİK GENELİ TEK TABAN — mimari kural 7 ("her kameranın
    # normali ayrı öğrenilir") saldırganlık modülünde TAM uygulanmış
    # değil. Katman A kamera başına profil tutuyor, bu modül tutmuyor.
    # `kalibre_rwf.py` kamera başına koşturulabilir; bağlanması açık iş.
    taban_bilek_hiz: float = 1.529
    taban_bilek_sarsinti: float = 1.259
    taban_enerji: float = 1.209
    taban_yaklasma: float = 1.00

    # ⚠⚠ 08.09.2026 — UYARLANABİLİR TABAN KALDIRILDI
    #
    # P-52'de kamera başına uyarlanabilir bir ölü bölge tabanı
    # eklenmişti (kameranın kendi p90'ı, çiftlik p50-p90×1.5 arasına
    # sıkıştırılmış). Gerekçesi mimari kural 7'ydi ve makuldü.
    #
    # ⭐ AMA ÖLÇÜLDÜ VE HİÇBİR FAYDASI ÇIKMADI:
    #     etkin taban  1.529 → 1.438
    #     cam-15 ayrım  1.01 → 1.01     (değişmedi)
    #     RWF AUC      0.633 → 0.633    (değişmedi)
    #
    # Sebebi de anlaşıldı: kameranın p90'ı olay sonrası kalabalığı da
    # içeriyor. Doğru taban "bu kameranın NORMALİNİN p90'ı" olmalı ama
    # normali ayırmak için zaten bir dedektöre ihtiyaç var — döngüsel.
    #
    # Hakem denetimi (§5.1) bunu haklı olarak eleştirdi: *"faydası
    # ölçülemeyen bir soyutlama, bakım borcudur."* Kaldırıldı.
    # Aynı gerekçeyle P-51'in "seyirci referansı" da kaldırıldı.
    #
    # ⚠ Bulgu SİLİNMEDİ, problems.md · P-52'de duruyor. Kaldırılan şey
    # kod, öğrenilen şey değil.

    # ─── Doyum noktaları (bu değerde bileşen 1.0) ───
    # Normalin p99'unun biraz üstü: p99 hâlâ normal davranıştır,
    # doyum ancak onu aşan hareket için ayrılmalı.
    # ⚠ 07.09.2026 — doyum artık p90 × 2.0 (p99 DEĞİL).
    # p99, fiziksel sınır uygulandıktan sonra bile uzun kuyruklu:
    # gürültünün bir kısmı 8.0 sınırının altında kalıyor. p90 sağlam
    # bir üst çeyrek göstergesi ve "normalin belirgin üstü" tanımını
    # koruyor.
    doyum_bilek_hiz: float = 3.057
    doyum_bilek_sarsinti: float = 2.519
    doyum_enerji: float = 2.418
    doyum_yaklasma: float = 2.50

    # ─── Histerezis eşikleri ───
    # Girme eşiği çıkma eşiğinden yüksek: skor sınırda salınırsa
    # alarm açılıp kapanmasın.
    #
    # ⚠ 26.08.2026 — ESKİ DEĞERLER (0.35/0.55/0.75) ARTIK GEÇERSİZDİ
    # Ölü bölge ve etkileşim kapısı skorun ölçeğini değiştirdi. Aynı
    # eşikleri bırakmak modülü tümden susturmak olurdu: RWF kavga
    # kliplerinin skor medyanı 0.089, eski uyarı eşiği 0.55.
    #
    # ⚠ Ölçek değişince eşik de değişmeli — yoksa "yanlış alarmı
    # düşürdüm" diye rapor edilen şey aslında sağırlıktır.
    #
    # Yeni değerler İKİ ölçümden birlikte türetildi:
    #
    #   canlı çiftlik, normal kameralar (aggression_calib_20260826-180807)
    #     skor p50 = 0.053 · p99 = 0.189
    #   RWF-2000 val, 60+60 klip (rwf_eval_20260826-181902)
    #     kavga p50 = 0.089 · p75 = 0.137 · p90 = 0.189
    #     normal p50 = 0.063 · p90 = 0.170
    #
    # ⚠ İKİ DAĞILIM İÇ İÇE GEÇMİŞ. AUC = 0.629. Bu bir ayar sorunu
    # değil, skorun kendi sınırı: eşik nereye konursa konsun
    #
    #     eşik 0.05 → kavganın %78'i yakalanır, normalin %53'ü yanar
    #     eşik 0.15 → kavganın %20'si,          normalin %20'si
    #     eşik 0.19 → kavganın  %8'i,           normalin  %3'ü
    #
    # 0.15'te yakalama oranı yanlış pozitif oranına EŞİT — yani şans
    # seviyesi. Kural tabanlı skor tek başına K5'i (F1 ≥ 0.85)
    # taşıyamaz; ölçülen en iyi F1 = 0.712.
    #
    # SEÇİM: sessizlik tarafı. Gerekçe operasyonel —
    #   · Çiftlikte kavga içeriği neredeyse yok; duyarlı eşik
    #     pratikte SADECE yanlış alarm üretir (K7 ≤3/kamera-saat).
    #   · Alarmı kapatan operatör, hiç alarmı olmayan operatörden
    #     kötüdür: sistem varmış gibi görünür ama yoktur.
    #   · Duyarlılık eğitilmiş modelin işi (PLAN §6.5.5, Gün 17-18).
    #     Bu skor onun TABAN ÇİZGİSİ — geçmesi gereken sayı 0.712.
    #
    # ⚠ `dikkat` YAYINLANMIYOR (worker.py · _tirmanma_yayinla), yalnızca
    # skor geçmişine giriyor. Bu yüzden duyarlı tutulabiliyor: K8 (erken
    # uyarı avansı) ölçümü tüm geçmişi kullanacak, bildirim kapısı ayrı.
    esik_dikkat_gir: float = 0.12   # RWF kavgasının ~%30'u — ölçüm için
    esik_dikkat_cik: float = 0.08
    esik_uyari_gir: float = 0.20    # canlı normalin p99'unun (0.189) üstü
    esik_uyari_cik: float = 0.13
    esik_alarm_gir: float = 0.32
    esik_alarm_cik: float = 0.20

    # Zamansal yumuşatma (üstel hareketli ortalama).
    # ⚠ Düşük değer = kararlı ama geç. 0.4 seçildi çünkü ERKEN UYARI
    # hedefimiz var: fazla yumuşatmak avansı doğrudan yer.
    ema_alfa: float = 0.4

    # Skor bu tamlığın altında hesaplanmıyor.
    # Saldırganlık iddiası ciddi; iki örnekten üretilmemeli.
    asgari_tamlik: float = 0.3

    # ─── Etkileşim kapısı ───
    # Açıkken skor `etkilesim × şiddet` olarak çarpılır; etkileşim =
    # max(yakınlık, yaklaşma). Kapalıyken saf ağırlıklı toplam.
    #
    # ⚠ Gerekçesi modülün kendi tanımında: "saldırganlık tanımı gereği
    # ETKİLEŞİMLİDİR". Toplamsal yapı bunu söylüyor ama uygulamıyordu —
    # yalnız koşan biri bilek + enerji + duruştan skor toplayabiliyordu.
    # Çarpımsal kapı iddiayı koda geçirir.
    #
    # ⚠ Kapı YAKINLIK DEĞİL, max(yakınlık, yaklaşma): salt yakınlığa
    # bağlamak erken uyarıyı öldürürdü — birbirine koşan iki kişi henüz
    # yakın değildir, projenin özgün katkısı tam olarak o anı yakalamak.
    etkilesim_kapisi: bool = True
    # Kapı hiçbir zaman tam sıfırlamasın: ölçülemeyen çift bilgisi
    # yüzünden gerçek bir olayı kaçırmayalım (bakış bileşeninde
    # yaşanan hatanın tekrarı olmasın).
    etkilesim_taban: float = 0.15


VARSAYILAN = Esikler()

# Geriye dönük uyumluluk: mevcut kod ve testler bu adları kullanıyor.
A_YAKINLIK = VARSAYILAN.a_yakinlik
A_BILEK = VARSAYILAN.a_bilek
A_YAKLASMA = VARSAYILAN.a_yaklasma
A_ENERJI = VARSAYILAN.a_enerji
A_DURUS = VARSAYILAN.a_durus
DOYUM_BILEK_HIZ = VARSAYILAN.doyum_bilek_hiz
DOYUM_BILEK_SARSINTI = VARSAYILAN.doyum_bilek_sarsinti
DOYUM_ENERJI = VARSAYILAN.doyum_enerji
DOYUM_YAKLASMA = VARSAYILAN.doyum_yaklasma
ESIK_DIKKAT_GIR, ESIK_DIKKAT_CIK = VARSAYILAN.esik_dikkat_gir, VARSAYILAN.esik_dikkat_cik
ESIK_UYARI_GIR, ESIK_UYARI_CIK = VARSAYILAN.esik_uyari_gir, VARSAYILAN.esik_uyari_cik
ESIK_ALARM_GIR, ESIK_ALARM_CIK = VARSAYILAN.esik_alarm_gir, VARSAYILAN.esik_alarm_cik
EMA_ALFA = VARSAYILAN.ema_alfa
ASGARI_TAMLIK = VARSAYILAN.asgari_tamlik


def _bant(deger: float | None, taban: float, doyum: float) -> float:
    """Değeri [taban, doyum] aralığından 0-1'e eşler.

    Tabanın altı SIFIR — "normal davranış kanıt değildir" ilkesi.
    None de sıfır: eksik bilgi kanıt sayılamaz (person.py modül başlığı).
    """
    if deger is None or doyum <= taban:
        return 0.0
    return min(1.0, max(0.0, (deger - taban) / (doyum - taban)))


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

    def __init__(self, esikler: Esikler | None = None) -> None:
        self._izler: dict[tuple[str, int], _IzDurumu] = {}
        self._e = esikler or VARSAYILAN

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
            if kisi.track_id < 0 or kisi.tamlik < self._e.asgari_tamlik:
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
        e = self._e
        # ⚠⚠ 07.09.2026 — `azami` YERİNE p75 (P-47)
        #
        # `bilek_hizi_azami` pencere içindeki AZAMİ hızdı ve ölçüldü ki
        # o azami, hareketi değil **eklem tahmini hatasını** örnekliyor:
        # RWF-2000'de kavga/normal ayırt etme gücü AUC 0.558 (şans
        # seviyesi). Aynı seriden p75 alınca 0.677 — tek bir
        # toplulaştırma değişikliğiyle +0.120.
        #
        # ⚠ `... or kisi.bilek_hizi_azami` YEDEĞİ BİLİNÇLİ:
        # p75 alanı yalnızca yeni özellik çıkarımından geliyor. Eski
        # bir kayıt (kaydedilmiş profil, tekrar oynatılan ölçüm)
        # okunursa alan `None` olur ve modül sessizce susardı. Yedek,
        # o durumda ESKİ davranışa dönüyor — daha kötü ama sağır değil.
        hiz = _bant(
            kisi.bilek_hizi_p75 if kisi.bilek_hizi_p75 is not None
            else kisi.bilek_hizi_azami,
            e.taban_bilek_hiz, e.doyum_bilek_hiz,
        )
        sarsinti = _bant(
            kisi.bilek_sarsintisi_p75 if kisi.bilek_sarsintisi_p75 is not None
            else kisi.bilek_sarsintisi,
            e.taban_bilek_sarsinti, e.doyum_bilek_sarsinti,
        )
        # Sarsıntı hızdan daha ayırt edici: kontrollü bir hareket düzgün
        # hızlanır, vuruş ANİ sıçrar. Bu yüzden daha ağır.
        b["bilek"] = 0.4 * hiz + 0.6 * sarsinti

        # ── 3. Yaklaşma (ERKEN sinyal) ──
        # Negatif yaklaşma hızı = yaklaşıyor. Kavga, iki kişinin
        # birbirine yaklaşmasıyla BAŞLAR — alarm eşiğine varmadan önce
        # görebileceğimiz ilk şey bu.
        if cift is not None and cift.yaklasma_hizi is not None:
            b["yaklasma"] = _bant(
                max(0.0, -cift.yaklasma_hizi), e.taban_yaklasma, e.doyum_yaklasma
            )
        else:
            b["yaklasma"] = 0.0

        # ── 4. Enerji + senkron ──
        enerji = _bant(kisi.hareket_enerjisi, e.taban_enerji, e.doyum_enerji)
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
            e.a_yakinlik * b["yakinlik"]
            + e.a_bilek * b["bilek"]
            + e.a_yaklasma * b["yaklasma"]
            + e.a_enerji * b["enerji"]
            + e.a_durus * b["durus"]
        )

        # ── Etkileşim kapısı ──
        # Saldırganlık iki kişi arasında olur. Yalnız bir kişinin hızlı
        # kol hareketi + yüksek enerjisi, kimseyle etkileşimi yoksa,
        # saldırganlık kanıtı değildir — koşan, el sallayan, spor yapan
        # herkes bu örüntüyü verir.
        if e.etkilesim_kapisi:
            etkilesim = max(b["yakinlik"], b["yaklasma"])
            b["etkilesim"] = etkilesim
            ham *= e.etkilesim_taban + (1.0 - e.etkilesim_taban) * etkilesim

        # ── Zamansal yumuşatma ──
        durum = self._izler.setdefault((camera, kisi.track_id), _IzDurumu())
        durum.son_gorulme = simdi
        durum.ema = e.ema_alfa * ham + (1 - e.ema_alfa) * durum.ema
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

    def _seviye(self, skor: float, mevcut: str) -> str:
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
        if skor >= self._e.esik_alarm_gir:
            return "alarm"
        if skor >= self._e.esik_uyari_gir:
            return "uyari" if mevcut != "alarm" else "alarm"
        if skor >= self._e.esik_dikkat_gir and mevcut in ("sakin", "dikkat"):
            return "dikkat"

        # ── Aşağı: çıkma eşiğinin altına inene kadar seviyeyi koru ──
        if mevcut == "alarm":
            return "alarm" if skor >= self._e.esik_alarm_cik else "uyari"
        if mevcut == "uyari":
            return "uyari" if skor >= self._e.esik_uyari_cik else "dikkat"
        if mevcut == "dikkat":
            return "dikkat" if skor >= self._e.esik_dikkat_cik else "sakin"
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
    "VARSAYILAN",
    "Esikler",
    "TirmanmaSkorlayici",
    "TirmanmaSkoru",
]
