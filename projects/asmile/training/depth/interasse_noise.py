"""Interasse passo 2: sigma_d MISURATO (px) dalle finestre di interasse_prep. Tre stimatori indipendenti:
 T) temporale: residuo di fit quadratico della disparita' di tracce LK su 9 fotogrammi (corretto per i gradi di liberta')
 S) spaziale: residuo di piano su patch 16x16 di SGBM validato LR
 F) campo lontano: dispersione dei pixel con Z>150 m (disparita' vera ~0)
uso: python3 interasse_noise.py <lavoro> -> stampa e salva noise.json nel lavoro"""
import sys,glob,json,numpy as np
Wk=sys.argv[1];BANDS=[(1,3),(3,7),(7,12),(12,18),(18,30),(30,1e9)]
def band(Z):
    for i,(a,b) in enumerate(BANDS):
        if a<=Z<b:return i
T=[];S=[];F=[];meta={}
for fn in sorted(glob.glob(Wk+'/win*.npz')):
    z=np.load(fn);f=float(z['f']);B=float(z['B']);d0=float(z['d0']);dd=z['dd'];tr=z['tr'];n=dd.shape[1];t=np.arange(n)-n/2
    moving=None;tag=fn[-9:-4]
    for q in range(len(dd)):
        v=~np.isnan(dd[q])
        if v.sum()<8 or not z['alive'][q]:continue
        y=dd[q][v].astype(float);x=t[v];c=np.polyfit(x,y,2);res=y-np.polyval(c,x);s=np.sqrt((res**2).sum()/(len(y)-3))
        dm=np.median(y)-d0
        if dm<1.0:continue                       # tracce a disparita' ~0: trattate dal campo lontano
        Z=f*B/dm;px,py=tr[q,0];zone=int(py//240)*3+int(px//427)
        T.append((s,dm,Z,zone,float(z['t']),abs(c[1])*n))
    D=z['D'].astype(np.float32);OK=z['OK']
    for k in range(0,n,4):
        d=D[k];ok=OK[k]
        for y0 in range(16,704,16):
            for x0 in range(32,1250,16):
                m=ok[y0:y0+16,x0:x0+16]
                if m.sum()<200:continue
                p=d[y0:y0+16,x0:x0+16][m];yy,xx=np.nonzero(m)
                A=np.c_[np.ones(len(p)),xx,yy];c=np.linalg.lstsq(A,p,rcond=None)[0];r=p-A@c
                if np.abs(r).max()>3:continue    # salti di profondita'/bordi
                dm=p.mean()-d0
                if dm<1:continue
                S.append((np.sqrt((r**2).sum()/(len(p)-3)),dm,f*B/dm,int((y0)//240)*3+int(x0//427)))
        far=d[ok&(d-d0<1.5)&(d-d0>-3)]
        if far.size>2000:F.append((far.mean()-d0,far.std(),np.percentile(np.abs(far-np.median(far)),95),far.size,float(z['t'])))
T=np.array(T);S=np.array(S)
def stat(a,bands):
    out={}
    for i,(lo,hi) in enumerate(BANDS):
        m=np.array([band(Z)==i for Z in bands]) if len(bands) else None
        s=a[m] if m is not None and m.any() else []
        if len(s)>=20:out[f'{lo}-{hi}']=dict(n=int(len(s)),med=round(float(np.median(s)),3),p95=round(float(np.percentile(s,95)),3))
    return out
res=dict(temporale=stat(T[:,0],T[:,2]),spaziale=stat(S[:,0],S[:,2]))
zn={}
for zz in range(9):
    mt=T[:,3]==zz;ms=S[:,3]==zz
    zn[zz]=dict(T=[int(mt.sum()),round(float(np.median(T[mt,0])),3) if mt.any() else None,round(float(np.percentile(T[mt,0],95)),3) if mt.any() else None],
                S=[int(ms.sum()),round(float(np.median(S[ms,0])),3) if ms.any() else None,round(float(np.percentile(S[ms,0],95)),3) if ms.any() else None])
res['zone_3x3']=zn
res['temporale_tracce_ferme_vs_moto']={'ferme(<0.5px di deriva)':[int((T[:,5]<0.5).sum()),round(float(np.median(T[T[:,5]<0.5,0])),3)],'moto':[int((T[:,5]>=0.5).sum()),round(float(np.median(T[T[:,5]>=0.5,0])),3)]}
F=np.array(F);res['campo_lontano']=dict(n_finestre_frame=len(F),media_d_vera_px=round(float(F[:,0].mean()),3),std_px_med=round(float(np.median(F[:,1])),3),std_px_p95=round(float(np.percentile(F[:,1],95)),3),p95abs_med=round(float(np.median(F[:,2])),3))
json.dump(res,open(Wk+'/noise.json','w'),indent=1);print(json.dumps(res,indent=1))
