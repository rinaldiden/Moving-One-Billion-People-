#!/usr/bin/env python3
"""
fedelta_fuori_fit.py - fedelta' del gemello su una sessione REALE di #001 MAI entrata nel fit della calib.

Perche': fedelta_reale_driver.py usava sessioni dell'11/11 che SONO nel fit B30 (082437, 083054, 083632, 101400, 102053):
lo scarto 0.22-0.39 px era in-sample (= RMS del fit). Qui si usa session_20261030_180306 (1a ripresa, 500 kbps, tabellone
ChArUco 11x8 50 mm): mai nel fit B30 ne' PRIMA_20261111 (verificato: report.input + elenco sessioni del fit). La 112806
dell'11/11 NON ha il tabellone (muro+borsa), quindi non e' usabile per i corner.
ATTENZIONE: fra il 30/10 e l'11/11 il montaggio puo' essere cambiato di poco: lo scarto contiene anche questo (e' un test
vero della calib, non solo del gemello). Controllo: la stessa sessione con la calib fittata SU di essa (CANDIDATO.json 1a ripresa)
da' il pavimento (rumore 500 kbps + gemello).
Metrica principale = scarto GREZZO per zona/camera (nessun allineamento per vista). cam1 = sinistra fisica: la posa PnP e'
stimata proprio su cam1, quindi lo scarto cam1 e' in parte assorbito dalla posa; cam2 (destra fisica) e' il test indipendente
(R, T, lente destra). L'allineato (similarita' per vista) e' solo informativo.

  python3 fedelta_fuori_fit.py --calib ../calib_asmile-001.json --out <json>
"""
import argparse, json, os, sys
import cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import fedelta  # noqa

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SESS = os.path.join(ROOT, "asmile-loggers", "asmile-001", "session_20261030_180306")
NPZ = os.path.join(os.path.dirname(HERE), "regressione_views_asmile-001_180306.npz")


def load_pairs(n=70, min_ids=25):
    z = np.load(NPZ, allow_pickle=True)
    fr, Lo, Ro = z["frame"], z["L_off"], z["R_off"]
    nl, nr = np.diff(Lo), np.diff(Ro)
    ok = np.where((nl >= min_ids) & (nr >= min_ids))[0]
    sel = ok[np.linspace(0, len(ok) - 1, min(n, len(ok))).astype(int)]
    want = {int(fr[i]) for i in sel}
    out = {}
    # video_right = camera fisicamente SINISTRA, video_left = DESTRA (calib order=RL)
    for cam, name in (("L", "video_right.h264"), ("R", "video_left.h264")):
        c = cv2.VideoCapture(os.path.join(SESS, name)); k = 0
        while True:
            okf, f = c.read()
            if not okf:
                break
            if k in want:
                out.setdefault(k, {})[cam] = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            k += 1
    keys = sorted(k for k in out if len(out[k]) == 2)
    return [(out[k]["L"], out[k]["R"]) for k in keys], keys


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--calib", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=70)
    a = ap.parse_args()
    pairs, keys = load_pairs(a.n)
    r = fedelta.compare(pairs, a.calib, "A2_11x8_50mm")
    r.update(sessione="session_20261030_180306 (fuori fit)", calib=os.path.basename(a.calib), frames=keys)
    zn = ["alto-sx", "alto-c", "alto-dx", "medio-sx", "centro", "medio-dx", "basso-sx", "basso-c", "basso-dx"]
    r["zone"] = zn
    json.dump(r, open(a.out, "w"), indent=1)
    for k in ("scarto_grezzo_px", "scarto_allineato_px"):
        print(k)
        for c, L in r[k].items():
            print(" ", c, [None if z is None else (round(z["p50"], 2), round(z["p95"], 2), z["n"]) for z in L])
    print("coppie", r["n_coppie"], "rilevate reali/gemello", r["rilevate_reali"], r["rilevate_gemello"])
