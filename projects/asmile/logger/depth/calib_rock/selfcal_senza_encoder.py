#!/usr/bin/env python3
"""
selfcal_senza_encoder.py - calibrazione AUTOMATICA di logger02 (HW3, 2 x ESP32-P4 + OV9281), senza tabellone e SENZA encoder.
Giro 2026-11-23. Raccolta dei passi usati (ognuno = un modulo, separati da '# ===== file'; per rieseguire, spezzarli in file con
quei nomi). Ordine: idx -> extract25 -> selfcal/m -> fit7/fit8 (epipolare) -> chains -> rig/rig3/rig4 (d0 e focale dalla rigidita'
del moto) -> plane2 (piano strada) -> imu/imu2 (rotazione IMU->camera) -> bins (coerenza per distanza) -> dyzone -> control.
Risultati: calib_logger02.CANDIDATO_20261123.json, imu_montaggio_case_v5.json, banco_fisso_logger02.json.
Dati video SOLO locali. I percorsi puntano a asmile-loggers/logger02_giro_20261123 (mai su git).
Lezioni: il "solo montaggio" con la lente di #001 e' ROSSO (dy mediano 1.0-3.0 px, p95 5-14 px): i centri ottici non si trasferiscono
fra unita'; la rigidita' del moto va misurata in PIXEL (in spazio 3D collassa a f->0); piano strada nei vicoli inaffidabile.
"""

# ===== file: idx.py =====
import glob,csv,numpy as np,os,pickle
D=os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/logger02_giro_20261123')
def load(side,col):
    rows=[]
    for f in sorted(glob.glob(f'{D}/{side}/clip_*_{side}_*_frames.csv')):
        clip=f.replace('_frames.csv','.h264')
        for i,r in enumerate(csv.DictReader(open(f))):
            rows.append((int(r[col]),clip,i,int(r['frame'])))
    return rows
A=load('A','t_us'); B=load('B','t_a_us')
ta=np.array([r[0] for r in A]); tb=np.array([r[0] for r in B])
print(len(A),len(B),ta.min()/1e6,ta.max()/1e6,tb.min()/1e6,tb.max()/1e6)
j=np.searchsorted(tb,ta); j=np.clip(j,1,len(tb)-1)
jj=np.where(abs(tb[j]-ta)<abs(tb[j-1]-ta),j,j-1)
dt=tb[jj]-ta
ok=abs(dt)<10000
print(ok.sum(), np.percentile(dt[ok],[5,50,95]))
pairs=[(A[i],B[jj[i]],dt[i]) for i in range(len(A)) if ok[i]]
pickle.dump(pairs,open('pairs.pkl','wb'))
print(len(pairs))

# ===== file: dec.py =====
import subprocess,numpy as np,functools
@functools.lru_cache(maxsize=2)
def clip(path):
    p=subprocess.run(['ffmpeg','-v','error','-i',path,'-f','rawvideo','-pix_fmt','gray','-'],capture_output=True)
    a=np.frombuffer(p.stdout,np.uint8); return a.reshape(-1,720,1280)

# ===== file: selfcal.py =====
import pickle,json,numpy as np,cv2
from scipy.optimize import least_squares
CP='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_asmile-001.json'
c=json.load(open(CP))
K1n=np.array(c['K_left']);K2n=np.array(c['K_right']);d1n=np.array(c['dist_left']);d2n=np.array(c['dist_right'])
R0=np.array(c['R']);T0=np.array(c['T'])
W,H=1280,720
CAP=200
def Rm(w): return cv2.Rodrigues(np.asarray(w,float).reshape(3,1))[0]
def undist(P,K,d):
    q=cv2.undistortPointsIter(P.reshape(-1,1,2),K,d,None,None,(cv2.TERM_CRITERIA_COUNT|cv2.TERM_CRITERIA_EPS,40,1e-10)).reshape(-1,2)
    return q
def valid(P,K,d):
    # dominio d'invertibilita': r_d normalizzato entro 0.644 per modelli con k3 forte
    r=np.hypot((P[:,0]-K[0,2])/K[0,0],(P[:,1]-K[1,2])/K[1,1]);return r
def sampson(q1,q2,R,t):
    t=np.asarray(t,float);tx=np.array([[0,-t[2],t[1]],[t[2],0,-t[0]],[-t[1],t[0],0]])
    E=tx@R
    x1=np.c_[q1,np.ones(len(q1))];x2=np.c_[q2,np.ones(len(q2))]
    Ex1=x1@E.T;Etx2=x2@E
    num=np.sum(x2*Ex1,1)
    den=np.sqrt(Ex1[:,0]**2+Ex1[:,1]**2+Etx2[:,0]**2+Etx2[:,1]**2)
    return num/den   # in unita normalizzate
def load():
    M=pickle.load(open('matches.pkl','rb'));rng=np.random.default_rng(1)
    M=[m for m in M if len(m[3])>=60]
    ks=[];Ps=[];Qs=[]
    for m in M:
        i=rng.permutation(len(m[3]))[:CAP]
        ks.append(np.full(len(i),m[0]));Ps.append(m[3][i]);Qs.append(m[4][i])
    return np.concatenate(ks),np.concatenate(Ps),np.concatenate(Qs)
def zone(P):
    return (np.clip((P[:,1]/H*3).astype(int),0,2))*3+np.clip((P[:,0]/W*3).astype(int),0,2)

# ===== file: m.py =====
import sys;sys.path.insert(0,'.')
from selfcal import *
import pickle
pairs=pickle.load(open('pairs.pkl','rb'))
def tpair(kk): return pairs[kk][0][0]/1e6
def loadseg(t0,t1,cap=150,minn=100,seed=1):
    M=pickle.load(open('matches25.pkl','rb'));rng=np.random.default_rng(seed)
    ks=[];Ps=[];Qs=[]
    for m in M:
        if not(t0<=tpair(m[0])<t1) or len(m[3])<minn: continue
        i=rng.permutation(len(m[3]))[:cap]
        ks.append(np.full(len(i),m[0]));Ps.append(m[3][i]);Qs.append(m[4][i])
    return np.concatenate(ks),np.concatenate(Ps),np.concatenate(Qs)
