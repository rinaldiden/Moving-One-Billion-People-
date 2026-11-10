import sys,numpy as np
sys.path.insert(0,'logger/depth')
import calib_charuco_dual as ccd
ccd.F0["v"]=ccd.UNITS["asmile-001"]["f0"]
v,meta=ccd.load_views_npz('logger/depth/regressione_views_asmile-001_180306.npz')
ccd.drop_degenerate=lambda vs,min_corners=0:(vs,0)
a=ccd.build_parser().parse_args(["--unit","asmile-001","--out","x_CANDIDATO.json","--square-len","0.05","--models","std5"])
r,*_=ccd.analyze(v,meta,a,ccd.UNITS["asmile-001"])
print("RES nodrop",r["gate"],r["rms_mono_holdout"],r["rms_stereo_holdout"]["rms"],r["T_from_board_mm"])
print(r["gate_problemi"])
