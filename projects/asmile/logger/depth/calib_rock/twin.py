#!/usr/bin/env python3
"""
twin.py - gemello digitale (mock) del set camere di asmile #001: 2x OV9281 Inno-Maker SEPARATE.

COSA E': il profilo dell'unita' + un generatore di ISTANZE: set di camere "come montato davvero" = calibrazione
nominale (file calib_<unita>.json) + errori di montaggio e di lente. Serve a provare la calibrazione automatica
su un set nuovo PRIMA di averlo in mano.

REGOLE (dalle lezioni, vedi README):
 - la verita' del gemello usa un modello di lente RICCO (polinomio in theta + decentramento + prisma sottile +
   aspect), DIVERSO dal modello OpenCV con cui poi si fitta: niente test circolare.
 - le tolleranze di montaggio vengono dai valori MISURATI su #001 (rotazioni relative fino a -5.2/+2.1 gradi,
   cx -93 px, dcy 15 px) e si provano fino al DOPPIO (scala 2).
 - un profilo = un'unita'. Il logger (Arducam Camarray) NON ha profilo qui: mai fallback fra unita'.

CONVENZIONI: stereo "della pipeline": cam1 = SINISTRA fisica, cam2 = DESTRA fisica, X2 = R X1 + T,
T = (-B,0,0). Su #001 il file video_left e' la camera fisicamente DESTRA (order RL): to_files() fa lo scambio.
Assi camera: x destra, y giu', z avanti.
"""
import json
import os
import sys
from dataclasses import dataclass, field

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DEPTH = os.path.dirname(HERE)
if DEPTH not in sys.path:
    sys.path.insert(0, DEPTH)
from stereo_common import Calib  # noqa: E402

W, H = 1280, 800

PROFILE_001 = dict(
    unit="asmile-001",
    hw="2x Inno-Maker CAM-MIPIOV9281V2 (OV9281 mono global shutter) SEPARATE, rpicam --sync, M12",
    size=(W, H),
    baseline_mm=200.0,
    order="RL",
    file_left_is_physical="right",
    hfov_deg=58.0,
    pitch_deg=7.4,
    cam_height_m=0.825,
    wheel_circ_m=1.576,            # 10 giri col metro = 15.760 m
    blur_sigma_px=0.9,             # M12 economico: sfocatura al centro, piu' ai bordi
    noise_sigma=2.0,               # DN su 255
    # tolleranze di montaggio a scala 1 (valori MISURATI su #001); provate anche a scala 2
    tol=dict(rx_deg=5.2, ry_deg=2.1, rz_deg=0.5,     # rotazione cam2 rispetto al nominale
             baseline_mm=2.0, ty_tz_mm=2.0,
             f_pct=1.0, pp_px=100.0, lens_rel=0.10, tang=3e-4, prism=2e-4, aspect=5e-4),
    measured_001=dict(rx_ry_rz_deg=(-5.18, 2.09, 0.25), dcx_right_px=-93.2, dcy_right_px=15.0),
)
# SOLO #001. asmile-logger001 (Arducam Camarray, SBS, 0.71 m) avra' un profilo SUO quando serve il suo mock.
# Stress: CALIB_ROCK_SPORCO=k (default 1) moltiplica sfocatura e rumore del gemello, per non giudicare su un
# gemello piu' pulito del reale (corner 0.07-0.1 px contro 0.3-0.5 px veri). Va tarato con fedelta.py.
import os as _os
_k = float(_os.environ.get("CALIB_ROCK_SPORCO", "1"))
PROFILE_001["blur_sigma_px"] *= max(1.0, 0.5 + 0.5 * _k)
PROFILE_001["noise_sigma"] *= _k
PROFILES = {"asmile-001": PROFILE_001}


def load_profile(unit):
    if unit not in PROFILES:
        raise KeyError(f"nessun profilo per l'unita' '{unit}': i profili non si prestano fra unita' "
                       f"(disponibili: {list(PROFILES)}). Per un'altra unita' serve un suo profilo dedicato.")
    return PROFILES[unit]


def check_calib_file(path, unit):
    """La calib in ingresso deve essere DI QUELL'UNITA' (nome calib_<unita>*.json)."""
    b = os.path.basename(path)
    if not b.startswith(f"calib_{unit}"):
        raise ValueError(f"{b}: non e' una calib di '{unit}' (atteso calib_{unit}*.json): mai fallback fra unita'")
    return b


# ---------------------------------------------------------------------------------------------- lente ricca
@dataclass
class Lens:
    f: float
    cx: float
    cy: float
    a: tuple = (0.0, 0.0, 0.0)      # g(theta) = theta + a1 th^3 + a2 th^5 + a3 th^7
    p: tuple = (0.0, 0.0)           # decentramento (forma OpenCV)
    s: tuple = (0.0, 0.0)           # prisma sottile
    aspect: float = 0.0             # fy = f (1+aspect)


