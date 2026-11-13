import sys,csv,datetime;sys.path.insert(0,'.')
from logger_guide import *
ep=lambda s: datetime.datetime.fromisoformat(s).timestamp()
R={'r1':('2026-11-09T10:50:10','2026-11-09T10:55:15'),'r2':('2026-11-09T11:09:05','2026-11-09T11:14:40')}
k=sys.argv[1];o=road_flow_series('20261109_100554',ep(R[k][0]),ep(R[k][1]))
with open(sys.argv[2],'w') as f:
    w=csv.writer(f);w.writerow(['wall','flow']);w.writerows(o)
