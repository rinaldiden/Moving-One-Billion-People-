"""Misure AUTOMATICHE su tutta la sessione, senza finestre ne' semi del giro di oggi.
 far : d0 dai punti lontanissimi = match L-R SOPRA l'orizzonte IMU (riga calcolata dalla gravita' col montaggio v5), campionati ogni 1.5 s;
       istogramma delle disparita': primo picco (il piu' lontano) con >=60 punti, >=6 fotogrammi distinti, >=2 gruppi temporali (>20 s) e mediane per fotogramma stabili.
 plates: rilevatore a rettangolo (rapporto 520:110 => box 4.0-5.6, testo, contrasto, coerenza stereo wL~wR dL~dR dy) ogni 0.5 s -> catene temporali (>=3 viste
       consecutive, crescita di scala coerente) -> seme = vista di maggior contrasto -> inseguitore a template multi-scala -> regressione d=(B/520)w-d0."""
import os,sys,json,pickle,numpy as np,cv2
sys.path.insert(0,os.path.dirname(__file__))
from rect import *
from s4_plates import candidates,measure_plate,width3d,text_ok
from s4_track import run as track_run
Rimu=np.array(json.load(open(IMUJ))['R_imu_to_cam_rettificata_sx'])
def horizon(S,X,t):
    ti=X[:,0]/1e6;m=(ti>t-0.5)&(ti<t+0.5)
    if m.sum()<5: return None
    a=X[m,1:4].mean(0);up=Rimu@(a/np.linalg.norm(a));xs=np.arange(size()[0])
    if abs(up[1])<0.2: return None
    return S['cy']-((xs-S['cx'])*up[0]+S['f']*up[2])/up[1]
def auto_far(S,P,T,X,dt=1.5):
    sift=cv2.SIFT_create(nfeatures=1500,contrastThreshold=0.01);bf=cv2.BFMatcher();rows=[];nfr=0
    for t in np.arange(T.min()+5,T.max()-1,dt):
        k=int(np.argmin(abs(T-t)))
        hy=horizon(S,X,T[k])
        if hy is None: continue
        ymax=np.clip(hy-20,0,size()[1]-20).astype(int)
        if ymax.mean()<40: continue
        ra,rb=rectpair(S,P,k)
        if ra.mean()<25: continue
        m=np.zeros_like(ra)
        for x in range(8,size()[0]-8): m[8:max(ymax[x],8),x]=255
        if m.sum()/255<3000: continue
        nfr+=1;ka,da=sift.detectAndCompute(ra,m);kb,db=sift.detectAndCompute(rb,m)
        if da is None or db is None or len(ka)<10 or len(kb)<10: continue
        mt=bf.knnMatch(da,db,k=2);bk=bf.knnMatch(db,da,k=1)
        for q in mt:
            if len(q)==2 and q[0].distance<0.75*q[1].distance and bk[q[0].trainIdx][0].trainIdx==q[0].queryIdx:
                a=ka[q[0].queryIdx].pt;b=kb[q[0].trainIdx].pt
                if abs(a[1]-b[1])<1.0: rows.append((T[k],a[0],a[1],a[0]-b[0]))
    r=np.array(rows);out=dict(trovato=False,n_fotogrammi_sopra_orizzonte=nfr,n_match=int(len(r)))
    if len(r)<100: out['motivo']='troppi pochi punti sopra l\'orizzonte (niente colline/cielo con testura)';return out
    bins=np.arange(-10,25,0.5);h,e=np.histogram(r[:,3],bins=bins);hs=np.convolve(h,[1,2,1],'same')/4
    for i in range(1,len(h)-1):
        if hs[i]>=hs[i-1] and hs[i]>=hs[i+1] and h[max(i-1,0):i+2].sum()>=60:
            c=0.5*(e[i]+e[i+1]);sel=r[abs(r[:,3]-c)<1.2];c=np.median(sel[:,3]);sel=r[abs(r[:,3]-c)<1.2]
            ts=np.unique(sel[:,0]);pm=np.array([np.median(sel[sel[:,0]==t,3]) for t in ts if (sel[:,0]==t).sum()>=5])
            grp=1+int(np.sum(np.diff(np.sort(ts))>20))
            if len(pm)>=6 and grp>=2 and pm.std()<0.8:
                out.update(trovato=True,d0=float(np.median(sel[:,3])),n_punti=int(len(sel)),n_fotogrammi=int(len(pm)),gruppi_temporali=grp,sd_per_fotogramma=float(pm.std()),
                    per_x={f'{a}-{b}':float(np.median(sel[(sel[:,1]>=a)&(sel[:,1]<b),3])) for a,b in((0,430),(430,850),(850,size()[0])) if ((sel[:,1]>=a)&(sel[:,1]<b)).sum()>=15})
                return out
    out['motivo']='nessun picco di disparita\' stabile (>=60 punti, >=6 fotogrammi, >=2 gruppi temporali)';return out
