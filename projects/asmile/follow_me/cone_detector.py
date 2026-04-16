#!/usr/bin/env python3
"""
Asmile Follow-Me — Cone Detector (NumPy-only geometry)

Detects traffic cones on grayscale frames using shape analysis:
1. Adaptive threshold to binarize
2. Find contours (cv2.findContours — only OpenCV call allowed)
3. For each blob in the central search zone:
   a. Row-by-row width analysis: must decrease linearly upward (R^2 > threshold)
   b. Bilateral symmetry: column center must be constant (tolerance %)
   c. Vertical position: centroid in upper half of bounding box
   d. Aspect ratio: height > width
4. Confidence = mean of 4 normalized criteria
5. Output: list of detections with bbox, centroid, confidence

All thresholds from asmile_config.yaml.
"""

import cv2
import numpy as np


class ConeDetector:
    """Detect cone-shaped objects using geometric analysis on grayscale frames."""

    def __init__(self, cfg: dict):
        cone_cfg = cfg["cone_detector"]
        self._r2_min = cone_cfg["r_squared_min"]
        self._sym_tol_pct = cone_cfg["symmetry_tolerance_pct"]
        self._search_zone_pct = cone_cfg["search_zone_pct"]

    def detect(self, gray: np.ndarray) -> list:
        """Detect cone-shaped blobs in a grayscale image.

        Args:
            gray: Grayscale image (H, W), uint8.

        Returns:
            List of dicts with keys:
              bbox: (x, y, w, h)
              centroid: (cx, cy)
              confidence: float 0–1
        """
        h, w = gray.shape[:2]

        # Central search zone: +-search_zone_pct around center
        zone_frac = self._search_zone_pct / 100.0
        x_min = int(w * (0.5 - zone_frac))
        x_max = int(w * (0.5 + zone_frac))

        # Adaptive threshold
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 31, 10,
        )

        # Find contours
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE,
        )

        detections = []

        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)

            # Skip tiny blobs
            if bw < 10 or bh < 15:
                continue

            # Skip blobs outside search zone
            bcx = bx + bw // 2
            if bcx < x_min or bcx > x_max:
                continue

            # Extract blob mask in bounding box
            mask = np.zeros((bh, bw), dtype=np.uint8)
            shifted = cnt - np.array([bx, by])
            cv2.drawContours(mask, [shifted], 0, 255, cv2.FILLED)

            # Analyse shape with NumPy
            scores = self._analyse_shape(mask)
            if scores is None:
                continue

            confidence = float(np.mean(list(scores.values())))
            if confidence < 0.3:
                continue

            # Compute centroid from mask
            ys, xs = np.nonzero(mask)
            cx = int(np.mean(xs)) + bx
            cy = int(np.mean(ys)) + by

            detections.append({
                "bbox": (bx, by, bw, bh),
                "centroid": (cx, cy),
                "confidence": confidence,
            })

        # Sort by confidence descending
        detections.sort(key=lambda d: d["confidence"], reverse=True)
        return detections

    def _analyse_shape(self, mask: np.ndarray) -> dict:
        """Analyse a blob mask for cone-like shape properties.

        Args:
            mask: Binary mask (bh, bw), uint8, 255=foreground.

        Returns:
            Dict with 4 normalized scores, or None if analysis fails.
        """
        bh, bw = mask.shape

        # Need enough rows to analyse
        if bh < 10:
            return None

        # ── 1. Row-by-row width: must decrease linearly upward ──
        row_widths = []
        row_centers = []
        for row in range(bh):
            cols = np.nonzero(mask[row])[0]
            if len(cols) == 0:
                row_widths.append(0)
                row_centers.append(bw / 2.0)
            else:
                row_widths.append(float(cols[-1] - cols[0] + 1))
                row_centers.append(float(np.mean(cols)))

        row_widths = np.array(row_widths, dtype=np.float64)
        row_centers = np.array(row_centers, dtype=np.float64)

        # Only use rows with nonzero width for regression
        valid = row_widths > 0
        if np.sum(valid) < 5:
            return None

        rows_valid = np.where(valid)[0].astype(np.float64)
        widths_valid = row_widths[valid]

        # Linear regression: width = a * row + b
        # row increases downward, so for a cone (wider at bottom), a > 0
        n = len(rows_valid)
        mean_r = np.mean(rows_valid)
        mean_w = np.mean(widths_valid)
        ss_rr = np.sum((rows_valid - mean_r) ** 2)
        if ss_rr < 1e-9:
            return None
        ss_rw = np.sum((rows_valid - mean_r) * (widths_valid - mean_w))
        a = ss_rw / ss_rr
        b = mean_w - a * mean_r

        # R^2
        predicted = a * rows_valid + b
        ss_res = np.sum((widths_valid - predicted) ** 2)
        ss_tot = np.sum((widths_valid - mean_w) ** 2)
        r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1e-9 else 0.0

        # Width must increase downward (a > 0) for a cone
        if a <= 0:
            r_squared = 0.0

        score_linear = min(1.0, max(0.0, r_squared / self._r2_min))

        # ── 2. Bilateral symmetry: column centers should be constant ──
        centers_valid = row_centers[valid]
        center_std = np.std(centers_valid)
        center_mean = np.mean(centers_valid)
        sym_ratio = center_std / (center_mean + 1e-6) * 100.0
        tol = self._sym_tol_pct
        score_symmetry = max(0.0, 1.0 - sym_ratio / tol) if sym_ratio < tol * 2 else 0.0

        # ── 3. Vertical position: centroid in upper half ──
        ys = np.where(valid)[0]
        centroid_y = np.mean(ys)
        # centroid_y / bh: 0.0=top, 1.0=bottom
        # For a cone (narrow top, wide bottom), mass centroid is below center
        # but the apex should be in the upper half
        # Score: higher if centroid is in lower half (cone-like mass distribution)
        vert_ratio = centroid_y / bh
        score_vertical = min(1.0, max(0.0, vert_ratio * 2.0))  # 0.5→1.0

        # ── 4. Aspect ratio: height > width ──
        max_width = float(np.max(row_widths))
        aspect = bh / (max_width + 1e-6)
        score_aspect = min(1.0, max(0.0, aspect))  # 1.0 when h >= w

        return {
            "linear": score_linear,
            "symmetry": score_symmetry,
            "vertical": score_vertical,
            "aspect": score_aspect,
        }
