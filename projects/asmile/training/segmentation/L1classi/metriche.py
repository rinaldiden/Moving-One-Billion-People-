import json, collections
D="asmile-loggers/_seg_sam3_L1classi"
cf=json.load(open("training/segmentation/L1classi/controllo_fisso.json"))
R=[json.loads(l) for l in open(f"{D}/res_ctrl.jsonl")]
G=[json.loads(l) for l in open(f"{D}/res_gate.jsonl")]
GF=("gate","fence"); OLDC=[]
# esclusi a occhio (#001): main idx 44,46,56,57,58,59 ; riserva idx 11
exc=set()
for i in (44,46,56,57,58,59): exc.add(cf["asmile-001"][i]["frame"])
excr={cf["riserva_asmile-001"][11]["frame"]}
def cls(r,th,key="full"): return [d for d in r[key] if d["conf"]>=th]
out={}
for th in (0.45,0.70):
  for unit in ("asmile-001","asmile-logger001"):
    rs=[r for r in R if r["unit"] in (unit,"riserva_"+unit)]
    cert=[r for r in rs if not ((r["unit"]=="asmile-001" and r["frame"] in exc) or (r["unit"]=="riserva_asmile-001" and r["frame"] in excr))]
    ex=[r for r in rs if r not in cert]
    fp=[r for r in cert if any(d["c"] in GF for d in cls(r,th))]
    cf_=collections.Counter(); co=collections.Counter()
    for r in cert:
        for d in cls(r,th,"full"):
            if d["c"] not in GF: cf_[d["c"]]+=1
        for d in cls(r,th,"old"): co[d["c"]]+=1
    diff={c:(co[c],cf_[c]) for c in sorted(set(co)|set(cf_))}
    tot_o,tot_f=sum(co.values()),sum(cf_.values())
    out[f"{unit}@{th}"]=dict(n_cert=len(cert),n_esclusi=len(ex),falsi_frame=len(fp),pct=round(100*len(fp)/len(cert),2),
        falsi_dettaglio=[(r["video"][-9:-5] if unit!="asmile-001" else "",r["frame"],[(d["c"],d["conf"]) for d in cls(r,th) if d["c"] in GF]) for r in fp],
        esclusi_con_gatefence=sum(1 for r in ex if any(d["c"] in GF for d in cls(r,th))),
        vecchie_old_vs_full=diff,tot_old=tot_o,tot_full=tot_f,delta_tot_pct=round(100*(tot_f-tot_o)/max(tot_o,1),2),
        max_delta_classe_pct=max([(abs(b-a)/a*100 if a else (100 if b else 0), c) for c,(a,b) in diff.items()] or [(0,'')]))
for th in (0.30,0.45,0.70):
    n=len(G); ok=sum(1 for r in G if any(d["c"] in GF and d["conf"]>=th for d in r["full"]))
    cov=sum(1 for r in G if any(d["c"] in GF and d["conf"]>=th and (d["box"][2]-d["box"][0])*(d["box"][3]-d["box"][1])>=0.5*1280*800 for d in r["full"]))
    oldpole=sum(1 for r in G if any(d["c"]=="pole" and d["conf"]>=th for d in r["old"]))
    out[f"gate@{th}"]=dict(n=n,gate_o_fence=ok,box_ge50pct=cov,old_con_pole=oldpole)
    out[f"gate@{th}"]["solo_gate"]=sum(1 for r in G if any(d["c"]=="gate" and d["conf"]>=th for d in r["full"]))
json.dump(out,open("training/segmentation/L1classi/metriche_20261110.json","w"),indent=1,default=str)
for k,v in out.items(): print(k,json.dumps(v,default=str)[:900]); print()
