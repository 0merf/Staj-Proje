"""Olay yazma ve sorgulama — PLAN.md §8.

⚠ YAZMA YOLU ANALİZ DÖNGÜSÜNÜ BLOKLAMAMALI
------------------------------------------
Analytics worker saniyede onlarca kare işliyor. Her alarmda veritabanına
senkron `INSERT` atmak iki şeyi birden bozar:

  · Ağ turu + fsync, kare işleme bütçesinin kat kat üstünde
  · **Veritabanı yavaşlarsa ANALİZ yavaşlar.** Yardımcı bir bileşenin
    arızası ana boru hattını durdurmamalı (PLAN §4.2 hata izolasyonu)

Bu yüzden yazma **ayrı bir tüketici** işi: analytics worker Valkey
akışına yazmaya devam ediyor (zaten yapıyordu), alarm worker'ı o akışı
okuyup toplu hâlde veritabanına basıyor.

Mimari kural 5'in ("her kuyruk sınırlı") burada karşılığı: Valkey akışı
zaten `maxlen=1000` ile sınırlı. Veritabanı tümden çökerse alarmlar
kaybolur ama **sistem çalışmaya devam eder** — ve bu bilinçli bir
tercih, sessiz bir kusur değil. Alternatif (yazamayınca durmak) bir
gözetim sisteminde daha kötüdür.

⚠ NEDEN TOPLU (BATCH) YAZIM
Tek tek `INSERT` yerine `executemany`: 50 alarmlık bir kesitte 50 ağ
turu yerine 1. Alarmlar zaten patlamalı gelir (bir olayda birden çok
kamera birden alarm verir).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from sentinel.db.engine import motor
from sentinel.logging import get_logger

log = get_logger(__name__)

EKLE = text("""
INSERT INTO olaylar
    (ts, camera, tur, ciddiyet, skor, track_id, kanit, tamlik,
     karsi_taraf, klip_anahtar)
VALUES
    (:ts, :camera, :tur, :ciddiyet, :skor, :track_id,
     CAST(:kanit AS jsonb), :tamlik, :karsi_taraf, :klip_anahtar)
