"""Set di controllo FISSO L1.classi (2026-11-10), deterministico, scritto PRIMA di girare SAM 3.
#001: session_20261109_094146 (originale 10066 frame), frame>=30, scena in moto (blocks mediana±7 >= 60), 100 punti linspace.
logger001: clip_20261029_163359_00000..00025, 4 frame/clip a offset 60,180,300,420, meta' SINISTRA dell'SBS 2560x800 (104 frame).
Le due unita' restano SEPARATE."""
import json, os, subprocess, numpy as np
A = "asmile-loggers"
out = {"regola": __doc__, "asmile-001": [], "asmile-logger001": []}
b = np.load(f"{A}/_solo_movimento/asmile-001/session_20261109_094146/metrics.npz")["blocks"].astype(float)
n = len(b); med = np.array([np.median(b[max(0, i-7):i+8]) for i in range(n)])
el = [i for i in range(30, n) if med[i] >= 60]
sel = [el[int(round(k))] for k in np.linspace(0, len(el)-1, 100)]
out["asmile-001"] = [{"video": f"{A}/asmile-001/session_20261109_094146_left.h264", "frame": int(i)} for i in sel]
for c in range(26):
    for off in (60, 180, 300, 420):
        out["asmile-logger001"].append({"video": f"{A}/asmile-logger/clip_20261029_163359_{c:05d}.h264", "frame": off, "crop": "left_half"})
json.dump(out, open("training/segmentation/L1classi/controllo_fisso.json", "w"), indent=1)
print(len(out["asmile-001"]), len(out["asmile-logger001"]), len(el))
