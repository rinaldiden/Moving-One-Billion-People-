"""Rifit del MONTAGGIO (R relativa, T direzione, cx/cy per camera) su match L-R grezzi (m1_extract_lr). Lente fissa = quella della calib base (sx di #001).
Fit su blocchi di 60 s PARI, verifica su blocchi DISPARI (viste mai usate). Tre modelli:  C = solo cy relativo (R base);  R = solo rotazione (centri base);  RC = R + T + centri (metodo v2).
uso: python3 -m logger02_v2.m2_fit_mount <lavoro> <calib_base.json> <giro_dir>  -> mount_fit.json"""
import os,sys,json,pickle,glob,csv,numpy as np,cv2
from scipy.optimize import least_squares
W_,H_=1280,720
def undist(p,K,d,it=25):
    fx,fy,cx,cy=K[0,0],K[1,1],K[0,2],K[1,2];k1,k2,p1,p2,k3=d;xd=(p[:,0]-cx)/fx;yd=(p[:,1]-cy)/fy;x=xd.copy();y=yd.copy()
    for _ in range(it):
        r2=x*x+y*y;rad=1+k1*r2+k2*r2**2+k3*r2**3;x=(xd-(2*p1*x*y+p2*(r2+2*x*x)))/rad;y=(yd-(p1*(r2+2*y*y)+2*p2*x*y))/rad
    return np.c_[x,y]
def Rm(w): return cv2.Rodrigues(np.asarray(w,float).reshape(3,1))[0]
def skew(t): return np.array([[0,-t[2],t[1]],[t[2],0,-t[0]],[-t[1],t[0],0]])
class Model:
    def __init__(s,c): s.c=c;s.K1=np.array(c['K_left']);s.K2=np.array(c['K_right']);s.d=np.array(c['dist_left']);s.R0=np.array(c['R']);s.T0=np.array(c['T']).reshape(3);s.B=np.linalg.norm(s.T0)
    def build(s,p,mode):
        K1=s.K1.copy();K2=s.K2.copy();R=s.R0;T=s.T0.copy()
        if mode in('R','RC'): R=Rm(p[:3])@s.R0
        if mode=='RC':
            T=s.B*np.array([-1,p[3],p[4]]);T=T/np.linalg.norm(T)*s.B;K1[0,2]+=p[5];K1[1,2]+=p[6];K2[0,2]+=p[7];K2[1,2]+=p[8]
        if mode=='C': K2[1,2]+=p[0]
        return K1,K2,R,T
    def npar(s,mode): return {'C':1,'R':3,'RC':9}[mode]
def sampson(K1,K2,d,R,T,a,b):
    x1=undist(a,K1,d);x2=undist(b,K2,d);E=skew(T/np.linalg.norm(T))@R
    X1=np.c_[x1,np.ones(len(x1))];X2=np.c_[x2,np.ones(len(x2))];Ex=X1@E.T;Etx=X2@E
    return np.sum(X2*Ex,1)/np.sqrt(Ex[:,0]**2+Ex[:,1]**2+Etx[:,0]**2+Etx[:,1]**2)*K1[0,0]
def rect_pts(M,p,mode,a,b):
    K1,K2,R,T=M.build(p,mode);r=cv2.stereoRectify(K1,M.d,K2,M.d,(W_,H_),R,T.reshape(3,1),flags=cv2.CALIB_ZERO_DISPARITY,alpha=0)
    def f(q,K,Rr):
        x=undist(q,K,M.d);v=np.c_[x,np.ones(len(x))]@Rr.T;P=r[2];return np.c_[P[0,0]*v[:,0]/v[:,2]+P[0,2],P[1,1]*v[:,1]/v[:,2]+P[1,2]]
    return f(a,K1,r[0]),f(b,K2,r[1])
def zone(a): return np.clip((a[:,1]/H_*3).astype(int),0,2)*3+np.clip((a[:,0]/W_*3).astype(int),0,2)
def stats(M,p,mode,a,b,mov=None):
    qa,qb=rect_pts(M,p,mode,a,b);dy=qa[:,1]-qb[:,1];dx=qa[:,0]-qb[:,0];ok=(dx>1)&(abs(dy)<25);dy=dy[ok];z=zone(a[ok]);ad=abs(dy)
    zs=[(int((z==i).sum()),round(float(np.median(ad[z==i])),2) if (z==i).sum()>=15 else None,round(float(np.percentile(ad[z==i],95)),2) if (z==i).sum()>=15 else None) for i in range(9)]
    out=dict(n=int(ok.sum()),med=float(np.median(ad)),p95=float(np.percentile(ad,95)),segno=float(np.median(dy)),zone=zs)
    if mov is not None:
        m=mov[ok]
        if m.sum()>200: out['moto']=dict(n=int(m.sum()),med=float(np.median(ad[m])),p95=float(np.percentile(ad[m],95)),segno=float(np.median(dy[m])))
    return out
