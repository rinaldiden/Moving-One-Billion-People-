#!/usr/bin/env python3
"""
Asmile Segmentation Inference — run segmentation on frames or live camera.

Combines segmentation with depth to produce:
  "person at 3.2m left, road ahead clear, wall at 1.5m right"

Usage:
  python3 infer_segmentation.py --model segmentation_model.pth --session ~/wip/recorder/session_20260417_181452/ --output ~/wip/segmentation/inference/
  python3 infer_segmentation.py --model segmentation_model.pth --live
"""

import os
import sys
import argparse
import glob
import numpy as np
import cv2
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_SIZE = (320, 200)  # model input size
NUM_CLASSES = 13


def load_categories():
    with open(os.path.join(SCRIPT_DIR, "categories.yaml")) as f:
        data = yaml.safe_load(f)
    return data["categories"], data.get("drivable", {})


def load_calibration(calib_path):
    """Load stereo calibration for depth computation."""
    fs = cv2.FileStorage(calib_path, cv2.FILE_STORAGE_READ)
    K1 = fs.getNode("camera_matrix_left").mat()
    D1 = fs.getNode("dist_coeffs_left").mat()
    K2 = fs.getNode("camera_matrix_right").mat()
    D2 = fs.getNode("dist_coeffs_right").mat()
    R1 = fs.getNode("R1").mat()
    R2 = fs.getNode("R2").mat()
    P1 = fs.getNode("P1").mat()
    P2 = fs.getNode("P2").mat()
    T = fs.getNode("T").mat()
    fs.release()

    focal = P1[0, 0]
    baseline = abs(T[0, 0])

    w, h = 1280, 800
    map1l, map2l = cv2.initUndistortRectifyMap(K1, D1, R1, P1, (w, h), cv2.CV_32FC1)
    map1r, map2r = cv2.initUndistortRectifyMap(K2, D2, R2, P2, (w, h), cv2.CV_32FC1)

    return {
        "focal": focal, "baseline": baseline,
        "map1l": map1l, "map2l": map2l,
        "map1r": map1r, "map2r": map2r,
    }


def compute_depth(left, right, calib, block_size=7, num_disp=192, uniq_ratio=15):
    """Compute depth map in mm from stereo pair."""
    rl = cv2.remap(left, calib["map1l"], calib["map2l"], cv2.INTER_LINEAR)
    rr = cv2.remap(right, calib["map1r"], calib["map2r"], cv2.INTER_LINEAR)

    stereo = cv2.StereoSGBM_create(
        minDisparity=0, numDisparities=num_disp, blockSize=block_size,
        P1=8 * block_size * block_size, P2=32 * block_size * block_size,
        disp12MaxDiff=1, uniquenessRatio=uniq_ratio,
        speckleWindowSize=50, speckleRange=32)

    disp = stereo.compute(rl, rr).astype(np.float32) / 16.0
    depth = np.zeros_like(disp)
    mask = disp > 0
    depth[mask] = (calib["focal"] * calib["baseline"]) / disp[mask]
    return depth


