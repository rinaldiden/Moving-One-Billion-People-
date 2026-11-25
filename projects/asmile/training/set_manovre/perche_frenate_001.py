#!/usr/bin/env python3
"""perche_frenate_001.py — PERCHE' ha frenato Daniele: 30 frenate del giro #001 25/11 09:50 (session_20261125_095037).
Riprende la decisione asmile-seg-situation 2026-11-25 11:52 (registro palla): tassonomia FISSA, un motivo principale,
finestra -4 s/+1 s, regole costruite sulle prime 15 frenate (nel tempo) e verificate sulle ultime 15.
Verita' di confronto = lettura visiva dei fotogrammi (lettura_visiva_frenate_001_20261125.csv), scritta PRIMA di
calcolare le regole (15:40). Disaccordi e letture incerte -> coda casi dubbi per Daniele.

Ingressi (solo Mac, sola lettura):
  agents/registro_frenate/001/frenate_001.csv                      30 frenate (t_wall, v0, v1, durata, decel)
  asmile-loggers/asmile-001/_sensors/da_pi_20261125/sensors_t3290-3618_dalPi.csv   50 Hz: encoder ruota, sterzo, IMU, GPS
  asmile-loggers/_seg_sam3/frenate_001_20261125/f*.json            per fotogramma (3 Hz): SAM 3 (camera DESTRA fisica,
        pulita), Z stereo (calib VALIDATA logger/depth/calib_asmile-001.json), Z da piano fisso (+-25%), bordi guidabile
Uscite: training/set_manovre/perche_frenate_001_20261125.csv (una riga per frenata) + stampa del confronto.

Regole (soglie dichiarate in testa, ordine di priorita' fisso: vince la prima che scatta):
  1 stop_segnale        cartello stop/semaforo cf>=0.60, Z<=25 m, in >=2 fotogrammi
  2 persona_bici        persona/bambino/passeggino/carrozzina cf>=0.45, Z<=12 m, |x|<=3.5 m, in >=2 fotogrammi
  3 auto_in_arrivo      veicolo |x|<=2.5 m, Z<=25 m, che si avvicina: Z + strada fatta dalla bici cala di >1.0 m/s (>=4 punti)
  4 ostacolo_traiettoria  palo/paletto/barriera/bidone/panchina/cono/cancello/recinzione |x|<=0.70 m, 1.5<=Z<=max(4, 2.5 s*v0), >=2 fotogrammi
  5 incrocio_immissione guidabile largo >=7 m a 10-14 m e stretto <5 m a 4-6 m (si apre davanti), in >=4 fotogrammi, e bici che si ferma (v1<=4 km/h)
  6 curva               |imbardata| integrata in [t-1, t+4] >= 30 gradi oppure |sterzo| >= 15 gradi in [t, t+3]
  7 auto_ferma_laterale veicolo fermo (|velocita' propria|<=1.0 m/s) a Z<=8 m, 0.6<=|x|<=3.0 m, >=2 fotogrammi
  8 rallentamento_libero_altro  nessuna delle precedenti
  unknown               meno di 4 fotogrammi elaborati nella finestra
Giro 2 (ritocchi guardando SOLO le prime 15, prima di contare le ultime 15): distanza stereo solo con >=150 punti, piano fisso
solo per box a terra; oggetto 'a terra' (fondo del box sulla riga della strada alla sua Z, +-40%); controllo d'altezza fisico (persona 0.8-2.2 m, veicolo 0.9-3.8 m); ostacoli solo box stretti (<35% largh.);
incrocio solo con apertura in >=4 fotogrammi e bici che si ferma.
DOPO il conteggio (dichiarato): aggiunto il secondo file sensori (sensors_20261125_095548) perche' le frenate 26-30 cadevano
dopo la fine del primo e non avevano sterzo/imbardata (prima: verifica 6/15, dopo: 7/15; #27 diventa 'curva' per lo sterzo 18 gradi).
Poi la revisione dello scettico (revisione_scettico_frenate_001.csv) rimanda a Daniele #26, #27, #29, #30.
"""
import csv, glob, json, os, sys
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FR = os.path.join(ROOT, "agents/registro_frenate/001/frenate_001.csv")
SENS = [os.path.join(ROOT, "asmile-loggers/asmile-001/_sensors/da_pi_20261125/sensors_t3290-3618_dalPi.csv"),
        os.path.join(ROOT, "asmile-loggers/asmile-001/_sensors/sensors/sensors_20261125_095548.csv")]   # il giro continua nel file delle 09:55:48
