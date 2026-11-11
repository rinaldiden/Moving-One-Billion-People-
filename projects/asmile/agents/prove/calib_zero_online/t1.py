from core import *
P1,P2=load();Z0,dy0,d0=depth(REF,P1,P2)
sel=np.isfinite(Z0)&(Z0>2)&(Z0<8)
cen=sel&(abs(P1[:,0]-640)<250);edg=sel&((P1[:,0]<250)|(P1[:,0]>1030))
print('n cen',cen.sum(),'edge',edg.sum())
# idx: 0 rx 1 ry 2 rz 3 fL 4 k1L 5 dcx 6 fR 7 k1R 8 dcy
def run(name,mod):
    out=[]
    for sgn in (+1,-1):
        p=REF.copy();mod(p,sgn);Z,dy,d=depth(p,P1,P2)
        e=100*(Z/Z0-1)
        _,dyp,_=depth(p,P1,P2)
        out.append((np.nanmedian(abs(e[cen])),np.nanmedian(abs(e[edg])),np.nanmedian(abs(dyp-dy0)[cen|edg])))
    o=np.mean(out,0);print(f'{name:38s} centro {o[0]:6.2f}%  bordi {o[1]:6.2f}%  d(dy) {o[2]:5.2f}px')
    return name,o
R=[]
def fboth(a):
    def m(p,s): p[3]*=1+s*a;p[6]*=1+s*a
    return m
R.append(run('f comune +-3%',fboth(.03)))
R.append(run('f comune +-5%',fboth(.05)))
def fd(a):
    def m(p,s): p[3]*=1+s*a/2;p[6]*=1-s*a/2
    return m
R.append(run('f L/R differente 1% (+-0.5)',fd(.01)))
R.append(run('f L/R differente 3%',fd(.03)))
def pp(i,px):
    def m(p,s): p[i]+=s*px
    return m
for px in (3,8,17): R.append(run(f'pp x destra +-{px}px (={px*3/1000:.3f}mm)',pp(5,px)))
for px in (3,8,17): R.append(run(f'pp y destra +-{px}px',pp(8,px)))
def ang(i,dg):
    def m(p,s): p[i]+=s*dg
    return m
for dg in (0.05,0.1,0.3): R.append(run(f'yaw (ry) +-{dg} deg',ang(1,dg)))
for dg in (0.1,0.3,1.0): R.append(run(f'pitch (rx) +-{dg} deg',ang(0,dg)))
for dg in (0.1,0.3,1.0): R.append(run(f'roll (rz) +-{dg} deg',ang(2,dg)))
def kk(a):
    def m(p,s): p[4]+=s*a;p[7]+=s*a
    return m
for a in (0.02,0.05,0.1): R.append(run(f'k1 comune +-{a} (su {REF[4]:.2f})',kk(a)))
def kd(a):
    def m(p,s): p[4]+=s*a/2;p[7]-=s*a/2
    return m
R.append(run('k1 L/R differente 0.05',kd(.05)))
