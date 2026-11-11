import csv,sys,os,numpy as np
for f in sorted(sys.argv[1:]):
    R=list(csv.DictReader(open(f))); t=np.array([float(r['t']) for r in R]); p=np.array([int(r['pos']) for r in R]); vs=np.array([float(r['v_ref']) for r in R]); im=np.array([abs(float(r['i_motor'])) for r in R])
    v=np.array([(p[i]-p[np.searchsorted(t,t[i]-0.1)])*360/16384/max(t[i]-t[np.searchsorted(t,t[i]-0.1)],1e-3) for i in range(len(p))])
    m=(abs(vs)>=0.95*abs(vs).max())&(t>0.15)
    print(os.path.basename(f)[18:], 'SX' if p[-1]<p[0] else 'DX', f'{t[-1]:.1f}s', 'oscill %.0f%%  I media %.1f max %.1f'%(100*v[m].std()/abs(v[m].mean()),im.mean(),im.max()))
