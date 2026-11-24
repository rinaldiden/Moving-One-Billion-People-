"""Prima/dopo del Regolatore a fascia di contatto. Da projects/asmile: python3 agents/prove/freno_001_20261124/sim_fascia.py
'prima' = Regolatore anello-accelerazione del HEAD (freno_prima.py); zona morta del freno = angolo_contatto (8), pedalate ~0.4 m/s2."""
import importlib.util, os, sys
import numpy as np
sys.path.insert(0, 'pi/autonomous')
from speed_limiter_v3 import controllo
from speed_limiter_v3.controllo import carica_soglie
from speed_limiter_v3.scenari import nuovo, comando_liscio, jerk_decel
from speed_limiter_v3.sim import esegui_sintetico
QUI = os.path.dirname(os.path.abspath(__file__))
sp = importlib.util.spec_from_file_location('speed_limiter_v3.freno_prima', os.path.join(QUI, 'freno_prima.py'))
prima = importlib.util.module_from_spec(sp); sp.loader.exec_module(prima)
class Vecchio(prima.Regolatore):
    rate_su = rate_giu = None; fase = '-'
NUOVO = controllo.Regolatore
cfg = carica_soglie(); ZM = cfg['freno']['angolo_contatto_deg']

def gira(reg, kd, pend, v0, seed, dur=60):
    controllo.Regolatore = reg
    rng = np.random.default_rng(seed); ph = rng.uniform(0, 6.28, 3); f = rng.uniform(0.8, 2.0, 3)
    fn = lambda t: pend + sum(0.25*np.sin(6.28*f[i]*t+ph[i]) for i in range(3))
    _, s, ctl, b = nuovo(cfg, k_dec_per_grado=kd, zona_morta_deg=ZM, v0_kmh=v0, seed=seed, a_nat_fn=fn)
    r = esegui_sintetico(ctl, s, b, dur)
    sl, inv = comando_liscio(r)
    v = np.array([x['v_vera'] for x in r])*3.6; ang = np.array([x['angolo'] for x in r]); a = np.array([x['a_vera'] for x in r])
    tr = v[:500].max(); vm = v[250:].max()   # transitorio = primi 10 s ; dopo
    return [inv/(dur/60), np.abs(np.diff(ang)).sum()/dur, len([e for e in s.eventi if e[1]=='pwm'])/dur, tr, vm, v[250:].mean(), ang.max(), (-a).max(), kd*np.abs(np.diff(np.maximum(0, ang-ZM))).max()/0.02]

if __name__ == '__main__':
    print('| freno | scenario | regolatore | inv/min | gradi/s | impulsi/s | v max 0-10s | v max dopo | v media | ang max | decel max | jerk freno oltre contatto m/s3 |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|')
    for kd in (0.1, 0.2, 0.3):
        for pend, v0, lab in [(1.2, 13.0, 'discesa ripida'), (0.8, 13.0, 'discesa forte'), (0.3, 17.0, 'arrivo a 17'), (0.15, 14.0, 'quasi piano')]:
            for nome, reg in (('prima', Vecchio), ('dopo', NUOVO)):
                m = np.array([gira(reg, kd, pend, v0, s) for s in range(4)]).mean(0)
                print(f'| {kd} | {lab} | {nome} | {m[0]:.1f} | {m[1]:.1f} | {m[2]:.1f} | {m[3]:.1f} | {m[4]:.1f} | {m[5]:.1f} | {m[6]:.0f} | {m[7]:.2f} | {m[8]:.1f} |')
