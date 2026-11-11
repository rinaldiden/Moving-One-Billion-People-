import sys, json, pickle
sys.path.insert(0, "logger/depth")
import calib_charuco_dual as C
nb = int(sys.argv[1]); out = sys.argv[2]
ss = ["082437","083054","083632","101400","102053"]
views=[]; info=None
for k,s in enumerate(ss):
    v,inf = pickle.load(open(f"/tmp/cv2/{s}.pkl","rb"))
    for x in v: x["frame"] += 100000*k
    views += v; info = info or inf
print("views", len(views), flush=True)
ap = C.build_parser(); prof = C.UNITS["asmile-001"]; C.F0["v"] = prof.get("f0", C.F0_DEFAULT)
a = ap.parse_args(["--unit","asmile-001","--out",out,"--square-len","0.05","--holdout-blocks",str(nb)])
rep, s, best, sel, hold = C.analyze(views, info, a, prof)
cal = C.Calib(s["K1"], s["D1"], s["K2"], s["D2"], s["R"], s["T"], size=(C.CAM_W, C.CAM_H), baseline_mm=s["T_raw_m"]*1000)
cal.save(out); blob=json.load(open(out)); blob.update({"order":prof["order"],"flip180":prof["flip180"],"d0_px":0.0,"modello":best,"holdout_blocks":nb,"stato":"CANDIDATO v2"}); json.dump(blob,open(out,"w"),indent=2)
rep["calib_model"]=best
json.dump(rep, open(out+".report.json","w"), indent=1, default=float)
print("MODEL", best, "RMS mono", rep["rms_mono_holdout"], "stereo", rep["rms_stereo_holdout"]["rms"], "T", rep["T_from_board_mm"], rep["gate"])
st = rep["stereo_holdout"]
print("zone n/patch", st["dy_n"], st["dy_patch_n"]); print("p95patch", st["dy_patch_abs_p95"]); print("p50", st["dy_abs_p50"])
print(rep["gate_problemi"])
