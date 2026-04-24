#!/usr/bin/env python3
"""
Asmile Buzzer — KY-006 passive piezo on GPIO 5 (via Level Shifter #2 ch4)

Sound patterns for different events.
"""

import lgpio
import time

GPIO_CHIP = 4
BUZZER_PIN = 5


def _beep(h, freq, duration):
    lgpio.tx_pwm(h, BUZZER_PIN, freq, 50)
    time.sleep(duration)
    lgpio.tx_pwm(h, BUZZER_PIN, 0, 0)


def boot(h):
    """System ready — two quick high beeps"""
    _beep(h, 2000, 0.1)
    time.sleep(0.05)
    _beep(h, 2000, 0.1)


def follow_me_searching(h):
    """Follow-me searching for target — rapid beeps (call in loop, non-blocking)"""
    _beep(h, 2000, 0.08)
    time.sleep(0.12)


def follow_me_locked(h):
    """Follow-me target acquired — pause + long beep"""
    time.sleep(0.3)
    _beep(h, 2000, 0.4)


def follow_me_off(h):
    """Follow-me stopped (voluntary or target lost) — descending two-tone"""
    _beep(h, 2000, 0.1)
    time.sleep(0.05)
    _beep(h, 1000, 0.15)


def shutdown(h):
    """Shutting down — beeps that slow down and die"""
    freq = 400
    on_time = 0.08
    off_time = 0.08
    while freq > 80:
        _beep(h, freq, on_time)
        time.sleep(off_time)
        freq -= 30
        on_time += 0.02
        off_time += 0.04


# --- Test all patterns ---
if __name__ == "__main__":
    h = lgpio.gpiochip_open(GPIO_CHIP)
    patterns = [
        ("boot", boot),
        ("follow_me_searching x5", lambda h: [follow_me_searching(h) for _ in range(5)]),
        ("follow_me_locked", follow_me_locked),
        ("follow_me_off", follow_me_off),
        ("shutdown", shutdown),
    ]
    for name, fn in patterns:
        print(f"  {name}")
        fn(h)
        time.sleep(0.5)
    print("done")
    lgpio.gpiochip_close(h)
