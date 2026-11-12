import pickle, numpy as np, os, sys
base="out_20261112_v12_A"
for sess,parts in (("094146","abc"),("093909","def")):
    fr=[];zm={}
    for p in parts:
        d=f"{base}/{p}/session_20261109_{sess}_A"
        fr+=pickle.load(open(d+"/frames.pkl","rb")); z=np.load(d+"/zmap.npz"); zm.update({k:z[k] for k in z.files})
    fr.sort(key=lambda f:f["frame"]); out=f"{base}/session_20261109_{sess}_A"; os.makedirs(out,exist_ok=True)
    pickle.dump(fr,open(out+"/frames.pkl","wb")); np.savez_compressed(out+"/zmap.npz",**zm); print(sess,len(fr),fr[0]["frame"],fr[-1]["frame"])
