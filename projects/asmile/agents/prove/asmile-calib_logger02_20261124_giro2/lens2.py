"""ROUND 2 punto 1 (PREREG.md): modelli di lente giudicati per zona 3x3 sui blocchi tenuti fuori. uso: python3 lens2.py <W> -> lens2.json"""
import os,sys,json,pickle,numpy as np,cv2
from scipy.optimize import least_squares
from fitlib import undist,Rm,skew,zone,W_,H_
V5=os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_logger02.CANDIDATO_v5_20261124.json')
c=json.load(open(V5));K1_0=np.array(c['K_left']);K2_0=np.array(c['K_right']);d0=np.array(c['dist_left']);R0=np.array(c['R']);T0=np.array(c['T']);B=np.linalg.norm(T0)
# p: 0 Rx 1 Ry 2 Rz 3 Ty 4 Tz 5 cx1 6 cy1 7 cx2 8 cy2 9 k1L 10 k2L 11 k1R 12 k2R 13 k3 14 e_f(dx destra) 
def build(p,shared):
    K1=K1_0.copy();K2=K2_0.copy();R=Rm(p[:3])@R0;u=T0/abs(T0[0]);u[1]+=p[3];u[2]+=p[4];T=u/np.linalg.norm(u)*B
    K1[0,2]+=p[5];K1[1,2]+=p[6];K2[0,2]+=p[7];K2[1,2]+=p[8];K2[0,0]*=1+p[14];K2[1,1]*=1+p[14]
    dL=d0.copy();dR=d0.copy();dL[0]+=p[9];dL[1]+=p[10];dR[0]+=(p[9] if shared else p[11]);dR[1]+=(p[10] if shared else p[12]);dL[4]+=p[13];dR[4]+=p[13];return K1,K2,dL,dR,R,T
def sampson(a,b,p,shared):
    K1,K2,dL,dR,R,T=build(p,shared);x1=undist(a,K1,dL);x2=undist(b,K2,dR);E=skew(T/np.linalg.norm(T))@R;X1=np.c_[x1,np.ones(len(x1))];X2=np.c_[x2,np.ones(len(x2))];Ex=X1@E.T;Etx=X2@E
    return np.sum(X2*Ex,1)/np.sqrt(Ex[:,0]**2+Ex[:,1]**2+Etx[:,0]**2+Etx[:,1]**2)*K1[0,0]
