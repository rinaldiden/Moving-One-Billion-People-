import pickle,sys,json
def L(d): return pickle.load(open(d+"/tracks_20261109_094146.pkl","rb"))
a,b=L(sys.argv[1]),L(sys.argv[2])
def fr(t,i):
    fid=t["cs"][i]["first"]["arc"]
    if fid is None: return None
    r=next(q for q in t["per"][i] if q["id"]==fid); return (r["fam"],round(float(r["Z"]),1),r["box"],fid)
def iou(p,q):
    x0,y0=max(p[0],q[0]),max(p[1],q[1]);x1,y1=min(p[2],q[2]),min(p[3],q[3]);i=max(0,x1-x0)*max(0,y1-y0)
    return i/((p[2]-p[0])*(p[3]-p[1])+(q[2]-q[0])*(q[3]-q[1])-i+1e-9)
ch=[]
for i,f in enumerate(a["frames"]):
    x,y=fr(a,i),fr(b,i)
    if y is None or y[1]>=5: continue
    if x is None or x[0]!=y[0] and iou(x[2],y[2])<0.5 or abs(x[1]-y[1])>0.6 and iou(x[2],y[2])<0.5: ch.append(f)
print(len(ch),"frame con NUOVO primo ostacolo <5 m (box diverso)")
runs=[];
for f in ch:
    if runs and f-runs[-1][1]<=2: runs[-1][1]=f
    else: runs.append([f,f])
print(runs)
json.dump(ch,open(sys.argv[3],"w"))
