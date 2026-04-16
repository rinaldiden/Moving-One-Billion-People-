#!/usr/bin/env python3
"""
Asmile Follow-Me — Configuration Loader

Loads asmile_config.yaml and stereo calibration YAML.
Returns a unified config dict with all parameters.
"""

import os
import yaml
import cv2
import numpy as np


def _resolve_path(base_dir: str, rel_path: str) -> str:
    """Resolve a relative path against the config file directory."""
    return os.path.normpath(os.path.join(base_dir, rel_path))


def load_stereo_calibration(calib_path: str) -> dict:
    """Load stereo calibration from OpenCV YAML (FileStorage format).

    Returns dict with keys: camera_matrix_left, dist_coeffs_left,
    camera_matrix_right, dist_coeffs_right, R, T, R1, R2, P1, P2, Q.
    """
    fs = cv2.FileStorage(calib_path, cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        raise FileNotFoundError(f"Cannot open stereo calibration: {calib_path}")

    keys = [
        "camera_matrix_left", "dist_coeffs_left",
        "camera_matrix_right", "dist_coeffs_right",
        "R", "T", "R1", "R2", "P1", "P2", "Q",
    ]
    calib = {}
    for key in keys:
        node = fs.getNode(key)
        if node.empty():
            raise KeyError(f"Missing key '{key}' in {calib_path}")
        calib[key] = node.mat()

    # Extract scalar metadata
    for scalar_key in ["image_width", "image_height"]:
        node = fs.getNode(scalar_key)
        if not node.empty():
            calib[scalar_key] = int(node.real())

    fs.release()
    return calib


def load_config(config_path: str = None) -> dict:
    """Load asmile_config.yaml and resolve stereo calibration.

    Args:
        config_path: Path to asmile_config.yaml.
                     Defaults to asmile_config.yaml in the same directory as this file.

    Returns:
        dict with keys: asmile, stereo, gpio, follow_me, stereo_matching,
        cone_detector, safety, buzzer, stereo_calibration.
    """
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "asmile_config.yaml",
        )

    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    # Resolve stereo calibration path relative to config file
    base_dir = os.path.dirname(os.path.abspath(config_path))
    calib_rel = cfg["stereo"]["calibration_file"]
    calib_path = _resolve_path(base_dir, calib_rel)

    cfg["stereo_calibration"] = load_stereo_calibration(calib_path)

    return cfg


if __name__ == "__main__":
    cfg = load_config()
    print("Config loaded successfully.")
    print(f"  Stereo calib keys: {list(cfg['stereo_calibration'].keys())}")
    print(f"  Follow-me range: {cfg['follow_me']['range_min_m']}–{cfg['follow_me']['range_max_m']} m")
    print(f"  GPIO buzzer={cfg['gpio']['buzzer_pin']}, button={cfg['gpio']['button_pin']}")
