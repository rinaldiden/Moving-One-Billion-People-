"""Fit v5 (PREREG.md): pari/dispari + scambio, RC vs RCL, controllo su finestre ferme mai usate. uso: python3 fit.py <W>"""
import os,sys,json,pickle,numpy as np
from fitlib import *
W=sys.argv[1];S=pickle.load(open(W+'/lr_matches.pkl','rb'));M=Base();rng=np.random.default_rng(0)
rd=lambda p,K:np.hypot((p[:,0]-K[0,2])/K[0,0],(p[:,1]-K[1,2])/K[1,1]);L=[]
for s in S:
    n=len(s['a']);i=rng.permutation(n)[:250];a=s['a'][i];b=s['b'][i];v=(rd(a,M.K1)<0.64)&(rd(b,M.K2)<0.64);L.append((s['reg'],s['t'],a[v],b[v]))
cat=lambda sel:(np.concatenate([x[2] for x in sel]),np.concatenate([x[3] for x in sel]))
mov=[x for x in L if x[0]=='M'];fer=[x for x in L if x[0]=='F'];ev=[x for x in mov if int(x[1]//60)%2==0];od=[x for x in mov if int(x[1]//60)%2==1]
(Ae,Be),(Ao,Bo),(Am,Bm),(Af,Bf)=cat(ev),cat(od),cat(mov),cat(fer);print('punti pari',len(Ae),'dispari',len(Ao),'ferme',len(Af),flush=True)
o=dict(n_pari=len(Ae),n_dispari=len(Ao),n_ferme=len(Af));z=np.zeros(9)
o['v4_riferimento']=dict(dispari=stats(M,z,'RC',Ao,Bo),pari=stats(M,z,'RC',Ae,Be),ferme=stats(M,z,'RC',Af,Bf));print('v4 (pre-fuoco) dispari med %.2f p95 %.2f segno %.2f'%tuple(o['v4_riferimento']['dispari'][k] for k in('med','p95','segno')),flush=True)
P={}
for mode in('RC','RCL'):
    pe=fit(M,Ae,Be,mode);po=fit(M,Ao,Bo,mode);P[mode]=(pe,po)
    o[mode]=dict(par_pari=pe.tolist(),par_dispari=po.tolist(),test_dispari=stats(M,pe,mode,Ao,Bo),test_pari=stats(M,po,mode,Ae,Be),train_pari=stats(M,pe,mode,Ae,Be))
    print(mode,'par pari',np.round(pe,4),'\n   par dispari',np.round(po,4),'\n   TEST dispari med %.2f p95 %.2f | TEST pari med %.2f p95 %.2f'%(o[mode]['test_dispari']['med'],o[mode]['test_dispari']['p95'],o[mode]['test_pari']['med'],o[mode]['test_pari']['p95']),flush=True)
# regola RCL
rc,rl=o['RC'],o['RCL'];imp=lambda k,t:(rc[t][k]-rl[t][k])/rc[t][k]
zw=[any(a[1] and b[1] and b[1]>1.1*a[1] for a,b in zip(rc[t]['zone'],rl[t]['zone'])) for t in('test_dispari','test_pari')]
ok=all(imp(k,t)>=0.05 for k in('med','p95') for t in('test_dispari','test_pari')) and not any(zw)
mode='RCL' if ok else 'RC';o['regola_RCL']=dict(adottato=mode,miglioramento_pct={t+'_'+k:round(100*imp(k,t),1) for k in('med','p95') for t in('test_dispari','test_pari')},zone_peggiorate=zw);print('MODELLO',mode,o['regola_RCL'],flush=True)
pall=fit(M,Am,Bm,mode);o['finale']=dict(modo=mode,par=pall.tolist(),ferme=stats(M,pall,mode,Af,Bf),moto_tutto=stats(M,pall,mode,Am,Bm));print('FINALE par',np.round(pall,4),'FERME mai usate med %.2f p95 %.2f segno %.2f'%tuple(o['finale']['ferme'][k] for k in('med','p95','segno')),flush=True)
o['ferme_con_fit_pari']=stats(M,P[mode][0],mode,Af,Bf);o['ferme_con_fit_dispari']=stats(M,P[mode][1],mode,Af,Bf)
for k in('ferme_con_fit_pari','ferme_con_fit_dispari'): print(k,'med %.2f p95 %.2f'%(o[k]['med'],o[k]['p95']))
# finestre 30 s con fit pari / dispari (tenute fuori) + salti
W30={}
for x in L: W30.setdefault(int(x[1]//30)*30,[]).append(x)
rows=[]
for w in sorted(W30):
    A_,B_=cat(W30[w]);blk=int(w//60)%2;p=P[mode][1] if blk==0 else P[mode][0]  # fit sull'altra parita'
    s=stats(M,p,mode,A_,B_);rows.append(dict(t0=w,reg=W30[w][0][0],n=s['n'],med=round(s['med'],2),p95=round(s['p95'],2),segno=round(s['segno'],2)))
o['finestre30_fuori']=rows;jj=[round(b['segno']-a['segno'],2) for a,b in zip(rows,rows[1:]) if b['t0']-a['t0']==30 and a['reg']==b['reg']];o['salti_segno_max']=max(abs(v) for v in jj);print('salto max',o['salti_segno_max'])
# Rx per blocco 60 s (solo Rx, altri a finale)
bl={}
for x in L:
    if x[0]=='M': bl.setdefault(int(x[1]//60),[]).append(x)
rx=[]
for k in sorted(bl):
    A_,B_=cat(bl[k])
    if len(A_)<1500: continue
    pp=fit(M,A_,B_,mode,x0=pall,only=[0]);rx.append(dict(t0=k*60,n=int(len(A_)),Rx_deg=float(np.degrees(pp[0]-pall[0]))))
o['rx_blocchi']=rx;v=[r['Rx_deg'] for r in rx];o['rx_range_deg']=float(max(v)-min(v));print('Rx per blocco',[(r['t0'],round(r['Rx_deg'],3)) for r in rx],'range',o['rx_range_deg'])
json.dump(o,open(W+'/../fit_v5.json','w'),indent=1,default=float);pickle.dump(dict(mode=mode,par=pall,pari=P[mode][0],dispari=P[mode][1]),open(W+'/par.pkl','wb'))
