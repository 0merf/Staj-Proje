"""Kimlik doğrulama ve yetkilendirme — PLAN.md §11.1 (G01-G05).

⚠ NEDEN BUGÜNE KADAR YOKTU VE NEDEN ARTIK VAR
---------------------------------------------
`PLAN.md` güvenliği **Öncelik-1** ilan ediyor ve `config.py` JWT
ayarlarını Gün 1'den beri taşıyordu — ama tek satır kod yoktu. API
tamamen açıktı: kamera listesi, olay geçmişi, webcam açma/kapatma,
hepsi kimlik doğrulamasız.

Tek hafifletici koşul her şeyin `127.0.0.1`'e bağlı olması. Bu bir
savunma değil bir **tesadüf**: Caddy ters vekili devreye girdiği an
(PLAN §10) API dış ağa açılıyor ve o gün "sonra ekleriz" demiş olmak
üç kat pahalıya patlıyor (çalışma ilkesi 3).

Kararlar
--------
**Parola hash'i: Argon2id** (G01). MD5/SHA-256 değil — onlar HIZLI
olmak için tasarlandı ve parola hash'inde hız saldırganın işine yarar.
Argon2id hem CPU hem BELLEK maliyeti dayatıyor, yani GPU'yla paralel
kırma avantajını da siliyor. 2015 Password Hashing Competition
kazananı ve OWASP'ın birinci önerisi.

**Token: JWT, kısa ömürlü erişim + uzun ömürlü yenileme** (G02).
  · erişim  15 dakika — çalınırsa zarar penceresi dar
  · yenileme 7 gün   — kullanıcı her 15 dakikada giriş yapmasın

⚠ JWT İPTAL EDİLEMEZ — bilinen kısıt, dürüstçe raporlanacak
Kendi kendini doğrulayan bir token, süresi dolana kadar geçerlidir;
"çıkış yap" gerçek bir iptal değildir. Doğru çözüm bir iptal listesi
(Valkey'de `jti` kara listesi) ve bu, erişim tokenının 15 dakikalık
ömrüyle sınırlı bir risk karşılığında **bilinçli olarak** yapılmadı.
Yenileme tokenı için iptal gerekliydi ve yapıldı: veritabanındaki
`token_surumu` artırılınca o kullanıcının tüm yenileme tokenları
geçersizleşiyor.

**Roller** (G05): `admin` > `operator` > `viewer`. Hiyerarşik, çünkü
"operatörün yapabildiği her şeyi admin de yapabilir" doğal bir kural
ve rol başına ayrı izin listesi tutmak bu küçük sistemde
kazandırdığından fazla makine getirirdi.

⚠ SALT OKUNUR ile YAZAN uçlar AYRILIYOR
Kamera listesi ve olay geçmişi `viewer`'a açık; webcam açmak
`operator` istiyor. Mahremiyet açısından fark büyük: biri geçmişe
bakmak, diğeri YENİ bir kamera açmak.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sentinel.config import get_settings
from sentinel.logging import get_logger

log = get_logger(__name__)

# ⚠ Varsayılan parametreler OWASP'ın önerdiği taban değerlerin üstünde
# tutuluyor (argon2-cffi varsayılanı: 64 MiB, 3 tur). Bu makinede
# ölçülen doğrulama süresi ~50 ms — kullanıcı için görünmez, saldırgan
# için kaba kuvvet denemesi başına 50 ms.
_hasher = PasswordHasher()

_bearer = HTTPBearer(auto_error=False)


class Rol(StrEnum):
    """Yetki seviyeleri — hiyerarşik."""

    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


# Büyükten küçüğe yetki sırası. `_YETKI[rol] >= _YETKI[gereken]` testi
# hiyerarşiyi tek satırda uyguluyor.
_YETKI = {Rol.VIEWER: 0, Rol.OPERATOR: 1, Rol.ADMIN: 2}


@dataclass(frozen=True, slots=True)
class Kullanici:
    """Doğrulanmış istek sahibi."""

    kullanici_adi: str
    rol: Rol


def parola_hashle(parola: str) -> str:
    """Argon2id ile hash üretir. Tuz kütüphane tarafından üretiliyor."""
    return _hasher.hash(parola)


def parola_dogru_mu(hash_degeri: str, parola: str) -> bool:
    """Parolayı doğrular.

    ⚠ İSTİSNA SIZDIRMIYOR. `VerifyMismatchError` ile `InvalidHashError`
    farklı sebeplerdir (yanlış parola vs bozuk kayıt) ama çağırana
    ikisi de `False` dönüyor: hata türünü dışarı vermek, saldırgana
    "bu kullanıcı var ama hash'i bozuk" gibi bilgiler sızdırır.
    """
    try:
        return _hasher.verify(hash_degeri, parola)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _anahtar() -> str:
    """JWT imza anahtarı — YOKSA HATA.

    ⚠ Varsayılan bir anahtar ÜRETİLMİYOR. "Ayarlanmamışsa rastgele
    üret" davranışı cazip görünür ama iki felakete yol açar: her
    yeniden başlatmada tüm oturumlar düşer, ve daha kötüsü, kimse
    anahtarı ayarlamayı hatırlamaz. Açıkça patlamak, sessizce güvensiz
    çalışmaktan iyidir.
    """
    anahtar = get_settings().jwt_secret_key.get_secret_value()
    if not anahtar:
        raise RuntimeError(
            "JWT_SECRET_KEY ayarlanmamış. .env dosyasına güçlü bir değer koyun: "
            'python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    return anahtar


def token_uret(
    kullanici_adi: str, rol: Rol, *, yenileme: bool = False, token_surumu: int = 0
) -> str:
    """Erişim ya da yenileme tokenı üretir.

    ⚠ `tip` alanı ZORUNLU. Olmasaydı bir yenileme tokenı erişim tokenı
    gibi kullanılabilirdi — yani 15 dakikalık pencere 7 güne çıkardı.
    Doğrulama tarafında tip açıkça karşılaştırılıyor.
    """
    ayarlar = get_settings()
    simdi = int(time.time())
    omur = (
        ayarlar.refresh_token_expire_days * 86400
        if yenileme
        else ayarlar.access_token_expire_minutes * 60
    )
    govde: dict[str, Any] = {
        "sub": kullanici_adi,
        "rol": rol.value,
        "tip": "yenileme" if yenileme else "erisim",
        "iat": simdi,
        "exp": simdi + omur,
        # ⚠ `jti`: ileride iptal listesi kurulacaksa gereken benzersiz
        # kimlik. Şimdi kullanılmıyor ama token biçimini sonradan
        # değiştirmek, dolaşımdaki tüm tokenları geçersiz kılmak demek.
        "jti": uuid.uuid4().hex,
    }
    if yenileme:
        # Kullanıcının token sürümü — parola değişince ya da "tüm
        # oturumları kapat" denince artırılıyor ve eski yenileme
        # tokenları geçersizleşiyor.
        govde["ver"] = token_surumu
    return jwt.encode(govde, _anahtar(), algorithm=ayarlar.jwt_algorithm)


def token_coz(token: str, *, yenileme: bool = False) -> dict[str, Any]:
    """Tokenı doğrular ve gövdesini döndürür. Geçersizse 401.

    ⚠ `algorithms` AÇIKÇA veriliyor. Verilmezse kütüphane tokenın kendi
    başlığındaki algoritmaya güvenir ve saldırgan `alg: none` yazarak
    imzasız token kabul ettirebilir — JWT'nin en bilinen açığı.
    """
    ayarlar = get_settings()
    try:
        govde: dict[str, Any] = jwt.decode(
            token, _anahtar(), algorithms=[ayarlar.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "oturum süresi doldu",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.InvalidTokenError:
        # ⚠ Sebep ayrıntısı VERİLMİYOR: "imza geçersiz" ile "gövde
        # bozuk" arasındaki fark saldırgana yol gösterir.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "geçersiz oturum",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    beklenen = "yenileme" if yenileme else "erisim"
    if govde.get("tip") != beklenen:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "geçersiz oturum")
    return govde


async def mevcut_kullanici(
    request: Request,
    kimlik: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> Kullanici:
    """İsteği doğrular ve kullanıcıyı döndürür.

    ⚠ Token iki yerden okunuyor: `Authorization: Bearer` başlığı ve
    `sentinel_token` çerezi. Çerez desteği tarayıcı paneli için —
    `<video>` ve WebSocket bağlantılarına özel başlık eklemek
    tarayıcıda mümkün değil.
    """
    ham = kimlik.credentials if kimlik else request.cookies.get("sentinel_token")
    if not ham:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "kimlik doğrulaması gerekli",
            headers={"WWW-Authenticate": "Bearer"},
        )
    govde = token_coz(ham)
    try:
        rol = Rol(govde.get("rol", ""))
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "geçersiz oturum") from None
    return Kullanici(kullanici_adi=str(govde.get("sub", "")), rol=rol)


def rol_gerekli(en_az: Rol) -> Any:
    """Belirli bir rolü (ya da üstünü) zorunlu kılan bağımlılık üretir.

    Kullanımı:
        @router.post("/webcam/start")
        async def baslat(u: Kullanici = Depends(rol_gerekli(Rol.OPERATOR))): ...

    ⚠ 403, 401 DEĞİL. İkisi farklı şey söyler: 401 "kim olduğunu
    bilmiyorum", 403 "kim olduğunu biliyorum ama bunu yapamazsın".
    Karıştırmak istemciyi sonsuz yeniden giriş döngüsüne sokar.
    """

    async def dogrula(
        kullanici: Annotated[Kullanici, Depends(mevcut_kullanici)],
    ) -> Kullanici:
        if _YETKI[kullanici.rol] < _YETKI[en_az]:
            log.warning(
                "yetkisiz_erisim_denemesi",
                kullanici=kullanici.kullanici_adi,
                rol=kullanici.rol.value,
                gereken=en_az.value,
            )
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"bu işlem için {en_az.value} yetkisi gerekli"
            )
        return kullanici

    return dogrula


__all__ = [
    "Kullanici",
    "Rol",
    "mevcut_kullanici",
    "parola_dogru_mu",
    "parola_hashle",
    "rol_gerekli",
    "token_coz",
    "token_uret",
]
