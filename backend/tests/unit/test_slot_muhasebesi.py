"""Slot muhasebesi — çöken bir tüketicinin sızdırdığı slotları kurtarma.

⚠ NEDEN BU TESTLER VAR — 30.08.2026'da ölçülen SESSİZ arıza
-----------------------------------------------------------
Çıkarım worker'ı sert kapatıldığında (kill, çökme, ölçüm betiğinin
yeniden başlatması) elindeki mesajlar tüketici grubunda **asılı**
kalıyor ve paylaşımlı bellek slotları havuza dönmüyordu:

    48 slotun 48'i sızmış · boş slot 0/48 · üretim durmuş

Arıza **sessiz**: bütün süreçler ayakta, panel bağlı, sağlık kontrolü
yeşil — alım worker'ı yalnızca slot bulamadığı için her kareyi atıyor
(`reason="no_slot"`) ve sistem hiçbir şey işlemiyor.

Gün 23'te 24 saatlik dayanıklılık koşusu var. Tek bir çökme havuzu
kalıcı olarak küçültüyorsa o koşu anlamsız.

⚠ TESTLER GERÇEK VALKEY İSTEMİYOR
Slot muhasebesi saf bir küme hesabı: "üç yerden birinde olmayan slot
sızmıştır". Küme mantığını sınamak için sahte bir istemci yeterli;
`XAUTOCLAIM`/`XPENDING` davranışı entegrasyon testinin konusu.
"""

from __future__ import annotations

from typing import Any

from sentinel.bus.streams import SlotAllocator


class SahteIstemci:
    """`lrange` ve `llen` dışında hiçbir şey yapmayan sahte Valkey."""

    def __init__(self, bos: list[int]) -> None:
        self._bos = [str(s) for s in bos]

    def lrange(self, _key: str, _bas: int, _bit: int) -> list[str]:
        return list(self._bos)

    def llen(self, _key: str) -> int:
        return len(self._bos)

    def rpush(self, _key: str, *degerler: Any) -> None:
        self._bos.extend(str(d) for d in degerler)


def _dagitici(bos: list[int], toplam: int = 8) -> tuple[SlotAllocator, SahteIstemci]:
    istemci = SahteIstemci(bos)
    return SlotAllocator(istemci, toplam), istemci  # type: ignore[arg-type]


class TestSizanSlotlar:
    def test_HICBIR_YERDE_OLMAYAN_slot_sizmis_sayiliyor(self) -> None:
        """8 slotluk havuz: 3'ü boş, 2'si işlenmemiş → 3'ü sızmış."""
        dagitici, _ = _dagitici(bos=[0, 1, 2])
        assert sorted(dagitici.sizanlari_geri_al({3, 4})) == [5, 6, 7]

    def test_HER_SLOT_YERINDEYSE_sizinti_YOK(self) -> None:
        """⚠ Yanlış pozitif, kaçırmaktan tehlikeli.

        Kullanımdaki bir slotu "sızmış" sanıp havuza atmak, aynı slota
        iki karenin birden yazılmasına yol açar — ve o bozulma
        görüntüde sessizce belirir.
        """
        dagitici, _ = _dagitici(bos=[0, 1, 2, 3])
        assert dagitici.sizanlari_geri_al({4, 5, 6, 7}) == []

    def test_TAMAMEN_SIZMIS_havuz_tamamen_kurtariliyor(self) -> None:
        """Gerçekte yaşanan durum: boş liste sıfır, hiçbiri kullanımda değil."""
        dagitici, _ = _dagitici(bos=[])
        assert sorted(dagitici.sizanlari_geri_al(set())) == list(range(8))

    def test_geri_alinan_slotlar_havuza_donuyor(self) -> None:
        dagitici, _ = _dagitici(bos=[])
        sizan = dagitici.sizanlari_geri_al(set())
        dagitici.release_many(sizan)
        assert dagitici.available == 8

    def test_BOZUK_kayit_cokertmiyor(self) -> None:
        """Boş listede sayıya çevrilemeyen bir değer varsa atlanmalı.

        Havuz anahtarı elle kurcalanmış ya da eski bir sürümden kalmış
        olabilir; bu, kurtarma yolunu tümden çalışmaz hâle
        getirmemeli — kurtarma zaten bir arızadan çıkış yolu.
        """
        istemci = SahteIstemci([])
        istemci._bos = ["0", "bozuk", "2"]
        dagitici = SlotAllocator(istemci, 4)  # type: ignore[arg-type]
        assert sorted(dagitici.sizanlari_geri_al(set())) == [1, 3]
