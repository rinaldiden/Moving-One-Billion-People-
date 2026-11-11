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
    g = th + sum(c * th ** (3 + 2 * i) for i, c in enumerate(L.a))
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
        # partenza RADIALE robusta: inversione della sola curva g(theta) (monotona, verificata) per interpolazione su tabella densa;
        # poi Newton 2D (solo p,s e aspect restano da assorbire). Il Newton partito da (tx,ty) divergeva su lenti variate (NaN).
        L = self.L
        th_end = getattr(L, "th_end", 1.2)
        tt = np.linspace(0.0, th_end, 6000)
        gg = tt + sum(c * tt ** (3 + 2 * i) for i, c in enumerate(L.a))
        rd = np.hypot(tx, ty)
        if np.all(np.diff(gg) > 0):
            th0 = np.interp(rd, gg, tt)
            sc0 = np.where(rd > 1e-12, np.tan(th0) / np.maximum(rd, 1e-12), 1.0)
            x, y = tx * sc0, ty * sc0
        else:
            x, y = tx.copy(), ty.copy()
        h = 1e-6
        for _ in range(40):
            fx, fy = _fwd_norm(self.L, x, y)
            ex, ey = fx - tx, fy - ty
            if float(np.nanmax(np.maximum(np.abs(ex), np.abs(ey)))) * L.f < 1e-6:
                break
            fxx, fyx = _fwd_norm(self.L, x + h, y)
            fxy, fyy = _fwd_norm(self.L, x, y + h)
            a, b, c, d = (fxx - fx) / h, (fxy - fx) / h, (fyx - fy) / h, (fyy - fy) / h
            det = a * d - b * c
            x = x - (d * ex - b * ey) / det
            y = y - (-c * ex + a * ey) / det
        fx, fy = _fwd_norm(self.L, x, y)
        res = np.maximum(np.abs(fx - tx), np.abs(fy - ty)) * self.L.f
        if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y)) and float(np.max(res)) < 0.01):
            raise RuntimeError(f"twin.Cam.rays: inversione non convergente/NaN ({int((~np.isfinite(res)).sum())} NaN, "
                               f"residuo max {float(np.nanmax(res)):.3g} px): verita' del gemello non monotona")
        return np.stack([x, y, np.ones_like(x)], -1)


MONO_SLOPE = 0.45      # pendenza (rapporto a quella centrale) alla quale la verita' lascia la curva OpenCV se questa non e' monotona


def _cv_curve(r, k1, k2, k3):
    return r * (1 + k1 * r ** 2 + k2 * r ** 4 + k3 * r ** 6)


def _cv_slope(r, k1, k2, k3):
    return 1 + 3 * k1 * r ** 2 + 5 * k2 * r ** 4 + 7 * k3 * r ** 6


RD_MARGIN = 0.12       # la verita' e' valida oltre il bordo nominale di tanto (spostamento del centro ottico a scala 2 = 200 px = 0.18)


