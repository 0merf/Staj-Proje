"""Kullanıcı tablosu ve denetim izi — PLAN.md §11.1 (G01, G05, G11).

⚠ NEDEN DENETİM İZİ (AUDIT LOG) AYRI BİR TABLO
Bir gözetim sistemi insanları izliyor. "Kim, ne zaman, hangi kamerayı
izledi" sorusunun cevabı olmadan sistemin kendisi denetlenemez hâle
gelir — ve denetlenemeyen bir gözetim sistemi, izlediği kişilerden çok
onu işletenlere ayrıcalık tanır (PLAN §12.3).

Bu yüzden denetim izi uygulama günlüğüne değil VERİTABANINA yazılıyor:
günlük dosyası döner, silinir, biçimi değişir; tablo sorgulanabilir ve
saklama politikası uygulanabilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from sentinel.db.engine import motor
from sentinel.logging import get_logger

log = get_logger(__name__)

SEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS kullanicilar (
        kullanici_adi TEXT PRIMARY KEY,
        parola_hash   TEXT        NOT NULL,
        rol           TEXT        NOT NULL DEFAULT 'viewer',
        aktif         BOOLEAN     NOT NULL DEFAULT TRUE,
        -- ⚠ Yenileme tokenlarını topluca iptal etmenin yolu.
        -- Parola değişince ya da "tüm oturumları kapat" denince
        -- artırılıyor; eski yenileme tokenları geçersizleşiyor.
        -- JWT kendi kendini doğruladığı için iptal ancak böyle bir
        -- sunucu tarafı sayaçla mümkün.
        token_surumu  INTEGER     NOT NULL DEFAULT 0,
        olusturuldu   TIMESTAMPTZ NOT NULL DEFAULT now(),
        son_giris     TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS denetim_izi (
        ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
        kullanici_adi TEXT,
        eylem         TEXT        NOT NULL,
        hedef         TEXT,
        -- ⚠ IP saklanıyor çünkü "kim izledi" sorusunun cevabı yalnızca
        -- kullanıcı adı değil. Ama bu da kişisel veri: saklama süresi
        -- olay tablosuyla aynı (KVKK, PLAN §12.4).
        ip            TEXT,
        basarili      BOOLEAN     NOT NULL DEFAULT TRUE,
        ayrinti       JSONB       NOT NULL DEFAULT '{}'::jsonb
    )
    """,
    "CREATE INDEX IF NOT EXISTS denetim_ts ON denetim_izi (ts DESC)",
    "CREATE INDEX IF NOT EXISTS denetim_kullanici ON denetim_izi (kullanici_adi, ts DESC)",
)


@dataclass(frozen=True, slots=True)
class KullaniciKaydi:
    kullanici_adi: str
    parola_hash: str
    rol: str
    aktif: bool
    token_surumu: int


async def semayi_kur(baglanti: AsyncConnection) -> None:
    for ifade in SEMA:
        await baglanti.execute(text(ifade))


async def kullanici_al(kullanici_adi: str) -> KullaniciKaydi | None:
    async with motor().connect() as b:
        sonuc = await b.execute(
            text(
                "SELECT kullanici_adi, parola_hash, rol, aktif, token_surumu "
                "FROM kullanicilar WHERE kullanici_adi = :ad"
            ),
            {"ad": kullanici_adi},
        )
        satir = sonuc.first()
    if satir is None:
        return None
    return KullaniciKaydi(
        kullanici_adi=satir[0],
        parola_hash=satir[1],
        rol=satir[2],
        aktif=bool(satir[3]),
        token_surumu=int(satir[4]),
    )


async def kullanici_ekle(
    kullanici_adi: str, parola_hash: str, rol: str = "viewer"
) -> None:
    """Kullanıcı ekler ya da varsa parolasını/rolünü günceller.

    ⚠ `ON CONFLICT ... DO UPDATE`: bu fonksiyon hem kurulum betiğinden
    hem yönetim ucundan çağrılıyor ve ikisinde de "varsa güncelle"
    doğru davranış. `token_surumu` de artırılıyor — parola değiştiyse
    eski oturumlar düşmeli.
    """
    async with motor().begin() as b:
        await b.execute(
            text("""
                INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol)
                VALUES (:ad, :hash, :rol)
                ON CONFLICT (kullanici_adi) DO UPDATE
                SET parola_hash  = EXCLUDED.parola_hash,
                    rol          = EXCLUDED.rol,
                    token_surumu = kullanicilar.token_surumu + 1
            """),
            {"ad": kullanici_adi, "hash": parola_hash, "rol": rol},
        )


async def giris_isaretle(kullanici_adi: str) -> None:
    async with motor().begin() as b:
        await b.execute(
            text("UPDATE kullanicilar SET son_giris = now() WHERE kullanici_adi = :ad"),
            {"ad": kullanici_adi},
        )


async def denetim_yaz(
    eylem: str,
    *,
    kullanici_adi: str | None = None,
    hedef: str | None = None,
    ip: str | None = None,
    basarili: bool = True,
    ayrinti: dict[str, Any] | None = None,
) -> None:
    """Denetim izine bir satır yazar.

    ⚠ İSTİSNA FIRLATMIYOR. Denetim yazımı başarısız diye asıl isteğin
    reddedilmesi, kullanılabilirliği güvenliğe feda etmek olurdu ve
    saldırgana kolay bir hizmet dışı bırakma yolu verirdi (veritabanını
    yorup girişleri engellemek). Başarısızlık loglanıyor.
    """
    import json

    try:
        async with motor().begin() as b:
            await b.execute(
                text("""
                    INSERT INTO denetim_izi
                        (kullanici_adi, eylem, hedef, ip, basarili, ayrinti)
                    VALUES
                        (:ad, :eylem, :hedef, :ip, :basarili,
                         CAST(:ayrinti AS jsonb))
                """),
                {
                    "ad": kullanici_adi,
                    "eylem": eylem,
                    "hedef": hedef,
                    "ip": ip,
                    "basarili": basarili,
                    "ayrinti": json.dumps(ayrinti or {}, ensure_ascii=False),
                },
            )
    except Exception as exc:
        log.error("denetim_yazilamadi", eylem=eylem, error=f"{type(exc).__name__}: {exc}")


async def denetim_oku(limit: int = 100) -> list[dict[str, Any]]:
    async with motor().connect() as b:
        sonuc = await b.execute(
            text(
                "SELECT ts, kullanici_adi, eylem, hedef, ip, basarili, ayrinti "
                "FROM denetim_izi ORDER BY ts DESC LIMIT :limit"
            ),
            {"limit": max(1, min(limit, 1000))},
        )
        return [dict(s._mapping) for s in sonuc]


__all__ = [
    "KullaniciKaydi",
    "denetim_oku",
    "denetim_yaz",
    "giris_isaretle",
    "kullanici_al",
    "kullanici_ekle",
    "semayi_kur",
]
