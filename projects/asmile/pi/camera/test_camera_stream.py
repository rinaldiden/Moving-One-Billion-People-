#!/usr/bin/env python3
"""
Quick test to verify camera stream (RTSP or local) works.
Shows live feed with FPS counter. Press 'q' to quit.
"""

import cv2
import sys
import time
import argparse


def main():
    p = argparse.ArgumentParser(description="Test camera stream")
    p.add_argument("--source", default="rtsp://192.168.1.112:8554/stream",
                   help="RTSP URL or camera index (0, 1, ...)")
    p.add_argument("--timeout", type=int, default=10,
                   help="Connection timeout in seconds")
    args = p.parse_args()

    source = args.source
    try:
        source = int(source)
    except ValueError:
        pass

    print(f"Connecting to: {source}")

    if isinstance(source, str) and source.startswith("rtsp://"):
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
    else:
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"ERROR: Cannot open {source}")
        sys.exit(1)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps_cam = cap.get(cv2.CAP_PROP_FPS)
    print(f"Stream opened: {w}x{h} @ {fps_cam:.1f} FPS (reported)")

    frame_count = 0
    start = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Lost frame, retrying...")
            time.sleep(0.1)
            continue

        frame_count += 1
        elapsed = time.time() - start
        fps = frame_count / elapsed if elapsed > 0 else 0

        cv2.putText(frame, f"FPS: {fps:.1f} | {w}x{h}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("Camera Test", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"Average FPS: {fps:.1f}")


if __name__ == "__main__":
    main()
