"""Strada 3 (vincolo linee dritte / plumb-line): i bordi rettilinei del mondo devono restare dritti dopo la correzione della lente.
Residuo = rms ortogonale di ogni pezzo (in pixel equivalenti) rispetto alla retta migliore, nel piano normalizzato non distorto.
Modelli (per camera): M0 = lente candidata v1; M1 = k1,k2 + centro; M2 = k1,k2,k3 + centro; M3 = M2 + tangenziali + aspetto fy/fx.
Valutazione su blocchi di tempo TENUTI FUORI (blocchi di 60 s alterni)."""
import os,sys,json,pickle,numpy as np,cv2
from scipy.optimize import least_squares
sys.path.insert(0,os.path.dirname(__file__))
from common import *
c=json.load(open(CALIB))
F=1123.5266816247774
def undist_np(u,v,K,dist,it=12):
    fx,fy,cx,cy=K;k1,k2,p1,p2,k3=dist
    xd=(u-cx)/fx;yd=(v-cy)/fy;x=xd.copy();y=yd.copy()
    for _ in range(it):
        r2=x*x+y*y;rad=1+k1*r2+k2*r2**2+k3*r2**3
        dx=2*p1*x*y+p2*(r2+2*x*x);dy=p1*(r2+2*y*y)+2*p2*x*y
        x=(xd-dx)/rad;y=(yd-dy)/rad
    return x,y
def build(side,minlen=90):
    L=pickle.load(open(os.path.join(W,'lines.pkl'),'rb'));L=[l for l in L if l[1]==side]
    pts=[];starts=[0];ts=[]
    for t,_,p in L:
        p=p[::2];
        if len(p)<25: continue
        pts.append(p);starts.append(starts[-1]+len(p));ts.append(t)
    return np.concatenate(pts).astype(np.float64),np.array(starts),np.array(ts)
def piece_rms(x,y,starts):
    n=np.diff(starts).astype(float);S=lambda a:np.add.reduceat(a,starts[:-1])
    mx=S(x)/n;my=S(y)/n;a=S(x*x)/n-mx**2;b=S(x*y)/n-mx*my;cc=S(y*y)/n-my**2
    h=np.sqrt(((a-cc)/2)**2+b**2);lam=(a+cc)/2-h;lam1=(a+cc)/2+h
    return np.sqrt(np.maximum(lam,0)/np.maximum(lam1,1e-12)),n   # rettilineita' adimensionale: sigma_minore/sigma_maggiore
def params(p,model,base):
    K=np.array([base['K'][0],base['K'][1],base['K'][2],base['K'][3]],float);d=np.array(base['d'],float)
    i=0
    if model>=1: K[2]+=p[0];K[3]+=p[1];d[0]+=p[2];d[1]+=p[3];i=4
    if model>=2: d[4]+=p[i];i+=1
    if model>=3: d[2]+=p[i];d[3]+=p[i+1];K[1]*=1+p[i+2];i+=3
    return K,d
def npar(model): return 0 if model==0 else 4+(model>=2)+3*(model>=3)
def res(p,model,base,pts,starts,rmax=0.64):
    K,d=params(p,model,base);x,y=undist_np(pts[:,0],pts[:,1],K,d)
    r=np.hypot(x,y);rms,n=piece_rms(x,y,starts)
    bad=np.maximum.reduceat((r>rmax).astype(float),starts[:-1])>0
    out=rms*60.0;out[bad]=1.5   # 60 px = sigma maggiore tipica di un pezzo: residuo ~ px   # pezzi fuori dominio: costo costante (non guida il fit)
    return out
def fit(model,base,pts,starts,x0=None):
    p0=np.zeros(npar(model)) if x0 is None else x0
    if npar(model)==0: return p0
    sc=np.r_[[5,5,0.02,0.02],[0.02]*(model>=2),[0.002,0.002,0.01]*(model>=3)]
    lo=np.r_[[-60,-60,-0.6,-0.6],[-0.6]*(model>=2),[-0.01,-0.01,-0.05]*(model>=3)];hi=-lo
    s=least_squares(lambda p:res(p,model,base,pts,starts),p0,loss='soft_l1',f_scale=0.5,x_scale=sc,bounds=(lo,hi),max_nfev=40);return s.x
def sub(pts,starts,ts,mask):
    idx=np.where(mask)[0];P=[];S=[0]
    for i in idx: P.append(pts[starts[i]:starts[i+1]]);S.append(S[-1]+starts[i+1]-starts[i])
    return np.concatenate(P),np.array(S)
if __name__=='__main__':
    out={}
    for side in 'AB':
        pts,starts,ts=build(side);Kc=c['K_left' if side=='A' else 'K_right'];dc=c['dist_left']
        base=dict(K=[Kc[0][0],Kc[1][1],Kc[0][2],Kc[1][2]],d=dc)
        blk=(ts//60).astype(int)%2;tr=blk==0;te=~tr
        Ptr,Str=sub(pts,starts,ts,tr);Pte,Ste=sub(pts,starts,ts,te)
        print(side,'pezzi',len(ts),'train',tr.sum(),'test',te.sum())
        for model in (0,1,2,3):
            p=fit(model,base,Ptr,Str)
            r_tr=res(p,model,base,Ptr,Str);r_te=res(p,model,base,Pte,Ste);ok_te=r_te!=1.5
            print('  M%d  train med %.3f p90 %.3f | TEST med %.3f p90 %.3f (pezzi %d)'%(model,np.median(r_tr),np.percentile(r_tr,90),np.median(r_te[ok_te]),np.percentile(r_te[ok_te],90),ok_te.sum()),'par',np.round(p,4).tolist(),flush=True)
            K,d=params(p,model,base);out[f'{side}_M{model}']=dict(K=K.tolist(),d=d.tolist(),test_med=float(np.median(r_te[ok_te])),test_p90=float(np.percentile(r_te[ok_te],90)))
    json.dump(out,open(os.path.join(W,'plumb.json'),'w'),indent=1)
