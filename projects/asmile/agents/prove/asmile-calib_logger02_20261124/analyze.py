"""Misura principale (PREREG.md): R fissa fittata sul blocco FIT (S2 t<69.6), dy su tutto il resto. uso: python3 analyze.py <lavoro>"""
import os,sys,json,glob,csv,pickle,numpy as np,cv2
sys.path.insert(0,os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/logger/depth/calib_rock/logger02_v2'))
import m2_fit_mount as m2
from m2_fit_mount import *
m2.H_=800
D=os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/logger02')
IMUTAG={'S1_bench_1403':'140339','S2_officina_1432':'143247','M_mattina_1037':'103842'}
def imu(tag):
    rows=[]
    for f in sorted(glob.glob(f'{D}/sensors_20261124_{tag}_*.csv')):
        for r in csv.DictReader(open(f)):
            try: rows.append([int(r['t_us'])/1e6]+[float(r[c]) for c in('imu_ax_g','imu_ay_g','imu_az_g','imu_gx_dps','imu_gy_dps','imu_gz_dps')])
            except Exception: pass
    return np.array(sorted(rows))
def moving(X,b):
    m=(X[:,0]>=b)&(X[:,0]<b+30)
    if m.sum()<50: return None
    g=X[m,4:7];return bool(np.abs(g-np.median(g,0)).max()>5 or X[m,1:4].std(0).mean()>0.02)
def fitR(M,A,B,mode='Rxz'):
    pf=(lambda p:np.array([p[0],0,p[1]])) if mode=='Rxz' else (lambda p:np.array([p[0],0,0]))
    n=2 if mode=='Rxz' else 1
    def res(p): K1,K2,R,T_=M.build(pf(p),'R');return sampson(K1,K2,M.d,R,T_,A,B)
    return pf(least_squares(res,np.zeros(n),loss='soft_l1',f_scale=1.0,x_scale=[0.005]*n,max_nfev=60).x)
deg=lambda p:np.degrees(cv2.Rodrigues(Rm(p))[0].ravel())
def main():
    Wk=os.path.abspath(sys.argv[1]);M=Model(json.load(open(os.path.join(Wk,'v3_800.json'))));S=pickle.load(open(os.path.join(Wk,'lr_matches.pkl'),'rb'))
    rng=np.random.default_rng(0);L=[]
    rd=lambda p,K:np.hypot((p[:,0]-K[0,2])/K[0,0],(p[:,1]-K[1,2])/K[1,1])
    for s in S:
        n=len(s['a']);i=rng.permutation(n)[:300];a=s['a'][i];b=s['b'][i];v=(rd(a,M.K1)<0.64)&(rd(b,M.K2)<0.64)
        L.append((s['sess'],s['t'],a[v],b[v]))
    I={k:imu(t) for k,t in IMUTAG.items()}
    def cat(sel):
        sel=list(sel)
        return (np.concatenate([x[2] for x in sel]),np.concatenate([x[3] for x in sel])) if sel else (np.zeros((0,2)),np.zeros((0,2)))
    fitsel=[x for x in L if x[0].startswith('S2') and x[1]<69.6];Af,Bf=cat(fitsel)
    p=fitR(M,Af,Bf);z0=np.zeros(3);dRv=deg(p);print('FIT n',len(Af),'dR xyz gradi (rispetto a v3)',np.round(dRv,4))
    out=dict(fit_block=dict(n_punti=int(len(Af)),n_coppie=len(fitsel),dR_xyz_deg_vs_v3=dRv.tolist(),par=p.tolist()))
    # finestre
    wins={}
    for x in L:
        k=(x[0],int(x[1]//30));wins.setdefault(k,[]).append(x)
    rows=[]
    for k in sorted(wins):
        sess,w=k;A,B=cat(wins[k]);mv=moving(I[sess],w*30)
        isfit=sess.startswith('S2') and w*30+30<=69.6+30 and w*30<60   # finestre 0,30 (t<60) dentro blocco FIT
        qa,qb=m2.rect_pts(M,p,'R',A,B);ok=(qa[:,0]-qb[:,0]>1)&(abs(qa[:,1]-qb[:,1])<25);zz=m2.zone(A[ok])
        zc=[int((zz==i).sum()) for i in range(9)];valid=bool(ok.sum()>=1000 and sum(c>=15 for c in zc)>=6)
        s0=m2.stats(M,z0,'R',A,B);s1=m2.stats(M,p,'R',A,B)
        rows.append(dict(sess=sess,t0=w*30,n=int(ok.sum()),moto=mv,valida=valid,fit=bool(sess.startswith('S2') and w*30<60),
            v3_med=s0['med'],v3_p95=s0['p95'],v3_segno=s0['segno'],R_med=s1['med'],R_p95=s1['p95'],R_segno=s1['segno'],zone_n=zc))
        print(sess[:2],w*30,'n',rows[-1]['n'],'moto',mv,'valida',valid,'fit' if rows[-1]['fit'] else '','| v3 med %.2f segno %.2f | R med %.2f p95 %.2f segno %.2f'%(s0['med'],s0['segno'],s1['med'],s1['p95'],s1['segno']))
    out['finestre']=rows
    def pool(f,tag):
        sel=[x for x in L if f(x)];
        if not sel: return None
        A,B=cat(sel);o=dict(n=int(len(A)),R=m2.stats(M,p,'R',A,B),v3=m2.stats(M,z0,'R',A,B));print(tag,'n',o['n'],'v3 med %.2f p95 %.2f | R med %.2f p95 %.2f'%(o['v3']['med'],o['v3']['p95'],o['R']['med'],o['R']['p95']));return o
    keyv={(r['sess'],r['t0']):r for r in rows}
    def vv(x,mov=True,sess=None):
        r=keyv[(x[0],int(x[1]//30)*30)];return r['valida'] and not r['fit'] and r['moto']==mov and (sess is None or x[0].startswith(sess))
    out['pool_verdetto_moto_S2']=pool(lambda x:vv(x,True,'S2'),'VERDETTO moto S2 (tenuti fuori)')
    out['pool_verdetto_moto_S1']=pool(lambda x:vv(x,True,'S1'),'moto S1 (360-450 maneggio)')
    out['pool_verdetto_moto_tutti']=pool(lambda x:vv(x,True),'VERDETTO moto tutti')
    out['pool_ferme_valide_S1']=pool(lambda x:vv(x,False,'S1'),'ferme valide S1')
    out['pool_ferme_valide_S2']=pool(lambda x:vv(x,False,'S2'),'ferme valide S2')
    out['pool_mattina_debole']=pool(lambda x:x[0].startswith('M'),'MATTINA (2 clip, debole)')
    # salti
    vs=[r for r in rows if r['valida'] and not r['sess'].startswith('M')];jumps=[]
    for a,b in zip(vs,vs[1:]):
        if a['sess']==b['sess'] and b['t0']-a['t0']==30: jumps.append((a['sess'][:2],a['t0'],round(b['R_segno']-a['R_segno'],2)))
    out['salti_R']=jumps;mx=max([abs(j[2]) for j in jumps],default=None);print('salti >1px:',[j for j in jumps if abs(j[2])>1],'max',mx)
    # Rx per blocco 60 s
    blocks={}
    for x in L:
        if x[0].startswith('M'): continue
        blocks.setdefault((x[0],int(x[1]//60)),[]).append(x)
    rx=[]
    for k in sorted(blocks):
        A,B=cat(blocks[k])
        if len(A)<2000: continue
        pp=fitR(M,A,B,'Rx');rx.append(dict(sess=k[0],t0=k[1]*60,n=int(len(A)),Rx_deg_vs_v3=float(deg(pp)[0])))
    out['rx_per_blocco']=rx
    for r in rx: print('Rx',r['sess'][:2],r['t0'],r['n'],'%.4f'%r['Rx_deg_vs_v3'])
    v=[r['Rx_deg_vs_v3'] for r in rx];out['rx_range_deg']=float(max(v)-min(v));print('Rx max-min',out['rx_range_deg'])
    json.dump(out,open(os.path.join(Wk,'analisi.json'),'w'),indent=1,default=float)
main()
