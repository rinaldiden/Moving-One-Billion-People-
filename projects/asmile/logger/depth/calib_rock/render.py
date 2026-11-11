#!/usr/bin/env python3
"""
render.py - immagini sintetiche viste dal gemello: piani texturizzati (tabellone ChArUco vero, scena strada).

Ogni pixel = raggio della lente RICCA (twin.py) -> intersezione con i piani -> texture (mipmap per distanza) ->
vignettatura, sfocatura M12 (piu' forte ai bordi), rumore, esposizione. Il tabellone e' il generatore di
cv2.aruco vero, quindi il DETECTOR vero lavora sulle immagini rese.

Scene naturali: render_scene() usa piani texturizzati proceduralmente (strada, muri, oggetti). Fotogrammi VERI di #001
riproiettati con depth nota: interfaccia render_real_with_depth() (non implementata: oggi sul Mac non c'e' una
coppia frame+depth densa verificata di #001; vedi README).
"""
import os
import sys
from dataclasses import dataclass

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twin import W, H  # noqa: E402

BOARDS = {
    # nome: (dict, squares_x, squares_y, lato_quadretto_m, lato_marker_m)
    "A2_11x8_50mm": ("DICT_5X5_1000", 11, 8, 0.050, 0.037),
    "A3_10x7_38mm": ("DICT_5X5_1000", 10, 7, 0.038, 0.028),
}
MARGIN_M = 0.02


def make_board(name="A2_11x8_50mm", sq_scale=1.0):
    d, sx, sy, sq, mk = BOARDS[name]
    dic = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, d))
    b = cv2.aruco.CharucoBoard((sx, sy), sq, mk, dic)
    b.setLegacyPattern(False)
    return b


