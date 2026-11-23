"""Dopo m2_fit_mount: (1) dy(t) per blocchi di 30 s con la R del fit (deriva del montaggio nella sessione); (2) fit R sul tratto STABILE (t>=390 s) a blocchi di 60 s alterni,
verifica su blocchi tenuti fuori e sul tratto iniziale (fuori segmento); (3) ricalibrazione AUTOMATICA per blocco di 60 s (solo Rx, o Rx+Ry+Rz) su fotogrammi pari, verifica sui dispari
dello stesso blocco = quanto regge una auto-calibrazione per sessione.   uso: python3 -m logger02_v2.m3_segments <lavoro> <calib_base.json>   -> segments.json"""
import os,sys,json,numpy as np,cv2
sys.path.insert(0,os.path.dirname(__file__))
from m2_fit_mount import *
def fitR(M,A,B,mode='R',x0=None,sel=None):
    xs={'R':[0.005]*3,'Rx':[0.005]}[mode]
    def pf(p): return np.r_[p,0,0] if mode=='Rx' else p
    def res(p): K1,K2,R,T_=M.build(pf(p),'R');return sampson(K1,K2,M.d,R,T_,A,B)
    return pf(least_squares(res,np.zeros(len(xs)) if x0 is None else x0,loss='soft_l1',f_scale=1.0,x_scale=xs,max_nfev=60).x)
def main():
    Wk=os.path.abspath(sys.argv[1]);M=Model(json.load(open(sys.argv[2])));z=np.load(os.path.join(Wk,'pts.npz'));A,B,T,Wm=z['A'],z['B'],z['T'],z['Wm'];mov=Wm>15
    out={};tcut=390.0
    # (1) deriva: mediana dy con la R-del-fit-globale (mode R di m2)
    m2=json.load(open(os.path.join(Wk,'mount_fit.json')));pg=np.array(m2['R']['par']);qa,qb=rect_pts(M,pg,'R',A,B);dy=qa[:,1]-qb[:,1];d=qa[:,0]-qb[:,0];ok=(d>1)&(abs(dy)<25)
    out['deriva_dy_per_30s']={int(b):[int(((T>=b)&(T<b+30)&ok).sum()),round(float(np.median(dy[(T>=b)&(T<b+30)&ok])),2)] for b in range(120,1060,30) if ((T>=b)&(T<b+30)&ok).sum()>=500}
    # (2) fit sul tratto stabile
    st=T>=tcut;blk=(T//60).astype(int);tr=st&(blk%2==0);te=st&(blk%2==1);early=T<340
    p=fitR(M,A[tr],B[tr]);pswap=fitR(M,A[te],B[te]);z0=np.zeros(3)
    rv=lambda p_:np.degrees(cv2.Rodrigues(Rm(p_))[0].ravel())
    out['stabile']=dict(par=p.tolist(),dR_xyz_deg=rv(p).tolist(),par_swap=pswap.tolist(),dR_swap_xyz_deg=rv(pswap).tolist(),
        base_test=stats(M,z0,'R',A[te],B[te],mov[te]),fit_test=stats(M,p,'R',A[te],B[te],mov[te]),swap_test=stats(M,pswap,'R',A[tr],B[tr],mov[tr]),
        base_early=stats(M,z0,'R',A[early],B[early]),fit_early=stats(M,p,'R',A[early],B[early]),n_early=int(early.sum()))
    # (3) auto-ricalibrazione per blocco
    rows=[];allres={'Rx':[],'R':[]};base_all=[];
    for b in sorted(set(blk[T>=120])):
        m=(blk==b)&(T>=120)
        if m.sum()<4000: continue
        idx=np.where(m)[0];fr=np.unique(T[idx]);half=np.isin(T[idx],fr[::2]);I1=idx[half];I2=idx[~half]
        r=dict(blocco=int(b),n=int(m.sum()))
        for mode in('Rx','R'):
            pp=fitR(M,A[I1],B[I1],mode);s=stats(M,pp,'R',A[I2],B[I2]);r[mode]=dict(med=round(s['med'],2),p95=round(s['p95'],2),segno=round(s['segno'],2),dR_xyz_deg=[round(v,3) for v in rv(pp)])
            q1,q2=rect_pts(M,pp,'R',A[I2],B[I2]);dd=q1[:,1]-q2[:,1];allres[mode].append(abs(dd[(q1[:,0]-q2[:,0]>1)&(abs(dd)<25)]))
        s0=stats(M,z0,'R',A[I2],B[I2]);r['base']=dict(med=round(s0['med'],2),p95=round(s0['p95'],2),segno=round(s0['segno'],2));rows.append(r)
    out['auto_per_blocco']=rows
    for mode in allres: a=np.concatenate(allres[mode]);out['auto_'+mode+'_tutti']=dict(n=len(a),med=float(np.median(a)),p95=float(np.percentile(a,95)))
    json.dump(out,open(os.path.join(Wk,'segments.json'),'w'),indent=1)
    s=out['stabile'];print('STABILE (t>=390): dR xyz gradi',np.round(s['dR_xyz_deg'],3),'swap',np.round(s['dR_swap_xyz_deg'],3))
    for k in('base_test','fit_test','swap_test','base_early','fit_early'): print(' ',k,'n',s[k]['n'],'med %.2f p95 %.2f segno %.2f'%(s[k]['med'],s[k]['p95'],s[k]['segno']),s[k].get('moto'))
    print(' zone fit_test',s['fit_test']['zone']);print(' zone base_test',s['base_test']['zone'])
    for r in rows: print(r)
    print('AUTO Rx tutti',out['auto_Rx_tutti'],'\nAUTO R tutti',out['auto_R_tutti'])
main()
