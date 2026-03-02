#!/usr/bin/env python3
"""
RTSP streaming – Arducam Camarray dual OV9281 su Raspberry Pi 5

Stereo side-by-side 1280x400 GREY → H264 → RTSP via MediaMTX

Avvio MANUALE:  python3 rtsp_stream.py
Stop:           Ctrl+C

CPU stimata: ~28% a 15fps
"""

import subprocess, signal, sys, time, os

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIAMTX_BIN = os.path.join(WORK_DIR, "mediamtx")
MEDIAMTX_CFG = os.path.join(WORK_DIR, "mediamtx.yml")
ARDUCAM_FIX  = os.path.join(WORK_DIR, "arducam_fix.so")

# ──── Parametri modificabili ────
WIDTH   = 1280
HEIGHT  = 400
FPS     = 15       # ← CAMBIA QUI: 15 = leggero (~28% CPU), 30 = più fluido (~50% CPU)
BITRATE = 500_000  # ← CAMBIA QUI: 500k = leggero, 800k-1500k = più qualità
# ────────────────────────────────


def build_gst_pipeline() -> list[str]:
    return [
        "gst-launch-1.0", "-e",
        "libcamerasrc",
        "!", f"video/x-raw,width={WIDTH},height={HEIGHT},framerate={FPS}/1",
        "!", "queue",
        "!", "videoconvert",
        "!", "video/x-raw,format=I420",
        "!", "openh264enc",
            f"bitrate={BITRATE}",
            f"max-bitrate={int(BITRATE * 1.25)}",
            f"gop-size={FPS}",
            "enable-frame-skip=true",
        "!", "h264parse",
        "!", "rtspclientsink",
            "location=rtsp://127.0.0.1:8554/stream",
            "protocols=tcp",
    ]


procs: list[subprocess.Popen] = []


def cleanup(sig=None, frame=None):
    print("\n[*] Stopping...")
    for p in reversed(procs):
        try:
            p.terminate()
        except ProcessLookupError:
            pass
    for p in reversed(procs):
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def build_env() -> dict:
    env = os.environ.copy()
    if os.path.isfile(ARDUCAM_FIX):
        existing = env.get("LD_PRELOAD", "")
        env["LD_PRELOAD"] = (ARDUCAM_FIX + ":" + existing).strip(":")
    else:
        print(f"[!] WARNING: {ARDUCAM_FIX} not found — camera may not work")
    return env


def main():
    for f, name in [(MEDIAMTX_BIN, "mediamtx"), (MEDIAMTX_CFG, "mediamtx.yml")]:
        if not os.path.isfile(f):
            print(f"[!] {name} not found at {f}")
            sys.exit(1)

    print("[*] Starting MediaMTX...")
    mtx = subprocess.Popen(
        [MEDIAMTX_BIN, MEDIAMTX_CFG],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    procs.append(mtx)
    time.sleep(1.5)

    if mtx.poll() is not None:
        print("[!] MediaMTX failed to start")
        sys.exit(1)

    print(f"[*] Starting GStreamer pipeline ({WIDTH}x{HEIGHT}@{FPS}fps, {BITRATE//1000}kbps)...")
    gst = subprocess.Popen(
        build_gst_pipeline(),
        env=build_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    procs.append(gst)
    time.sleep(4)

    if gst.poll() is not None:
        err = gst.stderr.read().decode(errors="replace")
        print(f"[!] GStreamer pipeline failed:\n{err}")
        cleanup()

    try:
        ip = subprocess.check_output(["hostname", "-I"], text=True).strip().split()[0]
    except Exception:
        ip = "<IP_DEL_PI>"

    print(f"")
    print(f"  ╔═══════════════════════════════════════════╗")
    print(f"  ║  Stream LIVE!                             ║")
    print(f"  ║  rtsp://{ip}:8554/stream         ║")
    print(f"  ║                                           ║")
    print(f"  ║  VLC: Media > Open Network Stream         ║")
    print(f"  ║  Ctrl+C to stop                           ║")
    print(f"  ╚═══════════════════════════════════════════╝")
    print(f"")

    while True:
        if mtx.poll() is not None:
            print("[!] MediaMTX died, stopping...")
            cleanup()
        if gst.poll() is not None:
            print("[!] GStreamer died, stopping...")
            cleanup()
        time.sleep(2)


if __name__ == "__main__":
    main()
