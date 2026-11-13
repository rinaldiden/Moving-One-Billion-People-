import sys,csv,datetime;sys.path.insert(0,'.')
from logger_guide import *
ep=lambda s: datetime.datetime.fromisoformat(s).timestamp()
RIDES={'r1':('2026-11-09T10:50:10','2026-11-09T10:55:15'),'r2':('2026-11-09T11:09:05','2026-11-09T11:14:40')}
which=sys.argv[1]
a,b=RIDES[which]
s=speed_series('20261109_100554',ep(a),ep(b))
with open(f'/private/tmp/claude-501/-Users-danielerinaldi-progetti-Moving-One-Billion-People-/1b32ebd7-24f0-43c1-a686-c4879d52bcb7/scratchpad/vis_{which}.csv','w') as f:
    w=csv.writer(f);w.writerow(['wall','v','n']);w.writerows(s)
print(which,len(s))
