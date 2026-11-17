"""Uso: analizza_v2.py dev  -> griglia SOLO su DEV, scrive dev_v2.json | analizza_v2.py test -> legge rules_v2_frozen.json, misura TEST (una volta)."""
import json, sys, itertools, collections
O = "asmile-loggers/_seg_sam3_L1classi_v2"; L = "training/segmentation/L1classi"
R = [json.loads(l) for l in open(f"{O}/res_v2.jsonl")]
ce = json.load(open(f"{L}/certificazione_v2.json")); st = json.load(open(f"{L}/set_v2.json"))
split = {(u, it["idx"]): it["split"] for u in ("asmile-001", "asmile-logger001") for it in st[u]}
GRID = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]; GF = ("gate", "fence")
def iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]); i = max(0, x2-x1) * max(0, y2-y1)
    u = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - i; return i/u if u else 0
def survivors(r, variant, tg, tf):
    W, H = r["W"], r["H"]; out = []
    for d in r["full"]:
        if d["c"] not in GF: continue
        if d["c"] == "gate":
            if d["conf"] < tg: continue
            b = d["box"]; cx = (b[0]+b[2])/2
            if "a" in variant and not ((b[3] >= 0.55*H and 0.2*W <= cx <= 0.8*W) or (b[2]-b[0]) >= 0.30*W): continue
            if "b" in variant and any(o["c"] in ("door", "garage door") and o["conf"] > d["conf"] and iou(o["box"], b) >= 0.5 for o in r["full"]): continue
        else:
            if d["conf"] < tf: continue
        out.append(d)
    return out
def lab(r):
    k = r["key"]
    if k in ("asmile-001", "asmile-logger001"):
        c = ce[k]; i = r["idx"]
        if i in c["invalido"] or i in c["ambiguo"]: return None
        if i in c["gate_real"] or i in c["fence_real"]: return ("pos", f"{k}_set_" + str(i)) 
        return ("neg", k)
    return ("pos", k)
def events(rs):
    # raggruppa positivi: set certificati = run consecutivi di idx; altri per key
    ev = collections.defaultdict(list)
    for r in rs:
        l = lab(r)
        if l and l[0] == "pos":
            if r["key"] in ("asmile-001", "asmile-logger001"): ev[(r["key"], "set")].append(r)
            else: ev[r["key"]].append(r)
    out = {}
    for k, l in ev.items():
        if isinstance(k, tuple):
            l = sorted(l, key=lambda r: r["idx"]); run = []; n = 0
            for r in l:
                if run and r["idx"] - run[-1]["idx"] > 1: out[f"{k[0]}_set_run{n}"] = run; run = []; n += 1
                run.append(r)
            out[f"{k[0]}_set_run{n}"] = run
        else: out[k] = sorted(l, key=lambda r: r["idx"])
    return out
def ssplit(r, pos_i, key):
    if key in ("asmile-001", "asmile-logger001"): return split[(key, r["idx"])]
    return "DEV" if pos_i % 2 == 0 else "TEST"
def evaluate(which, variant, tg, tf, th_old=None):
    res = {}
    for u in ("asmile-001", "asmile-logger001"):
        neg = [r for r in R if r["key"] == u and lab(r) == ("neg", u) and split[(u, r["idx"])] == which]
        fp = [r for r in neg if survivors(r, variant, tg, tf)]
        res[u] = dict(n_neg=len(neg), falsi=len(fp), pct=round(100*len(fp)/max(1, len(neg)), 2), falsi_idx=[r["idx"] for r in fp])
    evs = events(R); res["eventi"] = {}
    for name, l in evs.items():
        sub = [r for i, r in enumerate(l) if ssplit(r, i, r["key"]) == which]
        if sub: res["eventi"][name] = dict(n=len(sub), rec=round(sum(1 for r in sub if survivors(r, variant, tg, tf))/len(sub), 3))
    return res
if sys.argv[1] == "dev":
    out = []
    for variant in ("", "a", "b", "ab"):
        for tg, tf in itertools.product(GRID, GRID):
            e = evaluate("DEV", variant, tg, tf)
            recs = [v["rec"] for v in e["eventi"].values()]
            out.append(dict(variant=variant or "base", tg=tg, tf=tf, f001=e["asmile-001"]["pct"], flog=e["asmile-logger001"]["pct"], rec_mean=round(sum(recs)/len(recs), 3), rec_min=min(recs), eventi=e["eventi"], n001=e["asmile-001"]["n_neg"], nlog=e["asmile-logger001"]["n_neg"]))
    json.dump(out, open(f"{L}/dev_v2.json", "w"), indent=1)
    ok = [o for o in out if o["f001"] <= 2 and o["flog"] <= 2]
    print("config con falsi DEV<=2% su entrambe:", len(ok))
    for o in sorted(ok, key=lambda o: (-o["rec_mean"], o["tg"]))[:8]: print({k: o[k] for k in ("variant", "tg", "tf", "f001", "flog", "rec_mean", "rec_min")})
    print("migliori per somma falsi:")
    for o in sorted(out, key=lambda o: (o["f001"]+o["flog"], -o["rec_mean"]))[:8]: print({k: o[k] for k in ("variant", "tg", "tf", "f001", "flog", "rec_mean", "rec_min")})
    print("base 0.30..: ", [{k: o[k] for k in ("variant","tg","tf","f001","flog","rec_mean")} for o in out if o["variant"]=="base" and o["tg"]==0.5 and o["tf"]==0.5])
else:
    fz = json.load(open(f"{L}/rules_v2_frozen.json"))
    e = evaluate("TEST", fz["variant"], fz["tg"], fz["tf"]); base = evaluate("TEST", "", 0.7, 0.7)
    # classi vecchie: conteggi old vs full su TEST (frame validi), soglie 0.70 e 0.45
    cl = {}
    for u in ("asmile-001", "asmile-logger001"):
        rs = [r for r in R if r["key"] == u and lab(r) and split[(u, r["idx"])] == "TEST"]
        for th in (0.45, 0.70):
            co, cf = collections.Counter(), collections.Counter()
            for r in rs:
                for d in r["old"]:
                    if d["conf"] >= th: co[d["c"]] += 1
                for d in r["full"]:
                    if d["conf"] >= th and d["c"] not in GF and d["c"] not in ("door", "garage door"): cf[d["c"]] += 1
            cl[f"{u}@{th}"] = dict(old=sum(co.values()), full=sum(cf.values()), delta_pct=round(100*(sum(cf.values())-sum(co.values()))/max(1, sum(co.values())), 2),
                                  max_class_delta_pct=max([round(abs(cf[c]-co[c])/co[c]*100, 1) for c in co] or [0]))
    r = dict(regola=fz, TEST=e, TEST_senza_regola_v1_0p70=base, classi_vecchie=cl)
    json.dump(r, open(f"{L}/test_v2.json", "w"), indent=1); print(json.dumps(r, indent=1)[:6000])
