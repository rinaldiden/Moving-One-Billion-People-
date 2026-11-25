#!/usr/bin/env python3
"""casi_frenate_001.py — dalle 30 frenate classificate (perche_frenate_001_20261125.csv) mette in coda casi dubbi quelle
che il maestro non capisce: regola e lettura visiva in disaccordo, oppure lettura visiva 'bassa', oppure perche' = libero/unknown.
Per ogni caso: striscia di 5 fotogrammi rettificati (t-4, -2, -1, 0, +1 s, camera destra fisica) con le classi SAM 3
(cf>=0.45) e la distanza stereo, i dati della frenata e una domanda chiara. Nessun invio.
Uso: ~/.asmile_depth_venv/bin/python training/set_manovre/casi_frenate_001.py
"""
import csv, glob, json, os, sys
import numpy as np, cv2
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "training", "depth")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "training", "segmentation"))
import depth_seg_001 as D
import casi as C
import seg_teacher_student as S

SESS = "session_20261125_095037"
CSV = os.path.join(ROOT, "training", "set_manovre", "perche_frenate_001_20261125.csv")
SEG = os.path.join(ROOT, "asmile-loggers", "_seg_sam3", "frenate_001_20261125")
IT = {"curva": "curva / svolta", "incrocio_immissione": "incrocio o immissione", "auto_in_arrivo": "auto in arrivo",
      "auto_ferma_laterale": "auto ferma di lato (passaggio)", "persona_bici": "persona o bici", "stop_segnale": "stop / semaforo",
      "ostacolo_traiettoria": "ostacolo sulla traiettoria", "rallentamento_libero_altro": "rallentamento senza un motivo visibile", "unknown": "non so"}


def disegna(img, rec):
    out = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR) if img.ndim == 2 else img.copy()
    if rec is None: return out
    for d in rec["dets"]:
        if d["cf"] < 0.45 or d.get("ego"): continue
        x1, y1, x2, y2 = d["box"]
        z = d["z_st"] if (d.get("z_st") and d.get("n_st", 0) >= 150) else None
        col = (0, 0, 255) if d["c"] in ("person", "child", "bicycle", "car", "van", "truck", "bus", "motorcycle") else (0, 220, 255)
        cv2.rectangle(out, (x1, y1), (x2, y2), col, 2)
        t = S.THINGS_IT.get(d["c"], d["c"]) + (f" {z:.1f}m" if z else "")
        cv2.putText(out, t, (x1, max(16, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
        cv2.putText(out, t, (x1, max(16, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
    return out


def main():
    rows = list(csv.DictReader(open(CSV)))
    recs = {}
    for f in glob.glob(os.path.join(SEG, "f*.json")):
        r = json.load(open(f)); recs[r["frame"]] = r
    grid = np.array(sorted(recs))
    da_fare = []
    for r in rows:
        if r["in_coda_daniele"] == "True" and r["n"] != "29":     # #29 = stesso evento di #30 (scettico): un solo caso
            da_fare.append(r)
    want = {}
    for r in da_fare:
        f0 = int(r["frame"])
        sel = []
        for dt in (-4, -2, -1, 0, 1):
            tgt = f0 + dt * 15
            k = int(grid[np.argmin(np.abs(grid - tgt))])
            sel.append(k)
        want[r["n"]] = sel
    allf = sorted(set(sum(want.values(), [])))
    rc = D.Rect(D.CALIB)
    imgs = {}
    k = 0
    for i, (Lr, Rr) in enumerate(zip(D.gray_frames(os.path.join(D.LOGS, f"{SESS}_right.h264")), D.gray_frames(os.path.join(D.LOGS, f"{SESS}_left.h264")))):
        if k >= len(allf): break
        if i != allf[k]: continue
        k += 1
        L, R = rc(Lr, Rr)
        imgs[i] = R
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fotogrammi as F
    out = []
    for r in da_fare:
        n = int(r["n"]); sel = want[r["n"]]
        tiles = [disegna(imgs.get(i), recs.get(i)) if imgs.get(i) is not None else None for i in sel]
        lab = [f"#{n} t{(i - int(r['frame'])) / 15:+.1f}s f{i}" for i in sel]
        strip = F.striscia(tiles, lab, larg=420)
        cand = []
        if r["perche_regola"]: cand.append(dict(reading=f"regola: {IT[r['perche_regola']]} (scattate: {r['regole_scattate'] or 'nessuna'})", confidence={"alta": 0.7, "media": 0.5, "bassa": 0.3}[r["conf_regola"]]))
        if r["perche_visivo"]: cand.append(dict(reading=f"lettura visiva: {IT[r['perche_visivo']]} - {r['nota_visiva']}", confidence={"alta": 0.7, "media": 0.5, "bassa": 0.3}[r["conf_visivo"]]))
        opts = []
        for x in (r["perche_visivo"], r["perche_regola"]):
            if x and IT[x] not in opts: opts.append(IT[x])
        for x in ("curva", "incrocio_immissione", "auto_in_arrivo", "persona_bici", "auto_ferma_laterale", "ostacolo_traiettoria", "stop_segnale", "rallentamento_libero_altro"):
            if IT[x] not in opts: opts.append(IT[x])
        unito = " (insieme alla frenata 29, 1 s prima: e' lo stesso arresto)" if n == 30 else ""
        q = (f"Giro #001 del 25/11, frenata {n}{unito} alle {r['t_video_s']} s dall'inizio del video (fotogramma {r['frame']}): da {float(r['v0_kmh']):.0f} a "
             f"{float(r['v1_kmh']):.0f} km/h in {float(r['durata_s']):.1f} s. Perche' hai frenato? (la regola dice '{IT[r['perche_regola']]}', "
             f"io guardando ho letto '{IT[r['perche_visivo']]}')")
        ss = dict(classes=sorted(set(d["c"] for i in sel if recs.get(i) for d in recs[i]["dets"] if d["cf"] >= 0.45 and not d.get("ego"))),
                  distances_m=dict(persona_min=r["persona_zmin"] or None, ostacolo_min=r["ostacolo_zmin"] or None, veicolo_centro_min=r["veic_centro_zmin"] or None),
                  drivable=dict(passaggio_stretto_fotogrammi=r["stretto_n"], apertura_fotogrammi=r["apertura_n"]),
                  sensors=dict(v0_kmh=r["v0_kmh"], v1_kmh=r["v1_kmh"], durata_s=r["durata_s"], dec_media=r["dec_media"], dec_picco=r["dec_picco"],
                               imbardata_gradi=r["dpsi_deg"], sterzo_max_gradi=r["sterzo_max_deg"], gps=[r["lat"], r["lon"]]))
        cid, esito = C.scrivi(SESS, (sel[0], sel[-1]), "3-situations", q, opts + ["Due motivi insieme (scrivili)"], ss, cand, img=strip,
                              tag=f"perche_frenata_{n}", extra=dict(unita="asmile-001", frenata=n, video=f"asmile-loggers/asmile-001/{SESS}_left.h264",
                                                                     immagine="5 fotogrammi rettificati camera destra fisica; rosso = persone/veicoli, giallo = altre classi; distanza solo se stereo affidabile"))
        out.append((n, cid, esito))
    print(len(out), "casi:", out)


if __name__ == "__main__":
    main()
