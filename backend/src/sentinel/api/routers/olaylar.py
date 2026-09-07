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

⚠ 03.09.2026 — KLİP UCU EKLENDİ VE NEDEN ÖNEMLİ
Bu dosya alarmların `klip` anahtarını 30.08'den beri döndürüyordu ve
o anahtarla yapılacak HİÇBİR ŞEY yoktu: klibi getiren bir uç yoktu,
panel alanı hiç kullanmıyordu. Yani zincir şöyleydi:

    alarm → klip KESİLDİ → anahtar veritabanına yazıldı → ???

Klip yazıcısının 12 birim testi vardı ve hepsi geçiyordu; kimse
"peki kesilen klibe nasıl ulaşılıyor" diye sormamıştı. Kapsam
maddesi (PLAN §1.3 "olay öncesi/sonrası klip arşivi") yarım
kalmıştı — ve yarım olduğu görünmüyordu, çünkü her parçası tek tek
çalışıyordu.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from sentinel.api.guvenlik import Kullanici, mevcut_kullanici
from sentinel.config import PROJECT_ROOT
from sentinel.db import olaylar as depo
from sentinel.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])

KLIP_KOKU = PROJECT_ROOT / "data" / "clips"

# ⚠ G12 — PATH TRAVERSAL: BEYAZ LİSTE, KARA LİSTE DEĞİL
#
# Klip anahtarı `alerting/klip.py · klip_anahtari()` tarafından
# üretiliyor ve biçimi TAM olarak şu:
#
#     2026/09/03/cam-16/115742_fall.mp4
#     YYYY/MM/DD/<kamera>/HHMMSS_<tur>.mp4
#
# Desen bu biçimin tamamını tarif ediyor. `..`, mutlak yol, sürücü
# harfi, ters bölü, boş parça — hiçbiri desene UYMADIĞI için elenmiş
# oluyor; tek tek yasaklamaya gerek kalmıyor.
#
# ⚠ Kara liste yaklaşımı burada özellikle tehlikeli olurdu: `..` için
# filtre yazan biri `%2e%2e`, `..%2f`, `....//` gibi kodlamaları
# kaçırır. Beyaz liste bu sınıf hatanın tamamını kapatıyor — yalnızca
# İZİN VERİLEN biçimi tarif ettiğimiz için, düşünmediğimiz saldırı
# biçimleri de tanım gereği eleniyor.
# ⚠ SON ÇAPA `\Z`, `$` DEĞİL — küçük ama gerçek bir fark
# Python'da `$` yalnızca dizenin sonunu değil, SONDAKİ YENİ SATIRDAN
# ÖNCESİNİ de eşleştirir. Yani `^...\.mp4$` deseni
# `".../115742_fall.mp4\n"` girdisini KABUL EDER. `\Z` bunu yapmaz:
# yalnızca dizenin gerçek sonu.
#
# Tek başına sömürülebilir değil (sondaki `\n` yolu değiştirmez) ama
# doğrulayıcının "tam olarak bu biçim" iddiası ile davranışı
# ayrışıyordu — ve bu projede tam olarak o ayrışmalar pahalıya
# patladı. Bir kontrolün adı, yaptığı işi söylemeli.
KLIP_DESENI = re.compile(
    r"\A\d{4}/\d{2}/\d{2}/[A-Za-z0-9_-]{1,32}/\d{6}_[a-z_]{1,32}\.mp4\Z"
)

# ⚠ Kamera adı beyaz listesi yerine biçim doğrulaması: `cam-NN` ya da
# test kameraları. Doğrudan SQL'e bağlı parametre olarak gidiyor
# (enjeksiyon yolu yok) ama biçimi doğrulamak, yazım hatası yüzünden
# sessizce boş sonuç dönmeyi de engelliyor.
KAMERA_DESENI = r"^[A-Za-z0-9_-]{1,32}$"
TUR_DESENI = r"^[a-z_]{1,32}$"


