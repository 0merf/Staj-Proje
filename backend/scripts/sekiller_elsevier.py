"""Makale ve staj raporu şekillerini Elsevier sanat eseri kurallarına göre çizer.

⚠ NEDEN YENİDEN ÇİZİLDİ (13.09.2026)
Danışman geri bildirimi: "grafiklerin daha iyi olması lazım ... Elsevier
formatına uygun biçimde çizdir". Eski şekiller (docs/report/diagrams/*.svg)
bir mühendislik panosu gibiydi: şeklin içine gömülü başlık, uzun açıklama
paragrafları, iç kayıt numaraları (P-66), dosya yolları, tarihler, BÜYÜK
HARF vurgular. Dergi şeklinde bunların hepsi başlığa ve metne aittir;
şekilde yalnızca mekanizma ve ölçülen değerler kalır.

Uygulanan kurallar (Elsevier "Artwork and media instructions"):
  · Boyut fiziksel ölçüde: çift sütun genişliği 190 mm
  · Yazı tipi Arial; YERLEŞTİRİLDİĞİ boyutta en küçük 7 punto
    (190 mm tasarım, 17 cm yerleşim → 8 × 0,895 = 7,16 pt)
  · Çizgi kalınlığı 0,6 punto (Elsevier alt sınırı 0,25 pt)
  · Şeklin içinde başlık YOK; başlık şekil altyazısında
  · Çok panelli şekilde (a), (b) etiketleri
  · Gri tonlu: renkli baskı olmadan da okunur
  · Çıktı: vektör PDF (yazı tipleri gömülü) + 600 dpi TIFF ve PNG

⚠ SAYILAR ELLE KOPYALANMIYOR
Çubuk grafiğin değerleri doğrudan ölçüm çıktısından okunuyor
(benchmarks/asama_kirilimi_*.json). Kutulardaki değerler makalede
doğrulanmış değerlerle aynıdır.

⚠ TAŞMA DENETİMİ OTOMATİK
Eski diyagram testi "taşma kontrolü" diyordu ama yalnızca sayfa kenarına
bakıyordu; bir etiketin başka bir kutunun altında kalmasını göremiyordu.
Burada her şekil kaydedilmeden önce: (1) her metin kendi kutusunun içinde
mi, (2) hiçbir iki metin üst üste biniyor mu, (3) hiçbir metin şeklin
dışına taşıyor mu — ölçülür. Biri bozuksa betik HATA verir, dosya yazmaz.

Kullanım:
    uv run --with matplotlib python scripts/sekiller_elsevier.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

KOK = Path(__file__).resolve().parents[2]
CIKTI = KOK / "docs" / "report" / "diagrams" / "elsevier"
OLCUM = KOK / "benchmarks"

MM = 1 / 25.4                       # inç
GENISLIK = 190.0                    # Elsevier çift sütun, mm
CIZGI = 0.6                         # punto
# ⚠ Şekiller 190 mm tasarlanıyor ama belgelere METİN GENİŞLİĞİNDE
# yerleştiriliyor: makalede 18 cm, staj raporunda 17 cm. Yerleşimde
# ölçek 170/190 = 0,895 oluyor; 7 punto tasarlanan yazı 6,3 puntoya
# düşüp Elsevier'in 7 punto alt sınırının altına iniyordu. Bu yüzden
# tasarım puntosu, EN DAR yerleşimde bile 7 puntonun üstünde kalacak
# şekilde 8 seçildi ve etkin punto kaydederken hesaplanıp yazdırılıyor.
EN_DAR_YERLESIM_MM = 170.0
ALT_SINIR_PUNTO = 7.0
PUNTO_BASLIK = 8.5
PUNTO_GOVDE = 8.0
PUNTO_ETIKET = 8.0
MUREKKEP = "#000000"
IKINCIL = "#404040"
DOLGU_VURGU = "#E4E4E4"             # GPU süreci — tek vurgu
DOLGU = "#FFFFFF"
KOYU = "#404040"                   # çubuk: GPU model çıkarımı
ACIK = "#B4B4B4"                   # çubuk: diğer aşamalar

mpl.rcParams.update({
    "font.family": "Arial",
    "font.size": PUNTO_GOVDE,
    "pdf.fonttype": 42,              # TrueType gömülü — Elsevier şartı
    "ps.fonttype": 42,
    "axes.linewidth": CIZGI,
    "xtick.major.width": CIZGI,
    "ytick.major.width": CIZGI,
    "xtick.major.size": 2.5,
    "ytick.major.size": 0,
    "savefig.dpi": 600,
})


# ─── Metinler: şekillerde görünen HER sözcük burada, dil başına ───────────
METIN = {
    "tr": {
        "kamera": ("Kamera çiftliği", ["20 video + web kamerası", "MediaMTX, RTSP",
                                       "döngüde (5–345 sn)"]),
        "alim": ("Alım süreci (CPU)", ["çözme, hareket kapısı",
                                       "örnekleme 2,84 kare/sn",
                                       "2,42 çekirdek"]),
        "cikarim": ("Çıkarım süreci (GPU)", ["tespit + takip + poz",
                                             "+ yüz ve ifade",
                                             "analiz 2,34 kare/sn",
                                             "22,65 ms/kare, 0,89 çekirdek"]),
        "analitik": ("Analitik süreci (CPU)", ["Katman A + Katman B",
                                               "füzyon + EMA", "AUC 0,869"]),
        "bellek": ("Paylaşımlı bellek", ["96 yuva × 2,76 MB", "= 265 MB"]),
        "valkey": ("Valkey akışları", ["yalnızca meta veri", "ve referans"]),
        "alarm": ("Alarm motoru", ["TimescaleDB, kanıt klibi",
                                   "kesinlik 0,895", "(19 olayda 17)"]),
        "api": ("FastAPI + React", ["REST + WebSocket", "video ayrıca WHEP ile"]),
        "caddy": ("Caddy (ters vekil)", ["TLS, tek giriş noktası",
                                         "forward_auth"]),
        "k_rtsp": "RTSP", "k_yaz": "(1) kare yaz", "k_ref": "(2) referans",
        "k_oku": "(3) oku", "k_ham": "(4) ham kare paylaşımlı bellekten okunur",
        "k_json": "JSON", "k_olay": "olay", "k_alarm": "alarm", "k_https": "HTTPS",
        "k3": "Uçtan uca gecikme: p50 378 ms, p95 652 ms",

        "a": "(a)", "b": "(b)",
        "kademeler": [
            ("Kademe 0 — hareket kapısı (CPU)",
             ["hareketsiz kamerada örnekleme 4 → 1 kare/sn",
              "yayınlanan: kamera başına 2,84 kare/sn"], False),
            ("Kademe 1 — kişi tespiti, YOLO26-s (GPU)",
             ["7,46 ms/kare"], True),
            ("Kademe 1b — takip, BoT-SORT",
             ["1,56 ms/kare"], False),
            ("Kademe 2a — poz kestirimi, YOLO26-pose (GPU)",
             ["10,96 ms/kare"], True),
            ("Kademe 2b — yüz + ifade",
             ["kapı: kişi kutusu ≥ 180 piksel → 2087 kişiden 171'i",
              "0,46 ms/kare"], False),
            ("Kademe 3 — video tabanlı eylem doğrulayıcı",
             ["planlandı, gerçekleştirilmedi"], None),
        ],
        "asama_ad": {"pose": "poz kestirimi", "detect": "kişi tespiti",
                     "track": "takip", "publish": "sonuç yayını",
                     "serialize": "serileştirme", "emotion": "yüz + ifade",
                     "slot_release": "yuva bırakma",
                     "shm_read": "paylaşımlı bellek okuma"},
        "eksen": "Kare başına maliyet (ms)",
        "gpu": "GPU model çıkarımı", "diger": "diğer aşamalar",
        "kapanis": "Aşamaların toplamı {t} ms  ·  bağımsız ölçülen döngü {p} ms",

        "tarayici": ("Tarayıcı", ["HttpOnly çerez"]),
        "vekil": ("Caddy (ters vekil)", ["TLS sonlandırma", "tek giriş noktası",
                                         "güvenlik başlıkları"]),
        "uygulama": ("Uygulama arayüzü", ["/api/v1/auth/ben",
                                          "geçerliyse 200, değilse 401"]),
        "medya": ("Medya sunucusu", ["WHEP video akışı",
                                     "doğrudan erişilemez"]),
        "ic": ("İç uç noktalar", ["/metrics", "vekilde 404"]),
        "a_https": "HTTPS", "a_sorgu": "(1) yetki sorgusu",
        "a_cevap": "(2) 200 / 401", "a_medya": "(3) yalnızca 200 ise",
        "a_ic": "dışarıya kapalı",
    },
    "en": {
        "kamera": ("Camera farm", ["20 videos + webcam", "MediaMTX, RTSP",
                                   "looped (5–345 s)"]),
        "alim": ("Ingest process (CPU)", ["decoding, motion gate",
                                          "sampling 2.84 fps",
                                          "2.42 cores"]),
        "cikarim": ("Inference process (GPU)", ["detection + tracking + pose",
                                                "+ face and expression",
                                                "analysed 2.34 fps",
                                                "22.65 ms/frame, 0.89 core"]),
        "analitik": ("Analytics process (CPU)", ["Layer A + Layer B",
                                                 "fusion + EMA", "AUC 0.869"]),
        "bellek": ("Shared memory", ["96 slots × 2.76 MB", "= 265 MB"]),
        "valkey": ("Valkey streams", ["metadata and", "references only"]),
        "alarm": ("Alert engine", ["TimescaleDB, evidence clip",
                                   "precision 0.895", "(17 of 19 events)"]),
        "api": ("FastAPI + React", ["REST + WebSocket", "video separately via WHEP"]),
        "caddy": ("Caddy (reverse proxy)", ["TLS, single entry point",
                                            "forward_auth"]),
        "k_rtsp": "RTSP", "k_yaz": "(1) write frame", "k_ref": "(2) reference",
        "k_oku": "(3) read", "k_ham": "(4) raw frame read from shared memory",
        "k_json": "JSON", "k_olay": "events", "k_alarm": "alerts",
        "k_https": "HTTPS",
        "k3": "End-to-end latency: p50 378 ms, p95 652 ms",

        "a": "(a)", "b": "(b)",
        "kademeler": [
            ("Stage 0 — motion gate (CPU)",
             ["sampling 4 → 1 fps on idle cameras",
              "published: 2.84 fps per camera"], False),
            ("Stage 1 — person detection, YOLO26-s (GPU)",
             ["7.46 ms/frame"], True),
            ("Stage 1b — tracking, BoT-SORT",
             ["1.56 ms/frame"], False),
            ("Stage 2a — pose estimation, YOLO26-pose (GPU)",
             ["10.96 ms/frame"], True),
            ("Stage 2b — face + expression",
             ["gate: person box ≥ 180 px → 171 of 2087 pass",
              "0.46 ms/frame"], False),
            ("Stage 3 — video-based action verifier",
             ["planned, not implemented"], None),
        ],
        "asama_ad": {"pose": "pose estimation", "detect": "person detection",
                     "track": "tracking", "publish": "result publishing",
                     "serialize": "serialisation", "emotion": "face + expression",
                     "slot_release": "slot release",
                     "shm_read": "shared memory read"},
        "eksen": "Cost per frame (ms)",
        "gpu": "GPU model inference", "diger": "other stages",
        "kapanis": "Sum of stages {t} ms  ·  independently measured loop {p} ms",

        "tarayici": ("Browser", ["HttpOnly cookie"]),
        "vekil": ("Caddy (reverse proxy)", ["TLS termination",
                                            "single entry point",
                                            "security headers"]),
        "uygulama": ("Application API", ["/api/v1/auth/ben",
                                         "200 if valid, otherwise 401"]),
        "medya": ("Media server", ["WHEP video stream",
                                   "not directly reachable"]),
        "ic": ("Internal endpoints", ["/metrics", "404 at the proxy"]),
        "a_https": "HTTPS", "a_sorgu": "(1) authorisation subrequest",
        "a_cevap": "(2) 200 / 401", "a_medya": "(3) only if 200",
        "a_ic": "not exposed",
    },
}


def _sayi(deger: float, dil: str, basamak: int = 2) -> str:
    """Dile göre ondalık ayırıcı: TR virgül, EN nokta."""
    s = f"{deger:.{basamak}f}"
    return s.replace(".", ",") if dil == "tr" else s


# ─── Çizim yardımcıları (mm koordinatında) ──────────────────────────────
PT_MM = 0.3528                      # 1 punto = 0,3528 mm
IC = 1.8                            # kutu iç boşluğu, mm
SATIR_MM = PUNTO_GOVDE * PT_MM * 1.32


@dataclass
class Tuval:
    fig: plt.Figure
    ax: plt.Axes
    yukseklik: float
    # (metin sanatçısı, sahibi olan kutu (x0,y0,x1,y1) ya da None)
    metinler: list = field(default_factory=list)
    kutular: list = field(default_factory=list)   # (x0,y0,x1,y1)
    cizgiler: list = field(default_factory=list)  # ((x0,y0),(x1,y1))


def _tuval(yukseklik_mm: float) -> Tuval:
    fig = plt.figure(figsize=(GENISLIK * MM, yukseklik_mm * MM))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, GENISLIK)
    ax.set_ylim(0, yukseklik_mm)
    ax.set_aspect("equal")
    ax.axis("off")
    return Tuval(fig, ax, yukseklik_mm)


def kutu_yuksekligi(satir_sayisi: int, baslik_punto: float = PUNTO_BASLIK) -> float:
    """Kutunun İÇERİKTEN hesaplanan yüksekliği, mm.

    ⚠ İlk sürümde yükseklikler sabit verilmişti ve kutuların altında
    içerikten bağımsız boşluk kalıyordu.
    """
    return IC + baslik_punto * PT_MM * 1.45 + satir_sayisi * SATIR_MM + IC


def _kutu(t: Tuval, x: float, y: float, g: float, h: float | None, baslik: str,
          satirlar: list[str], vurgu: bool = False, kesik: bool = False,
          baslik_punto: float = PUNTO_BASLIK) -> tuple[float, float, float, float]:
    """Sol üstten dolan kutu. (x, y) SOL ALT köşe, mm. h=None → içerikten."""
    if h is None:
        h = kutu_yuksekligi(len(satirlar), baslik_punto)
    t.ax.add_patch(Rectangle((x, y), g, h, linewidth=CIZGI,
                             edgecolor=MUREKKEP,
                             facecolor=DOLGU_VURGU if vurgu else DOLGU,
                             linestyle=(0, (4, 2)) if kesik else "-",
                             joinstyle="miter"))
    sinir = (x, y, x + g, y + h)
    t.kutular.append(sinir)
    ust = y + h - IC
    m = t.ax.text(x + IC, ust, baslik, fontsize=baslik_punto,
                  fontweight="bold", va="top", ha="left", color=MUREKKEP)
    t.metinler.append((m, sinir))
    ust -= baslik_punto * PT_MM * 1.45
    for s in satirlar:
        m = t.ax.text(x + IC, ust, s, fontsize=PUNTO_GOVDE, va="top",
                      ha="left", color=IKINCIL if kesik else MUREKKEP)
        t.metinler.append((m, sinir))
        ust -= SATIR_MM
    return sinir


def _cizgi(t: Tuval, xs: list[float], ys: list[float]) -> None:
    t.ax.plot(xs, ys, color=MUREKKEP, linewidth=CIZGI)
    for i in range(len(xs) - 1):
        t.cizgiler.append(((xs[i], ys[i]), (xs[i + 1], ys[i + 1])))


def _ok(t: Tuval, noktalar: list[tuple[float, float]], kesik: bool = False) -> None:
    """Kırık çizgi ok: son parça ok başlı."""
    stil = (0, (3, 2)) if kesik else "-"
    for (x0, y0), (x1, y1) in pairwise(noktalar[:-1]):
        t.ax.plot([x0, x1], [y0, y1], color=MUREKKEP, linewidth=CIZGI,
                  linestyle=stil, solid_capstyle="butt")
    (x0, y0), (x1, y1) = noktalar[-2], noktalar[-1]
    t.ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1),
                                   arrowstyle="-|>,head_length=2.2,head_width=1.1",
                                   mutation_scale=1, linewidth=CIZGI,
                                   linestyle=stil, color=MUREKKEP,
                                   shrinkA=0, shrinkB=0))
    for a, b in pairwise(noktalar):
        t.cizgiler.append((a, b))


def _etiket(t: Tuval, x: float, y: float, metin: str, ha: str = "center",
            va: str = "bottom", italik: bool = False) -> None:
    m = t.ax.text(x, y, metin, fontsize=PUNTO_ETIKET, ha=ha, va=va,
                  color=IKINCIL, fontstyle="italic" if italik else "normal")
    t.metinler.append((m, None))


# ─── Otomatik taşma / çakışma denetimi ─────────────────────────────────
def _parca_dikdortgeni_kesiyor(a, b, r) -> bool:
    """Liang–Barsky: (a,b) doğru parçası r=(x0,y0,x1,y1) dikdörtgenini kesiyor mu."""
    (px, py), (qx, qy) = a, b
    dx, dy = qx - px, qy - py
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, px - r[0]), (dx, r[2] - px), (-dy, py - r[1]), (dy, r[3] - py)):
        if p == 0:
            if q < 0:
                return False
            continue
        oran = q / p
        if p < 0:
            t0 = max(t0, oran)
        else:
            t1 = min(t1, oran)
        if t0 > t1:
            return False
    return True


def _denetle(t: Tuval, ad: str) -> list[str]:
    """Dört kontrol. Hiçbiri göz kararı değil, ölçü.

    1. Her metin şeklin içinde.
    2. Kutu içi metin kendi kutusunun içinde.
    3. İki metin üst üste binmiyor.
    4. ⚠ SONRADAN EKLENDİ: serbest etiket hiçbir kutunun üstüne binmiyor
       ve hiçbir ok/çizgi hiçbir metnin üstünden geçmiyor. İlk sürümde
       bu iki kontrol YOKTU; denetim "temiz" dediği hâlde ok etiketleri
       kutu kenarlarının üstündeydi — ancak şekle bakınca görüldü.
    """
    t.fig.canvas.draw()
    r = t.fig.canvas.get_renderer()
    donustur = t.ax.transData.inverted()
    kutular = []
    for m, sinir in t.metinler:
        bb = m.get_window_extent(renderer=r)
        (x0, y0), (x1, y1) = donustur.transform([(bb.x0, bb.y0), (bb.x1, bb.y1)])
        kutular.append((m.get_text(), (x0, y0, x1, y1), sinir))

    hatalar = []
    tol = 0.3                                      # mm
    for metin, (x0, y0, x1, y1), sinir in kutular:
        if x0 < -tol or y0 < -tol or x1 > GENISLIK + tol or y1 > t.yukseklik + tol:
            hatalar.append(f"{ad}: şeklin DIŞINA taşıyor: '{metin}'")
        if sinir is not None:
            sx0, sy0, sx1, sy1 = sinir
            if x0 < sx0 - tol or x1 > sx1 - 0.6 or y0 < sy0 + 0.4 or y1 > sy1 + tol:
                hatalar.append(f"{ad}: kutusundan TAŞIYOR: '{metin}' "
                               f"(metin x1={x1:.1f} kutu x1={sx1:.1f}, "
                               f"metin y0={y0:.1f} kutu y0={sy0:.1f})")
        else:
            for k in t.kutular:
                if x0 < k[2] + 0.5 and k[0] - 0.5 < x1 and y0 < k[3] + 0.5 \
                        and k[1] - 0.5 < y1:
                    hatalar.append(f"{ad}: etiket KUTUYA biniyor: '{metin}'")
                    break
        daralt = (x0 + 0.15, y0 + 0.15, x1 - 0.15, y1 - 0.15)
        for a, b in t.cizgiler:
            if _parca_dikdortgeni_kesiyor(a, b, daralt):
                hatalar.append(f"{ad}: ok/çizgi METNİN üstünden geçiyor: "
                               f"'{metin}'")
                break
    for i in range(len(kutular)):
        for j in range(i + 1, len(kutular)):
            a, b = kutular[i][1], kutular[j][1]
            if a[0] < b[2] - tol and b[0] < a[2] - tol \
                    and a[1] < b[3] - tol and b[1] < a[3] - tol:
                hatalar.append(f"{ad}: ÜST ÜSTE: '{kutular[i][0]}' ⟷ "
                               f"'{kutular[j][0]}'")
    return hatalar


def _kaydet(t: Tuval, ad: str, dil: str) -> None:
    hatalar = _denetle(t, f"{dil}/{ad}")
    if hatalar:
        plt.close(t.fig)
        raise SystemExit("ŞEKİL DENETİMİ BAŞARISIZ — dosya yazılmadı:\n  "
                         + "\n  ".join(hatalar))
    etkin = PUNTO_GOVDE * EN_DAR_YERLESIM_MM / GENISLIK
    if etkin < ALT_SINIR_PUNTO:
        plt.close(t.fig)
        raise SystemExit(f"{dil}/{ad}: en dar yerleşimde yazı {etkin:.2f} pt, "
                         f"alt sınır {ALT_SINIR_PUNTO} pt — dosya yazılmadı")
    hedef = CIKTI / dil
    hedef.mkdir(parents=True, exist_ok=True)
    for uzanti in ("pdf", "png", "tiff"):
        ek = {"pil_kwargs": {"compression": "tiff_lzw"}} if uzanti == "tiff" else {}
        t.fig.savefig(hedef / f"{ad}.{uzanti}", facecolor="white", **ek)
    plt.close(t.fig)
    print(f"  yazıldı: {dil}/{ad}.{{pdf,png,tiff}} · denetim temiz "
          f"({len(t.metinler)} metin, {len(t.cizgiler)} çizgi, "
          f"{len(t.kutular)} kutu) · 17 cm'de en küçük yazı {etkin:.2f} pt")

# ─── Şekil 1: veri akışı ────────────────────────────────────────────────
def sekil_veri_akisi(dil: str) -> None:
    tx = METIN[dil]
    ara = 10.5
    g = (GENISLIK - 4.0 - 3 * ara) / 4
    sut = [2.0 + i * (g + ara) for i in range(4)]

    ust_h = max(kutu_yuksekligi(len(tx[k][1]))
                for k in ("kamera", "alim", "cikarim", "analitik"))
    orta_h = max(kutu_yuksekligi(len(tx[k][1])) for k in ("bellek", "valkey"))
    alt_h = max(kutu_yuksekligi(len(tx[k][1])) for k in ("caddy", "api", "alarm"))

    alt_y = 2.0
    yol_y = alt_y + alt_h + 7.0            # (4) kesik yol ve etiketi
    orta_y = yol_y + 4.0
    ust_y = orta_y + orta_h + 13.0
    ayrac_y = ust_y + ust_h + 3.0
    t = _tuval(ayrac_y + 4.5)

    _kutu(t, sut[0], ust_y, g, ust_h, *tx["kamera"])
    _kutu(t, sut[1], ust_y, g, ust_h, *tx["alim"])
    _kutu(t, sut[2], ust_y, g, ust_h, *tx["cikarim"], vurgu=True)
    _kutu(t, sut[3], ust_y, g, ust_h, *tx["analitik"])
    _kutu(t, sut[1], orta_y, g, orta_h, *tx["bellek"])
    _kutu(t, sut[2], orta_y, g, orta_h, *tx["valkey"])
    _kutu(t, sut[1], alt_y, g, alt_h, *tx["caddy"])
    _kutu(t, sut[2], alt_y, g, alt_h, *tx["api"])
    _kutu(t, sut[3], alt_y, g, alt_h, *tx["alarm"])
    orta_ust = orta_y + orta_h

    # üst sıra: kamera → alım (RTSP), çıkarım → analitik (JSON)
    # ⚠ alım → çıkarım DOĞRUDAN ok yok: veri yolu Valkey + paylaşımlı
    # bellek üzerinden; doğrudan ok çizmek yanlış bir yol gösterirdi.
    ok_y = ust_y + ust_h - 8.0
    for i, anahtar in ((0, "k_rtsp"), (2, "k_json")):
        _ok(t, [(sut[i] + g, ok_y), (sut[i + 1], ok_y)])
        _etiket(t, sut[i] + g + ara / 2, ok_y + 0.8, tx[anahtar])

    # (1) alım → bellek
    x1 = sut[1] + 8.0
    _ok(t, [(x1, ust_y), (x1, orta_ust)])
    _etiket(t, x1 + 1.2, orta_ust + 1.5, tx["k_yaz"], ha="left")
    # (2) alım → Valkey (çapraz); etiket okun orta noktasının sağında
    a = (sut[1] + g - 5.0, ust_y)
    b = (sut[2] + 7.0, orta_ust)
    _ok(t, [a, b])
    _etiket(t, (a[0] + b[0]) / 2 + 2.0, (a[1] + b[1]) / 2 + 0.2, tx["k_ref"],
            ha="left")
    # (3) Valkey → çıkarım
    x3 = sut[2] + g - 12.0
    _ok(t, [(x3, orta_ust), (x3, ust_y)])
    _etiket(t, x3 + 1.2, orta_ust + 1.5, tx["k_oku"], ha="left")

    # (4) ham kare: bellek → çıkarım (kesik, Valkey'in altından dolaşır)
    xk = sut[2] + g + ara / 2
    xb = sut[1] + g / 2
    _ok(t, [(xb, orta_y), (xb, yol_y), (xk, yol_y), (xk, ust_y + 5.0),
            (sut[2] + g, ust_y + 5.0)], kesik=True)
    _etiket(t, (xb + xk) / 2, yol_y - 0.8, tx["k_ham"], va="top", italik=True)

    # analitik → alarm → API → Caddy
    xa = sut[3] + g / 2
    _ok(t, [(xa, ust_y), (xa, alt_y + alt_h)])
    _etiket(t, xa + 1.2, (ust_y + alt_y + alt_h) / 2, tx["k_olay"], ha="left",
            va="center")
    alt_ok = alt_y + alt_h / 2 - 2.0
    _ok(t, [(sut[3], alt_ok), (sut[2] + g, alt_ok)])
    _etiket(t, sut[2] + g + ara / 2, alt_ok + 0.8, tx["k_alarm"])
    _ok(t, [(sut[2], alt_ok), (sut[1] + g, alt_ok)])
    _etiket(t, sut[1] + g + ara / 2, alt_ok + 0.8, tx["k_https"])

    # Uçtan uca gecikmenin KAPSAMI: kameradan çıkarım sonucuna kadar.
    # Ayraç bunu yazıyla değil geometriyle gösteriyor (analitik dışarıda).
    x_bas, x_son = sut[0], sut[2] + g
    _cizgi(t, [x_bas, x_bas, x_son, x_son],
           [ayrac_y - 1.5, ayrac_y, ayrac_y, ayrac_y - 1.5])
    _etiket(t, (x_bas + x_son) / 2, ayrac_y + 0.7, tx["k3"])
    _kaydet(t, "sekil-1-veri-akisi", dil)


# ─── Şekil 2: kademeli işleme (a) + maliyet dağılımı (b) ───────────────
def _asama_olcumu() -> dict:
    dosyalar = sorted(OLCUM.glob("asama_kirilimi_*.json"))
    if not dosyalar:
        raise SystemExit("ölçüm yok: benchmarks/asama_kirilimi_*.json")
    return json.loads(dosyalar[-1].read_text(encoding="utf-8"))


def sekil_kademeler(dil: str) -> None:
    tx = METIN[dil]
    olcum = _asama_olcumu()
    bp = PUNTO_GOVDE + 0.5
    bosluk = 4.5
    yukseklikler = [kutu_yuksekligi(len(s), bp) for _, s, _ in tx["kademeler"]]
    yuk = 7.0 + sum(yukseklikler) + bosluk * (len(yukseklikler) - 1) + 2.0
    t = _tuval(yuk)

    # (a) kademeler — sol yarı
    sol_x, sol_g = 7.0, 86.0
    _etiket_panel = t.ax.text(1.0, yuk - 1.0, tx["a"], fontsize=PUNTO_BASLIK,
                              fontweight="bold", va="top")
    t.metinler.append((_etiket_panel, None))
    y = yuk - 7.0
    konumlar = []
    for (baslik, satirlar, gpu), h in zip(tx["kademeler"], yukseklikler, strict=False):
        y -= h
        _kutu(t, sol_x, y, sol_g, h, baslik, satirlar, vurgu=bool(gpu),
              kesik=gpu is None, baslik_punto=bp)
        konumlar.append((y, h))
        y -= bosluk
    orta = sol_x + sol_g / 2
    for i in range(len(konumlar) - 1):
        y_ust = konumlar[i][0]
        y_alt, h_alt = konumlar[i + 1]
        _ok(t, [(orta, y_ust), (orta, y_alt + h_alt)],
            kesik=(i + 1 == len(konumlar) - 1))

    # (b) maliyet dağılımı — sağ yarı, gerçek eksen
    _etiket_panel = t.ax.text(101.0, yuk - 1.0, tx["b"], fontsize=PUNTO_BASLIK,
                              fontweight="bold", va="top")
    t.metinler.append((_etiket_panel, None))
    asamalar = olcum["asamalar_ms_kare"]
    sira = sorted(asamalar, key=lambda k: asamalar[k], reverse=True)
    toplam = olcum["olculen_toplam_ms"]
    gpu_asama = {"pose", "detect"}

    eksen_alt, eksen_ust = 24.0, yuk - 9.0
    ax = t.fig.add_axes((133.0 / GENISLIK, eksen_alt / yuk,
                         40.0 / GENISLIK, (eksen_ust - eksen_alt) / yuk))
    yler = list(range(len(sira)))[::-1]
    degerler = [asamalar[k] for k in sira]
    renkler = [KOYU if k in gpu_asama else ACIK for k in sira]
    ax.barh(yler, degerler, height=0.62, color=renkler, linewidth=0)
    ax.set_yticks(yler)
    ax.set_yticklabels([tx["asama_ad"][k] for k in sira], fontsize=PUNTO_GOVDE)
    ax.set_ylim(-0.6, len(sira) - 0.4)
    ax.set_xlim(0, 12.5)
    ax.set_xticks([0, 4, 8, 12])
    ax.set_xticklabels([_sayi(v, dil, 0) for v in (0, 4, 8, 12)],
                       fontsize=PUNTO_GOVDE)
    ax.set_xlabel(tx["eksen"], fontsize=PUNTO_GOVDE, labelpad=2)
    for kenar in ("top", "right"):
        ax.spines[kenar].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=3)
    ax.tick_params(axis="x", pad=1.5)
    for yy, k in zip(yler, sira, strict=False):
        v = asamalar[k]
        pay = round(100 * v / toplam)
        yazi = f"{_sayi(v, dil)} ({pay}%)" if dil == "en" \
            else f"{_sayi(v, dil)} (%{pay})"
        ax.text(v + 0.25, yy, yazi, va="center", ha="left",
                fontsize=PUNTO_GOVDE, color=MUREKKEP)

    # Gösterge: grafiğin altında, grafiğe ortalı
    gy = 11.0
    ogeler = [(KOYU, tx["gpu"]), (ACIK, tx["diger"])]
    genislik = [4.2 + len(m) * PUNTO_ETIKET * 0.207 for _, m in ogeler]
    toplam_g = sum(genislik) + 6.0
    x = 146.0 - toplam_g / 2
    for (renk, metin), gw in zip(ogeler, genislik, strict=False):
        t.ax.add_patch(Rectangle((x, gy - 1.2), 3.0, 2.4, color=renk,
                                 linewidth=0))
        _etiket(t, x + 4.2, gy, metin, ha="left", va="center")
        x += gw + 6.0
    _etiket(t, 146.0, 4.0,
            tx["kapanis"].format(t=_sayi(toplam, dil),
                                p=_sayi(olcum["parti_toplam_ms"], dil)),
            ha="center", va="center")
    _kaydet(t, "sekil-2-kademeli-isleme", dil)


# ─── Şekil 3: tek giriş noktası ─────────────────────────────────────────
def sekil_kimlik(dil: str) -> None:
    tx = METIN[dil]
    sx, sg = 132.0, 56.0
    h_ic = kutu_yuksekligi(len(tx["ic"][1]))
    h_medya = kutu_yuksekligi(len(tx["medya"][1]))
    h_uyg = kutu_yuksekligi(len(tx["uygulama"][1]))
    h_vekil = kutu_yuksekligi(len(tx["vekil"][1]))
    h_tar = kutu_yuksekligi(len(tx["tarayici"][1]))

    y_ic = 2.0
    y_medya = y_ic + h_ic + 8.0
    y_uyg = y_medya + h_medya + 12.0
    yuk = y_uyg + h_uyg + 2.0
    t = _tuval(yuk)

    _kutu(t, sx, y_uyg, sg, h_uyg, *tx["uygulama"])
    _kutu(t, sx, y_medya, sg, h_medya, *tx["medya"])
    _kutu(t, sx, y_ic, sg, h_ic, *tx["ic"], kesik=True)

    medya_orta = y_medya + h_medya / 2
    vx, vg = 50.0, 52.0
    vy = medya_orta - h_vekil / 2 - 2.0
    _kutu(t, vx, vy, vg, h_vekil, *tx["vekil"], vurgu=True)
    ty = medya_orta - h_tar / 2
    _kutu(t, 2.0, ty, 34.0, h_tar, *tx["tarayici"])

    ok_y = medya_orta - 1.5
    _ok(t, [(36.0, ok_y), (vx, ok_y)])
    _etiket(t, 43.0, ok_y + 0.8, tx["a_https"])
    # (3) yalnızca 200 ise → medya
    _ok(t, [(vx + vg, ok_y), (sx, ok_y)])
    _etiket(t, (vx + vg + sx) / 2, ok_y + 0.8, tx["a_medya"])
    # (1) yetki sorgusu ve (2) cevap
    ust1 = y_uyg + h_uyg - 5.0
    ust2 = y_uyg + 3.5
    _ok(t, [(vx + 16.0, vy + h_vekil), (vx + 16.0, ust1), (sx, ust1)])
    _etiket(t, (vx + 16.0 + sx) / 2, ust1 + 0.8, tx["a_sorgu"])
    _ok(t, [(sx, ust2), (vx + 36.0, ust2), (vx + 36.0, vy + h_vekil)], kesik=True)
    _etiket(t, (vx + 36.0 + sx) / 2, ust2 + 0.8, tx["a_cevap"])
    # iç uçlar — dışarıya kapalı
    x_dik = 117.0
    ic_orta = y_ic + h_ic / 2
    _ok(t, [(vx + vg, vy + 3.0), (x_dik, vy + 3.0), (x_dik, ic_orta), (sx, ic_orta)],
        kesik=True)
    _etiket(t, x_dik - 1.2, (vy + 3.0 + ic_orta) / 2, tx["a_ic"], ha="right",
            va="center", italik=True)
    _kaydet(t, "sekil-3-kimlik-dogrulama", dil)

def main() -> int:
    for dil in ("tr", "en"):
        print(f"[{dil}]")
        sekil_veri_akisi(dil)
        sekil_kademeler(dil)
        sekil_kimlik(dil)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