def _fwd_norm(L, x, y):
    """(x,y)=X/Z,Y/Z -> coordinate normalizzate distorte (prima di K)."""
    r = np.hypot(x, y)
    th = np.arctan(r)
    g = th + L.a[0] * th ** 3 + L.a[1] * th ** 5 + L.a[2] * th ** 7
    sc = np.where(r > 1e-9, g / np.maximum(r, 1e-12), 1.0)
    xd, yd = x * sc, y * sc
    r2 = xd * xd + yd * yd
    xt = xd + 2 * L.p[0] * xd * yd + L.p[1] * (r2 + 2 * xd * xd) + L.s[0] * r2
    yt = yd + L.p[0] * (r2 + 2 * yd * yd) + 2 * L.p[1] * xd * yd + L.s[1] * r2
    return xt, yt


class Cam:
    def __init__(self, lens: Lens):
        self.L = lens

    def project(self, Xc):
        Xc = np.asarray(Xc, float).reshape(-1, 3)
        x, y = Xc[:, 0] / Xc[:, 2], Xc[:, 1] / Xc[:, 2]
        xt, yt = _fwd_norm(self.L, x, y)
        return np.stack([self.L.f * xt + self.L.cx, self.L.f * (1 + self.L.aspect) * yt + self.L.cy], 1)

    def rays(self, u, v):
        """pixel -> direzione (x/z,y/z,1) per inversione di Newton (jacobiano numerico, vettoriale)."""
        tx = (np.asarray(u, float) - self.L.cx) / self.L.f
        ty = (np.asarray(v, float) - self.L.cy) / (self.L.f * (1 + self.L.aspect))
        x, y = tx.copy(), ty.copy()
        h = 1e-6
        for _ in range(8):
            fx, fy = _fwd_norm(self.L, x, y)
            ex, ey = fx - tx, fy - ty
            fxx, fyx = _fwd_norm(self.L, x + h, y)
            fxy, fyy = _fwd_norm(self.L, x, y + h)
            a, b, c, d = (fxx - fx) / h, (fxy - fx) / h, (fyx - fy) / h, (fyy - fy) / h
            det = a * d - b * c
            x = x - (d * ex - b * ey) / det
            y = y - (-c * ex + a * ey) / det
        return np.stack([x, y, np.ones_like(x)], -1)


def rich_from_opencv(f, cx, cy, k1, k2, rmax=0.75):
    """Coefficienti theta-polinomiali che riproducono la curva radiale OpenCV (k1,k2) su r in [0,rmax]."""
    r = np.linspace(1e-3, rmax, 200)
    th = np.arctan(r)
    target = r * (1 + k1 * r ** 2 + k2 * r ** 4)
    A = np.stack([th ** 3, th ** 5, th ** 7], 1)
    a = np.linalg.lstsq(A, target - th, rcond=None)[0]
    return Lens(f=f, cx=cx, cy=cy, a=tuple(a))


# ---------------------------------------------------------------------------------------------- istanza
def rodrigues(w):
    import cv2
    return cv2.Rodrigues(np.asarray(w, float).reshape(3, 1))[0]


def euler_deg_to_R(rx, ry, rz):
    return rodrigues(np.radians([rx, ry, rz]))


@dataclass
class Instance:
    profile: dict
    cam1: Cam
    cam2: Cam
    R: np.ndarray                   # verita': X2 = R X1 + T
    T: np.ndarray
    meta: dict = field(default_factory=dict)
    _ray_cache: dict = field(default_factory=dict, repr=False)

    @property
    def baseline_m(self):
        return float(np.linalg.norm(self.T))

    def cam(self, i):
        return self.cam1 if i == 1 else self.cam2

    def rays_cam1(self, i):
        """(origine, direzioni) di ogni pixel della camera i, espressi nel frame di cam1. Cache."""
        if i in self._ray_cache:
            return self._ray_cache[i]
        u, v = np.meshgrid(np.arange(W) + 0.0, np.arange(H) + 0.0)
        d = self.cam(i).rays(u, v)
        if i == 1:
            o = np.zeros(3)
        else:
            d = d @ self.R                      # R^T d  (riga: d @ R)
            o = -self.R.T @ self.T.ravel()
        d = d / np.linalg.norm(d, axis=-1, keepdims=True)
        self._ray_cache[i] = (o, d)
        return o, d

    def project(self, X1, i):
        X1 = np.asarray(X1, float).reshape(-1, 3)
        return self.cam1.project(X1) if i == 1 else self.cam2.project(X1 @ self.R.T + self.T.ravel())

    def to_files(self, img_cam1, img_cam2):
        """(video_left, video_right) come li scrive il recorder #001: left = camera fisicamente DESTRA."""
        return img_cam2, img_cam1


