"""Punti di fuga ortogonali sul giro2 con filtri di condizionamento (VP finiti 0.4-8 unita', >=8 rette ciascuno, angolo VP-VP 55-125 gradi dal centro, residuo 0.7 gradi).
q = f_vera/f_K. Riporta mediana/MAD per scena e bootstrap a livello di SCENA (non di fotogramma: i fotogrammi vicini non sono indipendenti)."""
import os,sys,json,numpy as np
sys.path.insert(0,os.path.dirname(__file__))
import v1_vp as V
rng=np.random.default_rng(0);res=[]
for t,pcs in sorted(V.frames.items()):
    lines=[V.fit_line(p) for p in pcs];lines=[l for l in lines if l is not None]
    if len(lines)<16: continue
    r1=V.ransac(lines,rng,thr=np.sin(np.radians(0.7)))
    if r1 is None: continue
    v1,in1=r1;rest=[l for l,k in zip(lines,in1) if not k]
    if len(rest)<8: continue
    r2=V.ransac(rest,rng,thr=np.sin(np.radians(0.7)))
    if r2 is None: continue
    v2,in2=r2;n1,n2=int(in1.sum()),int(in2.sum());a1,a2=np.linalg.norm(v1),np.linalg.norm(v2);dot=v1@v2
    cosang=dot/(a1*a2+1e-9)
    if min(n1,n2)>=8 and 0.4<a1<8 and 0.4<a2<8 and dot<-0.3 and cosang<-0.1: res.append((t,float(np.sqrt(-dot)),n1,n2,float(a1),float(a2)))
R=np.array(res);print('fotogrammi accettati',len(R))
out=dict(n=len(R))
if len(R)>=5:
    q=R[:,1];t=R[:,0];sc=(t//60).astype(int)  # scena = blocco da 60 s
    print('q med %.3f MAD*1.48 %.3f  p25-75 %.3f-%.3f'%(np.median(q),1.4826*np.median(abs(q-np.median(q))),*np.percentile(q,[25,75])))
    u=sorted(set(sc));med={int(s):round(float(np.median(q[sc==s])),3) for s in u};print('q per scena(60 s):',{s:(int((sc==s).sum()),med[s]) for s in u})
    bs=[np.median([np.median(q[sc==s]) for s in rng.choice(u,len(u))]) for _ in range(1000)];print('bootstrap per scena: q %.3f +- %.3f -> f %.0f +- %.0f px (f_K=%.0f)'%(np.mean(bs),np.std(bs),V.Kc[0][0]*np.mean(bs)*1.1006,V.Kc[0][0]*np.std(bs)*1.1006,V.Kc[0][0]))
    out.update(q_med=float(np.median(q)),q_mad=float(1.4826*np.median(abs(q-np.median(q)))),q_scene_boot_mean=float(np.mean(bs)),q_scene_boot_sd=float(np.std(bs)),n_scene=len(u),q_per_scena=med)
json.dump(out,open(os.path.join(os.environ['L02W'],'vp_filtrato.json'),'w'),indent=1)