def lensK(kind):
    if kind=='sym': return K1n.copy(),d1n.copy(),K1n.copy(),d1n.copy()
    return K1n.copy(),d1n.copy(),K2n.copy(),d2n.copy()
def build(p,mode,kind,off=40):
    K1,d1,K2,d2=lensK(kind)
    K1[1,2]-=off;K2[1,2]-=off
    w=p[:3];ty,tz=p[3],p[4];i=5
    if mode>=1:
        K1[0,2]+=p[i];K1[1,2]+=p[i+1];K2[0,2]+=p[i+2];K2[1,2]+=p[i+3];i+=4
    if mode>=2:
        d1[0]+=p[i];d1[1]+=p[i+1];d2[0]+=p[i+2];d2[1]+=p[i+3];i+=4
    if mode>=3:
        K1[0,0]*=1+p[i];K1[1,1]*=1+p[i];K2[0,0]*=1+p[i+1];K2[1,1]*=1+p[i+1];i+=2
    return K1,d1,K2,d2,Rm(w),np.array([-1,ty,tz])
def okmask(P,Q,kind,off=40):
    K1,d1,K2,d2=lensK(kind);K1[1,2]-=off;K2[1,2]-=off
    return (valid(P,K1,d1)<0.64)&(valid(Q,K2,d2)<0.64)
def resid(p,P,Q,mode,kind):
    K1,d1,K2,d2,R,t=build(p,mode,kind)
    return sampson(undist(P,K1,d1),undist(Q,K2,d2),R,t)*K1[0,0]
def nparams(mode): return 5+4*(mode>=1)+4*(mode>=2)+2*(mode>=3)
def xscale(mode): return np.r_[np.full(5,0.01),np.full(4*(mode>=1),5.0),np.full(4*(mode>=2),0.02),np.full(2*(mode>=3),0.01)]
def fit(P,Q,mode,kind,x0=None):
    x=np.zeros(nparams(mode));x[:3]=np.radians([1.41,-0.55,-0.56]);x[3:5]=[-0.012,-0.022]
    if x0 is not None:x[:len(x0)]=x0
    s=least_squares(resid,x,args=(P,Q,mode,kind),loss='soft_l1',f_scale=1.0,x_scale=xscale(mode))
    return s.x
def zstats(r,P):
    z=zone(P);r=np.abs(r)
    return float(np.median(r)),float(np.percentile(r,95)),[(round(float(np.median(r[z==i])),2),round(float(np.percentile(r[z==i],95)),2)) for i in range(9)]

# ===== file: fit7.py =====
from m import *
k,P,Q=loadseg(150,870)
uk=np.unique(k);blk=np.searchsorted(uk,k)//8;tr=blk%2==0;te=~tr
print(len(P),tr.sum(),te.sum())
for kind in('own','sym'):
  for mode in(0,1,2,3):
    ok=okmask(P,Q,kind);itr=tr&ok;ite=te&ok
    p=fit(P[itr],Q[itr],mode,kind)
    m,p95,z=zstats(resid(p,P[ite],Q[ite],mode,kind),P[ite])
    m2,p952,_=zstats(resid(p,P[itr],Q[itr],mode,kind),P[itr])
    print(kind,mode,'TEST med %.2f p95 %.2f | train med %.2f p95 %.2f'%(m,p95,m2,p952),'w',np.degrees(p[:3]).round(2))
    print('    zone',z,'extra',p[5:].round(2))

# ===== file: fit8.py =====
from m import *
import json
k1,P1,Q1=loadseg(150,870);ok=okmask(P1,Q1,'sym');
p=fit(P1[ok],Q1[ok],1,'sym');lens=p[5:];print('S1',np.degrees(p[:3]).round(3),p[3:5].round(4),lens.round(2))
np.save('p_S1.npy',p)
for name,(a,b) in {'S2':(1090,1400),'S2a':(1090,1250),'S2b':(1250,1400)}.items():
    k,P,Q=loadseg(a,b,cap=150,minn=60);ok=okmask(P,Q,'sym');k,P,Q=k[ok],P[ok],Q[ok]
    uk=np.unique(k);blk=np.searchsorted(uk,k)//4;tr=blk%2==0;te=~tr
    q=fit(P[tr],Q[tr],1,'sym',np.r_[p[:5],lens]) if False else None
    f=lambda x,P,Q:resid(np.r_[x,lens],P,Q,1,'sym')
    s=least_squares(f,p[:5],args=(P[tr],Q[tr]),loss='soft_l1',f_scale=1.0,x_scale=0.01)
    print(name,len(P),'w',np.degrees(s.x[:3]).round(3),s.x[3:].round(4))
    m,p95,z=zstats(f(s.x,P[te],Q[te]),P[te]);print('  TEST med %.2f p95 %.2f'%(m,p95),z)
    m,p95,z=zstats(f(p[:5],P[te],Q[te]),P[te]);print('  con S1: med %.2f p95 %.2f'%(m,p95))
    for kk in uk[::3]:
        mm=(k==kk)&te
        if mm.sum()>20: print('   t=%.0f n=%d med %.2f'%(tpair(kk),mm.sum(),np.median(np.abs(f(s.x,P[mm],Q[mm])))))
    np.save('p_%s.npy'%name,s.x)

