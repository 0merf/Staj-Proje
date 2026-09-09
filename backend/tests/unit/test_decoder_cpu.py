"""Çözme maliyeti metriklerinin ölçtüğünü sandığımız şeyi ölçtüğünü sınar (P-60).

⭐ NEDEN BU TEST VAR
-------------------
Eski `decode_duration` metriği adının söylediği şeyi ölçmüyordu:

    last = time.perf_counter()          # önceki karenin İŞİ BİTTİĞİNDE
    for frame in decoder.frames():
        now = time.perf_counter()       # yeni kare GELDİĞİNDE
        decode_duration.observe(now - last)

Ölçtüğü şey çözme değil, **bir sonraki karenin gelmesini bekleme**
süresiydi. 17 gün panoda durdu ve kimse fark etmedi — çünkü sayı
**makul** görünüyordu.

Yeni metrikler `time.thread_time()` kullanıyor: yalnızca o iş
parçacığının harcadığı CPU. Bloke geçen süre sayılmaz.

⚠⚠ BU TESTİN NEYİ KANITLAMADIĞI — dürüstçe
-------------------------------------------
İlk yazdığım sürüm "eski kodda düşerdi" diye iddia ediyordu. **Yanlıştı
ve ölçülerek yakalandı:**

    duvar saati toplam      :  554.4 ms
    ESKİ metrik toplasaydı  :   46.3 ms   ⬅ küçük!
    YENİ çözme CPU          :   15.6 ms

Sebep: eski metriğin şiştiği yer **canlı akışın tempo sınırıdır**. RTSP
sunucusu kareleri gerçek zamanlı veriyor, yani 2.75 FPS'te bir sonraki
kare ~360 ms sonra geliyor ve eski metrik o beklemeyi yazıyordu. Yerel
bir dosyada ise sonraki kare **anında** hazır — bekleme yok, eski
metrik de küçük çıkıyor.

> ⭐ Yani bu birim testi, üretimdeki hatayı **yeniden üretemez**;
> bunun için gerçek zamanlı bir kaynak gerekir. Test etmediği şeyi
> test ettiğini söylemek, ölçütün tanımını yanlış çizmek olurdu —
> projede altı kez yakalanan hatanın (P-49) ta kendisi.

**Test ettiği şey**, ölçümün *atıf sınırı*: tüketicinin harcadığı CPU
çözmenin hanesine yazılmamalı. Bu, `frames()` içindeki `yield`den
sonra CPU işaretinin tazelenmesine bağlı ve kolayca bozulabilir bir
ayrıntı — gerçek bir gerileme testi.
"""

from __future__ import annotations

import time
from pathlib import Path

import av
import numpy as np
import pytest

from sentinel import metrics
from sentinel.ingest.decoder import RtspDecoder

GENISLIK, YUKSEKLIK, KAYNAK_FPS, KARE_SAYISI = 320, 240, 15, 45


def _sayac(metrik: object, cam: str) -> float:
    """Etiketli bir Prometheus Counter'ının anlık değeri."""
    return float(metrik.labels(cam=cam)._value.get())  # type: ignore[attr-defined]


def _cpu_yak(saniye: float) -> None:
    """Verilen kadar GERÇEK CPU harcar (uyku değil — uyku CPU harcamaz)."""
    hedef = time.thread_time() + saniye
    while time.thread_time() < hedef:
        sum(i * i for i in range(2000))


