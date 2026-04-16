#!/usr/bin/env python3
"""
Asmile Follow-Me — GPIO Button Handler

Button on GPIO 27 with internal pull-up, active LOW.
Detects a 2-second hold for follow-me activation.

Wiring:
  GPIO 27 (Pin 13) ──── button ──── GND (Pin 14)

Events:
  HOLD_START    — button pressed, hold timer started
  HOLD_COMPLETE — button held for acquisition_hold_s (2s) → activate
  RELEASE       — button released before hold completed → cancel
"""

import lgpio
import time
import threading
from enum import Enum, auto


class ButtonEvent(Enum):
    NONE = auto()
    HOLD_START = auto()
    HOLD_COMPLETE = auto()
    RELEASE = auto()


class ButtonHandler:
    """Non-blocking button handler using lgpio polling."""

    def __init__(self, gpio_handle: int, cfg: dict):
        self._h = gpio_handle
        gpio_cfg = cfg["gpio"]
        fm_cfg = cfg["follow_me"]

        self._pin = gpio_cfg["button_pin"]
        self._hold_s = fm_cfg["acquisition_hold_s"]
        self._chip = gpio_cfg["gpio_chip"]

        # Claim pin with pull-up
        lgpio.gpio_claim_input(self._h, self._pin, lgpio.SET_PULL_UP)

        self._pressed = False
        self._press_time = 0.0
        self._hold_completed = False
        self._event = ButtonEvent.NONE
        self._lock = threading.Lock()

        # Polling thread
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _poll_loop(self):
        """Poll button state at 50Hz."""
        debounce_count = 0
        debounce_threshold = 3  # 3 consecutive reads = 60ms debounce

        while self._running:
            level = lgpio.gpio_read(self._h, self._pin)
            button_down = (level == 0)  # active LOW

            with self._lock:
                if button_down and not self._pressed:
                    debounce_count += 1
                    if debounce_count >= debounce_threshold:
                        self._pressed = True
                        self._press_time = time.monotonic()
                        self._hold_completed = False
                        self._event = ButtonEvent.HOLD_START
                        debounce_count = 0

                elif not button_down and self._pressed:
                    debounce_count += 1
                    if debounce_count >= debounce_threshold:
                        self._pressed = False
                        if not self._hold_completed:
                            self._event = ButtonEvent.RELEASE
                        debounce_count = 0

                elif button_down and self._pressed and not self._hold_completed:
                    elapsed = time.monotonic() - self._press_time
                    if elapsed >= self._hold_s:
                        self._hold_completed = True
                        self._event = ButtonEvent.HOLD_COMPLETE
                    debounce_count = 0

                else:
                    debounce_count = 0

            time.sleep(0.02)  # 50Hz

    def poll_event(self) -> ButtonEvent:
        """Return and consume the latest event.

        Call this from the main loop. Returns ButtonEvent.NONE if no new event.
        """
        with self._lock:
            ev = self._event
            self._event = ButtonEvent.NONE
            return ev

    @property
    def is_pressed(self) -> bool:
        with self._lock:
            return self._pressed

    @property
    def hold_progress(self) -> float:
        """Returns 0.0–1.0 indicating how far through the hold we are."""
        with self._lock:
            if not self._pressed:
                return 0.0
            elapsed = time.monotonic() - self._press_time
            return min(1.0, elapsed / self._hold_s)

    def cleanup(self):
        """Stop polling thread."""
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)
