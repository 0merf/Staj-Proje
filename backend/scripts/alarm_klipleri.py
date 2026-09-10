"""Her alarmı KAYNAK VİDEODA bulup klip keser — yer gerçeği için (P-68).

⭐⭐ NEDEN BU BETİK — projenin en büyük bilimsel açığı
------------------------------------------------------
Kullanıcının tespiti:

> *"Sistem alarm veriyor ama bu alarmı doğrulayan bir şey yok. Bu bizim
> projenin en büyük sıkıntılarından biri olmaz mı?"*

Haklıydı. Elimizdeki yer gerçeği RWF-2000 (klip seviyesi), Avenue (kare
seviyesi), cam-16 (UR Fall) ve cam-18 (kontrol) ile sınırlıydı. 20
kameralık çiftliğin geneli için hiçbir etiket yoktu — **ve K7 tam da
orada ölçülüyordu.** Bu yüzden bildirilen "11.69 alarm/kamera-saat" bir
*alarm oranı*dır, yanlış alarm oranı değil.

⭐ Çözüm mümkün, çünkü kameralarımız **video dosyası**. Gerçek bir IP
kamerada geçmişe dönüp bakmak imkânsız olurdu; bizde her alarmın
kaynak videoda tam olarak nereye denk geldiği bulunabiliyor.

⚠ EKSİK OLAN TEK ŞEY BİLGİNİN TAŞINMASIYDI
`FrameMessage.pts` (kaynak videodaki saniye) boru hattında Gün 1'den
beri vardı; çıkarım worker'ı sonucu yayınlarken onu **düşürüyordu**.
Üç küçük değişiklikle uçtan uca taşındı ve `kanit.video_pts` olarak
kaydediliyor — `kanit` zaten `jsonb` olduğu için **veritabanı şeması
değişmedi**.

NASIL KULLANILIR
----------------
    uv run python scripts/alarm_klipleri.py --saat 6 --adet 60
    # -> data/_tmp/alarm_klipleri/<tur>/<cam>_<pts>_<id>.mp4
    #    + etiket_sablonu.csv

Sonra klipler izlenip CSV'de `dogru` sütunu doldurulur (1 = gerçek olay,
0 = yanlış alarm, boş = emin değilim). Ardından:

    uv run python scripts/alarm_klipleri.py --ozet

⚠ ETİKETLEME KURALI — önce yaz, sonra bak
Neyin "gerçek" sayılacağı klipler izlenmeden yazılmalı. Sonradan
tanımlamak, gördüğünü haklı çıkaracak bir tanım seçmek olur (P-49'un
dersi: ölçütün TANIMI olayın tanımını yanlış çizebiliyor).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIZINI = PROJECT_ROOT / "data" / "videos"
CIKTI = PROJECT_ROOT / "data" / "_tmp" / "alarm_klipleri"
CSV_YOLU = CIKTI / "etiket_sablonu.csv"

ONCE_S = 3.0  # alarmdan kaç saniye ÖNCE başlasın
TOPLAM_S = 6.0  # klip uzunluğu


async def _olaylari_al(saat: float, adet: int) -> list[dict[str, Any]]:
    from sqlalchemy import text

    from sentinel.db.engine import motor

    sorgu = text("""
        SELECT ts, camera, tur, ciddiyet, skor, track_id, kanit
        FROM olaylar
        WHERE ts > now() - (:saat || ' hours')::interval
        ORDER BY ts DESC
        LIMIT :adet
    """)
    async with motor().connect() as baglanti:
        sonuc = await baglanti.execute(sorgu, {"saat": str(saat), "adet": adet})
        return [dict(r._mapping) for r in sonuc]


def _kes(kamera: str, pts: float, hedef: Path) -> bool:
    """Kaynak videodan alarm anının etrafını keser. Başarısızsa False.

    ⚠ NEDEN `ffmpeg` CLI DEĞİL: bu makinede `ffmpeg` PATH'te yok (PyAV
    kütüphaneyi gömüyor ama komut satırı aracını değil). Dış bir araca
    bağlanmak, betiği "benim makinemde çalışıyor" sınıfına sokardı.
    OpenCV zaten bağımlılığımız.

    ⚠ Alarm anı klibin ORTASINDA: `ONCE_S` saniye öncesinden başlıyor.
    Sebep — bir alarmın doğru olup olmadığına karar vermek için olayın
    ÖNCESİNİ görmek gerekiyor. Yalnızca alarm anından itibaren kesmek,
    "neden alarm verdi" sorusunu cevaplanamaz kılardı.
    """
    import cv2

    kaynak = VIDEO_DIZINI / f"{kamera}.mp4"
    if not kaynak.exists():
        return False
    cap = cv2.VideoCapture(str(kaynak))
    if not cap.isOpened():
        return False
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        genislik = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        yukseklik = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if genislik <= 0 or yukseklik <= 0:
            return False

        # ⚠⚠ 10.09.2026 — `pts` DOSYA İÇİ KONUM DEĞİL, DÖNGÜ BOYUNCA BİRİKİYOR
        #
        # MediaMTX kaynak videoları `-stream_loop -1 -fflags +genpts` ile
        # SONSUZ DÖNGÜDE yayınlıyor. `genpts` her turda zaman damgasını
        # sıfırlamıyor, **birikimli** üretiyor. Yani `pts = 2037.73` bir
        # 300 saniyelik videoda "2037. saniye" demek değil, "yayın
        # başlayalı 2037 saniye oldu" demek.
        #
        # İlk sürüm bunu doğrudan konum olarak kullanıyordu:
        #   cap.set(POS_MSEC, 2037_730)  →  dosyanın SONUNUN ötesi
        #   → okuma başarısız → 257 baytlık BOŞ klip
        #
        # ⚠ Ve betik bunu BAŞARILI sanıyordu: kontrolü `dosya var ve
        # boyut > 0` idi. 257 bayt "var ve >0". "12/12 klip kesildi"
        # diye rapor edildi ve klipler açılmıyordu.
        #
        # ⭐ Doğrusu videonun süresine göre MOD almak. Bu, döngüdeki
        # konumu doğru veriyor — ve yalnızca kaynak sonsuz döngüde
        # olduğu için geçerli bir varsayım (kurulumumuzun özelliği).
        toplam_kare = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        sure = toplam_kare / fps if (toplam_kare > 0 and fps > 0) else 0.0
        if sure <= 0:
            return False
        konum = pts % sure

        basla = max(0.0, konum - ONCE_S)
        # Klip videonun sonunu taşarsa başa sar: döngüde zaten oraya
        # devam ediyor.
        if basla + TOPLAM_S > sure:
            basla = max(0.0, sure - TOPLAM_S)
        cap.set(cv2.CAP_PROP_POS_MSEC, basla * 1000.0)

        hedef.parent.mkdir(parents=True, exist_ok=True)
        yazici = cv2.VideoWriter(
            str(hedef), cv2.VideoWriter_fourcc(*"mp4v"), fps, (genislik, yukseklik),
        )
        if not yazici.isOpened():
            return False
        try:
            hedef_kare = int(TOPLAM_S * fps)
            yazilan = 0
            for _ in range(hedef_kare):
                ok, kare = cap.read()
                if not ok:
                    break
                yazici.write(kare)
                yazilan += 1
        finally:
            yazici.release()
    finally:
        cap.release()

    # ⚠⚠ BAŞARI KONTROLÜ ZAYIFTI VE YALAN SÖYLÜYORDU
    #
    # Eski kontrol: `hedef.exists() and st_size > 0`.
    # 257 baytlık, hiç kare içermeyen, açılamayan bir dosya bu testi
    # GEÇİYORDU — ve betik "12/12 klip kesildi" diye raporluyordu.
    #
    # ⭐ Bir çıktının var olması, kullanılabilir olması demek değil.
    # Şimdi dosya GERÇEKTEN AÇILIP ilk karesi okunuyor: kontrol, dosyanın
    # yapacağı işi yapıyor.
    if yazilan == 0 or not hedef.exists():
        return False
    dogrula = cv2.VideoCapture(str(hedef))
    try:
        ok, _ = dogrula.read()
    finally:
        dogrula.release()
    return bool(ok)


def _uret(args: argparse.Namespace) -> int:
    olaylar = asyncio.run(_olaylari_al(args.saat, args.adet))
    if not olaylar:
        print("Son pencerede olay yok.", file=sys.stderr)
        return 1

    ptssiz = sum(1 for o in olaylar if not (o.get("kanit") or {}).get("video_pts"))
    print(f"{len(olaylar)} olay · {ptssiz} tanesinde `video_pts` YOK")
    if ptssiz:
        print("  ⚠ `video_pts` içermeyen olaylar, bu alanı ekleyen sürümden")
        print("    ÖNCE yazılmış olanlardır. Onlar doğrulanamaz.")

    satirlar: list[dict[str, Any]] = []
    kesilen = 0
    for i, o in enumerate(olaylar):
        kanit = o.get("kanit") or {}
        pts = kanit.get("video_pts")
        if pts is None:
            continue
        ad = f"{o['camera']}_{float(pts):08.2f}_{i:03d}.mp4"
        hedef = CIKTI / str(o["tur"]) / ad
        ok = _kes(str(o["camera"]), float(pts), hedef)
        kesilen += int(ok)
        satirlar.append({
            "klip": str(hedef.relative_to(CIKTI)) if ok else "KESILEMEDI",
            "kamera": o["camera"],
            "tur": o["tur"],
            "ciddiyet": o["ciddiyet"],
            "skor": round(float(o["skor"]), 3),
            "video_pts": round(float(pts), 2),
            "ts": str(o["ts"]),
            # ⬇ ELLE DOLDURULACAK: 1 = gerçek olay · 0 = yanlış alarm
            #    boş = emin değilim (ANALİZ DIŞI bırakılır)
            "dogru": "",
            "not": "",
        })

    CIKTI.mkdir(parents=True, exist_ok=True)
    with CSV_YOLU.open("w", newline="", encoding="utf-8") as f:
        yazici = csv.DictWriter(f, fieldnames=list(satirlar[0].keys()))
        yazici.writeheader()
        yazici.writerows(satirlar)

    print(f"\n{kesilen}/{len(satirlar)} klip kesildi → {CIKTI}")
    print(f"etiket şablonu: {CSV_YOLU}")
    print("\nŞimdi: klipleri izle, CSV'de `dogru` sütununu doldur (1/0/boş).")
    print("Sonra: uv run python scripts/alarm_klipleri.py --ozet")
    return 0


def _ozet() -> int:
    if not CSV_YOLU.exists():
        print(f"Şablon yok: {CSV_YOLU}", file=sys.stderr)
        return 1
    with CSV_YOLU.open(encoding="utf-8") as f:
        satirlar = list(csv.DictReader(f))

    etiketli = [s for s in satirlar if s.get("dogru") in ("0", "1")]
    if not etiketli:
        print("Hiç etiket girilmemiş.", file=sys.stderr)
        return 1

    print(f"toplam {len(satirlar)} alarm · etiketli {len(etiketli)} "
          f"· emin değil/boş {len(satirlar) - len(etiketli)}\n")
    print(f"{'tür':<14}{'etiketli':>9}{'gerçek':>8}{'yanlış':>8}{'kesinlik':>10}")
    turler: dict[str, list[str]] = {}
    for s in etiketli:
        turler.setdefault(s["tur"], []).append(s["dogru"])
    for tur, degerler in sorted(turler.items(), key=lambda kv: -len(kv[1])):
        g = degerler.count("1")
        y = degerler.count("0")
        print(f"{tur:<14}{len(degerler):>9}{g:>8}{y:>8}{g / len(degerler):>10.2f}")

    g = sum(1 for s in etiketli if s["dogru"] == "1")
    print(f"\n⭐ GENEL KESİNLİK (precision): {g / len(etiketli):.3f}")
    print(f"   yanlış alarm oranı: {1 - g / len(etiketli):.3f}")
    print("\n⚠ Bu bir KESİNLİK ölçüsüdür, duyarlılık DEĞİL: yalnızca")
    print("  sistemin ürettiği alarmlara bakıldı. Kaçırılan olaylar")
    print("  (yanlış negatif) bu yöntemle ölçülemez — onun için")
    print("  videoların tamamının etiketlenmesi gerekirdi.")

    ozet_yolu = CIKTI / "etiket_ozeti.json"
    ozet_yolu.write_text(json.dumps({
        "toplam_alarm": len(satirlar),
        "etiketli": len(etiketli),
        "kesinlik": round(g / len(etiketli), 4),
        "tur_bazli": {
            t: {"etiketli": len(d), "gercek": d.count("1"), "yanlis": d.count("0")}
            for t, d in turler.items()
        },
        "yontem": "alarm anından ±3 sn klip, elle görsel doğrulama",
        "sinir": "KESİNLİK ölçüsü; duyarlılık ölçülmedi",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nyazıldı: {ozet_yolu}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Alarm doğrulama klipleri (P-68)")
    ap.add_argument("--saat", type=float, default=6.0, help="son kaç saatlik olay")
    ap.add_argument("--adet", type=int, default=60, help="en çok kaç olay")
    ap.add_argument("--ozet", action="store_true", help="etiketleri özetle")
    args = ap.parse_args()
    return _ozet() if args.ozet else _uret(args)


if __name__ == "__main__":
    raise SystemExit(main())
