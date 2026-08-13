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

CAMERA_PLAN: list[CameraSpec] = [
    # ── Normal: VIRAT otopark/kampüs (aynı saha, farklı kayıtlar) ──
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
    # ── Kalabalık: Oxford (gerçek etiketli veri de var) ──
    CameraSpec("cam-09", "video", "_sources/oxford/TownCentreXVID.mp4", "Cadde — yoğun yaya"),
    # ── PETS2009: aynı sahnenin 7 FARKLI AÇISI ──
    CameraSpec("cam-10", "frames", f"{PETS_BASE}/View_001", "Meydan — açı 1"),
    CameraSpec("cam-11", "frames", f"{PETS_BASE}/View_003", "Meydan — açı 3"),
    CameraSpec("cam-12", "frames", f"{PETS_BASE}/View_004", "Meydan — açı 4"),
    CameraSpec("cam-13", "frames", f"{PETS_BASE}/View_005", "Meydan — açı 5"),
    CameraSpec("cam-14", "frames", f"{PETS_BASE}/View_006", "Meydan — açı 6"),
    CameraSpec("cam-15", "frames", f"{PETS_BASE}/View_007", "Meydan — açı 7"),
    CameraSpec("cam-16", "frames", f"{PETS_BASE}/View_008", "Meydan — açı 8"),
    # ── Saldırganlık: RWF-2000 birleştirilmiş, ground-truth üretilir ──
    CameraSpec("cam-17", "rwf", "", "Test — kavga (seyrek)", clip_count=60, fight_ratio=0.10, seed=17),
    CameraSpec("cam-18", "rwf", "", "Test — kavga (orta)", clip_count=60, fight_ratio=0.20, seed=18),
    CameraSpec("cam-19", "rwf", "", "Test — kavga (yoğun)", clip_count=60, fight_ratio=0.35, seed=19),
    CameraSpec("cam-20", "rwf", "", "Test — tamamı normal", clip_count=60, fight_ratio=0.00, seed=20),
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
    return {"source_frames": len(list(src_dir.glob("*.jpg"))), "input_fps": spec.input_fps}


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


BUILDERS = {"video": build_video, "frames": build_frames, "rwf": build_rwf}


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
    manifest: list[dict[str, object]] = []
    failures: list[tuple[str, str]] = []
    started = time.monotonic()

    for index, spec in enumerate(plan, start=1):
        out = VIDEOS / f"{spec.cam}.mp4"
        prefix = f"[{index:>2}/{len(plan)}] {spec.cam}"

        if out.exists() and not args.force:
            print(f"{prefix}  atlandı (mevcut, --force ile yeniden üret)")
            manifest.append({"camera": spec.cam, "label": spec.label, "status": "skipped"})
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
        manifest.append(
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

    (VIDEOS / "manifest.json").write_text(
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
