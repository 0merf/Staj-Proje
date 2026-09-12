"""Staj raporu Markdown'unu bölüm şablonuna uygun .docx belgesine çevirir.

⚠ NEDEN AYRI BİR BETİK
Metnin tek kaynağı Markdown dosyasıdır. Word belgesi elle düzenlenirse
iki sürüm ayrışır. Bu betik belgeyi her çalıştırıldığında Markdown'dan
YENİDEN üretir.

Şablon kuralları (`docs/report/Staj raporu.docx` içinden okundu):
  · Times New Roman, 12 punto
  · 1,5 satır aralığı — İSTİSNA: şekil, tablo, ek, dipnot ve kaynaklar
    TEK satır aralığı
  · İki yana yaslı
  · Aynı bölümdeki paragraflar arasında BOŞ SATIR YOK
  · Sayfa numarası altta ortada — kapak ve içindekiler HARİÇ
  · Bölüm başlıkları BÜYÜK HARF + kalın; alt başlıklar yalnızca kalın
  · Şekil açıklaması şeklin ALTINDA, tablo açıklaması tablonun ÜSTÜNDE
  · Kapakta italik ve altı çizili kullanılmaz
  · Kod, raporun gövdesinde değil YALNIZCA eklerde bulunur

Kullanım:
    uv run --with python-docx python scripts/staj_raporu_docx.py
    uv run --with python-docx python scripts/staj_raporu_docx.py --dil en
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import (
    WD_ALIGN_PARAGRAPH,
    WD_BREAK,
    WD_TAB_ALIGNMENT,
    WD_TAB_LEADER,
)
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

KOK = Path(__file__).resolve().parents[2]
GORSEL_KOK = KOK / "docs" / "report"

KAYNAKLAR = {
    "tr": (GORSEL_KOK / "staj" / "01-staj-raporu-tr.md",
           GORSEL_KOK / "staj" / "SENTINEL-staj-raporu-TR.docx"),
    "en": (GORSEL_KOK / "staj" / "02-staj-raporu-en.md",
           GORSEL_KOK / "staj" / "SENTINEL-internship-report-EN.docx"),
}

YAZI = "Times New Roman"
KOD_YAZI = "Consolas"
PUNTO = 12.0
KUCUK = 10.0          # tablo hücreleri — 12 punto ile tablolar sayfaya sığmıyor
ARALIK_GOVDE = 1.5
ARALIK_TEK = 1.0

# İçindekiler ve kapak dışındaki her şeyde sayfa numarası olacağı için
# belge iki Word bölümüne ayrılıyor.
BASLIK_ICINDEKILER = ("## İÇİNDEKİLER", "## CONTENTS")
BASLIK_KAPAK = ("## KAPAK", "## COVER PAGE")


def _tipi_ayarla(calisma, punto: float, kalin=False, italik=False,
                 kod=False) -> None:
    ad = KOD_YAZI if kod else YAZI
    calisma.font.name = ad
    calisma.font.size = Pt(punto)
    calisma.font.bold = kalin
    calisma.font.italic = italik
    # ⚠ Word, Latin olmayan karakterler için AYRI bir yazı tipi alanı
    # kullanıyor. Yalnızca `font.name` verilirse Türkçe karakterler başka
    # bir yazı tipine düşebiliyor; `eastAsia` ve `cs` de yazılmalı.
    r = calisma._element.rPr.rFonts
    r.set(qn("w:eastAsia"), ad)
    r.set(qn("w:cs"), ad)


def _paragraf(belge, metin="", punto=PUNTO, kalin=False, italik=False,
              hiza=WD_ALIGN_PARAGRAPH.JUSTIFY, aralik=ARALIK_GOVDE,
              sonra=0, once=0, kod=False):
    par = belge.add_paragraph()
    par.alignment = hiza
    par.paragraph_format.line_spacing = aralik
    # Şablon: "aynı bölümdeki paragraflar arasında boş satır olmamalı"
    par.paragraph_format.space_after = Pt(sonra)
    par.paragraph_format.space_before = Pt(once)
    if metin:
        _zengin_metin(par, metin, punto, kalin, italik, kod)
    return par


def _zengin_metin(par, metin: str, punto: float, kalin=False, italik=False,
                  kod=False) -> None:
    """`**kalın**`, `*italik*` ve `` `kod` `` işaretlerini biçime çevirir."""
    if kod:
        c = par.add_run(metin)
        _tipi_ayarla(c, punto, kod=True)
        return
    parcalar = re.split(r"(\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*)|`[^`]+`)", metin)
    for parca in parcalar:
        if not parca:
            continue
        k, i, m = kalin, italik, False
        if parca.startswith("**") and parca.endswith("**"):
            parca, k = parca[2:-2], True
        elif parca.startswith("*") and parca.endswith("*"):
            parca, i = parca[1:-1], True
        elif parca.startswith("`") and parca.endswith("`"):
            parca, m = parca[1:-1], True
        c = par.add_run(parca)
        _tipi_ayarla(c, punto, k, i, kod=m)


def _sayfa_numarasi(bolum) -> None:
    """Altbilgiye ortalanmış PAGE alanı koyar."""
    altbilgi = bolum.footer
    altbilgi.is_linked_to_previous = False
    par = altbilgi.paragraphs[0]
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.line_spacing = ARALIK_TEK
    for eleman, oznitelik in (("w:fldChar", ("w:fldCharType", "begin")),
                              ("w:instrText", ("xml:space", "preserve")),
                              ("w:fldChar", ("w:fldCharType", "end"))):
        c = par.add_run()
        _tipi_ayarla(c, PUNTO)
        e = OxmlElement(eleman)
        e.set(qn(oznitelik[0]), oznitelik[1])
        if eleman == "w:instrText":
            e.text = " PAGE "
        c._element.append(e)


def _numaralandirmayi_sifirla(bolum) -> None:
    """Yeni bölümde sayfa numarası 1'den başlasın."""
    sp = bolum._sectPr
    pg = sp.find(qn("w:pgNumType"))
    if pg is None:
        pg = OxmlElement("w:pgNumType")
        sp.append(pg)
    pg.set(qn("w:start"), "1")