SEG = os.path.join(ROOT, "asmile-loggers/_seg_sam3/frenate_001_20261125")
VIS = os.path.join(ROOT, "training/set_manovre/lettura_visiva_frenate_001_20261125.csv")
OUT = os.path.join(ROOT, "training/set_manovre/perche_frenate_001_20261125.csv")
SESS_DIR = os.path.join(ROOT, "asmile-loggers/asmile-001/session_20261125_095037")
T0_VIDEO = 1795596646.0
CIRC, CENTER, DEG_STEP, GZ_SEGNO = 0.3374, 4112, 0.02197, -1.0

PERSONE = {"person", "child", "stroller", "wheelchair"}
VEICOLI = {"car", "van", "truck", "bus", "motorcycle", "tractor"}
OSTACOLI = {"pole", "bollard", "barrier", "trash can", "bench", "traffic cone", "gate", "fence", "chain", "boom barrier", "metal grille", "railing"}
SEGNALI = {"stop sign", "traffic light"}
TAX = ["curva", "incrocio_immissione", "auto_in_arrivo", "auto_ferma_laterale", "persona_bici", "stop_segnale",
       "ostacolo_traiettoria", "rallentamento_libero_altro", "unknown"]


def carica_sensori(files=None, off=None, center=None):
    """files/off/center: per riusarlo su altre sessioni #001 (build_set.py); default = giro 25/11 09:50"""
    import pandas as pd
    files = files or SENS
    d = pd.concat([pd.read_csv(f, low_memory=False, usecols=["t_ms", "enc_wheel_cum", "enc_steer_raw", "imu_gz_dps", "gps_lat", "gps_lon", "gps_fix"]) for f in files])
    d = d.drop_duplicates("t_ms").sort_values("t_ms").reset_index(drop=True)
    if off is None: off = json.load(open(os.path.join(SESS_DIR, "metadata.json")))["clock_map_start"]["wall_minus_boottime_s"]
    d["tw"] = d.t_ms / 1000 + off
    d = d[d.enc_wheel_cum.notna()].reset_index(drop=True)
    d["s"] = d.enc_wheel_cum.astype(float) * CIRC / 16384.0
    from scipy.signal import savgol_filter
    d["v"] = savgol_filter(d.s.values, 25, 2, deriv=1, delta=0.02)
    still = np.abs(d.v) < 0.05
    bias = float(d.imu_gz_dps[still].median()) if still.sum() > 200 else 0.0
    d["gz"] = (d.imu_gz_dps - bias) * GZ_SEGNO
    d["steer"] = (d.enc_steer_raw - (CENTER if center is None else center)) * DEG_STEP
    return d, bias


def carica_frame():
    F = []
    for f in sorted(glob.glob(os.path.join(SEG, "f*.json"))):
        F.append(json.load(open(f)))
    return F


F_PX = 1379.9         # focale rettificata a piena risoluzione (calib VALIDATA #001)
W_IMG, H_IMG = 1280, 800


def zeta(dt):
    """Distanza affidabile o None. Giro 2 (costruito sulle prime 15): stereo solo con >=150 punti validi (meno = rumore,
    visto: pali a 2 m che stanno a 10 m); piano fisso solo se il fondo del box e' a terra (sotto l'orizzonte) e il box non
    e' tagliato in alto. Visto: z_st<1.5 sui muri a destra (barra/ripetizione) -> scartato."""
    if dt.get("z_st") is not None and dt.get("n_st", 0) >= 150 and 1.5 <= dt["z_st"] <= 30: return dt["z_st"]
    x1, y1, x2, y2 = dt["box"]
    if dt.get("z_gr") is not None and y2 > 470 and y1 > 5 and 1.5 <= dt["z_gr"] <= 30: return dt["z_gr"]
    return None


