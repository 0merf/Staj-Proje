"""Olay tablosu ve TimescaleDB kurulumu — PLAN.md §8.

Neden bu dosya var
------------------
26.08.2026'ya kadar alarmlar **hiçbir yere kaydedilmiyordu.** Analytics
worker bir olay üretiyor, Valkey akışına yazıyor, panel açıksa
gösteriyor — panel kapalıysa olay hiç olmamış gibi kayboluyordu.

Bir gözetim sisteminde bu kabul edilemez: operatörün asıl sorusu
"şu an ne oluyor" değil, **"dün gece 03:00'te ne oldu"**dur.

Neden TimescaleDB, neden düz PostgreSQL değil
---------------------------------------------
Bu tablonun üç özelliği var ve üçü de zaman serisi:

1. **Yalnızca ekleme yapılıyor**, güncelleme yok. Olaylar sonradan
   değişmez.
2. **Sorgular hep zaman aralıklı.** "Son 24 saatte cam-09'da neler
   oldu" — hiçbir zaman "tüm tarihte" sorulmuyor.
3. **Eski veri değerini yitiriyor** ama ÖZETİ yitirmiyor. Üç ay
   önceki tek bir alarmın ayrıntısı gereksiz; "üç ay önce günde kaç
   alarm vardı" değerli.

TimescaleDB üçü için de hazır makine veriyor:

    hypertable          → zaman dilimlerine (chunk) otomatik bölme;
                          eski dilimler sorguda hiç açılmıyor
    sürekli toplulaştırma → saatlik özet arka planda güncelleniyor
    saklama politikası   → eski ham satırlar otomatik siliniyor,
                          özet kalıyor

⚠ SÜREKLİ TOPLULAŞTIRMA K7'NİN TA KENDİSİ
K7 kriteri "kamera-saat başına yanlış alarm ≤3" diyor ve bugüne kadar
her ölçümde elle bir betik yazıp Valkey akışını dinledik. `olay_saatlik`
görünümü tam olarak bu sayıyı **sürekli** üretiyor: kriter artık bir
ölçüm koşusunun değil, sistemin normal çıktısının parçası.

⚠ NEDEN AYRI BİR "kanit" JSONB SÜTUNU
Her anomali türünün kanıtı farklı: düşmede en-boy oranı ve eğim,
saldırganlıkta bileşen skorları, Katman A'da sigma sapması. Bunları
ayrı sütunlara açmak, her yeni kural için şema değişikliği demekti.
JSONB, alarmın NEDEN verildiğini kaybetmeden şemayı sabit tutuyor —
ve operatöre gösterilen açıklama da buradan geliyor.

⚠ NEDEN ALEMBIC DEĞİL DE DÜZ SQL
Alembic bağımlılığı kurulu ama tek tablolu bir şema için otomatik
revizyon üretimi, kazandırdığından fazla makine getiriyor. Daha
önemlisi: hypertable ve sürekli toplulaştırma Alembic'in bilmediği
TimescaleDB çağrıları; hepsi elle SQL olarak yazılacaktı zaten.
Şema büyürse Alembic'e geçiş açık bir iş.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from sentinel.logging import get_logger

log = get_logger(__name__)

# Ham olay satırları bu süre sonra siliniyor; saatlik özet kalıyor.
# ⚠ Staj/demo için 30 gün. Gerçek bir kurulumda bu sayı hukuki
# saklama yükümlülüğüne göre belirlenir (PLAN §12.4 KVKK notu):
# gözetim kayıtları için tipik sınır 30-60 gün ve "gerektiğinden uzun
# saklamamak" bir yükümlülük, tercih değil.
SAKLAMA_GUN = 30

# Hypertable dilim aralığı. Küçük dilim = çok dosya, büyük dilim =
# sorguda gereksiz veri okuma. Günde ~10 bin olay beklenen bir sistemde
# 1 gün makul.
DILIM_ARALIGI = "1 day"

# ⚠ İFADELER AYRI AYRI TUTULUYOR, TEK METİN + `split(";")` DEĞİL
#
# İlk sürüm şemayı tek bir metin olarak yazıp `;` ile bölüyordu ve
# `syntax error at end of input` veriyordu. Sebep: SQL YORUMUNUN İÇİNDE
# noktalı virgül vardı ("...daha az güvenilirdir; operatör bunu
# görmeli"). Naif bölme, ifadeyi yorumun ortasından kesti.
#
# Genel ders: SQL'i ayırıcıya bakarak bölmek, dizeleri ve yorumları
# tanımayan bir ayrıştırıcı yazmaktır. Ayrı ayrı tutmak hem doğru hem
# okunaklı — her ifade kendi gerekçesiyle yan yana duruyor.
SEMA: tuple[str, ...] = (
    # Olay tablosu.
    #   kanit  : alarmın NEDEN verildiği (JSONB). Bu sütun boşsa alarm
    #            bir iddiadır, doluysa bir gözlemdir. Türden türe
    #            değiştiği için ayrı sütunlara açılmadı — her yeni kural
    #            şema değişikliği gerektirirdi.
    #   tamlik : özellik penceresinin doluluğu (0-1). Düşük tamlıklı bir
    #            alarm yanlış değildir ama daha az güvenilirdir ve
    #            operatör bunu görmelidir.
    """
    CREATE TABLE IF NOT EXISTS olaylar (
        ts           TIMESTAMPTZ  NOT NULL,
        camera       TEXT         NOT NULL,
        tur          TEXT         NOT NULL,
        ciddiyet     TEXT         NOT NULL,
        skor         REAL         NOT NULL,
        track_id     BIGINT,
        kanit        JSONB        NOT NULL DEFAULT '{}'::jsonb,
        tamlik       REAL,
        karsi_taraf  BIGINT,
        klip_anahtar TEXT
    )
    """,
    # ⚠ Hypertable'a çevirme İDEMPOTENT olmak zorunda: bu fonksiyon her
    # açılışta çağrılıyor ve ikinci çağrıda sessizce geçmeli.
    """
    SELECT create_hypertable(
        'olaylar', 'ts',
        chunk_time_interval => INTERVAL '{dilim}',
        if_not_exists => TRUE
    )
    """,
    # Operatörün gerçek sorgusu: "şu kamerada, şu aralıkta, ne oldu".
    # ⚠ Sütun sırası önemli: eşitlik (camera) önce, aralık (ts) sonra.
    # Aralık koşulu başta olsaydı eşitlik kısmı indeksten yararlanamazdı.
    "CREATE INDEX IF NOT EXISTS olaylar_kamera_ts ON olaylar (camera, ts DESC)",
    "CREATE INDEX IF NOT EXISTS olaylar_tur_ts ON olaylar (tur, ts DESC)",
)

# ⚠ K7 KRİTERİ ARTIK SÜREKLİ ÖLÇÜLÜYOR
# Bu görünüm arka planda güncelleniyor; "kamera-saat başına alarm"
# sayısı elle betik koşmadan sorgulanabiliyor.
SUREKLI_TOPLULASTIRMA = """
CREATE MATERIALIZED VIEW IF NOT EXISTS olay_saatlik
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
    time_bucket('1 hour', ts) AS saat,
    camera,
    tur,
    ciddiyet,
    count(*)     AS adet,
    avg(skor)    AS ort_skor,
    max(skor)    AS azami_skor
