"""Üretim özellik hesabı ⟷ eğitim özellik hesabı kilidi (P-56).

⭐⭐ BU TESTİN VARLIK SEBEBİ
--------------------------
`analytics/model.py · pencere_ozeti()` ile
`scripts/train_aggression.py · _klip_ozellikleri()` **aynı** özet
vektörünü üretmek zorunda. Ayrışırlarsa model, eğitildiğinden farklı
bir dağılımla beslenir ve hata **SESSİZ** olur: skor üretilir, boru
hattı çalışır, yalnızca sonuç yanlıştır.

⚠ Bu, projenin en pahalı hata türü. Aynı desen daha önce iki kez
yakalandı:
  * P-39 — koordinat uzayı ayrışması, AUC 0.483 gösterdi
  * `evaluate_k8_video.py` — özellik adlarını kopyalamak yerine
    eğitim betiğinden import ederek çözmüştü

`src/` bir betikten import edemez (betikler pakette değil), o yüzden
`model.py` adları kopyalamak zorunda. **Kopya varsa kilit gerekir** —
bu dosya o kilit.
"""

from __future__ import annotations

import statistics

import pytest

from sentinel.analytics.model import (
    BILESENLER,
    HAM_ALANLAR,
    SaldirganlikModeli,
    iz_paylari,
    pencere_ozeti,
)


class _SahteSkor:
    """`TirmanmaSkoru` yerine geçen asgari nesne."""

    def __init__(self, track_id: int, skor: float) -> None:
        self.track_id = track_id
        self.skor = skor
        self.egim = 0.0
        self.bilesenler = dict.fromkeys(BILESENLER, 0.0)


def _egitim_ozeti(
    bilesen_kareleri: list[dict[str, float]],
    ham_kareler: list[list[dict[str, float]]],
) -> dict[str, float]:
    """`train_aggression.py · _klip_ozellikleri` özet bloğunun ikizi.

    ⚠ KASTEN BAĞIMSIZ YAZILDI. `pencere_ozeti`yi çağırsaydı test
    hiçbir şey doğrulamazdı — iki uygulamanın aynı sonucu vermesi
    ancak ikisi ayrı yazılırsa anlamlı.
    """

    def _p(sirali: list[float], oran: float) -> float:
        if not sirali:
            return 0.0
        return sirali[min(len(sirali) - 1, int(len(sirali) * oran))]

    cikti: dict[str, float] = {}
    for alan in (*BILESENLER, "skor"):
        degerler = sorted(s[alan] for s in bilesen_kareleri)
        cikti[f"{alan}_azami"] = degerler[-1]
        cikti[f"{alan}_p90"] = degerler[int(len(degerler) * 0.9)]
        cikti[f"{alan}_ortalama"] = statistics.fmean(degerler)
    cikti["egim_azami"] = max(s["egim"] for s in bilesen_kareleri)

    ham_seri = [k for kare in ham_kareler for k in kare]
    for alan in HAM_ALANLAR:
        d = sorted(s[alan] for s in ham_seri if alan in s)
        if d:
            cikti[f"ham_{alan}_azami"] = d[-1]
            cikti[f"ham_{alan}_p75"] = d[min(len(d) - 1, int(len(d) * 0.75))]
            cikti[f"ham_{alan}_medyan"] = statistics.median(d)

    for alan in HAM_ALANLAR:
        aykiriliklar: list[float] = []
        medyanlar: list[float] = []
        for kare in ham_kareler:
            d = sorted(k[alan] for k in kare if alan in k)
            if len(d) < 2:
                continue
            med = statistics.median(d)
            aykiriliklar.append(d[-1] - med)
            medyanlar.append(med)
        if aykiriliklar:
            a = sorted(aykiriliklar)
            cikti[f"ayk_{alan}_azami"] = a[-1]
            cikti[f"ayk_{alan}_p75"] = a[min(len(a) - 1, int(len(a) * 0.75))]
            cikti[f"ayk_{alan}_medyan"] = statistics.median(a)
            cikti[f"sahne_{alan}_medyan"] = statistics.median(medyanlar)
    return cikti


def _ornek_pencere() -> tuple[list[dict[str, float]], list[list[dict[str, float]]]]:
    """Gerçekçi bir pencere: 6 kare, kare başına 1-4 kişi."""
    bilesen = [
        {**{b: 0.1 * (i % 5) + 0.05 * j for j, b in enumerate(BILESENLER)},
         "skor": 0.02 * i, "egim": 0.01 * i}
        for i in range(6)
    ]
    ham: list[list[dict[str, float]]] = []
    for i in range(6):
        kare = []
        for kisi in range(1 + i % 4):
            kare.append({
                alan: 0.3 + 0.07 * k + 0.11 * kisi + 0.05 * i
                for k, alan in enumerate(HAM_ALANLAR)
            })
        ham.append(kare)
    return bilesen, ham


