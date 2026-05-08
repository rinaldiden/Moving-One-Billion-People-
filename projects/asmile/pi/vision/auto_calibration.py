#!/usr/bin/env python3
"""
Asmile Auto Stereo Calibration — no checkerboard needed.

Phase 1: Feature-based self-calibration from driving footage.
         ORB features matched between left/right frames → estimate F → extract
         intrinsic + extrinsic params. Refines over time as more frames arrive.

Phase 2: Online quality monitoring — tracks disparity consistency and
         recalibrates if quality degrades (vibrations, bumps, temperature).

Runs on Raspberry Pi 5 — no GPU needed, pure OpenCV.

Usage:
  # Calibrate from live camera
  python3 auto_calibration.py --live

  # Calibrate from recorded video
  python3 auto_calibration.py --video /path/to/stereo.h264

  # Monitor and recalibrate continuously
  python3 auto_calibration.py --monitor
"""

import cv2
import numpy as np
import json
import time
import os
import argparse
from pathlib import Path

CALIB_DIR = Path.home() / "wip" / "calibration" / "auto"
CALIB_FILE = CALIB_DIR / "stereo_auto.json"
CALIB_LOG = CALIB_DIR / "calibration_log.csv"

# Stereo camera params (Arducam Camarray OV9281 side-by-side)
FRAME_W = 2560   # total width (1280 per cam, side-by-side)
FRAME_H = 800
CAM_W = 1280
CAM_H = 800
BASELINE_MM = 200.0  # physical baseline between cameras (measured)

# Feature detection — SIFT for sub-pixel accuracy on grayscale
SIFT_FEATURES = 3000
MATCH_RATIO = 0.70       # Lowe's ratio test (stricter for SIFT)
MIN_MATCHES = 50         # minimum matches to attempt calibration
MIN_INLIERS = 30         # minimum inliers for valid F matrix

# Vertical alignment — Camarray mechanical misalignment
VERTICAL_SHIFT_PX = 15   # measured: right image is ~15px higher than left
                          # corrected before matching by shifting right image

# Calibration quality
MIN_FRAMES_INITIAL = 100    # frames needed for first calibration
RECALIB_INTERVAL = 500      # re-evaluate calibration every N frames
QUALITY_THRESHOLD = 0.85    # below this → recalibrate

# Initial guess for OV9281 intrinsics at 1280px wide
# OV9281: 3μm pixel, typical M12 lens ~2.8mm → f = 2800/3 ≈ 933px at native
# At 1280 wide (vs 1280 native) → ~933px. But measured from wall test: ~406px at 640w = ~812px at 1280w
FOCAL_INIT = 812.0
CX_INIT = CAM_W / 2.0
CY_INIT = CAM_H / 2.0


