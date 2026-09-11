"""Markdown makaleyi CDEJ şablonuna uygun .docx belgesine çevirir.

⚠ NEDEN AYRI BİR BETİK
Metnin tek kaynağı Markdown dosyasıdır. Word belgesi elle düzenlenirse
iki sürüm ayrışır ve hangisinin güncel olduğu belirsizleşir. Bu betik
her çalıştırıldığında belgeyi Markdown'dan YENİDEN üretir; yani
Markdown tek doğru kaynaktır (single source of truth).

Şablon kuralları (`templateCDEJ_ENG.docx` içinden okundu):
  · Yazı tipi Cambria
  · Öz 9 punto, tek satır aralığı, paragraf sonrası 6 punto
  · Gövde 10 punto
  · Tablo başlığı tablonun ÜSTÜNDE, şekil altyazısı şeklin ALTINDA
  · Sayfa numarası, üstbilgi ve altbilgi KULLANILMAZ
  · Kaynaklar APA

Kullanım:
    uv run --with python-docx python scripts/makale_docx.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

KOK = Path(__file__).resolve().parents[2]
KAYNAK = KOK / "docs" / "report" / "makale" / "05-makale-tr-final.md"
CIKTI = KOK / "docs" / "report" / "makale" / "SENTINEL-CDEJ-makale-TR.docx"
SEKIL_DIZIN = KOK / "docs" / "report" / "diagrams"

YAZI = "Cambria"


def _tipi_ayarla(calisma, punto: float, kalin=False, italik=False) -> None:
    calisma.font.name = YAZI
    calisma.font.size = Pt(punto)
    calisma.font.bold = kalin
    calisma.font.italic = italik
    # ⚠ Word, Latin olmayan karakterler için AYRI bir yazı tipi alanı
    # kullanıyor. Yalnızca `font.name` verilirse Türkçe karakterler
    # başka bir yazı tipine düşebiliyor; `eastAsia` da yazılmalı.
    r = calisma._element.rPr.rFonts
    r.set(qn("w:eastAsia"), YAZI)
    r.set(qn("w:cs"), YAZI)


def _paragraf(belge, metin="", punto=10.0, kalin=False, italik=False,
              hiza=WD_ALIGN_PARAGRAPH.JUSTIFY, sonra=6, once=0,
              aralik=1.0):
    par = belge.add_paragraph()
    par.alignment = hiza
    par.paragraph_format.space_after = Pt(sonra)
    par.paragraph_format.space_before = Pt(once)
    par.paragraph_format.line_spacing = aralik
    if metin:
        _zengin_metin(par, metin, punto, kalin, italik)
    return par


def _zengin_metin(par, metin: str, punto: float, kalin=False, italik=False) -> None:
    """`**kalın**`, `*italik*` ve `` `kod` `` işaretlerini biçime çevirir."""
    parcalar = re.split(r"(\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*)|`[^`]+`)", metin)
    for parca in parcalar:
        if not parca:
            continue
        k, i = kalin, italik
        if parca.startswith("**") and parca.endswith("**"):
            parca, k = parca[2:-2], True
        elif parca.startswith("*") and parca.endswith("*"):
            parca, i = parca[1:-1], True
        elif parca.startswith("`") and parca.endswith("`"):
            parca = parca[1:-1]
        c = par.add_run(parca)
        _tipi_ayarla(c, punto, k, i)


def _tablo(belge, satirlar: list[list[str]]) -> None:
    """Markdown tablo satırlarını Word tablosuna çevirir."""
    basliklar = satirlar[0]
    govde = satirlar[2:]  # satirlar[1] hizalama satiri
    t = belge.add_table(rows=1, cols=len(basliklar))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for h, baslik in zip(t.rows[0].cells, basliklar, strict=False):
        h.text = ""
        par = h.paragraphs[0]
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.paragraph_format.space_after = Pt(2)
        _zengin_metin(par, baslik, 9.0, kalin=True)
    for satir in govde:
        hucreler = t.add_row().cells
        for h, deger in zip(hucreler, satir, strict=False):
            h.text = ""
            par = h.paragraphs[0]
            par.alignment = (WD_ALIGN_PARAGRAPH.LEFT if satir.index(deger) == 0
                             else WD_ALIGN_PARAGRAPH.CENTER)
            par.paragraph_format.space_after = Pt(2)
            _zengin_metin(par, deger, 9.0)
    _paragraf(belge, "", punto=6, sonra=6)


def _md_tablo_mu(satir: str) -> bool:
    return satir.strip().startswith("|") and satir.strip().endswith("|")


def _hucreler(satir: str) -> list[str]:
    return [h.strip() for h in satir.strip().strip("|").split("|")]


def main() -> int:
    if not KAYNAK.is_file():
        print(f"❌ Kaynak yok: {KAYNAK}")
        return 1
    ham = KAYNAK.read_text(encoding="utf-8").splitlines()

    belge = Document()
    # ─── Sayfa düzeni ───
    for bolum in belge.sections:
        bolum.top_margin = Cm(2.5)
        bolum.bottom_margin = Cm(2.5)
        bolum.left_margin = Cm(2.5)
        bolum.right_margin = Cm(2.5)
        # Şablon: üstbilgi/altbilgi ve sayfa numarası KULLANILMAZ.
        bolum.different_first_page_header_footer = False

    normal = belge.styles["Normal"]
    normal.font.name = YAZI
    normal.font.size = Pt(10)

    i = 0
    n = len(ham)
    while i < n:
        satir = ham[i]
        kirp = satir.strip()

        # Ayraç ve boş satırlar
        if not kirp or kirp == "---":
            i += 1
            continue

        # Yazara not kutusu: belgeye GİRMEZ
        if kirp.startswith(">"):
            i += 1
            continue

        # Tablo
        if _md_tablo_mu(kirp):
            blok = []
            while i < n and _md_tablo_mu(ham[i].strip()):
                blok.append(_hucreler(ham[i]))
                i += 1
            _tablo(belge, blok)
            continue

        # Başlıklar
        if kirp.startswith("# "):
            _paragraf(belge, kirp[2:], punto=12, kalin=True,
                      hiza=WD_ALIGN_PARAGRAPH.CENTER, sonra=12, aralik=1.15)
            i += 1
            continue
        if kirp.startswith("## "):
            baslik = kirp[3:]
            _paragraf(belge, baslik, punto=11, kalin=True,
                      hiza=WD_ALIGN_PARAGRAPH.LEFT, once=12, sonra=6)
            i += 1
            continue
        if kirp.startswith("### "):
            _paragraf(belge, kirp[4:], punto=10.5, kalin=True,
                      hiza=WD_ALIGN_PARAGRAPH.LEFT, once=8, sonra=4)
            i += 1
            continue
        if kirp.startswith("#### "):
            _paragraf(belge, kirp[5:], punto=10, kalin=True, italik=True,
                      hiza=WD_ALIGN_PARAGRAPH.LEFT, once=6, sonra=4)
            i += 1
            continue

        # Şekil yer tutucusu
        if kirp.startswith("**[ŞEKİL"):
            no = re.search(r"ŞEKİL (\d+)", kirp)
            dosya = {"1": "01-veri-akisi.png",
                     "2": "02-kademeli-isleme.png",
                     "3": "03-kimlik-dogrulama.png"}.get(
                no.group(1) if no else "", "")
            yol = SEKIL_DIZIN / dosya if dosya else None
            par = belge.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if yol and yol.is_file():
                par.add_run().add_picture(str(yol), width=Cm(16))
            else:
                c = par.add_run(f"[{kirp.strip('*[]')}]")
                _tipi_ayarla(c, 9, italik=True)
            i += 1
            continue

        # Şekil altyazısı (şeklin ALTINDA)
        if kirp.startswith("*Şekil "):
            _paragraf(belge, kirp.strip("*"), punto=9, italik=True,
                      hiza=WD_ALIGN_PARAGRAPH.CENTER, sonra=10)
            i += 1
            continue

        # Tablo başlığı (tablonun ÜSTÜNDE)
        if kirp.startswith("*Tablo "):
            _paragraf(belge, kirp.strip("*"), punto=9, italik=True,
                      hiza=WD_ALIGN_PARAGRAPH.CENTER, once=8, sonra=3)
            i += 1
            continue

        # Öz ve Abstract gövdesi 9 punto
        punto = 10.0
        if kirp.startswith("**Anahtar Kelimeler:**") or kirp.startswith("**Keywords:**"):
            punto = 9.0
        _paragraf(belge, kirp, punto=punto)
        i += 1

    # Öz paragrafını 9 puntoya indir: başlıktan sonraki ilk gövde
    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    belge.save(CIKTI)
    print(f"yazıldı: {CIKTI.relative_to(KOK)}")
    print(f"paragraf: {len(belge.paragraphs)} · tablo: {len(belge.tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
