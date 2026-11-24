"""Scenari sintetici a anello chiuso (bici simulata + controllo vero). Usati da prova_secco.py e dai test."""
import json

import numpy as np

from .controllo import Controllo, carica_soglie
from .sim import Guasti, ServoFinto, SimBici, esegui_sintetico


def nuovo(cfg=None, **kw_bici):
    cfg = cfg or carica_soglie()
    s = ServoFinto()
    ctl = Controllo(cfg, s, log_eventi=lambda *a: ctl.eventi_log.append(a))
    ctl.eventi_log = []
    b = SimBici(cfg["encoder"]["m_per_count"], **kw_bici)
    return cfg, s, ctl, b


def comando_liscio(r):
    """slew max (gradi/s) dell'angolo ESCLUDENDO i cicli di rilascio anti-impuntata, e inversioni >=0.7 gradi."""
    ang = np.array([x["angolo"] for x in r])
    ril = np.array([x["rilascia_ora"] for x in r])
    sl = np.abs(np.diff(ang)) / 0.02
    sl[ril[1:]] = 0.0
    inv, ext, dirr = 0, ang[0], 0
    for x in ang[1:]:
        if dirr >= 0 and x < ext - 0.7:
            inv += dirr == 1
            dirr, ext = -1, x
        elif dirr <= 0 and x > ext + 0.7:
            inv += dirr == -1
            dirr, ext = 1, x
        elif (dirr >= 0 and x > ext) or (dirr <= 0 and x < ext):
            ext = x
    return float(sl.max()), int(inv)


def jerk_decel(r):
    """massimo |d a_misurata/dt| in m/s3 (la decel vera della bici simulata)."""
    a = np.array([x["a_vera"] for x in r])[25:]          # salta il primo mezzo secondo (assestamento della simulazione)
    return float(np.abs(np.diff(a)).max() / 0.02)


def discesa_forte(g=0.05, durata=60, pend=1.2, v0=13.0):
    cfg, s, ctl, b = nuovo(k_dec_per_grado=g, pendenza_ms2=pend, v0_kmh=v0)
    return esegui_sintetico(ctl, s, b, durata), ctl


def con_guasto(guasti, durata=40, g=0.05, pend=0.6, v0=14.0, impuntate=(), cfg=None):
    cfg, s, ctl, b = nuovo(cfg, k_dec_per_grado=g, pendenza_ms2=pend, v0_kmh=v0)
    r = esegui_sintetico(ctl, s, b, durata, guasti, impuntate=impuntate)
    return r, ctl, s


def salto_max_v(r, t0, t1):
    """Massimo salto di v (m/s) fra cicli consecutivi nell'intervallo, solo dove v esiste."""
    v = [(x["t"], x["v"]) for x in r if t0 <= x["t"] < t1 and x["v"] is not None]
    return float(max(abs(b[1] - a[1]) for a, b in zip(v, v[1:]))) if len(v) > 1 else 0.0


def pedalate(pend, seed=0, ampl=0.7, f=2.5):
    """accelerazione naturale a(t) = pendenza + pedalate (f Hz, +-ampl m/s2) + componente a 1 Hz (+-0.3)."""
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 6.2832, 2)
    return lambda t: pend + ampl * np.sin(6.2832 * f * t + ph[0]) + 0.3 * np.sin(6.2832 * 1.0 * t + ph[1])


def profilo_pedalate(pend, seed=0, pre_s=4.0, rialzo=None, ampl=0.7):
    """4 s di rullaggio a freno staccato (a naturale ~0: il regolatore misura la decel naturale) e poi la pendenza `pend`;
    rialzo=(durata_s, a) = tratto iniziale piu' ripido per arrivare 'a 17'. Sempre con le pedalate."""
    ped = pedalate(0.0, seed, ampl)
    def a(t):
        if t < pre_s:
            base = 0.0
        elif rialzo is not None and t < pre_s + rialzo[0]:
            base = rialzo[1]
        else:
            base = pend
        return base + ped(t)
    return a
