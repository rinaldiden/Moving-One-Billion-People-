"""Sync A/B logger02 24/11: solo CSV (nessun dy). uso: python3 sync.py"""
import glob,csv,json,numpy as np,os
D=os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/logger02')
SESS={'S1_bench_1403':('140339','140323'),'S2_officina_1432':('143247','143252'),'M_mattina_1037':('103842','103743'),'N_notte_0011':('001138','001117')}
def rows(side,tag):
    out=[]
    for f in sorted(glob.glob(f'{D}/clip_20261124_{tag}_{side}_*_frames.csv')):
        clip=f.replace('_frames.csv','.h264')
        for i,r in enumerate(csv.DictReader(open(f))): out.append((int(r['t_us' if side=='A' else 't_a_us']),clip,i,int(r['frame'])))
    return out
def pairs(ta_,tb_):
    A=rows('A',ta_);B=sorted(rows('B',tb_),key=lambda r:r[0]);ta=np.array([r[0] for r in A]);tb=np.array([r[0] for r in B])
    j=np.clip(np.searchsorted(tb,ta),1,len(tb)-1);jj=np.where(abs(tb[j]-ta)<abs(tb[j-1]-ta),j,j-1)
    return [dict(t=ta[i]/1e6,dt=(tb[jj[i]]-ta[i])/1e3,a=A[i][1:3],b=B[jj[i]][1:3],fa=A[i][3],fb=B[jj[i]][3]) for i in range(len(A))]
def sfasati(P,w=101):
    off=np.array([p['fa']-p['fb'] for p in P]);med=np.array([np.median(off[max(0,i-w//2):i+w//2+1]) for i in range(len(off))]);return off,off!=med
if __name__=='__main__':
    res={}
    for k,(a,b) in SESS.items():
        P=pairs(a,b);dt=np.array([p['dt'] for p in P]);off,sf=sfasati(P);ad=abs(dt)
        res[k]=dict(n=len(P),dt_med_ms=float(np.median(dt)),abs_med_ms=float(np.median(ad)),abs_p95_ms=float(np.percentile(ad,95)),abs_max_ms=float(ad.max()),
          frac_abs_gt5=float((ad>5).mean()),frac_abs_gt10=float((ad>10).mean()),frac_abs_gt30=float((ad>30).mean()),frac_frame_sfasato=float(sf.mean()),offsets={int(o):int((off==o).sum()) for o in np.unique(off)})
        print(k,json.dumps(res[k]))
    json.dump(res,open('sync.json','w'),indent=1)