def rect(a,b,p,shared):
    K1,K2,dL,dR,R,T=build(p,shared);r=cv2.stereoRectify(K1,dL,K2,dR,(W_,H_),R,T.reshape(3,1),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    def f(q,K,d,Rr):
        x=undist(q,K,d);v=np.c_[x,np.ones(len(x))]@Rr.T;P=r[2];return np.c_[P[0,0]*v[:,0]/v[:,2]+P[0,2],P[1,1]*v[:,1]/v[:,2]+P[1,2]]
    return f(a,K1,dL,r[0]),f(b,K2,dR,r[1])
MODELS={'RC':([0,2,3,4,8],True),'K2':([0,2,3,4,8,9,10],True),'K3':([0,2,3,4,8,9,10,13],True),'KC':([0,2,3,4,8,9,10,11,12],False),'KCF':([0,2,3,4,8,9,10,11,12,14],False),'KCFc':([0,2,3,4,8,9,10,11,12,14,6],False)}
XS=np.array([0.005,0.005,0.005,0.005,0.005,5,5,5,5,0.02,0.02,0.02,0.02,0.01,0.005])
def fit(a,b,m,x0=None):
    free,sh=MODELS[m];x0=np.zeros(15) if x0 is None else x0.copy();lo=np.full(len(free),-np.inf);hi=np.full(len(free),np.inf)
    for i,k in enumerate(free):
        if k==6: lo[i],hi[i]=-15,15
        if k==14: lo[i],hi[i]=-0.05,0.05
    def res(q): p=x0.copy();p[free]=q;return sampson(a,b,p,sh)
    r=least_squares(res,x0[free],loss='soft_l1',f_scale=1.0,x_scale=XS[free],bounds=(lo,hi),max_nfev=100);p=x0.copy();p[free]=r.x;return p
def stats(a,b,p,sh,ref=None):
    qa,qb=rect(a,b,p,sh);dy=qa[:,1]-qb[:,1];dx=qa[:,0]-qb[:,0];ok=(dx>1)&(abs(dy)<40);z=zone(a[ok]);ad=abs(dy[ok]);zs=[]
    for i in range(9):
        k=z==i
        zs.append(dict(n=int(k.sum()),med=round(float(np.median(ad[k])),3) if k.sum()>=15 else None,segno=round(float(np.median(dy[ok][k])),3) if k.sum()>=15 else None,p95=round(float(np.percentile(ad[k]),95) if False else float(np.percentile(ad[k],95)),2) if k.sum()>=15 else None))
    o=dict(n=int(ok.sum()),med=float(np.median(ad)),p95=float(np.percentile(ad,95)),zone=zs,n_zone_gt1=sum(1 for q in zs if q['med'] and q['med']>1))
    if ref is not None: o['dx_shift_zone']=[round(float(np.median((dx-ref)[ok][z==i])),3) if (z==i).sum()>=15 else None for i in range(9)]
    o['_dx']=dx;o['_ok']=ok;return o
def monotona(p,shared):
    k1,k2,k3=d0[0]+p[9],d0[1]+p[10],d0[4]+p[13];r=np.linspace(0.01,0.95,200);f=lambda r:r*(1+k1*r**2+k2*r**4+k3*r**6);return bool((np.diff(f(r))>0).all())
if __name__=='__main__':
    W=sys.argv[1];S=pickle.load(open(W+'/lr_matches.pkl','rb'));rng=np.random.default_rng(0);rd=lambda p,K:np.hypot((p[:,0]-K[0,2])/K[0,0],(p[:,1]-K[1,2])/K[1,1]);L=[]
    for s in S:
        if s['reg']!='M': continue
        n=len(s['a']);i=rng.permutation(n)[:250];a=s['a'][i];b=s['b'][i];v=(rd(a,K1_0)<0.64)&(rd(b,K2_0)<0.64);L.append((s['t'],a[v],b[v]))
    cat=lambda sel:(np.concatenate([x[1] for x in sel]),np.concatenate([x[2] for x in sel]))
    ev=cat([x for x in L if int(x[0]//60)%2==0]);od=cat([x for x in L if int(x[0]//60)%2==1]);out={}
    z=np.zeros(15);ref={}
    for tag,(A,Bq) in(('dispari',od),('pari',ev)):
        s0=stats(A,Bq,z,True);ref[tag]=s0['_dx'];out['v5_'+tag]={k:v for k,v in s0.items() if not k.startswith('_')}
    for m in MODELS:
        out[m]={}
        for tag,trn,tst in(('test_dispari',ev,od),('test_pari',od,ev)):
            p=fit(*trn,m);sh=MODELS[m][1];s=stats(*tst,p,sh,ref=ref['dispari' if 'dispari' in tag else 'pari']) if False else stats(*tst,p,sh)
            # dx shift rispetto a v5 sugli stessi punti
            qa,qb=rect(*tst,p,sh);dx=qa[:,0]-qb[:,0];ok=s['_ok'];zz=zone(tst[0][ok]);r5=ref['dispari' if 'dispari' in tag else 'pari'];okr=ok  # ref calcolato sugli stessi punti
            s['dx_shift_zone']=[round(float(np.median((dx-r5)[ok][zz==i])),3) if (zz==i).sum()>=15 else None for i in range(9)]
            out[m][tag]={k:v for k,v in s.items() if not k.startswith('_')};out[m][tag]['par']=p.tolist();out[m][tag]['monotona']=monotona(p,sh)
            print(m,tag,'med %.3f p95 %.2f zone>1: %d'%(s['med'],s['p95'],s['n_zone_gt1']),'zone med',[q['med'] for q in s['zone']],'segno z8',s['zone'][8]['segno'],'dx_shift',s['dx_shift_zone'],flush=True)
    json.dump(out,open('lens2.json','w'),indent=1)
