"""Olay klibi kesme — segment seçimi ve adlandırma.

⚠ NE TEST EDİLİYOR, NE EDİLMİYOR
--------------------------------
Bu testler **video kesmiyor**: gerçek fMP4 segmenti üretmek FFmpeg
gerektirir ve birim testi entegrasyon testine dönüştürürdü.

Test edilen şey, kesimden ÖNCEKİ karar zinciri:

  · segment adından zaman okunuyor mu (yanlış okunursa klip kayar)
  · doğru segmentler seçiliyor mu (yanlış seçilirse klip boş çıkar)
  · anahtar biçimi doğru mu

Bu üçü yanlışsa remux'un kusursuz çalışması bir işe yaramaz — yanlış
saniyeyi kusursuz keser.

⚠ Remux'un kendisi CANLI sistemde doğrulanacak: kayıt açılıp gerçek bir
alarmda üretilen klip izlenerek. Bir dosyanın "video olduğunu" iddia
eden bir birim testi, dosyanın DOĞRU videoyu içerdiğini söylemez.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sentinel.alerting import klip


def _segment_yaz(dizin: Path, an: datetime) -> Path:
    """Adı MediaMTX biçiminde olan boş bir segment dosyası oluşturur."""
    dizin.mkdir(parents=True, exist_ok=True)
    yol = dizin / f"{an:%Y-%m-%d_%H-%M-%S}-000000.mp4"
    yol.write_bytes(b"")
    return yol


class TestSegmentListeleme:
    def test_dosya_adindan_zaman_okunuyor(self, tmp_path: Path) -> None:
        """⚠ `mtime` DEĞİL, dosya ADI.

        `mtime` dosyanın son yazıldığı andır — yani 60 saniyelik bir
        segmentin BİTİŞİ. Ondan okusaydık her klip bir segment kayardı.
        """
        an = datetime(2026, 8, 30, 11, 57, 42).astimezone()
        _segment_yaz(tmp_path / "cam-16", an)

        s = klip._segmentleri_listele(tmp_path, "cam-16")
        assert len(s) == 1
        assert s[0].baslangic.hour == 11
        assert s[0].baslangic.minute == 57
        assert s[0].baslangic.second == 42

    def test_ILGISIZ_dosyalar_atlaniyor(self, tmp_path: Path) -> None:
        """Kayıt dizininde başka dosyalar olabilir; çökmemeli."""
        dizin = tmp_path / "cam-16"
        dizin.mkdir(parents=True)
        (dizin / "not-a-segment.txt").write_text("x")
        (dizin / "README.md").write_text("x")
        assert klip._segmentleri_listele(tmp_path, "cam-16") == []

    def test_olmayan_kamera_bos_donuyor(self, tmp_path: Path) -> None:
        """Kayıt kapalıyken beklenen durum — istisna DEĞİL boş liste."""
        assert klip._segmentleri_listele(tmp_path, "cam-99") == []

    def test_zamana_gore_siralaniyor(self, tmp_path: Path) -> None:
        taban = datetime(2026, 8, 30, 12, 0, 0).astimezone()
        for dk in (2, 0, 1):
            _segment_yaz(tmp_path / "cam-01", taban + timedelta(minutes=dk))
        s = klip._segmentleri_listele(tmp_path, "cam-01")
        assert [x.baslangic.minute for x in s] == [0, 1, 2]


class TestSegmentSecimi:
    def _segmentler(self) -> list[klip.Segment]:
        taban = datetime(2026, 8, 30, 12, 0, 0).astimezone()
        return [
            klip.Segment(Path(f"s{i}.mp4"), taban + timedelta(minutes=i))
            for i in range(5)
        ]

    def test_olay_tek_segmentin_ortasindaysa_tek_segment_secilir(self) -> None:
        s = self._segmentler()
        bas = s[2].baslangic + timedelta(seconds=20)
        bit = s[2].baslangic + timedelta(seconds=40)
        assert klip._kapsayan_segmentler(s, bas, bit) == [s[2]]

    def test_SEGMENT_SINIRINA_denk_gelen_olay_IKI_segment_aliyor(self) -> None:
        """⚠ Asıl zor durum bu.

        Olay penceresi (±10 sn) bir segment sınırına denk gelirse iki
        dosyadan da paket almak gerekiyor. Tek segment alınsaydı klibin
        yarısı eksik çıkardı ve bu SESSİZ bir kusur olurdu — dosya
        oynatılabilir, sadece olay içinde yok.
        """
        s = self._segmentler()
        bas = s[2].baslangic - timedelta(seconds=5)
        bit = s[2].baslangic + timedelta(seconds=5)
        secilen = klip._kapsayan_segmentler(s, bas, bit)
        assert secilen == [s[1], s[2]]

    def test_kayittan_ONCEKI_olay_hicbir_segment_secmiyor(self) -> None:
        """`recordDeleteAfter: 1h` ile eski segmentler siliniyor.

        Alarm geçmişi 30 gün, kayıt 1 saat. Yani eski bir alarmın klibi
        YOKTUR ve bu beklenen durum — boş liste dönmeli, uydurma bir
        segment değil.
        """
        s = self._segmentler()
        cok_eski = s[0].baslangic - timedelta(hours=3)
        assert klip._kapsayan_segmentler(
            s, cok_eski, cok_eski + timedelta(seconds=15)
        ) == []

    def test_son_segmentten_SONRAKI_olay_son_segmenti_aliyor(self) -> None:
        """Süresi bilinmeyen son segment için üst sınır payı kullanılıyor.

        Segment henüz yazılmakta olabilir; "bitmiş" varsayıp atlamak,
        tam da en taze olayın klibini kaçırmak demekti.
        """
        s = self._segmentler()
        an = s[-1].baslangic + timedelta(seconds=30)
        assert s[-1] in klip._kapsayan_segmentler(
            s, an, an + timedelta(seconds=5)
        )


class TestAnahtar:
    def test_tarihe_gore_bolumleniyor(self) -> None:
        """⚠ Düz dizin DEĞİL.

        On binlerce dosyayı tek dizine koymak listelemeyi ve "şu günün
        kliplerini sil" işlemini pahalı hâle getirir. Tarih öneki bunu
        tek önek taramasına indiriyor.
        """
        ts = datetime(2026, 8, 30, 9, 4, 37, tzinfo=UTC).timestamp()
        a = klip.klip_anahtari("cam-16", ts, "fall")
        assert a == "2026/08/30/cam-16/090437_fall.mp4"

    def test_ayni_saniyede_FARKLI_TUR_farkli_anahtar(self) -> None:
        """Aynı anda iki tür alarm çıkabilir; biri diğerini ezmemeli."""
        ts = datetime(2026, 8, 30, 9, 4, 37, tzinfo=UTC).timestamp()
        assert klip.klip_anahtari("cam-16", ts, "fall") != klip.klip_anahtari(
            "cam-16", ts, "aggression"
        )


class TestKlipCikar:
    def test_KAYIT_YOKSA_None_donuyor_ISTISNA_FIRLATMIYOR(
        self, tmp_path: Path
    ) -> None:
        """⚠ Varsayılan yapılandırmada BEKLENEN durum.

        Kayıt varsayılan olarak kapalı (~14 GB/saat). Klip
        üretilemediği için alarm yazımının durması, çözdüğü sorundan
        büyük bir sorun olurdu: kanıtı olmayan bir alarm hâlâ bir
        alarmdır.
        """
        sonuc = klip.klip_cikar(
            kayit_koku=tmp_path,
            camera="cam-16",
            olay_ts=datetime.now(UTC).timestamp(),
            hedef=tmp_path / "cikti.mp4",
        )
        assert sonuc is None
        assert not (tmp_path / "cikti.mp4").exists(), "boş dosya bırakılmamalı"

    def test_BOZUK_segment_None_donuyor(self, tmp_path: Path) -> None:
        """Segment adı doğru ama içerik video değil.

        Disk dolduğunda ya da MediaMTX yazarken kapandığında olabiliyor.
        Sistem çökmemeli, klip üretmeden devam etmeli.
        """
        an = datetime.now().astimezone()
        _segment_yaz(tmp_path / "cam-16", an)
        sonuc = klip.klip_cikar(
            kayit_koku=tmp_path,
            camera="cam-16",
            olay_ts=an.timestamp() + 5,
            hedef=tmp_path / "cikti.mp4",
        )
        assert sonuc is None
        assert not (tmp_path / "cikti.mp4").exists()