FROM olaylar
GROUP BY saat, camera, tur, ciddiyet
WITH NO DATA;
"""

# ⚠ `end_offset` SIFIR DEĞİL: en son saat hâlâ dolmakta olduğu için
# özetlenmemeli, yoksa yarım saatlik veriyle tam saat gibi görünür.
YENILEME_POLITIKASI = """
SELECT add_continuous_aggregate_policy(
    'olay_saatlik',
    start_offset => INTERVAL '3 days',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE
);
"""

# ⚠ GERÇEK ZAMANLI TOPLULAŞTIRMA AÇILIYOR — ve sebebi bir hataydı
#
# İlk sürüm varsayılan `materialized_only = true` ile kuruldu ve
# `/api/v1/events/ozet?saat=1` **boş** dönüyordu. Sebep sessizdi:
# yenileme politikası `end_offset => 1 hour` kullanıyor, yani en son
# saat kasten özetlenmiyor (yarım saatlik veriyi tam saat gibi
# göstermemek için). Materyalize edilmemiş bölge sorguya hiç
# girmediğinden operatör "son 1 saatte hiçbir şey olmadı" cevabı
# alıyordu — oysa alarmlar tabloya yazılmıştı.
#
# Gözetim sisteminde en tehlikeli cevap budur: "hiçbir şey yok" ile
# "bakmadım" aynı görünüyorsa, sistem sessizce yanıltıyor demektir.
#
# `materialized_only = false` ile görünüm, materyalize edilmiş eski
# veriyi ham tablodan gelen TAZE veriyle birleştiriyor. TimescaleDB'de
# bu özellik tam olarak bu senaryo için var.
#
# ⚠ ALTER ayrıca çağrılıyor: `CREATE ... IF NOT EXISTS` var olan bir
# görünümü DEĞİŞTİRMEZ. Önceki sürümle kurulmuş bir veritabanı
# yükseltilirken bu satır olmasa hata sessizce kalıcı olurdu.
GERCEK_ZAMANLI = """
ALTER MATERIALIZED VIEW olay_saatlik
SET (timescaledb.materialized_only = false);
"""

SAKLAMA_POLITIKASI = """
SELECT add_retention_policy(
    'olaylar', INTERVAL '{gun} days', if_not_exists => TRUE
);
"""


async def semayi_kur(baglanti: AsyncConnection) -> None:
    """Tabloyu, hypertable'ı, özet görünümü ve politikaları kurar.

    ⚠ HER AÇILIŞTA ÇAĞRILIYOR ve idempotent olmak ZORUNDA. Şemayı elle
    kurmayı gerektiren bir sistem, bir bileşen yeniden başladığında
    sessizce çalışmaz duruma gelir.

    ⚠ TimescaleDB eklentisi yoksa tablo yine kuruluyor, yalnızca
    zaman serisi özellikleri atlanıyor. Sistem düz PostgreSQL'de de
    ayakta kalmalı — eklenti bir optimizasyon, bir ön koşul değil.
    """
    await baglanti.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))

    # ⚠ `.format()` DEĞİL `.replace()`
    # SQL metni `'{}'::jsonb` içeriyor ve `.format()` onu bir yer tutucu
    # sanıp `IndexError` fırlatıyor. SQL'de süslü parantez sık geçtiği
    # için bu şablonlarda `format` genel olarak yanlış araç.
    for ifade in SEMA:
        await baglanti.execute(text(ifade.replace("{dilim}", DILIM_ARALIGI)))

    try:
        await baglanti.execute(text(SUREKLI_TOPLULASTIRMA))
        await baglanti.execute(text(GERCEK_ZAMANLI))
        await baglanti.execute(text(YENILEME_POLITIKASI))
        await baglanti.execute(
            text(SAKLAMA_POLITIKASI.replace("{gun}", str(SAKLAMA_GUN)))
        )
    except Exception as exc:
        # ⚠ Özet görünüm ve politikalar OLMAZSA OLMAZ değil: olaylar
        # yine kaydediliyor, yalnızca saatlik özet ve otomatik temizlik
        # yok. Bunun için sistemi durdurmak orantısız olurdu.
        log.warning(
            "timescale_ozellikleri_kurulamadi",
            error=f"{type(exc).__name__}: {exc}",
            etki="olaylar kaydediliyor; saatlik ozet ve saklama politikasi yok",
        )


__all__ = ["SAKLAMA_GUN", "semayi_kur"]
