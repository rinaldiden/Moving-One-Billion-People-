import numpy as np,pandas as pd,datetime as dt,os
D=os.path.dirname(os.path.abspath(__file__)); L="asmile-loggers/asmile-logger/_sensors/sensors/"
f=pd.read_csv(D+"/flusso.csv")
s=pd.concat([pd.read_csv(L+n,usecols=["t_ms","wall","imu_ax_g","imu_gz_dps"]) for n in ["sensors_20261109_101007.csv","sensors_20261109_111007.csv"]])
s["w"]=s.wall.map(lambda x:dt.datetime.fromisoformat(x).timestamp()); s=s.drop_duplicates("t_ms").sort_values("w")
# nota: wall del hub vs mtime clip: offset ignoto, lo stimo per correlazione
for ride,(a,b) in {"1050":("2026-11-09T10:50:10","2026-11-09T10:55:15"),"1109":("2026-11-09T11:09:05","2026-11-09T11:14:40")}.items():
    fr=f[f.ride==int(ride)].sort_values("wall"); fr=fr[fr.wall>=dt.datetime.fromisoformat(a).timestamp()]
    t0=fr.wall.min(); t1=fr.wall.max()
    t=np.arange(t0,t1,0.1)
    fl=np.interp(t,fr.wall,fr.flow.rolling(8,center=True,min_periods=1).mean())
    ss=s[(s.w>t0-5)&(s.w<t1+5)]
    ax=np.interp(t,ss.w,ss.imu_ax_g.values*9.81); ax=ax-pd.Series(ax).rolling(150,center=True,min_periods=1).median().values
    ax=pd.Series(ax).rolling(10,center=True,min_periods=1).mean().values
    fls=pd.Series(fl).rolling(10,center=True,min_periods=1).mean().values
    dfl=np.gradient(fls,0.1)
    res=[]
    for lag in np.arange(-1.5,1.51,0.25):
        k=int(round(lag*10)); x=np.roll(ax,k)
        res.append((lag,np.corrcoef(dfl[20:-20],x[20:-20])[0,1]))
    print(ride,"corr(d flusso/dt, ax) per lag:",[(round(l,2),round(c,2)) for l,c in res])
    # transizioni
    mov=fls>np.percentile(fls,30)*0+0.25
    print(" frazione moto",mov.mean().round(2),"flow pct10/50/90",np.percentile(fls,[10,50,90]).round(2))
    # stop: moto>=3s poi fermo >=2s
    ev=[]
    i=0
    while i<len(t)-60:
        if mov[i-30 if i>=30 else 0:i+1].all() and i>=30 and not mov[i+1:i+21].any():
            ev.append(("stop",i)); i+=60
        elif i>=20 and (not mov[i-20:i+1].any()) and mov[i+1:i+31].all():
            ev.append(("start",i)); i+=60
        else: i+=1
    for kind,i in ev:
        w=slice(max(i-20,0),i) if kind=="stop" else slice(i,i+20)
        print("  ",kind,dt.datetime.fromtimestamp(t[i]).strftime("%H:%M:%S"),"ax medio 2s=%.2f"%ax[w].mean(),"picco=%.2f"%(ax[w][np.argmax(np.abs(ax[w]))]))
    st=[ax[max(i-20,0):i].mean() for k,i in ev if k=="stop"]; sr=[ax[i:i+20].mean() for k,i in ev if k=="start"]
    print(" stop n=%d media ax %.2f ; start n=%d media ax %.2f"%(len(st),np.mean(st) if st else np.nan,len(sr),np.mean(sr) if sr else np.nan))