def main():
    Wk,calib,giro=map(os.path.abspath,sys.argv[1:4]);M=Model(json.load(open(calib)));S=pickle.load(open(os.path.join(Wk,'lr_matches.pkl'),'rb'))
    # giroscopio per sapere i fotogrammi in moto (|giro-bias|>15 dps), sessione 1 (la sola con stereo)
    rows=[]
    for f in sorted(glob.glob(giro+'/A/sensors_*134617*.csv')):
        for r in csv.DictReader(open(f)):
            try: rows.append([int(r['t_us'])/1e6,*(float(r[c]) for c in('imu_gx_dps','imu_gy_dps','imu_gz_dps'))])
            except Exception: pass
    X=np.array(sorted(rows));ti=X[:,0]
    def wmax(t):
        i0=np.searchsorted(ti,t-0.05);i1=np.searchsorted(ti,t+0.05);return float(np.abs(X[i0:i1,1:]-[-1,0.85,-0.94]).max()) if i1>i0 else 0.0
    rng=np.random.default_rng(0);A=[];B=[];T=[];Wm=[]
    for s in S:
        if s['sess']!=0: continue
        n=len(s['a']);i=rng.permutation(n)[:200];A.append(s['a'][i]);B.append(s['b'][i]);T.append(np.full(len(i),s['t']));Wm.append(np.full(len(i),wmax(s['t'])))
    A=np.concatenate(A);B=np.concatenate(B);T=np.concatenate(T);Wm=np.concatenate(Wm)
    # valido: r_d<0.64 su entrambe
    def rd(p,K): return np.hypot((p[:,0]-K[0,2])/K[0,0],(p[:,1]-K[1,2])/K[1,1])
    v=(rd(A,M.K1)<0.64)&(rd(B,M.K2)<0.64);A,B,T,Wm=A[v],B[v],T[v],Wm[v]
    blk=(T//60).astype(int);tr=blk%2==0;te=~tr;mov=Wm>15
    print('punti',len(A),'train',tr.sum(),'test',te.sum(),'blocchi',len(set(blk)),'in moto',mov.sum(),flush=True)
    out=dict(n_punti=int(len(A)),n_train=int(tr.sum()),n_test=int(te.sum()))
    z0=np.zeros(0);out['base']=dict(train=stats(M,z0,'C',A[tr],B[tr],mov[tr]) if False else None)
    def run(mode,Atr,Btr,seed=None):
        x0=np.zeros(M.npar(mode))
        if mode=='RC': x0[3:5]=[M.T0[1]/-M.T0[0]*-1*-1,M.T0[2]/-M.T0[0]*-1*-1]
        def res(p): K1,K2,R,T_=M.build(p,mode);return sampson(K1,K2,M.d,R,T_,Atr,Btr)
        xs={'C':[5.0],'R':[0.005]*3,'RC':[0.005]*3+[0.005]*2+[5.0]*4}[mode]
        return least_squares(res,x0,loss='soft_l1',f_scale=1.0,x_scale=xs,max_nfev=60).x
    # base (nessun fit) su test e train
    out['base']=dict(train=stats(M,np.zeros(1),'C',A[tr],B[tr],mov[tr]),test=stats(M,np.zeros(1),'C',A[te],B[te],mov[te]))
    out['base']['test_segno_nota']='dy = yL_rett - yR_rett (px)'
    for mode in('C','R','RC'):
        p=run(mode,A[tr],B[tr]);K1,K2,R,T_=M.build(p,mode);dR=R@M.R0.T;rv=cv2.Rodrigues(dR)[0].ravel();ang=np.degrees(np.linalg.norm(rv))
        # scambio blocchi (fit sui dispari, test sui pari) = secondo giro indipendente
        p2=run(mode,A[te],B[te])
        o=dict(par=p.tolist(),par_swap=p2.tolist(),train=stats(M,p,mode,A[tr],B[tr],mov[tr]),test=stats(M,p,mode,A[te],B[te],mov[te]),test_swap=stats(M,p2,mode,A[tr],B[tr],mov[tr]),
               dR_deg_xyz=np.degrees(rv).tolist(),dR_deg=float(ang))
        if mode=='RC':
            o['K1_c']=[float(K1[0,2]),float(K1[1,2])];o['K2_c']=[float(K2[0,2]),float(K2[1,2])];o['T']=T_.tolist()
        out[mode]=o
        print(mode,'par',np.round(p,4),'| dR gradi xyz',np.round(np.degrees(rv),3),'| TEST med %.2f p95 %.2f segno %.2f'%(o['test']['med'],o['test']['p95'],o['test']['segno']),'| swap med %.2f p95 %.2f'%(o['test_swap']['med'],o['test_swap']['p95']),flush=True)
    print('BASE test med %.2f p95 %.2f segno %.2f'%(out['base']['test']['med'],out['base']['test']['p95'],out['base']['test']['segno']))
    # fit finale su TUTTI i punti (per il candidato) con il modello migliore su test
    best=min(('C','R','RC'),key=lambda m:out[m]['test']['p95']+out[m]['test_swap']['p95']);out['migliore']=best
    pall=run(best,A,B);K1,K2,R,T_=M.build(pall,best);out['finale']=dict(modo=best,par=pall.tolist(),R=R.tolist(),T=T_.tolist(),K_left=K1.tolist(),K_right=K2.tolist(),dR_vs_base_deg=float(np.degrees(np.linalg.norm(cv2.Rodrigues(R@M.R0.T)[0]))),dR_xyz_deg=np.degrees(cv2.Rodrigues(R@M.R0.T)[0].ravel()).tolist())
    json.dump(out,open(os.path.join(Wk,'mount_fit.json'),'w'),indent=1);print('migliore',best)
    np.savez(os.path.join(Wk,'pts.npz'),A=A,B=B,T=T,Wm=Wm)
if __name__=='__main__': main()