# ===== file: extract25.py =====
import pickle,numpy as np,cv2,collections
from multiprocessing import Pool
from dec import clip
pairs=pickle.load(open('pairs.pkl','rb'))
STEP=25
sel=list(range(0,len(pairs),STEP))
def work(grp):
    out=[]
    sift=cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.015)
    bf=cv2.BFMatcher(cv2.NORM_L2)
    for k in grp:
        a,b,dt=pairs[k]
        ia=clip(a[1])[a[2]].copy(); ib=clip(b[1])[b[2]].copy()
        m=np.zeros_like(ia);m[10:-10,10:-10]=255
        ka,da=sift.detectAndCompute(ia,m);kb,db=sift.detectAndCompute(ib,m)
        if da is None or db is None or len(ka)<20 or len(kb)<20: continue
        ab=bf.knnMatch(da,db,k=2);ba=bf.knnMatch(db,da,k=1)
        P=[];Q=[]
        for mm in ab:
            if len(mm)==2 and mm[0].distance<0.8*mm[1].distance and ba[mm[0].trainIdx][0].trainIdx==mm[0].queryIdx:
                P.append(ka[mm[0].queryIdx].pt);Q.append(kb[mm[0].trainIdx].pt)
        P=np.array(P,np.float64);Q=np.array(Q,np.float64)
        if len(P)<15: continue
        F,inl=cv2.findFundamentalMat(P,Q,cv2.USAC_MAGSAC,6.0,0.999,10000)
        if F is None: continue
        inl=inl.ravel().astype(bool)
        out.append((k,a[0],a[3],P[inl],Q[inl],ia[::4,::4].copy() if k%1000==0 else None))
    return out
if __name__=='__main__':
    g=collections.OrderedDict()
    for k in sel: g.setdefault((pairs[k][0][1],pairs[k][1][1]),[]).append(k)
    # un job per (A,B) clip
    with Pool(4) as p: res=p.map(work,list(g.values()))
    res=[r for rr in res for r in rr]; res.sort(key=lambda r:r[0])
    print(len(res),sum(len(r[3]) for r in res))
    pickle.dump([(r[0],r[1],r[2],r[3],r[4]) for r in res],open('matches25.pkl','wb'))

# ===== file: chains.py =====
import pickle,numpy as np,cv2,collections
from multiprocessing import Pool
from dec import clip
pairs=pickle.load(open('pairs.pkl','rb'))
T=np.array([p[0][0]/1e6 for p in pairs])
DK=8
ks=[k for k in range(0,len(pairs)-DK,30) if 150<=T[k]<870 and 0.4<T[k+DK]-T[k]<0.6]
def feats(sift,im):
    m=np.zeros_like(im);m[10:-10,10:-10]=255
    kp,de=sift.detectAndCompute(im,m);return np.array([q.pt for q in kp],np.float64),de
def mt(bf,da,db,ratio=0.8):
    ab=bf.knnMatch(da,db,k=2);ba=bf.knnMatch(db,da,k=1);i=[];j=[]
    for m in ab:
        if len(m)==2 and m[0].distance<ratio*m[1].distance and ba[m[0].trainIdx][0].trainIdx==m[0].queryIdx:
            i.append(m[0].queryIdx);j.append(m[0].trainIdx)
    return np.array(i,int),np.array(j,int)
def work(grp):
    sift=cv2.SIFT_create(nfeatures=2500,contrastThreshold=0.015);bf=cv2.BFMatcher(cv2.NORM_L2);out=[]
    for k in grp:
        a0,b0,_=pairs[k];a1,b1,_=pairs[k+DK]
        im=[clip(a0[1])[a0[2]].copy(),clip(b0[1])[b0[2]].copy(),clip(a1[1])[a1[2]].copy(),clip(b1[1])[b1[2]].copy()]
        F=[feats(sift,x) for x in im]
        if any(f[1] is None or len(f[0])<30 for f in F): continue
        i01,j01=mt(bf,F[0][1],F[1][1]);i02,j02=mt(bf,F[0][1],F[2][1]);i23,j23=mt(bf,F[2][1],F[3][1])
        d01=dict(zip(i01,j01));d23=dict(zip(i23,j23))
        rows=[]
        for a,c in zip(i02,j02):
            if a in d01 and c in d23: rows.append((a,d01[a],c,d23[c]))
        if len(rows)<20: continue
        r=np.array(rows)
        L0=F[0][0][r[:,0]];R0=F[1][0][r[:,1]];L1=F[2][0][r[:,2]];R1=F[3][0][r[:,3]]
        # gate temporale: F-RANSAC L0->L1
        try: Fm,inl=cv2.findFundamentalMat(L0,L1,cv2.USAC_MAGSAC,3.0,0.999,5000)
        except cv2.error: continue
        if Fm is None or inl is None: continue
        inl=inl.ravel().astype(bool)
        out.append((k,T[k],T[k+DK],L0[inl],R0[inl],L1[inl],R1[inl],float(np.median(np.hypot(*(L1[inl]-L0[inl]).T)))))
    return out
if __name__=='__main__':
    g=collections.OrderedDict()
    for k in ks: g.setdefault(pairs[k][0][1],[]).append(k)
    with Pool(4) as p: res=p.map(work,list(g.values()))
    res=[r for rr in res for r in rr];res.sort(key=lambda r:r[0])
    print(len(ks),len(res),sum(len(r[3]) for r in res))
    pickle.dump(res,open('chains.pkl','wb'))

