#!/usr/bin/env python3
"""ego_001.py — moto proprio di #001 per il video fluido v6 (12/11/2026): velocita' (encoder ruota), imbardata (giroscopio IMU), sterzo (encoder), curvatura.
Verifiche dai dati (094146, v>2 m/s): il giroscopio che segue lo sterzo e' gz (corr -0.952 col sterzo, gx +0.02, gy -0.15), asse Z su (az=+0.92 g):
imbardata a DESTRA = gz NEGATIVO -> yaw_dx = -(gz - bias). Bias gz a bici ferma = 1.75 dps (mediana su tutte le righe v<0.02 del file, 13513+ campioni).
Curvatura k [1/m, + = destra] = yaw_dx[rad/s] / v, media mobile centrata +-0.2 s (offline, zero fase); per v<1.5 m/s (rapporto instabile) = c*sterzo_deg con c
FIT dai dati (k_imu vs sterzo, v>2: c=0.00968 1/m/deg, corr 0.93; il picco di correlazione yaw-sterzo e' a lag 0). Transizione lineare fra v=1.0 e 1.5 m/s.
Velocita': m_per_count 2.1219e-5 (wheel_circum 0.3374 attivo); v_prop = v * 0.3477/0.3374 (+3.05%, PROPOSTA non deployata).
Sterzo: centro 6606, 0.02197 deg/step, + = destra (fleet/001/data/steering_limits_asmile-001.json, validi per i video del 09/11).
"""
import os, csv, json, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
LOGS = os.path.join(ROOT, "asmile-loggers", "asmile-001")
SFILE = os.path.join(LOGS, "_sensors", "sensors", "sensors_20261109_085334.csv")
M_PER_COUNT = 2.1219e-5; PROP = 0.3477 / 0.3374
CENTER, DEG_STEP = 6606, 0.02197
CENTER_1113 = 4112     # centro sterzo dopo il rimontaggio encoder (fleet/001/data/steering_limits_asmile-001.json, 13/11/2026)
def center_for(sess): return CENTER_1113 if sess.replace("session_", "")[:8] >= "20261113" else CENTER
C_STEER = 0.00968


def x_arc(k, Z):
    """spostamento laterale (+ destra) dell'arco di curvatura k [1/m] alla profondita' Z (m, davanti alla bici); cerchio esatto, saturato a |k Z|<0.98"""
    k = np.asarray(k, float); Z = np.asarray(Z, float)
    kz = np.clip(k * Z, -0.98, 0.98)
    with np.errstate(all="ignore"):
        return np.where(np.abs(k) < 1e-6, 0.0, (1 - np.sqrt(1 - kz ** 2)) / k)


L_TAPER = 3.5   # m: lunghezza di decadimento della curvatura lungo il percorso, dai dati (autocorrelazione di k sulla distanza percorsa in 094146: 1.0 a 0 m, 0.61 a 2 m, 0.27 a 4 m, 0.08 a 6 m)


def path_xz(k0, L=L_TAPER, smax=45.0, ds=0.25):
    """percorso previsto con curvatura che decade k(s) = k0 exp(-s/L) (E[k(s)] = k0 rho(s), rho = autocorrelazione misurata): ritorna (z, x) con z = profondita' in avanti, x = spostamento laterale (+ destra).
    Sui dati di 094146 (v>1.5 m/s, 500+ finestre) l'errore laterale vs il percorso reale poi percorso: a 10 m mediana 0.33 m / p90 2.1 m (arco puro k0 costante: 0.52 / 6.06; rettilineo: 0.39 / 2.42);
    a 20 m 1.08 / 6.6 (arco puro 1.93 / 18.5; rettilineo 1.19 / 7.8). Stima sulla stessa sessione del video: NON held-out."""
    ss = np.arange(0, smax, ds) + ds / 2; ks = k0 * np.exp(-ss / L); psi = np.cumsum(ks) * ds
    return np.concatenate([[0.0], np.cumsum(np.cos(psi)) * ds]), np.concatenate([[0.0], np.cumsum(np.sin(psi)) * ds])


def x_path(k0, Z):
    z, x = path_xz(float(k0)); return np.interp(Z, z, x)


class Ego:
    def __init__(self, sess):
        import glob
        self.center = center_for(sess)
        sf = sorted(glob.glob(os.path.join(LOGS, "_sensors", "sensors", "sensors_" + sess.replace("session_", "")[:8] + "_*.csv")))
        SFILE_ = SFILE if sess.replace("session_", "")[:8] == "20261109" else sf[0]
        m = json.load(open(os.path.join(LOGS, sess, "metadata.json")))
        s0 = dt.datetime.fromisoformat(m["start_time"])
        a = s0 - dt.timedelta(seconds=15); b = s0 + dt.timedelta(seconds=float(m["duration_seconds"]) + 15)
        T, C, G, ST, AZ = [], [], [], [], []; allrest = []
        for r in csv.DictReader(open(SFILE_)):
            if not (r["wall"] and r["enc_wheel_cum"] and r["imu_gz_dps"] and r["enc_steer_raw"]): continue
            allrest.append((float(r["t_ms"]), float(r["enc_wheel_cum"]), float(r["imu_gz_dps"])))
            w = dt.datetime.fromisoformat(r["wall"])
            if a <= w <= b:
                T.append(float(r["t_ms"])); C.append(float(r["enc_wheel_cum"])); G.append(float(r["imu_gz_dps"])); ST.append(float(r["enc_steer_raw"]))
        ar = np.array(allrest); sv = (np.interp(ar[:, 0] + 1000, ar[:, 0], ar[:, 1]) - np.interp(ar[:, 0] - 1000, ar[:, 0], ar[:, 1])) * M_PER_COUNT / 2
        self.bias = float(np.median(ar[np.abs(sv) < 0.02, 2]))
        t = np.array(T); s = np.array(C) * M_PER_COUNT; o = np.argsort(t); t, s = t[o], s[o]
        self.t = t; dtm = 0.02
        def vel(w): return (np.interp(t + w * 1000, t, s) - np.interp(t - w * 1000, t, s)) / (2 * w)
        self.v = vel(0.25); self.s = s
        # filtro picchi encoder ruota (13/11): velocita' fuori [-1, 12 m/s = 43 km/h] -> mediana mobile 1 s; si conta quanti campioni
        bad = (self.v > 12.0) | (self.v < -1.0); self.n_spike = int(bad.sum())
        if self.n_spike:
            n_ = 51; vp = np.pad(self.v, n_ // 2, mode="edge"); med = np.array([np.median(vp[i:i + n_]) for i in range(len(self.v))]); self.v = np.where(bad, med, self.v)
        self.v = np.maximum(self.v, 0.0)
        self.yaw_dx = -(np.array(G)[o] - self.bias)              # dps, + destra
        self.steer = (np.array(ST)[o] - self.center) * DEG_STEP        # gradi, + destra
        n = int(round(0.2 / dtm)) * 2 + 1; ker = np.ones(n) / n
        sm = lambda x: np.convolve(np.pad(x, n // 2, mode="edge"), ker, mode="valid")
        self.yaw_s = sm(self.yaw_dx); self.steer_s = sm(self.steer); self.v_s = sm(self.v)
        k_imu = np.radians(self.yaw_s) / np.maximum(self.v_s, 1.0)
        k_st = C_STEER * self.steer_s
        w = np.clip((self.v_s - 1.0) / 0.5, 0, 1)
        self.k_imu, self.k_st = k_imu, k_st; self.k = w * k_imu + (1 - w) * k_st

    def at(self, tms, name):
        return np.interp(tms, self.t, getattr(self, name))
