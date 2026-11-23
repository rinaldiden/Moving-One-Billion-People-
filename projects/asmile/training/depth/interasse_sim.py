"""Interasse passo 3: tabella errore-distanza (sigma_d misurato), prova dy sul SGBM reale, simulazione su oggetti reali, immagine.
uso: python3 interasse_sim.py <giro_dir> <calib.json> <lavoro> <out_prefix_rapporti>"""
import sys,os,json,glob,numpy as np,cv2
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import interasse_prep as P
D,calib,Wk,OUT=sys.argv[1:5];rng=np.random.default_rng(7)
nz=json.load(open(Wk+'/noise.json'));z0=np.load(Wk+'/win00.npz');f=float(z0['f']);B0=float(z0['B'])*1000;d0=float(z0['d0'])
SIG_C=0.24;SIG_P=0.61   # central = mediana tracce in moto (temporale 0.236 / spaziale 0.22); pessimista = p95 spaziale
res={}
# 1) formula con sigma misurato
tab={}
for B in(200,150,100):
    for Z in(2,5,10,15,20):
        d=f*B/1000/Z;tab[f'B{B}_Z{Z}']=dict(d_px=round(d,1),**{k:round(100*Z*s/(f*B/1000),2) for k,s in(('sigC',SIG_C),('sigP',SIG_P),('sigC_bias0.5',np.hypot(SIG_C,0.5)),('sigC_bias1',np.hypot(SIG_C,1.0)))})
