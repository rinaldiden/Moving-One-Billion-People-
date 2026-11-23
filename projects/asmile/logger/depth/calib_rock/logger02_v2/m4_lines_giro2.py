"""Estrae pezzi rettilinei (l1_lines.pieces) dai fotogrammi A della sessione 1 del giro2 -> $L02W/lines.pkl (stesso formato di l1_lines), poi si lancia v1_vp / l2_plumb.
Decodifica solo i fotogrammi scelti (ffmpeg select), 2 processi.   uso: L02W=.. L02_GIRO=.. L02_CALIB=.. python3 -m logger02_v2.m4_lines_giro2 [passo_s=3] [t0=150]"""
import os,sys,pickle,collections,numpy as np
from multiprocessing import Pool
sys.path.insert(0,os.path.dirname(__file__))
from m1_extract_lr import pairs_per_session,decode
from l1_lines import pieces
def work(a):
    clip,lst=a;V=decode(clip,[i for i,_ in lst]);out=[]
    for i,t in lst:
        im=V[i]
        if im.mean()<25 or im.mean()>235: continue
        for p in pieces(im): out.append((t,'A',p))
    return out
if __name__=='__main__':
    step=float(sys.argv[1]) if len(sys.argv)>1 else 3.0;t0=float(sys.argv[2]) if len(sys.argv)>2 else 150.0
    P=[p for p in pairs_per_session(os.environ['L02_GIRO']) if p['sess']==0];T=np.array([p['t'] for p in P]);g=collections.OrderedDict()
    for t in np.arange(t0,T.max()-1,step):
        k=int(np.argmin(abs(T-t)));g.setdefault(P[k]['a'][0],[]).append((P[k]['a'][1],float(T[k])))
    with Pool(2) as pool: out=[x for o in pool.map(work,list(g.items())) for x in o]
    print(len(out),'pezzi');pickle.dump(out,open(os.path.join(os.environ['L02W'],'lines.pkl'),'wb'))
