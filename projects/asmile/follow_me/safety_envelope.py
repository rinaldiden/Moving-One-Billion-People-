#!/usr/bin/env python3
"""
Asmile Follow-Me — Safety Envelope

Projects Asmile physical dimensions onto the depth map to detect obstacles
in the tricycle's path. The tracked cone target is EXCLUDED from obstacle checks.

Zones (from config):
  d_stop  — hard brake for non-target obstacles
  d_brake — proportional braking
  d_steer — steer to avoid

The safety corridor is the width of the tricycle (larghezza_max_cm)
centered on the camera, plus a margin. Depth is checked in the forward
direction only.
"""

import numpy as np


class SafetyEnvelope:
    """Obstacle detection in the tricycle's forward path using depth map."""

    def __init__(self, cfg: dict):
        asmile_cfg = cfg["asmile"]
        safety_cfg = cfg["safety"]
        stereo_cfg = cfg["stereo"]

        self._width_cm = asmile_cfg["larghezza_max_cm"]
        self._nose_cm = asmile_cfg["sporgenza_muso_cm"]
        self._cam_height_cm = asmile_cfg["altezza_cam_da_terra_cm"]

        self._d_stop_m = safety_cfg["d_stop_m"]
        self._d_brake_m = safety_cfg["d_brake_m"]
        self._d_steer_m = safety_cfg["d_steer_m"]

        self._frame_w = stereo_cfg["frame_width"] // 2  # single camera width
        self._frame_h = stereo_cfg["frame_height"]

        # Focal length from calibration (set after config_loader runs)
        calib = cfg["stereo_calibration"]
        self._focal_px = float(calib["P1"][0, 0])

    def check(self, depth_mm: np.ndarray, target_bbox=None) -> dict:
        """Check for obstacles in the safety corridor.

        Args:
            depth_mm: Depth map in mm, shape (H, W).
            target_bbox: (x, y, w, h) of the tracked target to exclude,
                         or None if no target is being tracked.

        Returns:
            dict with keys:
              obstacle_stop: bool — hard brake needed
              obstacle_brake: bool — proportional brake needed
              obstacle_brake_factor: float 0–1 — braking intensity
              obstacle_steer: bool — lateral obstacle, steer to avoid
              obstacle_steer_side: "left" | "right" | None
              min_obstacle_m: float — nearest obstacle distance in meters
        """
        h, w = depth_mm.shape[:2]

        # Build corridor mask: central strip as wide as the tricycle
        half_width_mm = self._width_cm * 10.0 / 2.0  # cm → mm
        corridor_mask = np.ones((h, w), dtype=bool)

        # For each row, determine which columns are within the corridor
        # at each depth. Approximate: use a fixed corridor based on
        # the median depth of valid pixels, or just use the frame center.
        cx = w // 2
        # At 3m, how many pixels is half the tricycle width?
        # px = focal * (half_width_mm) / depth_mm
        # Use a conservative estimate at d_stop distance
        ref_depth = self._d_stop_m * 1000.0  # mm
        half_px = int(self._focal_px * half_width_mm / ref_depth) if ref_depth > 0 else w // 2
        half_px = max(half_px, w // 6)  # at least some corridor

        corridor_mask[:, :max(0, cx - half_px)] = False
        corridor_mask[:, min(w, cx + half_px):] = False

        # Exclude target bbox from obstacle detection
        if target_bbox is not None:
            tx, ty, tw, th = target_bbox
            # Add margin around target
            margin = max(tw, th) // 4
            tx0 = max(0, tx - margin)
            ty0 = max(0, ty - margin)
            tx1 = min(w, tx + tw + margin)
            ty1 = min(h, ty + th + margin)
            corridor_mask[ty0:ty1, tx0:tx1] = False

        # Valid depth pixels in corridor
        valid = corridor_mask & (depth_mm > 0)
        depths_m = depth_mm[valid] / 1000.0  # mm → m

        result = {
            "obstacle_stop": False,
            "obstacle_brake": False,
            "obstacle_brake_factor": 0.0,
            "obstacle_steer": False,
            "obstacle_steer_side": None,
            "min_obstacle_m": float("inf"),
        }

        if len(depths_m) == 0:
            return result

        # Account for nose overhang: obstacles are closer than depth suggests
        depths_m_adj = depths_m - self._nose_cm / 100.0

        # Minimum obstacle distance (use percentile to ignore noise)
        if len(depths_m_adj) > 10:
            min_d = float(np.percentile(depths_m_adj, 2))
        else:
            min_d = float(np.min(depths_m_adj))

        result["min_obstacle_m"] = max(0.0, min_d)

        # Zone checks
        if min_d <= self._d_stop_m:
            result["obstacle_stop"] = True
            result["obstacle_brake_factor"] = 1.0
        elif min_d <= self._d_brake_m:
            result["obstacle_brake"] = True
            # Linear interpolation: 1.0 at d_stop, 0.0 at d_brake
            span = self._d_brake_m - self._d_stop_m
            result["obstacle_brake_factor"] = max(0.0, 1.0 - (min_d - self._d_stop_m) / span)

        # Lateral obstacle check (steer zone)
        if min_d <= self._d_steer_m and not result["obstacle_stop"]:
            # Find which side the obstacle is on
            obstacle_pixels = np.where(valid & (depth_mm / 1000.0 <= self._d_steer_m))
            if len(obstacle_pixels[1]) > 0:
                mean_col = np.mean(obstacle_pixels[1])
                if mean_col < cx:
                    result["obstacle_steer"] = True
                    result["obstacle_steer_side"] = "left"
                elif mean_col > cx:
                    result["obstacle_steer"] = True
                    result["obstacle_steer_side"] = "right"

        return result
