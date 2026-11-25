#!/usr/bin/env python3
"""build_set.py — INDICE DETERMINISTICO del set di manovre per il maestro (una riga per manovra, JSONL + CSV).
Unisce (tutto locale, sola lettura):
  manovre_001.csv                      frenate/sterzate di #001 dai sensori (estrai_manovre_001.py)
  manovre_logger.csv (se c'e')         frenate/sterzate dei logger da IMU (estrai_manovre_logger.py), qualita' bassa
  manovre_asmile2.csv (se c'e')        frenate (GPS) e sterzate (encoder sterzo) di asmile2, apr-mag 2026 (estrai_manovre_asmile2.py)
  perche_frenate_001_20261125.csv      le 30 frenate del 25/11 09:50 con perche' controllato (regola + occhio)
  per-fotogramma: 25/11 #001 -> asmile-loggers/_seg_sam3/{frenate_001_20261125, set_manovre_001/<sess>}/f*.json (classi + Z stereo)
                  altre date/unita' -> asmile-loggers/_seg_sam3/set_manovre_*/classi_*/<video>_f*.json (solo classi, nessuna distanza)
PERCHE': stesse regole di perche_frenate_001.py (stesse soglie, nessun ritocco). Sulle 30 frenate controllate la regola
concorda con l'occhio 13/30: l'etichetta di sola regola e' quindi DEBOLE e porta 'precisione_regola_30' per tipo.
Distanze: solo #001 dal 25/11 (calib VALIDATA quel giorno); prima del 25/11 la calib non e' dimostrata per quel montaggio -> vuote.
Uscite: training/set_manovre/set_manovre.jsonl, set_manovre.csv
"""
import csv, glob, json, os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import perche_frenate_001 as P

SEG = os.path.join(ROOT, "asmile-loggers", "_seg_sam3")
OUTJ = os.path.join(HERE, "set_manovre.jsonl"); OUTC = os.path.join(HERE, "set_manovre.csv")
OFFS = (-3, -2, -1, 0, 1)
CENTRI = {"6606": 6606, "4112": 4112}


def precisione_30():
    d = pd.read_csv(os.path.join(HERE, "perche_frenate_001_20261125.csv"))
    return {k: f"{int(g.accordo.sum())}/{len(g)}" for k, g in d.groupby("perche_regola")}


def frame_dir_001(sess):
    if sess == "session_20261125_095037": return os.path.join(SEG, "frenate_001_20261125")
    p = os.path.join(SEG, "set_manovre_001", sess)
    return p if os.path.isdir(p) else None


def carica_frames(sess, video, off, tms):
    """record per-fotogramma con t_wall, dalle due fonti possibili"""
    F = []
    fd = frame_dir_001(sess) if sess.startswith("session_20261125") else None
    if fd:
        F = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(fd, "f*.json")))]
        return F, True
    base = os.path.basename(video).replace(".h264", "")
    for f in sorted(glob.glob(os.path.join(SEG, "set_manovre_*", "classi_*", f"{base}_f*.json"))):
        r = json.load(open(f)); i = r["frame"]
        if i < len(tms):
            r["t_wall"] = tms[i] / 1000 + off
            for x in r["dets"]: x.update(z_st=None, n_st=0, z_gr=None, x=None, ego=False)
            r.setdefault("edges", None); F.append(r)
    return F, False


def riassunto_classi(F, t):
    c = {}
    for f in F:
        if not (t - 4 <= f["t_wall"] <= t + 1): continue
        for x in f["dets"]:
            if x["cf"] < 0.45 or x.get("ego"): continue
            z = P.zeta(x) if x.get("n_st") else None
            k = x["c"]
            e = c.setdefault(k, dict(fotogrammi=set(), z_min=None))
            e["fotogrammi"].add(f["frame"])
            if z is not None and (e["z_min"] is None or z < e["z_min"]): e["z_min"] = round(z, 2)
    return {k: dict(fotogrammi=len(v["fotogrammi"]), z_min_m=v["z_min"]) for k, v in sorted(c.items())}


