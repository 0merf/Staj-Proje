"""Yüz ifadesi → risk sinyali eşlemesi (w4 = 0.10).

Neden bu dosya var — ve neden 03.09.2026'ya kadar yoktu
---------------------------------------------------------
Kademe 2b (yüz tespiti + ifade sınıflandırma) Gün 13'te yazıldı,
Gün 14'te boru hattına bağlandı ve çalışıyor. Sonuç `Track.expression`
alanına yazılıyor, oradan WebSocket'e gidiyor ve **panelde görünüyor.**

Ama analitik zincire hiç girmiyordu. `analytics/worker.py` füzyon
sinyallerini kurarken `ifade=0.0` diye sabit yazıyordu.

Daha kötüsü, iki ayrı yerde şu iddia yazılıydı:

> *"Bağlantı yeri hazır; gerçek bir kurulumda beslendiğinde kod
>  değişikliği gerekmeyecek."*

Bu **yanlıştı.** Bağlantı yeri hazır değildi: analytics worker
mesajdaki `expr` alanını hiç okumuyordu. Yüzler 60 pikselden büyük
olsaydı bile skor füzyona ulaşmazdı. İddia ölçülmemişti — kimse
"peki beslenirse gerçekten akar mı" diye bakmamıştı.

Bu, şartname açısından önemli bir boşluktu: **"duygu analizi"
şartnamedeki üç yetenekten biri** ve sistemin kararına hiç
katılmıyordu. Ekrana çıkmak ile karara girmek aynı şey değil.

Neden ifade düşük ağırlıklı ve neden yine de var
------------------------------------------------
Proje planının bilimsel uyarısı: yüz hareketleriyle içsel duygu
arasında güvenilir, kültürler arası tutarlı bir eşleme bulunmadığı
gösterilmiştir (Barrett vd., 2019). Gözetim
görüntüsünde yüzler ayrıca küçük, açılı ve bulanık.

Bu yüzden modül:
  · "duygu okuma" değil **"yüz ifadesi sınıflandırma"** olarak anılıyor
  · tek başına asla alarm üretmiyor (füzyon ağırlığı 0.10)
  · her çıktı bir **güven** ve bir **kalite** skoru taşıyor
  · "yüz yeterince net değil" ayrı bir durum ve sık görülmesi normal

Skor güven ve kaliteyle çarpılıyor — bu bir süsleme değil
Model her girdiye bir etiket verir; girdinin anlamlı olup olmadığını
söylemez. 20×20 bulanık bir lekeye "öfke" demesi teknik olarak bir
çıktıdır ama bilgi değildir (`emotion/base.py · face_quality`).
Çarpım, o ayrımı skora taşıyor: düşük kaliteli bir "öfke" füzyona
neredeyse hiç katkı vermiyor, yüksek kaliteli bir "öfke" veriyor.

Eşleme ahlâki değil, davranışsal
"Öfke = kötü insan" demiyoruz. Diyoruz ki: kavga tırmanışının
görüntüsel işaretlerinden biri öfke ifadesidir ve **başka sinyallerle
birlikte** dikkat çekmeye değer. Tek başına hiçbir şey ifade etmiyor —
füzyonun katkı eşiği (0.15) ve "en az iki sinyal" kuralı bunu yapısal
olarak garanti ediyor.

Korku da sayılıyor — ve sebebi mağdur tarafı
Saldırganlık iki taraflı bir olay. Öfkeli bir yüzün yanındaki korkmuş
yüz, olayın kendisi kadar bilgi verir. Yalnızca öfkeye bakmak,
tırmanmanın yarısını görmek olurdu.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

# Etiket → temel risk katkısı (0-1). Anahtarlar `emotion/base.py`
# içindeki `EXPRESSION_TR` ile aynı olmak zorunda — model çıktısı
# İngilizce anahtarla geliyor ve sessiz bir yazım hatası tüm sinyali
# sıfırlar (eşleşmeyen etiket 0.0 döner, hiçbir hata vermez).
#
# Değerler ölçülmüş değil, gerekçelendirilmiş başlangıç değerleri.
# Proje planı, ağırlıkların "Faz 5'te doğrulama setinde optimize
# edileceğini" söylüyor; bu tablo da o kapsamda. Raporda "başlangıç
# değeri, optimize edilmedi" diye yazılacak — ölçülmüş gibi
# sunulmayacak.
IFADE_RISK: dict[str, float] = {
    "Anger": 1.00,      # tırmanmanın en doğrudan yüz işareti
    "Fear": 0.80,       # mağdur tarafı — olayın diğer yarısı
    "Disgust": 0.40,    # husumet göstergesi ama zayıf ve belirsiz
    "Contempt": 0.40,
    "Surprise": 0.20,   # irkilme olabilir, sevinç de olabilir — belirsiz
    "Sadness": 0.20,    # sıkıntı sinyali; saldırganlık göstergesi değil
    "Neutral": 0.00,
    "Happiness": 0.00,
}

# Bu kalitenin altındaki sınıflandırma hiç dikkate alınmıyor.
# Çarpımla söndürmek yetmiyor: kalite 0.15 olan bir "öfke" çarpımdan
# 0.15 çıkar ve füzyonun katkı eşiği de 0.15. Yani gürültü tam sınırda
# "katkıda bulunan sinyal" sayılabilirdi ve "en az iki sinyal" kuralını
# gürültüyle doldurmak, o kuralın varlık sebebini ortadan kaldırırdı.
ASGARI_KALITE = 0.35

# Aynı iz için son N sınıflandırmanın ortalaması.
# Kademe 2b iz başına ~2 saniyede bir çalışıyor, yani 5 örnek ~10
# saniyelik bir pencere. Tek bir kareye dayanan ifade kararı, yüzün
# o anki açısına ve hareket bulanıklığına aşırı duyarlı.
PENCERE = 5

# Bir iz bu süre boyunca hiç görünmezse durumu atılıyor. Aksi hâlde
# uzun koşuda sözlük sınırsız büyürdü (mimari kural 5: her şey sınırlı).
MAX_YAS_S = 60.0


def ham_skor(expr: Any) -> float:
    """Tek bir ifade çıktısını 0-1 risk katkısına çevirir.

    `expr`, mesajdaki `detections[i]["expr"]` alanı:
        {"label": "Anger", "tr": "öfke", "conf": 0.82, "q": 0.61}

    Alan yoksa 0.0 dönüyor ve bu sık görülecek — normaldir.
    Kademe 2b seyrek çalışıyor (bütçe) ve yüzlerin çoğu eşiğin
    altında. "İfade yok" bir arıza değil, beklenen durum.
    """
    if not isinstance(expr, dict):
        return 0.0
    taban = IFADE_RISK.get(str(expr.get("label", "")), 0.0)
    if taban <= 0.0:
        return 0.0

    kalite = float(expr.get("q", 0.0) or 0.0)
    if kalite < ASGARI_KALITE:
        return 0.0
    guven = float(expr.get("conf", 0.0) or 0.0)
    return max(0.0, min(1.0, taban * guven * kalite))


class IfadeSinyali:
    """İz başına ifade riskini yumuşatarak tutar.

    Neden durum tutuluyor — ve neden bu bir "hatırlama" değil
    kademe 2b her karede çalışmıyor; bir izin ifadesi 2 saniyede bir
    güncelleniyor. Durum tutulmasaydı, sinyal karelerin %95'inde 0.0,
    %5'inde tam değer olurdu — füzyonun EMA'sı bunu zaten söndürürdü
    ama "iki sinyal aynı anda" kuralı neredeyse hiç sağlanmazdı, çünkü
    ifade yalnızca o tek karede varlık gösterirdi.

    Son değer, yeni bir sınıflandırma gelene ya da iz kaybolana kadar
    geçerli sayılıyor. Duygu 100 ms'de değişmez — bu bir
    varsayım değil, modülün tasarım gerekçesinin ta kendisi.
    """

    def __init__(self, pencere: int = PENCERE) -> None:
        self._pencere = pencere
        self._gecmis: dict[tuple[str, int], deque[float]] = defaultdict(
            lambda: deque(maxlen=self._pencere)
        )
        self._son_gorulme: dict[tuple[str, int], float] = {}

    def guncelle(
        self, camera: str, tespitler: list[dict[str, Any]], simdi: float
    ) -> dict[int, float]:
        """Kareyi işler, iz kimliği → ifade risk skoru döndürür.

        Yalnızca yeni sınıflandırma gelince geçmişe ekleniyor.
        Her karede 0.0 eklemek, iki gerçek örneğin arasını sıfırlarla
        doldurup ortalamayı yapay olarak düşürürdü — ölçülen şey ifade
        değil, kademe 2b'nin çalışma sıklığı olurdu.
        """
        for d in tespitler:
            track_id = d.get("id")
            if track_id is None:
                continue
            anahtar = (camera, int(track_id))
            self._son_gorulme[anahtar] = simdi
            expr = d.get("expr")
            if expr is None:
                continue
            self._gecmis[anahtar].append(ham_skor(expr))

        cikti: dict[int, float] = {}
        for d in tespitler:
            track_id = d.get("id")
            if track_id is None:
                continue
            gecmis = self._gecmis.get((camera, int(track_id)))
            if gecmis:
                cikti[int(track_id)] = sum(gecmis) / len(gecmis)
        return cikti

    def buda(self, simdi: float, max_yas_s: float = MAX_YAS_S) -> int:
        """Görülmeyen izlerin durumunu atar."""
        eskiler = [
            k for k, t in self._son_gorulme.items() if simdi - t > max_yas_s
        ]
        for k in eskiler:
            self._gecmis.pop(k, None)
            self._son_gorulme.pop(k, None)
        return len(eskiler)

    @property
    def aktif_iz(self) -> int:
        return len(self._son_gorulme)


__all__ = ["ASGARI_KALITE", "IFADE_RISK", "IfadeSinyali", "ham_skor"]
