"""RWF-2000 veri setini güvenli şekilde çıkarır.

Neden özel bir betiğe ihtiyaç var?
----------------------------------
Kaggle'daki RWF-2000 arşivinde bazı dosya adları 240 karaktere kadar
çıkıyor ve bozuk kodlamalı (mojibake). Windows'un MAX_PATH sınırı 260
karakter olduğu için Gezgin ile çıkarma "0x80010135: Yol çok uzun"
hatası veriyor ve dosyalar atlanıyor.

Çözüm: Etiket bilgisi zaten klasör adında (Fight / NonFight). Dosya
adının hiçbir analitik değeri yok. Bu yüzden dosyaları kısa, sıralı
adlarla çıkarıyoruz:

    RWF-2000/train/Fight/-1l5631l3fg_0.avi  ->  train/fight/fight_0001.avi

İzlenebilirlik için orijinal adlar bir manifest CSV'sine yazılır
(rapor ve tekrarlanabilirlik açısından önemli).

Kullanım
--------
    py -3.13 backend/scripts/extract_rwf2000.py
    py -3.13 backend/scripts/extract_rwf2000.py --zip "C:/yol/RWF2000.zip"
    py -3.13 backend/scripts/extract_rwf2000.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
import zipfile
from pathlib import Path

# Proje kökü: backend/scripts/extract_rwf2000.py -> ../..
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEST = PROJECT_ROOT / "data" / "datasets" / "RWF-2000"

# Zip'in aranacağı yerler (ilk bulunan kullanılır)
SEARCH_DIRS = [
    Path.home() / "OneDrive" / "Masaüstü",
    Path.home() / "OneDrive" / "Desktop",
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    PROJECT_ROOT / "data" / "datasets",
    Path("D:/"),
]
ZIP_PATTERNS = ["RWF2000.zip", "rwf2000.zip", "RWF-2000.zip", "archive.zip"]


def find_zip() -> Path | None:
    """Bilinen konumlarda RWF-2000 arşivini arar."""
    for directory in SEARCH_DIRS:
        try:
            if not directory.is_dir():
                continue
        except OSError:
            continue
        for pattern in ZIP_PATTERNS:
            candidate = directory / pattern
            if candidate.is_file():
                return candidate
    return None


def long_path(path: Path) -> str:
    r"""Windows MAX_PATH sınırını aşmak için \\?\ önekini ekler.

    Bu önek Win32 API'sine "yolu olduğu gibi kullan, 260 karakter
    sınırını uygulama" der. Yalnızca mutlak yollarla çalışır.
    """
    resolved = path.resolve()
    if sys.platform == "win32":
        text = str(resolved)
        if not text.startswith("\\\\?\\"):
            return "\\\\?\\" + text
        return text
    return str(resolved)


def classify(member: str) -> tuple[str, str] | None:
    """Arşiv içi yolu (split, label) çiftine çevirir.

    'RWF-2000/train/Fight/xyz.avi' -> ('train', 'fight')
    Beklenmeyen yapıdaki girdiler için None döner.
    """
    parts = [p for p in member.replace("\\", "/").split("/") if p]
    if len(parts) < 3:
        return None
    split = parts[-3].lower()
    label = parts[-2].lower()
    if split not in {"train", "val"}:
        return None
    if label not in {"fight", "nonfight"}:
        return None
    return split, label


def main() -> int:
    parser = argparse.ArgumentParser(description="RWF-2000 arşivini kısa adlarla çıkarır")
    parser.add_argument("--zip", type=Path, default=None, help="Arşiv yolu (boşsa otomatik aranır)")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="Hedef dizin")
    parser.add_argument("--dry-run", action="store_true", help="Yazmadan sadece planı göster")
    args = parser.parse_args()

    zip_path = args.zip or find_zip()
    if zip_path is None or not zip_path.is_file():
        print("HATA: RWF2000.zip bulunamadı. --zip ile yolunu ver.", file=sys.stderr)
        print("Aranan yerler:", file=sys.stderr)
        for d in SEARCH_DIRS:
            print(f"  {d}", file=sys.stderr)
        return 1

    dest: Path = args.dest
    print(f"Arşiv  : {zip_path}  ({zip_path.stat().st_size / 1024**3:.1f} GB)")
    print(f"Hedef  : {dest}")
    if args.dry_run:
        print("MOD    : DENEME (hiçbir şey yazılmayacak)")
    print()

    with zipfile.ZipFile(zip_path) as archive:
        members = [i for i in archive.infolist() if not i.is_dir()]

        # (split, label) -> [ZipInfo, ...]  — sıralı ki numaralar deterministik olsun
        groups: dict[tuple[str, str], list[zipfile.ZipInfo]] = {}
        skipped: list[str] = []
        for info in members:
            key = classify(info.filename)
            if key is None:
                skipped.append(info.filename)
                continue
            groups.setdefault(key, []).append(info)
        for items in groups.values():
            items.sort(key=lambda i: i.filename)

        print("Bulunan içerik:")
        for (split, label), items in sorted(groups.items()):
            print(f"  {split:<6} / {label:<9} {len(items):>5} dosya")
        if skipped:
            print(f"  (tanınmayan {len(skipped)} girdi atlanacak)")
        print()

        if args.dry_run:
            return 0

        manifest_rows: list[dict[str, str]] = []
        total = sum(len(v) for v in groups.values())
        done = 0
        reused = 0
        started = time.monotonic()

        for (split, label), items in sorted(groups.items()):
            out_dir = dest / split / label
            out_dir.mkdir(parents=True, exist_ok=True)

            for index, info in enumerate(items, start=1):
                suffix = Path(info.filename).suffix.lower() or ".avi"
                out_name = f"{label}_{index:04d}{suffix}"
                out_path = out_dir / out_name
                manifest_rows.append(
                    {
                        "split": split,
                        "label": label,
                        "new_name": out_name,
                        "size_bytes": str(info.file_size),
                        "original_name": info.filename,
                    }
                )

                # Yeniden çalıştırmada tamamlananları atla (kesinti dostu)
                if out_path.exists() and out_path.stat().st_size == info.file_size:
                    reused += 1
                    done += 1
                    continue

                with archive.open(info) as src, open(long_path(out_path), "wb") as dst:
                    while chunk := src.read(1 << 20):
                        dst.write(chunk)

                done += 1
                if done % 100 == 0 or done == total:
                    elapsed = time.monotonic() - started
                    rate = done / elapsed if elapsed > 0 else 0
                    eta = (total - done) / rate if rate > 0 else 0
                    print(
                        f"  {done:>5}/{total}  ({done / total:5.1%})  "
                        f"{rate:5.1f} dosya/sn  kalan ~{eta / 60:4.1f} dk",
                        flush=True,
                    )

        manifest = dest / "manifest.csv"
        with open(manifest, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["split", "label", "new_name", "size_bytes", "original_name"],
            )
            writer.writeheader()
            writer.writerows(manifest_rows)

        print()
        print(f"TAMAM. {done} dosya hazır ({reused} tanesi zaten mevcuttu).")
        print(f"Manifest: {manifest}")
        print()
        print("Kaynak atfı — rapora yazılacak:")
        print("  Cheng, Hou, Zhang, Chen — 'RWF-2000: An Open Large Scale Video")
        print("  Database for Violence Detection', arXiv:1911.05913")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
