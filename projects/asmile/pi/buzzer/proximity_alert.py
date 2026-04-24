#!/usr/bin/env python3
"""
Asmile Proximity Alert — Tesla-style buzzer warning

Beep frequency increases as objects get closer.
Uses stereo depth estimation to measure distance to nearest obstacle.

Zones:
  > 3.0m  — silence
  2.0-3.0m — slow beeps
  1.0-2.0m — medium beeps
  0.5-1.0m — fast beeps
  < 0.5m  — continuous tone

Input: distance in meters (from stereo depth or segmentation pipeline)
Output: buzzer beeps on GPIO 5 via Level Shifter #2 ch4
"""

import lgpio
import time
import threading

GPIO_CHIP = 4
BUZZER_PIN = 5
FREQ_HZ = 2500

# Distance thresholds (meters) and beep intervals (seconds)
ZONES = [
    (0.5, 0.0),    # < 0.5m  → continuous
    (1.0, 0.10),   # 0.5-1.0m → very fast
    (2.0, 0.30),   # 1.0-2.0m → medium
    (3.0, 0.60),   # 2.0-3.0m → slow
]
SAFE_DISTANCE = 3.0  # > 3m = no alert


class ProximityAlert:
    def __init__(self):
        self.h = lgpio.gpiochip_open(GPIO_CHIP)
        self._running = False
        self._distance = SAFE_DISTANCE + 1
        self._thread = None

    def _beep_loop(self):
        while self._running:
            d = self._distance

            if d > SAFE_DISTANCE:
                time.sleep(0.1)
                continue

            # Find zone
            interval = None
            for threshold, intv in ZONES:
                if d < threshold:
                    interval = intv
                    break

            if interval is None:
                time.sleep(0.1)
                continue

            # Continuous tone
            if interval == 0.0:
                lgpio.tx_pwm(self.h, BUZZER_PIN, FREQ_HZ, 50)
                while self._running and self._distance < ZONES[0][0]:
                    time.sleep(0.05)
                lgpio.tx_pwm(self.h, BUZZER_PIN, 0, 0)
                continue

            # Beep
            lgpio.tx_pwm(self.h, BUZZER_PIN, FREQ_HZ, 50)
            time.sleep(0.05)
            lgpio.tx_pwm(self.h, BUZZER_PIN, 0, 0)
            time.sleep(interval)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._beep_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        lgpio.tx_pwm(self.h, BUZZER_PIN, 0, 0)
        if self._thread:
            self._thread.join(timeout=1)

    def update(self, distance_m):
        """Call this with the latest distance to nearest obstacle."""
        self._distance = distance_m

    def close(self):
        self.stop()
        lgpio.gpiochip_close(self.h)


# --- Demo: simulate approaching an object ---
if __name__ == "__main__":
    alert = ProximityAlert()
    alert.start()
    print("Simulating approach...")
    try:
        for d in [4.0, 3.5, 2.8, 2.2, 1.8, 1.3, 0.9, 0.7, 0.4, 0.3]:
            print(f"  {d:.1f}m")
            alert.update(d)
            time.sleep(1.5)
        alert.update(5.0)
        print("  safe — silence")
        time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        alert.close()
        print("done")