def test_uretim_ve_egitim_ozeti_AYNI_vektoru_uretiyor() -> None:
    """⭐ Kilit: iki bağımsız uygulama aynı girdide aynı çıktıyı vermeli."""
    bilesen, ham = _ornek_pencere()
    uretim = pencere_ozeti(bilesen, ham)
    egitim = _egitim_ozeti(bilesen, ham)

    assert set(uretim) == set(egitim), (
        "Sütun kümeleri ayrıştı — model eğitildiğinden farklı "
        f"sütunlarla beslenir. Fark: {set(uretim) ^ set(egitim)}"
    )
    for anahtar in sorted(uretim):
        assert uretim[anahtar] == pytest.approx(egitim[anahtar], rel=1e-9), (
            f"'{anahtar}' değeri ayrıştı: "
            f"üretim {uretim[anahtar]} ⟷ eğitim {egitim[anahtar]}"
        )


def test_tek_kisilik_karelerde_aykirilik_URETILMIYOR() -> None:
    """Aykırılık en az 2 kişi ister — tek kişide 'sahneye göre' tanımsız."""
    bilesen = [{**dict.fromkeys(BILESENLER, 0.2), "skor": 0.3, "egim": 0.0}]
    ham = [[dict.fromkeys(HAM_ALANLAR, 0.5)]]  # tek kişi
    ozet = pencere_ozeti(bilesen, ham)
    assert not any(k.startswith("ayk_") for k in ozet)
    assert any(k.startswith("ham_") for k in ozet)


def test_bos_pencere_bos_ozet_veriyor() -> None:
    assert pencere_ozeti([], []) == {}


def test_eksik_ham_alan_SIFIR_DEGIL_yok_sayiliyor() -> None:
    """⚠ Eksik ≠ sıfır. Eksik alan özete HİÇ girmemeli.

    Sıfır yazmak modele "bu pencerede hareket yoktu" öğretirdi; oysa
    gerçek durum "ölçemedik" (person.py modül başlığı). LightGBM
    eksikliği `NaN` olarak öğreniyor ve o `NaN`, sütun özette
    olmadığında oluşuyor.
    """
    bilesen = [{**dict.fromkeys(BILESENLER, 0.2), "skor": 0.3, "egim": 0.0}]
    ham = [[{"govde_hizi": 0.4}, {"govde_hizi": 0.6}]]  # yalnızca bir alan
    ozet = pencere_ozeti(bilesen, ham)
    assert "ham_govde_hizi_medyan" in ozet
    assert "ham_bilek_hizi_p75_medyan" not in ozet
    assert "ayk_bilek_hizi_p75_azami" not in ozet


class TestIzPaylari:
    def test_en_yuksek_kural_skoru_tam_pay_aliyor(self) -> None:
        paylar = iz_paylari([_SahteSkor(1, 0.8), _SahteSkor(2, 0.4)])
        assert paylar[1] == pytest.approx(1.0)
        assert 0.5 < paylar[2] < 1.0

    def test_hicbir_iz_SIFIRLANMIYOR(self) -> None:
        """⚠ Kural düz çıkabiliyor; sıfırlamak gerçek olayı kaçırtır."""
        paylar = iz_paylari([_SahteSkor(1, 1.0), _SahteSkor(2, 0.0)])
        assert paylar[2] >= 0.5

    def test_tum_skorlar_sifirsa_herkes_esit(self) -> None:
        paylar = iz_paylari([_SahteSkor(1, 0.0), _SahteSkor(2, 0.0)])
        assert paylar == {1: 1.0, 2: 1.0}

    def test_bos_liste_bos_sozluk(self) -> None:
        assert iz_paylari([]) == {}


class TestModelYuklemesi:
    def test_model_dosyasi_yoksa_SESSIZCE_devre_disi(self, tmp_path) -> None:
        """⚠ Eksik bağımlılık boru hattını DURDURMAMALI.

        Model yoksa füzyon eski kural skoruna döner. İstisna fırlatmak,
        20 kameralı bir gözetim sistemini bir dosya yüzünden komple
        durdurmak olurdu.
        """
        m = SaldirganlikModeli(tmp_path / "yok.txt", None)
        assert m.etkin is False
        assert m.degerlendir("cam-01") is None

    def test_devre_disi_model_besleme_kabul_ediyor(self, tmp_path) -> None:
        """Devre dışıyken `besle()` sessizce hiçbir şey yapmamalı."""
        m = SaldirganlikModeli(tmp_path / "yok.txt", None)
        m.besle("cam-01", [], [], 0.0)
        assert m.kamera_sayisi() == 0
