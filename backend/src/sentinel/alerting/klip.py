"""Olay klibi çıkarma — MediaMTX kaydından PyAV ile REMUX.

Neden bu dosya var
------------------
Bir alarm satırı "cam-16'da 11:57'de düşme" diyor. Operatörün bir
sonraki sorusu her zaman aynı: **"göster."** Klip olmadan alarm bir
iddia; klip ile bir kanıt.

⚠ NEDEN YENİDEN KODLAMA YOK — "REMUX"
-------------------------------------
Klip, MediaMTX'in sürekli kaydettiği fMP4 segmentlerinden **kesilip
kopyalanıyor**, yeniden kodlanmıyor (`codec_context` aynen taşınıyor).

Fark küçük değil:

    yeniden kodlama : ~1-3 sn/klip CPU, kalite kaybı, GPU'ya rakip
    remux           : ~32 ms/klip, bit birebir aynı, CPU'da neredeyse
                      bedava

Bu fark 20 kameralı bir sistemde belirleyici. Alarm patlamasında
(bir olayda birden çok kamera alarm verir) yeniden kodlama, tam da
sistemin en meşgul olduğu anda CPU'yu tüketirdi.

⚠ KAYIT VARSAYILAN OLARAK KAPALI
--------------------------------
Kaynak videolar sonsuz döngüde oynadığı için sürekli kayıt **~14 GB/saat**
yazıyor (ölçüldü; ilk tahmin 3 kat düşüktü). Bu yüzden:

  · `.env` içinde `MEDIAMTX_RECORD=no` varsayılan
  · açıkken `recordDeleteAfter: 1h` ile kendiliğinden dönüyor
  · `stop_all.ps1` kapanışta ham kayıtları siliyor

Kayıt kapalıyken bu modül **sessizce klip üretmiyor** ve bu bir hata
değil: alarm yine kaydediliyor, yalnızca `klip_anahtar` boş kalıyor.
Diski doldurmamak için alarmı kaybetmek, yanlış takas olurdu.

⚠ ANAHTAR KARE (KEYFRAME) SINIRI — kaçınılmaz ve dürüstçe raporlanacak
----------------------------------------------------------------------
Remux, video akışını çözmediği için kesim ancak bir anahtar karede
başlayabilir. H.264'te anahtar kare aralığı tipik 1-2 saniye; yani
istenen başlangıç anı ile gerçek başlangıç arasında **1-2 saniyeye
kadar sapma** olabilir.

Bunu düzeltmenin tek yolu yeniden kodlamak ve o bedel bu sistemde
karşılığını vermiyor: olay penceresi zaten ±10 saniye, 1 saniyelik
kayma operatörün gördüğü şeyi değiştirmiyor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sentinel.logging import get_logger

log = get_logger(__name__)

# Olay ANI etrafındaki pencere. Öncesi sonrasından uzun: operatörün
# asıl merak ettiği "ne oldu da bu duruma gelindi", olayın kendisi
# değil. Tırmanma skorunun anlamı da burada — olay öncesi saniyeler.
ONCE_S = 10.0
SONRA_S = 5.0

# MediaMTX segment adı: `2026-08-30_11-57-42-123456.mp4`
# (`recordPath: /recordings/%path/%Y-%m-%d_%H-%M-%S-%f`)
SEGMENT_DESENI = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})-(\d{6})\.(mp4|mkv)$"
)


@dataclass(frozen=True, slots=True)
class Segment:
    yol: Path
    baslangic: datetime


def _segmentleri_listele(kok: Path, camera: str) -> list[Segment]:
    """Bir kameranın kayıt segmentlerini zamana göre sıralı döndürür.

    ⚠ Dosya ADINDAN zaman okunuyor, `mtime`'dan değil. `mtime` dosyanın
    SON YAZILDIĞI an — yani segmentin BİTİŞİ, başlangıcı değil. Aradaki
    60 saniyelik fark, kesilen klibi bir segment kaydırırdı.
    """
    dizin = kok / camera
    if not dizin.is_dir():
        return []
    segmentler: list[Segment] = []
    for yol in dizin.iterdir():
        m = SEGMENT_DESENI.match(yol.name)
        if not m:
            continue
        yil, ay, gun, sa, dk, sn, mikro, _uzanti = m.groups()
        segmentler.append(
            Segment(
                yol=yol,
                # ⚠⚠ 10.09.2026 — BU SATIR ÜÇ HAFTADIR YANLIŞTI (P-83)
                #
                # Eskiden `.astimezone()` çağrılıyordu ve üstündeki yorum
                # *"MediaMTX yerel saatle yazıyor"* diyordu. **Yazmıyor.**
                # MediaMTX konteynerinde TZ ayarlı değil (docker-compose
                # yalnızca PostgreSQL'e TZ veriyor), dolayısıyla dosya
                # adları UTC.
                #
                # `datetime(...)` naif bir zaman üretir; `.astimezone()`
                # onu YEREL sanıp +03:00 iliştiriyordu. Sonuç: her segment
                # 3 saat geçmişte görünüyor, olay penceresini hiçbir
                # segment kapsamıyor, `klip_cikar` her seferinde `None`
                # dönüyordu. `data/clips` 30.08'den beri bu yüzden BOŞTU
                # — zincir hiç çalışmadı.
                #
                # ⭐ Varsayım YAZILIYDI ama DOĞRULANMAMIŞTI. Doğrulaması
                # tek komut: `docker exec sentinel-mediamtx date`.
                baslangic=datetime(
                    int(yil), int(ay), int(gun), int(sa), int(dk), int(sn), int(mikro),
                    tzinfo=UTC,
                ),
            )
        )
    return sorted(segmentler, key=lambda s: s.baslangic)


def _kapsayan_segmentler(
    segmentler: list[Segment], bas: datetime, bit: datetime
) -> list[Segment]:
    """[bas, bit] aralığına dokunan segmentleri seçer.

    ⚠ Bir segmentin BİTİŞİ, bir SONRAKİNİN başlangıcıdır. Süre bilgisi
    dosya adında yok ve her segmenti açıp okumak pahalı; komşudan
    çıkarmak hem doğru hem bedava. Son segment için üst sınır olarak
    yapılandırılmış segment süresi + pay kullanılıyor.
    """
    secilen: list[Segment] = []
    for i, s in enumerate(segmentler):
        sonu = (
            segmentler[i + 1].baslangic
            if i + 1 < len(segmentler)
            else s.baslangic + timedelta(seconds=120)
        )
        if sonu > bas and s.baslangic < bit:
            secilen.append(s)
    return secilen


def klip_cikar(
    *,
    kayit_koku: Path,
    camera: str,
    olay_ts: float,
    hedef: Path,
    once_s: float = ONCE_S,
    sonra_s: float = SONRA_S,
) -> Path | None:
    """Olay anının etrafından bir klip keser. Başarısızsa `None`.

    ⚠ İSTİSNA FIRLATMIYOR. Çağıranı alarm worker'ının döngüsü; klip
    üretilemediği için alarm yazımının durması, çözdüğü sorundan büyük
    bir sorun olurdu. Kanıt olmayan bir alarm hâlâ bir alarmdır.
    """
    try:
        import av
    except ImportError:
        log.warning("pyav_yok_klip_uretilemiyor")
        return None

    bas = datetime.fromtimestamp(olay_ts - once_s, tz=UTC).astimezone()
    bit = datetime.fromtimestamp(olay_ts + sonra_s, tz=UTC).astimezone()

    segmentler = _segmentleri_listele(kayit_koku, camera)
    if not segmentler:
        # Kayıt kapalı ya da bu kamera için henüz segment yok.
        # ⚠ Uyarı DEĞİL bilgi: varsayılan yapılandırmada beklenen durum.
        log.debug("kayit_segmenti_yok", camera=camera)
        return None

    kapsayan = _kapsayan_segmentler(segmentler, bas, bit)
    if not kapsayan:
        # ⚠⚠ SAAT DİLİMİ TUZAĞINI SESSİZ OLMAKTAN ÇIKAR (P-83)
        #
        # Bu dal üç hafta boyunca HER ÇAĞRIDA çalıştı ve kimse fark
        # etmedi: mesajı "segment donmuş olabilir" diyordu, yani
        # tamamen olağan bir durumu işaret ediyordu. Gerçek sebep ise
        # segment adlarının UTC olması ve kodun yerel saat sanmasıydı.
        #
        # ⭐ Ders: bir hata dalının MESAJI, o dalın gerçekten neden
        # çalıştığını söyleyemiyorsa, hata sessizdir. Artık en yeni
        # segment ile olay anı arasındaki fark ölçülüyor ve tam saat
        # katlarına denk geliyorsa saat dilimi şüphesi AÇIKÇA
        # yazılıyor.
        fark_s = (bas - segmentler[-1].baslangic).total_seconds()
        saat_katina_yakin = abs(fark_s) > 1800 and abs(
            abs(fark_s) % 3600 - 1800
        ) > 1500
        log.warning(
            "olay_ani_kayitta_yok",
            camera=camera,
            olay=bas.isoformat(),
            en_eski=segmentler[0].baslangic.isoformat(),
            en_yeni=segmentler[-1].baslangic.isoformat(),
            fark_saat=round(fark_s / 3600, 2),
            sebep=(
                "⚠ FARK TAM SAAT KATINA YAKIN — segment adlarının saat "
                "dilimi yanlış yorumlanıyor olabilir (P-83). Doğrula: "
                "docker exec sentinel-mediamtx date"
                if saat_katina_yakin
                else "segment donmus olabilir (recordDeleteAfter)"
            ),
        )
        return None

    hedef.parent.mkdir(parents=True, exist_ok=True)
    yazilan = 0
    try:
        with av.open(str(hedef), mode="w") as cikti:
            akis_cikti = None
            for segment in kapsayan:
                with av.open(str(segment.yol)) as girdi:
                    video = next(
                        (s for s in girdi.streams if s.type == "video"), None
                    )
                    if video is None:
                        continue
                    if akis_cikti is None:
                        # ⚠ REMUX: kodek bağlamı OLDUĞU GİBİ taşınıyor.
                        # `add_stream(template=...)` çözme/kodlama
                        # yapmadan aynı bit akışını kabul eden bir çıkış
                        # akışı kuruyor.
                        akis_cikti = cikti.add_stream_from_template(video)

                    zaman_tabani = float(video.time_base or 0) or 1 / 90000
                    seg_bas = segment.baslangic
                    for paket in girdi.demux(video):
                        if paket.pts is None or paket.dts is None:
                            continue
                        an = seg_bas + timedelta(
                            seconds=float(paket.pts) * zaman_tabani
                        )
                        if an < bas:
                            continue
                        if an > bit:
                            break
                        # ⚠ İlk paket ANAHTAR KARE olmalı, yoksa oynatıcı
                        # bozuk kareyle başlar. Anahtar kare gelene kadar
                        # atlanıyor — kesimin 1-2 sn kayabilmesinin sebebi
                        # bu (modül başlığı).
                        if yazilan == 0 and not paket.is_keyframe:
                            continue
                        paket.stream = akis_cikti
                        cikti.mux(paket)
                        yazilan += 1
    except Exception as exc:
        log.error(
            "klip_cikarilamadi",
            camera=camera,
            error=f"{type(exc).__name__}: {exc}",
        )
        hedef.unlink(missing_ok=True)
        return None

    if yazilan == 0:
        # ⚠ Boş dosya BIRAKILMIYOR. Diskte 0 baytlık bir klip, "klip
        # var ama bozuk" izlenimi verir ve hata ayıklamayı zorlaştırır.
        hedef.unlink(missing_ok=True)
        log.info("klip_bos_kaldi", camera=camera, sebep="anahtar kare bulunamadi")
        return None

    log.info(
        "klip_uretildi",
        camera=camera,
        paket=yazilan,
        boyut_kb=round(hedef.stat().st_size / 1024, 1),
        yol=hedef.name,
    )
    return hedef


def klip_anahtari(camera: str, olay_ts: float, tur: str) -> str:
    """Nesne deposu anahtarı — tarihe göre bölümlenmiş.

    ⚠ Düz bir dizine on binlerce dosya koymak hem listeleme hem silme
    tarafında sorun çıkarır. Tarih öneki, "şu günün kliplerini sil"
    işlemini tek önek taramasına indiriyor.
    """
    d = datetime.fromtimestamp(olay_ts, tz=UTC)
    return (
        f"{d:%Y/%m/%d}/{camera}/{d:%H%M%S}_{tur}.mp4"
    )


__all__ = ["ONCE_S", "SONRA_S", "klip_anahtari", "klip_cikar"]
