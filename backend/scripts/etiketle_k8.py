"""K8 için elle etiketleme aracı — "kavga kaçıncı saniyede başlıyor?"

Neden bu araca ihtiyaç var
--------------------------
K8 kriteri (PLAN §1.4): *"erken uyarı avansı ≥ 2 saniye"* — yani sistem
olayı, olay OLMADAN önce haber vermeli. Bunu ölçmek için iki zamana
ihtiyaç var:

    (a) sistemin alarm verdiği an      → boru hattından çıkıyor
    (b) olayın gerçekten başladığı an  → ELDE YOK

⚠ RWF-2000 ETİKETİ (b)'Yİ VERMİYOR — ve K8'in zor olmasının sebebi bu
RWF etiketi **klip seviyesinde**: "bu 5 saniyelik klipte kavga var."
Kavganın kaçıncı saniyede başladığını söylemiyor. Literatürdeki
şiddet tespiti çalışmalarının neredeyse tamamı bu etiketle yetiniyor
ve "var/yok" doğruluğu raporluyor.

⭐ **Projenin özgün katkısı tam burada:** literatür "şiddet var mı"
diye soruyor, biz "kaç saniye önce söyleyebildik" diye soruyoruz.
İkinci soru bir gözetim sisteminde birincisinden daha değerli —
olaydan sonra doğru tespit etmek adli kayıt, olaydan önce haber vermek
müdahale imkânıdır.

Bu ayrımı ölçebilmenin bedeli, (b)'yi elle üretmek.

Nasıl kullanılır
----------------
    uv run python scripts/etiketle_k8.py --adet 25

Her klip için bir pencere açılır. Tuşlar:

    BOŞLUK  oynat / duraklat
    → / ←   bir kare ileri / geri
    D / A   on kare ileri / geri
    S       ŞU ANKİ KAREYİ "kavganın başladığı an" olarak İŞARETLE
    R       baştan oynat
    N       bu klibi ATLA (belirsizse — atlamak, tahmin etmekten iyi)
    Q       kaydet ve çık

⚠ ATLAMAK BİR SEÇENEK VE KULLANILMALI
Kavganın nerede başladığı belirsizse (klip zaten kavganın ortasında
başlıyorsa, ya da itişme mi şakalaşma mı belli değilse) **N'e bas.**
Belirsiz bir etiketi zorlamak, ölçüme gürültü katar ve K8 sayısını
sahte bir kesinlikle raporlamamıza yol açar.

⚠ ETİKETLEYİCİ TARAFLILIĞI — raporda yazılacak bilinen sınır
Etiketi, sistemi yazan kişi koyuyor. "Kavga burada başladı" kararı
öznel ve sistemin ne zaman alarm verdiğini bilen biri farkında
olmadan etiketi oraya yaklaştırabilir. İki azaltma uygulanıyor:

  1. Etiketleme, skorlamadan ÖNCE ve skorlar GÖRÜLMEDEN yapılıyor —
     bu araç boru hattını hiç çalıştırmıyor, sadece video gösteriyor.
  2. Klip sırası karıştırılıyor (sabit tohumla) ki dosya adına göre
     sistematik bir eğilim oluşmasın.

Gerçek çözüm bağımsız iki etiketleyici ve uyum katsayısı olurdu; tek
kişilik bir staj projesinde bu yok ve **eksik olarak raporlanacak.**

Çıktı
-----
`data/annotations/rwf_k8.json`

    {
      "olusturuldu": "...",
      "kaynak": "RWF-2000 val/fight",
      "yontem": "elle, tek etiketleyici, skorlar görülmeden",
      "etiketler": {"KLIP_ADI.avi": {"baslangic_s": 2.13, "kare": 64}},
      "atlananlar": ["...", ...]
    }
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RWF_FIGHT = PROJECT_ROOT / "data" / "datasets" / "RWF-2000" / "val" / "fight"
CIKTI = PROJECT_ROOT / "data" / "annotations" / "rwf_k8.json"

# ⚠ `evaluate_rwf.py` ile AYNI tohum. Aynı tohum, aynı sıralama demek;
# etiketlenen klipler ile skorlanan klipler örtüşsün diye.
TOHUM = 42


def _mevcut() -> dict[str, Any]:
    """Varsa önceki etiketleri yükler — iş yarıda bırakılabilsin.

    ⚠ 25 klip etiketlemek yaklaşık bir saat. Tek oturumda bitirmeyi
    zorunlu kılmak, yorgun etiketlemeye yol açar ve etiketin kalitesi
    ölçümün tavanıdır.
    """
    if CIKTI.is_file():
        try:
            return dict(json.loads(CIKTI.read_text(encoding="utf-8")))
        except Exception:
            print("⚠ mevcut etiket dosyası okunamadı, yenisi yazılacak", file=sys.stderr)
    return {}


def _kaydet(etiketler: dict[str, Any], atlananlar: list[str]) -> None:
    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    CIKTI.write_text(
        json.dumps(
            {
                "olusturuldu": datetime.now(UTC).isoformat(),
                "kaynak": "RWF-2000 val/fight",
                "yontem": "elle, tek etiketleyici, boru hattı skorları görülmeden",
                "bilinen_sinir": (
                    "tek etiketleyici; bağımsız ikinci etiketleyici ve uyum "
                    "katsayısı yok — raporda böyle yazılacak"
                ),
                "etiketler": etiketler,
                "atlananlar": atlananlar,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="K8 — kavga başlangıcı elle etiketleme")
    ap.add_argument("--adet", type=int, default=25, help="kaç klip etiketlenecek")
    args = ap.parse_args()

    import cv2

    if not RWF_FIGHT.is_dir():
        print(f"RWF kavga klipleri yok: {RWF_FIGHT}", file=sys.stderr)
        return 1

    onceki = _mevcut()
    etiketler: dict[str, Any] = dict(onceki.get("etiketler", {}))
    atlananlar: list[str] = list(onceki.get("atlananlar", []))

    klipler = sorted(RWF_FIGHT.glob("*.avi"))
    random.Random(TOHUM).shuffle(  # noqa: S311 — kripto değil, tekrarlanabilir sıra
        klipler)
    # Zaten karar verilmiş olanları atla — kaldığı yerden devam etsin.
    kalan = [
        y for y in klipler if y.name not in etiketler and y.name not in atlananlar
    ]
    hedef = max(0, args.adet - len(etiketler))
    kalan = kalan[:hedef]

    print(f"etiketli: {len(etiketler)} · atlanan: {len(atlananlar)} · "
          f"bu oturumda: {len(kalan)}")
    if not kalan:
        print("hedefe ulaşıldı — etiketleme tamam.")
        return 0
    print(
        "\nTUŞLAR  BOŞLUK oynat/dur · ←/→ kare · A/D on kare\n"
        "        S BAŞLANGICI İŞARETLE · R baştan · N atla · Q çık\n"
        "⚠ Belirsizse N'e bas. Tahmin etmek, atlamaktan kötüdür.\n"
    )

    for sira, yol in enumerate(kalan, 1):
        cap = cv2.VideoCapture(str(yol))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        kareler: list[Any] = []
        while True:
            ok, kare = cap.read()
            if not ok:
                break
            kareler.append(kare)
        cap.release()
        if not kareler:
            print(f"  {yol.name}: okunamadı, atlanıyor")
            atlananlar.append(yol.name)
            continue

        i = 0
        oynuyor = True
        pencere = f"K8 etiketleme [{sira}/{len(kalan)}] {yol.name}"
        cv2.namedWindow(pencere, cv2.WINDOW_NORMAL)
        karar: str | None = None

        while karar is None:
            kare = kareler[i].copy()
            saniye = i / fps
            # Üst şeritte konum bilgisi — etiketleyici hangi saniyede
            # olduğunu görmeden karar veremez.
            cv2.rectangle(kare, (0, 0), (kare.shape[1], 28), (0, 0, 0), -1)
            cv2.putText(
                kare,
                f"{saniye:5.2f}s  kare {i}/{len(kareler) - 1}"
                f"   {'>' if oynuyor else '||'}   [S]=baslangic [N]=atla [Q]=cik",
                (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1,
            )
            cv2.imshow(pencere, kare)

            # Oynarken kısa bekleme (yaklaşık gerçek hız), duraklatınca
            # tuş bekle. `waitKey(0)` duraklamada CPU yakmıyor.
            tus = cv2.waitKey(int(1000 / fps) if oynuyor else 0) & 0xFF

            if oynuyor and tus == 255:  # tuşa basılmadı, oynamaya devam
                i = min(i + 1, len(kareler) - 1)
                if i == len(kareler) - 1:
                    oynuyor = False  # sonda dur, başa sarma
                continue

            if tus == ord(" "):
                oynuyor = not oynuyor
            elif tus in (ord("d"), 83):  # d ya da sağ ok
                oynuyor = False
                i = min(i + (10 if tus == ord("d") else 1), len(kareler) - 1)
            elif tus in (ord("a"), 81):  # a ya da sol ok
                oynuyor = False
                i = max(i - (10 if tus == ord("a") else 1), 0)
            elif tus == ord("r"):
                i, oynuyor = 0, True
            elif tus == ord("s"):
                etiketler[yol.name] = {
                    "baslangic_s": round(saniye, 3),
                    "kare": i,
                    "kaynak_fps": round(fps, 3),
                }
                print(f"  ✓ {yol.name}: {saniye:.2f}s")
                karar = "etiket"
            elif tus == ord("n"):
                atlananlar.append(yol.name)
                print(f"  – {yol.name}: atlandı (belirsiz)")
                karar = "atla"
            elif tus == ord("q"):
                karar = "cik"

        cv2.destroyWindow(pencere)
        # ⚠ HER KLİPTEN SONRA KAYDEDİLİYOR. Bir saatlik elle işi
        # program çökmesine ya da yanlış tuşa emanet etmek olmaz.
        _kaydet(etiketler, atlananlar)
        if karar == "cik":
            break

    cv2.destroyAllWindows()
    _kaydet(etiketler, atlananlar)
    print(f"\nyazıldı: {CIKTI.relative_to(PROJECT_ROOT)}")
    print(f"  etiketli {len(etiketler)} · atlanan {len(atlananlar)}")
    if len(etiketler) < 15:
        print(
            "⚠ 15'ten az etiket var. K8 sayısı bu örneklemle çok gürültülü\n"
            "  olur; en az 20 hedeflenmeli (YOL-HARITASI §1.2).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
