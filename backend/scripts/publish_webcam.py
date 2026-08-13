"""Laptop webcam'ini "Kamera 21 — Canlı" olarak yayınlar.

Neden ayrı bir betik
--------------------
`cam-21-live` yolu MediaMTX'te `source: publisher` olarak tanımlıdır —
yani MediaMTX kendiliğinden webcam'e bağlanmaz, birinin yayın göndermesini
bekler. Bu bilinçli bir tercih: **kamera yalnızca sen istediğinde açılır.**
Arka planda sürekli açık kalan bir webcam ne mahremiyet açısından ne de
pil açısından kabul edilebilir.

Neden ffmpeg değil PyAV
-----------------------
Host'ta ffmpeg kurulu değil (kamera çiftliği betiği konteynerdekini
kullanıyor, ama konteyner host'un webcam'ine erişemez). PyAV ve OpenCV
zaten kurulu; ek bağımlılık gerekmiyor. Ayrıca kabuğa çıkmıyoruz (G09).

Kullanım
--------
    uv run python scripts/publish_webcam.py            # başlat, Ctrl+C ile dur
    uv run python scripts/publish_webcam.py --list     # kameraları listele
    uv run python scripts/publish_webcam.py --device 1 --fps 20

Yayın başlayınca panelde (http://127.0.0.1:8001) cam-21-live yeşile döner.
"""

from __future__ import annotations

import argparse
import fractions
import signal
import sys
import time
from types import FrameType

import av
import cv2

# OpenCV 5 + Windows: CAP_DSHOW "can't be used to capture by index" uyarısı
# veriyor. CAP_ANY, OpenCV'nin çalışan arka ucu (MSMF) seçmesini sağlıyor.
BACKEND = cv2.CAP_ANY

DEFAULT_PATH = "cam-21-live"
DEFAULT_RTSP = "rtsp://127.0.0.1:8554"

_stop = False


def _handle_signal(_sig: int, _frame: FrameType | None) -> None:
    global _stop
    _stop = True
    print("\nDurduruluyor…")


def list_devices(max_index: int = 5) -> None:
    """Bağlı kameraları tarar."""
    print("Kamera taranıyor (birkaç saniye sürebilir)…\n")
    found = 0
    for index in range(max_index):
        cap = cv2.VideoCapture(index, BACKEND)
        if cap.isOpened():
            ok, frame = cap.read()
            if ok and frame is not None:
                h, w = frame.shape[:2]
                print(f"  --device {index}   {w}×{h}")
                found += 1
            cap.release()
    if not found:
        print("  Kamera bulunamadı. Başka bir uygulama kullanıyor olabilir.")


def publish(device: int, fps: int, width: int, height: int, url: str) -> int:
    cap = cv2.VideoCapture(device, BACKEND)
    if not cap.isOpened():
        print(f"HATA: kamera {device} açılamadı. --list ile mevcutları gör.", file=sys.stderr)
        return 1

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # gecikme birikmesin

    ok, probe = cap.read()
    if not ok or probe is None:
        print("HATA: kameradan kare okunamadı.", file=sys.stderr)
        cap.release()
        return 1
    actual_h, actual_w = probe.shape[:2]

    try:
        output = av.open(url, mode="w", format="rtsp", options={"rtsp_transport": "tcp"})
    except av.error.FFmpegError as exc:
        print(f"HATA: MediaMTX'e bağlanılamadı ({url}): {exc}", file=sys.stderr)
        print("Altyapı ayakta mı?  docker compose ps", file=sys.stderr)
        cap.release()
        return 1

    stream = output.add_stream("libx264", rate=fps)
    stream.width = actual_w
    stream.height = actual_h
    stream.pix_fmt = "yuv420p"
    stream.time_base = fractions.Fraction(1, fps)
    stream.options = {
        "preset": "ultrafast",
        "tune": "zerolatency",
        # ⚠ B-frame KAPALI — WebRTC desteklemiyor (problems.md P-08)
        "bf": "0",
        "g": str(fps * 2),
    }

    signal.signal(signal.SIGINT, _handle_signal)
    print(f"Yayın başladı → {url}")
    print(f"  Çözünürlük : {actual_w}×{actual_h} @ {fps} FPS")
    print("  Panelde cam-21-live yeşile dönecek. Durdurmak için Ctrl+C.\n")

    sent = 0
    started = time.monotonic()
    interval = 1.0 / fps
    next_frame_at = started

    try:
        while not _stop:
            ok, frame = cap.read()
            if not ok:
                print("Kameradan kare gelmedi, duruluyor.", file=sys.stderr)
                break

            av_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
            av_frame.pts = sent
            av_frame.time_base = stream.time_base
            for packet in stream.encode(av_frame):
                output.mux(packet)

            sent += 1
            if sent % (fps * 5) == 0:
                elapsed = time.monotonic() - started
                print(f"  {sent:>6} kare · {sent / elapsed:.1f} FPS · {elapsed:.0f} sn", flush=True)

            # Gerçek zamanlı hızda tut
            next_frame_at += interval
            sleep_for = next_frame_at - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_frame_at = time.monotonic()
    finally:
        for packet in stream.encode():  # tamponu boşalt
            output.mux(packet)
        output.close()
        cap.release()
        elapsed = time.monotonic() - started
        print(f"\nYayın kapandı. {sent} kare, {elapsed:.0f} saniye.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Webcam'i cam-21-live olarak yayınlar")
    parser.add_argument("--list", action="store_true", help="Kameraları listele ve çık")
    parser.add_argument("--device", type=int, default=0, help="Kamera indeksi")
    parser.add_argument("--fps", type=int, default=25)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--path", default=DEFAULT_PATH, help="MediaMTX yol adı")
    parser.add_argument("--rtsp", default=DEFAULT_RTSP, help="MediaMTX RTSP adresi")
    args = parser.parse_args()

    if args.list:
        list_devices()
        return 0

    return publish(args.device, args.fps, args.width, args.height, f"{args.rtsp}/{args.path}")


if __name__ == "__main__":
    raise SystemExit(main())
