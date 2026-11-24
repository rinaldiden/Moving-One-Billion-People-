"""ROUND 2 punto 2 (PREREG.md): R_imu->camera per blocco, Procrustes fra rotazioni giroscopio e rotazioni visive. uso: python3 procrustes.py <gw dir con g1_matches.pkl e imu.npy>"""
import os,sys,json,pickle,numpy as np,cv2
from scipy.optimize import least_squares
gw=sys.argv[1];BIAS=np.array(json.load(open(os.path.dirname(gw.rstrip('/'))+'/w/bias.json')))
c=json.load(open(os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_logger02.CANDIDATO_v5_20261124.json')))
K=np.array(c['K_left']);d=np.array(c['dist_left']);F=1236.0
Rold=np.array(json.load(open(os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/imu_montaggio_case_v5.json')))['R_imu_to_cam_raw_A'])
M=pickle.load(open(gw+'/g1_matches.pkl','rb'));X=np.load(gw+'/imu.npy');t=X[:,0]/1e6
def integ(t0,t1):
    i0=np.searchsorted(t,t0);i1=np.searchsorted(t,t1);R=np.eye(3)
    for i in range(i0,i1):
        w=np.radians(X[i,4:7]-BIAS);dt=(min(t[i+1],t1)-max(t[i],t0)) if i+1<len(t) else 0.02;R=R@cv2.Rodrigues(w*max(dt,0))[0]
    return R
rv=lambda R:cv2.Rodrigues(R)[0].ravel()
rows=[]
for m in M:
    xa=cv2.undistortPointsIter(m['a'].reshape(-1,1,2).astype(np.float64),K,d,None,None,(cv2.TERM_CRITERIA_COUNT|cv2.TERM_CRITERIA_EPS,40,1e-10)).reshape(-1,2);xb=cv2.undistortPointsIter(m['b'].reshape(-1,1,2).astype(np.float64),K,d,None,None,(cv2.TERM_CRITERIA_COUNT|cv2.TERM_CRITERIA_EPS,40,1e-10)).reshape(-1,2)
    E,inl=cv2.findEssentialMat(xa,xb,focal=1.0,pp=(0,0),method=cv2.RANSAC,prob=0.999,threshold=1.0/F)
    if E is None or E.shape!=(3,3): continue
    n,Rv,tv,_=cv2.recoverPose(E,xa,xb,focal=1.0,pp=(0,0),mask=inl.copy())
    if n<40: continue
    rows.append((m['t0'],rv(Rv),rv(integ(m['t0'],m['t1'])),int(n)))
print('coppie con rotazione visiva',len(rows),'di',len(M),flush=True)
T0=np.array([r[0] for r in rows]);V=-np.array([r[1] for r in rows]);G=np.array([r[2] for r in rows]);wt=np.linalg.norm(G,axis=1)  # V = -rotvec_vis = s Rc g
def kabsch(G,V,w):
    H=(G*w[:,None]).T@V;U,S,Vt=np.linalg.svd(H);D=np.diag([1,1,np.sign(np.linalg.det(Vt.T@U.T))]);R=Vt.T@D@U.T;s=float(np.sum(w*np.sum(V*(G@R.T),1))/np.sum(w*np.sum(G*G,1)));return R,s
ang=lambda Ra,Rb:float(np.degrees(np.linalg.norm(rv(Ra@Rb.T))))
def err(G,V,R,s): return np.degrees(np.linalg.norm(V-s*(G@R.T),axis=1))
def sbest(G,V,R): return float(np.sum(np.sum(V*(G@R.T),1))/np.sum(np.sum((G@R.T)**2,1)))
def rel(G,V,R,s): return float(np.median(err(G,V,R,s)))
# prima: segno/convenzione con la Rc vecchia
for sg in (1,-1): print('Rc vecchia, segno',sg,'errore mediano gradi',round(rel(G,V*sg,Rold,sbest(G,V*sg,Rold)),3),'s',round(sbest(G,V*sg,Rold),3))
Rn,sn=kabsch(G,V,wt);out=dict(n=len(rows),angolo_Rnuova_vs_Rv5case_deg=ang(Rn,Rold),s_isotropa_nuova=sn,s_vecchia=sbest(G,V,Rold),err_med_deg_vecchia=rel(G,V,Rold,sbest(G,V,Rold)),err_med_deg_nuova=rel(G,V,Rn,sn))
print({k:round(v,3) if isinstance(v,float) else v for k,v in out.items()})
ev=(T0//60).astype(int)%2==0;od=~ev;o2={}
for tag,tr,te in(('fit_pari_test_dispari',ev,od),('fit_dispari_test_pari',od,ev)):
    R_,s_=kabsch(G[tr],V[tr],wt[tr]);eo=rel(G[te],V[te],Rold,sbest(G[te],V[te],Rold));en=rel(G[te],V[te],R_,s_);o2[tag]=dict(err_vecchia=eo,err_nuova=en,calo_pct=100*(eo-en)/eo,angolo_vs_vecchia=ang(R_,Rold),s=s_);print(tag,{k:round(v,3) for k,v in o2[tag].items()})
out['heldout']=o2
# per blocco
bl=[]
for b in sorted(set((T0//60).astype(int))):
    k=(T0//60).astype(int)==b
    if k.sum()<20: continue
    R_,s_=kabsch(G[k],V[k],wt[k]);u,sv,_=np.linalg.svd((G[k]*wt[k][:,None]).T@V[k]);bl.append(dict(t0=int(b*60),n=int(k.sum()),angolo_vs_vecchia=ang(R_,Rold),angolo_vs_globale=ang(R_,Rn),s=s_,cond=float(sv[0]/sv[2]),rotvec_deg=np.degrees(rv(R_@Rold.T)).round(2).tolist()));print('blocco',bl[-1])
out['blocchi']=bl;ad=np.array([b['angolo_vs_globale'] for b in bl]);out['dispersione_blocchi_med_max_deg']=[float(np.median(ad)),float(ad.max())]
# pendenze per asse camera (Rc vecchia e nuova)
for nm,R_ in(('vecchia',Rold),('nuova',Rn)):
    P=G@R_.T;out['pendenza_asse_cam_'+nm]=[float(np.sum(P[:,i]*V[:,i])/np.sum(P[:,i]**2)) for i in range(3)]
print('pendenze per asse cam (x,y,z) vecchia',np.round(out['pendenza_asse_cam_vecchia'],3),'nuova',np.round(out['pendenza_asse_cam_nuova'],3),'dispersione blocchi',out['dispersione_blocchi_med_max_deg'])
# ESPLORATIVO post-hoc (dichiarato): pendenze per asse camera con Rc vecchia, pari/dispari; q=s_imbardata/s_rollio (rollio indipendente da f)
P=G@Rold.T;sl=lambda k:[float(np.sum(P[k,i]*V[k,i])/np.sum(P[k,i]**2)) for i in range(3)]
out['esplorativo_pendenze_pari']=sl(ev);out['esplorativo_pendenze_dispari']=sl(od)
for nm,v in(('pari',out['esplorativo_pendenze_pari']),('dispari',out['esplorativo_pendenze_dispari']),('tutti',out['pendenza_asse_cam_vecchia'])): print('ESPL',nm,'x,y,z',np.round(v,3),'q=y/z %.3f  x/z %.3f'%(v[1]/v[2],v[0]/v[2]))
out['Rc_nuova']=Rn.tolist();out['Rc_vecchia']=Rold.tolist();json.dump(out,open('procrustes.json','w'),indent=1)
