"""20 kameralık sahte kamera çiftliğini kaynak videolardan üretir.

Ne yapar
--------
Elimizdeki üç farklı kaynağı tek biçime getirip `data/videos/cam-NN.mp4`
dosyalarına dönüştürür. MediaMTX bu dosyaları sonsuz döngüde RTSP olarak
yayınlar (bkz. infra/mediamtx/mediamtx.yml).

Hedef biçim: 720p · H.264 · 25 FPS · sessiz
  - 720p  : analitik için fazlasıyla yeterli, decode yükünü yarıya indirir.
            Gerçek IP kameralarda "substream" tam olarak bu iş içindir.
  - 25 FPS: sabit kare hızı, zamansal hesapları basitleştirir.
  - sessiz: ses analizi kapsam dışı; boşuna bant genişliği harcamayalım.

Kaynaklar
---------
  VIRAT   : gerçek dış mekân gözetim kayıtları (otopark/kampüs), 1080p30
  Oxford  : yoğun cadde CCTV'si + gerçek etiket dosyası
  PETS2009: aynı sahnenin 7 FARKLI KAMERA AÇISI — JPEG kare dizisi hâlinde
  RWF-2000: 5 saniyelik kavga/normal klipleri → uzun akışa birleştirilir

RWF kameralarının özel değeri
-----------------------------
Klipleri birleştirirken hangi saniyede kavga başladığını biliyoruz.
Bu bilgi `data/annotations/cam-NN.truth.json` dosyasına yazılır ve
"erken uyarı avansı" metriğinin (PLAN.md §6.5.5) ölçümünde kullanılır.
Bedava ground-truth.

ffmpeg
------
Host'ta ffmpeg kurulu değil; MediaMTX konteyner imajındaki ffmpeg
kullanılıyor. Ek kurulum gerekmez.

Kullanım
--------
    uv run python scripts/build_camera_farm.py            # tümünü kur
    uv run python scripts/build_camera_farm.py --only cam-17 cam-18
    uv run python scripts/build_camera_farm.py --list     # planı göster
    uv run python scripts/build_camera_farm.py --force    # var olanı yeniden üret
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA = PROJECT_ROOT / "data"
SOURCES = DATA / "_sources"
VIDEOS = DATA / "videos"
ANNOTATIONS = DATA / "annotations"
TMP = DATA / "_tmp"

FFMPEG_IMAGE = "bluenviron/mediamtx:latest-ffmpeg"

TARGET_HEIGHT = 720
TARGET_FPS = 25
MAX_SECONDS = 300  # 5 dakika — döngüye alınacağı için fazlası gereksiz


@dataclass(frozen=True)
class CameraSpec:
    """Tek bir sahte kameranın nasıl üretileceği."""

    cam: str
    kind: str  # "video" | "frames" | "rwf"
    source: str  # data/ köküne göre göreli yol (rwf için boş)
    label: str  # panelde/rapor'da görünecek açıklama
    frame_pattern: str = "frame_%04d.jpg"
    input_fps: int = 7  # yalnızca kind="frames"
    clip_count: int = 60  # yalnızca kind="rwf"
    fight_ratio: float = 0.15  # yalnızca kind="rwf"
    seed: int = 0


# ─── KAMERA ÇİFTLİĞİ PLANI ───────────────────────────────────
# Dağılım gerekçesi PLAN.md §7.1'de. Özet:
#   normal sahne çoğunlukta olmalı ki anomali modülü "normal"i öğrenebilsin.

PETS_BASE = "_sources/pets/Crowd_PETS09/S2/L1/Time_12-34"

# ⚠ 18.08.2026 — ÇİFTLİK YENİDEN DÜZENLENDİ
#
# Önceki dağılımın iki sorunu vardı:
#
# 1. **cam-10…cam-16 aynı sahnenin 7 açısıydı** (PETS09 · S2/L1 ·
#    Time_12-34). Yedi kamera aynı olayı izliyordu. Bu üç şeyi bozuyordu:
#      · "Her kameranın normali AYRI öğrenilir" ilkesi (mimari kural 7) —
#        yedisinin normali aynı çıkıyordu, ilke gösterilemiyordu
#      · Bir olayda 7 kamera birden alarm veriyordu → PLAN §6.6'daki
#        "sistem seviyesi olay" bastırma kuralı boşuna tetiklenirdi
#      · Sahne çeşitliliği yapay olarak düşüktü
#    3 açı bırakıldı (birbirine en uzak olanlar): kalabalık ve ani
#    dağılma senaryoları için yeterli, kopya değil.
#
# 2. **Pexels videoları HİÇ kullanılmıyordu** (10 klip, ~151 MB).
#    Oysa PLAN §7.1 "19-20: yakın plan yüz içeren sahne — duygu modülü
#    testi" diyordu ve o slotlara RWF kavga klipleri konmuştu.
#    Sonuç: KADEME 2b'nin çalışabileceği TEK kamera yoktu ve modül
#    kamera çiftliğinde hiç sonuç üretemiyordu
#    (benchmarks/expression_20260818-gun14.json).
#
# Ayrıca 10 Pexels klibi demografik olarak çeşitli (farklı yaş, cinsiyet,
# ten rengi, ışık, arka plan). PLAN §12.2 yanlılık değerlendirmesi için
# alt gruplara ayrılmış performans raporlamayı istiyor; elimizdeki tek
# elverişli malzeme bu.
#
# ⚠ Karşılanamayan istek: PLAN §7.1 "boş sahne" ve "düşme/koşma"
# kameraları da istiyor. Elimizde o tür görüntü YOK ve uydurmak
# ölçümü yanıltır. Raporda kapsam notu olarak yazılacak. (Hareket
# filtresinin yük düşürdüğü zaten sentetik `cam-test-static` ile ve
# gerçek kameraların gate oranlarıyla gösteriliyor.)

PEXELS = "_sources/pexels"

# CUHK Avenue Dataset — kare seviyesinde YER GERÇEĞİ olan anomali seti.
#
# ⚠ NEDEN BU SET ÖZEL
# Diğer kameralarımızın hiçbirinde "burada anomali var" diye etiket yok;
# kurallarımızın doğru çalışıp çalışmadığını ancak gözle bakarak
# değerlendirebiliyorduk. Avenue her karesi için piksel maskesi taşıyor:
# maskede sıfırdan farklı piksel varsa o kare anomalidir.
# Bu, K6 kriterinin (anomali ROC-AUC) gerçekten ÖLÇÜLEBİLMESİ demek.
#
# ⚠ İÇERİĞİ: koşma, nesne fırlatma, oyalanma, ters yön, çocuğun zıplaması.
# DÜŞME İÇERMİYOR. Düşme kuralımız hâlâ yalnızca sentetik testlerle
# doğrulanmış durumda; gerçek doğrulama için UR Fall / Le2i gerekiyor.
# Bu kısıt raporda açıkça yazılacak.
AVENUE = "archive/Avenue_Dataset/Avenue Dataset"

# UR Fall Detection Dataset — GERÇEK düşme görüntüsü.
#
# ⚠ NEDEN GEREKLİ
# Avenue'nun anomalileri koşma/fırlatma/oyalanma; DÜŞME İÇERMİYOR.
# Düşme kuralımız (rules.py · _dusme) şimdiye kadar yalnızca sentetik
# iskeletlerle test edilmişti — gerçek bir düşme görüntüsünde hiç
# denenmedi. Ofis ortamında kayıtlı bu dizi o boşluğu kapatıyor.
#
# ⚠ TEK DİZİ, KISA (160 kare @ 30 FPS ≈ 5.3 sn). Bu bir sınırlama ama
# döngüde oynadığı için düşme her ~5 saniyede tekrarlanıyor: kural
# defalarca sınanıyor. İstatistiksel güç için yetersiz, VARLIK
# doğrulaması için yeterli. Raporda böyle yazılacak.
UR_FALL = "fall-01-cam0-rgb/fall-01-cam0-rgb"

CAMERA_PLAN: list[CameraSpec] = [
    # ── 01-08 · Normal sahne: VIRAT otopark/kampüs ──
    # Anomali modülünün "normal"i öğrenmesi için çoğunluk normal olmalı.
    CameraSpec("cam-01", "video", "_sources/virat/VIRAT_S_000001.mp4", "Otopark — kuzey"),
    CameraSpec("cam-02", "video", "_sources/virat/VIRAT_S_000002.mp4", "Otopark — orta"),
    CameraSpec("cam-03", "video", "_sources/virat/VIRAT_S_000003.mp4", "Otopark — güney"),
    CameraSpec("cam-04", "video", "_sources/virat/VIRAT_S_000004.mp4", "Kampüs — geçiş"),
    CameraSpec("cam-05", "video", "_sources/virat/VIRAT_S_000006.mp4", "Kampüs — meydan"),
    CameraSpec("cam-06", "video", "_sources/virat/VIRAT_S_000102.mp4", "Bina girişi"),
    CameraSpec(
        "cam-07", "video", "_sources/virat/VIRAT_S_000200_00_000100_000171.mp4", "Yan saha — A"
    ),
    CameraSpec(
        "cam-08", "video", "_sources/virat/VIRAT_S_000200_01_000226_000268.mp4", "Yan saha — B"
    ),
    # ── 09 · Yoğun yaya trafiği: Oxford (yer gerçeği de var) ──
    CameraSpec("cam-09", "video", "_sources/oxford/TownCentreXVID.mp4", "Cadde — yoğun yaya"),
    # ── 10-16 · Kalabalık: PETS09, aynı sahnenin 7 açısı ──
    #
    # ⚠ 19.08.2026 — GERİ ALINDI, ve sebebi öğretici
    # 18.08'de bu 7 açının 3'e indirilmesi "kopya sahne" gerekçesiyle
    # savunulmuştu (her kameranın normali ayrı öğrenilmeli). Gerekçe
    # kendi başına DOĞRU. Ama değişiklik ölçülmeden yapıldı ve boşalan
    # 4 slota RWF kavga klipleri kondu — çiftliğin yükü sessizce arttı,
    # sistem yavaşladı, sebebi günlerce aranmadı.
    #
    # Ders: bir gerekçenin doğru olması, değişikliğin ölçülmeden
    # yapılabileceği anlamına gelmiyor. Çiftlik ÖLÇÜM ZEMİNİ — zemini
    # değiştirince tüm eski ölçümler kıyaslanamaz hâle geliyor.
    # 7 açı sorunu gerçek ama ayrı bir iş; çözülürse tek başına, ölçüm
    # öncesi/sonrası kıyaslamayla çözülecek.
    CameraSpec("cam-10", "frames", f"{PETS_BASE}/View_001", "Meydan — açı 1"),
    CameraSpec("cam-11", "frames", f"{PETS_BASE}/View_003", "Meydan — açı 3"),
    CameraSpec("cam-12", "frames", f"{PETS_BASE}/View_004", "Meydan — açı 4"),
    CameraSpec("cam-13", "frames", f"{PETS_BASE}/View_005", "Meydan — açı 5"),
    CameraSpec("cam-14", "frames", f"{PETS_BASE}/View_006", "Meydan — açı 6"),
    CameraSpec("cam-15", "frames", f"{PETS_BASE}/View_007", "Meydan — açı 7"),
    # ⚠ cam-16 PETS'in 8. açısıydı — 7 kopya açıdan biri, en az bilgi
    # taşıyanı. Yerine GERÇEK DÜŞME kondu: düşme kuralının tek
    # doğrulanmamış kural olması, kopya bir kalabalık açısından çok
    # daha önemli bir eksikti.
    CameraSpec(
        "cam-16", "frames", UR_FALL, "Düşme — gerçek (UR Fall)",
        frame_pattern="fall-01-cam0-rgb-%03d.png", input_fps=30,
    ),
    # ── 17-19 · Saldırganlık: RWF-2000 birleştirilmiş + ground-truth ──
    CameraSpec("cam-17", "rwf", "", "Test — kavga (seyrek)", clip_count=60, fight_ratio=0.10, seed=17),
    # ── 18-19 · CUHK Avenue: YER GERÇEKLİ anomali doğrulaması ──
    #
    # ⚠ KONTROLLÜ DENEY TASARIMI — ikisi AYNI sahne, aynı kamera açısı
    #   cam-18: yalnızca NORMAL kayıtlar   → kontrol grubu
    #   cam-19: anomali içeren kayıtlar    → deney grubu
    #
    # Neden ikisi birden: tek başına "anomali kamerasında alarm çıktı"
    # demek yetmez — sistem her şeye alarm veriyor olabilir. Aynı
    # sahnenin normal hâlinde SESSİZ kalması, alarmın gerçekten olaya
    # tepki verdiğinin kanıtı. Yanlış alarm oranı (K7) da buradan
    # doğrudan okunuyor: cam-18'de çıkan her alarm yanlıştır.
    CameraSpec("cam-18", "avenue", AVENUE, "Avenue — normal (kontrol)", seed=18),
    CameraSpec("cam-19", "avenue", AVENUE, "Avenue — anomali (yer gerçekli)", seed=19),
    # ── 20 · TEK DEĞİŞİKLİK: yakın plan yüz (PLAN §7.1) ──
    #
    # Eskiden "RWF tamamı normal" idi. Değiştirilme sebebi: KADEME 2b'nin
    # çalışabileceği TEK bir kamera bile yoktu — gözetim görüntüsünde
    # yüzler ~15 px ve ifade modeli 60 px istiyor. Modül kuruluydu ama
    # kamera çiftliğinde hiç sonuç üretemiyordu
    # (benchmarks/expression_20260818-gun14.json).
    #
    # ⚠ Neden 3 değil 1: 18.08'de üç yüz kamerası eklenmişti; yeteneği
    # göstermek için biri yeterli, üçü çiftliğin karakterini gereksiz
    # değiştiriyor. Ölçülen: bu kamerada kişi boyu p50 550 px, yüz
    # 68.8 px, yüz tespiti isabeti %100 — yani modül gerçekten çalışıyor.
    CameraSpec("cam-20", "faces", PEXELS, "Yakın plan yüz — duygu testi", seed=20),
]


# ─── ffmpeg yardımcıları ─────────────────────────────────────


def run_ffmpeg(args: list[str]) -> None:
    """MediaMTX imajındaki ffmpeg'i çalıştırır.

    data/ dizini konteynere /data olarak bağlanır; tüm yollar ona göre.
    subprocess'e liste veriyoruz — shell yok, enjeksiyon riski yok.
    """
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{DATA}:/data",
        "--entrypoint", "ffmpeg",
        FFMPEG_IMAGE,
        "-hide_banner", "-loglevel", "error", "-y",
        *args,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg başarısız:\n{result.stderr.strip()[:1500]}")


def encode_args(out_rel: str) -> list[str]:
    """Ortak çıktı kodlama parametreleri."""
    return [
        "-vf", f"scale=-2:{TARGET_HEIGHT}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-r", str(TARGET_FPS),
        "-g", str(TARGET_FPS * 2),  # 2 sn GOP — WebRTC'de hızlı başlangıç
        # ⚠ B-frame KAPALI olmalı. WebRTC'nin H.264 profili B-frame
        #   desteklemez; MediaMTX bağlantıyı "doesn't support H264 streams
        #   with B-frames" diyerek kapatır. libx264 varsayılanı B-frame
        #   ÜRETİR. Bkz. docs/report/problems.md · P-08
        "-bf", "0",
        "-pix_fmt", "yuv420p",
        "-an",  # ses yok
        "-movflags", "+faststart",
        f"/data/{out_rel}",
    ]


def probe_duration(path: Path) -> float:
    """Video süresini PyAV ile okur (docker çağrısından çok daha hızlı)."""
    import av

    with av.open(str(path)) as container:
        if container.duration:
            return float(container.duration) / av.time_base
        stream = container.streams.video[0]
        if stream.duration and stream.time_base:
            return float(stream.duration * stream.time_base)
    return 0.0


# ─── Kamera üreticileri ──────────────────────────────────────


def build_video(spec: CameraSpec) -> dict[str, object]:
    src = DATA / spec.source
    if not src.is_file():
        raise FileNotFoundError(src)
    run_ffmpeg(["-t", str(MAX_SECONDS), "-i", f"/data/{spec.source}", *encode_args(f"videos/{spec.cam}.mp4")])
    return {}


def build_frames(spec: CameraSpec) -> dict[str, object]:
    src_dir = DATA / spec.source
    if not src_dir.is_dir():
        raise FileNotFoundError(src_dir)
    pattern = f"/data/{spec.source}/{spec.frame_pattern}"
    # -framerate: girdinin gerçek hızı; -r: çıktı hızı.
    # İkisi farklı olunca ffmpeg kare çoğaltır → süre korunur, akış 25 FPS olur.
    run_ffmpeg(["-framerate", str(spec.input_fps), "-i", pattern, *encode_args(f"videos/{spec.cam}.mp4")])
    # ⚠ Kare sayısı desenin UZANTISINDAN okunuyor, "*.jpg" varsayılmıyor.
    # UR Fall PNG dizisi eklenince manifest "source_frames: 0" yazdı —
    # video üretilmişti, sayaç yalan söylüyordu. Sessiz yanlış sayı,
    # eksik sayıdan kötüdür: ölçüm zeminine güven kalmaz.
    uzanti = Path(spec.frame_pattern).suffix or ".jpg"
    return {"source_frames": len(list(src_dir.glob(f"*{uzanti}"))), "input_fps": spec.input_fps}


def build_rwf(spec: CameraSpec) -> dict[str, object]:
    """RWF-2000 kliplerini birleştirip ground-truth üretir."""
    root = DATA / "datasets" / "RWF-2000" / "train"
    fight_pool = sorted((root / "fight").glob("*.avi"))
    normal_pool = sorted((root / "nonfight").glob("*.avi"))
    if not fight_pool or not normal_pool:
        raise FileNotFoundError(f"RWF-2000 bulunamadı: {root}")

    # Sabit tohum: aynı komut her çalıştığında AYNI kamera üretilir.
    # Tekrarlanabilirlik ölçüm için şart — ground-truth ile video eşleşmeli.
    # (S311: güvenlik amaçlı değil, kasten deterministik.)
    rng = random.Random(spec.seed)  # noqa: S311
    n_fight = round(spec.clip_count * spec.fight_ratio)
    n_normal = spec.clip_count - n_fight
    chosen = rng.sample(fight_pool, n_fight) + rng.sample(normal_pool, n_normal)
    rng.shuffle(chosen)

    # Süreleri okuyup zaman çizelgesi (ground-truth) çıkar
    TMP.mkdir(parents=True, exist_ok=True)
    list_path = TMP / f"{spec.cam}.txt"
    segments: list[dict[str, object]] = []
    cursor = 0.0
    lines: list[str] = []

    for clip in chosen:
        duration = probe_duration(clip) or 5.0
        is_fight = clip.parent.name == "fight"
        segments.append(
            {
                "start_s": round(cursor, 3),
                "end_s": round(cursor + duration, 3),
                "label": "fight" if is_fight else "normal",
                "clip": clip.name,
            }
        )
        cursor += duration
        # concat demuxer: yolu tek tırnak içinde ve kaçışlı ister
        rel = clip.relative_to(DATA).as_posix()
        lines.append(f"file '/data/{rel}'")

    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    run_ffmpeg(
        [
            "-f", "concat", "-safe", "0",
            "-i", f"/data/_tmp/{spec.cam}.txt",
            *encode_args(f"videos/{spec.cam}.mp4"),
        ]
    )

    # Ground-truth dosyası — erken uyarı avansı ölçümü için
    ANNOTATIONS.mkdir(parents=True, exist_ok=True)
    truth = {
        "camera": spec.cam,
        "source": "RWF-2000 (train bölümü)",
        "citation": "Cheng et al., arXiv:1911.05913",
        # Bu dosya HANGİ kamera tanımından üretildi — bayat kalırsa
        # `_truth_denetle` yakalasın diye (bkz. o fonksiyonun docstring'i).
        "uretim_kaynagi": spec.source or "RWF-2000",
        "seed": spec.seed,
        "total_duration_s": round(cursor, 3),
        "fight_clip_count": n_fight,
        "normal_clip_count": n_normal,
        "segments": segments,
    }
    (ANNOTATIONS / f"{spec.cam}.truth.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"fight_clips": n_fight, "normal_clips": n_normal, "duration_s": round(cursor, 1)}


def build_faces(spec: CameraSpec) -> dict[str, object]:
    """Pexels yakın plan yüz kliplerini birleştirir — KADEME 2b'nin girdisi.

    ⚠ NEDEN İKİ AŞAMALI
    -------------------
    `concat` demuxer, birleştirilen dosyaların **aynı codec ve aynı
    çözünürlükte** olmasını ister; sadece paketleri arka arkaya
    ekler, yeniden kodlamaz. Pexels klipleri ise 1920×1080'den
    4096×2160'a kadar beş farklı çözünürlükte. Doğrudan birleştirmeye
    kalkarsak ffmpeg ya hata verir ya da sessizce bozuk çıktı üretir.

    Bu yüzden önce her klip tek tek 720p'ye normalize ediliyor, sonra
    birleştiriliyor. İkinci geçiş `-c copy` ile yeniden kodlamıyor.

    ⚠ NEDEN BİRDEN ÇOK KLİP
    -----------------------
    Tek bir yüz koysaydık ifade modülü tek kişiyle test edilirdi.
    Birkaç klip dönüşümlü olunca:
      · ifade sınıflandırma farklı yüzlerde deneniyor
      · PLAN §12.2'nin istediği demografik alt grup analizi mümkün oluyor
      · takip modülü "kişi kadraja girdi/çıktı" senaryosunu görüyor
    """
    src_dir = DATA / spec.source
    klipler = sorted(src_dir.glob("*.mp4"))
    if not klipler:
        raise FileNotFoundError(f"Pexels klibi yok: {src_dir}")

    # Sabit tohum: aynı komut aynı kamerayı üretir (tekrarlanabilirlik).
    # Kameralar farklı tohum aldığı için farklı klip karışımları alıyorlar.
    rng = random.Random(spec.seed)  # noqa: S311
    secilen = rng.sample(klipler, min(4, len(klipler)))

    TMP.mkdir(parents=True, exist_ok=True)
    satirlar: list[str] = []
    kullanilan: list[dict[str, object]] = []

    for sira, klip in enumerate(secilen):
        ara = f"_tmp/{spec.cam}_p{sira}.mp4"
        # 1. aşama: ortak biçime getir (720p, 25 FPS, H.264)
        run_ffmpeg(["-i", f"/data/{klip.relative_to(DATA).as_posix()}", *encode_args(ara)])
        satirlar.append(f"file '/data/{ara}'")
        kullanilan.append({"clip": klip.name, "duration_s": round(probe_duration(klip), 1)})

    liste = TMP / f"{spec.cam}_faces.txt"
    liste.write_text("\n".join(satirlar) + "\n", encoding="utf-8")

    # 2. aşama: birleştir — hepsi artık aynı biçimde, kopyalamak yeterli
    run_ffmpeg(
        [
            "-f", "concat", "-safe", "0",
            "-i", f"/data/_tmp/{spec.cam}_faces.txt",
            "-c", "copy",
            "-y", f"/data/videos/{spec.cam}.mp4",
        ]
    )

    # Ara dosyaları temizle — yoksa _tmp şişer
    for sira in range(len(secilen)):
        (DATA / "_tmp" / f"{spec.cam}_p{sira}.mp4").unlink(missing_ok=True)
    liste.unlink(missing_ok=True)

    return {"clips": kullanilan, "clip_count": len(secilen)}


def build_avenue(spec: CameraSpec) -> dict[str, object]:
    """CUHK Avenue kameralarını üretir + KARE SEVİYESİNDE yer gerçeği.

    ⚠ BU BETİĞİN EN DEĞERLİ ÇIKTISI
    Diğer kameralarımızda "burada anomali var" diye bir etiket yok;
    kuralların doğru çalışıp çalışmadığını gözle değerlendiriyorduk.
    Avenue her kare için piksel maskesi taşıyor ve maskede sıfırdan
    farklı piksel varsa o kare anomalidir.

    Maskeler `.mat` dosyalarında ve kare kare tutuluyor. Burada
    kare→anomali ikili etiketine indirgeniyor, sonra birleştirilmiş
    videodaki ZAMANA çevriliyor. Sonuç: "şu saniyeler arasında anomali
    var" listesi — kurallarımızın çıktısıyla doğrudan karşılaştırılabilir.

    ⚠ İKİ KAMERA, KONTROLLÜ DENEY
      cam-18 (seed 18) → yalnızca `training_videos`  = NORMAL, kontrol
      cam-19 (seed 19) → yalnızca `testing_videos`   = ANOMALİLİ, deney
    Aynı sahne, aynı kamera açısı. Tek başına "anomali kamerasında alarm
    çıktı" demek yetmez — sistem her şeye alarm veriyor olabilir. Aynı
    sahnenin normal hâlinde SESSİZ kalması, alarmın gerçekten olaya tepki
    verdiğinin kanıtı.
    """
    import scipy.io as sio

    kok = DATA / spec.source
    anomalili = spec.seed == 19
    klip_dizin = kok / ("testing_videos" if anomalili else "training_videos")
    klipler = sorted(klip_dizin.glob("*.avi"))
    if not klipler:
        raise FileNotFoundError(f"Avenue klibi yok: {klip_dizin}")

    maske_dizin = (
        DATA / "archive/ground_truth_demo/ground_truth_demo/testing_label_mask"
    )

    # Toplam süreyi MAX_SECONDS'a sığdır — döngüye alınacağı için
    # fazlası gereksiz ve disk yiyor.
    TMP.mkdir(parents=True, exist_ok=True)
    satirlar: list[str] = []
    segmentler: list[dict[str, object]] = []
    imlec = 0.0
    kullanilan: list[str] = []

    for klip in klipler:
        if imlec >= MAX_SECONDS:
            break
        sure = probe_duration(klip)
        if sure <= 0:
            continue

        ara = f"_tmp/{spec.cam}_{klip.stem}.mp4"
        run_ffmpeg(["-i", f"/data/{klip.relative_to(DATA).as_posix()}", *encode_args(ara)])
        satirlar.append(f"file '/data/{ara}'")
        kullanilan.append(klip.name)

        # ─── Yer gerçeği: hangi kareler anomali? ───
        if anomalili:
            # ⚠ ADLANDIRMA UYUŞMAZLIĞI — sessiz hata kaynağıydı
            # Videolar sıfır dolgulu (`01.avi`), maskeler değil
            # (`1_label.mat`). İlk sürüm `klip.stem` kullanıyordu, dosya
            # bulunamıyordu ve `if maske.is_file()` sessizce atlıyordu:
            # betik "0 hata" diye başarı raporladı ama yer gerçeği BOŞ
            # çıktı. Var olmayan bir dosyayı sessizce geçmek, olmayan
            # veriyi "veri yok" sanmaya yol açıyor.
            maske = maske_dizin / f"{int(klip.stem)}_label.mat"
            if not maske.is_file():
                raise FileNotFoundError(
                    f"Yer gerçeği maskesi yok: {maske.name} (klip {klip.name}). "
                    "Bu kameranın değeri yer gerçeğinde; maskesiz üretmek anlamsız."
                )
            vol = sio.loadmat(str(maske))["volLabel"]
            # Her eleman bir karenin piksel maskesi; herhangi bir
            # sıfırdan farklı piksel = o karede anomali var.
            bayraklar = [bool(vol.flat[i].any()) for i in range(vol.size)]
            fps = len(bayraklar) / sure if sure > 0 else TARGET_FPS
            segmentler.extend(_araliklar(bayraklar, fps, imlec, klip.name))
        imlec += sure

    liste = TMP / f"{spec.cam}_avenue.txt"
    liste.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    run_ffmpeg(
        [
            "-f", "concat", "-safe", "0",
            "-i", f"/data/_tmp/{spec.cam}_avenue.txt",
            "-c", "copy", "-y", f"/data/videos/{spec.cam}.mp4",
        ]
    )

    for klip in kullanilan:
        (DATA / "_tmp" / f"{spec.cam}_{Path(klip).stem}.mp4").unlink(missing_ok=True)
    liste.unlink(missing_ok=True)

    if anomalili:
        ANNOTATIONS.mkdir(parents=True, exist_ok=True)
        (ANNOTATIONS / f"{spec.cam}.truth.json").write_text(
            json.dumps(
                {
                    "camera": spec.cam,
                    "source": "CUHK Avenue Dataset (testing split)",
                    "citation": "Lu, Shi, Jia — Abnormal Event Detection at 150 FPS, ICCV 2013",
                    "uretim_kaynagi": spec.source,
                    "anomali_turleri": [
                        "kosma", "nesne firlatma", "oyalanma", "ters yon", "ziplama",
                    ],
                    "not": "DUSME ICERMIYOR — dusme kurali icin UR Fall / Le2i gerekli",
                    "total_duration_s": round(imlec, 3),
                    "clips": kullanilan,
                    "anomali_segment_sayisi": len(segmentler),
                    "segments": segmentler,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return {
        "clips": len(kullanilan),
        "duration_s": round(imlec, 1),
        "anomali_segment": len(segmentler),
    }


def _araliklar(
    bayraklar: list[bool], fps: float, ofset: float, klip: str
) -> list[dict[str, object]]:
    """Ardışık anomali karelerini zaman aralıklarına dönüştürür.

    Kare kare etiket yerine aralık tutmak hem okunabilir hem de
    karşılaştırması kolay: "12.4-15.8 sn arası anomali".
    """
    cikti: list[dict[str, object]] = []
    basla: int | None = None
    for i, bayrak in enumerate([*bayraklar, False]):
        if bayrak and basla is None:
            basla = i
        elif not bayrak and basla is not None:
            cikti.append(
                {
                    "start_s": round(ofset + basla / fps, 3),
                    "end_s": round(ofset + i / fps, 3),
                    "label": "anomaly",
                    "clip": klip,
                }
            )
            basla = None
    return cikti


def _truth_denetle(plan: list[CameraSpec]) -> None:
    """Yer gerçeği dosyaları hâlâ doğru kamerayı mı anlatıyor, kontrol eder.

    ⚠ 26.08.2026 — GERÇEK BİR ÖLÇÜM ZEHİRLENMESİ YAKALANDI

    cam-13…cam-16, cam-18 ve cam-20 bir zamanlar RWF-2000 kavga kameralarıydı
    ve `cam-NN.truth.json` dosyalarına kavga zaman damgaları yazılmıştı.
    Sonra bu slotlara PETS kalabalığı, Avenue ve Pexels yüzleri kondu —
    **ama yer gerçeği dosyaları yerinde kaldı.** Diskte, kalabalık bir
    meydan görüntüsünün yanında "şu saniyede kavga var" diyen bir dosya
    duruyordu.

    Kimse fark etmemişti çünkü hiçbir betik onları okumuyordu. Okusaydı
    sessizce yanlış ölçerdi — ve bir ölçüm zemini yanlış olduğunda üstüne
    kurulan her sayı da yanlış olur. Testi olmayan veri, testi olmayan
    koddan tehlikelidir: kod patlar, veri patlamaz.

    Çözüm: her yer gerçeği dosyası hangi kaynaktan üretildiğini yazar
    (`uretim_kaynagi`), bu betik de plandaki kaynakla karşılaştırır.
    Silmez — uyarır. Elle yazılmış bir dosyayı bir betiğin silmesi,
    çözdüğü sorundan büyük bir sorundur.
    """
    if not ANNOTATIONS.is_dir():
        return
    planlanan = {s.cam: (s.source or "RWF-2000") for s in CAMERA_PLAN}
    for yol in sorted(ANNOTATIONS.glob("cam-*.truth.json")):
        cam = yol.name.split(".")[0]
        if cam not in planlanan:
            print(f"UYARI  {yol.name}: planda böyle bir kamera yok")
            continue
        try:
            kaynak = json.loads(yol.read_text(encoding="utf-8")).get("uretim_kaynagi")
        except (json.JSONDecodeError, OSError) as exc:
            print(f"UYARI  {yol.name}: okunamadı ({exc})")
            continue
        if kaynak is None:
            print(f"UYARI  {yol.name}: 'uretim_kaynagi' yok — hangi kameraya ait doğrulanamıyor")
        elif kaynak != planlanan[cam]:
            print(
                f"UYARI  {yol.name}: BAYAT yer gerçeği.\n"
                f"       dosya  → {kaynak}\n"
                f"       plan   → {planlanan[cam]}\n"
                f"       Bu dosyayla yapılan her ölçüm yanlış olur; silin ya da yenileyin."
            )


BUILDERS = {
    "video": build_video,
    "frames": build_frames,
    "rwf": build_rwf,
    "faces": build_faces,
    "avenue": build_avenue,
}


# ─── Ana akış ────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="20 kameralık sahte kamera çiftliğini üretir")
    parser.add_argument("--only", nargs="*", help="Sadece bu kameraları üret (cam-01 cam-02 …)")
    parser.add_argument("--force", action="store_true", help="Var olan çıktıları yeniden üret")
    parser.add_argument("--list", action="store_true", help="Planı göster, üretme")
    args = parser.parse_args()

    plan = CAMERA_PLAN
    if args.only:
        wanted = set(args.only)
        plan = [s for s in plan if s.cam in wanted]
        if not plan:
            print(f"Eşleşen kamera yok: {args.only}", file=sys.stderr)
            return 1

    if args.list:
        print(f"{'KAMERA':<9} {'TÜR':<7} {'AÇIKLAMA':<26} KAYNAK")
        for s in plan:
            src = s.source or f"RWF-2000 ×{s.clip_count} (kavga %{s.fight_ratio:.0%})"
            print(f"{s.cam:<9} {s.kind:<7} {s.label:<26} {src}")
        return 0

    VIDEOS.mkdir(parents=True, exist_ok=True)

    # ⚠ `--only` MANİFESTİ EZMEZ — bu bir hataydı, düzeltildi
    #
    # Önceki sürüm manifesti sıfırdan kuruyordu. `--only cam-11 … cam-20`
    # ile çalıştırıldığında sonuç: manifest 20 değil **10 kayıt** içerdi
    # ve cam-01…cam-10 sessizce kayboldu. Videoları diskte duruyordu ama
    # etiketleri, kaynakları ve süreleri gitti; panelde çıplak "cam-01"
    # diye göründüler.
    #
    # Sessiz veri kaybıydı: betik "10 yeni kamera, 0 hata" diye başarı
    # raporladı. Kısmi bir işlem, dokunmadığı kayıtları silmemeli.
    mevcut: dict[str, dict[str, object]] = {}
    manifest_yolu = VIDEOS / "manifest.json"
    if manifest_yolu.is_file():
        try:
            for kayit in json.loads(manifest_yolu.read_text(encoding="utf-8")):
                mevcut[str(kayit["camera"])] = kayit
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"UYARI: mevcut manifest okunamadı, sıfırdan kuruluyor ({exc})")

    _truth_denetle(plan)

    failures: list[tuple[str, str]] = []
    started = time.monotonic()

    for index, spec in enumerate(plan, start=1):
        out = VIDEOS / f"{spec.cam}.mp4"
        prefix = f"[{index:>2}/{len(plan)}] {spec.cam}"

        if out.exists() and not args.force:
            print(f"{prefix}  atlandı (mevcut, --force ile yeniden üret)")
            mevcut.setdefault(
                spec.cam, {"camera": spec.cam, "label": spec.label, "status": "skipped"}
            )
            continue

        print(f"{prefix}  {spec.label} ... ", end="", flush=True)
        t0 = time.monotonic()
        try:
            extra = BUILDERS[spec.kind](spec)
        except Exception as exc:
            print(f"HATA: {exc}")
            failures.append((spec.cam, str(exc)))
            continue

        size_mb = out.stat().st_size / 1024**2
        dur = probe_duration(out)
        print(f"OK  {dur:5.0f} sn  {size_mb:6.1f} MB  ({time.monotonic() - t0:.0f} sn'de)")
        mevcut[spec.cam] = (
            {
                "camera": spec.cam,
                "label": spec.label,
                "kind": spec.kind,
                "source": spec.source or "RWF-2000",
                "duration_s": round(dur, 1),
                "size_mb": round(size_mb, 1),
                "status": "ok",
                **extra,
            }
        )

    # CAMERA_PLAN sırasına göre yaz — panel ve rapor kamera numarasına
    # göre okunuyor, sözlük ekleme sırası anlamsız bir sıralama verirdi.
    sira = {s.cam: i for i, s in enumerate(CAMERA_PLAN)}
    manifest = sorted(mevcut.values(), key=lambda k: sira.get(str(k["camera"]), 999))
    manifest_yolu.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    elapsed = time.monotonic() - started
    ok = sum(1 for m in manifest if m.get("status") == "ok")
    print()
    print(f"Tamamlandı: {ok} yeni kamera, {len(failures)} hata, {elapsed / 60:.1f} dakika")
    if failures:
        print("\nHatalar:")
        for cam, err in failures:
            print(f"  {cam}: {err[:200]}")
    print(f"\nÇıktı    : {VIDEOS}")
    print(f"Manifest : {VIDEOS / 'manifest.json'}")
    print("\nSonraki adım: docker compose restart mediamtx")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
