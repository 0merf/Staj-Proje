"""Üretilen staj raporu .docx dosyasını şablon kurallarına karşı DENETLER.

⚠ NEDEN BU BETİK VAR
Bu projede iki kez, "üretildi" denen bir Word belgesi gerçekte bozuktu ve
bunu yalnızca belgeyi RENDER EDİP BAKMAK gösterdi (makaledeki `.//w:t`
hatası, boş çıkan öz kutusu). Belgenin kaydedilmesi doğru olduğunun
kanıtı değil. Bu betik, göz kararına bırakılan kontrolleri ölçülebilir
hâle getiriyor.

Denetlenenler:
  1. Kapak TEK sayfaya sığıyor mu (künye taşmamış olmalı)
  2. İçindekiler kapaktan hemen sonra ve sayfa numaralı mı
  3. Gövde sayfa numarası 1'den başlıyor mu
  4. Her sayfada sayfa çerçevesi var mı
  5. Kaşe kutusu kapak DIŞINDA her sayfada var mı
  6. Emoji / markdown artığı / yer tutucu var mı
  7. Her tablo ve şeklin numarası, başlığı ve metin içinde ATFI var mı
  8. Kaynakların hepsi metin içinde anılıyor mu
  9. Asgari sayfa sayısı (15) tutuyor mu

⚠ PDF gerekiyor: Word olmadan sayfa sınırları bilinemez. PDF yolu
verilmezse sayfaya bağlı denetimler ATLANIR ve bu açıkça yazılır.

Kullanım:
    uv run --with python-docx --with pymupdf python \
        scripts/staj_raporu_dogrula.py --dil tr --pdf <render.pdf>
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

KOK = Path(__file__).resolve().parents[2]
STAJ = KOK / "docs" / "report" / "staj"

DOSYALAR = {
    "tr": (STAJ / "01-staj-raporu-tr.md", STAJ / "SENTINEL-staj-raporu-TR.docx",
           "İÇİNDEKİLER", "Tablo", "Şekil", "KAYNAKLAR"),
    "en": (STAJ / "02-staj-raporu-en.md", STAJ / "SENTINEL-internship-report-EN.docx",
           "CONTENTS", "Table", "Figure", "RESOURCES"),
}

ASGARI_SAYFA = 15
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿"
                   "️←-⇿]")
MD_ARTIGI = ("**", "## ", "```", "[GORSEL", "&nbsp;", "](", "| ---")
# ⚠ "devam ediyor" DÜZ METİN olarak aranmaz: "çalışmaya devam ediyor"
# normal bir cümle ve yanlış alarm veriyordu. Aranan şey, makalede bir
# kez görülen parantezli yer tutucu kalıbı: "(... — devam ediyor)".
YER_TUTUCU = ("TODO", "TBD", "XXX", "yer tutucu", "placeholder",
              "(devam ediyor)", "— devam ediyor)", "doldurulacak")
# AN02 anketi rapora olduğu gibi ekleniyor ve kendi 2 tablosunu getiriyor
AN02_TABLO = 2


class Denetim:
    def __init__(self) -> None:
        self.hata: list[str] = []
        self.atlanan: list[str] = []
        self.gecen = 0

    def kontrol(self, ad: str, kosul: bool, ayrinti: str = "") -> None:
        if kosul:
            self.gecen += 1
            print(f"  [gecti] {ad}")
        else:
            self.hata.append(f"{ad}{' — ' + ayrinti if ayrinti else ''}")
            print(f"  [KALDI] {ad}{' — ' + ayrinti if ayrinti else ''}")

    def atla(self, ad: str, neden: str) -> None:
        self.atlanan.append(f"{ad} ({neden})")
        print(f"  [atlandi] {ad} — {neden}")


def _belge_metni(belge) -> str:
    parcalar = [p.text for p in belge.paragraphs]
    for t in belge.tables:
        for satir in t.rows:
            for h in satir.cells:
                parcalar.append(h.text)
    return "\n".join(parcalar)


def _kaynak_soyadlari(ham: str, kaynak_basligi: str) -> list[str]:
    """Kaynakça bölümündeki her girdinin ilk yazar soyadını çıkarır."""
    bolum = ham.split(f"## 7. {kaynak_basligi}")[-1]
    adlar = []
    for satir in bolum.splitlines():
        e = re.match(r"^([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü'-]+),", satir.strip())
        if e:
            adlar.append(e.group(1))
    return adlar


def denetle(dil: str, pdf: Path | None) -> int:
    md_yolu, docx_yolu, icindekiler, tablo_sz, sekil_sz, kaynak_sz = DOSYALAR[dil]
    print(f"\n=== {docx_yolu.name} ===")
    d = Denetim()

    if not docx_yolu.is_file():
        print(f"  belge yok: {docx_yolu}")
        return 1
    belge = Document(docx_yolu)
    metin = _belge_metni(belge)
    ham = md_yolu.read_text(encoding="utf-8")

    # ─── 1-4: sayfa yapısı (PDF gerektiriyor) ───
    if pdf and pdf.is_file():
        import pymupdf

        pdf_belge = pymupdf.open(pdf)
        sayfalar = [pdf_belge[i].get_text() for i in range(pdf_belge.page_count)]
        cizimler = [len(pdf_belge[i].get_drawings()) for i in range(pdf_belge.page_count)]
        pdf_belge.close()

        d.kontrol("kapak tek sayfa (künye taşmamış)",
                  icindekiler in sayfalar[1],
                  f"2. sayfada '{icindekiler}' yok, kapak taşmış olabilir")
        d.kontrol("içindekilerde sayfa numarası var",
                  bool(re.search(r"\.{5,}\s*\d+", sayfalar[1])),
                  "nokta dolgulu sayfa numarası bulunamadı")
        d.kontrol("kapak ve içindekilerde sayfa numarası YOK",
                  not re.search(r"^\s*\d+\s*$", sayfalar[0], re.M)
                  and not re.search(r"^\s*\d+\s*$", sayfalar[1], re.M))
        d.kontrol("gövde sayfa numarası 1'den başlıyor",
                  re.search(r"^\s*1\s*$", sayfalar[2], re.M) is not None)
        d.kontrol(f"asgari {ASGARI_SAYFA} sayfa",
                  len(sayfalar) >= ASGARI_SAYFA, f"{len(sayfalar)} sayfa")
        # ⚠ "Sayfada vektör çizim var mı" diye bakmak YETMİYOR: tablolar da
        # çizgi çiziyor ve çerçeve hiç yokken bile kontrolü geçiriyorlar
        # (bilerek bozma denemesinde 29 sayfanın 28'i yanlışlıkla geçti).
        # Bu yüzden kapak sayfası ölçülüyor: orada tablo yok, çizim varsa
        # o çizim çerçevedir.
        d.kontrol("kapakta çerçeve çizimi var", cizimler[0] > 0,
                  "kapakta hiç vektör çizim yok")
    else:
        for ad in ("kapak tek sayfa", "içindekiler sayfa numarası",
                   "gövde numarası 1'den", "asgari sayfa", "kapak çerçevesi"):
            d.atla(ad, "PDF verilmedi")

    # ─── Sayfa çerçevesi: PDF'e değil, belgenin KENDİSİNE bakılıyor ───
    cercevesiz = [i for i, b in enumerate(belge.sections)
                  if b._sectPr.find(qn("w:pgBorders")) is None]
    d.kontrol("her bölümde sayfa çerçevesi tanımlı", not cercevesiz,
              f"çerçevesiz bölümler: {cercevesiz}")

    # ─── 5: kaşe kutusu ───
    kase = [b for b in belge.sections
            if b.header.tables and "Firma" in b.header.tables[0].rows[0].cells[0].text
            or b.header.tables and "Company" in b.header.tables[0].rows[0].cells[0].text]
    d.kontrol("kaşe kutusu tüm bölümlerde", len(kase) == len(belge.sections),
              f"{len(kase)}/{len(belge.sections)} bölümde var")
    d.kontrol("kapakta kaşe kutusu YOK",
              belge.sections[0].different_first_page_header_footer)

    # ─── 6: temizlik ───
    emojiler = sorted({c for c in metin if EMOJI.match(c)})
    d.kontrol("emoji yok", not emojiler,
              ", ".join(f"{c} {unicodedata.name(c, '?')}" for c in emojiler))
    artiklar = [a for a in MD_ARTIGI if a in metin]
    d.kontrol("markdown artığı yok", not artiklar, str(artiklar))
    yer = [y for y in YER_TUTUCU if y.lower() in metin.lower()]
    d.kontrol("yer tutucu yok", not yer, str(yer))

    # ─── 7: tablo ve şekil numaralandırma ───
    for tur, sz in (("tablo", tablo_sz), ("şekil", sekil_sz)):
        numaralar = sorted(set(re.findall(rf"{sz} (\d+\.\d+)", ham)))
        atifsiz = [n for n in numaralar
                   if len(re.findall(rf"{sz} {re.escape(n)}\b", ham)) < 2]
        d.kontrol(f"her {tur} metin içinde anılıyor ({len(numaralar)} adet)",
                  not atifsiz, f"atıfsız: {atifsiz}")
    # Word'de gerçekten o kadar tablo/görsel var mı
    md_tablo = len(re.findall(r"^\*\*" + tablo_sz + r" \d", ham, re.M))
    d.kontrol(f"tablo sayısı kaynakla aynı (+ AN02'nin {AN02_TABLO} tablosu)",
              len(belge.tables) == md_tablo + AN02_TABLO,
              f"docx={len(belge.tables)} beklenen={md_tablo + AN02_TABLO}")
    d.kontrol("AN02 anketi raporun sonunda",
              "Staj Yapan Öğrencinin" in metin
              and "KATILIYORUM" in metin.upper())
    # ⚠ Kapaktaki Düzce logosu kaynakta `[GORSEL:` olarak GEÇMİYOR —
    # onu `_kapak_sayfasi` şablondan koyuyor. Bu yüzden beklenen sayı
    # kaynaktaki işaret sayısı + 1.
    md_gorsel = len(re.findall(r"\[GORSEL:", ham))
    docx_gorsel = len(belge.element.body.findall(".//" + qn("a:blip")))
    d.kontrol("görsel sayısı kaynakla aynı (+ kapak logosu)",
              docx_gorsel == md_gorsel + 1,
              f"docx={docx_gorsel} beklenen={md_gorsel + 1}")

    # ─── 8: kaynak atıfları ───
    soyadlar = _kaynak_soyadlari(ham, kaynak_sz)
    govde = ham.split(f"## 7. {kaynak_sz}")[0]
    anilmayan = [s for s in soyadlar if s not in govde]
    d.kontrol(f"tüm kaynaklar metinde anılıyor ({len(soyadlar)} adet)",
              not anilmayan, f"anılmayan: {anilmayan}")

    print(f"  → {d.gecen} geçti · {len(d.hata)} kaldı · "
          f"{len(d.atlanan)} atlandı")
    return 1 if d.hata else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dil", choices=("tr", "en", "hepsi"), default="hepsi")
    ap.add_argument("--pdf-tr", type=Path)
    ap.add_argument("--pdf-en", type=Path)
    arg = ap.parse_args()
    diller = ("tr", "en") if arg.dil == "hepsi" else (arg.dil,)
    hata = 0
    for dil in diller:
        hata |= denetle(dil, arg.pdf_tr if dil == "tr" else arg.pdf_en)
    print("\nSONUC:", "HATA VAR" if hata else "hepsi temiz")
    return hata


if __name__ == "__main__":
    raise SystemExit(main())