def nominal_calib(path, unit="asmile-001"):
    check_calib_file(path, unit)
    return Calib.load(path)


def make_instance(calib_path, seed=0, scale=1.0, lens_var=True, unit="asmile-001", profile=None):
    """Istanza = nominale del file + errori di montaggio (scala 1 = tolleranze misurate, 2 = doppio) + lente.
    lens_var=False: stessa lente del nominale (solo montaggio: cio' che il software puo' compensare online)."""
    prof = profile or load_profile(unit)
    cal = nominal_calib(calib_path, unit)
    rng = np.random.default_rng(seed)
    tol = prof["tol"]
    U = lambda a: rng.uniform(-a, a) * scale
    k = lambda d, i: (float(d[i]) if len(d) > i else 0.0)
    L1 = rich_from_opencv(cal.K1[0, 0], cal.K1[0, 2], cal.K1[1, 2], k(cal.d1, 0), k(cal.d1, 1))
    L2 = rich_from_opencv(cal.K2[0, 0], cal.K2[0, 2], cal.K2[1, 2], k(cal.d2, 0), k(cal.d2, 1))
    # firma minima della lente vera (piccola ma non modellata dal fit semplice): fissa anche a lens_var=False
    L1.p, L1.s = (1.5e-4, -1.0e-4), (8e-5, -5e-5)
    L2.p, L2.s = (-1.0e-4, 1.2e-4), (-6e-5, 7e-5)
    meta = {}
    if lens_var:
        # le LENTI variano (lente-sensore M12: su #001 misurato cx -93 px => pp fino a +-100 px a scala 1) e la scala 2
        # raddoppia ANCHE le lenti (f, centro ottico, distorsione, tangenziale, prisma, aspect), non solo il montaggio
        U1 = lambda a: rng.uniform(-a, a) * scale
        for L, n in ((L1, "L"), (L2, "R")):
            L.f *= 1 + U1(tol["f_pct"] / 100)
            L.cx += U1(tol["pp_px"])
            L.cy += U1(tol["pp_px"])
            L.a = tuple(np.array(L.a) * (1 + rng.normal(0, tol["lens_rel"] * scale, 3)))
            L.p = tuple(np.array(L.p) + rng.normal(0, tol["tang"] * scale, 2))
            L.s = tuple(np.array(L.s) + rng.normal(0, tol["prism"] * scale, 2))
            L.aspect = U1(tol["aspect"])
    drot = np.array([U(tol["rx_deg"]), U(tol["ry_deg"]), U(tol["rz_deg"])])
    R = euler_deg_to_R(*drot) @ cal.R
    B = (cal.baseline_mm + U(tol["baseline_mm"])) / 1000.0
    T = np.array([-B, U(tol["ty_tz_mm"]) / 1000.0, U(tol["ty_tz_mm"]) / 1000.0])
    meta.update(seed=seed, scale=scale, lens_var=lens_var, drot_deg=drot.tolist(), baseline_mm=B * 1000,
                pitch_deg=prof["pitch_deg"] + (rng.normal(0, 0.5 * scale) if lens_var else 0.0),
                f1=L1.f, f2=L2.f, pp1=(L1.cx, L1.cy), pp2=(L2.cx, L2.cy))
    return Instance(prof, Cam(L1), Cam(L2), R, T, meta), cal


def self_check(calib_path):
    """Autotest: la lente ricca riproduce OpenCV (k1,k2) entro frazioni di pixel; inversione esatta."""
    import cv2
    inst, cal = make_instance(calib_path, 0, 1.0, lens_var=False)
    pts = np.random.default_rng(1).uniform([0, 0], [W, H], (500, 2))
    r = inst.cam1.rays(pts[:, 0], pts[:, 1])
    back = inst.cam1.project(r)
    e_inv = np.abs(back - pts).max()
    X = r * 3.0
    pcv = cv2.projectPoints(X.reshape(-1, 1, 3), np.zeros(3), np.zeros(3), cal.K1, cal.d1)[0].reshape(-1, 2)
    e_ocv = np.linalg.norm(pcv - inst.cam1.project(X), axis=1)
    return dict(inversione_max_px=float(e_inv), rich_vs_opencv_p50_px=float(np.median(e_ocv)),
                rich_vs_opencv_max_px=float(e_ocv.max()))


if __name__ == "__main__":
    p = os.path.join(DEPTH, "calib_asmile-001.json")
    print(json.dumps(self_check(p), indent=1))