class AutoCalibrator:
    def __init__(self):
        CALIB_DIR.mkdir(parents=True, exist_ok=True)

        # SIFT for better accuracy on low-texture grayscale
        self.sift = cv2.SIFT_create(nfeatures=SIFT_FEATURES)
        self.flann = cv2.FlannBasedMatcher(
            dict(algorithm=1, trees=5), dict(checks=50))
        # Keep ORB as fallback
        self.orb = cv2.ORB.create(nfeatures=2000)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

        # Accumulated data
        self.all_pts_left = []
        self.all_pts_right = []
        self.frame_count = 0
        self.calib_count = 0

        # Current calibration
        self.K_left = None
        self.K_right = None
        self.dist_left = None
        self.dist_right = None
        self.R = None
        self.T = None
        self.quality = 0.0

        # Load existing calibration if available
        self._load()

    def _load(self):
        if CALIB_FILE.exists():
            with open(CALIB_FILE) as f:
                data = json.load(f)
            self.K_left = np.array(data["K_left"])
            self.K_right = np.array(data["K_right"])
            self.dist_left = np.array(data["dist_left"])
            self.dist_right = np.array(data["dist_right"])
            self.R = np.array(data["R"])
            self.T = np.array(data["T"])
            self.quality = data.get("quality", 0.0)
            self.calib_count = data.get("calib_count", 0)
            print(f"[auto_calib] Loaded calibration #{self.calib_count}, "
                  f"quality={self.quality:.3f}")

    def _save(self):
        data = {
            "K_left": self.K_left.tolist(),
            "K_right": self.K_right.tolist(),
            "dist_left": self.dist_left.tolist(),
            "dist_right": self.dist_right.tolist(),
            "R": self.R.tolist(),
            "T": self.T.tolist(),
            "quality": self.quality,
            "calib_count": self.calib_count,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "frames_used": self.frame_count,
        }
        with open(CALIB_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[auto_calib] Saved calibration #{self.calib_count}, "
              f"quality={self.quality:.3f}")

    def _log(self, msg):
        with open(CALIB_LOG, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')},{msg}\n")

    def extract_matches(self, left, right):
        """Extract SIFT features, correct vertical alignment, match left/right."""
        # CLAHE for better contrast on grayscale
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        left_c = clahe.apply(left) if len(left.shape) == 2 else left
        right_c = clahe.apply(right) if len(right.shape) == 2 else right

        # Correct vertical misalignment
        if VERTICAL_SHIFT_PX != 0:
            M = np.float32([[1, 0, 0], [0, 1, VERTICAL_SHIFT_PX]])
            right_c = cv2.warpAffine(right_c, M, (right_c.shape[1], right_c.shape[0]))

        # SIFT matching
        kp1, des1 = self.sift.detectAndCompute(left_c, None)
        kp2, des2 = self.sift.detectAndCompute(right_c, None)

        if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
            return None, None

        matches = self.flann.knnMatch(des1, des2, k=2)

        # Lowe's ratio test
        good = [m for m, n in matches if m.distance < MATCH_RATIO * n.distance]

        if len(good) < MIN_MATCHES:
            return None, None

        pts1 = np.float32([kp1[m.queryIdx].pt for m in good])
        pts2 = np.float32([kp2[m.trainIdx].pt for m in good])

        # After vertical correction, dy should be small
        dy = np.abs(pts1[:, 1] - pts2[:, 1])
        mask = dy < 5.0  # tighter filter now that vertical is corrected
        pts1 = pts1[mask]
        pts2 = pts2[mask]

        # Horizontal disparity should be positive (left cam sees further left)
        dx = pts1[:, 0] - pts2[:, 0]
        mask = dx > 0
        pts1 = pts1[mask]
        pts2 = pts2[mask]

        if len(pts1) < MIN_MATCHES:
            return None, None

        return pts1, pts2

    def process_frame(self, stereo_frame, flip=True):
        """Process a stereo side-by-side frame. Returns True if calibrated."""
        # Cameras are mounted upside down — flip 180°
        if flip:
            stereo_frame = cv2.flip(stereo_frame, -1)

        # Split stereo frame
        if stereo_frame.shape[1] > CAM_W:
            left = stereo_frame[:, :CAM_W]
            right = stereo_frame[:, CAM_W:CAM_W * 2]
        else:
            return False

        if len(left.shape) == 3:
            left = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
            right = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)

        pts_l, pts_r = self.extract_matches(left, right)
        if pts_l is None:
            return False

        self.all_pts_left.append(pts_l)
        self.all_pts_right.append(pts_r)
        self.frame_count += 1

        # Initial calibration
        if self.K_left is None and self.frame_count >= MIN_FRAMES_INITIAL:
            return self.calibrate()

        # Periodic recalibration check
        if (self.K_left is not None and
                self.frame_count % RECALIB_INTERVAL == 0):
            q = self.evaluate_quality(left, right)
            if q < QUALITY_THRESHOLD:
                print(f"[auto_calib] Quality dropped to {q:.3f}, recalibrating...")
                self._log(f"recalib_triggered,quality={q:.3f}")
                return self.calibrate()

        return False

    def calibrate(self):
        """Run calibration from accumulated feature matches."""
        # Concatenate all points
        pts_l = np.vstack(self.all_pts_left)
        pts_r = np.vstack(self.all_pts_right)

        print(f"[auto_calib] Calibrating with {len(pts_l)} point pairs "
              f"from {self.frame_count} frames...")

        # Find Fundamental matrix
        F, mask = cv2.findFundamentalMat(pts_l, pts_r, cv2.FM_RANSAC,
                                         ransacReprojThreshold=1.0,
                                         confidence=0.999)
        if F is None:
            print("[auto_calib] Failed to find F matrix")
            return False

        inliers = mask.ravel().sum()
        if inliers < MIN_INLIERS:
            print(f"[auto_calib] Too few inliers: {inliers}")
            return False

        pts_l_in = pts_l[mask.ravel() == 1]
        pts_r_in = pts_r[mask.ravel() == 1]

        # Estimate intrinsics from F
        # For stereo with similar cameras: E = K'.T @ F @ K
        # Start with initial guess and refine
        K_init = np.array([
            [FOCAL_INIT, 0, CX_INIT],
            [0, FOCAL_INIT, CY_INIT],
            [0, 0, 1]
        ], dtype=np.float64)

        # Essential matrix from F
        E = K_init.T @ F @ K_init

        # Decompose E → R, T
        _, R, T, mask_pose = cv2.recoverPose(E, pts_l_in, pts_r_in, K_init)

        # Refine focal length from epipolar error
        K_refined = self._refine_intrinsics(pts_l_in, pts_r_in, K_init, R, T)

        # Scale T: normalize and multiply by known baseline
        T_scaled = (T / np.linalg.norm(T)) * BASELINE_MM
        # Force T to be mostly horizontal (cameras are parallel)
        T_scaled[1] = 0  # no vertical offset
        T_scaled[2] = 0  # no depth offset
        T_scaled[0] = -BASELINE_MM  # negative X = right cam is to the right

        # Set calibration
        self.K_left = K_refined.copy()
        self.K_right = K_refined.copy()
        self.dist_left = np.zeros(5)  # TODO: estimate from checkerboard
        self.dist_right = np.zeros(5)
        self.R = R
        self.T = T_scaled
        self.calib_count += 1

        # Evaluate quality
        self.quality = self._compute_epipolar_error(pts_l_in, pts_r_in, F)

        self._save()
        self._log(f"calibrated,count={self.calib_count},"
                  f"quality={self.quality:.4f},inliers={inliers},"
                  f"frames={self.frame_count},points={len(pts_l_in)}")

        print(f"[auto_calib] Calibration #{self.calib_count} done!")
        print(f"  Focal length: {K_refined[0,0]:.1f} px")
        print(f"  Principal point: ({K_refined[0,2]:.1f}, {K_refined[1,2]:.1f})")
        print(f"  Inliers: {inliers}/{len(pts_l)}")
        print(f"  Epipolar error: {self.quality:.4f} px")

        # Keep recent points, discard old ones
        n_keep = min(len(self.all_pts_left), 200)
        self.all_pts_left = self.all_pts_left[-n_keep:]
        self.all_pts_right = self.all_pts_right[-n_keep:]

        return True

    def _refine_intrinsics(self, pts_l, pts_r, K_init, R, T):
        """Refine focal length by minimizing epipolar error."""
        best_f = K_init[0, 0]
        best_err = float("inf")

        # Search around initial focal length
        for df in np.linspace(-100, 100, 201):
            f = K_init[0, 0] + df
            K_test = K_init.copy()
            K_test[0, 0] = f
            K_test[1, 1] = f

            E_test = K_test.T @ (self._skew(T) @ R) @ K_test
            F_test = np.linalg.inv(K_test).T @ E_test @ np.linalg.inv(K_test)

            err = self._compute_epipolar_error(pts_l, pts_r, F_test)
            if err < best_err:
                best_err = err
                best_f = f

        K_refined = K_init.copy()
        K_refined[0, 0] = best_f
        K_refined[1, 1] = best_f
        return K_refined

    @staticmethod
    def _skew(v):
        """Skew-symmetric matrix from 3-vector."""
        v = v.flatten()
        return np.array([
            [0, -v[2], v[1]],
            [v[2], 0, -v[0]],
            [-v[1], v[0], 0]
        ])

    @staticmethod
    def _compute_epipolar_error(pts1, pts2, F):
        """Mean symmetric epipolar distance."""
        ones = np.ones((len(pts1), 1))
        p1 = np.hstack([pts1, ones])
        p2 = np.hstack([pts2, ones])

        # Epipolar lines in right image
        lines2 = (F @ p1.T).T
        # Distance of right points to lines
        d2 = np.abs(np.sum(p2 * lines2, axis=1)) / \
             np.sqrt(lines2[:, 0]**2 + lines2[:, 1]**2)

        # Epipolar lines in left image
        lines1 = (F.T @ p2.T).T
        d1 = np.abs(np.sum(p1 * lines1, axis=1)) / \
             np.sqrt(lines1[:, 0]**2 + lines1[:, 1]**2)

        return float(np.mean(d1 + d2) / 2.0)

    def evaluate_quality(self, left, right):
        """Evaluate current calibration quality on a frame pair."""
        if self.K_left is None:
            return 0.0

        pts_l, pts_r = self.extract_matches(left, right)
        if pts_l is None or len(pts_l) < 20:
            return self.quality  # can't evaluate, keep current

        # Rectify points and check vertical alignment
        R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(
            self.K_left, self.dist_left,
            self.K_right, self.dist_right,
            (CAM_W, CAM_H), self.R, self.T,
            alpha=0
        )

        map1x, map1y = cv2.initUndistortRectifyMap(
            self.K_left, self.dist_left, R1, P1,
            (CAM_W, CAM_H), cv2.CV_32FC1
        )
        map2x, map2y = cv2.initUndistortRectifyMap(
            self.K_right, self.dist_right, R2, P2,
            (CAM_W, CAM_H), cv2.CV_32FC1
        )

        left_rect = cv2.remap(left, map1x, map1y, cv2.INTER_LINEAR)
        right_rect = cv2.remap(right, map2x, map2y, cv2.INTER_LINEAR)

        # Re-match on rectified images
        pts_lr, pts_rr = self.extract_matches(left_rect, right_rect)
        if pts_lr is None:
            return self.quality

        # Quality = how well rectified points align vertically
        dy = np.abs(pts_lr[:, 1] - pts_rr[:, 1])
        mean_dy = np.mean(dy)

        # Perfect rectification → dy ≈ 0
        # quality = 1.0 when mean_dy = 0, drops as dy increases
        q = max(0.0, 1.0 - mean_dy / 5.0)
        return q

    def get_rectify_maps(self):
        """Return rectification maps for use in depth estimation."""
        if self.K_left is None:
            return None

        R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(
            self.K_left, self.dist_left,
            self.K_right, self.dist_right,
            (CAM_W, CAM_H), self.R, self.T,
            alpha=0
        )

        map1x, map1y = cv2.initUndistortRectifyMap(
            self.K_left, self.dist_left, R1, P1,
            (CAM_W, CAM_H), cv2.CV_32FC1
        )
        map2x, map2y = cv2.initUndistortRectifyMap(
            self.K_right, self.dist_right, R2, P2,
            (CAM_W, CAM_H), cv2.CV_32FC1
        )

        return map1x, map1y, map2x, map2y, Q

    @property
    def is_calibrated(self):
        return self.K_left is not None


