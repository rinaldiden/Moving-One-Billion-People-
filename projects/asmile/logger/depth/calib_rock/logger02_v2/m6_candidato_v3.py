"""Candidato v3 (giro2): R = Rm(dRx,0,dRz) @ R_base, fit sul tratto STABILE (t>=390 s) del giro2. Ry NON si fitta (invisibile al vincolo epipolare con T lungo x: sposterebbe d0 di ~3.9 px per 0.2 gradi).
Verifica 1: blocchi di 60 s alterni. Verifica 2 (indipendente dal codice di rettifica a punti): SIFT su immagini RETTIFICATE con cv2.remap, 80 coppie dei blocchi DISPARI, gate +-25 px.
uso: L02W=.. L02_GIRO=.. python3 -m logger02_v2.m6_candidato_v3 <lavoro> <base.json> <out.json>"""
import os,sys,json,numpy as np,cv2
sys.path.insert(0,os.path.dirname(__file__))
from m2_fit_mount import *
from m1_extract_lr import pairs_per_session,decode
def fit(M,A,B,mode):
    def pf(p): return np.array([p[0],0,p[1]]) if mode=='Rxz' else p
    def res(p): K1,K2,R,T_=M.build(pf(p),'R');return sampson(K1,K2,M.d,R,T_,A,B)
    n=2 if mode=='Rxz' else 3;return pf(least_squares(res,np.zeros(n),loss='soft_l1',f_scale=1.0,x_scale=[0.005]*n,max_nfev=60).x)
def rv(p): return np.degrees(cv2.Rodrigues(Rm(p))[0].ravel()).round(4).tolist()
def zrow(s): return [[z[1],z[2]] for z in s['zone']]
def main():
    Wk,base,outp=[os.path.abspath(a) for a in sys.argv[1:4]];M=Model(json.load(open(base)));z=np.load(os.path.join(Wk,'pts.npz'));A,B,T,Wm=z['A'],z['B'],z['T'],z['Wm'];mov=Wm>15
    st=T>=390;blk=(T//60).astype(int);tr=st&(blk%2==0);te=st&(blk%2==1);z0=np.zeros(3);o={}
    for mode in('Rxz','R3'):
        p=fit(M,A[tr],B[tr],mode);p2=fit(M,A[te],B[te],mode)
        o[mode]=dict(dR_xyz_deg=rv(p),dR_swap_xyz_deg=rv(p2),test=stats(M,p,'R',A[te],B[te],mov[te]),swap=stats(M,p2,'R',A[tr],B[tr],mov[tr]))
        print(mode,'dR',o[mode]['dR_xyz_deg'],'swap',o[mode]['dR_swap_xyz_deg'],'TEST med %.2f p95 %.2f | swap med %.2f p95 %.2f'%(o[mode]['test']['med'],o[mode]['test']['p95'],o[mode]['swap']['med'],o[mode]['swap']['p95']),flush=True)
    o['base_test']=stats(M,z0,'R',A[te],B[te],mov[te]);o['base_swap']=stats(M,z0,'R',A[tr],B[tr],mov[tr])
    p=fit(M,A[st],B[st],'Rxz');K1,K2,R,T_=M.build(p,'R');dRdeg=rv(p);print('FINALE (tutto lo stabile) dR xyz gradi',dRdeg)
    # verifica indipendente con remap
    c=json.load(open(base));c3=dict(c);c3['R']=R.tolist();json.dump(c3,open(os.path.join(Wk,'_v3_tmp.json'),'w'))
    import rect as RC
    P=[q for q in pairs_per_session(os.environ['L02_GIRO']) if q['sess']==0 and q['t']>=390 and (int(q['t']//60)%2==1)][::90][:90]
    sift=cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.015);bf=cv2.BFMatcher();rows={}
    for name,cal in(('base',base),('v3',os.path.join(Wk,'_v3_tmp.json'))):
        S=RC.load(cal);rr=[]
        for q in P:
            ia=decode(q['a'][0],[q['a'][1]])[q['a'][1]];ib=decode(q['b'][0],[q['b'][1]])[q['b'][1]]
            ra=cv2.remap(ia,*S['m1'],cv2.INTER_LINEAR);rb=cv2.remap(ib,*S['m2'],cv2.INTER_LINEAR);m=np.zeros_like(ra);m[8:-8,8:-8]=255
            ka,da=sift.detectAndCompute(ra,m);kb,db=sift.detectAndCompute(rb,m)
            if da is None or db is None or len(ka)<20 or len(kb)<20: continue
            ab=bf.knnMatch(da,db,k=2);ba=bf.knnMatch(db,da,k=1)
            for qq in ab:
                if len(qq)==2 and qq[0].distance<0.75*qq[1].distance and ba[qq[0].trainIdx][0].trainIdx==qq[0].queryIdx:
                    a=ka[qq[0].queryIdx].pt;b=kb[qq[0].trainIdx].pt
                    if abs(a[1]-b[1])<25 and a[0]-b[0]>1: rr.append((a[0],a[1],b[1]-a[1]))
        rr=np.array(rr);ad=abs(rr[:,2]);zz=zone(rr[:,:2]);rows[name]=dict(n=len(rr),frames=len(P),med=float(np.median(ad)),p95=float(np.percentile(ad,95)),segno=float(np.median(rr[:,2])),
            zone=[[int((zz==i).sum()),round(float(np.median(ad[zz==i])),2),round(float(np.percentile(ad[zz==i],95)),2)] for i in range(9)])
        print('REMAP',name,rows[name]['n'],'med %.2f p95 %.2f segno %.2f'%(rows[name]['med'],rows[name]['p95'],rows[name]['segno']),rows[name]['zone'],flush=True)
    o['remap_odd_blocks']=rows;o['finale']=dict(dR_xyz_deg=dRdeg,R=R.tolist());o['n_punti_fit_finale']=int(st.sum())
    json.dump(o,open(os.path.join(Wk,'candidato_v3.json'),'w'),indent=1);os.remove(os.path.join(Wk,'_v3_tmp.json'))
if __name__=='__main__': main()
