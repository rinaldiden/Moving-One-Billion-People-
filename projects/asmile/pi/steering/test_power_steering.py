#!/usr/bin/env python3
"""
Test power steering by simulating encoder rotation.

Stops the real encoder daemon, writes simulated positions to /tmp/encoder_position,
runs power_steering.py, then restores the real daemon.

Simulates: slow rotation right (+60 steps), pause, slow rotation left (-60 steps), pause, stop.
"""

import subprocess
import time
import os
import sys
import signal
import math

POSITION_FILE = "/tmp/encoder_position"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
POWER_STEERING = os.path.join(SCRIPT_DIR, "power_steering.py")


def write_pos(pos):
    pos = pos % 4096
    tmp = POSITION_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(str(pos))
    os.replace(tmp, POSITION_FILE)


def main():
    # Read current real position as starting point
    try:
        with open(POSITION_FILE) as f:
            start_pos = int(f.read().strip())
    except:
        start_pos = 2048

    print(f"Starting position: {start_pos}")
    print("Stopping encoder daemon for simulation...")
    subprocess.run(["sudo", "systemctl", "stop", "encoder-ssi"], capture_output=True)
    time.sleep(0.5)

    # Write initial position
    write_pos(start_pos)

    # Launch power steering
    print("Launching power_steering.py...")
    ps_proc = subprocess.Popen(
        [sys.executable, POWER_STEERING],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    time.sleep(1.0)  # Let it initialize

    try:
        pos = start_pos

        # Phase 1: Rotate right slowly (+60 steps over 2s)
        print("\n--- Phase 1: Slow rotation RIGHT (+60 steps, 2s) ---")
        steps = 60
        duration = 2.0
        for i in range(steps):
            pos += 1
            write_pos(pos)
            time.sleep(duration / steps)

        # Pause 1.5s
        print("--- Pause 1.5s ---")
        time.sleep(1.5)

        # Phase 2: Rotate left faster (-60 steps over 1s)
        print("--- Phase 2: Faster rotation LEFT (-60 steps, 1s) ---")
        steps = 60
        duration = 1.0
        for i in range(steps):
            pos -= 1
            write_pos(pos)
            time.sleep(duration / steps)

        # Pause 1.5s
        print("--- Pause 1.5s ---")
        time.sleep(1.5)

        # Phase 3: Quick burst right (+30 steps, 0.3s)
        print("--- Phase 3: Quick burst RIGHT (+30 steps, 0.3s) ---")
        steps = 30
        duration = 0.3
        for i in range(steps):
            pos += 1
            write_pos(pos)
            time.sleep(duration / steps)

        # Let it decay
        print("--- Decay 2s ---")
        time.sleep(2.0)

    finally:
        # Stop power steering
        ps_proc.send_signal(signal.SIGINT)
        time.sleep(0.5)

        # Print output
        out, _ = ps_proc.communicate(timeout=3)
        print("\n=== Power Steering Output ===")
        print(out)

        # Restore encoder daemon
        print("Restoring encoder daemon...")
        subprocess.run(["sudo", "systemctl", "start", "encoder-ssi"], capture_output=True)
        time.sleep(0.5)
        print("Done.")


if __name__ == "__main__":
    main()
