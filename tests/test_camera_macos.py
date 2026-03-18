"""Standalone camera capture test — macOS (AVFoundation).

Verifies that cv2.VideoCapture delivers the requested FPS and resolution.
Pixel format is skipped — AVFoundation does not expose FOURCC reliably.

Usage:
    python tests/test_camera_macos.py
    python tests/test_camera_macos.py --device 0 --fps 15 --frames 60
    python tests/test_camera_macos.py --device 1 --width 320 --height 240
"""

import argparse
import sys
import time

import cv2


_FPS_TOLERANCE = 0.15  # 15%


def parse_args():
    p = argparse.ArgumentParser(description="Camera capture test (macOS)")
    p.add_argument("--device", type=int, default=0, help="Camera index (default: 0)")
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--frames", type=int, default=60, help="Frames to capture for FPS measurement")
    return p.parse_args()


def section(title):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


def row(label, requested, configured, measured=None, ok=None):
    r = str(requested)
    c = str(configured)
    m = str(measured) if measured is not None else "—"
    status = ""
    if ok is True:
        status = "✓"
    elif ok is False:
        status = "✗  <-- MISMATCH"
    print(f"  {label:<14}  req={r:<10} cfg={c:<10} meas={m:<10}  {status}")


def main():
    if sys.platform != "darwin":
        print("This script is for macOS only. Use test_camera_capture.py on Linux.")
        sys.exit(1)

    args = parse_args()

    section("Requested config")
    print(f"  device={args.device}  {args.width}x{args.height}  fps={args.fps}  measure_over={args.frames} frames")

    section("Opening camera")
    cap = cv2.VideoCapture(args.device, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        print(f"  ERROR: could not open camera index {args.device}")
        sys.exit(1)
    print(f"  Opened camera index {args.device}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)

    cfg_width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cfg_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cfg_fps    = cap.get(cv2.CAP_PROP_FPS)

    section("Warming up (5 frames)")
    for _ in range(5):
        cap.read()

    section(f"Capturing {args.frames} frames")
    t0 = time.monotonic()
    captured = 0
    frame = None
    for i in range(args.frames):
        ret, frame = cap.read()
        if not ret:
            print(f"  WARNING: failed to read frame {i}")
            break
        captured += 1
        if (i + 1) % 10 == 0:
            elapsed = time.monotonic() - t0
            print(f"  frame {i+1:>4}/{args.frames}  elapsed={elapsed:.2f}s")

    elapsed = time.monotonic() - t0
    measured_fps = captured / elapsed if elapsed > 0 else 0.0
    actual_h, actual_w = frame.shape[:2] if frame is not None else (0, 0)

    cap.release()

    section("Results")

    fps_ok = abs(measured_fps - args.fps) / args.fps <= _FPS_TOLERANCE
    dim_ok = (cfg_width == args.width) and (cfg_height == args.height)

    row("resolution",  f"{args.width}x{args.height}", f"{cfg_width}x{cfg_height}",
        f"{actual_w}x{actual_h}", ok=dim_ok)
    row("fps",         args.fps, f"{cfg_fps:.1f}", f"{measured_fps:.2f}", ok=fps_ok)
    print(f"  {'pixel format':<14}  (skipped — AVFoundation does not expose FOURCC reliably)")

    print()
    passed = fps_ok and dim_ok
    if passed:
        print("  PASS — all checks within tolerance")
    else:
        print("  FAIL — one or more checks failed")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
