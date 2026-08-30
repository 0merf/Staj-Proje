"""Olay geçmişi uç noktaları — operatörün "dün gece ne oldu" sorusu.

⚠ NEDEN CANLI WEBSOCKET YETMİYOR
Panel şu ana kadar alarmları yalnızca canlı WebSocket'ten alıyordu.
Bunun iki sonucu vardı:

  · Panel kapalıyken olan hiçbir şey görülemiyordu
  · Panel açıldığında geçmiş boştu — sistem sanki hiç alarm
    üretmemiş gibi görünüyordu

Gözetim sisteminin asıl değeri geriye bakabilmekte. Canlı akış
"dikkat", geçmiş "kanıt".

⚠ TAMAMEN OKUMA UÇLARI
Buradan hiçbir şey yazılmıyor, silinmiyor. Olay kaydı bir denetim izi
(audit trail) niteliğinde: sistemin ne zaman ne dediğini sonradan
değiştirebilmek, kaydın değerini bitirir.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from sentinel.db import olaylar as depo
from sentinel.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])

# ⚠ Kamera adı beyaz listesi yerine biçim doğrulaması: `cam-NN` ya da
# test kameraları. Doğrudan SQL'e bağlı parametre olarak gidiyor
# (enjeksiyon yolu yok) ama biçimi doğrulamak, yazım hatası yüzünden
# sessizce boş sonuç dönmeyi de engelliyor.
KAMERA_DESENI = r"^[A-Za-z0-9_-]{1,32}$"
TUR_DESENI = r"^[a-z_]{1,32}$"


@router.get("")
async def olay_listesi(
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    camera: Annotated[str | None, Query(pattern=KAMERA_DESENI)] = None,
    tur: Annotated[str | None, Query(pattern=TUR_DESENI)] = None,
    saat: Annotated[int | None, Query(ge=1, le=24 * 90)] = 24,
) -> dict[str, Any]:
    """Olay geçmişi — en yeniden eskiye.

    `saat`: kaç saat geriye bakılacağı. Üst sınır 90 gün, çünkü ham
    satırlar zaten 30 gün sonra siliniyor (`db/schema.py · SAKLAMA_GUN`)
    ve daha uzun bir aralık istemek boşuna tarama demek.
    """
    try:
        kayitlar = await depo.son_olaylar(
            limit=limit, camera=camera, tur=tur, saat=saat
        )
    except Exception as exc:
        # ⚠ İstisna metni ISTEMCIYE VERİLMİYOR (PLAN §11.1 / G09).
        # Veritabanı hataları şema adı, sütun adı, hatta bağlantı dizesi
        # sızdırabiliyor. Loga tam hâli, istemciye yalnızca durum.
        log.error("olay_sorgusu_basarisiz", error=f"{type(exc).__name__}: {exc}")
        raise HTTPException(503, "olay deposu şu anda erişilemiyor") from None

    return {
        "adet": len(kayitlar),
        "olaylar": [
            {
                "ts": k["ts"].timestamp(),
                "camera": k["camera"],
                "tur": k["tur"],
                "ciddiyet": k["ciddiyet"],
                "skor": round(float(k["skor"]), 3),
                "track": k["track_id"],
                "kanit": k["kanit"],
                "tamlik": round(float(k["tamlik"]), 2) if k["tamlik"] is not None else None,
                "karsi_taraf": k["karsi_taraf"],
                "klip": k["klip_anahtar"],
            }
            for k in kayitlar
        ],
    }


@router.get("/ozet")
async def saatlik(
    saat: Annotated[int, Query(ge=1, le=24 * 30)] = 24,
) -> dict[str, Any]:
    """Saatlik alarm özeti — K7 kriterinin sürekli hâli.

    ⚠ Bu uç, K7'yi ("kamera-saat başına yanlış alarm ≤3") artık bir
    ölçüm koşusu olmaktan çıkarıyor: sayı sistemin normal çıktısı.
    `alarm_kamera_saat` alanı doğrudan o kriterin karşılığı.

    ⚠ "YANLIŞ alarm" değil "alarm" sayılıyor. Bir alarmın yanlış
    olduğunu söyleyebilmek yer gerçeği ister ve o zemin yalnızca
    kontrol kamerasında (cam-18) var. Bu uç ham sayıyı veriyor;
    yorumu yapan raporun kendisi.
    """
    try:
        satirlar = await depo.saatlik_ozet(saat)
    except Exception as exc:
        log.error("ozet_sorgusu_basarisiz", error=f"{type(exc).__name__}: {exc}")
        raise HTTPException(503, "olay deposu şu anda erişilemiyor") from None

    toplam = sum(int(s["adet"]) for s in satirlar)
    kameralar = {str(s["camera"]) for s in satirlar}
    kamera_saat = len(kameralar) * saat if kameralar else 0

    return {
        "pencere_saat": saat,
        "toplam_alarm": toplam,
        "kamera_sayisi": len(kameralar),
        "alarm_kamera_saat": round(toplam / kamera_saat, 2) if kamera_saat else 0.0,
        "k7_hedef": 3.0,
        "satirlar": [
            {
                "saat": s["saat"].timestamp(),
                "camera": s["camera"],
                "tur": s["tur"],
                "ciddiyet": s["ciddiyet"],
                "adet": int(s["adet"]),
                "ort_skor": round(float(s["ort_skor"]), 3),
                "azami_skor": round(float(s["azami_skor"]), 3),
            }
            for s in satirlar
        ],
    }


__all__ = ["router"]