def detect_plates(S,P,T,step=5):
    dets=[]
    for k in range(0,len(P),step):
        ra,rb=rectpair(S,P,k)
        if ra.mean()<25: continue
        for bx in candidates(ra):
            x,y,w,h=map(int,bx)
            if not(4.0<w/h<5.6) or w<70: continue
            if text_ok(ra,y+int(.3*h),y+int(.7*h),x,x+w)<8: continue
            m=measure_plate(ra,rb,bx,S['f'])
            if m is None or m['ntext']<10 or m['ncc']<0.8 or abs(m['dy'])>3: continue
            if abs(m['wL']-m['wR'])>0.03*m['wL'] or abs(m['dL']-m['dR'])>0.04*m['dL']+1.0: continue
            w3=width3d(m,S)
            if w3 is None or abs(w3[1])>12: continue
            sharp=float(np.mean(np.abs(cv2.Sobel(ra[y:y+h,x:x+w],cv2.CV_32F,1,0))));dets.append(dict(k=int(k),t=float(T[k]),box=(x,y,w,h),contr=sharp,wL=m['wL'],xl=m['xl'],xr=m['xr'],yc=m['yc']))
    return dets
def chains(dets,gap=1.5,minlen=3):
    ch=[]
    for d in sorted(dets,key=lambda d:d['t']):
        for c in ch:
            l=c[-1]
            if 0<d['t']-l['t']<=gap and 0.6<d['wL']/l['wL']<1.6 and abs((d['box'][0]+d['box'][2]/2)-(l['box'][0]+l['box'][2]/2))<0.8*max(d['box'][2],l['box'][2]): c.append(d);break
        else: ch.append([d])
    return sorted([c for c in ch if len(c)>=minlen],key=lambda c:-len(c))
def auto_plates(S,P,T):
    dets=detect_plates(S,P,T);ch=chains(dets)
    out=dict(trovato=False,n_rilevazioni=len(dets),n_catene=len(ch))
    if not ch: out['motivo']='nessuna targa (rettangolo 520x110 con testo e coerenza stereo) tracciata su >=3 fotogrammi';return out
    res=[];sc=[]
    for c in ch[:3]:
        seed=max(c,key=lambda d:d['contr']);wv=seed['xr']-seed['xl']
        box=(int(seed['xl']-0.15*wv),int(seed['yc']-0.135*wv),int(1.25*wv),int(0.27*wv))   # rettangolo canonico portatarga (stesso schema del seme manuale)
        rr=track_run(S,P,T,c[0]['t']-4,c[-1]['t']+4,seed['k'],box)
        from s4_fit_lib import good,regress
        G=good(rr);rg=regress(G) if len(G)>=12 else None
        sc.append(dict(t0=c[0]['t'],t1=c[-1]['t'],seed_t=seed['t'],seed_box=list(box),n_catena=len(c),n_inseguite=len(rr),n_buone=len(G),risultato=rg))
    ok=[x for x in sc if x['risultato']]
    out.update(catene=sc)
    pl=[x for x in ok if 160<=x['risultato']['B_mm']<=240]    # plausibilita' meccanica (progetto 200 mm +-20%): scarta catene su oggetti non-targa
    if not pl: out['motivo']='nessuna catena con >=12 viste buone, scala x1.5 e B plausibile (160-240 mm)';return out
    Bs=np.array([x['risultato']['B_mm'] for x in pl]);w=np.array([x['risultato']['n_viste'] for x in pl],float)
    out.update(trovato=True,B_mm=float(np.sum(Bs*w)/w.sum()),B_boot_sd=float(np.sqrt(np.sum(w*np.array([x['risultato']['B_boot_sd'] for x in pl])**2)/w.sum())),
        B_spread_catene_mm=float(Bs.max()-Bs.min()),n_viste=int(w.sum()),n_catene_usate=len(pl),B_per_catena=[float(b) for b in Bs],B_sist_mm=3.5+0.5*float(Bs.max()-Bs.min()))
    return out
if __name__=='__main__':
    S=load();P=pairs();T=np.array([p[0][0]/1e6 for p in P]);X=imu()
    what=sys.argv[1]
    o=auto_far(S,P,T,X) if what=='far' else auto_plates(S,P,T)
    json.dump(o,open(os.path.join(W,f'auto_{what}.json'),'w'),indent=1);print(json.dumps(o,indent=1))
