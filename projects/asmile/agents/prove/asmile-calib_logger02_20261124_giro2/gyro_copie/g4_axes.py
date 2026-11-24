"""Strada 1 - passo 4: scala del giro PER ASSE della camera con f fissata (sf=1): rotazione = exp(diag(s) * rotvec_cam).
L'asse z camera (rollio, attorno all'asse ottico) e' INDIPENDENTE dalla focale: se s_z ~ 1 il giroscopio ha la scala giusta su quell'asse.
Poi: s_x, s_y (beccheggio, imbardata) confondibili con la focale (s ~ f_vera/f_assunta)."""
import os,sys
sys.path.insert(0,os.path.dirname(__file__))
from g2_scan import *
from scipy.optimize import least_squares
Rc=Rc0
def cost_pair(m,s,sf=1.0,rmax=None):
    Rg=integ(X,m['t0'],m['t1'])if '_g' not in m else m['_g']
    m['_g']=Rg
    Rrel=Rc@Rg.T@Rc.T;v=cv2.Rodrigues(Rrel)[0].ravel()*s;R=cv2.Rodrigues(v.reshape(3,1))[0]
    mk=np.ones(len(m['xa']),bool) if rmax is None else (m['r']<rmax)
    if mk.sum()<30: return None
    e=sampson_t(m['xa'][mk],m['xb'][mk],R,sf);return float(np.sqrt(np.mean(np.minimum(e,4.0)**2)))
def fit(Ms,x0,free,rmax=None):
    def f(p):
        s=np.array(x0,float);s[free]=p;v=[cost_pair(m,s,1.0,rmax) for m in Ms];return np.array([x for x in v if x is not None])
    r=least_squares(f,np.array(x0)[free],diff_step=1e-3,x_scale=0.02,max_nfev=30);return r.x,float(np.mean(r.fun**2))
if __name__=='__main__':
    # solo coppie con rotazione nel verso z apprezzabile: tutte, ma i pesi ricadono sull'asse piu' eccitato
    print('rotvec cam, deviazione std per asse (gradi):',np.degrees(np.std([cv2.Rodrigues(Rc@integ(X,m['t0'],m['t1']).T@Rc.T)[0].ravel() for m in M],0)).round(2))
    for name,sub in (('tutte',M),('150-880',[m for m in M if 150<=m['t0']<880]),('alterne A',M[::2]),('alterne B',M[1::2])):
        x,c=fit(sub,[1,1,1],[0,1,2]);print(name,len(sub),'s_x(beccheggio) %.3f s_y(imbardata) %.3f s_z(rollio) %.3f  cost %.3f'%(*x,c))
    rng=np.random.default_rng(1);bs=[]
    for _ in range(25):
        ii=rng.integers(0,len(M),len(M));x,_=fit([M[i] for i in ii],[1,1,1],[0,1,2]);bs.append(x)
    bs=np.array(bs);print('bootstrap sd s_x,s_y,s_z',bs.std(0).round(3),'media',bs.mean(0).round(3))
