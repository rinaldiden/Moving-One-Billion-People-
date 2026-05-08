# Stereo Calibration — Asmile Fleet ID 002

## Current best: stereo_auto_sift.json

Auto-calibrated from driving footage using SIFT + stereoCalibrate.
No checkerboard needed.

### Results
- **Epipolar error**: 0.183 px
- **Focal left**: 411.2 px
- **Focal right**: 399.6 px
- **Baseline**: 200 mm (physical)
- **Method**: SIFT features + FLANN matcher + stereoCalibrate
- **Data**: 38,148 matches from 391 frames across 12 sessions

### Depth precision at this calibration
| Distance | Depth error | Error % |
|---|---|---|
| 1m | ~9mm | 0.9% |
| 3m | ~27mm | 0.9% |
| 5m | ~45mm | 0.9% |
| 10m | ~180mm | 1.8% |

### Camera info
- Arducam Camarray OV9281 (stereo side-by-side)
- 2560x800 total (1280x800 per camera)
- Global shutter, monochrome
- Baseline: 200mm
- Mounted upside down (vflip + hflip in software)

### Known limitations
- Rectified dy = 3.75 px (should be < 0.5 for perfect rectification)
- Focal oscillates slightly between sessions (400-420 px range)
- Distortion coefficients differ between L/R (different lens units)
- Target: 0.1 px epipolar error (may need checkerboard calibration)

### Usage
```python
import json, cv2, numpy as np

with open("stereo_auto_sift.json") as f:
    cal = json.load(f)

K1 = np.array(cal["K_left"])
K2 = np.array(cal["K_right"])
d1 = np.array(cal["dist_left"])
d2 = np.array(cal["dist_right"])
R = np.array(cal["R"])
T = np.array(cal["T"])

R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(K1, d1, K2, d2, (1280, 800), R, T, alpha=0)
map1x, map1y = cv2.initUndistortRectifyMap(K1, d1, R1, P1, (1280, 800), cv2.CV_32FC1)
map2x, map2y = cv2.initUndistortRectifyMap(K2, d2, R2, P2, (1280, 800), cv2.CV_32FC1)

# Rectify
left_rect = cv2.remap(left, map1x, map1y, cv2.INTER_LINEAR)
right_rect = cv2.remap(right, map2x, map2y, cv2.INTER_LINEAR)

# Depth
stereo = cv2.StereoSGBM_create(...)
disp = stereo.compute(left_rect, right_rect)
depth_mm = (P1[0,0] * abs(T[0,0])) / disp
```