@pytest.fixture(scope="module")
def video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Küçük, GERÇEK bir H.264 dosyası üretir.

    ⚠ Sahte (mock) bir dekoder işe yaramazdı: ölçtüğümüz şey tam olarak
    gerçek çözme işinin CPU'su. Mock'lasaydık test, kodun kendi
    varsayımını tekrar etmekten ibaret olurdu.
    """
    hedef = tmp_path_factory.mktemp("video") / "test.mp4"
    kap = av.open(str(hedef), mode="w")
    try:
        akis = kap.add_stream("libx264", rate=KAYNAK_FPS)
    except Exception:  # pragma: no cover - libx264 yoksa
        akis = kap.add_stream("mpeg4", rate=KAYNAK_FPS)
    akis.width, akis.height = GENISLIK, YUKSEKLIK
    akis.pix_fmt = "yuv420p"

    for i in range(KARE_SAYISI):
        # Kayan gradyan: her kare farklı, yani çözücü gerçekten iş
        # yapıyor (sabit kare tek bir P-kareye inerdi).
        satir = ((np.arange(GENISLIK) + i * 7) % 256).astype(np.uint8)
        img = np.tile(satir, (YUKSEKLIK, 1))
        rgb = np.stack([img, np.roll(img, 40, axis=1), np.roll(img, 80, axis=1)], axis=2)
        kare = av.VideoFrame.from_ndarray(np.ascontiguousarray(rgb), format="rgb24")
        for paket in akis.encode(kare):
            kap.mux(paket)
    for paket in akis.encode():
        kap.mux(paket)
    kap.close()
    return hedef


class TestCozmeCpuAtfi:
    def test_TUKETICININ_CPUSU_cozmenin_hanesine_yazilmiyor(self, video: Path) -> None:
        """⭐ ASIL TEST — atıf sınırı.

        Tüketici her kare arasında ~50 ms GERÇEK CPU yakıyor (uyku
        değil; uyku `thread_time`'a zaten girmez, dolayısıyla hiçbir
        şey sınamazdı).

        `frames()` üreteci tüketiciyle **aynı iş parçacığında** koşuyor:
        `yield` tüketici dönene kadar bloke ediyor ve o sürede harcanan
        CPU bu iş parçacığının hanesine yazılıyor. Üreteç, dönüşten
        sonra CPU işaretini tazelemezse tüketicinin işi "çözme" diye
        raporlanır. Bu test tam olarak onu yakalar.
        """
        cam = "test-atif"
        onceki = _sayac(metrics.decode_cpu_seconds, cam)
        kare_sayisi, yakim = 6, 0.05

        with RtspDecoder(str(video), camera_id=cam, target_fps=5.0) as d:
            kareler = list(d.frames(max_frames=kare_sayisi))
            for _ in kareler:
                _cpu_yak(yakim)
        cpu = _sayac(metrics.decode_cpu_seconds, cam) - onceki
        yakilan = kare_sayisi * yakim

        assert len(kareler) == kare_sayisi
        # ⚠ `list(...)` üreteci tüketiciden ÖNCE tükettiği için burada
        # yakım zaten ayrı; asıl senaryo aşağıdaki döngüde.
        assert cpu < yakilan, (
            f"çözme CPU'su {cpu * 1000:.0f} ms, yakılan {yakilan * 1000:.0f} ms — "
            "tüketicinin işi çözmeye atfediliyor olabilir"
        )

    def test_yield_ICINDE_yakilan_cpu_cozmeye_atfedilmiyor(self, video: Path) -> None:
        """Aynı sınır, ama tüketici üreteci ADIM ADIM sürerken yakıyor.

        Yukarıdaki test `list()` kullanıyor (üreteç önce tükeniyor).
        Burada tüketici her `yield` arasında CPU yakıyor — üretimdeki
        gerçek desen bu ve atıf hatası ancak burada ortaya çıkar.
        """
        cam = "test-atif-adim"
        onceki = _sayac(metrics.decode_cpu_seconds, cam)
        kare_sayisi, yakim = 6, 0.05

        adet = 0
        with RtspDecoder(str(video), camera_id=cam, target_fps=5.0) as d:
            for _ in d.frames(max_frames=kare_sayisi):
                adet += 1
                _cpu_yak(yakim)
        cpu = _sayac(metrics.decode_cpu_seconds, cam) - onceki
        yakilan = kare_sayisi * yakim

        assert adet == kare_sayisi
        # ⭐ İşaret `yield`den sonra tazelenmezse cpu ≈ yakılan + çözme
        # olurdu. Yarısını eşik almak, Windows'un ~15.6 ms iş parçacığı
        # CPU çözünürlüğüne rağmen güvenli bir ayrım bırakıyor.
        assert cpu < yakilan / 2, (
            f"çözme CPU'su {cpu * 1000:.0f} ms; tüketici {yakilan * 1000:.0f} ms "
            "yaktı. `yield` sonrası CPU işareti tazelenmiyor (P-60 atıf hatası)."
        )

    def test_bgr_yalnizca_orneklenen_karelerde_odeniyor(self, video: Path) -> None:
        """Çözme her karede, BGR yalnızca yayınlananlarda ödeniyor.

        İkisini ayrı tutmak, örnekleme hızını düşürmenin neyi
        kazandırdığını gösteriyor: **decode bedeli DÜŞMEZ, BGR bedeli
        düşer.** `decoder.py` başındaki not tam da bunu söylüyor ve bu
        test o notun doğru olduğunu sınıyor.

        ⚠ SAYININ BÜYÜKLÜĞÜ SINANMIYOR — sınanamaz. Windows'ta iş
        parçacığı CPU çözünürlüğü ~15.6 ms; 320×240 bir karenin BGR
        dönüşümü ~0.1 ms. Tek tek ölçüldüğünde sayaç 0 okuyor. Sayaç
        monoton biriktiği için **üretimdeki binlerce karede toplam
        doğru**, ama bir birim testinde ölçülemez. Burada yalnızca
        muhasebe ilişkisi sınanıyor.
        """
        cam = "test-bgr"
        onceki = _sayac(metrics.bgr_cpu_seconds, cam)

        with RtspDecoder(str(video), camera_id=cam, target_fps=5.0) as d:
            kareler = list(d.frames(max_frames=6))
            cozulen = d.decoded_count

        assert len(kareler) == 6
        assert _sayac(metrics.bgr_cpu_seconds, cam) >= onceki, "sayaç geri gitti"
        # 15 FPS kaynaktan 5 FPS örneklenince yayınlanan kare başına ~3
        # kare çözülüyor. Çözülen ≤ yayınlanan olsaydı ya örnekleme
        # çalışmıyor ya da `_decoded` sayacı kırık demekti.
        assert cozulen > len(kareler), (
            f"çözülen {cozulen}, yayınlanan {len(kareler)} — örnekleme çalışmıyor"
        )


class TestDosyaKaynagi:
    def test_dosya_acilirken_CANLI_AKIS_secenekleri_uygulanmiyor(
        self, video: Path,
    ) -> None:
        """⚠ `fflags=nobuffer` dosya çözmeyi TAMAMEN bozuyor.

        Ölçüldü: aynı mp4, canlı akış seçenekleriyle **0 kare**,
        seçeneksiz 45 kare. Beş seçenek tek tek çıkarıldığında yalnızca
        `nobuffer` çıkarılınca düzeliyor — suçlu o.

        Üretim yalnızca `rtsp://` kullandığı için bu davranış değişikliği
        üretimi etkilemiyor; dekoderin gerçek bir videoyla test
        edilebilmesi için gerekti.
        """
        with RtspDecoder(str(video), camera_id="test-dosya", target_fps=0.0) as d:
            adet = sum(1 for _ in d.frames())
        assert adet == KARE_SAYISI, (
            f"{adet} kare çözüldü, {KARE_SAYISI} bekleniyordu — dosya "
            "kaynağına canlı akış seçenekleri sızmış olabilir"
        )
