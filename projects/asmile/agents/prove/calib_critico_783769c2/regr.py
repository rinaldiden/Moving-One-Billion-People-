import sys, json, numpy as np
sys.path.insert(0,'logger/depth')
import calib_charuco_dual as ccd
ccd.F0["v"]=ccd.UNITS["asmile-001"]["f0"]
v,meta=ccd.load_views_npz('logger/depth/regressione_views_asmile-001_180306.npz')
print("viste",len(v))
# copertura prima/dopo regola 12
def cov(vs,k):
    return ccd.coverage(vs,k)[0].tolist()
d,n=ccd.drop_degenerate(v)
for k in "LR":
    print(k,"prima",cov(v,k)); print(k,"dopo ",cov(d,k))
# quanti lati tolti per zona (centroide)
import collections
for k in "LR":
    c=collections.Counter()
    for a in v:
        x=a[k]
        if x is not None and len(x["ids"])<12:
            z=ccd.zone_of(x["img"]); c.update(z.tolist())
    print(k,"corner tolti per zona",dict(c))
args=["--unit","asmile-001","--out","x_CANDIDATO.json","--square-len","0.05","--models","k1k2,k1k2k3,std5,rational"]
for hb in sys.argv[1:]:
    a=ccd.build_parser().parse_args(args+(["--holdout-blocks",hb] if hb!="d" else []))
    r,*_=ccd.analyze(v,meta,a,ccd.UNITS["asmile-001"])
    print("RES",hb,r["gate"],r["rms_mono_holdout"],r["rms_stereo_holdout"]["rms"],r["T_from_board_mm"],r["model"],r["gate_problemi"])