@router.get("")
async def olay_listesi(
    _: Annotated[Kullanici, Depends(mevcut_kullanici)],
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
    _: Annotated[Kullanici, Depends(mevcut_kullanici)],
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


@router.get("/klip/{anahtar:path}")
async def klip(
    anahtar: str,
    kullanici: Annotated[Kullanici, Depends(mevcut_kullanici)],
) -> FileResponse:
    """Bir olayın kanıt klibini döndürür (G12 + G19).

    `anahtar`, olay kaydındaki `klip` alanı:
        `2026/09/03/cam-16/115742_fall.mp4`

    ⚠ ROL: `viewer` YETİYOR — ve bu bilinçli bir karar
    Canlı ızgara zaten `viewer`'a ham video gösteriyor. Klibi
    `operator`'a kısıtlamak tutarsız olurdu: aynı görüntünün canlısı
    serbest, kaydı yasak. Kısıtlanması gereken şey görüntüye erişim
    değil, görüntünün DIŞARI ÇIKARILMASI — ve onun mekanizması yetki
    değil DENETİM.

    ⚠ HER ERİŞİM DENETİME YAZILIYOR (G19)
    PLAN §11.1/G19 "klip dışa aktarma"yı açıkça denetlenecek eylemler
    arasında sayıyor. Bir klip indirilebilir bir dosya: bir kez
    çıktığında sistemin kontrolünden tamamen çıkıyor. Kimin neyi ne
    zaman indirdiği, indirmeyi engellemekten daha uygulanabilir bir
    koruma.

    ⚠ 404 AYRIM YAPMIYOR — bilinçli
    "Biçim bozuk", "dosya yok" ve "dizin dışına çıkıyor" durumlarının
    üçü de aynı 404'ü döndürüyor. Farklı cevaplar vermek, saldırgana
    dosya sisteminin haritasını çıkarma imkânı verirdi (var olan ve
    olmayan yolları ayırt etme).
    """
    if not KLIP_DESENI.match(anahtar):
        log.warning(
            "klip_bicimi_reddedildi",
            kullanici=kullanici.kullanici_adi,
            anahtar=anahtar[:120],
        )
        raise HTTPException(404, "klip bulunamadı")

    yol = (KLIP_KOKU / anahtar).resolve()

    # ⚠ İKİNCİ SAVUNMA: DESEN GEÇSE BİLE YOL DOĞRULANIYOR
    # Desen zaten `..` geçirmiyor; bu kontrol yine de duruyor çünkü
    # sembolik bağlantılar deseni atlatabilir. `data/clips/2026` bir
    # symlink ise `resolve()` onu takip eder ve dosya kök dizinin
    # DIŞINA düşebilir. Tek savunmaya güvenmemek, savunmanın
    # varsayımının yanlış çıkabileceğini kabul etmektir.
    if not yol.is_relative_to(KLIP_KOKU.resolve()) or not yol.is_file():
        raise HTTPException(404, "klip bulunamadı")

    # ⚠ Denetim kaydı dosya GÖNDERİLMEDEN önce yazılıyor. Sonra
    # yazılsaydı, aktarım yarıda kesilen bir indirme kayda hiç
    # geçmezdi — oysa dosya kısmen de olsa çıkmış olurdu.
    try:
        from sentinel.db import kullanicilar as denetim_deposu

        await denetim_deposu.denetim_yaz(
            "klip_goruntuleme",
            kullanici_adi=kullanici.kullanici_adi,
            hedef=anahtar,
        )
    except Exception as exc:  # pragma: no cover
        log.error("klip_denetimi_yazilamadi", error=f"{type(exc).__name__}: {exc}")

    return FileResponse(
        yol,
        media_type="video/mp4",
        # ⚠ `inline`: tarayıcı oynatsın, indirme diyaloğu açmasın.
        # Operatörün ihtiyacı "izlemek"; indirme ayrı ve daha ağır bir
        # eylem olarak kalmalı (kullanıcı yine de kaydedebilir ama
        # varsayılan davranış dışarı çıkarma olmamalı).
        headers={"Content-Disposition": f'inline; filename="{Path(anahtar).name}"'},
    )


__all__ = ["router"]
