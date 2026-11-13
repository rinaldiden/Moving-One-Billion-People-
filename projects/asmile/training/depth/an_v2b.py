import pickle,glob,sys
N=sys.argv[1]
for sg in ["frenata1","frenata2_monovolume","controsole_a","controsole_b","controsole_c"]:
    d=pickle.load(open(glob.glob(f"{N}/video_{sg}/tracks_*.pkl")[0],"rb"))
    fr=[]; 
    for f,cs,rows in zip(d["frames"],d["cs"],d["per"]):
        a=cs["act"]
        if a and a["act"]=="FRENA":
            r=[x for x in rows if x["id"]==cs["first"]["arc"]][0]
            fr.append((f,round(a["Z"],1),r["fam"],r["classe"],r.get("Zdim"),r["coast"],cs["wall"]))
    print(sg,len(fr)); [print("  ",x) for x in fr]
d=pickle.load(open(glob.glob(f"{N}/video_frenata2_monovolume/tracks_*.pkl")[0],"rb"))
for f,cs in zip(d["frames"],d["cs"]):
    if f in (4440,4470,4530,4722,4580,4558,4570,4588,4603,4736): print(f,cs["wall"],cs["act"] and (cs["act"]["act"],cs["act"]["Z"] and round(cs["act"]["Z"],1)),cs["firstZ"],cs["nm"])
d=pickle.load(open(glob.glob(f"{N}/video_frenata2_monovolume/tracks_*.pkl")[0],"rb"))
print([ (f,cs["wall"],round(cs["act"]["Z"],1)) for f,cs in zip(d["frames"],d["cs"]) if cs["act"] and cs["act"]["act"]=="RALLENTA"][:40])
