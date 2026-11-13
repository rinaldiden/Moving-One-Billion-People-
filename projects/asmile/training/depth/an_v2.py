import pickle,sys,collections
G="out_20261113_giri"; N=sys.argv[1]
segs=["frenata1","frenata2_monovolume","controsole_a","controsole_b","controsole_c"]
tot=collections.Counter()
for sg in segs:
    import glob
    fn=glob.glob(f"{N}/video_{sg}/tracks_*.pkl")[0]; d=pickle.load(open(fn,"rb"))
    c=collections.Counter()
    for f,cs in zip(d["frames"],d["cs"]):
        a=cs["act"]; act=a["act"] if a else None
        c["n"]+=1; c[str(act)]+=1
        if act=="FRENA" and a["Z"]<1: c["FRENA<1"]+=1
        if cs.get("nm") and cs["nm"][2]: c["NM"]+=1
    print(sg,dict(c)); tot.update(c)
print("TOT",dict(tot))
