import numpy as np,pandas as pd,datetime as dt,os
D=os.path.dirname(os.path.abspath(__file__)); L="asmile-loggers/asmile-logger/_sensors/sensors/"
f=pd.read_csv(D+"/flusso.csv").sort_values("wall"); f=f.groupby(f.wall.round(1)).flow.mean()
t=f.index.values; v=pd.Series(f.values).rolling(5,center=True,min_periods=1).mean().values
s=pd.concat([pd.read_csv(L+n,usecols=["wall","imu_ax_g"]) for n in ["sensors_20261109_101007.csv","sensors_20261109_111007.csv"]])
s["w"]=s.wall.map(lambda x:dt.datetime.fromisoformat(x).timestamp()); s=s.sort_values("w")
ax=(s.imu_ax_g*9.81); ax=(ax-ax.rolling(750,center=True,min_periods=1).median()).rolling(25,center=True,min_periods=1).mean().values; aw=s.w.values
A=lambda a,b: ax[(aw>=a)&(aw<b)].mean()
still=v<0.15; mov=v>0.6
for kind in ("stop","start"):
    out=[]
    for i in range(30,len(t)-30):
        if kind=="stop" and still[i] and not still[i-1] and mov[i-30:i-5].mean()>0.7 and still[i:i+15].all(): out.append(t[i])
        if kind=="start" and mov[i] and not mov[i-1] and still[i-30:i-1].all() and mov[i:i+15].mean()>0.7: out.append(t[i])
    clean=[]
    for x in out:
        if not clean or x-clean[-1]>5: clean.append(x)
    vals=[A(x-2.5,x-0.3) if kind=="stop" else A(x-0.5,x+2) for x in clean]
    print(kind,len(clean),[ (dt.datetime.fromtimestamp(x).strftime("%H:%M:%S"),round(v_,2)) for x,v_ in zip(clean,vals)])
    print("  mediana ax(m/s2)=%.2f  segni+/-: %d/%d"%(np.median(vals),sum(np.array(vals)>0),sum(np.array(vals)<0)))
