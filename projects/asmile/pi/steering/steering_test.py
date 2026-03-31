#!/usr/bin/env python3
"""
Asmile Power Steering — Test interattivo

Comandi:
  +/-  : scale ±0.1
  m/M  : max current ±1A
  s/S  : smoothing ±0.05
  d/D  : deadband ±1
  r/R  : ramp rate ±0.05 A/ciclo
  z    : rezero
  q    : quit
"""

import sys
import time
import select
import termios
import tty
from steering_controller import SteeringController


class RawInput:
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)

    def __enter__(self):
        tty.setraw(self.fd)
        return self

    def __exit__(self, *args):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def get_key(self, timeout=0.05):
        if select.select([sys.stdin], [], [], timeout)[0]:
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                if select.select([sys.stdin], [], [], 0.01)[0]:
                    sys.stdin.read(1)
                    sys.stdin.read(1)
                return None
            return ch
        return None


def main():
    scale = 0.5
    max_current = 5.0
    smoothing = 0.3
    deadband = 2

    ctrl = SteeringController(
        scale=scale,
        max_current=max_current,
        deadband_steps=deadband,
        smoothing=smoothing,
    )

    log_data = {'angle': 0.0, 'cur': 0.0, 'telem': {}}

    def log_fn(t, angle, current, telem):
        log_data['angle'] = angle
        log_data['cur'] = current
        if telem:
            log_data['telem'] = telem

    ctrl.on_log = log_fn

    print("=== Asmile Power Steering — Tuning ===")
    print("Posizione attuale = centro (0°)")

    if not ctrl.start():
        return

    print()
    print("Gira il manubrio — il motore assiste!")
    print("+/-=scale  m/M=max_I  s/S=smooth  d/D=deadband  z=zero  q=quit")
    print()

    last_display = 0

    with RawInput() as raw:
        try:
            while True:
                key = raw.get_key(timeout=0.05)

                if key == 'q' or key == '\x03':
                    break
                elif key == '+' or key == '=':
                    scale += 0.1
                    ctrl.set_scale(scale)
                elif key == '-' or key == '_':
                    scale = max(0.05, scale - 0.1)
                    ctrl.set_scale(scale)
                elif key == 'm':
                    max_current = min(30.0, max_current + 1.0)
                    ctrl.set_max_current(max_current)
                elif key == 'M':
                    max_current = max(1.0, max_current - 1.0)
                    ctrl.set_max_current(max_current)
                elif key == 's':
                    smoothing = min(0.95, smoothing + 0.05)
                    ctrl.smoothing = smoothing
                elif key == 'S':
                    smoothing = max(0.0, smoothing - 0.05)
                    ctrl.smoothing = smoothing
                elif key == 'd':
                    deadband += 1
                    ctrl.deadband_steps = deadband
                elif key == 'D':
                    deadband = max(1, deadband - 1)
                    ctrl.deadband_steps = deadband
                elif key == 'z':
                    ctrl.zero_here()

                now = time.monotonic()
                if now - last_display >= 0.1:
                    d = log_data
                    t = d['telem']
                    i_real = t.get('i_motor', 0)
                    v_in = t.get('v_in', 0)
                    line = (
                        f"\r\033[K"
                        f"ang={d['angle']:+6.1f}° "
                        f"I_cmd={d['cur']:+5.2f}A "
                        f"I_mot={i_real:+5.1f}A "
                        f"V={v_in:.1f}V "
                        f"| sc={scale:.1f} "
                        f"mx={max_current:.0f}A "
                        f"sm={smoothing:.2f} "
                        f"db={deadband} "
                        f"pk={ctrl.peak_i_motor:.1f}A"
                    )
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    last_display = now

        except KeyboardInterrupt:
            pass
        finally:
            ctrl.stop()
            print()
            print("Fine.")


if __name__ == "__main__":
    main()
