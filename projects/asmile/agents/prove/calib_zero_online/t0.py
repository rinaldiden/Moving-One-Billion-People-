from core import *
P1,P2=load();Z,dy,d=depth(REF,P1,P2)
print(len(P1),'dy ref med',np.median(abs(dy)),'p95',np.percentile(abs(dy),95))
ok=np.isfinite(Z)&(d>0)
print('frac d>0',ok.mean())
for q in (1,3,5,10,25,50,75,90): print(q,'pct disp',np.percentile(d[ok],q).round(2),'Z',np.percentile(Z[ok],100-q).round(1))
print('Z<5m frac',(Z<5).mean(),'Z<10',(Z<10).mean())
x=P1[:,0];
for lo,hi in((0,200),(200,500),(500,800),(800,1100),(1100,1280)): s=ok&(x>=lo)&(x<hi)&(Z<8); print('x',lo,hi,s.sum())
