"""RTSP akışından kare okuma (PyAV).

Neden PyAV, neden `subprocess` ile ffmpeg değil
-----------------------------------------------
PyAV, FFmpeg'in C kütüphanelerine doğrudan bağlanır. Kabuğa (shell)
hiç çıkmadığımız için kamera URL'sinden komut enjeksiyonu riski YOKTUR
(PLAN.md §11.1 / G09). Ayrıca kareyi bellekten alırız — boru üzerinden
ham bayt kopyalamaya gerek kalmaz.

Kare örnekleme hakkında dürüst bir not
--------------------------------------
H.264 kareler arası kodlamalıdır: 4. kareyi çözmek için önceki kareleri
de çözmek gerekir. Yani "25 FPS'ten 4 FPS'e düşürmek" decode maliyetini
düşürmez — sadece pahalı YZ modellerine giden kare sayısını düşürür.
Decode yükünü azaltmanın yolu donanımsal çözücüdür (NVDEC).
Ölçümler Gün 3'te yapılacak; şimdilik CPU decode ile başlıyoruz.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from types import TracebackType

import av
import av.error
import numpy as np

from sentinel import metrics
from sentinel.logging import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class DecodedFrame:
    """Çözülmüş ve örneklenmiş bir kare."""

    camera_id: str
    sequence: int
    # ⚠ DUVAR SAATİ (time.time), monotonik DEĞİL — bilinçli.
    # Bu damga Valkey üzerinden BAŞKA BİR SÜRECE (çıkarım worker'ı)
    # geçiyor ve orada `now - captured_at` diye kullanılıyor. Python
    # dokümanı `time.monotonic()` için açıkça şunu diyor: "The reference
    # point of the returned value is undefined, so that only the
    # difference between the results of two calls is valid." Yani iki
    # AYRI SÜREÇTEN alınmış monotonik değerleri çıkarmak tanımsızdır.
    # Pratikte Windows/Linux'ta ikisi de açılıştan itibaren saydığı için
    # çalışıyordu, ama garanti yok.
    #
    # İkinci sebep çözünürlük: Windows'ta time.monotonic() =
    # GetTickCount64(), adımı ~15.6 ms. 181 ms'lik bir gecikmeyi 15.6 ms
    # adımlı saatle ölçmek p50/p95 rakamlarını gereksiz kabalaştırıyordu.
    # time.time() aynı platformda mikrosaniye çözünürlüklü.
    #
    # Bu damgaya dayanan üç şey var, üçü de kritik:
    #   · _drop_stale()            → gecikmeyi bağlayan tek mekanizma
    #   · end_to_end_latency        → K3 kriterinin ta kendisi
    #   · tarayıcıdaki captureTime  → kutu hizalamasının tamamı
    timestamp: float  # duvar saati (epoch saniye)
    pts_seconds: float  # akış içindeki sunum zamanı
    image: np.ndarray  # BGR, (H, W, 3) uint8


class StreamClosedError(RuntimeError):
    """Akış beklenmedik şekilde kapandı."""


class RtspDecoder:
    """Tek bir RTSP akışını okur ve hedef FPS'e örnekler.

    Kullanım:
        with RtspDecoder("rtsp://…/cam-01", camera_id="cam-01") as dec:
            for frame in dec.frames():
                ...
    """

    def __init__(
        self,
        url: str,
        *,
        camera_id: str,
        target_fps: float = 4.0,
        timeout_s: float = 10.0,
        transport: str = "tcp",
    ) -> None:
        """
        Args:
            url: RTSP adresi.
            camera_id: Metriklerde ve mesajlarda kullanılacak kimlik.
            target_fps: Saniyede kaç kare *örnekleneceği* (decode değil).
            timeout_s: Soket zaman aşımı.
            transport: "tcp" önerilir — UDP'de kare kaybı sessizce olur.
        """
        self._url = url
        self._camera_id = camera_id
        self._interval = 1.0 / target_fps if target_fps > 0 else 0.0
        self._timeout_us = str(int(timeout_s * 1_000_000))
        self._transport = transport
        self._container: av.container.InputContainer | None = None
        self._sequence = 0
        self._decoded = 0

    # ─── Bağlam yöneticisi ───────────────────────────────────

    def __enter__(self) -> RtspDecoder:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def open(self) -> None:
        # ⚠ CANLI AKIŞ SEÇENEKLERİ YALNIZCA AĞ KAYNAKLARINA UYGULANIR
        #
        # `fflags=nobuffer` ve `flags=low_delay` gecikmeyi kırpmak için
        # var: demuxer'a "tampon biriktirme, hemen ver" diyor. Canlı
        # RTSP'de doğru; **dosyada yıkıcı** — ölçüldü: aynı mp4 bu
        # seçeneklerle **0 kare** çözüyor, seçeneksiz 45 kare. Suçlu tek
        # başına `nobuffer` (diğer dördü çıkarılınca dosya yine boş
        # kalıyor, yalnızca `nobuffer` çıkarılınca düzeliyor).
        #
        # `rtsp_transport` ve `timeout` zaten RTSP demuxer'ının
        # seçenekleri; mp4 demuxer'ına verilmeleri en iyi ihtimalle
        # anlamsız.
        #
        # ⚠ Üretimde yalnızca `rtsp://` kullanılıyor, yani bu üretim
        # davranışını DEĞİŞTİRMİYOR. Dosya yolunu açılabilir kılmak,
        # dekoderin gerçek bir videoyla test edilebilmesi için gerekti —
        # ve test edilemeyen bir ölçüm aracı bu projede tam olarak
        # sorunun kaynağı.
        canli = "://" in self._url and not self._url.startswith("file://")
        options = (
            {
                "rtsp_transport": self._transport,
                "timeout": self._timeout_us,  # soket zaman aşımı (mikrosaniye)
                "max_delay": "500000",
                "fflags": "nobuffer",
                "flags": "low_delay",
            }
            if canli
            else {}
        )
        self._container = av.open(self._url, options=options, timeout=None)
        stream = self._container.streams.video[0]
        # Kare atlamak yerine ÇÖZÜP atıyoruz; thread'li çözme CPU'yu daha iyi kullanır.
        stream.thread_type = "AUTO"
        log.info(
            "akis_acildi",
            camera=self._camera_id,
            codec=stream.codec_context.name,
            width=stream.codec_context.width,
            height=stream.codec_context.height,
            avg_fps=float(stream.average_rate or 0),
        )

    def close(self) -> None:
        if self._container is not None:
            self._container.close()
            self._container = None
            log.info("akis_kapandi", camera=self._camera_id, decoded=self._decoded)

    # ─── Kare üretimi ────────────────────────────────────────

    def frames(self, *, max_frames: int | None = None) -> Iterator[DecodedFrame]:
        """Hedef FPS'e örneklenmiş kareleri üretir.

        Args:
            max_frames: Bu kadar kare ürettikten sonra durur (test için).
        """
        if self._container is None:
            raise StreamClosedError("open() çağrılmadı")

        stream = self._container.streams.video[0]
        time_base = float(stream.time_base or 0) or 1 / 25
        next_emit = 0.0
        emitted = 0

        # ⭐⭐ ÇÖZME MALİYETİ CPU ZAMANIYLA ÖLÇÜLÜYOR (P-60)
        #
        # Eski `decode_duration` metriği çözmeyi değil kareler arası
        # BEKLEMEYİ ölçüyordu. Doğrusunu duvar saatiyle yapmak da mümkün
        # değil: `container.decode()` ağdan veri beklerken bloke oluyor,
        # yani `perf_counter` farkı yine beklemeyi içerirdi — hata bir
        # kat aşağıda tekrarlanmış olurdu.
        #
        # `time.thread_time()` yalnızca BU iş parçacığının CPU'sunu
        # sayar; bloke geçen süre girmez. Kamera başına bir iş parçacığı
        # olduğu için ölçtüğümüz şey tam olarak "bu kameranın çözme işi".
        #
        # ⚠ Sayaç Prometheus'ta Counter: Windows'ta iş parçacığı CPU
        # çözünürlüğü ~15.6 ms olduğu için kare başına fark çoğu zaman 0
        # çıkar, ama farklar teleskoplanıp TOPLAMI doğru verir.
        cozme_cpu = metrics.decode_cpu_seconds.labels(cam=self._camera_id)
        bgr_cpu = metrics.bgr_cpu_seconds.labels(cam=self._camera_id)
        cpu_isareti = time.thread_time()

        try:
            for frame in self._container.decode(stream):
                # Bir önceki `yield`den bu yana geçen CPU = bu karenin
                # çözme işi. Örnekleme yüzünden atılacak kareler de
                # buraya giriyor — ve girmeli: decode bedeli ödendi.
                simdi_cpu = time.thread_time()
                cozme_cpu.inc(max(simdi_cpu - cpu_isareti, 0.0))
                cpu_isareti = simdi_cpu

                self._decoded += 1
                pts_s = float(frame.pts * time_base) if frame.pts is not None else 0.0

                # Örnekleme: hedef aralık dolmadıysa kareyi at.
                # (Decode maliyeti yine ödendi — yukarıdaki nota bakınız.)
                if self._interval > 0 and pts_s < next_emit:
                    continue

                # ⚠ SABİT TAKVİM — kayma birikmesin
                # İlk sürüm `next_emit = pts_s + interval` yazıyordu, yani
                # takvimi her seferinde GERÇEKLEŞEN kareye sıfırlıyordu.
                # Gerçekleşen kare hedeften hep biraz sonradır (kaynak
                # ayrık: 25 FPS'te kareler 0.04 sn aralıklı), bu aşma her
                # turda birikiyordu:
                #   hedef 4 FPS (0.25 sn) → 0.24 < 0.25 olduğu için ancak
                #   her 7. kare alınabiliyor → 25/7 = 3.57 FPS
                # Takvimi sabit tutunca aralıklar 0.28/0.24/0.24/0.24 diye
                # değişiyor ama ORTALAMASI tam 0.25 sn = 4.0 FPS oluyor.
                next_emit += self._interval
                if next_emit <= pts_s:
                    # Çok geri kaldık (kare atlandı, yeniden bağlanıldı) —
                    # takvimi tazele, yoksa yetişmek için ardı ardına kare
                    # yayınlamaya çalışır.
                    next_emit = pts_s + self._interval

                self._sequence += 1
                emitted += 1

                # ⭐ BGR dönüşümü ayrı ölçülüyor: çözmeden bağımsız bir
                # maliyet ve yalnızca ÖRNEKLENEN karelerde ödeniyor.
                # Ayrı tutmak, örnekleme hızını düşürmenin neyi
                # kazandırdığını (ve neyi kazandırmadığını) gösteriyor:
                # decode bedeli düşmez, BGR bedeli düşer.
                bgr_basi = time.thread_time()
                goruntu = frame.to_ndarray(format="bgr24")
                bgr_cpu.inc(max(time.thread_time() - bgr_basi, 0.0))

                yield DecodedFrame(
                    camera_id=self._camera_id,
                    sequence=self._sequence,
                    # Duvar saati — süreçler arası karşılaştırılabilir
                    # olmak zorunda (gerekçe: DecodedFrame.timestamp)
                    timestamp=time.time(),
                    pts_seconds=pts_s,
                    image=goruntu,
                )

                # ⚠ `yield` tüketici işini bitirene kadar bloke eder;
                # o süre BU iş parçacığının CPU'suna yazılır ve çözmenin
                # hanesine geçmemeli. İşareti dönüşten SONRA tazeliyoruz.
                #
                # ⭐ Bu satır kaldırılınca `test_yield_ICINDE_yakilan_cpu...`
                # düşüyor: çözme CPU'su 328 ms okunuyor, tüketicinin
                # yaktığı 300 ms'in tamamı çözmeye atfediliyor. Testin
                # gerçekten bir şey doğruladığı böyle sınandı.
                cpu_isareti = time.thread_time()

                if max_frames is not None and emitted >= max_frames:
                    return
        except av.error.EOFError:
            log.info("akis_bitti", camera=self._camera_id)
        except av.error.FFmpegError as exc:
            raise StreamClosedError(f"{self._camera_id}: {exc}") from exc

    def set_target_fps(self, fps: float) -> None:
        """Örnekleme hızını çalışma anında değiştirir (uyarlanabilir FPS).

        PLAN.md §5.2: sistem her kameraya eşit davranmaz. Hareketsiz bir
        kamerayı 4 FPS örneklemek boşa iş — kareler zaten Kademe 0'da
        eleniyor, ama YUV→BGR dönüşümü (sürenin %77'si) çoktan ödenmiş
        oluyor. Onu 1 FPS'e düşürmek o CPU'yu kalabalık kameralara
        bırakır.

        Not: decode maliyeti düşmez, H.264 kareler arası kodlamalıdır
        (bkz. modül başlığı). Kazanç renk dönüşümü ve hareket
        filtresindedir.
        """
        self._interval = 1.0 / fps if fps > 0 else 0.0

    @property
    def target_fps(self) -> float:
        return 1.0 / self._interval if self._interval > 0 else 0.0

    # ─── İstatistik ──────────────────────────────────────────

    @property
    def decoded_count(self) -> int:
        """Çözülen toplam kare (örneklenen değil) — decode yükünün ölçüsü."""
        return self._decoded

    @property
    def emitted_count(self) -> int:
        return self._sequence


def rtsp_url(host: str, port: int, path: str) -> str:
    """RTSP adresi kurar."""
    return f"rtsp://{host}:{port}/{path}"


__all__ = ["DecodedFrame", "RtspDecoder", "StreamClosedError", "rtsp_url"]
