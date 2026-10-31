#!/usr/bin/env python3
"""
stereo_common.py — fondamenta della pipeline depth del logger asmile.

Hardware: Arducam Camarray, 2x OV9281 global-shutter mono 1280x800 affiancate
in un frame side-by-side 2560x800. Baseline FISSA ~200mm (ancora metrica).

Qui stanno: formato calibrazione (JSON), split del frame SBS in L/R (con
flip per montaggio capovolto + ordine L/R configurabile), costruzione delle
mappe di rettifica e la formula di profondita'.

La scala e' METRICA PER COSTRUZIONE: Z = f * B / disparita', con B=200mm nota.
Non si usa rettifica non-calibrata (Hartley): perderebbe la scala. Intrinseci
e baseline sono l'ancora; cio' che si ri-stima online e' solo la ROTAZIONE
relativa tra le camere (vedi autorectify.py).
"""
import json
import numpy as np
import cv2

# --- default fisici del rig (gia' noti dal progetto; sovrascrivibili da calib/CLI) ---
FULL_W, FULL_H = 2560, 800          # frame side-by-side
CAM_W, CAM_H = 1280, 800            # singola camera
BASELINE_MM = 200.0                 # baseline fisica Camarray (calib: 199.53mm) — NOTA
CAM_HEIGHT_M = 0.77                 # altezza camera da terra (da object_depth.py) — NOTA
                                    # (valore bici #001; ri-confermare solo se il mount logger cambia)


class Calib:
    """Calibrazione stereo. K/d per camera + R,T estrinseci (T in mm)."""

    def __init__(self, K1, d1, K2, d2, R, T, size=(CAM_W, CAM_H),
                 baseline_mm=BASELINE_MM):
        self.K1 = np.asarray(K1, float)
        self.d1 = np.asarray(d1, float).ravel()
        self.K2 = np.asarray(K2, float)
        self.d2 = np.asarray(d2, float).ravel()
        self.R = np.asarray(R, float)
        self.T = np.asarray(T, float).reshape(3, 1)
        self.size = (int(size[0]), int(size[1]))
        self.baseline_mm = float(baseline_mm)

    # ---- I/O ----
    @classmethod
    def load(cls, path):
        """Carica JSON (formato stereo_auto_sift.json) o YAML OpenCV."""
        if str(path).endswith((".yaml", ".yml")):
            return cls._from_yaml(path)
        with open(path) as f:
            c = json.load(f)
        T = np.array(c["T"], float).reshape(3, 1)
        baseline = c.get("baseline_mm", abs(float(T[0, 0])) or BASELINE_MM)
        size = tuple(c.get("size", (CAM_W, CAM_H)))
        return cls(c["K_left"], c["dist_left"], c["K_right"], c["dist_right"],
                   c["R"], T, size=size, baseline_mm=baseline)

    @classmethod
    def _from_yaml(cls, path):
        fs = cv2.FileStorage(str(path), cv2.FILE_STORAGE_READ)
        g = lambda k: fs.getNode(k).mat()
        w = int(fs.getNode("image_width").real() or CAM_W)
        h = int(fs.getNode("image_height").real() or CAM_H)
        T = g("T")
        obj = cls(g("camera_matrix_left"), g("dist_coeffs_left"),
                  g("camera_matrix_right"), g("dist_coeffs_right"),
                  g("R"), T, size=(w, h), baseline_mm=abs(float(T[0, 0])))
        fs.release()
        return obj

    def save(self, path):
        with open(path, "w") as f:
            json.dump({
                "K_left": self.K1.tolist(), "dist_left": self.d1.tolist(),
                "K_right": self.K2.tolist(), "dist_right": self.d2.tolist(),
                "R": self.R.tolist(), "T": self.T.ravel().tolist(),
                "size": list(self.size), "baseline_mm": self.baseline_mm,
            }, f, indent=2)

    # ---- rettifica ----
    def rectify(self, alpha=0):
        """stereoRectify -> dict con R1,R2,P1,P2,Q, mappe remap e focale/baseline."""
        R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(
            self.K1, self.d1, self.K2, self.d2, self.size, self.R, self.T,
            flags=cv2.CALIB_ZERO_DISPARITY, alpha=alpha)
        m1x, m1y = cv2.initUndistortRectifyMap(self.K1, self.d1, R1, P1,
                                               self.size, cv2.CV_32FC1)
        m2x, m2y = cv2.initUndistortRectifyMap(self.K2, self.d2, R2, P2,
                                               self.size, cv2.CV_32FC1)
        return {
            "R1": R1, "R2": R2, "P1": P1, "P2": P2, "Q": Q,
            "m1x": m1x, "m1y": m1y, "m2x": m2x, "m2y": m2y,
            "focal_px": float(P1[0, 0]),
            "baseline_m": self.baseline_mm / 1000.0,
        }


# --- split del frame side-by-side ---
def split_sbs(frame, order="LR", flip180=True):
    """
    Spezza il frame SBS 2560x800 nelle due viste (1280x800).

    order: 'LR' = sinistra a sx del frame; 'RL' se le camere sono scambiate.
    flip180: camere montate CAPOVOLTE -> ruota 180 (= vflip+hflip). ATTENZIONE:
             il 180 scambia anche L<->R, quindi dopo il flip si inverte l'ordine.
    """
    if frame.ndim == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = frame.shape[:2]
    half = w // 2
    a, b = frame[:, :half], frame[:, half:]           # viste grezze sx|dx del frame
    if flip180:
        a = cv2.rotate(a, cv2.ROTATE_180)
        b = cv2.rotate(b, cv2.ROTATE_180)
        a, b = b, a                                   # il 180 scambia L<->R
    left, right = (a, b) if order == "LR" else (b, a)
    return left, right


def depth_from_disparity(disp, focal_px, baseline_m, min_disp=0.5):
    """Z = f*B/d in metri. disp gia' in px (subpixel). <=min_disp -> 0 (invalido)."""
    disp = np.asarray(disp, np.float32)
    z = np.zeros_like(disp)
    valid = disp > min_disp
    z[valid] = (focal_px * baseline_m) / disp[valid]
    return z


def rel_error_model(focal_px, baseline_m, Z, dd_px):
    """Errore relativo di profondita' atteso: (Z/(f*B))*dd. Per sanity-check."""
    return (float(Z) / (focal_px * baseline_m)) * float(dd_px)