def rich_from_opencv(f, cx, cy, k1, k2, rmax=0.75, k3=0.0, rd_edge=None):
    """Coefficienti theta-polinomiali della VERITA' radiale del gemello, che riproducono la curva OpenCV (k1,k2,k3).

    VERITA' MONOTONA FINO AL BORDO (nota critico 11/11): la curva OpenCV r_d(r) = r(1+k1 r^2+k2 r^4+k3 r^6) puo' avere un
    massimo (B30 destra, k3 -0.296: massimo r_d 0.644 a r 0.91) mentre gli angoli dell'immagine arrivano a r_d 0.73. Oltre il
    massimo OpenCV non e' invertibile e nessuna lente fisica reale e' cosi': li' la curva non descrive niente di vero.
    Regola (deterministica, nessun parametro libero oltre MONO_SLOPE):
      - fino a r_c la verita' E' la curva OpenCV (r_c = ultimo r con pendenza >= MONO_SLOPE x pendenza centrale (0.45); se la
        curva e' monotona fino al bordo con pendenza sopra soglia -> r_c = oltre il bordo, NIENTE cambia: caso PRIMA e lente sinistra);
      - oltre r_c prosegue in linea retta (r_d lineare in r) con la pendenza di r_c: monotona, C1, finita;
      - r_c e' anche il DOMINIO del giudice (gate.calib_domain_rd): dentro verita' = curva OpenCV, fuori il giudice non misura;
      - il fit theta-polinomiale e' fatto fino a r_d = rd_edge x 1.02 (angolo piu' lontano dell'immagine) e poi VERIFICATO:
        monotono su tutto l'intervallo e fedele a OpenCV entro 0.5 px dove la curva e' valida; altrimenti RuntimeError.
    Perche' non altera cio' che il mock misura: il giudice valuta solo i punti in cui la calib e' invertibile (gate.truth_eval:
    fuori dominio = esclusi e CONTATI, e c'e' una guardia che li rende ROSSI); dentro il dominio verita' e OpenCV coincidono.
    L'anello esterno serve solo a far renderizzare l'immagine senza NaN."""
    if rd_edge is None:
        rd_edge = rmax / 1.02
    rd_edge = rd_edge + RD_MARGIN
    s0 = _cv_slope(0.0, k1, k2, k3)
    r = np.linspace(0.0, 3.0, 30001)
    ok = _cv_slope(r, k1, k2, k3) >= MONO_SLOPE * s0
    bad = np.where(~ok)[0]
    r_c = float(r[bad[0] - 1]) if len(bad) else None
    if r_c is not None and _cv_curve(r_c, k1, k2, k3) > rd_edge * 1.02:
        r_c = None                      # il bordo si raggiunge prima di perdere pendenza: curva OpenCV invariata
    if r_c is None:
        cur = _cv_curve(r, k1, k2, k3)
        j = np.where(cur >= rd_edge * 1.02)[0]
        r_end = float(r[j[0]]) if len(j) else rmax       # r (non distorto) a cui la curva raggiunge il bordo
        rr = np.linspace(1e-3, r_end, 400)
        target = _cv_curve(rr, k1, k2, k3)
    else:
        rd_c, sl = _cv_curve(r_c, k1, k2, k3), _cv_slope(r_c, k1, k2, k3)
        r_end = r_c + (rd_edge * 1.02 - rd_c) / sl
        rr = np.linspace(1e-3, r_end, 600)
        target = np.where(rr <= r_c, _cv_curve(rr, k1, k2, k3), rd_c + sl * (rr - r_c))
    th = np.arctan(rr)
    tt = np.linspace(1e-3, np.arctan(r_end), 2000)
    lim = r_end if r_c is None else r_c
    m = rr <= lim
    n0 = 3 if k3 == 0.0 else 4
    last = None
    w = np.where(rr <= lim, 3.0, 1.0)
    for n in range(n0, 11):          # il minimo numero di coefficienti (th^3..th^(2n+1)) che e' fedele e monotono
        A = np.stack([th ** (3 + 2 * i) for i in range(n)], 1)
        a = np.linalg.lstsq(A * w[:, None], (target - th) * w, rcond=None)[0]
        g = lambda t: t + sum(c * t ** (3 + 2 * i) for i, c in enumerate(a))
        gg = g(tt)
        err = float(np.abs(g(th[m]) - target[m]).max() * f)
        mono = bool(np.all(np.diff(gg) > 0) and np.all(np.isfinite(gg)) and gg[-1] >= rd_edge)
        last = (n, err, mono, float(gg[-1]))
        if mono and err <= 0.5:
            break
    n, err, mono, gend = last
    if not mono:
        raise RuntimeError(f"verita' del gemello NON monotona fino al bordo (rich_from_opencv, {n} coef, r_d finale {gend:.3f}, "
                           f"bordo {rd_edge:.3f}): lente non utilizzabile")
    if err > 0.5:
        raise RuntimeError(f"verita' del gemello: fit theta-polinomiale {err:.2f} px dalla curva OpenCV nel dominio valido: troppo")
    L = Lens(f=f, cx=cx, cy=cy, a=tuple(a))
    L.fit_err_px = err
    L.r_c = r_c
    L.th_end = float(np.arctan(r_end))
    return L


def lens_truth_ok(L):
    """La verita' radiale della lente L e' monotona fino al bordo REALE dell'immagine (con il suo centro ottico, f e aspect)?
    Vero = g(theta) strettamente crescente su [0, th_end] e g(th_end) >= raggio normalizzato dell'angolo piu' lontano."""
    tt = np.linspace(1e-3, L.th_end, 1500)
    gg = tt + sum(c * tt ** (3 + 2 * i) for i, c in enumerate(L.a))
    corner = max(np.hypot((x - L.cx) / L.f, (y - L.cy) / (L.f * (1 + L.aspect))) for x in (0, W) for y in (0, H))
    return bool(np.all(np.isfinite(gg)) and np.all(np.diff(gg) > 0) and gg[-1] >= corner * 1.02)


