"""Hardware FINTO per la prova a secco sul Mac: rilegge i CSV del sensor_hub di #001 (50 Hz) o simula una bici.
Non importa lgpio. Il controllo non sa di girare in simulazione."""
import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .fonti import Campione, G

COLONNE = ["t_ms", "wall", "imu_ax_g", "imu_ay_g", "imu_az_g", "imu_gx_dps", "imu_gy_dps", "imu_gz_dps", "enc_t_ms",
           "enc_wheel_cum", "servo_ma", "gps_t_ms", "gps_fix", "gps_speed_ms"]


class ServoFinto:
    """Backend servo: registra impulsi e rilasci (con l'istante) invece di toccare GPIO."""

    def __init__(self):
        self.t = 0.0
        self.eventi = []           # (t, 'pwm'|'free', angolo)
        self.angolo = 0.0
        self.pin_libero = True

    def pwm(self, angolo):
        self.angolo = angolo
        self.pin_libero = False
        self.eventi.append((self.t, "pwm", angolo))

    def libera(self):
        self.pin_libero = True
        self.eventi.append((self.t, "free", self.angolo))


@dataclass
class Guasti:
    """Intervalli [t0,t1) (secondi dall'inizio) in cui una fonte viene tolta o falsata."""
    enc_stacca: Optional[tuple] = None        # encoder: nessun dato nuovo
    enc_bloccato_zero: Optional[tuple] = None # encoder: dati nuovi ma il contatore non si muove
    gps_senza_fix: Optional[tuple] = None
    imu_morta: Optional[tuple] = None
    ina_stallo: Optional[tuple] = None        # (t0,t1,ma)
    ble_da_v: Optional[tuple] = None          # (t0,t1) BLE disponibile = velocita' vera con rumore, 1 Hz

    @staticmethod
    def _in(iv, t):
        return iv is not None and iv[0] <= t < iv[1]


def carica_csv(path):
    import pandas as pd
    d = pd.read_csv(path, low_memory=False, usecols=lambda c: c in COLONNE)
    if "enc_wheel_cum" not in d or d.enc_wheel_cum.notna().sum() < 100:
        return None
    return d


def campioni_da_csv(d, guasti: Optional[Guasti] = None, i0=0, i1=None, t_zero=None):
    """Generatore di Campione dalle righe del sensor_hub. Il tempo e' t_ms/1000."""
    g = guasti or Guasti()
    t_ms = d.t_ms.values.astype(float)
    te = d.enc_t_ms.values.astype(float)
    cum = d.enc_wheel_cum.values.astype(float)
    imu = d[["imu_ax_g", "imu_ay_g", "imu_az_g", "imu_gx_dps", "imu_gy_dps", "imu_gz_dps"]].values.astype(float)
    ma = d.servo_ma.values.astype(float)
    gt = d.gps_t_ms.values.astype(float)
    gf = d.gps_fix.values.astype(float)
    gs = d.gps_speed_ms.values.astype(float)
    i1 = len(d) if i1 is None else i1
    z = t_ms[i0] / 1000.0 if t_zero is None else t_zero
    ult_te = np.nan
    ult_gt = np.nan
    cum_blocco = None
    for i in range(i0, i1):
        t = t_ms[i] / 1000.0
        ts = t - z
        enc = None
        if not np.isnan(te[i]) and not np.isnan(cum[i]) and te[i] != ult_te:
            ult_te = te[i]
            c = cum[i]
            if Guasti._in(g.enc_bloccato_zero, ts):
                cum_blocco = c if cum_blocco is None else cum_blocco
                c = cum_blocco
            else:
                cum_blocco = None
            if not Guasti._in(g.enc_stacca, ts):
                enc = (te[i] / 1000.0, int(c))
        im = None
        if not np.isnan(imu[i, 1]) and not Guasti._in(g.imu_morta, ts):
            im = tuple(imu[i])
        gp = None
        if not np.isnan(gt[i]) and gt[i] != ult_gt:
            ult_gt = gt[i]
            fix = (gf[i] == 1.0) and not np.isnan(gs[i]) and not Guasti._in(g.gps_senza_fix, ts)
            gp = (float(gs[i]) if fix else 0.0, bool(fix))
        m = None if np.isnan(ma[i]) else float(ma[i])
        if Guasti._in(g.ina_stallo, ts):
            m = g.ina_stallo[2]
        yield Campione(t=t, enc=enc, imu=im, gps=gp, ina_ma=m)


