import sys;sys.path.insert(0,'agents/prove/eventi_scettico_impuntata_20261113')
from rules import *
def run(name,C=0.3374,verbose=True):
    R=load(name,C);t=R['t'];v=R['v'];a=R['a'];dec=R['dec'];d03=R['d03'];d=R['d']
    mv=v>0.28   # >1 km/h
    print('###',name,'dur moto min',round(mv.sum()*.02/60,1),'ay0',round(R['ay0'],3),'gx0',round(R['gx0'],2),'corr dec/-wheelacc',round(np.corrcoef(dec[mv],-a[mv])[0,1],2))
    # decel braking wheel segments: dv<-1.5 m/s... classify braking: any time wheel decel(0.5s)>1 for >=0.4 s
    br=episodes((-a>1.0)&mv,t,1.0)
    rules={'P1 dec>=2&d03>=1.5':(dec>=2)&(d03>=1.5),'P2 dec>=2.5&d03>=1.5':(dec>=2.5)&(d03>=1.5),
           'cap dec>=3':dec>=3,'cap dec>=3.5':dec>=3.5,'d03>=3':d03>=3,'old rate/pitch(not recon.)':d03>=2.0}
    # label "impuntata-like" = d03 peak>=3deg within 1s window with dec(wheel or IMU)>=2 : candidates
    for k,m in rules.items():
        eps=episodes(m&mv,t,1.0)
        print(f' {k:28s} episodi in moto {len(eps):3d} ({len(eps)/(mv.sum()*.02/60):.2f}/min)')
    P1=episodes(rules['P1 dec>=2&d03>=1.5']&mv,t,1.0)
    for i,j in P1:
        w=d.wall[i][11:19]; pk=i+np.argmax(d03[i:i+75])
        print(f"  P1 @ {w} v={v[i]*3.6:4.1f}km/h dec={dec[i]:.1f} d03pk={d03[pk]:.1f} lead_to_d03pk={t[pk]-t[i]:.2f}s servo={np.nanmax(d.brake_out_deg.values[max(0,i-75):i+1]):.1f}")
    return R,br
if __name__=='__main__':
    for n in sys.argv[1:]: run(n)
