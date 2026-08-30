"""İlk yönetici hesabını (ya da yeni bir kullanıcı) oluşturur.

⚠ NEDEN BETİK, NEDEN "İLK AÇILIŞTA VARSAYILAN ADMIN"
Bazı sistemler ilk açılışta `admin/admin` gibi bir hesap yaratır. Bu,
sahada en sık sömürülen açıklardan biri: kimse değiştirmiyor ve
varsayılan parolalar internette listeli.

Bu proje hiçbir hesabı kendiliğinden yaratmıyor. Hesap AÇIKÇA
oluşturulmalı ve parola operatör tarafından verilmeli.

⚠ PAROLA KOMUT SATIRINDA VERİLMİYOR. Komut geçmişine (`history`) ve
süreç listesine (`ps`, Görev Yöneticisi) düşer. `getpass` ile
sorulyor — ekrana da yazılmıyor.

Kullanım
--------
    uv run python scripts/kullanici_ekle.py admin --rol admin
    uv run python scripts/kullanici_ekle.py operator1 --rol operator
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

# Kısa parola, güçlü hash'i anlamsız kılar: Argon2 kaba kuvveti
# yavaşlatır ama 6 haneli bir parolayı yine de dakikalar içinde bulur.
ASGARI_UZUNLUK = 12


async def _calistir(kullanici_adi: str, rol: str, parola: str) -> int:
    from sentinel.api.guvenlik import Rol, parola_hashle
    from sentinel.db import kullanicilar
    from sentinel.db.engine import kapat, motor

    if rol not in {r.value for r in Rol}:
        print(f"Geçersiz rol: {rol}. Seçenekler: {[r.value for r in Rol]}", file=sys.stderr)
        return 1

    async with motor().begin() as baglanti:
        await kullanicilar.semayi_kur(baglanti)
    await kullanicilar.kullanici_ekle(kullanici_adi, parola_hashle(parola), rol)
    await kullanicilar.denetim_yaz(
        "kullanici_olusturuldu", kullanici_adi=kullanici_adi, hedef=rol
    )
    await kapat()
    print(f"✓ {kullanici_adi} ({rol}) kaydedildi")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Kullanıcı oluştur ya da parolasını değiştir")
    ap.add_argument("kullanici_adi")
    ap.add_argument("--rol", default="viewer", help="viewer | operator | admin")
    ap.add_argument(
        "--uret",
        action="store_true",
        help="parolayı rastgele üret ve ekrana yaz (ilk kurulum için)",
    )
    args = ap.parse_args()

    if args.uret:
        # ⚠ `secrets`, `random` DEĞİL. `random` tahmin edilebilir bir
        # sözde rastgele üreteç; parola üretiminde kullanılmamalı.
        parola = secrets.token_urlsafe(18)
        print(f"Üretilen parola: {parola}\n⚠ Bunu güvenli bir yere kaydedin, tekrar gösterilmeyecek.\n")
    else:
        parola = getpass.getpass("Parola: ")
        if parola != getpass.getpass("Parola (tekrar): "):
            print("Parolalar eşleşmiyor.", file=sys.stderr)
            return 1

    if len(parola) < ASGARI_UZUNLUK:
        print(f"Parola en az {ASGARI_UZUNLUK} karakter olmalı.", file=sys.stderr)
        return 1

    return asyncio.run(_calistir(args.kullanici_adi, args.rol, parola))


if __name__ == "__main__":
    raise SystemExit(main())
