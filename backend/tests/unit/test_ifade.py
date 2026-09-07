"""İfade → risk sinyali eşlemesinin testleri (analytics/ifade.py).

⚠ NEDEN BU TESTLER ÖZELLİKLE GEREKLİ
Bu modül 03.09.2026'da, **iki yerde yazılı bir iddianın yanlış
çıkması** üzerine yazıldı. `fusion.py` ve `analytics/worker.py`
şunu söylüyordu:

    "Bağlantı yeri hazır; gerçek bir kurulumda beslendiğinde kod
     değişikliği gerekmeyecek."

Oysa `ifade=0.0` sabit yazılıydı ve `expr` alanı hiç okunmuyordu.
İddia kimse tarafından sınanmamıştı — çünkü sınayacak bir test yoktu.

Bu testlerin asıl işi bir daha aynı şeyin olmaması: **sinyalin akıp
akmadığını** doğruluyorlar, yalnızca aritmetiği değil.
"""

from __future__ import annotations

from sentinel.analytics.ifade import (
    ASGARI_KALITE,
    IFADE_RISK,
    IfadeSinyali,
    ham_skor,
)


class TestHamSkor:
    def test_ifade_yoksa_sifir(self) -> None:
        """`expr` alanı olmayan tespit → 0.0. En sık görülen durum."""
        assert ham_skor(None) == 0.0
        assert ham_skor({}) == 0.0

    def test_bicimi_bozuk_girdi_patlamiyor(self) -> None:
        """Sözlük olmayan girdi sessizce 0.0.

        ⚠ Bu alan bir AĞ MESAJINDAN geliyor (`inference.results`).
        Analitik worker'ın tek bozuk mesajla düşmemesi gerekiyor —
        aynı ders P-29'da dışarıdan ulaşılabilir bir çökme yolu
        olarak çıkmıştı.
        """
        assert ham_skor("Anger") == 0.0
        assert ham_skor(42) == 0.0
        assert ham_skor([{"label": "Anger"}]) == 0.0

    def test_notr_ve_mutluluk_katki_vermiyor(self) -> None:
        """Yüksek güven ve kalitede bile sıfır — tabanları 0."""
        for etiket in ("Neutral", "Happiness"):
            assert ham_skor({"label": etiket, "conf": 0.99, "q": 0.99}) == 0.0

    def test_ofke_en_yuksek_katki(self) -> None:
        ofke = ham_skor({"label": "Anger", "conf": 1.0, "q": 1.0})
        korku = ham_skor({"label": "Fear", "conf": 1.0, "q": 1.0})
        uzuntu = ham_skor({"label": "Sadness", "conf": 1.0, "q": 1.0})
        assert ofke == 1.0
        assert ofke > korku > uzuntu > 0.0

    def test_dusuk_kalite_tamamen_eleniyor(self) -> None:
        """Kalite eşiğinin altındaki sınıflandırma HİÇ sayılmıyor.

        ⚠ Çarpımla söndürmek yetmiyordu: kalite 0.15 olan bir "öfke"
        çarpımdan 0.15 çıkar ve füzyonun katkı eşiği de tam 0.15.
        Yani gürültü, "katkıda bulunan sinyal" sayılabilirdi ve
        füzyonun "en az iki sinyal" kuralı gürültüyle doldurulabilirdi.
        """
        dusuk = ASGARI_KALITE - 0.01
        assert ham_skor({"label": "Anger", "conf": 1.0, "q": dusuk}) == 0.0
        assert ham_skor({"label": "Anger", "conf": 1.0, "q": ASGARI_KALITE}) > 0.0

    def test_guven_ve_kalite_carpiyor(self) -> None:
        """Skor = taban × güven × kalite."""
        s = ham_skor({"label": "Anger", "conf": 0.5, "q": 0.8})
        assert abs(s - (1.0 * 0.5 * 0.8)) < 1e-9

    def test_bilinmeyen_etiket_sifir(self) -> None:
        """Model yeni bir etiket üretirse sessizce 0 — patlamıyor.

        ⚠ Ama bu sessizlik bir risk: `IFADE_RISK` anahtarları
        `emotion/base.py · EXPRESSION_TR` ile birebir aynı olmak
        zorunda ve bir yazım hatası tüm sinyali sessizce sıfırlar.
        Aşağıdaki test tam bunu koruyor.
        """
        assert ham_skor({"label": "Öfke", "conf": 1.0, "q": 1.0}) == 0.0
        assert ham_skor({"label": "", "conf": 1.0, "q": 1.0}) == 0.0

    def test_etiket_kumesi_modelinkiyle_ayni(self) -> None:
        """⚠ EN DEĞERLİ TEST: iki sözlük ayrışırsa sinyal sessizce ölür.

        `IFADE_RISK` model çıktısının etiketleriyle eşleşmezse hiçbir
        hata oluşmaz — yalnızca her skor 0 çıkar ve "yüzler küçük"
        diye yanlış teşhis edilir. Bu test o sessiz arızayı gürültülü
        hâle getiriyor.
        """
        from sentinel.inference.emotion.base import EXPRESSION_TR

        assert set(IFADE_RISK) == set(EXPRESSION_TR)


