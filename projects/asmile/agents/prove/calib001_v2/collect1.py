import sys, json, pickle
sys.path.insert(0, "logger/depth")
import calib_charuco_dual as C
s = sys.argv[1]; out = sys.argv[2]
ap = C.build_parser(); prof = C.UNITS["asmile-001"]; C.F0["v"] = prof.get("f0", C.F0_DEFAULT)
a = ap.parse_args(["--unit","asmile-001","--out","x","--square-len","0.05"])
board = C.make_board(a.dict, 11, 8, 0.05, round(0.74*0.05,5))
a.session = "asmile-loggers/asmile-001/"+s
v, inf = C.collect(a, prof, board)
pickle.dump((v, json.loads(json.dumps(inf, default=str))), open(out,"wb"))
print(s, len(v), flush=True)
