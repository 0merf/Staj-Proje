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

# ══════════════════════════════════════════════════════════════
#  DENETİM İZİ SADECE-EKLEME (append-only)
# ══════════════════════════════════════════════════════════════
#
# ⚠ 03.09.2026 — PLAN §12.1 BUNU SÖZ VERİYORDU, KOD YAPMIYORDU
# PLAN'ın KVKK bölümü şunu yazıyor: *"Denetim kaydı ... sadece-ekleme,
# DB trigger ile UPDATE/DELETE engellenir."* Tablo vardı, trigger yoktu.
#
# ⚠ Neden bu bir detay değil: denetim izinin TEK değeri değiştirilemez
# olmasıdır. Silinebilen bir denetim kaydı, kötü niyetli bir yöneticiye
# karşı hiçbir şey ifade etmez — ve denetim izinin var oluş sebebi tam
# olarak yetkili birinin yetkisini kötüye kullanmasıdır. Yetkisiz
# kişiye karşı zaten RBAC var.
#
# ⚠ Bu koruma VERİTABANI seviyesinde, uygulama seviyesinde değil.
# Uygulama katmanında "UPDATE yazmayalım" demek bir disiplindir;
# trigger bir MEKANİZMADIR. Aradaki fark, psql'e doğrudan bağlanan
# birinin ne yapabildiğidir.
#
# ⚠ DÜRÜST SINIR: veritabanının SAHİBİ bu trigger'ı düşürebilir
# (`DROP TRIGGER`). Gerçek değişmezlik ayrı bir sunucuya yazmak ya da
# WORM depolama ister; bu kurulumda yok ve raporda böyle yazılacak.
# Trigger, kazayı ve sıradan kötüye kullanımı engelliyor; kararlı bir
# saldırganı değil.
DENETIM_KORUMASI: tuple[str, ...] = (
    """
    CREATE OR REPLACE FUNCTION denetim_degistirilemez()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION
            'denetim_izi sadece-ekleme bir tablodur: % engellendi',
            TG_OP;
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS denetim_no_update ON denetim_izi",
    """
    CREATE TRIGGER denetim_no_update
        BEFORE UPDATE OR DELETE ON denetim_izi
        FOR EACH ROW EXECUTE FUNCTION denetim_degistirilemez()
    """,
    # ⚠ TRUNCATE AYRI BİR TETİKLEYİCİ İSTİYOR — ve bu kolayca atlanır.
    # `TRUNCATE` satır bazlı değil ifade bazlı çalışır; yukarıdaki
    # `FOR EACH ROW` tetikleyicisi onu HİÇ görmez. Yani yalnızca
    # UPDATE/DELETE engellenseydi, tabloyu tek komutla boşaltmak
    # serbest kalırdı — korumanın adı doğru, kapsamı yanlış olurdu.
    "DROP TRIGGER IF EXISTS denetim_no_truncate ON denetim_izi",
    """
    CREATE TRIGGER denetim_no_truncate
        BEFORE TRUNCATE ON denetim_izi
        FOR EACH STATEMENT EXECUTE FUNCTION denetim_degistirilemez()
    """,
)


@dataclass(frozen=True, slots=True)
class KullaniciKaydi:
    kullanici_adi: str
    parola_hash: str
    rol: str
    aktif: bool
    token_surumu: int


async def semayi_kur(baglanti: AsyncConnection) -> None:
    """Kullanıcı ve denetim tablolarını kurar. Her açılışta çağrılır.

    ⚠ İdempotent olmak ZORUNDA: elle migration gerektiren bir sistem,
    bir bileşen yeniden başladığında sessizce çalışmaz duruma gelir.
    """
    for ifade in SEMA:
        await baglanti.execute(text(ifade))

    # ⚠ KORUMA AYRI VE HATASI YUTULUYOR — ama SESSİZCE DEĞİL
    # Trigger kurulamazsa (yetki yok, plpgsql eklentisi yok) sistem
    # yine çalışmalı: denetim yazımı devam eder, yalnızca
    # değiştirilemezlik garantisi düşer. Ama bu bir GÜVENLİK
    # bozulmasıdır ve WARNING seviyesinde, etkisiyle birlikte
    # loglanıyor — "denetim izi korumasız çalışıyor" cümlesi loga
    # düşmeden bu duruma girilmiyor.
    try:
        for ifade in DENETIM_KORUMASI:
            await baglanti.execute(text(ifade))
    except Exception as exc:
        log.warning(
            "denetim_korumasi_kurulamadi",
            error=f"{type(exc).__name__}: {exc}",
            etki="denetim izi yazılıyor ama UPDATE/DELETE'e karşı KORUMASIZ",
        )


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
