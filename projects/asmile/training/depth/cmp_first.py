import pickle,sys
def L(d): return pickle.load(open(d+"/tracks_20261109_094146.pkl","rb"))
a,b=L(sys.argv[1]),L(sys.argv[2])
def fr(t,i):
    fid=t["cs"][i]["first"]["arc"]
    if fid is None: return None
    r=next(q for q in t["per"][i] if q["id"]==fid); return (fid,r["fam"],round(float(r["Z"]),1))
ch=[]
for i,f in enumerate(a["frames"]):
    x,y=fr(a,i),fr(b,i)
    if (x is None)!=(y is None) or (x and y and x[0]!=y[0]): 
        if (y and y[2]<5) or (x and x[2]<5): ch.append((f,x,y))
print(len(ch),"frame con primo ostacolo <5 m diverso")
# raggruppa per id nuovo
from collections import defaultdict
g=defaultdict(list)
for f,x,y in ch: g[y[0] if y else None].append(f)
for k,v in g.items(): print("nuovo id",k,"fam",next((y[1] for f,x,y in ch if y and y[0]==k),None),"n",len(v),"frames",v[0],"-",v[-1], "Z",[y[2] for f,x,y in ch if y and y[0]==k][:3])
