import pickle,sys
from collections import Counter
t=pickle.load(open(sys.argv[1]+"/tracks_20261109_094146.pkl","rb")); print(Counter(c["act"]["act"] for c in t["cs"]))
def show(f):
    if f not in t["frames"]: return
    i=t["frames"].index(f); c=t["cs"][i]; fid=c["first"]["arc"]
    r=next((q for q in t["per"][i] if q["id"]==fid),None)
    print(f,"act",c["act"]["act"] and (c["act"]["act"],c["act"]["why"][:50]),"first",None if r is None else (r["id"],r["fam"],round(r["Z"],1),r["box"],round(r["X"],2),"wf",r.get("wf")))
for f in [int(x) for x in sys.argv[2].split(",")]: show(f)
