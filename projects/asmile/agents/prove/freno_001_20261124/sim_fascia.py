"""Prima/dopo: freno sull'ENCODER con stimatore a pettine + contatto APPRESO. Da projects/asmile:
python3 agents/prove/freno_001_20261124/sim_fascia.py
prima = Regolatore anello-accelerazione del main (freno_prima.py) + parabola 0.3 s. dopo = codice attuale.
Sim: pedalate 2.5 Hz +-0.7 m/s2 + 1 Hz +-0.3, jitter t encoder 3 ms, zona morta del freno = contatto VERO (5/8/12 gradi, mai dato al regolatore)."""
import importlib.util, os, sys
import numpy as np
sys.path.insert(0, 'pi/autonomous')
from speed_limiter_v3 import controllo, fonti
from speed_limiter_v3.controllo import carica_soglie
from speed_limiter_v3.scenari import nuovo, comando_liscio, profilo_pedalate
from speed_limiter_v3.sim import esegui_sintetico
QUI = os.path.dirname(os.path.abspath(__file__))
sp = importlib.util.spec_from_file_location('speed_limiter_v3.freno_prima', os.path.join(QUI, 'freno_prima.py'))
prima = importlib.util.module_from_spec(sp); sp.loader.exec_module(prima)
class Vecchio(prima.Regolatore):
    rate_su = rate_giu = None; fase = '-'; contatto = None; a_nat = None; appreso_ora = False; fonte = 'ENC'
    def __init__(self, cfg, c0=None, n0=0): super().__init__(cfg)
NUOVO = controllo.Regolatore
cfg = carica_soglie()
_pett = fonti.Encoder._pettine

def gira(reg, kd, zm, pend, v0, seed, dur=64, pettine=True, riall=None):
    controllo.Regolatore = reg
    fonti.Encoder._pettine = _pett if pettine else (lambda self, te: None)
    cfg_, s, ctl, b = nuovo(cfg, k_dec_per_grado=kd, zona_morta_deg=zm, v0_kmh=10.0, seed=seed, a_nat_fn=profilo_pedalate(pend, seed, rialzo=riall), jitter_s=0.003)
    r = esegui_sintetico(ctl, s, b, dur)[200:]; dur -= 4      # fuori i 4 s di rullaggio
    sl, inv = comando_liscio(r)
    v = np.array([x['v_vera'] for x in r])*3.6; ang = np.array([x['angolo'] for x in r]); a = np.array([x['a_vera'] for x in r])
    return [inv/(dur/60), np.abs(np.diff(ang)).sum()/dur, len([e for e in s.eventi if e[1]=='pwm'])/dur, v[:500].max(), v[250:].max(),
            v[250:].mean(), ang.max(), (-a).max(), kd*np.abs(np.diff(np.maximum(0, ang-zm))).max()/0.02,
            (ctl.reg.contatto - zm) if ctl.reg.contatto is not None else np.nan, comando_liscio(r[500:])[1] / ((len(r) - 500) * 0.02 / 60)]

if __name__ == '__main__':
    print('| contatto vero | freno | scenario | regolatore | inv/min | gradi/s | impulsi/s | v max 0-10s | v max dopo | v media | ang max | decel max | jerk freno | errore contatto appreso (gradi) | inv/min a regime (dopo 20 s) |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for zm in (5.0, 8.0, 12.0):
        for kd in (0.1, 0.2, 0.3):
            for pend, riall, lab in [(1.2, None, 'discesa ripida'), (0.8, None, 'discesa forte'), (0.3, (2.0, 1.4), 'arrivo a 17'), (0.15, None, 'quasi piano')]:
                for nome, reg, pet in (('prima', Vecchio, False), ('dopo', NUOVO, True)):
                    m = np.nanmean(np.array([gira(reg, kd, zm, pend, 0, s, pettine=pet, riall=riall) for s in range(3)]), 0)
                    err = '%.1f' % m[9] if nome == 'dopo' else '-'
                    print(f'| {zm:.0f} | {kd} | {lab} | {nome} | {m[0]:.1f} | {m[1]:.1f} | {m[2]:.1f} | {m[3]:.1f} | {m[4]:.1f} | {m[5]:.1f} | {m[6]:.0f} | {m[7]:.2f} | {m[8]:.1f} | {err} | {m[10]:.1f} |')
