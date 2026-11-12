#!/usr/bin/env python3
"""seg_postprocess_v2.py — post-processing delle maschere SAM 3 di #001 (giro 2, note del verifier). Niente SAM 3 rigirato.
Parametri DICHIARATI PRIMA di guardare i numeri:
  IOU_MERGE = 0.80  (IoU delle box nello stesso frame; fusione greedy: capo = classe a confidenza maggiore fra quelle NON unknown,
                     altrimenti la maggiore; le altre finiscono in `alternatives`, mai perse)
  FAMIGLIA primaria per la guida: veicolo / persona / bici-moto / paletto-palo / barriera-cancello / altro (+ unknown). La classe fine resta secondaria.
  NON_ORO = gate, fence, barrier, bicycle, pole, bollard, bench -> mai label d'oro: label_guida = ostacolo_generico (gate>=0.90 resta class_final gate, da_verificare).
  label_guida: unknown -> unknown; sure di persona/veicolo (non NON_ORO) -> persona/veicolo; low o NON_ORO -> ostacolo_generico.
  Consistenza temporale: per ogni det non-unknown del frame t cerca nel frame successivo campionato (gap<=20 frame) la det non-unknown con IoU box massima >=0.25
  (oggetti ripresi a 1 s di distanza); coerente se stessa etichetta. Misurata su: classe fine prima, famiglia prima (senza fusione), famiglia dopo (con fusione).
Uso: python3 training/segmentation/seg_postprocess_v2.py [session_20261109_094146]
"""
import os, sys, json
from collections import Counter, defaultdict
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SESS = sys.argv[1] if len(sys.argv) > 1 else "session_20261109_094146"
SRC = os.path.join(ROOT, "asmile-loggers", "_seg_sam3", SESS + "_001")
DST = os.path.join(ROOT, "asmile-loggers", "_seg_sam3", SESS + "_001_v2")
IOU_MERGE, GAP, IOU_T = 0.80, 20, 0.25
FAM = {"car": "veicolo", "van": "veicolo", "truck": "veicolo", "bus": "veicolo", "tractor": "veicolo",
       "person": "persona", "child": "persona", "stroller": "persona", "wheelchair": "persona",
       "bicycle": "bici-moto", "motorcycle": "bici-moto",
       "pole": "paletto-palo", "bollard": "paletto-palo", "traffic cone": "paletto-palo",
       "barrier": "barriera-cancello", "fence": "barriera-cancello", "gate": "barriera-cancello"}
NON_ORO = {"gate", "fence", "barrier", "bicycle", "pole", "bollard", "bench"}
family = lambda c: "unknown" if c == "unknown" else FAM.get(c, "altro")


def iou(a, b):
    iw = min(a[2], b[2]) - max(a[0], b[0]); ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0: return 0.0
    i = iw * ih; return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)


def dup_rate(recs, thr, key="class_final"):
    """quota di detection finali (non unknown) con un'altra finale nello stesso frame, IoU>=thr, etichetta diversa"""
    n = d = 0
    for r in recs:
        F = [x for x in r["detections"] if x["class_final"] != "unknown"]
        for a in F:
            n += 1
            if any(b is not a and iou(a["box"], b["box"]) >= thr and b[key] != a[key] for b in F): d += 1
    return d, n


def merge(r):
    D = r["detections"]
    order = sorted(D, key=lambda d: (d["class_final"] == "unknown", -d["conf"]))
    used, out = set(), []
    for d in order:
        if d["idx"] in used: continue
        grp = [e for e in order if e["idx"] not in used and (e is d or iou(d["box"], e["box"]) >= IOU_MERGE)]
        for e in grp: used.add(e["idx"])
        alts = [dict(class_raw=e["class_raw"], class_final=e["class_final"], tier=e["tier"], conf=e["conf"], idx=e["idx"]) for e in grp if e is not d]
        o = {k: v for k, v in d.items()}
        fam = family(d["class_final"])
        o.update(family=fam, family_hint=family(d["class_raw"]) if fam == "unknown" else fam, alternatives=alts, n_merged=len(grp))
        o["family_conflict"] = any(a["tier"] != "unknown" and a["conf"] >= 0.45 and family(a["class_final"]) not in (fam, "unknown") for a in alts)
        o["da_verificare"] = d["class_final"] in NON_ORO
        if d["tier"] == "unknown": o["label_guida"] = "unknown"
        elif d["tier"] == "sure" and fam in ("persona", "veicolo") and d["class_final"] not in NON_ORO: o["label_guida"] = fam
        else: o["label_guida"] = "ostacolo_generico"
        out.append(o)
    out.sort(key=lambda x: x["idx"]); return out


