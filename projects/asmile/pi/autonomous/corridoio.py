#!/usr/bin/env python3
"""
corridoio.py — il corridoio della bici: LARGO COME LA BICI, proiettato dove la bici sta andando.
Modulo UNICO per bordo (shadow mode sul Pi) e Mac (video, replay). Solo numpy/json/math, CAUSALE (filtri IIR del primo ordine, mai fase zero),
costo di un aggiornamento: vedi rapporto (decine di microsecondi). Daniele 2026-11-13.

INPUT per ogni istante:  update(t, steer_raw, v, gz, vis=None)
  t          secondi (monotonic; nel sensor_hub t_ms/1000, stesso orologio dei fotogrammi)
  steer_raw  conteggi grezzi encoder sterzo AMT22 (14 bit); centro e verso dalla calib PER UNITA' (steering_limits_<unita>.json), mai fallback fra unita'
  v          velocita' encoder ruota, m/s (>=0)
  gz         giroscopio IMU, dps (gz negativo = imbardata a destra); il bias e' stimato IN LINEA a bici ferma
  vis        opzionale, dict {"k": 1/m, "heading_rad": rad, "offset_m": m, "peso": 0..1}: percorso visto da bordi strada / flusso ottico.
             Assente o peso 0 = non usato. Il peso e' limitato da vis_peso_max (tabella parametri).
FUSIONE curvatura k [1/m, + = destra]:  k = w*k_imu + (1-w)*k_sterzo, poi con visione  k = (1-p)*k + p*k_vis.
  k_sterzo = tan(rapporto_ruota_colonna * angolo_colonna)/passo (cinematica Ackermann, passo 1.15 m; vale anche da fermo); k_imu = imbardata/v, peso w crescente fra v_imu_lo e v_imu_hi.
LATENZA dichiarata: stato["latenza_s"] = ritardo di gruppo dei filtri (w*tau_yaw + (1-w)*tau_sterzo).
PROIEZIONE: curvatura decrescente k(s)=k0 exp(-s/L) fino all'orizzonte = rallenta_entro della tabella soglie alla velocita' attuale.
LARGHEZZA = 1.10 m (geometria #001 = larghezza_asmile_m della tabella, controllo di coerenza) (config/soglie_attuazione_<unita>.json), centrata sul percorso. L'incertezza della previsione e'
restituita A PARTE (incertezza(Z), fascia per Z), mai sommata alla larghezza.
Il corridoio parte dalla PUNTA DEL MUSO (0.30 m davanti alla camera): orizzonte e Z sono dalla camera, distanza_da_punta(Z) = Z - muso.
Tutti i numeri: tabella soglie + config/corridoio_<unita>.json + calib sterzo. Nessuna soglia nel codice.
Sistema di riferimento: Z = avanti (orizzontale), X = laterale, + destra, origine = centro bici.
"""
import os
import sys
import json
import math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CONFIG_DIR = os.path.join(ROOT, "config")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from soglie import Soglie  # noqa: E402

CAMPI_LOG = ["corr_k", "corr_k_sterzo", "corr_k_imu", "corr_w_sterzo", "corr_w_imu", "corr_w_vis", "corr_larghezza_m",
             "corr_orizzonte_m", "corr_sigma_orizzonte_m", "corr_sigma_5m", "corr_latenza_s", "corr_bias_gz_dps", "corr_v_ms"]


def _nome(unita):
    return unita.replace("asmile-", "")


def _carica_calib(unita, path=None):
    """Calib sterzo DELLA SUA unita'. Cerca /data/steering_limits_<unita>.json (Pi) poi fleet/<nome>/data/ (repo). Unita' diversa nel file = errore."""
    cand = [path] if path else [f"/data/steering_limits_{unita}.json",
                                os.path.join(ROOT, "fleet", _nome(unita), "data", f"steering_limits_{unita}.json")]
    for p in cand:
        if p and os.path.exists(p):
            d = json.load(open(p))
            if d.get("unit") != unita:
                raise ValueError(f"calib {p} e' di {d.get('unit')}, non di {unita}: nessun fallback fra unita'")
            return d, p
    raise FileNotFoundError(f"calib sterzo di {unita} non trovata ({cand})")


