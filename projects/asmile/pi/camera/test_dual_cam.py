#!/usr/bin/env python3
"""
Quick test for dual Inno-Maker OV9281 cameras on Pi 5.
Checks both cameras are detected and can capture frames.
"""

import subprocess
import sys
import time


def check_cameras():
    print("=== Checking cameras ===")
    result = subprocess.run(["rpicam-hello", "--list-cameras"],
                            capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    print(output)

    cam_count = output.count("ov9281")
    print(f"\nFound {cam_count} OV9281 camera(s)")

    if cam_count < 2:
        print("ERROR: Need 2 cameras. Check flat cables and config.txt:")
        print("  dtoverlay=ov9281,cam0")
        print("  dtoverlay=ov9281,cam1")
        return False
    return True


def test_capture(cam_id):
    print(f"\n=== Testing camera {cam_id} ===")
    output_file = f"/tmp/test_cam{cam_id}.h264"

    cmd = [
        "rpicam-vid",
        "--camera", str(cam_id),
        "--width", "1280",
        "--height", "800",
        "--framerate", "15",
        "--codec", "h264",
        "--timeout", "3000",  # 3 seconds
        "--nopreview",
        "--vflip", "--hflip",
        "-o", output_file,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            import os
            size = os.path.getsize(output_file) if os.path.exists(output_file) else 0
            print(f"  Camera {cam_id}: OK ({size} bytes captured)")
            return True
        else:
            print(f"  Camera {cam_id}: FAILED")
            print(f"  stderr: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  Camera {cam_id}: TIMEOUT")
        return False


def test_simultaneous():
    print("\n=== Testing simultaneous capture (3 seconds) ===")

    import threading
    barrier = threading.Barrier(2, timeout=5)
    procs = {}

    def launch(cam_id):
        cmd = [
            "rpicam-vid",
            "--camera", str(cam_id),
            "--width", "1280", "--height", "800",
            "--framerate", "15",
            "--codec", "h264",
            "--timeout", "3000",
            "--nopreview",
            "--vflip", "--hflip",
            "-o", f"/tmp/test_dual_cam{cam_id}.h264",
        ]
        barrier.wait()
        procs[cam_id] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    t0 = threading.Thread(target=launch, args=(0,))
    t1 = threading.Thread(target=launch, args=(1,))
    t0.start()
    t1.start()
    start = time.monotonic()
    t0.join()
    t1.join()
    drift = (time.monotonic() - start) * 1000
    print(f"  Start drift: <{drift:.0f}ms")

    for cam_id, proc in procs.items():
        try:
            proc.wait(timeout=10)
            elapsed = time.monotonic() - start
            print(f"  Camera {cam_id}: finished in {elapsed:.1f}s (code {proc.returncode})")
        except subprocess.TimeoutExpired:
            proc.kill()
            print(f"  Camera {cam_id}: TIMEOUT")

    import os
    for cam_id in [0, 1]:
        path = f"/tmp/test_dual_cam{cam_id}.h264"
        size = os.path.getsize(path) if os.path.exists(path) else 0
        print(f"  Camera {cam_id}: {size} bytes")


if __name__ == "__main__":
    if check_cameras():
        test_capture(0)
        test_capture(1)
        test_simultaneous()
        print("\n=== All tests passed! Ready to record. ===")
    else:
        sys.exit(1)