def altezza_ok(dt, z, lo, hi):
    """controllo fisico: altezza vera = altezza in pixel * Z / f deve stare in [lo, hi] m (box non tagliato ai bordi)"""
    x1, y1, x2, y2 = dt["box"]
    if y1 <= 5 or y2 >= H_IMG - 5: return True          # tagliato: non controllabile
    return lo <= (y2 - y1) * z / F_PX <= hi


def a_terra(dt, z):
    """giro 2: un oggetto vicino sta sulla strada -> il fondo del box deve cadere sulla riga della strada alla sua distanza
    (Z dal punto di contatto col piano fisso entro +-40% della Z usata). Visto: pali 'a 2 m' con il fondo sopra l'orizzonte."""
    x1, y1, x2, y2 = dt["box"]
    if y2 >= H_IMG - 5: return True                     # fondo tagliato dal bordo: non controllabile
    zg = dt.get("z_gr")
    return zg is not None and abs(zg - z) <= 0.4 * z


def stretto_box(dt):
    x1, y1, x2, y2 = dt["box"]
    return (x2 - x1) < 0.35 * W_IMG                     # i box larghi sono muri/barriere lunghe, non oggetti puntuali


def features(t, v0, d, F):
    w = d[(d.tw >= t - 1) & (d.tw <= t + 4)]
    dpsi = float(np.trapezoid(w.gz.values, w.tw.values)) if len(w) > 10 else np.nan
    w2 = d[(d.tw >= t) & (d.tw <= t + 3)]
    steer = float(np.nanmax(np.abs(w2.steer.values))) if len(w2) else np.nan
    g = d.iloc[int(np.argmin(np.abs(d.tw.values - t)))]
    s_at = lambda tt: float(np.interp(tt, d.tw.values, d.s.values))
    fw = [f for f in F if t - 4 <= f["t_wall"] <= t + 0.5]
    out = dict(n_frame=len(fw), dpsi_deg=dpsi, sterzo_max_deg=steer, lat=float(g.gps_lat) if g.gps_fix == 1 else None,
               lon=float(g.gps_lon) if g.gps_fix == 1 else None, s_frame=[f["frame"] for f in fw])
    seen = {k: [] for k in ("segnale", "persona", "ostacolo", "veic_lat", "apertura", "stretto")}
    vser = []          # (t, Z + strada fatta) del veicolo centrale piu' vicino
    for f in fw:
        dets = [x for x in f["dets"] if not x.get("ego") and x["cf"] >= 0.45]
        for x in dets:
            z = zeta(x); xx = x.get("x")
            if z is None or xx is None: continue
            if x["c"] in SEGNALI and x["cf"] >= 0.60 and z <= 25: seen["segnale"].append((f["frame"], x["c"], z, xx))
            if x["c"] in PERSONE and z <= 12 and abs(xx) <= 3.5 and altezza_ok(x, z, 0.8, 2.2) and a_terra(x, z): seen["persona"].append((f["frame"], x["c"], z, xx))
            if x["c"] in OSTACOLI and stretto_box(x) and a_terra(x, z) and abs(xx) <= 0.70 and z <= max(4.0, 2.5 * v0): seen["ostacolo"].append((f["frame"], x["c"], z, xx))
        vc = [(zeta(x), x.get("x")) for x in dets if x["c"] in VEICOLI and zeta(x) is not None and x.get("x") is not None and altezza_ok(x, zeta(x), 0.9, 3.8)]   # veicoli: niente controllo a_terra (box grandi, stereo affidabile; con a_terra si perdeva l auto in arrivo di #8-#9)
        cen = [(z, xx) for z, xx in vc if abs(xx) <= 2.5 and z <= 25]
        if cen:
            for z, xx in cen: vser.append((f["t_wall"], z + s_at(f["t_wall"]) - s_at(t), z, xx))
        for z, xx in vc:
            if z <= 8 and 0.6 <= abs(xx) <= 3.0: seen["veic_lat"].append((f["frame"], f["t_wall"], z, xx))
        e = f.get("edges") or {}
        wd = lambda k: (e.get(k)[1] - e.get(k)[0]) if e.get(k) else None
        near = [wd(k) for k in ("4", "6") if wd(k) is not None]; far = [wd(k) for k in ("10", "14") if wd(k) is not None]
        if near and far and max(far) >= 7 and min(near) < 5: seen["apertura"].append(f["frame"])
        if near and min(near) < 2.5: seen["stretto"].append(f["frame"])
    # veicolo in arrivo: pendenza di (Z + strada fatta) nel tempo, Theil-Sen
    slope = None
    # giro 2: si segue LO STESSO veicolo (catena per |dX|<=0.8 m e Z coerente +-30%), non il piu' vicino di ogni fotogramma
    # (nel parcheggio di #8 il 'piu' vicino' saltava da un'auto all'altra). Vale la catena piu' lunga.
    catene = []
    for p in sorted(vser):
        c = next((c for c in catene if 0 < p[0] - c[-1][0] <= 0.8 and abs(p[3] - c[-1][3]) <= 0.8 and abs(p[2] - c[-1][2]) <= 0.3 * c[-1][2] + 1.0), None)
        if c is not None: c.append(p)
        else: catene.append([p])
    lunga = max(catene, key=len) if catene else []
    if len(lunga) >= 4:
        tt = np.array([a[0] for a in lunga]); zz = np.array([a[1] for a in lunga])
        sl = [(zz[j] - zz[i]) / (tt[j] - tt[i]) for i in range(len(tt)) for j in range(i + 1, len(tt)) if tt[j] - tt[i] > 0.3]
        slope = float(np.median(sl)) if sl else None
    # veicolo laterale fermo: stessa idea sulle sue Z (se >=2 punti)
    lat_static = False
    if len(seen["veic_lat"]) >= 2:
        tt = np.array([a[1] for a in seen["veic_lat"]]); zz = np.array([a[2] + s_at(a[1]) - s_at(t) for a in seen["veic_lat"]])
        lat_static = bool(abs(np.median(np.diff(zz) / np.maximum(np.diff(tt), 0.05))) <= 1.0) if len(tt) > 1 else False
    nfr = lambda L: len(set(a[0] for a in L))
    out.update(segnale_n=nfr(seen["segnale"]), persona_n=nfr(seen["persona"]), ostacolo_n=nfr(seen["ostacolo"]),
               veic_lat_n=nfr(seen["veic_lat"]), veic_lat_fermo=lat_static, veic_centro_n=len(lunga),
               veic_vel_propria_ms=None if slope is None else round(-slope, 2), apertura_n=len(set(seen["apertura"])),
               stretto_n=len(set(seen["stretto"])),
               persona_zmin=min([a[2] for a in seen["persona"]], default=None), ostacolo_zmin=min([a[2] for a in seen["ostacolo"]], default=None),
               ostacolo_classi="|".join(sorted(set(a[1] for a in seen["ostacolo"]))), veic_centro_zmin=min([a[2] for a in lunga], default=None))
    return out


