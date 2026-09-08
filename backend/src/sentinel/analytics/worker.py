"""Analitik worker'ı — iskeletten ANLAMA giden katman.

Mimarideki yeri
---------------
    çıkarım worker'ı  →  inference.results  (kutular + iskelet + kimlik)
                              ↓
                      ANALİTİK WORKER  (bu dosya)
                        · pencereleri besle
                        · özellik çıkar      (analytics/features/)
                        · kuralları uygula   (analytics/anomaly/rules.py)
                              ↓
                        analytics.events  →  API  →  panel

Neden AYRI bir süreç
--------------------
Çıkarım worker'ının tek işi GPU'yu doyurmak. Oraya analitik eklemek iki
şeyi birden bozardı: GPU boşta beklerken CPU analitik yapar (kare
gecikir) ve analitikte bir hata GPU boru hattını düşürür.

Ayrıca bu worker **GPU'ya hiç dokunmuyor** — tamamen CPU ve hafif.
Gerekirse ayrı bir makineye taşınabilir; çıkarım worker'ı taşınamaz.

⚠ NEDEN KADEME 0 BURAYA DA UYGULANMIYOR
---------------------------------------
Hareket filtresi alım tarafında. Buraya gelen her sonuç zaten filtreyi
geçmiş bir kareye ait, yani "bir şey oluyor" demek. Burada ikinci bir
eleme yapmak gerçek olayları kaçırma riski taşır ve kazanç getirmez:
bu katmanın maliyeti aritmetik, model çağrısı yok.

Kullanım
--------
    uv run python -m sentinel.analytics.worker
    uv run python -m sentinel.analytics.worker --duration 60
"""

from __future__ import annotations

import argparse
import json
import math
import signal
import sys
import time
from collections import Counter
from pathlib import Path
from types import FrameType
from typing import Any

import numpy as np

from sentinel import metrics
from sentinel.analytics import fusion
from sentinel.analytics.aggression import TirmanmaSkorlayici, TirmanmaSkoru
from sentinel.analytics.anomaly.normalcy import NormalProfilDeposu
from sentinel.analytics.anomaly.rules import Anomali, AnomaliTuru, KuralMotoru
from sentinel.analytics.features import pair
from sentinel.analytics.features import skeleton as sk
from sentinel.analytics.features.person import KisiOzellikleri, cikar
from sentinel.analytics.features.window import Ornek, PencereDeposu
from sentinel.analytics.fusion import RiskFuzyonu, RiskSonucu
from sentinel.analytics.ifade import IfadeSinyali
from sentinel.analytics.model import (
    ASGARI_PAY,
    SaldirganlikModeli,
    iz_paylari,
)
from sentinel.bus.streams import connect
from sentinel.config import PROJECT_ROOT, settings
from sentinel.logging import configure_logging, get_logger

log = get_logger(__name__)

GROUP = "analytics"
EVENT_STREAM = "analytics.events"
_stop = False


def _handle_signal(_sig: int, _frame: FrameType | None) -> None:
    global _stop
    _stop = True
    log.info("kapatma_sinyali_alindi")


def _model_sutun_yolu() -> Path | None:
    """Model sütun sırasını taşıyan en yeni ölçüm JSON'u.

    ⚠ Sütun SIRASI model dosyasıyla birlikte sabitlendi ve ayrı bir
    dosyada duruyor. Alfabetik yeniden üretmek yetmez: eğitim
    `sorted()` kullanıyor ama o varsayıma dayanmak sessiz bir hata
    kaynağı olurdu. `SaldirganlikModeli` sütun sayısını model
    dosyasıyla karşılaştırıp uyuşmazlıkta devre dışı kalıyor.
    """
    kayitlar = sorted(
        (PROJECT_ROOT / "benchmarks").glob("saldirganlik_model_*.json")
    )
    return kayitlar[-1] if kayitlar else None


