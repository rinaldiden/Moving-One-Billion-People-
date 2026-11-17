"""Set NUOVO v2 L1.classi (2026-11-10), deterministico, scritto PRIMA di girare SAM 3. Unita' SEPARATE.
#001: session_20261109_094146 (10066 fr), frame>=30, scena in moto (blocks mediana+-7 >= 1: con >=60 e l'esclusione +-30 restano solo 155 frame, v1 ne copriva quasi tutti),
  esclusi +-30 da TUTTI i frame del controllo v1 (main+riserva), spaziatura minima 10 frame, fino a 200 punti linspace unici (meno se i candidati sono pochi).
logger001: sessioni clip_20261109_100554 e clip_20261109_085836 (diverse da 20261029_163359), meta' SINISTRA SBS (il k-esimo clip di metrics = k-esimo file esistente in ordine, clip numerati con buchi),
  scena in moto (blocks mediana+-7 >= 20), spaziatura minima 45 frame, 200 punti linspace (140 da 100554, 60 da 085836).
DEV/TEST: alternato sull'ordine dell'indice (pari=DEV, dispari=TEST), deciso prima degli esiti."""
import json, numpy as np
A = "asmile-loggers"; cf = json.load(open("training/segmentation/L1classi/controllo_fisso.json"))
def pick(el, n, gap):
    out = []
    for i in el:
        if not out or i - out[-1] >= gap: out.append(i)
    return sorted(set(out[int(round(k))] for k in np.linspace(0, len(out) - 1, min(n, len(out)))))
def med(b, w): return np.array([np.median(b[max(0, i-w):i+w+1]) for i in range(len(b))])
res = {"regola": __doc__, "asmile-001": [], "asmile-logger001": []}
used = [it["frame"] for u in ("asmile-001", "riserva_asmile-001") for it in cf[u]]
b = np.load(f"{A}/_solo_movimento/asmile-001/session_20261109_094146/metrics.npz")["blocks"].astype(float)
m = med(b, 7)
el = [i for i in range(30, len(b)) if m[i] >= 1 and all(abs(i - u) > 30 for u in used)]
sel = pick(el, 200, 10)
res["asmile-001"] = [{"video": f"{A}/asmile-001/session_20261109_094146_left.h264", "frame": int(i)} for i in sel]
for sess, n in (("clip_20261109_100554", 140), ("clip_20261109_085836", 60)):
    z = np.load(f"{A}/_solo_movimento/asmile-logger/{sess}/metrics.npz"); bl = z["blocks"].astype(float); cn = z["counts"]
    import glob; files = sorted(glob.glob(f"{A}/asmile-logger/{sess}_*.h264")); assert len(files) == len(cn), (len(files), len(cn))
    mm = med(bl, 7); cum = np.concatenate([[0], np.cumsum(cn)])
    e = [i for i in range(len(bl)) if mm[i] >= 20]
    for i in pick(e, n, 45):
        c = int(np.searchsorted(cum, i, side="right") - 1); off = int(i - cum[c])
        if off < 30: off = 30   # warm-up
        res["asmile-logger001"].append({"video": files[c], "frame": off, "crop": "left_half", "sess": sess, "glob": int(i)})
for u in ("asmile-001", "asmile-logger001"):
    for k, it in enumerate(res[u]): it["idx"] = k; it["split"] = "DEV" if k % 2 == 0 else "TEST"
json.dump(res, open("training/segmentation/L1classi/set_v2.json", "w"), indent=1)
print(len(el), {u: len(res[u]) for u in ("asmile-001", "asmile-logger001")})
