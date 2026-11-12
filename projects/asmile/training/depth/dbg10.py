import sys, os, pickle, numpy as np
import video_fluido_001 as V
from ego_001 import Ego
sess="session_20261109_094146"; A=V.OUT_A
frames=pickle.load(open(os.path.join(A,sess+"_A","frames.pkl"),"rb")); zm=np.load(os.path.join(A,sess+"_A","zmap.npz")); st=np.load(os.path.join(V.D.HERE,"out_20261112_v10","stuff_20261109_094146.npz"))
ego=Ego(sess); per=V.run_tracking(frames,ego,V.load_famv2(sess)); cs=V.corridor_logic(per,frames,ego,zm,st)
for f in map(int,sys.argv[1:]):
    i=[x["frame"] for x in frames].index(f); b=cs[i]["bord"]["bf"]
    print(f,"v",round(cs[i]["v"],1),"k",round(cs[i]["k"],3),"par/front pts",b["par"],b["front"],"zl",round(b["zl"],1))
    for s_ in "LR": print(" ",s_,"clear",b[s_]["clear"],"viol",b[s_]["viol"]); print("   ",[(round(z,1),round(x,2),round(c,2),p) for z,x,c,p in sorted(b[s_]["bins"])])
import bordi_001 as BD
f=2600; i=[x["frame"] for x in frames].index(f); rows=per[i]
print([(r["id"],r["fam"],r["src"],round(r["Z"],1),r.get("bordo"),r.get("bgeo")) for r in rows if r["Z"]<12 and not r["coast"]])
fr=frames[i]; zf=zm["f2600"]; gp=V.smooth_gp(frames,i); lab=st["f2601"] if "f2601" in st.files else st["f2600"]
ga,gvh,gb=gp; valid=BD.consistent(zf); uu=(np.arange(320)*4+2.)[None,:]; vv=(np.arange(200)*4+2.)[:,None]; Z=zf/10.
with np.errstate(all="ignore"): d=V.F_PX*V.B_M/np.where(valid,Z,1); h=V.HP*(1-ga*(vv-gvh)/d)
X=(uu-BD.CX)*Z/V.F_PX
m=valid&np.isin(lab,(6,7))&(h>=.2)&(h<=2)&(Z>=2)&(Z<=4.5)&(np.abs(X)<0.6)
ys,xs=np.nonzero(m); print("n",len(ys),"rows",np.unique(ys)[:20],"cols",xs.min() if len(xs) else None,xs.max() if len(xs) else None,"Z",np.round(np.percentile(Z[m],[5,50,95]),1) if len(ys) else None,"h",np.round(np.percentile(h[m],[5,50,95]),2) if len(ys) else None, "lab",np.unique(lab[m]))