def consist(recs, labfn, only=None):
    ok = tot = 0; per = defaultdict(lambda: [0, 0])
    for a, b in zip(recs, recs[1:]):
        if b["frame"] - a["frame"] > GAP: continue
        B = [x for x in b["detections"] if x["class_final"] != "unknown"]
        for x in a["detections"]:
            if x["class_final"] == "unknown" or (only and family(x["class_final"]) != only): continue
            best = max(B, key=lambda y: iou(x["box"], y["box"]), default=None)
            if best is None or iou(x["box"], best["box"]) < IOU_T: continue
            tot += 1; per[labfn(x)][1] += 1
            if labfn(x) == labfn(best): ok += 1; per[labfn(x)][0] += 1
    return ok, tot, {k: v for k, v in per.items()}


def main():
    R = sorted((json.loads(l) for l in open(os.path.join(SRC, "index.jsonl"))), key=lambda r: r["frame"])
    st = {"n_frames": len(R), "iou_merge": IOU_MERGE}
    st["dup_prima"] = {str(t): dup_rate(R, t) for t in (0.5, 0.7, 0.8, 0.9)}
    st["dup_prima_famiglia_diversa"] = {str(t): [sum(1 for r in R for a in r["detections"] if a["class_final"] != "unknown" and any(
        b is not a and b["class_final"] != "unknown" and iou(a["box"], b["box"]) >= t and family(a["class_final"]) != family(b["class_final"]) for b in r["detections"])),
        sum(1 for r in R for a in r["detections"] if a["class_final"] != "unknown")] for t in (0.5, 0.8)}
    M = []
    for r in R:
        o = dict(r); o["detections_raw_n"] = len(r["detections"]); o["detections"] = merge(r); o["n_det"] = len(o["detections"]); M.append(o)
    st["det_prima"] = sum(len(r["detections"]) for r in R); st["det_dopo"] = sum(len(r["detections"]) for r in M)
    fin = lambda recs: [x for r in recs for x in r["detections"] if x["class_final"] != "unknown"]
    st["finali_prima"] = len(fin(R)); st["finali_dopo"] = len(fin(M))
    st["dup_dopo"] = {str(t): dup_rate(M, t) for t in (0.5, 0.7, 0.8)}
    st["famiglia_dopo"] = dict(Counter(x["family"] for r in M for x in r["detections"]))
    st["label_guida"] = dict(Counter(x["label_guida"] for r in M for x in r["detections"]))
    st["family_conflict"] = sum(1 for r in M for x in r["detections"] if x["family_conflict"])
    st["unione_fra_famiglie"] = sum(1 for r in M for x in r["detections"] for a in x["alternatives"] if a["tier"] != "unknown" and x["class_final"] != "unknown" and family(a["class_final"]) != x["family"])
    st["unione_stessa_famiglia_classi_diverse"] = sum(1 for r in M for x in r["detections"] for a in x["alternatives"] if a["tier"] != "unknown" and x["class_final"] != "unknown" and family(a["class_final"]) == x["family"] and a["class_final"] != x["class_final"])
    # senza fusione: famiglia della det originale
    for r in R:
        for x in r["detections"]: x["family"] = family(x["class_final"])
    c0 = consist(R, lambda x: x["class_final"]); c1 = consist(R, lambda x: x["family"]); c2 = consist(M, lambda x: x["family"])
    st["consistenza"] = {"classe_prima": c0[:2], "famiglia_prima": c1[:2], "famiglia_dopo": c2[:2],
                         "classe_prima_per_classe": c0[2], "famiglia_prima_per_famiglia": c1[2], "famiglia_dopo_per_famiglia": c2[2]}
    # solo veicoli: classe fine vs famiglia
    # solo i veicoli come punto di partenza; il match puo' cadere su qualunque finale del frame dopo (niente filtro che gonfi il risultato)
    st["consistenza_veicoli"] = {"classe": consist(R, lambda x: x["class_final"], "veicolo")[:2], "famiglia": consist(R, lambda x: family(x["class_final"]), "veicolo")[:2]}
    os.makedirs(DST, exist_ok=True)
    with open(os.path.join(DST, "index.jsonl"), "w") as f:
        for o in M: f.write(json.dumps(o) + "\n")
    json.dump(st, open(os.path.join(DST, "stats.json"), "w"), indent=1)
    print(json.dumps(st, indent=1))


if __name__ == "__main__":
    main()
