#!/usr/bin/env python3
"""
Asmile Follow-Me — Buzzer Controller

Non-blocking buzzer using lgpio hardware PWM on GPIO 13 (PWM1).
All frequencies and patterns from asmile_config.yaml.

Wiring:
  GPIO 13 (Pin 33) → Buzzer + terminal
  GND     (Pin 34) → Buzzer − terminal

Patterns:
  ready          — 2 short beeps at freq_ready (1kHz)
  window_active  — single beep every 2s at freq_window (800Hz)
  target_acquired — ascending trill 800→1200→1600Hz
  too_close      — rapid beeps at freq_close (2kHz), rate proportional to proximity
  target_lost    — descending tone 1200→400Hz over 1s
  obstacle_lateral — single beep at freq_obstacle (1.5kHz) every 500ms
"""

import lgpio
import time
import threading


class Buzzer:
    """Non-blocking buzzer on lgpio hardware PWM."""

    def __init__(self, gpio_handle: int, cfg: dict):
        self._h = gpio_handle
        gpio_cfg = cfg["gpio"]
        buzzer_cfg = cfg["buzzer"]

        self._pin = gpio_cfg["buzzer_pin"]
        self._freq_ready = buzzer_cfg["freq_ready"]
        self._freq_window = buzzer_cfg["freq_window"]
        self._freq_close = buzzer_cfg["freq_close"]
        self._freq_obstacle = buzzer_cfg["freq_obstacle"]

        self._thread = None
        self._stop_event = threading.Event()

    # ── low-level ──────────────────────────────────────────

    def _tone(self, freq_hz: int, duration_s: float):
        """Play a tone for duration_s seconds. Blocking."""
        if self._stop_event.is_set():
            return
        lgpio.tx_pwm(self._h, self._pin, freq_hz, 50)  # 50% duty
        self._stop_event.wait(duration_s)
        lgpio.tx_pwm(self._h, self._pin, 0, 0)

    def _silence(self, duration_s: float):
        """Silence for duration_s seconds. Blocking."""
        lgpio.tx_pwm(self._h, self._pin, 0, 0)
        self._stop_event.wait(duration_s)

    def _run_pattern(self, func, *args):
        """Run a pattern function in a background thread."""
        self.stop()
        self._stop_event.clear()
        self._thread = threading.Thread(target=func, args=args, daemon=True)
        self._thread.start()

    # ── public API ─────────────────────────────────────────

    def stop(self):
        """Stop any running pattern immediately."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        lgpio.tx_pwm(self._h, self._pin, 0, 0)
        self._thread = None

    def ready(self):
        """2 short beeps at freq_ready — system is ready."""
        def _pattern():
            self._tone(self._freq_ready, 0.1)
            self._silence(0.1)
            self._tone(self._freq_ready, 0.1)
        self._run_pattern(_pattern)

    def window_active(self):
        """Repeating beep every 2s — acquisition window open."""
        def _pattern():
            while not self._stop_event.is_set():
                self._tone(self._freq_window, 0.15)
                self._silence(1.85)
        self._run_pattern(_pattern)

    def target_acquired(self):
        """Ascending trill 800→1200→1600Hz — target locked."""
        def _pattern():
            for freq in [800, 1200, 1600]:
                if self._stop_event.is_set():
                    return
                self._tone(freq, 0.15)
                self._silence(0.05)
        self._run_pattern(_pattern)

    def too_close(self, proximity_factor: float = 1.0):
        """Rapid beeps at freq_close, rate proportional to proximity.

        Args:
            proximity_factor: 0.0 (far) to 1.0 (very close).
                              Controls beep interval: 0.5s at 0.0 → 0.1s at 1.0.
        """
        factor = max(0.0, min(1.0, proximity_factor))
        interval = 0.5 - 0.4 * factor  # 0.5s → 0.1s

        def _pattern():
            while not self._stop_event.is_set():
                self._tone(self._freq_close, 0.05)
                self._silence(interval - 0.05)
        self._run_pattern(_pattern)

    def target_lost(self):
        """Descending tone 1200→400Hz over 1s — target lost."""
        def _pattern():
            steps = 20
            for i in range(steps):
                if self._stop_event.is_set():
                    return
                freq = int(1200 - (800 * i / (steps - 1)))
                self._tone(freq, 1.0 / steps)
        self._run_pattern(_pattern)

    def obstacle_lateral(self):
        """Single beep at freq_obstacle every 500ms — lateral obstacle."""
        def _pattern():
            while not self._stop_event.is_set():
                self._tone(self._freq_obstacle, 0.1)
                self._silence(0.4)
        self._run_pattern(_pattern)

    def cleanup(self):
        """Stop buzzer and release PWM."""
        self.stop()
