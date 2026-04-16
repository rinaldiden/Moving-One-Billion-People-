#!/usr/bin/env python3
"""
Asmile Follow-Me — Control Logic

Translates target distance and lateral offset into brake and steering commands.

Distance zones (from config):
  d < range_min_m (3m) : proportional brake + buzzer rapid beeps
  range_ok_min_m ≤ d ≤ range_ok_max_m (3-8m) : OK zone, steer only
  d > range_ok_max_m (8m) : buzzer alert, still following
  d > range_max_m (10m) : target lost → idle

Steering:
  Proportional to horizontal pixel offset (dx) from frame center,
  with a deadband to avoid jitter.

All thresholds from asmile_config.yaml.
"""

import numpy as np


class ControlCommand:
    """Output of the control logic for one frame."""

    __slots__ = (
        "brake_pct", "steer_pct", "buzzer_action",
        "target_distance_m", "target_dx_pct", "zone",
    )

    def __init__(self):
        self.brake_pct = 0.0       # 0 = no brake, 100 = full brake
        self.steer_pct = 0.0       # -100 = full left, +100 = full right
        self.buzzer_action = None   # str or None
        self.target_distance_m = 0.0
        self.target_dx_pct = 0.0   # % offset from center
        self.zone = "idle"         # idle, too_close, ok, far, lost

    def __repr__(self):
        return (f"Cmd(zone={self.zone}, brake={self.brake_pct:.0f}%, "
                f"steer={self.steer_pct:.1f}%, d={self.target_distance_m:.1f}m)")


class FollowController:
    """Follow-me control logic: distance → brake/steer commands."""

    def __init__(self, cfg: dict):
        fm = cfg["follow_me"]
        self._range_min = fm["range_min_m"]
        self._range_max = fm["range_max_m"]
        self._ok_min = fm["range_ok_min_m"]
        self._ok_max = fm["range_ok_max_m"]
        self._deadband = fm["deadband_pct"]

        stereo = cfg["stereo"]
        self._frame_half_w = stereo["frame_width"] // 4  # half of one camera

    def compute(self, target_distance_m: float, target_cx: int,
                frame_width: int) -> ControlCommand:
        """Compute brake/steer from target distance and horizontal position.

        Args:
            target_distance_m: Target distance in meters.
            target_cx: Target centroid x-coordinate in pixels (in rectified frame).
            frame_width: Width of the rectified frame (single camera).

        Returns:
            ControlCommand with brake_pct, steer_pct, buzzer_action, zone.
        """
        cmd = ControlCommand()
        cmd.target_distance_m = target_distance_m

        # Lateral offset as percentage of half-frame
        frame_center = frame_width / 2.0
        dx = target_cx - frame_center
        dx_pct = (dx / frame_center) * 100.0 if frame_center > 0 else 0.0
        cmd.target_dx_pct = dx_pct

        # ── Distance zones ──

        if target_distance_m <= 0:
            cmd.zone = "lost"
            cmd.buzzer_action = "target_lost"
            return cmd

        if target_distance_m > self._range_max:
            cmd.zone = "lost"
            cmd.buzzer_action = "target_lost"
            return cmd

        if target_distance_m > self._ok_max:
            # Far zone: still following, alert buzzer
            cmd.zone = "far"
            cmd.buzzer_action = "window_active"
            cmd.steer_pct = self._compute_steer(dx_pct)
            return cmd

        if target_distance_m >= self._ok_min:
            # OK zone: steer only
            cmd.zone = "ok"
            cmd.steer_pct = self._compute_steer(dx_pct)
            return cmd

        # Too close: proportional braking
        cmd.zone = "too_close"
        # Brake intensity: 0% at ok_min, 100% at 0m
        brake_range = self._ok_min
        if brake_range > 0:
            cmd.brake_pct = max(0.0, min(100.0,
                (1.0 - target_distance_m / brake_range) * 100.0))
        else:
            cmd.brake_pct = 100.0

        # Proximity factor for buzzer (1.0 = very close, 0.0 = at ok_min)
        proximity = 1.0 - target_distance_m / brake_range if brake_range > 0 else 1.0
        cmd.buzzer_action = f"too_close:{proximity:.2f}"

        # Still steer even when braking
        cmd.steer_pct = self._compute_steer(dx_pct)

        return cmd

    def _compute_steer(self, dx_pct: float) -> float:
        """Proportional steering with deadband.

        Args:
            dx_pct: Lateral offset as percentage (-100 to +100).

        Returns:
            Steering command as percentage (-100 to +100).
        """
        if abs(dx_pct) < self._deadband:
            return 0.0

        # Remove deadband and scale
        sign = 1.0 if dx_pct > 0 else -1.0
        magnitude = abs(dx_pct) - self._deadband
        scale = 100.0 / (100.0 - self._deadband)
        steer = sign * magnitude * scale

        return max(-100.0, min(100.0, steer))
