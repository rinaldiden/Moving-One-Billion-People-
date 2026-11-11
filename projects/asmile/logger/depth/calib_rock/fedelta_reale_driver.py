import sys,glob,json,os,cv2,numpy as np
sys.path.insert(0,"."); sys.path.insert(0,"..")
import fedelta, render, autocal
S=sys.argv[1]
board=render.make_board("A2_11x8_50mm"); det=autocal.make_detector(board)
cand=[]
for s in sorted(x for x in os.listdir(S+"/fr") if os.path.isdir(S+"/fr/"+x)):
    for f in sorted(os.listdir(f"{S}/fr/{s}/left")):
        cand.append((s,f))
pairs=[];info=[]
for s,f in cand:
    vr=cv2.imread(f"{S}/fr/{s}/left/{f}",0); vl=cv2.imread(f"{S}/fr/{s}/right/{f}",0)  # video_left = destra fisica
    a=autocal._detect(det,board,vl); b=autocal._detect(det,board,vr)
    if a is None or b is None: continue
    if len(a["ids"])>=25 and len(b["ids"])>=25:
        pairs.append((vl,vr)); info.append((s,f,len(a["ids"]),len(b["ids"])))
print("coppie valide",len(pairs),"su",len(cand),flush=True)
idx=np.linspace(0,len(pairs)-1,min(70,len(pairs))).astype(int)
sel=[pairs[i] for i in idx]
# pairs = (phys-left, phys-right): video_right=phys-left, video_left=phys-right -> invertire
pass
r=fedelta.compare(sel,sys.argv[2],"A2_11x8_50mm")
r["sessioni"]={s:sum(1 for i in info if i[0]==s) for s in set(i[0] for i in info)}
json.dump(r,open(sys.argv[3],"w"),indent=1); print(json.dumps(r,indent=1))