res['formula_pct']=tab
# 2) prova dy sul SGBM reale (finestre in moto)
Wl=P.windows(D,[665,765,845],9);m1,m2,_,_,_=P.rectmaps(calib);dy={}
for t,ca,ia,cb,ib in Wl:
    a=P.decode(ca,[ia[0]])[0];b=P.decode(cb,[ib[0]])[0];L=cv2.remap(a,*m1,cv2.INTER_LINEAR);R0=cv2.remap(b,*m2,cv2.INTER_LINEAR)
    for sh in(0,0.5,1.0,2.0):
        R=cv2.warpAffine(R0,np.float32([[1,0,0],[0,1,sh]]),(1280,720),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
        dl,ok=P.disp_lr(L,R,P.sgbm());m=(ok&(dl-d0>1))
        S=[]
        for y0 in range(16,704,16):
            for x0 in range(32,1250,16):
                mm=ok[y0:y0+16,x0:x0+16]
                if mm.sum()<200:continue
                p=dl[y0:y0+16,x0:x0+16][mm];yy,xx=np.nonzero(mm);A=np.c_[np.ones(len(p)),xx,yy];r=p-A@np.linalg.lstsq(A,p,rcond=None)[0]
                if abs(r).max()<=3:S.append(np.sqrt((r**2).sum()/(len(p)-3)))
        dy.setdefault(sh,[]).append((float(ok[:,100:1200].mean()),float(np.median(S)),float(np.percentile(S,95)),len(S),float(np.median(dl[m]))))
        if sh==0:ref=dl.copy();refok=ok.copy()
        else:
            both=refok&ok;dy[sh][-1]+= (float(np.median((dl-ref)[both])),)
res['dy_test']={str(k):dict(valid_LR=round(float(np.mean([x[0] for x in v])),3),sigma_spaz_med=round(float(np.mean([x[1] for x in v])),3),sigma_spaz_p95=round(float(np.mean([x[2] for x in v])),3),n_patch=int(np.mean([x[3] for x in v])),bias_disp_px=round(float(np.mean([x[5] for x in v])),3) if k else 0) for k,v in dy.items()}
# 3) oggetti: (nome, finestra, x0,x1,y0,y1) full-res
OBJ=[('bollard sx (marciapiede)',7,240,310,370,700),('furgone sx',7,185,345,330,480),('palazzo dx (muro)',7,700,960,60,320),
('fioriera dx 1',9,1070,1260,320,470),('fioriera dx 2',9,880,990,320,420),('camion bianco dx',9,1090,1260,30,240),
('auto grigia dx',10,1000,1260,220,350),('auto lontana al centro',10,565,650,310,375),('vetrina/muro sx',10,175,415,95,480),
('siepe/muro dx',12,840,1260,320,430),('pilastro sx vicolo',14,536,608,0,640),('muro dx vicolo',3,800,960,100,640),
('arco in fondo al vicolo',3,500,720,190,460),('muro sx vicolo stretto',2,200,700,100,500),('blocco cemento dx',11,840,1100,300,450),
('muretto sx',11,0,160,320,480)]
ks=sorted({o[1] for o in OBJ});tmap={7:715,9:765,10:790,12:845,14:945,3:610,2:585,11:815}
rows=[]
for nm,k,x0,x1,y0,y1 in OBJ:
    z=np.load(f'{Wk}/win{k:02d}.npz');d=z['D'][0].astype(np.float32)[y0:y1,x0:x1]-d0;ok=z['OK'][0][y0:y1,x0:x1]&(d>1.5)
    if ok.sum()<200:print('scarto',nm,ok.sum());continue
    v=d[ok];m=np.median(v);v=v[abs(v-m)<0.15*m];dref=float(np.median(v));Zref=f*B0/1000/dref
    r=dict(nome=nm,win=k,Z200_m=round(Zref,1),d200_px=round(dref,1),npx=int(len(v)))
    for B in(200,150,100):
        for tag,sg,bs in(('c',SIG_C,0),('p',SIG_P,0),('c_b05',SIG_C,0.5),('c_b1',SIG_C,1.0)):
            n=20000;dm=dref*B/200+rng.normal(0,sg,n)+(rng.uniform(-bs,bs,n) if bs else 0)
            Ze=f*B/1000/np.maximum(dm,0.05);e=np.abs(Ze-Zref)/Zref*100
            r[f'B{B}_{tag}']=(round(float(np.mean(e>2))*100),round(float(np.mean(e>5))*100),round(float(np.percentile(e,95)),1))
    rows.append(r)
res['oggetti']=rows
for B in(200,150,100):
    for tag in('c','p','c_b05','c_b1'):
        a=np.array([[r[f'B{B}_{tag}'][0],r[f'B{B}_{tag}'][1],r[f'B{B}_{tag}'][2]] for r in rows]);res.setdefault('riassunto_oggetti',{})[f'B{B}_{tag}']=dict(oltre2_pct=round(float(a[:,0].mean())),oltre5_pct=round(float(a[:,1].mean())),p95_med=round(float(np.median(a[:,2])),1))
# Zmin
nmax=P.MIND+P.ND-2-d0
res['Zmin_m']={B:round(f*B/1000/nmax,2) for B in(200,150,100)}
res['f_rect']=f
json.dump(res,open(Wk+'/sim.json','w'),indent=1,default=float);print(json.dumps({k:v for k,v in res.items() if k!='oggetti'},indent=1,default=float))
for r in rows:print(r['nome'],r['Z200_m'],r['B200_c'],r['B150_c'],r['B100_c'],r['B150_c_b05'],r['B150_p'])
# 4) immagine
sc=[7,9,14];tiles=[]
def col(Z):
    c=cv2.applyColorMap(np.clip(255-Z/20*255,0,255).astype(np.uint8),cv2.COLORMAP_TURBO);c[Z==0]=0;return c
for k in sc:
    z=np.load(f'{Wk}/win{k:02d}.npz');d=z['D'][0].astype(np.float32)-d0;ok=z['OK'][0]&(d>1)
    Z200=np.where(ok,f*B0/1000/np.maximum(d,1),0)
    d150=0.75*d+np.sqrt(1-0.75**2)*SIG_C*rng.normal(size=d.shape).astype(np.float32);ok150=ok&(d150>1)
    Z150=np.where(ok150,f*0.15/np.maximum(d150,1),0)
    err=np.where(ok150,(Z150-Z200)/np.maximum(Z200,0.1)*100,np.nan);e=np.clip(np.nan_to_num(err,nan=0)*12.7+127,0,255).astype(np.uint8);ec=cv2.applyColorMap(e,cv2.COLORMAP_COOL);ec[~ok150]=0
    g=cv2.cvtColor(z['L0'],cv2.COLOR_GRAY2BGR)
    t=[g,col(Z200),col(Z150),ec]
    for i,tx in enumerate(['sinistra','Z 200 mm (SGBM)','Z 150 mm simulato','errore 150 vs 200 (+-10%)']):cv2.putText(t[i],tx,(10,30),0,1,(255,255,255),2)
    tiles.append(np.hstack([cv2.resize(x,(480,270)) for x in t]))
cv2.imwrite(OUT+'.png',np.vstack(tiles))
