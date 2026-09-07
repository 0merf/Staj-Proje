"""Klip uç noktasının yol doğrulaması — G12 (path traversal).

⚠ NEDEN AYRI BİR TEST DOSYASI
`test_klip.py` klibin KESİLMESİNİ test ediyor (12 test). Bu dosya
klibe ERİŞİMİ test ediyor. İkisi ayrı riskler:

    kesme  → yanlış anı içeren bir dosya üretme riski
    erişim → dosya sisteminde istenmeyen bir yere ulaşma riski

Klip ucu 03.09.2026'da eklendi ve eklenmesinin sebebi kendi başına
bir bulguydu: klipler 30.08'den beri kesiliyor, veritabanına
yazılıyor ve **hiçbir yerden erişilemiyordu.** Uç eklenince G12
(path traversal) ilk kez gerçek bir saldırı yüzeyi hâline geldi —
daha önce "gerekmedi" durumundaydı.

⚠ BEYAZ LİSTE SINANIYOR, KARA LİSTE DEĞİL
Testler yalnızca bilinen kötü girdileri denemiyor; **geçerli biçimin
tam olarak ne olduğunu** sabitliyor. Kara liste testi ("`..` reddedilsin")
yalnızca düşünülen saldırıları kapsar; beyaz liste testi düşünülmeyeni
de kapsar.
"""

from __future__ import annotations

import pytest

from sentinel.api.routers.olaylar import KLIP_DESENI


class TestGecerliAnahtar:
    """`alerting/klip.py · klip_anahtari()` çıktısı GEÇMELİ."""

    @pytest.mark.parametrize(
        "anahtar",
        [
            "2026/09/03/cam-16/115742_fall.mp4",
            "2026/12/31/cam-01/000000_risk.mp4",
            "2026/01/01/cam-21-live/235959_aggression.mp4",
            "2026/08/30/cam_test_1/120000_crowd.mp4",
        ],
    )
    def test_uretilen_bicim_geciyor(self, anahtar: str) -> None:
        assert KLIP_DESENI.match(anahtar)

    def test_gercek_uretici_ile_uyumlu(self) -> None:
        """⭐ EN ÖNEMLİ TEST: desen ile ÜRETİCİ ayrışırsa uç ölür.

        Desen çok darsa geçerli klipler 404 döner ve sebebi görünmez
        olur ("klip yok" der, oysa klip var). Bu test iki tarafı
        birbirine bağlıyor: anahtarı üreten kod değişirse burası
        kırılır.
        """
        from sentinel.alerting.klip import klip_anahtari

        anahtar = klip_anahtari("cam-16", 1_756_900_000.0, "fall")
        assert KLIP_DESENI.match(anahtar), anahtar


class TestReddedilenAnahtar:
    @pytest.mark.parametrize(
        "anahtar",
        [
            # ─── Klasik dizin çıkışı ───
            "../../../etc/passwd",
            "2026/09/03/cam-16/../../../../gizli.mp4",
            "2026/09/03/../../../.env",
            # ─── Mutlak yollar ───
            "/etc/passwd",
            "C:/Windows/System32/config/SAM",
            "//sunucu/paylasim/dosya.mp4",
            # ─── Windows'a özgü ───
            "2026\\09\\03\\cam-16\\115742_fall.mp4",
            "2026/09/03/cam-16/115742_fall.mp4:stream",
            # ─── Uzantı oyunları ───
            "2026/09/03/cam-16/115742_fall.mp4.exe",
            "2026/09/03/cam-16/115742_fall.py",
            "2026/09/03/cam-16/115742_fall",
            # ─── Biçim bozuklukları ───
            "",
            "2026/9/3/cam-16/115742_fall.mp4",       # tek haneli ay/gün
            "2026/09/03/cam-16/11574_fall.mp4",      # 5 haneli saat
            "2026/09/03//115742_fall.mp4",           # boş kamera
            "2026/09/03/cam-16/115742_FALL.mp4",     # büyük harf tür
            "2026/09/03/cam-16/115742_fall.mp4/x",   # fazladan parça
            # ⚠ Kodlanmış çıkış denemeleri: FastAPI yolu çözerek
            # verse bile desen bunları da elemeli.
            "2026/09/03/cam-16/%2e%2e%2fgizli.mp4",
            "....//....//gizli.mp4",
        ],
    )
    def test_reddediliyor(self, anahtar: str) -> None:
        assert KLIP_DESENI.match(anahtar) is None, f"GEÇTİ ama geçmemeliydi: {anahtar}"

    @pytest.mark.parametrize(
        "anahtar",
        [
            "2026/09/03/cam-16/115742_fall.mp4\n",
            "2026/09/03/cam-16/115742_fall.mp4\n../gizli",
            "\n2026/09/03/cam-16/115742_fall.mp4",
        ],
    )
    def test_yeni_satir_ile_desen_atlatilamiyor(self, anahtar: str) -> None:
        """⚠ `$` TUZAĞI — bu test deseni bulduğu için var.

        Python'da `$` yalnızca dizenin sonunu değil, SONDAKİ YENİ
        SATIRDAN ÖNCESİNİ de eşleştirir: `re.match(r"^abc$", "abc\\n")`
        EŞLEŞİR. Desenin ilk hâli `^...$` kullanıyordu, yani
        `".../115742_fall.mp4\\n"` girdisini kabul ediyordu.

        Tek başına sömürülebilir değil — sondaki `\\n` yolu
        değiştirmiyor. Ama doğrulayıcı "tam olarak bu biçim" iddia
        ederken başka bir şey yapıyordu, ve bu projede pahalıya patlayan
        şey hep bu oldu: bir kontrolün ADI ile YAPTIĞI işin ayrışması.

        Desen `\\A ... \\Z` çapalarına geçirildi.
        """
        assert KLIP_DESENI.match(anahtar) is None, f"GEÇTİ ama geçmemeliydi: {anahtar!r}"
