import pandas as pd, numpy as np
d=pd.read_pickle('hz1.pkl')
d['good']=(d.decl.values==False)&(d.sosp.values==False); print(d.good.sum())
d['mov']=d.v>0.3
for n,sg in {'in125-215':(125,215),'out230-320':(230,320),'tutto fuori 125-215':None,'0-125':(0,125),'320+':(320,999)}.items():
    s=d[(d.ts<125)|(d.ts>215)] if sg is None else d[(d.ts>=sg[0])&(d.ts<sg[1])]
    print(n,'campioni',s.frame.nunique())
    t=s[s.veh&s.good&(s.dm<=1.5)]
    print(' veic/pers (Z<25) entro1.5m da traiett reale:',len(t),'| fuori v6 curvo:',(~t.v6).sum(),'| fuori curvo+dritto(1.5+.03Z):',(~t.v6s).sum(),'| fuori v7:',(~t.v7).sum())
    t=s[(s.Z<5)&s.good&(s.dm<=1.5)]
    print(' ostacoli <5m in percorso reale:',len(t),'fuori v7:',(~t.v7).sum(),'| frames con almeno uno:',t.frame.nunique(),'frames senza nessuno in corridoio v7:',sum(1 for f,g in t.groupby('frame') if not g.v7.any()))
