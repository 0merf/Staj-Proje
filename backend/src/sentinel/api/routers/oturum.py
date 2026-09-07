"""Giriş / yenileme / çıkış uçları — PLAN.md §11.1.

⚠ HIZ SINIRI (G03) BU DOSYADA
Giriş ucu, kaba kuvvet saldırısının tek hedefi. Argon2 zaten deneme
başına ~50 ms dayatıyor ama bu tek başına yetmez: saldırgan paralel
deneyebilir. Kullanıcı adı + IP başına sayaç Valkey'de tutuluyor.

⚠ SAYAÇ NEDEN VALKEY'DE, SÜREÇ BELLEĞİNDE DEĞİL
Süreç belleğindeki sayaç yeniden başlatmada sıfırlanır ve saldırgan
sunucuyu yorup sayacı düşürebilir. Ayrıca birden çok API süreci
çalışırsa (üretimde çalışacak) her biri kendi sayacını tutardı.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from sentinel import metrics
from sentinel.api.guvenlik import (
    Kullanici,
    Rol,
    mevcut_kullanici,
    parola_dogru_mu,
    rol_gerekli,
    token_coz,
    token_uret,
)
from sentinel.bus.streams import connect
from sentinel.config import get_settings
from sentinel.db import kullanicilar as depo
from sentinel.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Kaba kuvvet sınırı: bu pencerede bu kadar BAŞARISIZ denemeden sonra
# kilit. ⚠ Başarılı giriş sayacı sıfırlıyor — meşru kullanıcı yanlış
# yazıp sonra doğru yazınca cezalandırılmamalı.
DENEME_SINIRI = 8
PENCERE_S = 300


def _istemci_ip(request: Request) -> str:
    """İstemci IP'si.

    ⚠ `X-Forwarded-For` GÜVENİLMİYOR. İstemci onu istediği gibi
    yazabilir; ters vekil arkasında çalışırken vekilin ayarladığı
    değere güvenmek gerekir ve o güven açıkça yapılandırılmalıdır
    (Caddy devreye girince, PLAN §10). Şimdilik doğrudan bağlantı
    adresi kullanılıyor — yanlış olabilir ama YANILTICI değil.
    """
    return request.client.host if request.client else "bilinmiyor"


def _anahtar(kullanici_adi: str, ip: str) -> str:
    return f"giris_deneme:{kullanici_adi}:{ip}"


def _kilitli_mi(kullanici_adi: str, ip: str) -> bool:
    try:
        deger = connect().get(_anahtar(kullanici_adi, ip))
        return int(deger) >= DENEME_SINIRI if deger else False
    except Exception:
        # ⚠ Valkey erişilemezse GİRİŞ ENGELLENMİYOR. Hız sınırı bir
        # ek koruma; onu zorunlu ön koşula çevirmek, Valkey arızasını
        # tüm sistemin kimlik doğrulama arızasına dönüştürürdü.
        # Argon2'nin deneme başına maliyeti hâlâ devrede.
        log.warning("hiz_siniri_okunamadi")
        return False


def _deneme_say(kullanici_adi: str, ip: str, *, sifirla: bool = False) -> None:
    try:
        istemci = connect()
        anahtar = _anahtar(kullanici_adi, ip)
        if sifirla:
            istemci.delete(anahtar)
            return
        istemci.incr(anahtar)
        istemci.expire(anahtar, PENCERE_S)
    except Exception:
        log.warning("hiz_siniri_yazilamadi")


class GirisIstegi(BaseModel):
    kullanici_adi: str = Field(min_length=1, max_length=64)
    parola: str = Field(min_length=1, max_length=256)


class YenilemeIstegi(BaseModel):
    yenileme_tokeni: str


def _cerez_koy(yanit: Response, token: str) -> None:
    """Erişim tokenını çereze koyar.

    ⚠ `httponly=True`: JavaScript okuyamıyor, yani XSS ile token
    çalınamıyor. `samesite=lax`: başka sitelerden gelen isteklerde
    gönderilmiyor (CSRF koruması). `secure` yalnızca HTTPS'te —
    geliştirmede `127.0.0.1` üzerinden HTTP kullanılıyor ve `secure`
    açıkken tarayıcı çerezi hiç göndermezdi.
    """
    ayarlar = get_settings()
    yanit.set_cookie(
        "sentinel_token",
        token,
        max_age=ayarlar.access_token_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=ayarlar.sentinel_env == "production",
        path="/",
    )


@router.post("/login")
async def giris(istek: GirisIstegi, request: Request, yanit: Response) -> dict[str, Any]:
    """Kullanıcı adı + parola → erişim ve yenileme tokenı."""
    ip = _istemci_ip(request)

    if _kilitli_mi(istek.kullanici_adi, ip):
        # ⚠ G20 kilidi ÇALIŞIYORDU ama GÖRÜNMÜYORDU (03.09.2026 eklendi).
        # Kilit Gün 16'da yazıldı; kaç kez devreye girdiğini gösteren
        # hiçbir metrik yoktu. G28 ("başarısız giriş serisi uyarısı")
        # ve PLAN §13.2'nin güvenlik panosu ikisi de bu sayaca
        # dayanıyor. Gözlemlenemeyen bir savunma, ilk sessiz arızasına
        # kadar çalışır.
        metrics.auth_failures.labels(reason="kilitli").inc()
        await depo.denetim_yaz(
            "giris_kilitli", kullanici_adi=istek.kullanici_adi, ip=ip, basarili=False
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"çok fazla başarısız deneme, {PENCERE_S // 60} dakika bekleyin",
        )

    kayit = await depo.kullanici_al(istek.kullanici_adi)

    # ⚠ KULLANICI YOKSA DA PAROLA DOĞRULANIYOR — zamanlama saldırısı
    # Var olmayan bir kullanıcı için hemen dönmek, cevap süresinden
    # "bu kullanıcı adı var mı" bilgisini sızdırır. Sahte bir hash'e
    # karşı doğrulama yaparak iki yolun süresi eşitleniyor.
    if kayit is None:
        parola_dogru_mu(
            "$argon2id$v=19$m=65536,t=3,p=4$" + "A" * 22 + "$" + "B" * 43,
            istek.parola,
        )
        gecerli = False
    else:
        gecerli = kayit.aktif and parola_dogru_mu(kayit.parola_hash, istek.parola)

    if not gecerli:
        _deneme_say(istek.kullanici_adi, ip)
        metrics.auth_failures.labels(reason="kimlik_hatali").inc()
        await depo.denetim_yaz(
            "giris", kullanici_adi=istek.kullanici_adi, ip=ip, basarili=False
        )
        # ⚠ TEK BİR HATA MESAJI. "kullanıcı yok" ile "parola yanlış"
        # ayrımı, saldırgana geçerli kullanıcı adlarını sayma imkânı
        # verir (kullanıcı numaralandırma).
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "kullanıcı adı ya da parola hatalı"
        )

    assert kayit is not None
    _deneme_say(istek.kullanici_adi, ip, sifirla=True)
    await depo.giris_isaretle(kayit.kullanici_adi)
    await depo.denetim_yaz("giris", kullanici_adi=kayit.kullanici_adi, ip=ip)

    rol = Rol(kayit.rol)
    erisim = token_uret(kayit.kullanici_adi, rol)
    _cerez_koy(yanit, erisim)
    return {
        "erisim_tokeni": erisim,
        "yenileme_tokeni": token_uret(
            kayit.kullanici_adi, rol, yenileme=True, token_surumu=kayit.token_surumu
        ),
        "tip": "Bearer",
        "kullanici_adi": kayit.kullanici_adi,
        "rol": rol.value,
        "gecerlilik_sn": get_settings().access_token_expire_minutes * 60,
    }


@router.post("/refresh")
async def yenile(istek: YenilemeIstegi, yanit: Response) -> dict[str, Any]:
    """Yenileme tokenı → yeni erişim tokenı.

    ⚠ TOKEN SÜRÜMÜ KONTROL EDİLİYOR. JWT kendi kendini doğruladığı için
    imzası geçerli olan eski bir yenileme tokenı, parola değiştirilmiş
    olsa bile çalışırdı. Veritabanındaki sayaçla karşılaştırmak,
    "tüm oturumları kapat" işlevini mümkün kılan tek mekanizma.
    """
    govde = token_coz(istek.yenileme_tokeni, yenileme=True)
    kullanici_adi = str(govde.get("sub", ""))
    kayit = await depo.kullanici_al(kullanici_adi)
    if kayit is None or not kayit.aktif:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "geçersiz oturum")
    if int(govde.get("ver", -1)) != kayit.token_surumu:
        metrics.auth_failures.labels(reason="token_surumu_eski").inc()
        await depo.denetim_yaz(
            "yenileme_reddedildi", kullanici_adi=kullanici_adi, basarili=False,
            ayrinti={"sebep": "token surumu eski"},
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "oturum iptal edilmiş")

    rol = Rol(kayit.rol)
    erisim = token_uret(kayit.kullanici_adi, rol)
    _cerez_koy(yanit, erisim)
    return {
        "erisim_tokeni": erisim,
        "tip": "Bearer",
        "gecerlilik_sn": get_settings().access_token_expire_minutes * 60,
    }


@router.post("/logout")
async def cikis(
    yanit: Response,
    kullanici: Annotated[Kullanici, Depends(mevcut_kullanici)],
) -> dict[str, str]:
    """Çerezi siler.

    ⚠ DÜRÜST İSİMLENDİRME: bu bir İPTAL değil. Elde tutulan bir Bearer
    tokenı süresi dolana kadar (en fazla 15 dakika) hâlâ geçerli.
    Gerçek iptal için `jti` kara listesi gerekiyor ve erişim tokenının
    kısa ömrü karşılığında bilinçli olarak yapılmadı (guvenlik.py).
    Yenileme tokenları için iptal VAR: `/auth/oturumlari-kapat`.
    """
    yanit.delete_cookie("sentinel_token", path="/")
    await depo.denetim_yaz("cikis", kullanici_adi=kullanici.kullanici_adi)
    return {"durum": "çerez silindi"}


@router.get("/ben")
async def ben(kullanici: Annotated[Kullanici, Depends(mevcut_kullanici)]) -> dict[str, str]:
    """Panelin 'kim olarak girdim' sorusu."""
    return {"kullanici_adi": kullanici.kullanici_adi, "rol": kullanici.rol.value}


@router.get("/denetim")
async def denetim(
    _: Annotated[Kullanici, Depends(rol_gerekli(Rol.ADMIN))],
    limit: int = 100,
) -> dict[str, Any]:
    """Denetim izi — YALNIZCA admin.

    ⚠ Bu uç, "kim hangi kamerayı izledi" sorusunun cevabını taşıyor ve
    kendisi de hassas: kimlerin ne zaman çalıştığını gösteriyor.
    Operatörlere kapalı olması bilinçli.
    """
    satirlar = await depo.denetim_oku(limit)
    return {
        "adet": len(satirlar),
        "kayitlar": [
            {
                "ts": s["ts"].timestamp(),
                "kullanici": s["kullanici_adi"],
                "eylem": s["eylem"],
                "hedef": s["hedef"],
                "ip": s["ip"],
                "basarili": s["basarili"],
                "ayrinti": s["ayrinti"],
            }
            for s in satirlar
        ],
    }


__all__ = ["router"]