# ===== file: rig.py =====
from m import *
import pickle
p=np.load('p_S1.npy');K1,d1,K2,d2,R,t=build(p,1,'sym');B=0.2
T=(t/np.linalg.norm(t)*-1*B*-1)  # direzione (-1,ty,tz) normalizzata * B
T=np.array([-1,t[1],t[2]]);T=T/np.linalg.norm(T)*B
r=cv2.stereoRectify(K1,d1,K2,d2,(1280,720),R,T.reshape(3,1),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
RR1,R2,P1,P2=r[0],r[1],r[2],r[3]
f0=P1[0,0];cx,cy=P1[0,2],P1[1,2]
def rect(P,Kc,d,Rr):
    return cv2.undistortPoints(P.reshape(-1,1,2),Kc,d,R=Rr,P=P1 if True else None).reshape(-1,2)
def prep():
    ch=pickle.load(open('chains.pkl','rb'));S=[]
    for c in ch:
        k,t0,t1,L0,R0,L1,Rp1,mv=c
        a=rect(L0,K1,d1,RR1);b=rect(R0,K2,d2,R2);c_=rect(L1,K1,d1,RR1);e=rect(Rp1,K2,d2,R2)
        ok=(abs(a[:,1]-b[:,1])<1.5)&(abs(c_[:,1]-e[:,1])<1.5)&(a[:,0]-b[:,0]>3)&(c_[:,0]-e[:,0]>3)
        if ok.sum()<25 or mv<3: continue
        S.append(dict(k=k,t=t0,a=a[ok],b=b[ok],c=c_[ok],e=e[ok],mv=mv))
    return S
if __name__=='__main__':
    S=prep();print(len(S),'f_rett',f0,cx,cy,'P2[0,3]/f',P2[0,3]/f0, 'B_rett',-P2[0,3]/f0)
    pickle.dump(dict(S=S,f0=f0,cx=cx,cy=cy,Bt=-P2[0,3]/f0),open('rig.pkl','wb'))
    print('mediana mov px',np.median([s['mv'] for s in S]))

# ===== file: rig3.py =====
import pickle,numpy as np,cv2,sys
from scipy.optimize import least_squares
D=pickle.load(open('rig.pkl','rb'));S=D['S'];f0,cx,cy,B=D['f0'],D['cx'],D['cy'],0.2
def P3(u,v,d,d0,f):
    dd=d+d0;return np.c_[(u-cx)*B/dd,(v-cy)*B/dd,f*B/dd]
def proj(P,f): return np.c_[f*P[:,0]/P[:,2]+cx,f*P[:,1]/P[:,2]+cy]
def inner(s,d0,f,zmax=20):
    a,b,c,e=s['a'],s['b'],s['c'],s['e']
    P0=P3(a[:,0],a[:,1],a[:,0]-b[:,0],d0,f);ok=(P0[:,2]>1.5)&(P0[:,2]<zmax)
    if ok.sum()<20: return None
    P0=P0[ok];c_=c[ok];e_=e[ok]
    def r(x):
        R=cv2.Rodrigues(x[:3].reshape(3,1))[0];P1=P0@R.T+x[3:]
        pl=proj(P1,f);pr=proj(P1-np.array([B,0,0]),f)
        return np.r_[(pl-c_).ravel(),(pr-e_).ravel()]
    x0=np.r_[0,0,0,0,0,s['tz0'] if 'tz0' in s else 1.5]
    sol=least_squares(r,x0,loss='soft_l1',f_scale=1.0,max_nfev=30)
    s['tz0']=sol.x[5]
    rr=np.abs(sol.fun);return float(np.median(rr)),float(np.mean(np.minimum(rr,5)**2)),sol.x
def score(sets,d0,f):
    v=[];
    for s in sets:
        o=inner(s,d0,f)
        if o: v.append(o[1])
    return float(np.mean(v)),len(v)
if __name__=='__main__':
    idx=np.arange(len(S));tr=[S[i] for i in idx if i%2==0];te=[S[i] for i in idx if i%2==1]
    print('base',score(tr[:10],0,f0))
    res={}
    for d0 in (-4,-2,0,2,4):
        for fs in (0.9,0.95,1.0,1.05,1.1):
            res[(d0,fs)]=score(tr,d0,f0*fs)[0];print(d0,fs,'%.4f'%res[(d0,fs)],flush=True)
    pickle.dump(res,open('rig3_grid.pkl','wb'))

# ===== file: rig4.py =====
from rig3 import *
idx=np.arange(len(S));tr=[S[i] for i in idx if i%2==0];te=[S[i] for i in idx if i%2==1]
G={}
for d0 in (-1,-0.5,0,0.5,1,1.5):
    row=[]
    for fs in (1.0,1.1,1.2,1.3):
        G[(d0,fs)]=score(tr,d0,f0*fs)[0];row.append('%.3f'%G[(d0,fs)])
    print(d0,row,flush=True)
b=min(G,key=G.get);print('best train',b)
for lab,(d0,fs) in (('nominale',(0,1.0)),('best',b),('d0=0,f=1.1',(0,1.1))):
    print(lab,'TEST',score(te,d0,f0*fs))
# test-set gird indipendente
G2={}
for d0 in (-1,0,1):
    for fs in (1.0,1.1,1.2):
        G2[(d0,fs)]=score(te,d0,f0*fs)[0]
print('best test',min(G2,key=G2.get),{k:round(v,3) for k,v in G2.items()})

# ===== file: plane2.py =====
from rig import *
import pickle
M=pickle.load(open('matches25.pkl','rb'));pairs=pickle.load(open('pairs.pkl','rb'))
f=f0;rng=np.random.default_rng(7);res=[]
def tp(k):return pairs[k][0][0]/1e6
def rectp(Pp,Qp):
    return rect(Pp,K1,d1,RR1),rect(Qp,K2,d2,R2)
blocks=[(150,260),(260,380),(380,520),(520,640),(640,760),(760,870)]
for lo,hi in blocks:
    PL=[];
    for m in M:
        if lo<=tp(m[0])<hi and len(m[3])>=100:
            a,b=rectp(m[3],m[4]);ok=(abs(a[:,1]-b[:,1])<1.5)&(a[:,0]-b[:,0]>2)
            a,b=a[ok],b[ok];d=a[:,0]-b[:,0];Z=f*B/d
            sel=(a[:,1]>cy+30)&(Z>2)&(Z<12)
            PL.append(np.c_[(a[sel,0]-cx)*B/d[sel],(a[sel,1]-cy)*B/d[sel],Z[sel]])
    Q=np.concatenate(PL) if PL else np.zeros((0,3))
    if len(Q)<200: print(lo,hi,'pochi',len(Q));continue
    best=None;bn=0
    for _ in range(1500):
        i=rng.choice(len(Q),3,replace=False);n=np.cross(Q[i[1]]-Q[i[0]],Q[i[2]]-Q[i[0]]);nr=np.linalg.norm(n)
        if nr<1e-9:continue
        n/=nr
        if n[1]<0:n=-n
        if n[1]<0.9:continue
        h=n@Q[i[0]]
        if not 0.3<h<2.0:continue
        inl=abs(Q@n-h)<0.03+0.008*Q[:,2]
        if inl.sum()>bn:best,bn=inl,inl.sum()
    A=np.c_[Q[best],-np.ones(best.sum())];v=np.linalg.svd(A,full_matrices=False)[2][-1];nn=v[:3]/np.linalg.norm(v[:3]);hh=v[3]/np.linalg.norm(v[:3])
    if nn[1]<0:nn,hh=-nn,-hh
    # incertezza: bootstrap sui punti inlier
    hs=[]
    idx=np.where(best)[0]
    for _ in range(30):
        bi=rng.choice(idx,len(idx));Aq=np.c_[Q[bi],-np.ones(len(bi))];vv=np.linalg.svd(Aq,full_matrices=False)[2][-1];n2=vv[:3]/np.linalg.norm(vv[:3]);h2=vv[3]/np.linalg.norm(vv[:3])
        if n2[1]<0:n2,h2=-n2,-h2
        hs.append((h2,np.degrees(np.arcsin(n2[2])),np.degrees(np.arcsin(n2[0]))))
    hs=np.array(hs)
    res.append(dict(t0=lo,t1=hi,n=len(Q),ninl=int(bn),h=float(hh),pitch=float(np.degrees(np.arcsin(nn[2]))),roll=float(np.degrees(np.arcsin(nn[0]))),h_sd=float(hs[:,0].std()),pitch_sd=float(hs[:,1].std()),roll_sd=float(hs[:,2].std()),n_vec=nn.tolist()))
    print(res[-1]['t0'],res[-1]['t1'],'n',len(Q),'inl',bn,'h %.3f±%.3f pitch %.2f±%.2f roll %.2f±%.2f'%(hh,hs[:,0].std(),res[-1]['pitch'],hs[:,1].std(),res[-1]['roll'],hs[:,2].std()))
pickle.dump(res,open('plane2.pkl','wb'))

# ===== file: imu.py =====
import glob,csv,numpy as np,pickle
D='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/logger02_giro_20261123/A'
rows=[]
for f in sorted(glob.glob(D+'/sensors_*.csv')):
    for r in csv.DictReader(open(f)):
        try: rows.append([int(r['t_us']),*(float(r[c]) for c in ('imu_ax_g','imu_ay_g','imu_az_g','imu_gx_dps','imu_gy_dps','imu_gz_dps'))])
        except: pass
X=np.array(rows);X=X[np.argsort(X[:,0])];t=X[:,0]/1e6
print(len(X),t.min(),t.max(),'dt med',np.median(np.diff(t)))
np.save('imu.npy',X)
# stop detection in finestre da 2 s
acc=X[:,1:4];gy=X[:,4:7]
w=100;stops=[]
for i in range(0,len(X)-w,w):
    a=acc[i:i+w];g=gy[i:i+w]
    if np.linalg.norm(a.std(0))<0.01 and g.std(0).max()<0.6:stops.append((t[i],a.mean(0),g.mean(0)))
print('finestre ferme',len(stops))
for s in stops[:6]:print(round(s[0]),s[1].round(3),np.linalg.norm(s[1]).round(3),s[2].round(2))
st=np.array([np.r_[s[0],s[1],s[2]] for s in stops]);np.save('stops.npy',st)
print('bias gyro mediana stop (dps)',np.median(st[:,4:7],0).round(2),'sd',st[:,4:7].std(0).round(2))
for lo,hi in((0,150),(150,300),(300,600),(600,870),(870,1470)):
    q=st[(st[:,0]>=lo)&(st[:,0]<hi)]
    if len(q):print(lo,hi,len(q),'g_media',q[:,1:4].mean(0).round(3),'bias',q[:,4:7].mean(0).round(2))

# ===== file: imu2.py =====
import numpy as np,pickle,cv2
X=np.load('imu.npy');t=X[:,0]/1e6;bias=np.array([-1.0,0.85,-0.94])
D=pickle.load(open('rig5.pkl','rb'));out=D['out']
import pickle as pk
S=pk.load(open('rig.pkl','rb'))['S'];tk={s['k']:s for s in S}
pairs=pk.load(open('pairs.pkl','rb'));T=np.array([p[0][0]/1e6 for p in pairs])
G=[];V=[];ts=[]
for o in out:
    t0=o['t0'];t1=T[o['k']+8]
    m=(t>=t0)&(t<t1)
    if m.sum()<15:continue
    g=np.radians(X[m,4:7]-bias).sum(0)*0.02*(t1-t0)/(0.02*m.sum())  # integrale ~ somma*dt
    G.append(g);V.append(o['rot']);ts.append(t0)
G=np.array(G);V=np.array(V);ts=np.array(ts)
print(len(G),'|g| med deg',np.degrees(np.linalg.norm(G,axis=1)).round(2)[:12],'|v| med',np.degrees(np.linalg.norm(V,axis=1)).round(2)[:12])
print('varianza per asse IMU (deg^2)',np.degrees(G).var(0).round(2),' visual',np.degrees(V).var(0).round(2))
def kabsch(A,B,w=None):
    # R tale che B ~ R A
    H=(A*(1 if w is None else w[:,None])).T@B;U,S,Vt=np.linalg.svd(H);d=np.sign(np.linalg.det(Vt.T@U.T));Dm=np.diag([1,1,d]);return Vt.T@Dm@U.T
idx=np.arange(len(G));tr=idx%2==0;te=~tr
best=None
for sg in(1,-1):
    Vs=sg*V
    # solo set con rotazione apprezzabile
    R=kabsch(G[tr],Vs[tr]);pred=G[te]@R.T
    err=np.degrees(np.linalg.norm(pred-Vs[te],axis=1));base=np.degrees(np.linalg.norm(Vs[te],axis=1))
    print('segno',sg,'TEST err mediano %.3f deg (|v| med %.3f)'%(np.median(err),np.median(base)),'residuo ratio',np.median(err)/np.median(base))
    print('   R=',R.round(3).tolist())
    if best is None or np.median(err)<best[0]:best=(np.median(err),sg,R)
np.save('imu_best.npy',np.r_[best[1],best[2].ravel()])

print('---- finale')
Vs=-V
R=kabsch(G,Vs);err=np.degrees(np.linalg.norm(G@R.T-Vs,axis=1));print('R tutti',R.round(3).tolist(),'err med %.3f p90 %.3f'%(np.median(err),np.percentile(err,90)))
rng=np.random.default_rng(0);ang=[]
for _ in range(200):
    i=rng.integers(0,len(G),len(G));Rb=kabsch(G[i],Vs[i]);ang.append(np.degrees(np.linalg.norm(cv2.Rodrigues(Rb@R.T)[0])))
print('bootstrap scostamento rotazione deg: med %.2f p95 %.2f'%(np.median(ang),np.percentile(ang,95)))
# ortogonalizza e confronta con permutazione ideale
Pm=np.array([[0,-1,0],[-1,0,0],[0,0,-1.]]);print('angolo da permutazione ideale deg',np.degrees(np.linalg.norm(cv2.Rodrigues(R@Pm.T)[0])).round(2))
st=np.load('stops.npy')
import pickle
sel=st[(st[:,0]>150)&(st[:,0]<900)]
up=(sel[:,1:4]/np.linalg.norm(sel[:,1:4],axis=1)[:,None])@R.T   # nel frame rettificato sx
pitch=np.degrees(np.arcsin(up[:,2]));roll=np.degrees(np.arcsin(up[:,0]))
print('stop (n=%d): elevazione asse ottico (rett) %.2f deg [p10 %.2f p90 %.2f], roll %.2f [%.2f %.2f]'%(len(sel),np.median(pitch),*np.percentile(pitch,[10,90]),np.median(roll),*np.percentile(roll,[10,90])))
np.save('R_imu_rect.npy',R)

# ===== file: bins.py =====
from rig3 import *
import pickle
d0=0.0;f=f0
bins=[(2,4),(4,7),(7,10),(10,15),(15,25)]
K={b:[] for b in bins};KZ={i:[] for i in range(9)};dirs=[];sp=[]
def kfit(P0,R,tt,c_,e_):
    def r(k):
        P1=(k[0]*P0)@R.T+tt
        return np.r_[(proj(P1,f)-c_).ravel(),(proj(P1-np.array([B,0,0]),f)-e_).ravel()]
    s=least_squares(r,[1.0],loss='soft_l1',f_scale=1.0);return s.x[0]
for s in S:
    o=inner(s,d0,f,zmax=25)
    if not o:continue
    x=o[2];R=cv2.Rodrigues(x[:3].reshape(3,1))[0];tt=x[3:]
    if np.linalg.norm(tt)<0.5:continue
    a,b,c,e=s['a'],s['b'],s['c'],s['e']
    P0=P3(a[:,0],a[:,1],a[:,0]-b[:,0],d0,f);ok=(P0[:,2]>1.5)&(P0[:,2]<25)
    P0,c_,e_,a_=P0[ok],c[ok],e[ok],a[ok]
    fw=-R.T@tt;dirs.append(fw/np.linalg.norm(fw));sp.append(np.linalg.norm(tt)/0.5)
    for bn in bins:
        m=(P0[:,2]>=bn[0])&(P0[:,2]<bn[1])
        if m.sum()>=12:K[bn].append(kfit(P0[m],R,tt,c_[m],e_[m]))
    m=(P0[:,2]>=3)&(P0[:,2]<15)
    z=np.clip((a_[:,1]/720*3).astype(int),0,2)*3+np.clip((a_[:,0]/1280*3).astype(int),0,2)
    for i in range(9):
        mm=m&(z==i)
        if mm.sum()>=10:KZ[i].append(kfit(P0[mm],R,tt,c_[mm],e_[mm]))
ref=np.median(K[(4,7)])
print('rapporto scala locale k (1=coerente col moto globale), relativo a 4-7 m:')
for bn in bins:
    v=np.array(K[bn]);print(bn,'n sets',len(v),'k med %.3f  rel %.3f  IQR %.3f-%.3f'%(np.median(v),np.median(v)/ref,*np.percentile(v,[25,75])))
print('zone (3-15 m):');
for i in range(9):
    v=np.array(KZ[i]);print(i,len(v),'k %.3f rel %.3f'%(np.median(v),np.median(v)/ref) if len(v) else 'vuoto')
dirs=np.array(dirs);m=np.median(dirs,0);print('direzione avanzamento (rett sx) med',m.round(3),'yaw %.2f deg pitch %.2f deg'%(np.degrees(np.arctan2(m[0],m[2])),np.degrees(np.arctan2(-m[1],m[2]))),'n',len(dirs))
print('velocita med (scala B=200mm) m/s',np.median(sp).round(2),'p90',np.percentile(sp,90).round(2))
pickle.dump(dict(K={str(k):v for k,v in K.items()},KZ=KZ,ref=ref,fw=m.tolist(),sp=sp),open('bins.pkl','wb'))

# ===== file: dyzone.py =====
from rig import *
import pickle
ch=pickle.load(open('chains.pkl','rb'));pairs=pickle.load(open('pairs.pkl','rb'))
DY=[];ZN=[];Zs=[]
for c in ch:
    k,t0,t1,L0,R0,L1,Rp1,mv=c
    if mv<10:continue   # in moto
    for A,Bp in((L0,R0),(L1,Rp1)):
        a=rect(A,K1,d1,RR1);b=rect(Bp,K2,d2,R2);d=a[:,0]-b[:,0];ok=d>2
        DY.append((b[ok,1]-a[ok,1]));ZN.append(np.clip((a[ok,1]/720*3).astype(int),0,2)*3+np.clip((a[ok,0]/1280*3).astype(int),0,2));Zs.append(f0*B/(d[ok]+0.4))
DY=np.concatenate(DY);ZN=np.concatenate(ZN);Zs=np.concatenate(Zs)
a=abs(DY);print('IN MOTO (set con scorrimento>10px): n',len(a),'dy med %.2f p95 %.2f'%(np.median(a),np.percentile(a,95)),'segno medio %.2f'%np.median(DY))
zs={}
for i in range(9):
    m=ZN==i;zs[i]=(int(m.sum()),round(float(np.median(a[m])),2),round(float(np.percentile(a[m],95)),2),round(float(np.median(DY[m])),2));print('zona',i,zs[i])
for lo,hi in((1,3),(3,6),(6,10),(10,20)):
    m=(Zs>=lo)&(Zs<hi);print('Z',lo,hi,int(m.sum()),'dy med %.2f p95 %.2f'%(np.median(a[m]),np.percentile(a[m],95)))
pickle.dump(zs,open('dyzone.pkl','wb'))

# ===== file: control.py =====
from rig import *
import pickle
from dec import clip
pairs=pickle.load(open('pairs.pkl','rb'));X=np.load('imu.npy');Rimu=np.load('R_imu_rect.npy')
maps1=cv2.initUndistortRectifyMap(K1,d1,RR1,P1,(1280,720),cv2.CV_32FC1);maps2=cv2.initUndistortRectifyMap(K2,d2,R2,P1,(1280,720),cv2.CV_32FC1)
sg=cv2.StereoSGBM_create(minDisparity=0,numDisparities=192,blockSize=7,P1=8*49,P2=32*49,uniquenessRatio=8,speckleWindowSize=100,speckleRange=2,disp12MaxDiff=1,mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
def label(img,txt,x,y,sc=0.9):
    cv2.putText(img,txt,(x,y),cv2.FONT_HERSHEY_SIMPLEX,sc,(0,0,0),4,cv2.LINE_AA);cv2.putText(img,txt,(x,y),cv2.FONT_HERSHEY_SIMPLEX,sc,(255,255,255),2,cv2.LINE_AA)
tiles=[];stats=[]
for k in (10993,11982,12984):
    a,b,_=pairs[k];ia=clip(a[1])[a[2]].copy();ib=clip(b[1])[b[2]].copy()
    ra=cv2.remap(ia,*maps1,cv2.INTER_LINEAR);rb=cv2.remap(ib,*maps2,cv2.INTER_LINEAR)
    disp=sg.compute(ra,rb).astype(np.float32)/16.0
    Z=np.where(disp>3,f0*B/(disp+0.4),np.nan)
    vis=cv2.cvtColor(ra,cv2.COLOR_GRAY2BGR)
    # orizzonte da gravita' IMU (media +-0.5 s)
    tt=a[0]/1e6;m=(X[:,0]/1e6>tt-0.5)&(X[:,0]/1e6<tt+0.5);acc=X[m,1:4].mean(0);up=Rimu@(acc/np.linalg.norm(acc))
    xs=np.array([0,1279]);ys=cy-((xs-cx)*up[0]+f0*up[2])/up[1]
    cv2.line(vis,(0,int(ys[0])),(1279,int(ys[1])),(0,255,255),2,cv2.LINE_AA);label(vis,'orizzonte (IMU, +-5 gradi)',10,int(min(ys))-8,0.7)
    n=0
    for yy in range(70,720,90):
        for xx in range(80,1280,160):
            patch=Z[yy-18:yy+18,xx-18:xx+18]
            v=patch[np.isfinite(patch)]
            if len(v)>=0.5*patch.size and np.median(v)<30:
                label(vis,'%.1f m'%np.median(v),xx-35,yy,0.8);n+=1;cv2.circle(vis,(xx,yy),4,(0,0,255),-1)
    print(k,'etichette',n,'t=%.0f'%tt,'up',up.round(3))
    tiles.append(cv2.resize(vis,(1000,563)))
out=np.vstack(tiles)
D='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/logger02_giro_20261123/controllo_distanze.jpg'
cv2.imwrite(D,out,[cv2.IMWRITE_JPEG_QUALITY,85]);print(out.shape)

# ===== file: plate.py =====
from rig import *
import pickle
from dec import clip
pairs=pickle.load(open('pairs.pkl','rb'))
maps1=cv2.initUndistortRectifyMap(K1,d1,RR1,P1,(1280,720),cv2.CV_32FC1);maps2=cv2.initUndistortRectifyMap(K2,d2,R2,P1,(1280,720),cv2.CV_32FC1)
def rectpair(k):
    a,b,_=pairs[k];ia=clip(a[1])[a[2]].copy();ib=clip(b[1])[b[2]].copy()
    return cv2.remap(ia,*maps1,cv2.INTER_LINEAR),cv2.remap(ib,*maps2,cv2.INTER_LINEAR)
if __name__=='__main__':
    ra,rb=rectpair(10993)
    c=ra[400:500,640:800];d=rb[400:500,640:800]
    cv2.imwrite('plate_L.png',cv2.resize(c,None,fx=6,fy=6,interpolation=cv2.INTER_CUBIC))
    print(ra.shape)

# ===== file: plate3.py =====
from plate import *
import json
def disp(ra,rb,cx,cy,hw,hh):
    tpl=ra[cy-hh:cy+hh,cx-hw:cx+hw];out=[]
    x0=max(cx-hw-200,0)
    res=cv2.matchTemplate(rb[cy-hh:cy+hh,x0:cx+hw+20],tpl,cv2.TM_CCOEFF_NORMED)[0]
    j=int(res.argmax());v=res[j]
    if 0<j<len(res)-1:
        a,b,c=res[j-1],res[j],res[j+1];s=j+0.5*(a-c)/(a-2*b+c)
    else:s=j
    return (cx-hw)-(x0+s),float(v)
ref,_=rectpair(11720);tpl0=ref[424:480,521:860].astype(np.float32);WREF=322.0;WOUT=339.0
def search(ra,scales):
    best=(-1,None,None)
    for s in scales:
        t=cv2.resize(tpl0,None,fx=s,fy=s,interpolation=cv2.INTER_AREA)
        if t.shape[0]<10 or t.shape[1]<20:continue
        r=cv2.matchTemplate(ra.astype(np.float32),t,cv2.TM_CCOEFF_NORMED);_,mv,_,ml=cv2.minMaxLoc(r)
        if mv>best[0]:best=(mv,s,ml)
    return best
rows=[]
for k in (11346,11420,11500,11570,11651,11720,11760,11800):
    try: ra,rb=rectpair(k)
    except Exception as e: print(k,'err',e);continue
    coarse=search(ra,np.geomspace(0.12,1.2,28))
    if coarse[1] is None or coarse[0]<0.5: print(k,'non trovata',coarse[0]);continue
    s0=coarse[1];fine=search(ra,np.linspace(s0*0.93,s0*1.07,15))
    mv,s,(x,y)=fine
    # affina scala per parabola
    ss=np.linspace(s0*0.93,s0*1.07,15);sc=[]
    for q in ss:
        t=cv2.resize(tpl0,None,fx=q,fy=q,interpolation=cv2.INTER_AREA);r=cv2.matchTemplate(ra.astype(np.float32),t,cv2.TM_CCOEFF_NORMED);sc.append(r.max())
    i=int(np.argmax(sc))
    if 0<i<len(ss)-1:
        a,b,c=sc[i-1],sc[i],sc[i+1];s=ss[i]+0.5*(a-c)/(a-2*b+c)*(ss[1]-ss[0])
    w=WREF*s
    th,tw=int(tpl0.shape[0]*s),int(tpl0.shape[1]*s)
    cxp=x+tw//2;cyp=y+th//2
    hw=max(int(tw*0.3),8);hh=max(int(th*0.25),4)
    d,v=disp(ra,rb,cxp,cyp,hw,hh)
    r=dict(k=k,zncc_scala=round(float(mv),2),scala=round(float(s),3),w_px=round(float(w),1),disp=round(float(d),2),zncc_disp=round(v,2),Z_stereo=round(float(1236.26*0.2/(d+0.4)),2),Z_targa=round(float(1236.26*0.52/w),2),B_eff_mm=round(float(520*(d+0.4)/w),1),x=int(cxp),y=int(cyp))
    rows.append(r);print(r)
b=np.array([r['B_eff_mm'] for r in rows if r['zncc_scala']>0.85]);print('B_eff (zncc>0.85) n=%d media %.1f mediana %.1f sd %.1f'%(len(b),b.mean(),np.median(b),b.std()))
json.dump(rows,open('plate_rows.json','w'))

# ===== file: height.py =====
from plate import *
import json
T=np.array([p[0][0]/1e6 for p in pairs])
sg=cv2.StereoSGBM_create(minDisparity=0,numDisparities=192,blockSize=7,P1=8*49,P2=32*49,uniquenessRatio=8,speckleWindowSize=100,speckleRange=2,disp12MaxDiff=1,mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
f=f0;Bn=0.2;rng=np.random.default_rng(11)
ts=list(np.arange(472,575,5))+list(np.arange(660,870,5))
res=[]
for t in ts:
    k=int(np.argmin(abs(T-t)));ra,rb=rectpair(k)
    disp=sg.compute(ra,rb).astype(np.float32)/16.0
    yy,xx=np.mgrid[470:710:3,150:1130:3]
    d=disp[yy,xx];ok=d>3
    Z=f*Bn/(d[ok]+0.4);u=xx[ok];v=yy[ok]
    P=np.c_[(u-cx)*Bn/(d[ok]+0.4),(v-cy)*Bn/(d[ok]+0.4),Z]
    sel=(Z>1.2)&(Z<10)
    P=P[sel]
    if len(P)<300:continue
    best=None;bn=0
    for _ in range(400):
        i=rng.choice(len(P),3,replace=False);n=np.cross(P[i[1]]-P[i[0]],P[i[2]]-P[i[0]]);nr=np.linalg.norm(n)
        if nr<1e-9:continue
        n/=nr
        if n[1]<0:n=-n
        if n[1]<0.95:continue
        h=n@P[i[0]]
        if not 0.3<h<1.8:continue
        inl=abs(P@n-h)<0.02+0.006*P[:,2]
        if inl.sum()>bn:best,bn=inl,inl.sum()
    if best is None or bn<0.35*len(P):continue
    A=np.c_[P[best],-np.ones(best.sum())];vv=np.linalg.svd(A,full_matrices=False)[2][-1];nn=vv[:3]/np.linalg.norm(vv[:3]);hh=vv[3]/np.linalg.norm(vv[:3])
    if nn[1]<0:nn,hh=-nn,-hh
    res.append(dict(t=float(t),k=k,h200=float(hh),pitch_up=float(-np.degrees(np.arcsin(nn[2]))),roll=float(np.degrees(np.arcsin(nn[0]))),inl=float(bn/len(P)),n=len(P),Zmed=float(np.median(P[best][:,2]))))
    print(res[-1])
json.dump(res,open('height.json','w'))
h=np.array([r['h200'] for r in res]);pi=np.array([r['pitch_up'] for r in res]);ro=np.array([r['roll'] for r in res])
print('frames',len(res),'h(B=200) med %.3f IQR %.3f-%.3f p10-p90 %.3f-%.3f'%(np.median(h),*np.percentile(h,[25,75]),*np.percentile(h,[10,90])))
print('pitch med %.2f IQR %.2f..%.2f ; roll med %.2f IQR %.2f..%.2f'%(np.median(pi),*np.percentile(pi,[25,75]),np.median(ro),*np.percentile(ro,[25,75])))
