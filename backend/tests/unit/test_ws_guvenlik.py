"""WebSocket güvenlik kontrolleri ve dosya adı temizleme.

⚠ NEDEN BU TESTLER
------------------
Buradaki üç fonksiyon güvenlik sınırında duruyor ve **ikisi zaten bir
kez hataya yol açtı**:

  · `origin_allowed`  → P-11 ve P-21: kontrol çalışıyordu ama meşru
    istemciyi de engelliyordu. İki kez aynı sınıf hata.
  · `_safe_name`      → G12 path traversal, kod incelemesinde bulundu.

Güvenlik kontrolü yazarken iki yönü de test etmek gerekiyor:
**kötüyü engelliyor mu** VE **iyiyi geçiriyor mu**. P-11'in dersi tam
olarak ikincisinin unutulmasıydı.
"""

from __future__ import annotations

import pytest

from sentinel.api.main import _safe_name
from sentinel.api.ws.live import MAX_SUBSCRIPTIONS, authorize_cameras, origin_allowed

# ══════════════════════════════════════════════════════════════
#  Origin doğrulaması (G06)
# ══════════════════════════════════════════════════════════════


class TestOriginDogrulamasi:
    """WebSocket CORS'a UYMAZ — Origin elle doğrulanmak zorunda.

    Kötü niyetli bir sayfa kullanıcının tarayıcısından bizim sunucumuza
    WS açabilir ve tüm kamera akışını dinleyebilir. `CORSMiddleware`
    bunu engellemez.
    """

    def test_ayni_koken_kabul_ediliyor(self) -> None:
        """Panel API ile aynı sunucudan servis ediliyorsa güvenilir.

        Bu kontrol olmasa beyaz listeye kendi adresimizi elle eklemek
        gerekirdi ve adres değişince sessizce kırılırdı (P-11).
        """
        assert origin_allowed("http://127.0.0.1:8001", "127.0.0.1:8001")
        assert origin_allowed("https://sentinel.local", "sentinel.local")

    def test_beyaz_listedeki_gelistirme_sunucusu_kabul_ediliyor(self) -> None:
        """Vite geliştirme sunucusu ayrı portta — beyaz listeden geçmeli."""
        assert origin_allowed("http://localhost:5173", "127.0.0.1:8001")

    def test_P21_GERILEMESI_localhost_ve_127_0_0_1_IKISI_DE_calisiyor(self) -> None:
        """⚠ P-21 gerilemesi — `localhost` ile `127.0.0.1` AYRI kökenlerdir.

        Tarayıcı `Origin` başlığını adres çubuğuna ne yazıldıysa ona göre
        gönderir. Aynı makineyi göstermeleri fark etmez. Beyaz listede
        yalnızca biri varsa diğeri 403 alır.

        Bu P-11'in tekrarıydı. Üçüncü kez yaşanmasın diye test.
        """
        assert origin_allowed("http://127.0.0.1:5173", "127.0.0.1:8001")
        assert origin_allowed("http://localhost:5173", "127.0.0.1:8001")

    def test_yabanci_koken_REDDEDILIYOR(self) -> None:
        """Asıl korunmak istediğimiz şey."""
        assert not origin_allowed("http://evil.example.com", "127.0.0.1:8001")
        assert not origin_allowed("https://evil.example.com", "127.0.0.1:8001")

    def test_ayni_host_FARKLI_PORT_reddediliyor(self) -> None:
        """Aynı köken politikası portu da kapsar.

        Aynı makinede çalışan başka bir uygulama (örn. `teknofest_api`)
        bizim akışımızı dinleyememeli.
        """
        assert not origin_allowed("http://127.0.0.1:9999", "127.0.0.1:8001")

    def test_ayni_host_FARKLI_SEMA_reddediliyor(self) -> None:
        """http ile https AYRI kökenlerdir — şema de karşılaştırılmalı.

        `Host` başlığı şema taşımaz; şema bağlantının kendisinden
        (ws/wss) türetilip veriliyor. Bu test olmasa `Origin: https://`
        ile `Host: 127.0.0.1:8001` eşleşmeye devam ederdi.
        """
        # Sunucu http (ws) üzerinde — https origin eşleşmemeli
        assert not origin_allowed("https://127.0.0.1:8001", "127.0.0.1:8001", "http")
        # Doğru şema ile eşleşmeli
        assert origin_allowed("http://127.0.0.1:8001", "127.0.0.1:8001", "http")
        # TLS arkasında (Caddy) tersi geçerli
        assert origin_allowed("https://sentinel.local", "sentinel.local", "https")
        assert not origin_allowed("http://sentinel.local", "sentinel.local", "https")

    def test_origin_YOKSA_reddediliyor(self) -> None:
        """Tarayıcı Origin'i her zaman gönderir.

        Göndermeyen istemci tarayıcı değildir; sunucu tarafı bir betik
        ya da doğrudan soket bağlantısıdır.
        """
        assert not origin_allowed(None, "127.0.0.1:8001")
        assert not origin_allowed("", "127.0.0.1:8001")

    def test_bozuk_origin_COKMUYOR(self) -> None:
        """Kötü niyetli girdi ayrıştırıcıyı patlatmamalı."""
        for bozuk in ["://", "http://[", "not-a-url", "http://:::"]:
            assert origin_allowed(bozuk, "127.0.0.1:8001") is False

    def test_host_basligi_yoksa_ayni_koken_gecmiyor(self) -> None:
        """Host yoksa "aynı köken" iddiası doğrulanamaz — reddedilmeli."""
        assert not origin_allowed("http://127.0.0.1:8001", None)


