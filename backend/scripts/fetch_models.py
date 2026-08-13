"""Model ağırlıklarını indirir ve bütünlüklerini kayıt altına alır.

⚠ NEDEN CHECKSUM (PLAN.md §11.4 / G26)
--------------------------------------
`.pt` dosyaları Python **pickle** formatındadır. Pickle yüklemek
**rastgele kod çalıştırmak** demektir — kötü niyetli bir `.pt` dosyası
açıldığı anda sisteme sahip olur. Bu, makine öğrenmesi ekosisteminin en
çok küçümsenen güvenlik riskidir.

Alınan önlemler:
1. Ağırlıklar yalnızca **resmi kaynaktan** indirilir (Ultralytics kendi
   sürüm deposundan çeker).
2. İndirilen her dosyanın SHA256'sı `models/checksums.json`'a yazılır.
3. Sonraki çalıştırmalarda dosya **yeniden doğrulanır**; hash değişmişse
   betik durur. Dosya sessizce değiştiyse haberimiz olur.
4. Uzun vadeli çözüm ONNX/TensorRT'ye ihraç edip `.pt`'yi çalışma
   zamanından tamamen çıkarmaktır — Faz 5 hedefi.

Kullanım
--------
    uv run python scripts/fetch_models.py                 # varsayılan set
    uv run python scripts/fetch_models.py --models yolo26s yolo26s-pose
    uv run python scripts/fetch_models.py --verify        # sadece doğrula
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "models"
CHECKSUMS = MODELS_DIR / "checksums.json"

# Ultralytics bu adları tanır ve resmi sürüm deposundan indirir.
DEFAULT_MODELS = ["yolo26s.pt", "yolo26s-pose.pt"]
FALLBACK_MODELS = ["yolo11s.pt", "yolo11s-pose.pt"]


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def load_checksums() -> dict[str, dict[str, object]]:
    if CHECKSUMS.is_file():
        return json.loads(CHECKSUMS.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    return {}


def save_checksums(data: dict[str, dict[str, object]]) -> None:
    CHECKSUMS.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def fetch(name: str) -> Path | None:
    """Ultralytics üzerinden ağırlığı indirip models/ altına taşır."""
    target = MODELS_DIR / name
    if target.is_file():
        return target

    try:
        from ultralytics import YOLO
    except ImportError:
        print("HATA: ultralytics kurulu değil. Önce:  uv sync --extra gpu", file=sys.stderr)
        return None

    print(f"  {name} indiriliyor (Ultralytics resmi kaynağı)…", flush=True)
    try:
        model = YOLO(name)  # yoksa indirir
    except Exception as exc:
        print(f"  {name}: indirilemedi — {type(exc).__name__}: {str(exc)[:160]}")
        return None

    # Ultralytics çalışma dizinine ya da kendi önbelleğine indirir; bul ve taşı
    candidates = [
        Path(getattr(model, "ckpt_path", "") or ""),
        Path.cwd() / name,
        PROJECT_ROOT / name,
        MODELS_DIR / name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            if candidate != target:
                shutil.move(str(candidate), str(target))
            return target

    print(f"  {name}: indirildi ama dosya bulunamadı", file=sys.stderr)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Model ağırlıklarını indir ve doğrula")
    parser.add_argument("--models", nargs="*", help="İndirilecek ağırlıklar")
    parser.add_argument("--fallback", action="store_true", help="YOLO11 yedek setini kullan")
    parser.add_argument("--verify", action="store_true", help="İndirme yapma, sadece doğrula")
    args = parser.parse_args()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    known = load_checksums()

    if args.verify:
        if not known:
            print("Kayıtlı checksum yok.")
            return 0
        print(f"{'MODEL':<24} {'DURUM':<12} SHA256")
        print("-" * 80)
        failed = 0
        for name, record in sorted(known.items()):
            path = MODELS_DIR / name
            if not path.is_file():
                print(f"{name:<24} {'EKSİK':<12} —")
                failed += 1
                continue
            digest = sha256_of(path)
            ok = digest == record["sha256"]
            print(f"{name:<24} {'TAMAM' if ok else 'BOZULMUŞ!':<12} {digest[:32]}…")
            if not ok:
                failed += 1
        print()
        if failed:
            print(f"⚠ {failed} model doğrulanamadı. Silip yeniden indirin.")
            return 1
        print("Tüm modeller doğrulandı.")
        return 0

    names = args.models or (FALLBACK_MODELS if args.fallback else DEFAULT_MODELS)
    print(f"Hedef dizin: {MODELS_DIR}\n")

    ok_count = 0
    for name in names:
        path = fetch(name)
        if path is None:
            continue

        digest = sha256_of(path)
        size_mb = path.stat().st_size / 1024**2

        previous = known.get(name)
        if previous and previous["sha256"] != digest:
            print(f"  ⚠ {name}: SHA256 DEĞİŞTİ!")
            print(f"      kayıtlı : {previous['sha256']}")
            print(f"      şimdiki : {digest}")
            print("      Dosya değiştirilmiş olabilir. İncelemeden kullanmayın.")
            return 1

        known[name] = {"sha256": digest, "size_bytes": path.stat().st_size}
        print(f"  {name:<20} {size_mb:6.1f} MB   {digest[:24]}…")
        ok_count += 1

    save_checksums(known)
    print(f"\n{ok_count}/{len(names)} model hazır.")
    print(f"Checksum kaydı: {CHECKSUMS.relative_to(PROJECT_ROOT)}")
    print("\nSonraki çalıştırmalarda doğrulamak için:")
    print("  uv run python scripts/fetch_models.py --verify")
    return 0 if ok_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