@dataclass
class Plane:
    p0: np.ndarray       # angolo (frame cam1)
    ex: np.ndarray       # versore asse texture x
    ey: np.ndarray       # versore asse texture y
    w: float             # m
    h: float
    tex: np.ndarray      # uint8 gray, risoluzione res m/px
    res: float
    pyr: list = None

    def levels(self):
        if self.pyr is None:
            self.pyr = [self.tex]
            for _ in range(7):
                t = self.pyr[-1]
                if min(t.shape) < 8:
                    break
                self.pyr.append(cv2.resize(t, (t.shape[1] // 2, t.shape[0] // 2), interpolation=cv2.INTER_AREA))
        return self.pyr


def board_texture(board_name, ppm=4.0):
    """Texture del tabellone con margine bianco. ppm = px per mm."""
    board = make_board(board_name)
    d, sx, sy, sq, mk = BOARDS[board_name]
    m = int(round(MARGIN_M * 1000 * ppm))
    size = (int(round(sx * sq * 1000 * ppm)) + 2 * m, int(round(sy * sq * 1000 * ppm)) + 2 * m)
    img = board.generateImage(size, marginSize=m, borderBits=1)
    return img, 1.0 / (ppm * 1000.0), (size[0] / (ppm * 1000), size[1] / (ppm * 1000))


def board_plane(board_name, rvec, tvec, ppm=4.0, tex_cache={}):
    key = (board_name, ppm)
    if key not in tex_cache:
        tex_cache[key] = board_texture(board_name, ppm)
    img, res, (wm, hm) = tex_cache[key]
    R = cv2.Rodrigues(np.asarray(rvec, float).reshape(3, 1))[0]
    t = np.asarray(tvec, float).ravel()
    p0 = R @ np.array([-MARGIN_M, -MARGIN_M, 0.0]) + t
    return Plane(p0, R[:, 0].copy(), R[:, 1].copy(), wm, hm, img, res)


def procedural_texture(rng, size_px=(1024, 1024), contrast=1.0):
    """Texture ricca di spigoli (SIFT-friendly): rumore multi-ottava + rettangoli + linee."""
    w, h = size_px
    img = np.zeros((h, w), np.float32)
    for o, amp in ((8, 1.0), (16, 0.8), (32, 0.6), (64, 0.45), (128, 0.3)):
        n = rng.normal(0, 1, (h // o + 2, w // o + 2)).astype(np.float32)
        img += amp * cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)
    out = ((img - img.min()) / (np.ptp(img) + 1e-6) * 255).astype(np.uint8)
    for _ in range(120):
        x, y = rng.integers(0, w - 20), rng.integers(0, h - 20)
        ww, hh = rng.integers(8, 90), rng.integers(8, 90)
        cv2.rectangle(out, (x, y), (x + ww, y + hh), int(rng.integers(0, 255)), -1 if rng.random() < .6 else 2)
    for _ in range(60):
        cv2.line(out, (int(rng.integers(0, w)), int(rng.integers(0, h))),
                 (int(rng.integers(0, w)), int(rng.integers(0, h))), int(rng.integers(0, 255)), int(rng.integers(1, 4)))
    out = np.clip((out.astype(np.float32) - 128) * contrast + 128, 0, 255).astype(np.uint8)
    return out


def _plane_hits(o, d, pl):
    n = np.cross(pl.ex, pl.ey)
    den = d @ n
    with np.errstate(divide="ignore", invalid="ignore"):
        lam = (n @ (pl.p0 - o)) / den
    X = o + d * lam[..., None]
    s = (X - pl.p0) @ pl.ex
    t = (X - pl.p0) @ pl.ey
    ok = (lam > 0.2) & np.isfinite(lam) & (s >= 0) & (s < pl.w) & (t >= 0) & (t < pl.h)
    return lam, s, t, ok, np.abs(den)


def render(inst, cam_i, planes, rng, exposure=1.0, blur=None, noise=None, bg=60):
    """Immagine uint8 1280x800 della camera cam_i (1 = sinistra fisica, 2 = destra) per i piani dati (frame cam1)."""
    prof = inst.profile
    o, d = inst.rays_cam1(cam_i)
    best = np.full((H, W), np.inf)
    val = np.full((H, W), float(bg), np.float32)
    f = inst.cam(cam_i).L.f
    for pl in planes:
        lam, s, t, ok, cosinc = _plane_hits(o, d, pl)
        if not np.isfinite(d).all():
            raise RuntimeError('render: raggi non finiti (verita\' del gemello non monotona)')
        ok &= lam < best
        if not ok.any():
            continue
        lv = pl.levels()
        # LOD: impronta del pixel in px di texture (lungo il lato piu' sfavorevole: incidenza radente)
        fp = lam / f / pl.res
        fp = fp / np.clip(cosinc, 0.15, 1.0)
        if not np.isfinite(fp[ok]).all():
            raise RuntimeError('render: impronta NaN nei pixel visibili (lod) - il render NON deve passare in silenzio')
        lod = np.clip(np.round(np.log2(np.maximum(fp, 1.0))), 0, len(lv) - 1).astype(int)
        for L in np.unique(lod[ok]):
            m = ok & (lod == L)
            sc = 2 ** L
            mx = (s[m] / pl.res / sc - 0.5).astype(np.float32)
            my = (t[m] / pl.res / sc - 0.5).astype(np.float32)
            n = mx.size
            wcol = 1024
            rows = -(-n // wcol)
            pad = rows * wcol - n
            mxp = np.pad(mx, (0, pad)).reshape(rows, wcol)
            myp = np.pad(my, (0, pad)).reshape(rows, wcol)
            samp = cv2.remap(lv[L], mxp, myp, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).ravel()[:n]
            val[m] = samp
        best[ok] = lam[ok]
    img = val * exposure
    # vignettatura
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    r2 = ((u - W / 2) ** 2 + (v - H / 2) ** 2) / ((W / 2) ** 2 + (H / 2) ** 2)
    img = img * (1 - 0.30 * r2)
    # sfocatura M12: nitida al centro, piu' morbida ai bordi (miscela di due gaussiane)
    s0 = prof["blur_sigma_px"] if blur is None else blur
    a = cv2.GaussianBlur(img, (0, 0), s0)
    b = cv2.GaussianBlur(img, (0, 0), s0 * 1.8)
    wgt = np.clip(r2 * 1.2, 0, 1)
    img = a * (1 - wgt) + b * wgt
    sg = prof["noise_sigma"] if noise is None else noise
    img = img + rng.normal(0, 1, img.shape) * (sg + 0.03 * np.sqrt(np.maximum(img, 0)))
    return np.clip(img, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------------------------- scena strada
def scene_planes(rng, inst, s, textures):
    """Scena stile strada per #001 con la bici a s metri dall'origine. Frame cam1 (cam pitchata di pitch_deg).
    textures: dict creato da scene_textures(). Ritorna lista di Plane."""
    p = np.radians(inst.meta.get("pitch_deg", inst.profile["pitch_deg"]))
    h = inst.profile["cam_height_m"]
    ex = np.array([1.0, 0, 0])
    g = np.array([0.0, np.cos(p), np.sin(p)])        # "giu'" in frame camera
    fh = np.array([0.0, -np.sin(p), np.cos(p)])      # avanti orizzontale in frame camera
    up = -g
    P = lambda lat, down, fwd: lat * ex + down * g + (fwd - s) * fh
    planes = []
    planes.append(Plane(P(-12, h, -3), ex, fh, 24.0, 80.0, textures["ground"], 24.0 / textures["ground"].shape[1]))
    planes.append(Plane(P(-4.0, h, -3), fh, up, 80.0, h + 4, textures["wall_l"], 80.0 / textures["wall_l"].shape[1]))
    planes.append(Plane(P(5.0, h, -3), fh, up, 80.0, h + 4, textures["wall_r"], 80.0 / textures["wall_r"].shape[1]))
    planes.append(Plane(P(-12, h, 45), ex, up, 24.0, h + 6, textures["far"], 24.0 / textures["far"].shape[1]))
    for k, (lat, fwd) in enumerate(((-1.0, 4.0), (1.2, 7.0), (-2.2, 11.0), (0.6, 16.0), (2.0, 22.0), (-0.5, 30.0))):
        tx = textures["obj"][k % len(textures["obj"])]
        planes.append(Plane(P(lat - 0.6, h, fwd), ex, up, 1.2, 1.8, tx, 1.2 / tx.shape[1]))
    return planes


def scene_textures(rng):
    return dict(ground=procedural_texture(rng, (2048, 4096 // 2 * 2), 1.0)[:, :2048],
                wall_l=procedural_texture(rng, (2048, 512)), wall_r=procedural_texture(rng, (2048, 512)),
                far=procedural_texture(rng, (1024, 512)),
                obj=[procedural_texture(rng, (256, 384)) for _ in range(3)])


def render_real_with_depth(*a, **k):
    raise NotImplementedError(
        "Riproiezione di un fotogramma VERO di #001 con depth nota: interfaccia pronta, non implementata. "
        "Serve una coppia (frame, depth densa) di #001 verificata col metro; oggi non e' sul Mac. "
        "Firma prevista: render_real_with_depth(inst, frame_cam1, depth_cam1_m, cam_i) -> img cam_i.")
