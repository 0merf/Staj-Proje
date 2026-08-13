"""WebSocket kanalını uçtan uca doğrular.

Test edilenler:
1. **Origin doğrulaması (G06)** — Origin başlığı olmayan bağlantı
   reddedilmeli. WebSocket CORS'a uymadığı için bu kontrol elle yapılıyor;
   çalıştığını kanıtlamak önemli.
2. Yanlış Origin reddedilmeli.
3. Doğru Origin ile bağlantı → hello → subscribe → sonuç akışı.

Kullanım (ingest + inference worker çalışırken):
    uv run python scripts/test_websocket.py
    uv run python scripts/test_websocket.py --cameras cam-09 --seconds 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter

import websockets
from websockets.exceptions import InvalidStatus, WebSocketException

URL = "ws://127.0.0.1:8001/ws/live"
GOOD_ORIGIN = "http://localhost:5173"
BAD_ORIGIN = "http://evil.example.com"


async def expect_rejection(label: str, origin: str | None) -> bool:
    """Bağlantının reddedildiğini doğrular."""
    headers = {"Origin": origin} if origin else None
    try:
        async with websockets.connect(URL, additional_headers=headers) as ws:
            # Kabul edilmiş olsa bile sunucu hemen kapatmalı
            try:
                await asyncio.wait_for(ws.recv(), timeout=2.0)
            except (TimeoutError, WebSocketException):
                print(f"  ✅ {label}: reddedildi (bağlantı kapatıldı)")
                return True
        print(f"  ❌ {label}: KABUL EDİLDİ — güvenlik açığı!")
        return False
    except (InvalidStatus, WebSocketException, OSError):
        print(f"  ✅ {label}: reddedildi")
        return True


async def consume(cameras: list[str], seconds: float) -> bool:
    """Doğru Origin ile bağlanıp sonuç akışını dinler."""
    async with websockets.connect(URL, additional_headers={"Origin": GOOD_ORIGIN}) as ws:
        hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
        if hello.get("type") != "hello":
            print(f"  ❌ beklenen 'hello', gelen: {hello.get('type')}")
            return False
        print(f"  ✅ hello alındı — {hello.get('note', '')}")

        await ws.send(json.dumps({"type": "subscribe", "cameras": cameras}))
        ack = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
        print(f"  ✅ abone olundu: {ack.get('cameras') or '(tümü)'}")

        by_camera: Counter[str] = Counter()
        detections = 0
        total_bytes = 0
        frames = 0
        deadline = asyncio.get_running_loop().time() + seconds

        while asyncio.get_running_loop().time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
            except TimeoutError:
                break
            total_bytes += len(raw)
            message = json.loads(raw)
            if message.get("type") != "frame":
                continue
            frames += 1
            by_camera[message["cam"]] += 1
            detections += message.get("count", 0)

        print()
        if frames == 0:
            print("  ⚠ Hiç kare gelmedi. ingest + inference worker çalışıyor mu?")
            return False

        print(f"{'KAMERA':<16} {'KARE':>7} {'FPS':>7}")
        print("-" * 32)
        for camera, count in sorted(by_camera.items()):
            print(f"{camera:<16} {count:>7} {count / seconds:>7.2f}")
        print()
        print(f"  Toplam {frames} kare · {frames / seconds:.1f} FPS · {detections} tespit")
        print(f"  Bant genişliği: {total_bytes / seconds / 1024:.1f} KB/sn "
              f"(mesaj başına ort. {total_bytes / frames:.0f} bayt)")
        print(f"  Kamera sayısı : {len(by_camera)}")
        return True


async def main_async(args: argparse.Namespace) -> int:
    print("1) GÜVENLİK — Origin doğrulaması (G06)\n")
    checks = [
        await expect_rejection("Origin YOK", None),
        await expect_rejection("Origin yanlış (evil.example.com)", BAD_ORIGIN),
    ]
    if not all(checks):
        print("\n  ⚠ Origin doğrulaması çalışmıyor — düzeltilmeden devam edilmemeli.")
        return 1

    print(f"\n2) VERİ AKIŞI — {args.seconds} saniye dinleniyor\n")
    ok = await consume(args.cameras or [], args.seconds)
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="WebSocket kanalı testi")
    parser.add_argument("--cameras", nargs="*", help="Abone olunacak kameralar (boş = tümü)")
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
