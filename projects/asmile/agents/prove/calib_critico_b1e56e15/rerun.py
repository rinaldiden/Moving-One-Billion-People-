import sys, os, json
sys.path.insert(0, "logger/depth")
import calib_charuco_dual as C
nb = int(sys.argv[1]); out = sys.argv[2]; guard = int(sys.argv[3]) if len(sys.argv) > 3 else 1
base = "asmile-loggers/asmile-001/"
sess = ["session_20261111_082437", "session_20261111_083054", "session_20261111_083632"]
cache = "agents/prove/calib_critico_b1e56e15/views_all.npz"
ap = C.build_parser()
prof = C.UNITS["asmile-001"]; C.F0["v"] = prof.get("f0", C.F0_DEFAULT)
a = ap.parse_args(["--unit", "asmile-001", "--out", out, "--square-len", "0.05", "--holdout-blocks", str(nb), "--holdout-guard", str(guard)])
board = C.make_board(a.dict, 11, 8, 0.05, round(0.74 * 0.05, 5))
if os.path.exists(cache):
    views, meta = C.load_views_npz(cache); info = meta["info"]
else:
    views = []; info = None
    for k, s in enumerate(sess):
        a.session = base + s
        v, inf = C.collect(a, prof, board)
        for x in v: x["frame"] += 100000 * k
        views += v
        if info is None: info = inf
        print(s, len(v), flush=True)
    meta = dict(dict=a.dict, sx=11, sy=8, square_len=0.05, marker_len=round(0.74*0.05,5), info=json.loads(json.dumps(info, default=str)))
    C.save_views_npz(cache, views, meta)
print("views", len(views), flush=True)
rep, s, best, sel, hold = C.analyze(views, info, a, prof)
json.dump(rep, open(out + ".report.json", "w"), indent=1, default=float)
print("MODEL", best, "RMS mono", rep["rms_mono_holdout"], "stereo", rep["rms_stereo_holdout"]["rms"], "T", rep["T_from_board_mm"], rep["gate"])
st = rep["stereo_holdout"]
print("zone n/patch", st["dy_n"], st["dy_patch_n"]); print("p95patch", st["dy_patch_abs_p95"]); print("p50", st["dy_abs_p50"])
print(rep["gate_problemi"])