class AnalyticsWorker:
    """`inference.results` akışını tüketip anomali üretir."""

    def __init__(self, *, worker_id: str = "analytics-0", block_ms: int = 500) -> None:
        self._worker_id = worker_id
        self._block_ms = block_ms
        self._client = connect()
        self._pencereler = PencereDeposu()
        self._kurallar = KuralMotoru()
        # KATMAN A — kamera başına öğrenilen normal profil.
        # Diskten yükleniyor: profil kaybı sistem körlüğü demek
        # (bkz. anomaly/normalcy.py · NormalProfilDeposu).
        self._normal = NormalProfilDeposu(PROJECT_ROOT / "data" / "profiles")
        # SALDIRGANLIK — kişi + çift özelliklerinden tırmanma skoru
        self._tirmanma = TirmanmaSkorlayici()
        # ⭐⭐ ÖĞRENİLMİŞ MODEL — P-56, hakem denetiminin en ağır bulgusu
        #
        # 08.09.2026'ya kadar canlı boru hattında HİÇBİR öğrenilmiş
        # model yoktu: K5 F1 = 0.889 yalnızca çevrim dışı betiklerde
        # ölçülüyordu. Ve bu, füzyonun EN AĞIR sinyalini (0.40)
        # P-52'de ayırt etmediği ölçülen kural kümesine bırakıyordu.
        # K7 koşusunda üretilen 39 alarmın SIFIRI saldırganlıktandı.
        #
        # Model kamera seviyesinde karar veriyor, kural iz seviyesinde
        # atıf yapıyor (bkz. analytics/model.py modül başlığı).
        self._model: SaldirganlikModeli | None = None
        if settings.aggression_model_enabled:
            self._model = SaldirganlikModeli(
                settings.aggression_model_weights,
                _model_sutun_yolu(),
            )
            if not self._model.etkin:
                log.warning("saldirganlik_modeli_devre_disi_kurala_donuluyor")
                self._model = None
        # FÜZYON — beş sinyali tek risk skorunda birleştirir (PLAN §6.6)
        self._fuzyon = RiskFuzyonu()
        # İFADE — KADEME 2b çıktısını füzyona taşıyan katman.
        # ⚠ 03.09.2026'ya kadar YOKTU: füzyon sinyali `ifade=0.0` diye
        # sabit yazılıydı ve mesajdaki `expr` alanı hiç okunmuyordu.
        # "Duygu analizi" şartnamedeki üç yetenekten biri ve sistemin
        # kararına hiç katılmıyordu (bkz. analytics/ifade.py).
        self._ifade = IfadeSinyali()
        # Kamera başına son değerlendirme anı — oyalanma birikimi için
        # gereken `dt`. Kameralar farklı hızlarda analiz edildiği için
        # (uyarlanabilir FPS) sabit adım kullanmak yanlış olurdu.
        self._son_degerlendirme: dict[str, float] = {}

        self.islenen = 0
        self.anomaliler = 0
        self.saldirganlik = 0
        self.fuzyon_alarm = 0
        # ⚠ Bastırılan füzyon alarmı sayısı AYRI tutuluyor: "füzyon
        # çalışıyor ama tek sinyalli olduğu için susuyor" ile "füzyon
        # hiç skor üretmiyor" arasındaki farkı ancak bu sayaç gösterir.
        self.fuzyon_bastirilan = 0
        self.by_camera: Counter[str] = Counter()
        self._ensure_group()

    def _ensure_group(self) -> None:
        """Tüketici grubunu kurar (varsa sessizce geçer).

        ⚠ `id="$"` bilinçli — çıkarım worker'ının aksine.
        Orada `"0"` gerekiyordu çünkü akıştaki her mesaj işlenmemiş bir
        SLOT taşıyor ve okunmazsa havuz kilitleniyor (P-10). Burada öyle
        bir kaynak yok: analitik geç açıldıysa geçmişteki sonuçları
        işlemenin değeri de yok — gerçek zamanlı bir sistemde 10 dakika
        önceki anomaliyi şimdi bildirmek yanlış olur.
        """
        from redis.exceptions import ResponseError

        try:
            self._client.xgroup_create(
                settings.stream_results, GROUP, id="$", mkstream=True
            )
            log.info("tuketici_grubu_olusturuldu", stream=settings.stream_results)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    # ─── Ana döngü ───────────────────────────────────────────

    def run(self, *, duration: float | None = None, stats_interval: float = 10.0) -> None:
        log.info("analitik_worker_basliyor", worker=self._worker_id)
        metrics.worker_up.labels(component="analytics", worker_id=self._worker_id).set(1)

        started = time.monotonic()
        last_report = started
        last_prune = started
        deadline = started + duration if duration else None

        while not _stop:
            try:
                yanit = self._client.xreadgroup(
                    GROUP,
                    self._worker_id,
                    {settings.stream_results: ">"},
                    count=64,
                    block=self._block_ms,
                )
            except Exception as exc:
                if "NOGROUP" in str(exc):
                    # Çıkarım worker'ı akışı sıfırladı — grubu yeniden kur
                    # ve devam et. Bir bileşenin yeniden başlaması bunu
                    # düşürmemeli (P-20 ile aynı ders).
                    log.warning("grup_kayboldu_yeniden_kuruluyor")
                    self._ensure_group()
                    continue
                log.error("okuma_hatasi", error=f"{type(exc).__name__}: {exc}")
                time.sleep(1.0)
                continue

            if yanit:
                self._isle(yanit)

            now = time.monotonic()
            if now - last_prune >= 30.0:
                self._pencereler.buda(time.time())
                self._kurallar.buda(time.time())
                self._tirmanma.buda(time.time())
                # ⚠ 03.09.2026 — FÜZYON BUDANMIYORDU: SESSİZ BELLEK SIZINTISI
                #
                # `RiskFuzyonu.buda()` 01.09'da füzyon katmanıyla birlikte
                # YAZILDI ama hiçbir yerden ÇAĞRILMADI. Diğer üç bileşen
                # buradan budanıyordu; füzyon listeye eklenmemişti.
                #
                # Etkisi: `_izler` sözlüğü her yeni (kamera, iz) çifti için
                # kalıcı bir kayıt tutuyordu. İz kimlikleri sürekli
                # yenilendiği için bu sözlük SINIRSIZ büyüyor — mimari
                # kural 5'in ("her kuyruk sınırlı, sınırsız kuyruk = RAM
                # patlaması") doğrudan ihlali.
                #
                # ⚠ Neden 2 gün fark edilmedi: sızıntı yavaş ve BELİRTİSİZ.
                # Sistem çalışmaya devam ediyor, alarm üretmeye devam
                # ediyor, yalnızca bellek büyüyor. Kısa koşularda
                # görünmez — ve bugüne kadar hiç uzun koşu yapılmamıştı.
                # K4 kriterinin varlık sebebi tam olarak bu sınıf arıza.
                self._fuzyon.buda(time.time())
                self._ifade.buda(time.time())
                self._normal.kaydet()
                last_prune = now
            if now - last_report >= stats_interval:
                self._rapor(now - started)
                last_report = now
            if deadline and now >= deadline:
                break

        self._bitir(time.monotonic() - started)

    def _isle(self, yanit: Any) -> None:
        """⚠ `Any` bilinçli: `redis-py`'nin `xreadgroup` dönüş tipi,
        `decode_responses` ayarına göre değişen çok kollu bir birleşim
        (union) ve statik olarak daraltılamıyor. Tipi burada zorlamak
        okunmayan bir `cast` yığını üretirdi; yapı zaten aşağıda
        açılırken doğrulanıyor ve bozuk mesaj yakalanıyor."""
        ids: list[str] = []
        for _akis, girdiler in yanit:
            for message_id, alanlar in girdiler:
                ids.append(message_id)
                try:
                    self._kare_isle(alanlar)
                except Exception as exc:
                    # Tek bir bozuk mesaj worker'ı düşürmemeli.
                    log.warning("kare_islenemedi", error=f"{type(exc).__name__}: {exc}")
        if ids:
            self._client.xack(settings.stream_results, GROUP, *ids)

    def _kare_isle(self, alanlar: dict[str, str]) -> None:
        camera = alanlar.get("cam", "")
        if not camera:
            return
        veri = json.loads(alanlar.get("data", "{}"))
        tespitler = veri.get("detections", [])
        ts = float(alanlar.get("ts", 0.0)) or time.time()

        self.islenen += 1

        # ─── Pencereleri besle ───
        ozellikler = []
        for d in tespitler:
            track_id = d.get("id")
            if track_id is None:
                continue  # kimliksiz izde zamansal analiz yapılamaz (P-13)

            bbox = tuple(float(v) for v in d["bbox"])
            kp = d.get("kp")
            kp_dizi = np.asarray(kp, dtype=np.float64) if kp else None

            pencere = self._pencereler.ekle(
                camera,
                int(track_id),
                Ornek(
                    ts=ts,
                    bbox=bbox,  # type: ignore[arg-type]
                    kp=kp_dizi,
                    olcek=sk.govde_boyu(kp_dizi, bbox) if kp_dizi is not None else None,  # type: ignore[arg-type]
                    ayak=sk.ayak_noktasi(bbox),  # type: ignore[arg-type]
                ),
            )
            ozellikler.append(cikar(pencere))

        # ─── Kuralları uygula ───
        onceki = self._son_degerlendirme.get(camera, ts)
        dt = max(0.0, min(5.0, ts - onceki))  # sıçramalara karşı sınırlı
        self._son_degerlendirme[camera] = ts

        # ─── SALDIRGANLIK: çift özellikleri + tırmanma skoru ───
        # ⚠ Kişi özellikleri "ne yapıyor" der, çift özellikleri "kiminle"
        # der. Saldırganlık tanımı gereği etkileşimli olduğu için ikisi
        # birlikte gerekiyor (analytics/features/pair.py).
        kamera_pencereleri = self._pencereler.kamera_pencereleri(camera)
        ciftler = pair.kamera_ciftleri(kamera_pencereleri)
        skorlar = self._tirmanma.degerlendir(camera, ozellikler, ciftler, ts)
        # ⭐ Öğrenilmiş modeli besle — kayan 5 sn penceresi (P-56).
        # ⚠ Kural skorlarından SONRA çağrılıyor çünkü modelin girdisinin
        # bir kısmı kural bileşenleri (eğitimde de öyleydi).
        if self._model is not None:
            self._model.besle(camera, ozellikler, skorlar, ts)
        for skor in skorlar:
            if skor.seviye in ("uyari", "alarm"):
                self._tirmanma_yayinla(camera, skor, ts)

        # ⚠ KATMAN A → KATMAN B'ye TEK YÖNLÜ BİLGİ AKIŞI
        # Oyalanma kuralı "burada durulur mu" sorusunun cevabını
        # öğrenilmiş profilden alıyor (rules.py · _oyalanma). Bağlantı
        # burada kuruluyor, kural motorunun içinde değil: iki katman
        # birbirini import etmemeli, füzyon noktası worker.
        bulgular = self._kurallar.degerlendir(
            camera,
            ozellikler,
            ts,
            dt,
            self._oyalanma_normali(camera, tespitler, ozellikler, veri),
        )

        # ─── KATMAN A: kamera normaline göre skorla ───
        # ⚠ ARTIK ALARM ÜRETMİYOR, SKOR ÜRETİYOR (30.08.2026)
        # Katman A istatistiksel bir sapma sinyali. Tek başına alarm
        # vermesi kontrol kamerasında saatte 90 alarma yol açıyordu ve
        # kod bunu "geçici bir kısıtlama, kalıcı çözüm füzyon" diye
        # yazıyordu. Kalıcı çözüm geldi: skor füzyona giriyor.
        anomali_skorlari = self._katman_a(camera, ozellikler, tespitler, veri, ts)

        # ─── KADEME 2b: yüz ifadesi → füzyon sinyali ───
        # ⚠ Mesajdaki `expr` alanı burada İLK KEZ okunuyor (03.09.2026).
        # KADEME 2b Gün 14'ten beri çalışıyor ve çıktısı panele gidiyordu;
        # analitik zincire hiç girmiyordu (analytics/ifade.py).
        ifade_skorlari = self._ifade.guncelle(camera, tespitler, ts)

        for bulgu in bulgular:
            self._yayinla(bulgu, ts)

        # ─── FÜZYON: beş sinyal, tek risk skoru (PLAN §6.6) ───
        self._fuzyon_degerlendir(
            camera, ozellikler, skorlar, bulgular, anomali_skorlari,
            ifade_skorlari, ts,
        )

    def _oyalanma_normali(
        self,
        camera: str,
        tespitler: list[dict[str, Any]],
        ozellikler: list[KisiOzellikleri],
        veri: dict[str, Any],
    ) -> dict[int, float | None]:
        """İz kimliği → bulunduğu hücrede durağan gözlemlerin oranı.

        Yalnızca hâlihazırda oyalanıyor görünen kişiler için hesaplanıyor:
        kare başına 20 kişi varken hepsi için profil sorgulamak boşuna iş,
        oyalanma kuralı zaten yalnızca duranlarla ilgileniyor.
        """
        kare_w = float(veri.get("w", 0) or 0)
        kare_h = float(veri.get("h", 0) or 0)
        if kare_w <= 0 or kare_h <= 0:
            return {}
        profil = self._normal.al(camera)
        cikti: dict[int, float | None] = {}
        for d, ozellik in zip(tespitler, ozellikler, strict=False):
            if ozellik.oyalanma_s <= 0.0 or ozellik.track_id < 0:
                continue
            bbox = [float(v) for v in d["bbox"]]
            cikti[ozellik.track_id] = profil.oyalanma_olagan_mi(
                (bbox[0] + bbox[2]) / 2.0, bbox[3], kare_w, kare_h
            )
        return cikti

    def _katman_a(
        self,
        camera: str,
        ozellikler: list[Any],
        tespitler: list[dict[str, Any]],
        veri: dict[str, Any],
        ts: float,
    ) -> dict[int, tuple[float, dict[str, float]]]:
        """Kamera normaline göre olağandışılık (PLAN §6.4 Katman A).

        ⚠ İZ KİMLİĞİ → (skor, kanıt) DÖNDÜRÜYOR, alarm listesi DEĞİL.
        30.08.2026'ya kadar burası doğrudan alarm üretiyordu ve eşiği
        0.85'e çekmek zorunda kalmıştık. Artık skor füzyona giriyor
        (`analytics/fusion.py`), eşik orada ve sinyaller birlikte
        değerlendiriliyor.

        ⚠ ÖNCE ÖĞREN, SONRA SKORLA — ve sıra önemli.
        Profil `hazir` değilken skor üretmiyor; yalnızca öğreniyor.
        Bu koruma olmadan sistem AÇILIŞTA alarm yağdırırdı: hiçbir şey
        öğrenilmemişken her gözlem "hiç görülmemiş" olur.

        ⚠ ÖĞRENME DURDURULMUYOR.
        Profil hazır olduktan sonra da öğrenmeye devam ediyor — sahne
        mevsimle, saatle, mobilya değişimiyle kayar. Donmuş bir profil
        birkaç hafta sonra her şeyi anomali sayardı.
        Bedeli: gerçek bir olay uzun sürerse normal öğrenilir
        (kirlenme). Bu, denetimsiz öğrenmenin bilinen kısıtı ve
        raporda böyle yazılacak.
        """
        profil = self._normal.al(camera)
        kare_w = float(veri.get("w", 0) or 0)
        kare_h = float(veri.get("h", 0) or 0)
        if kare_w <= 0 or kare_h <= 0:
            return {}

        profil.kare_ogren(len(tespitler))
        cikti: dict[int, tuple[float, dict[str, float]]] = {}

        for d, ozellik in zip(tespitler, ozellikler, strict=False):
            bbox = [float(v) for v in d["bbox"]]
            ayak_x = (bbox[0] + bbox[2]) / 2.0
            ayak_y = bbox[3]

            hiz = ozellik.govde_hizi
            # Yön: hız vektöründen. Yoksa (durgun kişi) yön bilgisi de yok.
            hz = d.get("v")
            yon = None
            if hz and (abs(hz[0]) > 1 or abs(hz[1]) > 1):
                yon = math.atan2(float(hz[1]), float(hz[0]))

            # ⚠ SIRA: önce skorla, SONRA öğren.
            # Tersi olsaydı gözlem kendi normalini yükseltip kendini
            # olağan gösterirdi — özellikle nadir hücrelerde.
            skor, kanit = profil.skorla(ayak_x, ayak_y, kare_w, kare_h, hiz, yon)
            # ⚠ `oyalanma_s > 0` = kişi 3 sn'lik pencerede yarım gövde
            # boyundan az yer değiştirdi (person.py). Bu gözlem hücrenin
            # "burada durulur mu" istatistiğini besliyor: oyalanma kuralı
            # tek başına süreye bakmasın, bağlama da baksın.
            profil.ogren(
                ayak_x, ayak_y, kare_w, kare_h, hiz, yon,
                duragan=ozellik.oyalanma_s > 0.0,
            )

            # ⚠ EŞİK YOK — skorun tamamı füzyona gidiyor.
            # Eşik koymak, füzyonun birleştirebileceği zayıf sinyalleri
            # daha kaynağında yok etmek olurdu. Karar füzyonun işi.
            if ozellik.track_id >= 0:
                cikti[ozellik.track_id] = (skor, kanit)

        return cikti

    def _fuzyon_degerlendir(
        self,
        camera: str,
        ozellikler: list[KisiOzellikleri],
        tirmanma: list[TirmanmaSkoru],
        bulgular: list[Anomali],
        anomali_skorlari: dict[int, tuple[float, dict[str, float]]],
        ifade_skorlari: dict[int, float],
        ts: float,
    ) -> None:
        """Beş sinyali iz bazında birleştirir (PLAN §6.6).

        ⚠ NEDEN DOĞRUDAN ALARMLAR DA GİRDİ OLUYOR
        Bir düşme zaten kendi alarmını verdi (yukarıda yayınlandı).
        Yine de füzyona giriyor çünkü füzyonun işi "bu kişi ne kadar
        riskli" sorusuna cevap vermek; düşen bir kişi risklidir ve
        risk skoru bunu yansıtmalı. İki alarm çıkması bir tekrar değil:
        biri "düştü" der, diğeri "bu kişi genel olarak riskli" der ve
        operatör için ikisi farklı bilgidir.

        ⚠ İFADE SİNYALİ ARTIK GERÇEKTEN AKIYOR (03.09.2026)
        Önceki sürüm `ifade=0.0` diye SABİT yazıyordu ve yanına şunu
        not düşmüştü: *"Bağlantı yeri hazır; gerçek bir kurulumda
        beslendiğinde kod değişikliği gerekmeyecek."*

        O iddia yanlıştı ve **ölçülmemişti.** Bağlantı yeri hazır
        değildi: bu worker mesajdaki `expr` alanını hiç okumuyordu.
        Yüzler yeterince büyük olsa bile skor buraya ulaşmazdı.

        ⚠ BU KAMERA ÇİFTLİĞİNDE SİNYAL YİNE DE ÇOĞUNLUKLA 0 OLACAK —
        ama artık sebebi farklı ve bu ayrım raporda önemli:
          · ÖNCE : kod sinyali taşımıyordu     (mühendislik eksiği)
          · ŞİMDİ: yüzler ~15 px, kalite eşiğinin altında (veri sınırı)
        Birincisi bir hata, ikincisi bir bulgu. Bulgu raporlanabilir,
        hata raporlanamaz — düzeltilir.
        """
        # İz kimliği → o izin sinyalleri
        tirmanma_map = {s.track_id: s.skor for s in tirmanma}

        # ⭐⭐ SALDIRGANLIK SİNYALİ: model KARAR, kural ATIF (P-56)
        #
        # 08.09.2026'ya kadar bu sinyal doğrudan kural skoruydu ve
        # P-52 onun gerçek görüntüde ayırt etmediğini ölçmüştü
        # (kavga/normal oranı 1.01). Füzyondaki ağırlığı 0.40 —
        # yani en ağır sinyal bilgisizdi.
        #
        #     saldirganlik(iz) = model_kamera × pay(iz)
        #
        # Model "ne kadar riskli" (ölçülmüş F1 0.889), kural "kim"
        # sorusunu yanıtlıyor. Model yoksa `model_skoru` None kalır
        # ve eski davranışa dönülür — bilerek, sessizce.
        model_skoru = self._model.degerlendir(camera) if self._model else None
        paylar = iz_paylari(tirmanma) if model_skoru is not None else {}
        if model_skoru is not None:
            metrics.aggression_model_score.labels(cam=camera).set(model_skoru)

        # Kural sinyali: bu izde ateşleyen kuralların EN YÜKSEĞİ.
        # ⚠ Toplam değil azami — iki kural birden ateşlemek, birinin
        # iki katı kadar riskli demek değil.
        kural_map: dict[int, float] = {}
        for b in bulgular:
            if b.track_id is not None and b.track_id >= 0:
                kural_map[b.track_id] = max(kural_map.get(b.track_id, 0.0), b.skor)

        # Kalabalık KAMERA seviyesinde bir sinyal, iz seviyesinde değil:
        # aynı kameradaki herkes aynı kalabalığın içinde.
        kalabalik = max(
            (b.skor for b in bulgular if b.tur is AnomaliTuru.KALABALIK), default=0.0
        )

        kamera_azami_risk = 0.0
        for ozellik in ozellikler:
            iz = ozellik.track_id
            if iz < 0:
                continue
            anomali_skor, _kanit = anomali_skorlari.get(iz, (0.0, {}))
            sinyaller = fusion.Sinyaller(
                saldirganlik=(
                    model_skoru * paylar.get(iz, ASGARI_PAY)
                    if model_skoru is not None
                    else tirmanma_map.get(iz, 0.0)
                ),
                anomali=anomali_skor,
                kural=kural_map.get(iz, 0.0),
                ifade=ifade_skorlari.get(iz, 0.0),
                kalabalik=kalabalik,
            )
            sonuc = self._fuzyon.degerlendir(
                camera, iz, sinyaller, ozellik.tamlik, ts
            )
            if sonuc is None:
                continue
            kamera_azami_risk = max(kamera_azami_risk, sonuc.risk)
            if sonuc.seviye in ("uyari", "alarm"):
                self._risk_yayinla(camera, sonuc, ts)

        # ⚠ EŞİĞİN ALTINDAKİ RİSK DE YAYINLANIYOR — ve asıl değeri bu.
        # Alarm sayacı yalnızca eşiği GEÇEN riski gösterir; bu gauge
        # tırmanmayı eşiğe varmadan gösteriyor. "Sistem sessiz" ile
        # "sistem sessiz ama risk yükseliyor" arasındaki fark, K8'in
        # (erken uyarı avansı) tam olarak konusu.
        metrics.risk_score.labels(cam=camera).set(kamera_azami_risk)

    def _risk_yayinla(self, camera: str, sonuc: RiskSonucu, ts: float) -> None:
        """Füzyon riskini alarm akışına yazar.

        ⚠ TEK SİNYALLİ RİSK YAYINLANMIYOR
        Füzyonun varlık sebebi sinyalleri BİRLEŞTİRMEK. Tek bir
        sinyalin yükselttiği bir risk skoru, o sinyalin kendi alarmının
        kopyasından başka bir şey değil — ve operatöre aynı olayı iki
        kez göstermek, K7'nin asıl riskini (operatörün sistemi
        umursamamaya başlaması) doğrudan besler.
        """
        if sonuc.katkida_bulunan < 2:
            self.fuzyon_bastirilan += 1
            # ⚠ 03.09.2026 — BU SAYAÇ DIŞARI ÇIKMIYORDU
            # `fuzyon_bastirilan` yalnızca worker kapanırken loga
            # düşüyordu. Oysa K7 anlatısının en güçlü sayısı bu:
            # "kaç alarm operatöre gitmeden önlendi". Bastırılmayan
            # alarmlar sayılıp bastırılanlar sayılmayınca, sistemin
            # sessizliği bir başarı mı yoksa bir arıza mı ayırt
            # edilemiyordu.
            metrics.false_alarm_suppressed.labels(reason="tek_sinyal").inc()
            return
        if self._kurallar.saldirganlik_sogumada_mi(camera, sonuc.track_id, ts):
            metrics.false_alarm_suppressed.labels(reason="sogumada").inc()
            return

        d = sonuc.to_dict()
        self._client.xadd(
            EVENT_STREAM,
            {
                "cam": camera,
                "type": "risk",
                "ts": f"{ts:.6f}",
                "data": json.dumps(
                    {
                        "cam": camera,
                        "anomaly": "risk",
                        "severity": "alarm" if d["level"] == "alarm" else "warning",
                        "track": d["track"],
                        "score": d["risk"],
                        "evidence": {
                            "risk_skoru": d["risk"],
                            "katkida_bulunan_sinyal": d["katkida_bulunan"],
                            **{k: v for k, v in d.items() if k.startswith("s_")},
                        },
                        "completeness": d["completeness"],
                    },
                    separators=(",", ":"),
                ),
            },
            maxlen=1000,
            approximate=True,
        )
        self.anomaliler += 1
        self.by_camera[camera] += 1
        self.fuzyon_alarm += 1
        metrics.anomalies_total.labels(
            cam=camera, type="risk", severity=sonuc.seviye
        ).inc()
        log.info(
            "risk",
            cam=camera,
            iz=d["track"],
            risk=d["risk"],
            sinyal=d["katkida_bulunan"],
            seviye=d["level"],
        )

    def _tirmanma_yayinla(
        self, camera: str, skor: TirmanmaSkoru, ts: float
    ) -> None:
        """Tırmanma skorunu alarm akışına yazar.

        ⚠ Yalnızca `uyari` ve `alarm` seviyeleri yayınlanıyor.
        `dikkat` seviyesi operatöre gösterilmeye değmez — sistemde her
        an onlarca kişi o seviyededir. Ama skor SÜREKLİ hesaplanıyor;
        seviye eşiği yalnızca BİLDİRİM kapısı, ölçüm kapısı değil.
        Erken uyarı avansı (K8) hesaplanırken tüm skor geçmişi kullanılacak.

        Soğuma kural motorundan geçiyor: aynı kişi için saldırganlık ve
        anomali alarmı ayrı ayrı bildirilmemeli.
        """
        # ⚠ Sözlüğe çevirmeden ÖNCE soğuma kontrolü: bastırılacak bir
        # alarm için serileştirme yapmak boşuna iş.
        if self._kurallar.saldirganlik_sogumada_mi(camera, skor.track_id, ts):
            return
        d = skor.to_dict()
        self._client.xadd(
            EVENT_STREAM,
            {
                "cam": camera,
                "type": "aggression",
                "ts": f"{ts:.6f}",
                "data": json.dumps(
                    {
                        "cam": camera,
                        "anomaly": "aggression",
                        "severity": "alarm" if d["level"] == "alarm" else "warning",
                        "track": d["track"],
                        "score": d["score"],
                        "evidence": {
                            "tirmanma_skoru": d["score"],
                            "tirmanma_egimi": d["slope"],
                            **{f"b_{k}": v for k, v in skor.bilesenler.items()},
                        },
                        "completeness": d["completeness"],
                        "against": d["against"],
                    },
                    separators=(",", ":"),
                ),
            },
            maxlen=1000,
            approximate=True,
        )
        self.anomaliler += 1
        self.by_camera[camera] += 1
        self.saldirganlik += 1
        metrics.anomalies_total.labels(
            cam=camera, type="aggression", severity=skor.seviye
        ).inc()
        log.info(
            "saldirganlik",
            cam=camera,
            iz=d["track"],
            karsi=d["against"],
            skor=d["score"],
            egim=d["slope"],
            seviye=d["level"],
        )

    def _yayinla(self, anomali: Anomali, ts: float) -> None:
        """Anomaliyi akışa yazar — API oradan okuyup panele iletecek."""
        self._client.xadd(
            EVENT_STREAM,
            {
                "cam": anomali.camera,
                "type": anomali.tur.value,
                "ts": f"{ts:.6f}",
                "data": json.dumps(anomali.to_dict(), separators=(",", ":")),
            },
            maxlen=1000,
            approximate=True,
        )
        self.anomaliler += 1
        self.by_camera[anomali.camera] += 1
        metrics.anomalies_total.labels(
            cam=anomali.camera, type=anomali.tur.value, severity=anomali.ciddiyet
        ).inc()
        log.info(
            "anomali",
            cam=anomali.camera,
            tur=anomali.tur.value,
            iz=anomali.track_id,
            skor=round(anomali.skor, 2),
            kanit=anomali.kanit,
        )

    # ─── Raporlama ───────────────────────────────────────────

    def _rapor(self, elapsed: float) -> None:
        hiz = self.islenen / elapsed if elapsed > 0 else 0.0
        print(
            f"  {self.islenen:>6} sonuç · {hiz:5.1f}/sn · "
            f"{self._pencereler.aktif_iz_sayisi:>3} aktif pencere · "
            f"{self.anomaliler:>3} anomali "
            f"(saldırganlık {self.saldirganlik}) · {self._kurallar.stats}",
            flush=True,
        )

    def _bitir(self, elapsed: float) -> None:
        print()
        print(f"  İşlenen sonuç : {self.islenen} ({self.islenen / max(elapsed, 1):.1f}/sn)")
        print(f"  Anomali       : {self.anomaliler}")
        for tur, sayi in self._kurallar.stats.items():
            if sayi:
                print(f"    {tur:<12} {sayi}")
        if self.by_camera:
            print("  Kamera bazında:")
            for cam, n in self.by_camera.most_common(10):
                print(f"    {cam:<14} {n}")
        metrics.worker_up.labels(component="analytics", worker_id=self._worker_id).set(0)
        self._client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="SENTINEL analitik worker'ı")
    parser.add_argument("--worker-id", default="analytics-0")
    parser.add_argument("--metrics-port", type=int, default=9120)
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--stats-interval", type=float, default=10.0)
    args = parser.parse_args()

    configure_logging(settings.log_level)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    metrics.serve_metrics(args.metrics_port)

    worker = AnalyticsWorker(worker_id=args.worker_id)
    worker.run(duration=args.duration, stats_interval=args.stats_interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
