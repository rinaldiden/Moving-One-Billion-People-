import pickle,glob,os
for d in sorted(glob.glob("out_20261112_v12_synth015_*/B")):
    p=d+"/tracks_20261109_094146.pkl"
    if not os.path.exists(p): print(d,"manca"); continue
    t=pickle.load(open(p,"rb")); fr=t["frames"]; out=[]
    for i,f in enumerate(fr):
        a=t["cs"][i]["act"]; fid=t["cs"][i]["first"]["arc"]
        r=next((q for q in t["per"][i] if q["id"]==fid),None)
        out.append((f,a["act"],None if r is None else (r["fam"],round(r["Z"],1))))
    fa=next((x for x in out if x[1]=="FRENA"),None)
    print(d.split("synth015_")[1][:-2],"primo FRENA:",fa and (fa[0],"ritardo %.2f s"%((fa[0]-2284)/15)),"| primo ostacolo f2284..2290:",[x[2] for x in out[:7]])