class VelRuota:
    """Velocita' CAUSALE dai conteggi cumulativi ruota (sensor_hub enc_wheel_cum): differenza all'indietro su finestra_s."""
    def __init__(self, m_per_count, finestra_s=0.2):
        self.m = m_per_count; self.w = finestra_s; self.buf = []

    def update(self, t, cum):
        self.buf.append((t, cum))
        while len(self.buf) > 2 and self.buf[1][0] <= t - self.w:
            self.buf.pop(0)
        t0, c0 = self.buf[0]
        return abs(cum - c0) * self.m / (t - t0) if t > t0 else 0.0


class Corridoio:
    def __init__(self, unita="asmile-001", calib=None, calib_path=None, params=None, soglie=None):
        self.unita = unita
        if calib is None:
            calib, self.calib_path = _carica_calib(unita, calib_path)
        else:
            self.calib_path = "(dict)"
            if calib.get("unit") != unita:
                raise ValueError(f"calib di {calib.get('unit')} per l'unita' {unita}: no")
        if "DX" not in str(calib.get("encoder_pos_increases_to", "")).upper() and "SX" not in str(calib.get("encoder_pos_increases_to", "")).upper():
            raise ValueError("calib senza verso encoder (encoder_pos_increases_to)")
        self.calib = calib
        self.centro = int(calib["encoder_center_raw"]); self.deg_step = float(calib["deg_per_step"])
        self.verso = 1.0 if "DX" in calib["encoder_pos_increases_to"].upper() else -1.0
        self.bits = int(calib.get("encoder_bits", 14)); self.giro = 1 << self.bits
        if params is None:
            params = json.load(open(os.path.join(CONFIG_DIR, f"corridoio_{_nome(unita)}.json")))
        self.par = {k: v for k, v in params["parametri"].items() if not k.startswith("_")}
        self.sig_z = np.asarray(params["incertezza_laterale"]["z_m"], float); self.sig_m = np.asarray(params["incertezza_laterale"]["sigma_m"], float)
        self.sog = soglie or Soglie(unita)
        self.geo = params["geometria"]       # misure di #001 copiate da follow_me/asmile_config.yaml (sezione asmile) + docs/ackermann_calc.py; test_corridoio verifica che coincidano
        self.hw = self.geo["larghezza_max_cm"] / 200.0                       # semi-larghezza = larghezza esterna mozzi ruote anteriori / 2
        if abs(2 * self.hw - self.sog.p["larghezza_asmile_m"]) > 0.005:
            raise ValueError("larghezza della geometria diversa da larghezza_asmile_m della tabella soglie: una sola verita'")
        self.muso = self.geo["sporgenza_muso_cm"] / 100.0                    # camera -> punta del muso: il corridoio parte da qui
        self.passo = self.geo["passo_mm"] / 1000.0
        self.h_cam = self.geo["altezza_cam_da_terra_cm"] / 100.0
        self.x_cam = self.geo.get("x_camera_rif_rispetto_asse_m", 0.0)       # posizione laterale della camera di riferimento rispetto all'asse bici (+ destra)
        delta_max = max(abs(calib.get("delta_dx_deg", 45.0)), abs(calib.get("delta_sx_deg", 45.0)))
        self.k_max = math.tan(math.radians(self.par["rapporto_ruota_colonna"] * delta_max)) / self.passo
        self.reset()

    def reset(self):
        p = self.par
        self.t = None; self.steer_f = 0.0; self.yaw_f = 0.0; self.v_f = 0.0; self.bias = p["bias_gz_iniziale_dps"]; self.t_ferma = 0.0
        self.k = 0.0; self.k_st = 0.0; self.k_imu = 0.0; self.w_imu = 0.0; self.w_vis = 0.0; self.psi0 = 0.0; self.x0 = 0.0
        self.latenza = p["tau_sterzo_s"]; self.orizzonte = 0.0; self._cache = None; self.steer_deg = 0.0

    # ------------------------------------------------------------------ aggiornamento
    def angolo_sterzo(self, steer_raw):
        d = (int(steer_raw) - self.centro + self.giro // 2) % self.giro - self.giro // 2
        return self.verso * d * self.deg_step      # gradi, + destra

    def update(self, t, steer_raw, v, gz, vis=None):
        p = self.par
        deg = self.angolo_sterzo(steer_raw); v = max(0.0, float(v))
        if self.t is None:
            self.steer_f, self.v_f, self.yaw_f = deg, v, 0.0; dt = 0.0
        else:
            dt = min(max(t - self.t, 0.0), 0.5)
        self.t = t
        al = lambda tau: 1.0 - math.exp(-dt / tau) if dt > 0 else 1.0
        self.steer_f += al(p["tau_sterzo_s"]) * (deg - self.steer_f); self.v_f += al(p["tau_v_s"]) * (v - self.v_f)
        # bias del giroscopio: solo a bici ferma da almeno t_fermo_bias_s e senza rotazioni vere
        if v < p["v_fermo_ms"]:
            self.t_ferma += dt
            if self.t_ferma >= p["t_fermo_bias_s"] and abs(gz - self.bias) < p["gz_max_bias_dps"]:
                self.bias += al(p["tau_bias_s"]) * (gz - self.bias)
        else:
            self.t_ferma = 0.0
        yaw = p["gz_segno"] * (gz - self.bias)       # dps, + destra
        self.yaw_f += al(p["tau_yaw_s"]) * (yaw - self.yaw_f)
        self.steer_deg = self.steer_f
        self.k_st = math.tan(math.radians(p["rapporto_ruota_colonna"] * self.steer_f)) / self.passo   # cinematica: angolo ruota = rapporto * angolo colonna, k = tan(delta)/passo
        self.k_imu = math.radians(self.yaw_f) / max(self.v_f, p["v_min_k_ms"])
        self.w_imu = p["peso_imu_max"] * min(max((self.v_f - p["v_imu_lo_ms"]) / (p["v_imu_hi_ms"] - p["v_imu_lo_ms"]), 0.0), 1.0)
        k = self.w_imu * self.k_imu + (1.0 - self.w_imu) * self.k_st
        self.w_vis = 0.0; self.psi0 = 0.0; self.x0 = 0.0
        if vis:
            pv = min(max(float(vis.get("peso", 0.0)), 0.0), p["vis_peso_max"])
            if pv > 0:
                self.w_vis = pv
                if vis.get("k") is not None:
                    k = (1.0 - pv) * k + pv * float(vis["k"])
                if vis.get("heading_rad") is not None:
                    self.psi0 = pv * float(vis["heading_rad"])
                if vis.get("offset_m") is not None:
                    self.x0 = pv * float(vis["offset_m"])
        self.k = min(max(k, -self.k_max), self.k_max)
        self.latenza = self.w_imu * p["tau_yaw_s"] + (1.0 - self.w_imu) * p["tau_sterzo_s"]
        self.orizzonte = self.muso + self.sog.a(max(self.v_f, p["v_min_orizzonte_ms"]))["rallenta_entro_m"]   # rallenta_entro e' dalla punta del muso; Z e' dalla camera
        self._cache = None
        return self.stato()

    # ------------------------------------------------------------------ percorso e geometria
    def percorso(self, zmax=None):
        """(z, x) del centro del percorso: z in avanti (m), x laterale (+ destra), curvatura k0 exp(-s/L), fino a zmax (default orizzonte)."""
        zm = self.orizzonte if zmax is None else zmax
        if self._cache is not None and self._cache[0] >= zm:
            z, x = self._cache[1], self._cache[2]
            n = int(np.searchsorted(z, zm)) + 2
            return z[:n], x[:n]
        ds = self.par["ds_m"]; L = self.par["L_decadimento_m"]
        n = max(int(zm / ds * 1.1) + 3, 4)
        ss = (np.arange(n) + 0.5) * ds
        psi = np.cumsum(self.k * np.exp(-ss / L)) * ds + self.psi0
        z = np.concatenate([[0.0], np.cumsum(np.cos(psi)) * ds])
        x0 = self.x0 - self.x_cam                  # coordinate camera: asse bici a -x_cam
        x = np.concatenate([[x0], x0 + np.cumsum(np.sin(psi)) * ds])
        self._cache = (z[-1], z, x)
        return z, x

    def x_percorso(self, Z):
        z, x = self.percorso(max(float(np.max(Z)), 1e-3) if np.size(Z) else 1.0)
        return np.interp(Z, z, x)

    def incertezza(self, Z):
        """sigma laterale (m, ~68% degli errori held-out) della previsione del centro percorso alla profondita' Z. A PARTE dalla larghezza."""
        return np.interp(Z, self.sig_z, self.sig_m)

    def dentro(self, X, Z):
        """True se il punto (X, Z) [coordinate camera] sta dentro la sagoma della bici sul percorso (|X - x_percorso(Z)| <= semi-larghezza), fra la punta del muso (Z>=muso: cio' che e' fra camera e muso e' la bici stessa) e l'orizzonte."""
        X = np.asarray(X, float); Z = np.asarray(Z, float)
        return (np.abs(X - self.x_percorso(Z)) <= self.hw) & (Z >= self.muso) & (Z <= self.orizzonte)

    def spazio_laterale(self, X_sx, X_dx, Z):
        """margine libero (m) fra il bordo della sagoma e l'ostacolo/bordo piu' vicino a sinistra (X_sx, negativo) e a destra (X_dx, positivo) alla profondita' Z.
        <0 = il bordo interseca la sagoma. None/nan = nessun ostacolo da quel lato -> inf. Ritorna (margine_sx, margine_dx)."""
        Z = np.asarray(Z, float); xp = self.x_percorso(Z)
        def m(a, f):
            if a is None: return np.full(np.shape(Z), np.inf) if np.ndim(Z) else math.inf
            a = np.asarray(a, float); r = f(a); return np.where(np.isnan(r), np.inf, r)
        sx = m(X_sx, lambda a: (xp - self.hw) - a); dx = m(X_dx, lambda a: a - (xp + self.hw))
        return (sx if np.ndim(sx) else float(sx)), (dx if np.ndim(dx) else float(dx))

    def distanza_da_punta(self, Z):
        """distanza dalla punta del muso (m) di un punto a profondita' Z dalla camera: e' questa che va confrontata con frena_entro / rallenta_entro."""
        return np.asarray(Z, float) - self.muso

    def bordi(self, Z):
        xp = self.x_percorso(Z); return xp - self.hw, xp + self.hw

    def poligono_immagine(self, K, pitch, h_cam=None, z_min=None, n=40, incertezza=False):
        """poligono (N,2) pixel della sagoma sul PIANO STRADA, per disegnarlo: bordo sinistro dal vicino al lontano, poi destro dal lontano al vicino.
        K = matrice 3x3 (rettificata), pitch = inclinazione in giu' (rad), h_cam = altezza camera dal piano (m, default dalla geometria: 82.5 cm). Punti dietro/sopra l'orizzonte scartati.
        incertezza=True: bordi esterni = sagoma +- sigma(Z) (fascia di incertezza, disegnata a parte)."""
        h_cam = self.h_cam if h_cam is None else h_cam; z_min = max(self.muso, 1.0) if z_min is None else z_min
        Zs = np.geomspace(z_min, max(self.orizzonte, z_min * 1.5), n)
        xp = self.x_percorso(Zs); w = self.hw + (self.incertezza(Zs) if incertezza else 0.0)
        pts = []
        for sgn in (-1.0, 1.0):
            X = xp + sgn * w
            zc = Zs * math.cos(pitch) + h_cam * math.sin(pitch); yc = h_cam * math.cos(pitch) - Zs * math.sin(pitch)
            ok = zc > 0.1
            u = K[0, 0] * X / zc + K[0, 2]; vv = K[1, 1] * yc / zc + K[1, 2]
            pts.append(np.stack([u, vv], 1)[ok & (yc > 0)])
        return np.concatenate([pts[0], pts[1][::-1]]) if len(pts[0]) and len(pts[1]) else np.zeros((0, 2))

    # ------------------------------------------------------------------ stato e log
    def stato(self):
        return {"t": self.t, "k": self.k, "k_sterzo": self.k_st, "k_imu": self.k_imu, "angolo_sterzo_deg": self.steer_deg,
                "pesi": {"sterzo": (1 - self.w_imu) * (1 - self.w_vis), "imu": self.w_imu * (1 - self.w_vis), "visione": self.w_vis},
                "larghezza_m": 2 * self.hw, "orizzonte_m": self.orizzonte, "sigma_orizzonte_m": float(self.incertezza(self.orizzonte)),
                "latenza_s": self.latenza, "bias_gz_dps": self.bias, "v_ms": self.v_f}

    def riga_log(self):
        s = self.stato(); return [f"{s['k']:.5f}", f"{s['k_sterzo']:.5f}", f"{s['k_imu']:.5f}", f"{s['pesi']['sterzo']:.3f}", f"{s['pesi']['imu']:.3f}",
                                  f"{s['pesi']['visione']:.3f}", f"{s['larghezza_m']:.3f}", f"{s['orizzonte_m']:.2f}", f"{s['sigma_orizzonte_m']:.3f}",
                                  f"{float(self.incertezza(5.0)):.3f}", f"{s['latenza_s']:.3f}", f"{s['bias_gz_dps']:.3f}", f"{s['v_ms']:.3f}"]
