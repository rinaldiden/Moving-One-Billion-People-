import copy,numpy as np,sys
sys.path.insert(0,'.')
from speed_limiter_v3.controllo import carica_soglie
from speed_limiter_v3.scenari import nuovo, comando_liscio
from speed_limiter_v3.sim import esegui_sintetico
base=carica_soglie()
def var(cfg,**kv):
    c=copy.deepcopy(cfg)
    for k,v in kv.items():
        a,b=k.split('__');c[a][b]=v
    return c
CAND={'attuale':base,
 'calmo':var(base,regolatore__a_filtro_s=0.5,freno__k_anello_deg_s_per_ms2=6.0,regolatore__banda_morta_ms2=0.15,freno__rampa_su_sopra_vmax_deg_s=10.0,freno__rampa_giu_deg_s=12.0),
 'calmo_k8':var(base,regolatore__a_filtro_s=0.4,freno__k_anello_deg_s_per_ms2=8.0,regolatore__banda_morta_ms2=0.15,freno__rampa_su_sopra_vmax_deg_s=8.0,freno__rampa_giu_deg_s=10.0)}
def gira(cfg,kd,pend,v0,seed):
    rng=np.random.default_rng(seed);ph=rng.uniform(0,6.28,3);f=rng.uniform(0.8,2.0,3)
    fn=lambda t: pend+sum(0.25*np.sin(6.28*f[i]*t+ph[i]) for i in range(3))   # pedalate/buche ~0.4 m/s2 rms
    cfg_,s,ctl,b=nuovo(cfg,k_dec_per_grado=kd,zona_morta_deg=2.0,v0_kmh=v0,seed=seed,a_nat_fn=fn)
    r=esegui_sintetico(ctl,s,b,60)
    sl,inv=comando_liscio(r);v=np.array([x['v_vera'] for x in r])*3.6;ang=np.array([x['angolo'] for x in r]);a=np.array([x['a_vera'] for x in r])
    return inv,sl,v[-1500:].max(),v[-1500:].mean(),ang.max(),len([e for e in s.eventi if e[1]=='pwm'])/60,np.abs(np.diff(ang)).sum()/60,(-a).max()
for kd in (0.1,0.3):
  for pend,v0,lab in [(0.8,13.0,'discesa'),(0.3,17.0,'arrivo 17'),(0.15,14.0,'quasi piano')]:
    for nome,cfg in CAND.items():
        m=np.array([gira(cfg,kd,pend,v0,s) for s in range(4)]).mean(0)
        print(f'freno {kd:.1f} {lab:11s} {nome:9s} invers/min {m[0]:4.1f} | gradi percorsi/s {m[6]:4.1f} | impulsi/s {m[5]:4.1f} | v max {m[2]:5.1f} media {m[3]:5.1f} | ang max {m[4]:4.1f} | decel max {m[7]:4.2f}')