def load_model(model_path):
    """Load PyTorch segmentation model."""
    import torch
    import torch.nn as nn

    class SegNet(nn.Module):
        def __init__(self, n_classes):
            super().__init__()
            self.enc1 = nn.Sequential(
                nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
                nn.Conv2d(32, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
                nn.MaxPool2d(2))
            self.enc2 = nn.Sequential(
                nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
                nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
                nn.MaxPool2d(2))
            self.enc3 = nn.Sequential(
                nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
                nn.Conv2d(128, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
                nn.MaxPool2d(2))
            self.dec3 = nn.Sequential(
                nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False),
                nn.Conv2d(128, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU())
            self.dec2 = nn.Sequential(
                nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False),
                nn.Conv2d(64, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU())
            self.dec1 = nn.Sequential(
                nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False),
                nn.Conv2d(32, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU())
            self.final = nn.Conv2d(32, n_classes, 1)

        def forward(self, x):
            e1 = self.enc1(x)
            e2 = self.enc2(e1)
            e3 = self.enc3(e2)
            d3 = self.dec3(e3)
            d2 = self.dec2(d3)
            d1 = self.dec1(d2)
            return self.final(d1)

    model = SegNet(NUM_CLASSES)
    model.load_state_dict(torch.load(model_path, weights_only=True, map_location="cpu"))
    model.eval()
    return model


def segment_frame(model, gray, device="cpu"):
    """Run segmentation on a single grayscale frame."""
    import torch

    h, w = gray.shape
    resized = cv2.resize(gray, IMG_SIZE, interpolation=cv2.INTER_AREA)
    tensor = torch.FloatTensor(resized / 255.0).unsqueeze(0).unsqueeze(0).to(device)

    with torch.no_grad():
        pred = model(tensor).argmax(1).squeeze().cpu().numpy()

    # Resize back to original
    mask = cv2.resize(pred.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
    return mask


def describe_scene(mask, depth, categories, drivable):
    """Generate text description of the scene."""
    h, w = mask.shape
    descriptions = []

    # Divide frame into left, center, right thirds
    zones = {"left": (0, w // 3), "center": (w // 3, 2 * w // 3), "right": (2 * w // 3, w)}

    for zone_name, (x1, x2) in zones.items():
        zone_mask = mask[:, x1:x2]
        zone_depth = depth[:, x1:x2]

        for cat in categories:
            cid = cat["id"]
            if cid == 0:
                continue
            cat_pixels = zone_mask == cid
            if cat_pixels.sum() < 100:  # too few pixels
                continue

            cat_depth = zone_depth[cat_pixels]
            valid = cat_depth[(cat_depth > 0) & (cat_depth < 15000)]
            if len(valid) > 0:
                dist_m = np.median(valid) / 1000.0
                descriptions.append(f"{cat['name']} at {dist_m:.1f}m {zone_name}")

    # Drivable area check
    stop_ids = set(drivable.get("stop", []))
    for zone_name, (x1, x2) in zones.items():
        zone_mask = mask[:, x1:x2]
        zone_depth = depth[:, x1:x2]
        for sid in stop_ids:
            cat_pixels = zone_mask == sid
            if cat_pixels.sum() < 50:
                continue
            cat_depth = zone_depth[cat_pixels]
            valid = cat_depth[(cat_depth > 0) & (cat_depth < 5000)]
            if len(valid) > 0 and np.median(valid) < 3000:
                cat_name = next((c["name"] for c in categories if c["id"] == sid), "?")
                descriptions.append(f"WARNING: {cat_name} at {np.median(valid)/1000:.1f}m {zone_name}")

    # Road ahead
    center_bottom = mask[h * 2 // 3:, w // 3:2 * w // 3]
    road_pct = (center_bottom == 1).sum() / max(center_bottom.size, 1) * 100
    descriptions.append(f"Road ahead: {road_pct:.0f}%")

    return descriptions


def colorize_mask(mask, categories):
    """Convert category mask to colored image."""
    h, w = mask.shape
    colored = np.zeros((h, w, 3), dtype=np.uint8)
    for cat in categories:
        colored[mask == cat["id"]] = cat["color"]
    return colored


def process_session(model, session_dir, output_dir, calib, categories, drivable, max_frames=0):
    """Process a recorded session."""
    import torch
    device = "cpu"

    video_path = os.path.join(session_dir, "video.h264")
    if not os.path.exists(video_path):
        print(f"No video found in {session_dir}")
        return

    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    frame_idx = 0
    results = []

    print(f"Processing {session_dir}...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if max_frames and frame_idx >= max_frames:
            break

        h, w = frame.shape[:2]
        mid = w // 2
        left = cv2.cvtColor(frame[:, :mid], cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame[:, :mid]
        right = cv2.cvtColor(frame[:, mid:], cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame[:, mid:]

        # Segmentation
        mask = segment_frame(model, left, device)

        # Depth
        depth = compute_depth(left, right, calib)

        # Description
        desc = describe_scene(mask, depth, categories, drivable)

        # Save
        colored = colorize_mask(mask, categories)
        overlay = cv2.addWeighted(
            cv2.cvtColor(left, cv2.COLOR_GRAY2BGR), 0.6,
            colored, 0.4, 0)

        # Add text
        for i, d in enumerate(desc[:5]):
            cv2.putText(overlay, d, (10, 20 + i * 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        cv2.imwrite(os.path.join(output_dir, f"seg_{frame_idx:05d}.png"), overlay)
        results.append({"frame": frame_idx, "description": desc})

        if frame_idx % 50 == 0:
            print(f"  Frame {frame_idx}: {'; '.join(desc[:3])}")

        frame_idx += 1

    cap.release()
    print(f"Processed {frame_idx} frames → {output_dir}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Asmile Segmentation Inference")
    parser.add_argument("--model", required=True, help="Path to trained model (.pth)")
    parser.add_argument("--session", help="Session directory to process")
    parser.add_argument("--output", default="./seg_output", help="Output directory")
    parser.add_argument("--calib", default=None, help="Stereo calibration YAML")
    parser.add_argument("--max-frames", type=int, default=0, help="Max frames to process (0=all)")
    parser.add_argument("--live", action="store_true", help="Real-time inference from camera")
    args = parser.parse_args()

    categories, drivable = load_categories()

    # Find calibration
    calib_path = args.calib
    if not calib_path:
        calib_path = os.path.join(SCRIPT_DIR, "../../config/stereo_calibration.yaml")
    calib = load_calibration(calib_path)

    model = load_model(args.model)

    if args.session:
        process_session(model, args.session, args.output, calib, categories, drivable, args.max_frames)
    elif args.live:
        print("Live inference — press Ctrl+C to stop")
        # TODO: picamera2 live capture
        print("Not implemented yet — use --session for now")
    else:
        print("Specify --session or --live")


if __name__ == "__main__":
    main()
