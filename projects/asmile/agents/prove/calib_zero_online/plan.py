import numpy as np, pandas as pd
A='/Users/danielerinaldi/progetti/Moving-One-Billion-People-/projects/asmile/asmile-loggers/asmile-001/'
fr=pd.read_csv(A+'session_20261109_094146/frames_right.csv')   # file right = sinistra fisica
s=pd.read_csv(A+'_sensors/sensors/sensors_20261109_085334.csv',usecols=['t_ms','enc_wheel_cum'])
s=s.dropna()
cum=np.interp(fr.t_ms,s.t_ms,s.enc_wheel_cum)
print(len(fr),fr.t_ms.iloc[0],s.t_ms.iloc[0],s.t_ms.iloc[-1])
d=np.diff(cum);print('ticks/frame stats',np.percentile(abs(d),[10,50,90,99]))
tot=abs(cum[-1]-cum[0]);print('ticks totali',tot)
# gps check
g=pd.read_csv(A+'_sensors/sensors/sensors_20261109_085334.csv',usecols=['t_ms','gps_speed_ms']).dropna()
m=(g.t_ms>=fr.t_ms.iloc[0])&(g.t_ms<=fr.t_ms.iloc[-1]);print('gps dist m',g.gps_speed_ms[m].mean()*(fr.t_ms.iloc[-1]-fr.t_ms.iloc[0])/1000, 'metri enc se 0.3374/4096:',tot*0.3374/4096)
np.save('cum.npy',cum)