def lens_truth_ok(L):
    """La verita' radiale della lente L e' monotona fino al bordo REALE dell'immagine (col suo centro ottico, f e aspect)?
    Vero = g(theta) strettamente crescente su [0, th_end] e g(th_end) >= raggio normalizzato dell'angolo piu' lontano."""
    tt = np.linspace(1e-3, L.th_end, 1500)
    gg = tt + sum(c * tt ** (3 + 2 * i) for i, c in enumerate(L.a))
    corner = max(np.hypot((x - L.cx) / L.f, (y - L.cy) / (L.f * (1 + L.aspect))) for x in (0, W) for y in (0, H))
    return bool(np.all(np.isfinite(gg)) and np.all(np.diff(gg) > 0) and gg[-1] >= corner * 1.02)


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
    def _rm(K):
        return float(max(np.hypot(x - K[0, 2], y - K[1, 2]) for x in (0, W) for y in (0, H)) / K[0, 0]) * 1.02
    def _re(K):
        return float(max(np.hypot((x - K[0, 2]) / K[0, 0], (y - K[1, 2]) / K[1, 1]) for x in (0, W) for y in (0, H)))
    L1 = rich_from_opencv(cal.K1[0, 0], cal.K1[0, 2], cal.K1[1, 2], k(cal.d1, 0), k(cal.d1, 1), _rm(cal.K1), k(cal.d1, 4), rd_edge=_re(cal.K1))
    L2 = rich_from_opencv(cal.K2[0, 0], cal.K2[0, 2], cal.K2[1, 2], k(cal.d2, 0), k(cal.d2, 1), _rm(cal.K2), k(cal.d2, 4), rd_edge=_re(cal.K2))
    # firma minima della lente vera (piccola ma non modellata dal fit semplice): fissa anche a lens_var=False
    # fy/fx della calib (B30: 0.995): il gemello lo ignorava (errore di 2 px a 400 righe dal centro), ora lo legge
    L1.aspect = float(cal.K1[1, 1] / cal.K1[0, 0] - 1)
    L2.aspect = float(cal.K2[1, 1] / cal.K2[0, 0] - 1)
    L1.p, L1.s = (1.5e-4, -1.0e-4), (8e-5, -5e-5)
    L2.p, L2.s = (-1.0e-4, 1.2e-4), (-6e-5, 7e-5)
    meta = {}
    if lens_var:
        # le LENTI variano (lente-sensore M12: su #001 misurato cx -93 px => pp fino a +-100 px a scala 1) e la scala 2
        # raddoppia ANCHE le lenti (f, centro ottico, distorsione, tangenziale, prisma, aspect), non solo il montaggio
        U1 = lambda a: rng.uniform(-a, a) * scale
        # RIFIUTO delle estrazioni non fisiche: una variazione di lente che rende la verita' NON monotona fino al bordo
        # (lente impossibile) viene RIESTRATTA (stesso rng, deterministico). Cosi' il render non vede mai NaN e non si rattoppa
        # niente a posteriori. Il tasso di rifiuto e' riportato in meta['lens_var_rifiuti'].
        rif = {}
        for L, n in ((L1, "L"), (L2, "R")):
            orig = (L.f, L.cx, L.cy, L.a, L.p, L.s, L.aspect)
            for tent in range(60):
                L.f, L.cx, L.cy, L.a, L.p, L.s, L.aspect = orig
                L.f *= 1 + U1(tol["f_pct"] / 100)
                L.cx += U1(tol["pp_px"])
                L.cy += U1(tol["pp_px"])
                L.a = tuple(np.array(L.a) * (1 + rng.normal(0, tol["lens_rel"] * scale, len(L.a))))
                L.p = tuple(np.array(L.p) + rng.normal(0, tol["tang"] * scale, 2))
                L.s = tuple(np.array(L.s) + rng.normal(0, tol["prism"] * scale, 2))
                L.aspect += U1(tol["aspect"])
                if lens_truth_ok(L):
                    break
            else:
                raise RuntimeError(f"twin: nessuna variazione di lente {n} con verita' monotona in 60 estrazioni (calib/scala non adatte)")
            rif[n] = tent
        meta["lens_var_rifiuti"] = rif
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
