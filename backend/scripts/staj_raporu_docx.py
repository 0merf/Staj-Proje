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

⚠ GİRDİLERİ BU DEPODA DEĞİL (12.09.2026)
Bu betik depoda duruyor ama beslendiği dosyalar durmuyor:
`docs/report/staj/*.md`, `docs/report/assets/duzce-logo.png` ve
`docs/report/staj/AN02.docx` `.gitignore` içinde. Sebep, teslim
edilecek belgelerin ve kişisel form verisinin genel bir depoya
girmemesi. Depoyu klonlayan biri bu betiği OLDUĞU GİBİ çalıştıramaz;
betik burada yöntemi belgelemek için duruyor. Eksik dosyada sessizce
bozulmak yerine adını söyleyerek uyarıyor.

Kullanım:
    uv run --with python-docx python scripts/staj_raporu_docx.py
    uv run --with python-docx python scripts/staj_raporu_docx.py --dil en

İki geçişli üretim (içindekilerin sayfa numaraları için):
    1. geçiş  → .docx üret, Word ile PDF'e render et
    2. geçiş  → --pdf <render.pdf> ile tekrar üret
"""

from __future__ import annotations

import argparse
import copy
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
from docx.shared import Cm, Pt, Twips

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

KOK = Path(__file__).resolve().parents[2]
GORSEL_KOK = KOK / "docs" / "report"
# Şablonun kapağındaki logo, `Staj raporu.docx` içinden çıkarıldı
LOGO = GORSEL_KOK / "assets" / "duzce-logo.png"
# Öğrencinin doldurduğu AN02 anketi — raporun SONUNA eklenir (şablon m.31)
AN02 = GORSEL_KOK / "staj" / "AN02.docx"

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


def _sayfa_duzeni(bolum) -> None:
    """Şablonun sayfa ölçülerini uygular (A4, kenar boşlukları, çerçeve).

    Değerler `Staj raporu.docx` içindeki `w:sectPr`'den birebir alındı:
    üst 815, sağ/sol/alt 1134 twip; üstbilgi/altbilgi 709 twip.
    """
    bolum.page_width = Cm(21.0)
    bolum.page_height = Cm(29.7)
    bolum.top_margin = Twips(815)
    bolum.bottom_margin = Twips(1134)
    bolum.left_margin = Twips(1134)
    bolum.right_margin = Twips(1134)
    bolum.header_distance = Twips(709)
    bolum.footer_distance = Twips(709)
    _sayfa_cercevesi(bolum)


def _sayfa_cercevesi(bolum) -> None:
    """Şablondaki çift çizgili sayfa çerçevesi.

    ⚠ Kenarlara göre FARKLI stil: üst ve sol `thinThickMediumGap`, alt ve
    sağ `thickThinMediumGap`. Şablonda böyle olduğu için aynen kopyalandı;
    dördünü de aynı yapmak görünür bir fark yaratıyor.
    """
    sp = bolum._sectPr
    for eski in sp.findall(qn("w:pgBorders")):
        sp.remove(eski)
    kenarlik = OxmlElement("w:pgBorders")
    kenarlik.set(qn("w:offsetFrom"), "page")
    for kenar, stil in (("top", "thinThickMediumGap"),
                        ("left", "thinThickMediumGap"),
                        ("bottom", "thickThinMediumGap"),
                        ("right", "thickThinMediumGap")):
        e = OxmlElement(f"w:{kenar}")
        e.set(qn("w:val"), stil)
        e.set(qn("w:sz"), "24")
        e.set(qn("w:space"), "30")
        e.set(qn("w:color"), "auto")
        kenarlik.append(e)
    # w:pgBorders, sectPr içinde w:cols'tan ÖNCE gelmeli; şemaya
    # uymayan sıralamada Word dosyayı bozuk sayıyor.
    ref = sp.find(qn("w:cols"))
    if ref is not None:
        ref.addprevious(kenarlik)
    else:
        sp.append(kenarlik)


def _hucre_kenarliklari(tablo, dis_ust: str, dis_alt: str) -> None:
    """Kaşe tablosunun şablondaki kenarlık stilini uygular."""
    tblPr = tablo._tbl.tblPr
    for eski in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(eski)
    k = OxmlElement("w:tblBorders")
    for kenar, stil, kalinlik in (("top", dis_ust, "24"), ("left", dis_ust, "24"),
                                  ("bottom", dis_alt, "24"), ("right", dis_alt, "24"),
                                  ("insideH", "single", "4"),
                                  ("insideV", "single", "4")):
        e = OxmlElement(f"w:{kenar}")
        e.set(qn("w:val"), stil)
        e.set(qn("w:sz"), kalinlik)
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), "auto")
        k.append(e)
    tblPr.append(k)


def _kase_ustbilgisi(bolum, dil: str) -> None:
    """Şablondaki 'Firma Adı / Sorumlu Mühendis' kaşe kutusunu kurar.

    Staj kurallarının 'her sayfada firma kaşe imzası olmalı' maddesini
    karşılayan yer burası. Alt satır boş bırakılıyor: kaşe oraya basılacak.
    """
    ustbilgi = bolum.header
    ustbilgi.is_linked_to_previous = False
    for p in list(ustbilgi.paragraphs):
        p._element.getparent().remove(p._element)
    t = ustbilgi.add_table(rows=2, cols=2, width=Twips(10207))
    t.autofit = False
    _hucre_kenarliklari(t, "thinThickLargeGap", "thickThinLargeGap")
    for satir in t.rows:
        satir.cells[0].width = Twips(5921)
        satir.cells[1].width = Twips(4286)
    sol, sag = (("Firma Adı", "Sorumlu Mühendis\nUnvan, İsim, İmza, Kaşe")
                if dil == "tr" else
                ("Company Name", "Responsible Engineer\nTitle, Name, Signature, Stamp"))
    for hucre, metin, punto, kalin in ((t.rows[0].cells[0], sol, 11.0, False),
                                       (t.rows[0].cells[1], sag, 9.0, True)):
        hucre.text = ""
        for sira, parca in enumerate(metin.split("\n")):
            par = hucre.paragraphs[0] if sira == 0 else hucre.add_paragraph()
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            par.paragraph_format.line_spacing = ARALIK_TEK
            par.paragraph_format.space_after = Pt(0)
            c = par.add_run(parca)
            _tipi_ayarla(c, punto, kalin=kalin)
    # İkinci satır kaşe için boş ve yüksek bırakılıyor (şablon: 874 twip)
    _satir_yuksekligi(t.rows[1], 874)
    # Üstbilgiden sonra gövdeye yapışmasın
    son = ustbilgi.add_paragraph()
    son.paragraph_format.space_after = Pt(0)
    son.paragraph_format.line_spacing = ARALIK_TEK
    _tipi_ayarla(son.add_run(""), 2.0)


def _satir_yuksekligi(satir, twip: int) -> None:
    trPr = satir._tr.get_or_add_trPr()
    e = OxmlElement("w:trHeight")
    e.set(qn("w:val"), str(twip))
    trPr.append(e)


def _kapak_sayfasi(belge, ham: list[str], dil: str) -> None:
    """Şablonun kapak düzenini birebir kurar: logo, kurum, başlık.

    Ölçüler `Staj raporu.docx` kapağından alındı: logo 5,93 × 3,86 cm,
    kurum satırları 16 punto, "Staj Raporu" başlığı 28 punto kalın.
    """
    # ⚠ Boşluklar boş paragraf SAYARAK değil, punto cinsinden AÇIKÇA
    # veriliyor. Boş paragraf saymak yazı tipi ölçüsüne bağlı; şablonun
    # kapağıyla hizalamak için ölçülebilir bir değer gerekiyor.
    if LOGO.is_file():
        par = belge.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.paragraph_format.line_spacing = ARALIK_TEK
        par.paragraph_format.space_before = Pt(78)   # logo üstü ~2,75 cm
        par.paragraph_format.space_after = Pt(0)
        par.add_run().add_picture(str(LOGO), width=Cm(5.93), height=Cm(3.86))
    else:
        print(f"  ⚠ logo bulunamadı: {LOGO}")

    kurum = (("T.C. DÜZCE ÜNİVERSİTESİ", "MÜHENDİSLİK FAKÜLTESİ",
              "BİLGİSAYAR MÜHENDİSLİĞİ BÖLÜMÜ")
             if dil == "tr" else
             ("DUZCE UNIVERSITY", "FACULTY OF ENGINEERING",
              "COMPUTER ENGINEERING DEPARTMENT"))
    for sira, satir in enumerate(kurum):
        _paragraf(belge, satir, punto=16.0, hiza=WD_ALIGN_PARAGRAPH.CENTER,
                  aralik=ARALIK_TEK, once=150 if sira == 0 else 0)

    _paragraf(belge, "Staj Raporu" if dil == "tr" else "Internship Report",
              punto=28.0, kalin=True, hiza=WD_ALIGN_PARAGRAPH.CENTER,
              aralik=ARALIK_TEK, once=112)

    # Kapaktaki künye satırları kaynak dosyadan geliyor
    for sira, satir in enumerate(_kapak_kunyesi(ham)):
        _paragraf(belge, satir, punto=13.0, hiza=WD_ALIGN_PARAGRAPH.CENTER,
                  aralik=ARALIK_TEK, once=30 if sira == 0 else 0, sonra=6)


def _kapak_kunyesi(ham: list[str]) -> list[str]:
    """Kaynaktaki kapak bloğundan yalnızca künye satırlarını ayıklar.

    Kurum adı ve "Staj Raporu" başlığı `_kapak_sayfasi` içinde
    şablondaki puntolarla yazıldığı için burada ATLANIYOR; yoksa
    iki kez basılırlardı.
    """
    icinde, kunye = False, []
    atla = ("T.C. DÜZCE", "MÜHENDİSLİK FAKÜLTESİ", "BİLGİSAYAR MÜHENDİSLİĞİ",
            "STAJ RAPORU", "REPUBLIC OF TURKEY", "DUZCE UNIVERSITY",
            "FACULTY OF ENGINEERING", "COMPUTER ENGINEERING DEPARTMENT",
            "INTERNSHIP REPORT")
    for satir in ham:
        kirp = satir.strip()
        if kirp in BASLIK_KAPAK:
            icinde = True
            continue
        if icinde and kirp.startswith("## "):
            break
        if not icinde or not kirp or kirp == "---":
            continue
        if any(kirp.strip("*").upper().startswith(a) for a in atla):
            continue
        kunye.append(kirp)
    return kunye


def _an02_ekle(belge, dil: str) -> bool:
    """AN02 (Öğrenci Staj Değerlendirme Anketi) formunu raporun SONUNA ekler.

    Şablon kuralı 31: *"AN02 form must be uploaded at the end of the
    internship report."*

    ⚠ Form yeniden YAZILMIYOR, kaynak belgeden XML olarak kopyalanıyor.
    Yeniden yazmak, öğrencinin doldurduğu alanları ve anketin işaretleme
    kutularını bozma riski taşıyor; kopyalama birebir aynısını veriyor.
    `w:sectPr` atlanıyor, yoksa AN02'nin sayfa düzeni raporunkini ezer.
    """
    if not AN02.is_file():
        print(f"  ⚠ AN02 bulunamadı, eklenmedi: {AN02}")
        return False
    if belge.paragraphs:
        belge.paragraphs[-1].add_run().add_break(WD_BREAK.PAGE)
    _paragraf(belge,
              "EK F — AN02 ÖĞRENCİ STAJ DEĞERLENDİRME ANKETİ" if dil == "tr"
              else "APPENDIX F — AN02 STUDENT INTERNSHIP EVALUATION SURVEY",
              kalin=True, hiza=WD_ALIGN_PARAGRAPH.LEFT, sonra=10)
    kaynak = Document(AN02)
    kopyalanan = 0
    for oge in kaynak.element.body:
        if oge.tag == qn("w:sectPr"):
            continue
        belge.element.body.append(copy.deepcopy(oge))
        kopyalanan += 1
    print(f"  AN02 eklendi ({kopyalanan} öğe)")
    return True


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
    ilk_bolum = belge.sections[0]
    _sayfa_duzeni(ilk_bolum)
    # ⚠ Kapakta kaşe kutusu YOK (şablon da böyle), içindekilerde VAR.
    ilk_bolum.different_first_page_header_footer = True
    _kase_ustbilgisi(ilk_bolum, dil)

    normal = belge.styles["Normal"]
    normal.font.name = YAZI
    normal.font.size = Pt(PUNTO)
    normal.paragraph_format.space_after = Pt(0)

    # ⚠ Kapak + içindekiler sayfa numarası ALMAZ. Bu yüzden belge iki
    # Word bölümüne ayrılıyor ve numaralandırma ikincide 1'den başlıyor.
    # Kapak sayfası şablondaki düzenle kuruluyor (logo, 16/28 punto)
    _kapak_sayfasi(belge, ham, dil)

    numara_bolumu_acildi = False
    ekler_basladi = False
    kapakta = False       # kapak bloğunun gövde satırlarını atlamak için
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
                # ⚠ Kapak zaten `_kapak_sayfasi` ile kuruldu. Buradaki
                # satırlar aynı içeriğin kaynaktaki hâli; ATLANIYOR,
                # yoksa kapak iki kez basılır.
                kapakta = True
                i += 1
                continue
            kapakta = False
            icindekilerde = kirp in BASLIK_ICINDEKILER
            # İçindekiler bittikten sonra numaralı bölüm: yeni Word bölümü
            if (not numara_bolumu_acildi
                    and re.match(r"^\d+\.", baslik)):
                yeni = belge.add_section(WD_SECTION.NEW_PAGE)
                _sayfa_duzeni(yeni)
                yeni.different_first_page_header_footer = False
                _kase_ustbilgisi(yeni, dil)
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

        # ─── Kapak satırı: `_kapak_sayfasi` yazdı, burada atlanıyor ───
        if kapakta:
            i += 1
            continue

        # ─── Gövde paragrafı ───
        kirp = kirp.replace("&nbsp;", " ")
        aralik = ARALIK_TEK if ekler_basladi else ARALIK_GOVDE
        _paragraf(belge, kirp, aralik=aralik)
        i += 1

    _an02_ekle(belge, dil)

    cikti.parent.mkdir(parents=True, exist_ok=True)
    try:
        belge.save(cikti)
    except PermissionError:
        # ⚠ En sık sebep: dosya Word'de AÇIK. Ham traceback bunu
        # söylemediği için burada açıkça yazılıyor.
        print(f"YAZILAMADI: {cikti.name} başka bir program tarafından "
              f"kilitli.\n  Büyük ihtimalle Word'de açık; kapatıp "
              f"betiği yeniden çalıştırın.")
        return 1
    yol = cikti.relative_to(KOK) if cikti.is_relative_to(KOK) else cikti
    print(f"yazıldı: {yol}")
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