def main():
    prec = precisione_30()
    m = pd.read_csv(os.path.join(HERE, "manovre_001.csv"))
    ctrl = pd.read_csv(os.path.join(HERE, "perche_frenate_001_20261125.csv"))
    out = []
    sens_cache = {}
    sessinfo = {}
    for _, r in m.iterrows():
        rec = {k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in r.items()}
        rec["id"] = f"{r.unita}|{r.file_sensori.split('/')[-1]}|{int(r.t_ms)}|{r.tipo}"
        sess = r.sessione_video if isinstance(r.sessione_video, str) else ""
        rec.update(perche=None, perche_fonte=None, conf=None, regole_scattate=None, classi=None, distanze_valide=False, fotogrammi=None)
        if sess:
            if sess not in sessinfo:
                sd = os.path.join(ROOT, "asmile-loggers", "asmile-001", sess)
                off = json.load(open(os.path.join(sd, "metadata.json")))["clock_map_start"]["wall_minus_boottime_s"]
                tms = [int(x["t_ms"]) for x in csv.DictReader(open(os.path.join(sd, "frames_left.csv")))]
                sessinfo[sess] = (off, tms)
            off, tms = sessinfo[sess]
            t = r.t_ms / 1000 + off
            fr0 = int(r.frame)
            rec["fotogrammi"] = [fr0 + 15 * o for o in OFFS if 0 <= fr0 + 15 * o < len(tms)]
            rec["t_wall"] = round(t, 3)
            key = (r.file_sensori, sess)
            if key not in sens_cache:
                cen = next((v for k, v in CENTRI.items() if str(r.centro_sterzo).startswith(k)), None)
                if cen is None:
                    raw = pd.read_csv(os.path.join(ROOT, r.file_sensori), usecols=["enc_steer_raw"]).enc_steer_raw
                    cen = int(np.nanmedian(raw[raw >= 0]))
                sens_cache[key] = P.carica_sensori([os.path.join(ROOT, r.file_sensori)], off=off, center=cen)[0]
            d = sens_cache[key]
            F, con_z = carica_frames(sess, r.video, off, tms)
            rec["classi"] = riassunto_classi(F, t)
            rec["distanze_valide"] = bool(con_z)
            if F and r.chi == "Daniele":
                ft = P.features(t, float(r.v0_kmh) / 3.6, d, F)
                ft["v1_kmh"] = float(r.v1_kmh) if r.tipo == "frenata" and not pd.isna(r.v1_kmh) else float(r.v0_kmh)
                lab, sc = P.regole(ft)
                rec.update(perche=lab, perche_fonte="regola", regole_scattate="|".join(sc), conf="bassa",
                           precisione_regola_30=prec.get(lab, "mai vista"), imbardata_deg=ft["dpsi_deg"], sterzo_max_deg=ft["sterzo_max_deg"],
                           passaggio_stretto_fotogrammi=ft["stretto_n"])
                # le 30 controllate: vale l'esito regola+occhio
                if r.tipo == "frenata" and sess == "session_20261125_095037":
                    c = ctrl.iloc[(ctrl.t_wall - t).abs().argmin()]
                    if abs(c.t_wall - t) < 2.0:
                        rec.update(perche=c.perche, perche_fonte=f"regola+occhio (frenata {int(c.n)} del 25/11)", conf=c.conf,
                                   perche_regola=c.perche_regola, perche_visivo=c.perche_visivo, in_coda_daniele=bool(c.in_coda_daniele))
        out.append(rec)
    from classi_finestre import nome_base
    for lg in (os.path.join(HERE, "manovre_logger.csv"), os.path.join(HERE, "manovre_asmile2.csv")):
        if not os.path.exists(lg): continue
        for _, r in pd.read_csv(lg).iterrows():
            rec = {k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in r.items()}
            rec["id"] = f"{r.unita}|{r.get('sessione', '')}|{r.get('t_ms', r.get('ora', ''))}|{r.get('frame', '')}|{r.tipo}"
            rec.update(perche=None, perche_fonte="nessuna regola (unita' senza distanze valide; classi solo dove elaborate)", distanze_valide=False)
            if isinstance(r.video, str) and r.video and not pd.isna(r.frame):
                base = nome_base(r.video); f0 = int(r.frame)
                rec["fotogrammi"] = [f0 + 15 * o for o in OFFS if f0 + 15 * o >= 0]
                c = {}
                for fi in rec["fotogrammi"]:
                    p = glob.glob(os.path.join(SEG, "set_manovre_*", "classi_*", f"{base}_f{fi:06d}.json"))
                    if not p: continue
                    for x in json.load(open(p[0]))["dets"]:
                        if x["cf"] >= 0.45: c[x["c"]] = c.get(x["c"], 0) + 1
                rec["classi"] = {k: dict(fotogrammi=v, z_min_m=None) for k, v in sorted(c.items())} or None
            out.append(rec)
    out.sort(key=lambda x: (x["unita"], str(x.get("ora", "")), x["tipo"], str(x["id"])))
    with open(OUTJ, "w") as fo:
        for r in out: fo.write(json.dumps(r, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n")
    keys = []
    for r in out:
        for k in r:
            if k not in keys: keys.append(k)
    with open(OUTC, "w", newline="") as fo:
        w = csv.DictWriter(fo, keys); w.writeheader()
        for r in out: w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in r.items()})
    df = pd.DataFrame(out)
    print("manovre", len(df)); print(df.groupby(["unita", "tipo", "chi"]).size())
    dd = df[df.chi == "Daniele"]
    print(dd.groupby(["tipo", "perche"]).size())


if __name__ == "__main__":
    main()
