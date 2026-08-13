"""Test tüketicisi — boru hattının uçtan uca çalıştığını doğrular.

Ne yapar
--------
Valkey Stream'den kare meta verilerini okur, **paylaşımlı bellekten gerçek
pikselleri alır** ve slotu havuza geri verir. Yani ingest worker'ın ürettiği
zinciri kapatır.

Neden önemli
------------
Paylaşımlı bellek mimarisinin gerçekten çalıştığını kanıtlar: bu betik
**ayrı bir süreçtir** ve ingest worker'ın yazdığı karelere sıfır kopyalama
ile erişir. Kareler Valkey'den geçmiyor — geçseydi saniyede ~200 MB
serileştirme yapılırdı.

Gün 4'te bu betiğin yerini GPU çıkarım worker'ı alacak; sözleşme aynı
kalacak (oku → işle → slotu bırak → ACK).

Kullanım
--------
    # 1. terminal
    uv run python -m sentinel.ingest.worker --all --owner --duration 120
    # 2. terminal
    uv run python scripts/consume_frames.py --duration 120
"""

from __future__ import annotations

import argparse
import signal
import time
from collections import Counter
from types import FrameType

import numpy as np

from sentinel.bus.shm import DEFAULT_SLOT_BYTES, FramePool, FramePoolError
from sentinel.bus.streams import FrameStream, SlotAllocator, connect
from sentinel.config import settings
from sentinel.logging import configure_logging, get_logger

log = get_logger(__name__)

GROUP = "test-consumers"
_stop = False


def _handle_signal(_sig: int, _frame: FrameType | None) -> None:
    global _stop
    _stop = True


def main() -> int:
    parser = argparse.ArgumentParser(description="Kare tüketicisi (test)")
    parser.add_argument("--consumer-id", default="consumer-0")
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--work-ms", type=float, default=0.0,
                        help="Kare başına yapay iş yükü (GPU çıkarımını taklit eder)")
    parser.add_argument("--stats-interval", type=float, default=5.0)
    args = parser.parse_args()

    configure_logging(settings.log_level)
    signal.signal(signal.SIGINT, _handle_signal)

    client = connect()
    stream = FrameStream(client)
    allocator = SlotAllocator(client, settings.shm_slot_count)
    stream.ensure_group(GROUP)

    try:
        pool = FramePool(slot_count=settings.shm_slot_count, slot_bytes=DEFAULT_SLOT_BYTES)
    except FramePoolError as exc:
        print(f"HATA: {exc}")
        return 1

    print(f"Tüketici '{args.consumer_id}' başladı — grup '{GROUP}'")
    print("Kareler paylaşımlı bellekten SIFIR KOPYALAMA ile okunuyor.\n")

    consumed = 0
    by_camera: Counter[str] = Counter()
    checksum_ok = 0
    started = time.monotonic()
    last_report = started
    deadline = started + args.duration if args.duration else None

    try:
        while not _stop:
            batch = list(stream.consume(GROUP, args.consumer_id, count=16, block_ms=1000))
            released: list[int] = []
            acks: list[str] = []

            for message in batch:
                # Paylaşımlı bellekten oku (kopyalamadan)
                image = pool.read(message.ref)

                # Verinin gerçekten geldiğini doğrula: tamamen sıfır olmamalı
                if int(np.count_nonzero(image[::16, ::16])) > 0:
                    checksum_ok += 1

                if args.work_ms > 0:
                    time.sleep(args.work_ms / 1000.0)

                by_camera[message.camera] += 1
                consumed += 1
                released.append(message.ref.slot)
                acks.append(message.message_id)

            # Slotları toplu geri ver — havuz tıkanmasın
            allocator.release_many(released)
            stream.ack(GROUP, *acks)

            now = time.monotonic()
            if now - last_report >= args.stats_interval:
                elapsed = now - started
                print(
                    f"  {consumed:>6} kare · {consumed / elapsed:5.1f} FPS · "
                    f"{len(by_camera)} kamera · boş slot {allocator.available}/"
                    f"{settings.shm_slot_count} · kuyruk {stream.depth}",
                    flush=True,
                )
                last_report = now

            if deadline and now >= deadline:
                break
    finally:
        elapsed = time.monotonic() - started
        print()
        print(f"{'KAMERA':<16} {'KARE':>8} {'FPS':>7}")
        print("-" * 33)
        for camera, count in sorted(by_camera.items()):
            print(f"{camera:<16} {count:>8} {count / elapsed:>7.2f}")
        print()
        print(f"Toplam {consumed} kare · {consumed / elapsed:.1f} FPS · {elapsed:.0f} saniye")
        print(f"Veri doğrulaması: {checksum_ok}/{consumed} karede gerçek piksel var")
        pool.close()
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