# ══════════════════════════════════════════════════════════════
#  Kamera abonelik doğrulaması (G07)
# ══════════════════════════════════════════════════════════════


class TestKameraYetkilendirmesi:
    """İstemcinin gönderdiği listeye ASLA olduğu gibi güvenilmez (G07).

    ⚠ 01.09.2026 — SÖZLEŞME DEĞİŞTİ: biçim → BEYAZ LİSTE
    Önceki sürüm yalnızca "harf-rakam-tire" diye bakıyordu ve `cam-99`
    gibi var olmayan adlar geçiyordu. Tek başına ciddi bir açık değil
    (olmayan kameradan veri akmaz) ama yetki kontrolünün ilkesi
    ihlal ediliyordu: **bilinen iyileri saymak, kötüleri tahmin
    etmekten güvenlidir.**

    Bu sınıftaki testler o eski sözleşmeyi kodluyordu; yeni davranışa
    göre güncellendi. Test bir sözleşmedir ve sözleşme değişince test
    de değişmeli — ama değişikliğin GEREKÇESİ yazılmalı, yoksa
    "testi geçirmek için testi değiştirdim" ile ayırt edilemez.
    """

    def test_TANIMLI_kamera_adlari_geciyor(self) -> None:
        assert authorize_cameras(["cam-01", "cam-20", "cam-21-live"]) == [
            "cam-01",
            "cam-20",
            "cam-21-live",
        ]

    def test_TANIMSIZ_kamera_adi_ELENIYOR(self) -> None:
        """⚠ Yeni davranış. `cam-99` biçim olarak kusursuz ama YOK.

        Eski sürümde geçiyordu ve istemci "abone oldum" cevabı alıp
        hiç veri görmüyordu — sessiz bir hata kaynağı.
        """
        assert authorize_cameras(["cam-99", "cam-01", "admin-panel"]) == ["cam-01"]

    def test_bicimsiz_adlar_eleniyor(self) -> None:
        """Yol ayracı, joker ve boşluk içeren adlar geçmemeli."""
        kirli = ["cam-01", "../../etc", "cam/*", "cam 02", "", "a" * 100]
        assert authorize_cameras(kirli) == ["cam-01"]

    def test_string_olmayan_girdiler_cokmeye_yol_acmiyor(self) -> None:
        """İstemci JSON'una güvenilmez — sayı, None, sözlük gelebilir."""
        assert authorize_cameras([1, None, {"a": 1}, ["x"], "cam-05"]) == ["cam-05"]  # type: ignore[list-item]

    def test_abonelik_sayisi_sinirli(self) -> None:
        """Sınırsız abonelik = tek istemcinin sunucuyu boğması (G13/G14).

        ⚠ Sınır DOĞRULAMADAN ÖNCE uygulanıyor: istemci 10 000 ad
        gönderirse hepsini beyaz listeye karşı sınamak da bir yük
        olurdu. Kesme önce, doğrulama sonra.
        """
        cok = ["cam-01"] * (MAX_SUBSCRIPTIONS + 50)
        assert len(authorize_cameras(cok)) == MAX_SUBSCRIPTIONS

    def test_bos_liste_bos_donuyor(self) -> None:
        assert authorize_cameras([]) == []


# ══════════════════════════════════════════════════════════════
#  Dosya adı temizleme (G12 — path traversal)
# ══════════════════════════════════════════════════════════════


class TestDosyaAdiTemizleme:
    """`/debug/trace` istemciden gelen `camera` alanını dosya adına koyuyordu.

    Beyaz liste yaklaşımı kullanılıyor (kara liste değil): yalnızca
    `[A-Za-z0-9_-]` geçer. Böylece tehlikeli karakterleri tek tek
    saymaya gerek kalmıyor — sayılmayan bir tanesini unutmak zaten
    bu sınıf açığın klasik sebebi.
    """

    @pytest.mark.parametrize(
        "saldiri",
        [
            "../../../etc/passwd",
            "..\\..\\Windows\\System32\\config",
            "/mutlak/yol",
            "C:\\Windows\\sistem",
            "cam/../../gizli",
            "cam\x00.json",       # null bayt enjeksiyonu
            "cam%2e%2e%2fgizli",  # URL kodlanmış ..
        ],
    )
    def test_yol_kacisi_engelleniyor(self, saldiri: str) -> None:
        temiz = _safe_name(saldiri)
        assert "/" not in temiz
        assert "\\" not in temiz
        assert ".." not in temiz
        assert ":" not in temiz
        assert "\x00" not in temiz

    def test_mesru_kamera_adi_BOZULMUYOR(self) -> None:
        """⚠ P-11'in dersi: güvenlik kontrolü meşru girdiyi de geçirmeli."""
        assert _safe_name("cam-09") == "cam-09"
        assert _safe_name("cam-21-live") == "cam-21-live"
        assert _safe_name("cam_test_01") == "cam_test_01"

    def test_bos_kalirsa_yedek_ad_donuyor(self) -> None:
        """Aksi hâlde `trace_20260818-101500_.json` gibi adsız dosyalar birikirdi."""
        assert _safe_name("") == "bilinmeyen"
        assert _safe_name("///") == "bilinmeyen"
        assert _safe_name("../..") == "bilinmeyen"

    def test_uzunluk_sinirlaniyor(self) -> None:
        """Windows MAX_PATH 260 karakter; uzun ad dosya yazımını bozardı."""
        assert len(_safe_name("a" * 500)) == 32