def main():
    parser = argparse.ArgumentParser(description="Asmile Auto Stereo Calibration")
    parser.add_argument("--live", action="store_true",
                        help="Calibrate from live camera")
    parser.add_argument("--video", type=str,
                        help="Calibrate from recorded video file")
    parser.add_argument("--monitor", action="store_true",
                        help="Monitor calibration quality continuously")
    args = parser.parse_args()

    cal = AutoCalibrator()

    if args.video:
        cap = cv2.VideoCapture(args.video)
        print(f"[auto_calib] Processing video: {args.video}")
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            # Process every 5th frame (avoid redundant similar frames)
            if frame_idx % 5 == 0:
                calibrated = cal.process_frame(frame)
                if calibrated:
                    print(f"  Calibrated at frame {frame_idx}")
            frame_idx += 1
            if frame_idx % 100 == 0:
                print(f"  Frame {frame_idx}...")
        cap.release()

    elif args.live or args.monitor:
        # Use rpicam-vid via pipe
        import subprocess
        cmd = [
            "rpicam-vid", "--width", str(FRAME_W), "--height", str(FRAME_H),
            "--framerate", "15", "--codec", "yuv420",
            "--timeout", "0", "--nopreview",
            "--vflip", "--hflip", "-o", "-"
        ]

        env = os.environ.copy()
        fix_path = str(Path.home() / "streaming" / "arducam_fix.so")
        if os.path.exists(fix_path):
            env["LD_PRELOAD"] = fix_path

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, env=env)
        frame_size = FRAME_W * FRAME_H * 3 // 2  # YUV420

        print("[auto_calib] Live capture started. "
              f"Need {MIN_FRAMES_INITIAL} frames for initial calibration...")

        try:
            while True:
                raw = proc.stdout.read(frame_size)
                if len(raw) < frame_size:
                    break

                yuv = np.frombuffer(raw, dtype=np.uint8).reshape(
                    FRAME_H * 3 // 2, FRAME_W)
                gray = yuv[:FRAME_H, :]  # Y channel = grayscale

                calibrated = cal.process_frame(
                    gray.reshape(FRAME_H, FRAME_W), flip=False)  # rpicam-vid already flips

                if calibrated and not args.monitor:
                    print("[auto_calib] Initial calibration done!")
                    break

                if cal.frame_count % 50 == 0:
                    status = "CALIBRATED" if cal.is_calibrated else "collecting"
                    print(f"  Frame {cal.frame_count} [{status}] "
                          f"quality={cal.quality:.3f}")

        except KeyboardInterrupt:
            pass
        finally:
            proc.terminate()

    # Final status
    if cal.is_calibrated:
        print(f"\n=== Calibration Result ===")
        print(f"  Focal length: {cal.K_left[0,0]:.1f} px")
        print(f"  Principal point: ({cal.K_left[0,2]:.1f}, {cal.K_left[1,2]:.1f})")
        print(f"  Baseline: {np.linalg.norm(cal.T):.1f} mm")
        print(f"  Quality: {cal.quality:.4f} (epipolar error in px)")
        print(f"  Calibrations: {cal.calib_count}")
        print(f"  Frames processed: {cal.frame_count}")
        print(f"  Saved to: {CALIB_FILE}")
    else:
        print(f"\n[auto_calib] Not enough data yet. "
              f"Processed {cal.frame_count} frames, "
              f"need {MIN_FRAMES_INITIAL}.")


if __name__ == "__main__":
    main()
