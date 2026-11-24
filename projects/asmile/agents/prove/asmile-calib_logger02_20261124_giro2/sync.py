"""Sync A/B giro2 24/11: A=162459, B=162506. Solo CSV. Righe B dopo l'ultimo reset di t_a_us (salto <-1 s). Salva pairs.pkl (formato common.make_pairs) in $L02W e sync.json."""
import glob,csv,json,pickle,os,numpy as np
D=os.path.expanduser('~/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/logger02');TA='162459';TB='162506'
def rows(side,tag,col):
    o=[]
    for f in sorted(glob.glob(f'{D}/clip_20261124_{tag}_{side}_*_frames.csv')):
        for i,r in enumerate(csv.DictReader(open(f))): o.append((int(r[col]),f.replace('_frames.csv','.h264'),i,int(r['frame'])))
    return o
def build():
    A=rows('A',TA,'t_us');B=rows('B',TB,'t_a_us');tb0=np.array([r[0] for r in B]);drop=np.where(np.diff(tb0)<-1e6)[0]
    if len(drop): B=B[drop[-1]+1:]
    B=sorted(B,key=lambda r:r[0]);ta=np.array([r[0] for r in A]);tb=np.array([r[0] for r in B])
    j=np.clip(np.searchsorted(tb,ta),1,len(tb)-1);jj=np.where(abs(tb[j]-ta)<abs(tb[j-1]-ta),j,j-1);dt=tb[jj]-ta
    return A,B,ta,tb,[(A[i],B[jj[i]],dt[i]) for i in range(len(A))],len(drop)
if __name__=='__main__':
    A,B,ta,tb,P,nd=build();ad=abs(np.array([p[2] for p in P]))/1e3;off=np.array([p[0][3]-p[1][3] for p in P])
    mod=np.array([np.median(off[max(0,i-50):i+51]) for i in range(len(off))]);v,c=np.unique(off,return_counts=True)
    res=dict(reset_B=nd,n_A=len(A),n_B=len(B),t_A=[ta[0]/1e6,ta[-1]/1e6],t_B=[tb[0]/1e6,tb[-1]/1e6],absdt_med_ms=float(np.median(ad)),absdt_p95_ms=float(np.percentile(ad,95)),absdt_max_ms=float(ad.max()),frac_gt1ms=float((ad>1).mean()),offset_frame={int(a):int(b) for a,b in zip(v,c)},frac_sfasato=float((off!=mod).mean()))
    print(json.dumps(res));json.dump(res,open('sync.json','w'),indent=1)
    W=os.environ['L02W'];os.makedirs(W,exist_ok=True);inB=np.array([p[0][0]>=tb[0] for p in P]);good=[p for p in P if abs(p[2])<=100]
    tt=np.array([p[0][0]/1e6 for p in P]);dd=np.array([p[2] for p in P])/1e3
    res['soglia_us']=100;res['coppie_tot_A']=len(P);res['coppie_tenute']=len(good);res['pct_scartate']=100*(1-len(good)/len(P));res['pct_scartate_dopo_16.7s']=100*(1-len(good)/inB.sum())
    res['dt_per_intervallo_ms']={f'{a}-{b}s':[round(float(np.median(abs(dd[(tt>=a)&(tt<b)]))),3),round(float(np.percentile(abs(dd[(tt>=a)&(tt<b)]),95)),3),round(float(abs(dd[(tt>=a)&(tt<b)]).max()),3)] for a,b in((8,17),(17,30),(30,60),(60,130),(130,400),(400,830))}
    gd=np.array([abs(p[2]) for p in good])/1e3;res['tenute_dt_ms_med_p95_max']=[float(np.median(gd)),float(np.percentile(gd,95)),float(gd.max())]
    res['primo_t_tenuto_s']=float(min(p[0][0] for p in good)/1e6)
    print(json.dumps({k:v for k,v in res.items() if k!='offset_frame'}));json.dump(res,open('sync.json','w'),indent=1)
    pickle.dump(good,open(W+'/pairs.pkl','wb'))
