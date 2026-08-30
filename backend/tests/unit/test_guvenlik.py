"""Kimlik doğrulama ve yetkilendirme — PLAN.md §11.1.

⚠ NEDEN BU TESTLER ÖZELLİKLE ÖNEMLİ
-----------------------------------
Güvenlik hataları **sessizdir.** Yanlış bir anomali eşiği panelde
görülür; yanlış bir yetki kontrolü hiçbir şey göstermez — sistem
çalışmaya devam eder, sadece yapmaması gereken şeyi de yapar.

Bu yüzden testler "doğru parola çalışıyor mu" değil, ağırlıklı olarak
**yanlış olanın reddedildiğini** sınıyor: süresi dolmuş token, yanlış
tipte token, imzasız token, yetersiz rol.
"""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi import HTTPException

from sentinel.api import guvenlik
from sentinel.config import get_settings


@pytest.fixture(autouse=True)
def _anahtar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Testler gerçek `.env` anahtarına bağlı olmamalı."""
    from pydantic import SecretStr

    ayarlar = get_settings()
    monkeypatch.setattr(
        ayarlar, "jwt_secret_key", SecretStr("test-anahtari-yeterince-uzun-olmali-123")
    )


# ══════════════════════════════════════════════════════════════
#  Parola hash'i
# ══════════════════════════════════════════════════════════════


class TestParola:
    def test_dogru_parola_kabul_ediliyor(self) -> None:
        h = guvenlik.parola_hashle("cok-guclu-bir-parola")
        assert guvenlik.parola_dogru_mu(h, "cok-guclu-bir-parola")

    def test_yanlis_parola_reddediliyor(self) -> None:
        h = guvenlik.parola_hashle("cok-guclu-bir-parola")
        assert not guvenlik.parola_dogru_mu(h, "cok-guclu-bir-parolb")

    def test_AYNI_PAROLA_FARKLI_HASH(self) -> None:
        """⚠ Tuz (salt) çalışıyor mu.

        İki kullanıcı aynı parolayı seçtiğinde hash'leri AYNI olsaydı,
        veritabanını ele geçiren biri "bu ikisi aynı parolayı
        kullanıyor" bilgisini bedava alırdı — ve gökkuşağı tabloları
        (rainbow table) işe yarardı.
        """
        a = guvenlik.parola_hashle("ayni-parola")
        b = guvenlik.parola_hashle("ayni-parola")
        assert a != b
        assert guvenlik.parola_dogru_mu(a, "ayni-parola")
        assert guvenlik.parola_dogru_mu(b, "ayni-parola")

    def test_BOZUK_HASH_istisna_firlatmiyor(self) -> None:
        """Veritabanındaki bozuk bir kayıt giriş ucunu çökertmemeli.

        ⚠ `False` dönüyor, istisna değil: hata türünü dışarı vermek
        saldırgana "bu kullanıcı var ama kaydı bozuk" gibi bilgiler
        sızdırır.
        """
        assert not guvenlik.parola_dogru_mu("bu-bir-hash-degil", "parola")

    def test_argon2id_kullaniliyor(self) -> None:
        """⚠ MD5/SHA DEĞİL — onlar HIZLI olmak için tasarlandı.

        Parola hash'inde hız saldırganın işine yarar. Argon2id hem CPU
        hem BELLEK maliyeti dayatıyor, yani GPU'yla paralel kırma
        avantajını da siliyor.
        """
        assert guvenlik.parola_hashle("x").startswith("$argon2id$")


# ══════════════════════════════════════════════════════════════
#  Token
# ══════════════════════════════════════════════════════════════


class TestToken:
    def test_uretilen_token_cozulebiliyor(self) -> None:
        t = guvenlik.token_uret("ali", guvenlik.Rol.OPERATOR)
        govde = guvenlik.token_coz(t)
        assert govde["sub"] == "ali"
        assert govde["rol"] == "operator"

    def test_YENILEME_TOKENI_ERISIM_OLARAK_KULLANILAMIYOR(self) -> None:
        """⚠ En kritik test.

        `tip` alanı olmasaydı 7 günlük bir yenileme tokenı, 15 dakikalık
        erişim tokenı yerine kullanılabilirdi — yani çalınan bir tokenın
        zarar penceresi 15 dakikadan 7 güne çıkardı.
        """
        yenileme = guvenlik.token_uret("ali", guvenlik.Rol.VIEWER, yenileme=True)
        with pytest.raises(HTTPException) as e:
            guvenlik.token_coz(yenileme)
        assert e.value.status_code == 401

    def test_erisim_tokeni_yenileme_olarak_kullanilamiyor(self) -> None:
        erisim = guvenlik.token_uret("ali", guvenlik.Rol.VIEWER)
        with pytest.raises(HTTPException):
            guvenlik.token_coz(erisim, yenileme=True)

    def test_SURESI_DOLMUS_token_reddediliyor(self) -> None:
        ayarlar = get_settings()
        gecmis = int(time.time()) - 100
        t = jwt.encode(
            {"sub": "ali", "rol": "viewer", "tip": "erisim",
             "iat": gecmis - 10, "exp": gecmis},
            ayarlar.jwt_secret_key.get_secret_value(),
            algorithm=ayarlar.jwt_algorithm,
        )
        with pytest.raises(HTTPException) as e:
            guvenlik.token_coz(t)
        assert e.value.status_code == 401

    def test_BASKA_ANAHTARLA_imzalanan_token_reddediliyor(self) -> None:
        """İmza doğrulaması gerçekten yapılıyor mu."""
        t = jwt.encode(
            {"sub": "saldirgan", "rol": "admin", "tip": "erisim",
             "exp": int(time.time()) + 3600},
            "baska-bir-anahtar",
            algorithm="HS256",
        )
        with pytest.raises(HTTPException):
            guvenlik.token_coz(t)

    def test_ALG_NONE_saldirisi_calismiyor(self) -> None:
        """⚠ JWT'nin en bilinen açığı.

        `algorithms=` verilmezse kütüphane tokenın KENDİ başlığındaki
        algoritmaya güvenir; saldırgan `alg: none` yazıp imzasız token
        kabul ettirebilir. `token_coz` algoritmayı açıkça veriyor.
        """
        imzasiz = jwt.encode(
            {"sub": "saldirgan", "rol": "admin", "tip": "erisim",
             "exp": int(time.time()) + 3600},
            key="",
            algorithm="none",
        )
        with pytest.raises(HTTPException):
            guvenlik.token_coz(imzasiz)

    def test_ANAHTAR_YOKSA_ACIKCA_PATLIYOR(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """⚠ Rastgele anahtar ÜRETİLMİYOR.

        "Ayarlanmamışsa üret" davranışı cazip görünür ama iki felakete
        yol açar: her yeniden başlatmada tüm oturumlar düşer, ve daha
        kötüsü kimse anahtarı ayarlamayı hatırlamaz. Açıkça patlamak,
        sessizce güvensiz çalışmaktan iyidir.
        """
        from pydantic import SecretStr

        monkeypatch.setattr(get_settings(), "jwt_secret_key", SecretStr(""))
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            guvenlik.token_uret("ali", guvenlik.Rol.VIEWER)


# ══════════════════════════════════════════════════════════════
#  Roller
# ══════════════════════════════════════════════════════════════


class TestRoller:
    @pytest.mark.parametrize(
        ("sahip", "gereken", "gecmeli"),
        [
            (guvenlik.Rol.ADMIN, guvenlik.Rol.VIEWER, True),
            (guvenlik.Rol.ADMIN, guvenlik.Rol.OPERATOR, True),
            (guvenlik.Rol.ADMIN, guvenlik.Rol.ADMIN, True),
            (guvenlik.Rol.OPERATOR, guvenlik.Rol.VIEWER, True),
            (guvenlik.Rol.OPERATOR, guvenlik.Rol.OPERATOR, True),
            (guvenlik.Rol.OPERATOR, guvenlik.Rol.ADMIN, False),
            (guvenlik.Rol.VIEWER, guvenlik.Rol.VIEWER, True),
            (guvenlik.Rol.VIEWER, guvenlik.Rol.OPERATOR, False),
            (guvenlik.Rol.VIEWER, guvenlik.Rol.ADMIN, False),
        ],
    )
    def test_hiyerarsi(
        self, sahip: guvenlik.Rol, gereken: guvenlik.Rol, gecmeli: bool
    ) -> None:
        """Roller hiyerarşik: admin > operator > viewer.

        ⚠ Tablo TAM: 3×3 = 9 kombinasyonun hepsi yazılı. Yalnızca
        "beklenen" durumları test etmek, hiyerarşinin ters çevrildiği
        bir hatayı kaçırırdı.
        """
        import asyncio

        dogrula = guvenlik.rol_gerekli(gereken)
        kullanici = guvenlik.Kullanici(kullanici_adi="test", rol=sahip)
        if gecmeli:
            assert asyncio.run(dogrula(kullanici)) is kullanici
        else:
            with pytest.raises(HTTPException) as e:
                asyncio.run(dogrula(kullanici))
            # ⚠ 403, 401 DEĞİL: "kim olduğunu biliyorum ama bunu
            # yapamazsın". 401 dönseydi istemci sonsuz yeniden giriş
            # döngüsüne girerdi.
            assert e.value.status_code == 403
