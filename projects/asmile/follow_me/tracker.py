#!/usr/bin/env python3
"""
Asmile Follow-Me — Centroid Tracker

Simple single-target tracker using NumPy:
- Matches the acquired target frame-by-frame via IoU and centroid distance
- Returns current target position or None if lost
- No external dependencies beyond NumPy
"""

import numpy as np


def _iou(box_a, box_b) -> float:
    """Compute Intersection over Union between two bboxes (x, y, w, h)."""
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b

    # Convert to (x1, y1, x2, y2)
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh

    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = aw * ah
    area_b = bw * bh
    union_area = area_a + area_b - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def _centroid_dist(det_a, det_b) -> float:
    """Euclidean distance between two centroids."""
    ax, ay = det_a["centroid"]
    bx, by = det_b["centroid"]
    return float(np.sqrt((ax - bx) ** 2 + (ay - by) ** 2))


class Tracker:
    """Single-target centroid tracker for the follow-me cone.

    Once a target is acquired, it is matched frame-by-frame against
    incoming detections using IoU overlap and centroid proximity.
    """

    def __init__(self, cfg: dict):
        fm_cfg = cfg["follow_me"]
        self._lost_threshold = fm_cfg["lost_frame_threshold"]

        # Match thresholds (adaptive based on target size)
        self._min_iou = 0.15
        self._max_centroid_px = 150  # max pixels between frames

        self._target = None       # last matched detection dict
        self._frames_lost = 0     # consecutive frames without match

    @property
    def is_tracking(self) -> bool:
        return self._target is not None

    @property
    def target(self) -> dict:
        """Current target detection dict, or None."""
        return self._target

    @property
    def frames_lost(self) -> int:
        return self._frames_lost

    def acquire(self, detection: dict):
        """Set the initial target from an acquisition detection.

        Args:
            detection: dict with bbox, centroid, confidence.
        """
        self._target = detection.copy()
        self._frames_lost = 0

    def update(self, detections: list) -> dict:
        """Match the tracked target against new detections.

        Args:
            detections: List of detection dicts from ConeDetector.

        Returns:
            Matched detection dict, or None if target is lost.
        """
        if self._target is None:
            return None

        if not detections:
            self._frames_lost += 1
            if self._frames_lost >= self._lost_threshold:
                self._target = None
            return self._target

        # Score each detection: weighted combination of IoU and centroid distance
        best_score = -1.0
        best_det = None

        for det in detections:
            iou = _iou(self._target["bbox"], det["bbox"])
            dist = _centroid_dist(self._target, det)

            # Normalize distance: 0 at 0px, 1 at max_centroid_px
            dist_norm = max(0.0, 1.0 - dist / self._max_centroid_px)

            # Combined score: IoU + distance + confidence
            score = 0.4 * iou + 0.4 * dist_norm + 0.2 * det["confidence"]

            if score > best_score:
                best_score = score
                best_det = det

        # Accept match if score is reasonable
        if best_score > 0.3 and best_det is not None:
            self._target = best_det.copy()
            self._frames_lost = 0
        else:
            self._frames_lost += 1
            if self._frames_lost >= self._lost_threshold:
                self._target = None

        return self._target

    def reset(self):
        """Clear the tracked target."""
        self._target = None
        self._frames_lost = 0