class SimBici:
    """Bici fisica semplice per le prove SINTETICHE a anello chiuso (discesa che accelera, freno col suo ritardo)."""

    def __init__(self, k_enc, v0_kmh=12.0, pendenza_ms2=0.5, resistenza=0.02, k_dec_per_grado=0.05, zona_morta_deg=4.0,
                 ritardo_s=0.25, imu_scala=1.5, seed=1, imu_rumore_g=0.02, a_nat_fn=None, t0=0.0, jitter_s=0.0):
        self.k_enc = k_enc
        self.jitter_s = jitter_s            # jitter dell'istante di campionamento dell'encoder (t dato = t vero: lo stimatore usa i t veri)
        self.a_nat_fn = a_nat_fn
        self.t0 = t0
        self.v = v0_kmh / 3.6
        self.x = 0.0
        self.pend = pendenza_ms2
        self.res = resistenza
        self.kd = k_dec_per_grado
        self.zm = zona_morta_deg
        self.rit = ritardo_s
        self.ang_eff = 0.0
        self.a_vera = 0.0
        self.imu_scala = imu_scala
        self.rnd = random.Random(seed)
        self.rum = imu_rumore_g
        self.cum_f = 0.0
        self.t = 0.0
        self.t_gps = 0.0
        self.t_ble = 0.0
        self.v_hist = []

    def passo(self, dt, ang_cmd):
        self.ang_eff += (ang_cmd - self.ang_eff) * min(1.0, dt / self.rit)
        frenata = self.kd * max(0.0, self.ang_eff - self.zm)
        if self.a_nat_fn is not None:
            self.a_vera = self.a_nat_fn(self.t0 + self.t) - frenata
        else:
            self.a_vera = self.pend - self.res * self.v - frenata
        self.v = max(0.0, self.v + self.a_vera * dt)
        self.x += self.v * dt
        self.cum_f += self.v * dt / self.k_enc
        self.t += dt
        self.v_hist.append(self.v)

    def campione(self, ancora=None, ritardo_gps_s=0.25):
        r = self.rnd
        a = self.a_vera
        sc = self.imu_scala if a < 0 else 1.0
        ay = 0.043 - a * sc / G + r.gauss(0, self.rum)
        vib = 0.1 if self.v > 0.5 else 0.002           # in moto l'IMU vibra (std az ~0.05-0.17 g), ferma no
        imu = (0.0, ay, 0.92 + r.gauss(0, vib), 0.0, r.gauss(0, 0.3), r.gauss(0, 0.3))
        imu = (imu[0], imu[1], imu[2], -2.64 + r.gauss(0, 0.5), imu[4], imu[5])
        gps = ble = None
        if self.t - self.t_gps >= 0.1:
            self.t_gps = self.t
            k = min(len(self.v_hist) - 1, int(ritardo_gps_s / 0.02))
            gps = (max(0.0, self.v_hist[-1 - k] + r.gauss(0, 0.1)), True)
        if self.t - self.t_ble >= 1.0:
            self.t_ble = self.t
            ble = max(0.0, self.v_hist[-1] + r.gauss(0, 0.1))
        dj = max(-2 * self.jitter_s, min(2 * self.jitter_s, r.gauss(0, self.jitter_s))) if self.jitter_s else 0.0
        return Campione(t=self.t, enc=(self.t + dj, int(self.cum_f + self.v * dj / self.k_enc)), imu=imu, gps=gps, ble=ble, ina_ma=27.0)


def esegui_sintetico(ctl, servo, bici, durata_s, guasti: Optional[Guasti] = None, dt=0.02, impuntate=(), dt_imp=0.4):
    """Anello chiuso: bici -> sensori -> ctl.passo -> servo finto -> bici. Ritorna lista di record (dict)."""
    g = guasti or Guasti()
    out = []
    n = int(durata_s / dt)
    for _ in range(n):
        servo.t = bici.t
        c = bici.campione()
        ts = bici.t
        if Guasti._in(g.enc_stacca, ts):
            c.enc = None
        if Guasti._in(g.enc_bloccato_zero, ts):
            c.enc = (bici.t, 0)
        if Guasti._in(g.gps_senza_fix, ts):
            c.gps = (0.0, False) if c.gps is not None else None
        if Guasti._in(g.imu_morta, ts):
            c.imu = None
        if g.ble_da_v is not None and not Guasti._in(g.ble_da_v, ts):
            c.ble = None
        elif g.ble_da_v is None:
            c.ble = None
        if Guasti._in(g.ina_stallo, ts):
            c.ina_ma = g.ina_stallo[2]
        for ti in impuntate:       # muso giu': decel IMU ~4.5 m/s2 e beccheggio +20 dps per dt_imp secondi
            if ti <= ts < ti + dt_imp and c.imu is not None:
                im = list(c.imu)
                im[1] += 4.5 / G
                im[3] += 20.0
                c.imu = tuple(im)
        r = ctl.passo(c)
        r["v_vera"] = bici.v
        r["a_vera"] = bici.a_vera
        r["ang_servo"] = servo.angolo
        out.append(r)
        bici.passo(dt, servo.angolo)
    return out
