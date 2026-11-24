"""Stimatore velocita'/decel dall'encoder: parabola 0.3 s (prima) vs pettine su una spinta di pedale (dopo).
Da projects/asmile: python3 agents/prove/freno_001_20261124/misura_stimatore.py
1) dati veri sensors_1440_1505.csv: rumore residuo dell'accelerazione in moto 8-16 km/h (std, potenza 2-5 Hz = pedalate)
2) sintetico con verita' nota (pedalate 2.5 Hz +-0.7 m/s2 + 1 Hz + jitter t): errore rms e ritardo di un gradino di decel."""
import os, sys
import numpy as np
sys.path.insert(0, 'pi/autonomous')
from speed_limiter_v3.controllo import carica_soglie
from speed_limiter_v3.fonti import Encoder
QUI = os.path.dirname(os.path.abspath(__file__))
cfg = carica_soglie(); K = cfg['encoder']['m_per_count']

def corri(te, cum):
    e = Encoder(cfg['encoder']); out = []
    for i in range(len(te)):
        e.aggiorna(te[i], (te[i], int(cum[i])))
        out.append((te[i], e.v_par, e.a_par, e.v if e.pettine else np.nan, e.a if e.pettine else np.nan, e.T))
    return np.array(out)

def banda(t, x, f0, f1):
    tt = np.arange(t[0], t[-1], 0.02); xx = np.interp(tt, t, x); xx = xx - xx.mean()
    F = np.abs(np.fft.rfft(xx * np.hanning(len(xx))))**2; fr = np.fft.rfftfreq(len(xx), 0.02)
    return F[(fr >= f0) & (fr < f1)].sum()

def vero():
    import pandas as pd
    d = pd.read_csv(os.path.join(QUI, 'sensors_1440_1505.csv'), usecols=['enc_t_ms', 'enc_wheel_cum'], low_memory=False)
    d = d.dropna().drop_duplicates('enc_t_ms'); te = d.enc_t_ms.values / 1000; cum = d.enc_wheel_cum.values
    o = corri(te, cum)
    # segmenti continui in moto 8-16 km/h (dalla v del pettine)
    ok = (o[:, 3] > 8/3.6) & (o[:, 3] < 16/3.6)
    idx = np.where(ok)[0]; segs = np.split(idx, np.where(np.diff(idx) > 5)[0] + 1)
    segs = [s for s in segs if len(s) > 150]
    A_par, A_pet, Bp, Bq, Tn = [], [], [0, 0], [0, 0], []
    for s in segs:
        t = o[s, 0]
        A_par.append(o[s, 2] - np.convolve(o[s, 2], np.ones(75)/75, 'same'))     # fuori dal trend lento (1.5 s)
        A_pet.append(o[s, 4] - np.convolve(o[s, 4], np.ones(75)/75, 'same'))
        Bp[0] += banda(t, o[s, 2], 2, 5); Bq[0] += banda(t, o[s, 4], 2, 5); Tn += list(o[s, 5])
    n = sum(len(s) for s in segs)
    print('DATI VERI: %d segmenti, %.0f s in moto 8-16 km/h, T pedale mediano %.2f s (p5-p95 %.2f-%.2f), dt encoder p5/p50/p95 %s ms' % (
        len(segs), n*0.021, np.median(Tn), *np.percentile(Tn, [5, 95]), np.round(np.percentile(np.diff(te), [5, 50, 95])*1000)))
    a1 = np.concatenate(A_par); a2 = np.concatenate(A_pet)
    print('| accel residuo std m/s2 | parabola 0.3 s | pettine |\n|---|---|---|\n| std | %.3f | %.3f |\n| potenza 2-5 Hz (relativa) | 1.00 | %.3f |' % (a1.std(), a2.std(), Bq[0]/Bp[0]))

def sintetico(seed=0, ped=1.0):
    rng = np.random.default_rng(seed); dt = 0.021
    te = np.cumsum(np.maximum(0.012, dt + rng.normal(0, 0.003, 4000))); te -= te[0]
    f1 = 2.5; ph = rng.uniform(0, 6.28, 2)
    # v vera: 12 km/h costante, gradino di decel -1.0 m/s2 a t=30 s fino a t=33; pedalate sovrapposte
    def a_vera(t):
        return -1.0 * ((t >= 30) & (t < 33)) + ped*(0.7*np.sin(2*np.pi*f1*t+ph[0]) + 0.3*np.sin(2*np.pi*1.0*t+ph[1]))
    tt = np.arange(0, te[-1]+0.1, 0.001); av = a_vera(tt); vv = 3.33 + np.cumsum(av)*0.001
    vv -= 0.7/(2*np.pi*f1)*0   # (offset irrilevante)
    ss = np.cumsum(vv)*0.001; s = np.interp(te, tt, ss); cum = np.round(s / K)
    o = corri(te, cum); vt = np.interp(te, tt, vv); at = np.interp(te, tt, -1.0*((tt >= 30) & (tt < 33)))
    m = te > 8
    r = {}
    for nome, c in (('parabola', 2), ('pettine', 4)):
        pre = (te > 8) & (te < 29) & ~np.isnan(o[:, c])
        w = (te > 29.0) & (te < 32.5); idx = np.where(o[w, c] < -0.5)[0]
        r[nome] = (np.nanstd(o[pre, c]), (te[w][idx[0]] - 30) if len(idx) else float('nan'))
    return r
def sint_tab():
    rp = sintetico(ped=1.0); r0 = sintetico(ped=0.0)
    print('SINTETICO (verita\' nota; pedalate 2.5 Hz +-0.7 + 1 Hz +-0.3, jitter t 3 ms; ritardo = tempo a -0.5 m/s2 sul gradino -1.0 senza pedalate):')
    print('| | parabola | pettine |\n|---|---|---|\n| accel std a regime con pedalate | %.3f | %.3f |\n| ritardo gradino (s) | %.2f | %.2f |' % (
        rp['parabola'][0], rp['pettine'][0], r0['parabola'][1], r0['pettine'][1]))
if __name__ == '__main__':
    vero(); sint_tab()