class TestIfadeSinyali:
    def _tespit(self, track_id: int, expr: object = None) -> dict[str, object]:
        d: dict[str, object] = {"id": track_id, "bbox": [0, 0, 10, 20]}
        if expr is not None:
            d["expr"] = expr
        return d

    def test_ifade_gelmeden_skor_yok(self) -> None:
        s = IfadeSinyali()
        assert s.guncelle("cam-01", [self._tespit(1)], 0.0) == {}

    def test_sinyal_gercekten_akiyor(self) -> None:
        """⭐ Modülün varlık sebebi: skor iz kimliğine ULAŞIYOR mu."""
        s = IfadeSinyali()
        cikti = s.guncelle(
            "cam-01",
            [self._tespit(7, {"label": "Anger", "conf": 1.0, "q": 1.0})],
            0.0,
        )
        assert cikti == {7: 1.0}

    def test_son_deger_sonraki_karelerde_korunuyor(self) -> None:
        """KADEME 2b seyrek çalışıyor; aradaki karelerde sinyal düşmemeli.

        ⚠ Durum tutulmasaydı sinyal karelerin %95'inde 0 olurdu ve
        füzyonun "iki sinyal aynı anda" kuralı neredeyse hiç
        sağlanmazdı — ifade ağırlığı kâğıt üstünde kalırdı.
        """
        s = IfadeSinyali()
        s.guncelle("cam-01", [self._tespit(7, {"label": "Anger", "conf": 1.0, "q": 1.0})], 0.0)
        # Sonraki iki karede `expr` YOK (2b çalışmadı)
        for t in (0.25, 0.50):
            assert s.guncelle("cam-01", [self._tespit(7)], t) == {7: 1.0}

    def test_pencere_ortalamasi_alinıyor(self) -> None:
        """Ardışık iki sınıflandırmanın ortalaması (PLAN §6.3)."""
        s = IfadeSinyali()
        s.guncelle("cam-01", [self._tespit(3, {"label": "Anger", "conf": 1.0, "q": 1.0})], 0.0)
        cikti = s.guncelle(
            "cam-01", [self._tespit(3, {"label": "Neutral", "conf": 1.0, "q": 1.0})], 2.0
        )
        assert abs(cikti[3] - 0.5) < 1e-9

    def test_kameralar_birbirine_karismiyor(self) -> None:
        """Aynı iz numarası farklı kameralarda AYRI kişilerdir.

        ⚠ Takip kimlikleri kamera başına üretiliyor; `cam-01`'deki 5
        ile `cam-02`'deki 5 aynı kişi değil. Anahtarı yalnızca iz
        numarası yapmak, iki kameranın sinyalini birbirine karıştırırdı.
        """
        s = IfadeSinyali()
        s.guncelle("cam-01", [self._tespit(5, {"label": "Anger", "conf": 1.0, "q": 1.0})], 0.0)
        assert s.guncelle("cam-02", [self._tespit(5)], 0.0) == {}

    def test_kimliksiz_tespit_atlaniyor(self) -> None:
        """`id` yoksa (onaylanmamış iz, P-13) zamansal analiz yapılamaz."""
        s = IfadeSinyali()
        cikti = s.guncelle(
            "cam-01",
            [{"bbox": [0, 0, 1, 1], "expr": {"label": "Anger", "conf": 1.0, "q": 1.0}}],
            0.0,
        )
        assert cikti == {}

    def test_budama_eski_izleri_atiyor(self) -> None:
        """⚠ Mimari kural 5: sınırsız büyüyen hiçbir yapı olmayacak.

        Füzyon katmanında bu tam olarak atlanmıştı: `RiskFuzyonu.buda()`
        yazılmış ama hiç çağrılmamıştı (03.09.2026'da düzeltildi).
        Aynı hatanın burada tekrarlanmaması için test.
        """
        s = IfadeSinyali()
        s.guncelle("cam-01", [self._tespit(1, {"label": "Anger", "conf": 1.0, "q": 1.0})], 0.0)
        assert s.aktif_iz == 1
        assert s.buda(simdi=1000.0) == 1
        assert s.aktif_iz == 0
