#!/usr/bin/env python3
"""giro_logger001_lib.py — adattatore asmile-logger001 per la pipeline video del #001 (21/11/2026). NON modifica nessun file di #001: i moduli di #001
(depth_seg_001, depth_fluido_a_001, video_fluido_001) vengono importati e i loro punti di ingresso sostituiti A RUNTIME (monkeypatch) da install().
Contiene: elenco dei clip e mappa frame->clip (per MTIME/conteggio pacchetti, clip mancante = buco), sessione virtuale (solo i fotogrammi scelti),
sorgente SBS 2560x800 -> L|R (profilo asmile-logger001: order LR, flip180 False), calibrazione (json: K/R/T + opzionali d0_px, focal_fit_px), Rect del logger.
"""
import os, sys, csv, json, subprocess, glob
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "logger", "depth"))
LOGS = os.path.join(ROOT, "asmile-loggers", "asmile-logger")
TAG = "20261121_152215"
FRAMES_CSV = os.path.join(LOGS, "_sensors", "frames", f"clip_{TAG}_frames.csv")
W, H = 1280, 800
CAM_H_LOGGER = 0.71          # altezza camera logger (CLAUDE.md agenti: 0.71 m logger)
CAL_DIR = os.path.join(ROOT, "logger", "depth")
CAL_OLD = os.path.join(CAL_DIR, "calib_asmile-logger_metro.json")          # 08/11, K=935 nominale, R=I, d0 26.3 px dal metro
CAL_NEW = os.path.join(CAL_DIR, "calib_asmile-logger001.CANDIDATO_20261121.json")
PKT = {0: 450, 1: 450, 9: 450}     # conteggi pacchetti misurati con ffprobe (gli altri 465); clip 23 non scaricato (buco) ma il suo conteggio vale 465


def chunk_table():
    """[(n, frame_inizio, frame_fine_escl, path)] per i clip presenti. Il conteggio dei frame per clip e' misurato (ffprobe -count_packets), il clip 23 manca nel pull: indice globale = somma con 465 per il buco."""
    present = {int(os.path.basename(f).split("_")[-1].split(".")[0]): f for f in glob.glob(os.path.join(LOGS, f"clip_{TAG}_*.h264"))}
    out = []; idx = 0
    for n in range(0, max(present) + 1):
        c = PKT.get(n, 465)
        if n in present: out.append((n, idx, idx + c, present[n]))
        idx += c
    return out


def select_frames():
    """fotogrammi del giro verso casa: tratti in cui la bici si muove (BLE>0.15 m/s o imbardata>3 dps, vedi report) + 1 s di margine, solo dove il clip c'e'."""
    import ego_logger001 as E
    e = E.EgoLogger(); ft = np.loadtxt(FRAMES_CSV, delimiter=",", skiprows=1)[:, 1]
    v = e.at(ft, "v"); g = np.abs(e.at(ft, "yaw_s")); mov = (v > 0.15) | (g > 3)
    idx = np.nonzero(mov)[0]; segs = []; s = p = idx[0]
    for i in idx[1:]:
        if i - p > 60: segs.append((s, p)); s = i
        p = i
    segs.append((s, p))
    have = np.zeros(len(ft), bool)
    for n, a, b, f in chunk_table(): have[a:min(b, len(ft))] = True
    sel = np.zeros(len(ft), bool)
    for a, b in segs:
        if b - a >= 60: sel[max(0, a - 15):b + 16] = True      # tratti < 4 s (mosse isolate) scartati
    sel &= have
    return np.nonzero(sel)[0], ft, e


class Session:
    """sessione virtuale: i fotogrammi scelti, in ordine, numerati 0..N-1 (i = posizione nella lista). Il t_ms e' quello del frames csv (stesso orologio dei sensori)."""
    def __init__(self, sel, ft):
        self.sel = np.asarray(sel); self.t = [int(ft[i]) for i in self.sel]
        self.tab = chunk_table()

    def gen(self, side):
        """generatore di immagini grigie 1280x800 (side 'L' o 'R'), UNA per fotogramma scelto; decodifica solo i clip che servono"""
        want = set(int(x) for x in self.sel); pos = 0
        for n, a, b, f in self.tab:
            if not any(a <= w < b for w in want): continue
            p = subprocess.Popen(["ffmpeg", "-v", "error", "-framerate", "15", "-i", f, "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
            k = 0
            while True:
                buf = p.stdout.read(2 * W * H)
                if len(buf) < 2 * W * H: break
                gi = a + k; k += 1
                if gi in want:
                    im = np.frombuffer(buf, np.uint8).reshape(H, 2 * W)
                    yield (im[:, :W] if side == "L" else im[:, W:]).copy()
            p.kill()


def load_cal(path=None):
    path = path or (CAL_NEW if os.path.exists(CAL_NEW) else CAL_OLD)
    d = json.load(open(path))
    return path, d


def make_rect_class(D, path):
    """Rect del logger: stessa interfaccia di D.Rect (Calib.rectify), con spostamento d0 della destra (se il json lo dichiara) e focale di fit per Z = f B / d."""
    path, d = load_cal(path); d0 = float(d.get("d0_px", 0.0)); ff = d.get("focal_fit_px")
    orig = D.Rect

    class RectLogger(orig):
        def __init__(self):
            super().__init__(calib=path)
            if ff: self.f = float(ff)
            self.r["baseline_m"] = 0.200; self.d0 = d0
            self.M = np.float32([[1, 0, d0], [0, 1, 0]])

        def __call__(self, Lraw, Rraw):
            L, R = super().__call__(Lraw, Rraw)
            if self.d0: R = cv2.warpAffine(R, self.M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            return L, R
    return RectLogger, path, d