def regole(ft):
    scattate = []
    if ft["n_frame"] < 4: return "unknown", ["pochi_fotogrammi"]
    if ft["segnale_n"] >= 2: scattate.append("stop_segnale")
    if ft["persona_n"] >= 2: scattate.append("persona_bici")
    if ft["veic_vel_propria_ms"] is not None and ft["veic_vel_propria_ms"] > 1.0: scattate.append("auto_in_arrivo")
    if ft["ostacolo_n"] >= 2: scattate.append("ostacolo_traiettoria")
    if ft["apertura_n"] >= 4 and ft["v1_kmh"] <= 4.0: scattate.append("incrocio_immissione")      # giro 2: apertura da sola scattava quasi sempre
    if (np.isfinite(ft["dpsi_deg"]) and abs(ft["dpsi_deg"]) >= 30) or (np.isfinite(ft["sterzo_max_deg"]) and ft["sterzo_max_deg"] >= 15): scattate.append("curva")
    if ft["veic_lat_n"] >= 2 and ft["veic_lat_fermo"]: scattate.append("auto_ferma_laterale")
    return (scattate[0] if scattate else "rallentamento_libero_altro"), scattate


def main():
    d, bias = carica_sensori()
    F = carica_frame()
    fr = list(csv.DictReader(open(FR)))
    vis = {int(r["n"]): r for r in csv.DictReader(open(VIS))}
    rows = []
    for n, r in enumerate(fr, 1):
        t = float(r["t_wall"]); v0 = float(r["v0_kmh"]) / 3.6
        ft = features(t, v0, d, F); ft["v1_kmh"] = float(r["v1_kmh"])
        lab, sc = regole(ft)
        conf = "bassa" if lab in ("rallentamento_libero_altro", "unknown") else ("alta" if len(sc) == 1 else "media")
        vv = vis.get(n, {})
        rows.append(dict(n=n, gruppo="costruzione" if n <= 15 else "verifica", t_wall=t, t_video_s=round(t - T0_VIDEO, 2),
                         frame=int(round((t - T0_VIDEO) * 15)), v0_kmh=float(r["v0_kmh"]), v1_kmh=float(r["v1_kmh"]), durata_s=float(r["durata_s"]),
                         dec_media=float(r["dec_media"]), dec_picco=float(r["dec_picco"]), tipo=r["tipo"],
                         perche_regola=lab, regole_scattate="|".join(sc), conf_regola=conf,
                         perche_visivo=vv.get("visivo", ""), conf_visivo=vv.get("conf", ""), nota_visiva=vv.get("nota", ""),
                         accordo=lab == vv.get("visivo"),
                         perche=lab if lab == vv.get("visivo") else "unknown",
                         conf=("alta" if vv.get("conf") == "alta" else "media") if (lab == vv.get("visivo") and vv.get("conf") != "bassa" and lab != "rallentamento_libero_altro") else "bassa",
                         in_coda_daniele=not (lab == vv.get("visivo") and vv.get("conf") != "bassa" and lab != "rallentamento_libero_altro"),
                         **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in ft.items() if k not in ("s_frame", "v1_kmh")}))
    rev = os.path.join(ROOT, "training/set_manovre/revisione_scettico_frenate_001.csv")
    if os.path.exists(rev):
        for rv in csv.DictReader(open(rev)):
            x = rows[int(rv["n"]) - 1]
            x.update(perche=rv["perche"], conf="bassa", in_coda_daniele=rv["in_coda_daniele"] == "True", revisione=rv["nota"])
    for x in rows: x.setdefault("revisione", "")
    keys = list(rows[0].keys())
    with open(OUT, "w", newline="") as fo:
        w = csv.DictWriter(fo, keys); w.writeheader(); w.writerows(rows)
    solo = sys.argv[1] if len(sys.argv) > 1 else "tutte"
    print("bias gz", round(bias, 2))
    for g in ("costruzione", "verifica"):
        if solo != "tutte" and g != solo: continue
        R = [x for x in rows if x["gruppo"] == g]
        print(f"== {g}: accordo regola/visivo {sum(x['accordo'] for x in R)}/{len(R)}")
        for x in R:
            print(f"#{x['n']:2d} regola={x['perche_regola']:26s} visivo={x['perche_visivo']:26s} [{x['regole_scattate']}] dpsi={x['dpsi_deg']} st={x['sterzo_max_deg']} "
                  f"pers={x['persona_n']}/{x['persona_zmin']} vcen={x['veic_centro_n']} vprop={x['veic_vel_propria_ms']} vlat={x['veic_lat_n']}{'F' if x['veic_lat_fermo'] else ''} "
                  f"ost={x['ostacolo_n']}/{x['ostacolo_classi']} ap={x['apertura_n']} str={x['stretto_n']} nfr={x['n_frame']}")


if __name__ == "__main__":
    main()
