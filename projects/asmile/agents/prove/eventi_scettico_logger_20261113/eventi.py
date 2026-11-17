import numpy as np,pandas as pd,datetime as dt,os
D=os.path.dirname(os.path.abspath(__file__))
f=pd.read_csv(D+"/flusso.csv").sort_values("wall")
fl=f.groupby(f.wall.round(1)).flow.mean()
t=fl.index.values; v=pd.Series(fl.values).rolling(8,center=True,min_periods=1).mean().values
E=pd.read_csv("agents/registro_guide/frenate.csv"); E=E[E.unita=="asmile-logger001"]
rows=[]
for _,e in E.iterrows():
    day=dt.date(2026,11,9); h,m,s=map(int,e.wall.split(":")); w0=dt.datetime.combine(day,dt.time(h,m,s)).timestamp(); w1=w0+e.dur_s
    g=lambda a,b: v[(t>=a)&(t<b)].mean() if ((t>=a)&(t<b)).any() else np.nan
    pre=g(w0-2,w0); post=g(w1,w1+2); ev_=g(w0,w1)
    fer=pd.Series(v[(t>=w1)&(t<w1+2)]<0.25); ferma=bool(len(fer)>=10 and fer.rolling(10).sum().max()>=10)
    rows.append((e.classe,e.wall,e.dur_s,round(pre,2),round(post,2),round(post-pre,2),ferma))
R=pd.DataFrame(rows,columns="classe wall dur pre post d ferma".split()); print(R.to_string())
for c,g_ in R.groupby("classe"): print(c,len(g_),"flusso cala (post<pre):",(g_.d<0).sum(),"sale:",(g_.d>0).sum(),"ferma(mio):",g_.ferma.sum())
# baseline: finestre casuali 
rng=np.random.default_rng(0); d=[]
for w in rng.uniform(t.min()+3,t.max()-8,400):
    a=v[(t>=w-2)&(t<w)].mean(); b=v[(t>=w+3)&(t<w+5)].mean()
    if not np.isnan(a+b): d.append(b-a)
print("baseline cala %.2f"%np.mean(np.array(d)<0))