""")


@dataclass(frozen=True, slots=True)
class Olay:
    """Veritabanına yazılacak tek bir olay."""

    ts: datetime
    camera: str
    tur: str
    ciddiyet: str
    skor: float
    track_id: int | None = None
    kanit: dict[str, Any] | None = None
    tamlik: float | None = None
    karsi_taraf: int | None = None
    # Nesne deposu anahtarı. Alarm worker'ı klip kesebildiyse dolu.
    # ⚠ INSERT'e giriyor, sonradan UPDATE edilmiyor: olay kaydı bir
    # denetim izi ve değişmemeli.
    klip_anahtar: str | None = None

    @classmethod
    def akistan(cls, alanlar: dict[str, str]) -> Olay | None:
        """Valkey `analytics.events` kaydından olay üretir.

        ⚠ Bozuk kayıt sistemi durdurmamalı: `None` dönüyor ve çağıran
        atlıyor. Akıştaki tek bozuk JSON yüzünden alarm yazımının
        tamamen durması, çözdüğü sorundan büyük bir sorun olurdu.
        """
        try:
            veri = json.loads(alanlar.get("data") or "{}")
            return cls(
                ts=datetime.fromtimestamp(float(alanlar["ts"]), tz=UTC),
                camera=str(alanlar["cam"]),
                tur=str(alanlar["type"]),
                ciddiyet=str(veri.get("severity", "attention")),
                skor=float(veri.get("score", 0.0)),
                track_id=(
                    int(veri["track"]) if veri.get("track") is not None else None
                ),
                # ⭐⭐ `video_pts` KANITA EKLENİYOR — yer gerçeğinin anahtarı
                #
                # Bu alan olmadan bir alarmın doğru olup olmadığı
                # DOĞRULANAMIYORDU: kayıtta yalnızca duvar saati (`ts`)
                # vardı ve kameralarımız sonsuz döngüdeki video dosyaları
                # olduğu için o saat videodaki ana çevrilemiyordu.
                #
                # Sonuç ağırdı: sistem alarm üretiyor, hiç kimse o
                # alarmın gerçek olup olmadığını söyleyemiyordu. K7'nin
                # "11.69 alarm/kamera-saat" sayısı bu yüzden bir ALARM
                # oranı, yanlış alarm oranı değil.
                #
                # ⭐ `kanit` zaten `jsonb` → VERİTABANI ŞEMASI DEĞİŞMİYOR.
                # Yeni sütun, migrasyon, indeks gerekmedi.
                #
                # ⚠ `-1` = bilinmiyor. Sıfırla karıştırılmamalı: 0.0
                # videonun BAŞI demek, -1 "ölçemedim" demek.
                kanit={
                    **(veri.get("evidence") or {}),
                    **(
                        {"video_pts": float(alanlar["pts"])}
                        if alanlar.get("pts") is not None
                        and float(alanlar["pts"]) >= 0
                        else {}
                    ),
                },
                tamlik=(
                    float(veri["completeness"])
                    if veri.get("completeness") is not None
                    else None
                ),
                karsi_taraf=(
                    int(veri["against"]) if veri.get("against") is not None else None
                ),
            )
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
            log.warning("bozuk_olay_atlandi", error=f"{type(exc).__name__}: {exc}")
            return None

    def parametreler(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "camera": self.camera,
            "tur": self.tur,
            "ciddiyet": self.ciddiyet,
            "skor": self.skor,
            "track_id": self.track_id,
            # ⚠ JSON'a burada çevriliyor, sürücüye bırakılmıyor:
            # asyncpg jsonb için açık bir cast istiyor ve sözlüğü
            # kendiliğinden serileştirmiyor.
            "kanit": json.dumps(self.kanit or {}, ensure_ascii=False),
            "tamlik": self.tamlik,
            "karsi_taraf": self.karsi_taraf,
            "klip_anahtar": self.klip_anahtar,
        }


async def yaz(olaylar: list[Olay]) -> int:
    """Olayları toplu yazar. Hata durumunda 0 döner, İSTİSNA FIRLATMAZ.

    ⚠ Bilinçli olarak yutuluyor. Bu fonksiyonun çağıranı alarm
    worker'ının ana döngüsü; veritabanı erişilemezse döngü durmamalı,
    bir sonraki kesitte yeniden denemeli. Sessiz değil ama: her hata
    loglanıyor ve sayaç metriğe işleniyor.
    """
    if not olaylar:
        return 0
    try:
        async with motor().begin() as baglanti:
            await baglanti.execute(EKLE, [o.parametreler() for o in olaylar])
        return len(olaylar)
    except Exception as exc:
        log.error(
            "olay_yazilamadi",
            adet=len(olaylar),
            error=f"{type(exc).__name__}: {exc}",
        )
        return 0


async def son_olaylar(
    *,
    limit: int = 100,
    camera: str | None = None,
    tur: str | None = None,
    saat: float | None = None,
    ciddiyet: str | None = None,
    bas: float | None = None,
    bit: float | None = None,
) -> list[dict[str, Any]]:
    """Olay geçmişini sorgular — operatörün 'dün gece ne oldu' sorusu.

    ⚠ Parametreler BAĞLANIYOR, birleştirilmiyor. Filtreler kullanıcı
    girdisinden geliyor ve bu bir SQL enjeksiyon yüzeyi (PLAN §11.1
    Öncelik-1). Sütun adları sabit, yalnızca değerler dışarıdan.

    ⚠ `bas`/`bit` (unix saniye) 10.09'da eklendi. Sebep: zaman
    çizelgesindeki bir hücre "cam-13, saat 14:00" demek ve o hücreye
    tıklayınca TAM O SAATİN olayları gerekiyor. `saat` parametresi
    yalnızca "son N saat" diyebiliyordu, geçmişte bir PENCERE
    seçilemiyordu — çizelge bu yüzden tıklanamaz bir ısı haritasıydı.
    """
    kosullar = ["TRUE"]
    parametreler: dict[str, Any] = {"limit": max(1, min(limit, 1000))}
    if camera:
        kosullar.append("camera = :camera")
        parametreler["camera"] = camera
    if tur:
        kosullar.append("tur = :tur")
        parametreler["tur"] = tur
    if ciddiyet:
        kosullar.append("ciddiyet = :ciddiyet")
        parametreler["ciddiyet"] = ciddiyet
    # ⚠ `bas`/`bit` verilirse `saat` YOK SAYILIYOR: ikisi birlikte
    # "son 24 saat İÇİNDE ama 3 gün önceki şu saat" gibi hiçbir zaman
    # sonuç veremeyecek bir koşul üretirdi. Belirli pencere isteyen
    # daha spesifiktir, o kazanır.
    if bas is not None or bit is not None:
        if bas is not None:
            kosullar.append("ts >= to_timestamp(:bas)")
            parametreler["bas"] = float(bas)
        if bit is not None:
            kosullar.append("ts < to_timestamp(:bit)")
            parametreler["bit"] = float(bit)
    elif saat is not None:
        kosullar.append("ts >= now() - make_interval(hours => :saat)")
        parametreler["saat"] = int(saat)

    sorgu = text(f"""
        SELECT ts, camera, tur, ciddiyet, skor, track_id, kanit,
               tamlik, karsi_taraf, klip_anahtar
        FROM olaylar
        WHERE {" AND ".join(kosullar)}
        ORDER BY ts DESC
        LIMIT :limit
    """)  # noqa: S608 — koşullar sabit metin, değerler bağlı parametre

    async with motor().connect() as baglanti:
        sonuc = await baglanti.execute(sorgu, parametreler)
        return [dict(satir._mapping) for satir in sonuc]


async def saatlik_ozet(saat: int = 24) -> list[dict[str, Any]]:
    """Saatlik alarm özeti — K7'nin sürekli hâli.

    ⚠ Sürekli toplulaştırma görünümü yoksa (TimescaleDB eklentisi
    kurulamamış) ham tablodan hesaplanıyor. Yavaş ama doğru; özet
    görünüm bir hızlandırma, bir ön koşul değil.
    """
    try:
        async with motor().connect() as baglanti:
            sonuc = await baglanti.execute(
                text("""
                    SELECT saat, camera, tur, ciddiyet, adet, ort_skor, azami_skor
                    FROM olay_saatlik
                    WHERE saat >= now() - make_interval(hours => :saat)
                    ORDER BY saat DESC
                """),
                {"saat": saat},
            )
            return [dict(s._mapping) for s in sonuc]
    except Exception:
        async with motor().connect() as baglanti:
            sonuc = await baglanti.execute(
                text("""
                    SELECT time_bucket('1 hour', ts) AS saat, camera, tur,
                           ciddiyet, count(*) AS adet,
                           avg(skor) AS ort_skor, max(skor) AS azami_skor
                    FROM olaylar
                    WHERE ts >= now() - make_interval(hours => :saat)
                    GROUP BY saat, camera, tur, ciddiyet
                    ORDER BY saat DESC
                """),
                {"saat": saat},
            )
            return [dict(s._mapping) for s in sonuc]


__all__ = ["Olay", "saatlik_ozet", "son_olaylar", "yaz"]