def _basligi_tekrarla(satir) -> None:
    """Tablo sayfaya sığmayıp bölündüğünde başlık satırı tekrar yazılsın."""
    trPr = satir._tr.get_or_add_trPr()
    e = OxmlElement("w:tblHeader")
    e.set(qn("w:val"), "true")
    trPr.append(e)


def _icindekiler_satiri(belge, metin: str, sayfa: int | None) -> None:
    """İçindekiler satırı: başlık solda, sayfa numarası sağda, arada nokta."""
    girinti = len(metin) - len(metin.lstrip())
    par = belge.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.LEFT
    par.paragraph_format.line_spacing = ARALIK_GOVDE
    par.paragraph_format.space_after = Pt(0)
    if girinti:
        par.paragraph_format.left_indent = Cm(0.8)
    if sayfa is None:
        _zengin_metin(par, metin.strip(), PUNTO)
        return
    # Sağ kenara dayalı, nokta dolgulu sekme durağı
    tabs = par.paragraph_format.tab_stops
    tabs.add_tab_stop(Cm(15.5), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
    _zengin_metin(par, f"{metin.strip()}\t{sayfa}", PUNTO)


def _sayfa_haritasi_cikar(pdf_yolu: Path,
                          aranan: dict[str, str]) -> dict[str, int]:
    """PDF'ten her başlığın hangi sayfada başladığını bulur.

    `aranan`: {içindekiler satırı: PDF'te aranacak metin}

    ⚠ Gövde sayfa numarası kapak ve içindekilerden SONRA 1'den başlıyor;
    bu yüzden PDF sayfa sırası değil, gövde numarası döndürülüyor. Ofset
    varsayılmıyor, ilk bölüm başlığının bulunduğu sayfadan ölçülüyor.
    """
    import pymupdf

    belge = pymupdf.open(pdf_yolu)
    sayfalar = [belge[no].get_text() for no in range(belge.page_count)]
    belge.close()

    ilk = next(iter(aranan.values()))
    ofset = next((no for no, m in enumerate(sayfalar) if ilk in m), 0)

    harita: dict[str, int] = {}
    for satir, metin in aranan.items():
        for no in range(ofset, len(sayfalar)):
            if metin in sayfalar[no]:
                harita[satir] = no - ofset + 1
                break
    return harita


def _tablo(belge, satirlar: list[list[str]]) -> None:
    """Markdown tablo satırlarını Word tablosuna çevirir (TEK satır aralığı)."""
    basliklar = satirlar[0]
    govde = [s for s in satirlar[2:] if s]  # satirlar[1] hizalama satırı
    t = belge.add_table(rows=1, cols=len(basliklar))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _basligi_tekrarla(t.rows[0])
    for h, baslik in zip(t.rows[0].cells, basliklar, strict=False):
        h.text = ""
        par = h.paragraphs[0]
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.paragraph_format.line_spacing = ARALIK_TEK
        par.paragraph_format.space_after = Pt(1)
        _zengin_metin(par, baslik, KUCUK, kalin=True)
    for satir in govde:
        hucreler = t.add_row().cells
        for sutun, (h, deger) in enumerate(zip(hucreler, satir, strict=False)):
            h.text = ""
            par = h.paragraphs[0]
            par.alignment = (WD_ALIGN_PARAGRAPH.LEFT if sutun == 0
                             else WD_ALIGN_PARAGRAPH.CENTER)
            par.paragraph_format.line_spacing = ARALIK_TEK
            par.paragraph_format.space_after = Pt(1)
            _zengin_metin(par, deger, KUCUK)
    _paragraf(belge, "", punto=6, aralik=ARALIK_TEK, sonra=6)


def _md_tablo_mu(satir: str) -> bool:
    s = satir.strip()
    return s.startswith("|") and s.endswith("|")


def _hucreler(satir: str) -> list[str]:
    return [h.strip() for h in satir.strip().strip("|").split("|")]


def _buyuk(metin: str, dil: str = "tr") -> str:
    """Büyük harfe çevirir.

    ⚠ Türkçe'de i → İ, ı → I. Bu kural İNGİLİZCEYE UYGULANMAZ: aynı
    dönüşüm "Introduction" sözcüğünü "İNTRODUCTİON" yapardı.
    """
    if dil != "tr":
        return metin.upper()
    return metin.replace("i", "İ").replace("ı", "I").upper()


def _icindekiler_aramalari(ham: list[str], dil: str) -> dict[str, str]:
    """İçindekiler satırları için PDF'te aranacak metinleri hazırlar.

    Üst düzey bölüm başlıkları belgede BÜYÜK HARF yazılıyor, alt başlıklar
    olduğu gibi. Arama metni bu yüzden satır türüne göre farklı.
    """
    icinde = False
    aramalar: dict[str, str] = {}
    for satir in ham:
        kirp = satir.strip()
        if kirp in BASLIK_ICINDEKILER:
            icinde = True
            continue
        if icinde and kirp.startswith("## "):
            break
        if not icinde or not kirp or kirp == "---":
            continue
        temiz = kirp.replace("&nbsp;", " ").strip()
        if re.match(r"^\d+\.\d", temiz):
            aramalar[satir] = temiz          # alt başlık: olduğu gibi
        elif re.match(r"^\d+\.", temiz):
            aramalar[satir] = _buyuk(temiz, dil)  # bölüm başlığı: BÜYÜK
    return aramalar


def uret(kaynak: Path, cikti: Path, dil: str,
         sayfalar: dict[str, int] | None = None) -> int:
    if not kaynak.is_file():
        print(f"kaynak yok: {kaynak}")
        return 1
    ham = kaynak.read_text(encoding="utf-8").splitlines()
    sayfalar = sayfalar or {}

    belge = Document()
    for bolum in belge.sections:
        bolum.top_margin = Cm(2.5)
        bolum.bottom_margin = Cm(2.5)
        bolum.left_margin = Cm(3.0)     # ciltleme payı
        bolum.right_margin = Cm(2.5)

    normal = belge.styles["Normal"]
    normal.font.name = YAZI
    normal.font.size = Pt(PUNTO)
    normal.paragraph_format.space_after = Pt(0)

    # ⚠ Kapak + içindekiler sayfa numarası ALMAZ. Bu yüzden belge iki
    # Word bölümüne ayrılıyor ve numaralandırma ikincide 1'den başlıyor.
    numara_bolumu_acildi = False
    ekler_basladi = False
    kapakta = False
    icindekilerde = False

    i, n = 0, len(ham)
    while i < n:
        satir = ham[i]
        kirp = satir.strip()

        if not kirp or kirp == "---":
            i += 1
            continue

        # ─── İçindekiler satırı: sağda sayfa numarası, arada nokta ───
        if icindekilerde and not kirp.startswith("## "):
            _icindekiler_satiri(belge, satir.replace("&nbsp;", " "),
                                sayfalar.get(satir))
            i += 1
            continue

        # Belge başlığı (dosyanın ilk `# ` satırı) kapakta zaten var
        if kirp.startswith("# "):
            i += 1
            continue

        # ─── Kod bloğu — YALNIZCA eklerde ───
        if kirp.startswith("```"):
            i += 1
            blok = []
            while i < n and not ham[i].strip().startswith("```"):
                blok.append(ham[i].rstrip())
                i += 1
            i += 1
            if not ekler_basladi:
                print("  ⚠ gövdede kod bloğu bulundu, atlandı "
                      "(şablon: kod yalnızca eklerde)")
                continue
            for kod_satiri in blok:
                _paragraf(belge, kod_satiri or " ", punto=9,
                          hiza=WD_ALIGN_PARAGRAPH.LEFT, aralik=ARALIK_TEK,
                          kod=True)
            _paragraf(belge, "", punto=6, aralik=ARALIK_TEK, sonra=6)
            continue

        # ─── Tablo ───
        if _md_tablo_mu(kirp):
            blok = []
            while i < n and _md_tablo_mu(ham[i]):
                blok.append(_hucreler(ham[i]))
                i += 1
            _tablo(belge, blok)
            continue

        # ─── Bölüm başlığı: BÜYÜK HARF + kalın ───
        if kirp.startswith("## "):
            baslik = kirp[3:]
            if kirp in BASLIK_KAPAK:
                # ⚠ Kapak METNİ gövde satırları olarak geliyor; başlığın
                # kendisi yazdırılmıyor. Kapak ortalanır, italik ve altı
                # çizili kullanılmaz (şablon §3.1).
                kapakta = True
                _paragraf(belge, "", aralik=ARALIK_GOVDE, sonra=60)
                i += 1
                continue
            kapakta = False
            icindekilerde = kirp in BASLIK_ICINDEKILER
            # İçindekiler bittikten sonra numaralı bölüm: yeni Word bölümü
            if (not numara_bolumu_acildi
                    and re.match(r"^\d+\.", baslik)):
                yeni = belge.add_section(WD_SECTION.NEW_PAGE)
                yeni.top_margin = Cm(2.5)
                yeni.bottom_margin = Cm(2.5)
                yeni.left_margin = Cm(3.0)
                yeni.right_margin = Cm(2.5)
                _numaralandirmayi_sifirla(yeni)
                _sayfa_numarasi(yeni)
                numara_bolumu_acildi = True
            elif belge.paragraphs:
                belge.paragraphs[-1].add_run().add_break(WD_BREAK.PAGE)
            if re.match(r"^\d+\.\s*(EK|APPENDIX)", _buyuk(baslik, dil)):
                ekler_basladi = True
            _paragraf(belge, _buyuk(baslik, dil), kalin=True,
                      hiza=WD_ALIGN_PARAGRAPH.LEFT, aralik=ARALIK_GOVDE,
                      sonra=10)
            i += 1
            continue

        # ─── Alt başlık: yalnızca kalın ───
        if kirp.startswith("### "):
            _paragraf(belge, kirp[4:], kalin=True,
                      hiza=WD_ALIGN_PARAGRAPH.LEFT, once=10, sonra=4)
            i += 1
            continue

        # ─── Görsel ───
        eslesme = re.match(r"^\*\*\[GORSEL:\s*(.+?)\]\*\*$", kirp)
        if eslesme:
            yol = GORSEL_KOK / eslesme.group(1).strip()
            par = belge.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.paragraph_format.line_spacing = ARALIK_TEK
            par.paragraph_format.space_before = Pt(8)
            par.paragraph_format.space_after = Pt(3)
            if yol.is_file():
                par.add_run().add_picture(str(yol), width=Cm(15.5))
            else:
                print(f"  ⚠ görsel bulunamadı: {yol}")
                c = par.add_run(f"[görsel: {eslesme.group(1)}]")
                _tipi_ayarla(c, KUCUK, italik=True)
            i += 1
            continue

        # ─── Şekil açıklaması (şeklin ALTINDA) — tek satır aralığı ───
        if re.match(r"^\*\*(Şekil|Figure) ", kirp):
            _paragraf(belge, kirp, punto=KUCUK,
                      hiza=WD_ALIGN_PARAGRAPH.JUSTIFY, aralik=ARALIK_TEK,
                      sonra=10)
            i += 1
            continue

        # ─── Tablo açıklaması (tablonun ÜSTÜNDE) — tek satır aralığı ───
        if re.match(r"^\*\*(Tablo|Table) ", kirp):
            _paragraf(belge, kirp, punto=KUCUK,
                      hiza=WD_ALIGN_PARAGRAPH.JUSTIFY, aralik=ARALIK_TEK,
                      once=8, sonra=3)
            i += 1
            continue

        # ─── Kapak satırı: ortalı, geniş aralıklı ───
        if kapakta:
            _paragraf(belge, kirp, hiza=WD_ALIGN_PARAGRAPH.CENTER,
                      aralik=ARALIK_GOVDE, sonra=8)
            i += 1
            continue

        # ─── Gövde paragrafı ───
        kirp = kirp.replace("&nbsp;", " ")
        aralik = ARALIK_TEK if ekler_basladi else ARALIK_GOVDE
        _paragraf(belge, kirp, aralik=aralik)
        i += 1

    cikti.parent.mkdir(parents=True, exist_ok=True)
    belge.save(cikti)
    print(f"yazıldı: {cikti.relative_to(KOK)}")
    print(f"  paragraf: {len(belge.paragraphs)} · tablo: {len(belge.tables)} "
          f"· bölüm: {len(belge.sections)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dil", choices=("tr", "en", "hepsi"), default="hepsi")
    ap.add_argument("--pdf", type=Path,
                    help="Birinci geçişin PDF çıktısı. Verilirse içindekiler "
                         "sayfa numaralarıyla üretilir (ikinci geçiş).")
    arg = ap.parse_args()
    diller = ("tr", "en") if arg.dil == "hepsi" else (arg.dil,)
    hata = 0
    for dil in diller:
        kaynak, cikti = KAYNAKLAR[dil]
        if not kaynak.is_file():
            if arg.dil == "hepsi":
                print(f"atlandı ({dil}): {kaynak.name} henüz yok")
                continue
            print(f"kaynak yok: {kaynak}")
            return 1
        sayfalar = None
        if arg.pdf and arg.pdf.is_file():
            ham = kaynak.read_text(encoding="utf-8").splitlines()
            sayfalar = _sayfa_haritasi_cikar(
                arg.pdf, _icindekiler_aramalari(ham, dil))
            print(f"  içindekiler: {len(sayfalar)} satır numaralandı")
        hata |= uret(kaynak, cikti, dil, sayfalar)
    return hata


if __name__ == "__main__":
    raise SystemExit(main())
