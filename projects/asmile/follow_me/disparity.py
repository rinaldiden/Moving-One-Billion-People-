#!/usr/bin/env python3
"""
Asmile Follow-Me — Stereo Disparity and Depth

Loads stereo calibration, computes rectification maps once at init,
then runs StereoSGBM on each frame pair. Returns depth in mm.

depth_mm = focal_px * baseline_mm / disparity_px

Uses OpenCV for stereo rectification and disparity computation only.
All parameters from asmile_config.yaml.
"""

import cv2
import numpy as np


class DisparityEngine:
    """Stereo disparity computation with pre-computed rectification maps."""

    def __init__(self, cfg: dict):
        calib = cfg["stereo_calibration"]
        stereo_cfg = cfg["stereo"]
        match_cfg = cfg["stereo_matching"]

        # Camera matrices and distortion
        self._cam_left = calib["camera_matrix_left"]
        self._dist_left = calib["dist_coeffs_left"]
        self._cam_right = calib["camera_matrix_right"]
        self._dist_right = calib["dist_coeffs_right"]

        # Rectification transforms
        self._R1 = calib["R1"]
        self._R2 = calib["R2"]
        self._P1 = calib["P1"]
        self._P2 = calib["P2"]
        self._Q = calib["Q"]

        # Baseline from translation vector T (in mm, as calibrated)
        T = calib["T"]
        self._baseline_mm = float(np.linalg.norm(T))

        # Focal length from P1 (rectified projection matrix)
        self._focal_px = float(self._P1[0, 0])

        # Frame dimensions
        self._width = stereo_cfg["frame_width"]
        self._height = stereo_cfg["frame_height"]

        # The calibration was done at image_width from the YAML;
        # if frame_width differs, we scale rectification maps
        calib_w = calib.get("image_width", self._width // 2)
        calib_h = calib.get("image_height", self._height)
        self._calib_size = (calib_w, calib_h)

        # Each camera produces half the side-by-side frame
        self._cam_size = (self._width // 2, self._height)

        # Pre-compute rectification maps
        self._map1_left, self._map2_left = cv2.initUndistortRectifyMap(
            self._cam_left, self._dist_left, self._R1, self._P1,
            self._calib_size, cv2.CV_16SC2,
        )
        self._map1_right, self._map2_right = cv2.initUndistortRectifyMap(
            self._cam_right, self._dist_right, self._R2, self._P2,
            self._calib_size, cv2.CV_16SC2,
        )

        # StereoSGBM matcher
        num_disp = match_cfg["num_disparities"]
        block = match_cfg["block_size"]
        self._matcher = cv2.StereoSGBM.create(
            minDisparity=0,
            numDisparities=num_disp,
            blockSize=block,
            P1=8 * block * block,
            P2=32 * block * block,
            disp12MaxDiff=1,
            uniquenessRatio=match_cfg["uniqueness_ratio"],
            speckleWindowSize=100,
            speckleRange=2,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
        )

    @property
    def focal_px(self) -> float:
        return self._focal_px

    @property
    def baseline_mm(self) -> float:
        return self._baseline_mm

    def split_and_rectify(self, frame: np.ndarray):
        """Split a side-by-side stereo frame and rectify both halves.

        Args:
            frame: Grayscale or BGR frame of shape (H, W) or (H, W, 3)
                   where W = 2 * camera_width (side-by-side).

        Returns:
            (left_rect, right_rect): Rectified grayscale images.
        """
        h = frame.shape[0]
        half_w = frame.shape[1] // 2

        left = frame[:, :half_w]
        right = frame[:, half_w:]

        # Convert to grayscale if needed
        if len(left.shape) == 3:
            left = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
            right = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)

        left_rect = cv2.remap(left, self._map1_left, self._map2_left,
                              cv2.INTER_LINEAR)
        right_rect = cv2.remap(right, self._map1_right, self._map2_right,
                               cv2.INTER_LINEAR)
        return left_rect, right_rect

    def compute_disparity(self, left_rect: np.ndarray,
                          right_rect: np.ndarray) -> np.ndarray:
        """Compute disparity map from rectified image pair.

        Returns:
            Disparity in pixels as float32 (invalid pixels = 0).
        """
        disp_raw = self._matcher.compute(left_rect, right_rect)
        # StereoSGBM returns disparity * 16 as int16
        disp = disp_raw.astype(np.float32) / 16.0
        disp[disp <= 0] = 0
        return disp

    def disparity_to_depth_mm(self, disparity: np.ndarray) -> np.ndarray:
        """Convert disparity map to depth in mm.

        depth_mm = focal_px * baseline_mm / disparity_px

        Returns:
            Depth map in mm as float32. Invalid pixels = 0.
        """
        depth = np.zeros_like(disparity, dtype=np.float32)
        valid = disparity > 0
        depth[valid] = (self._focal_px * self._baseline_mm) / disparity[valid]
        return depth

    def process_frame(self, frame: np.ndarray):
        """Full pipeline: split → rectify → disparity → depth.

        Args:
            frame: Side-by-side stereo frame.

        Returns:
            (left_rect, depth_mm): Rectified left image and depth map in mm.
        """
        left_rect, right_rect = self.split_and_rectify(frame)
        disp = self.compute_disparity(left_rect, right_rect)
        depth_mm = self.disparity_to_depth_mm(disp)
        return left_rect, depth_mm
