#!/usr/bin/env python3
"""estrai_manovre_001.py — TUTTE le frenate e sterzate di asmile #001 dai CSV sensori locali (50 Hz), agganciate al video.
Riusa training/eventi/soglie_dalle_guide.py (stesse soglie gia' passate dallo scettico il 13/11): nessuna soglia nuova.
  tratti in moto: |v|>0.5 m/s per >5 s (v da encoder ruota, Savitzky-Golay 0.5 s; circ 0.3374 m/giro encoder, D011)
  frenata: a<-0.3 m/s2 (SG 1.5 s), estesa finche' a<-0.1; durata>=1 s, calo>=0.5 m/s, v0>=0.7 m/s
           classe: stop_umano/umano (servo <1 grado e limiter <20%) oppure stop_limiter/limiter (servo attivo: NON e' Daniele)
  sterzata: |imbardata|>22 gradi/s con v>1 m/s per >=0.5 s e ampiezza manubrio >=5 gradi
Centro sterzo per data: fino al 10/11 6606; 11/11-13/11 14:14 encoder smontato/rimontato -> centro = mediana della sessione
(dichiarato 'centro_stimato'); dal 13/11 14:14 4112 (steering_limits_asmile-001.json).
Ora vera: la colonna wall prima della sincronizzazione NTP e' finta (2026-10-30 18:00): ora vera = t_ms/1000 + scarto
dell'ultima riga del file (dopo la sincronizzazione). Aggancio al video: sessione con lo stesso scarto (wall - t_ms) entro 2 s
e t_ms dentro i suoi fotogrammi; fotogramma = il piu' vicino in frames_left.csv (camera destra fisica).
Uscite: training/set_manovre/manovre_001.csv  (+ file_sensori_001.csv con i file letti)
Uso: nice -n 10 python3 training/set_manovre/estrai_manovre_001.py
"""
import csv, datetime, glob, json, os, sys
import numpy as np, pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "training", "eventi"))
import soglie_dalle_guide as G

LOG = os.path.join(ROOT, "asmile-loggers", "asmile-001")
OUT = os.path.join(ROOT, "training", "set_manovre", "manovre_001.csv")
OUTF = os.path.join(ROOT, "training", "set_manovre", "file_sensori_001.csv")
CIRC = 0.3374
FINTA = "2026-10-30"          # data dell'orologio prima dell'NTP


def epoch(w):
    return datetime.datetime.fromisoformat(w).timestamp()     # wall = ora locale del Pi (CET), come il Mac


def centro(data_iso, steer):
    if data_iso < "2026-11-11": return 6606, "6606 (calib 09/11)"
    if data_iso < "2026-11-13T14:14": return int(np.nanmedian(steer)), "centro_stimato (mediana sessione: encoder smontato 11-13/11)"
    return 4112, "4112 (calib 13/11)"


def sessioni_video():
    S = []
    for sd in sorted(glob.glob(os.path.join(LOG, "session_*"))):
        if not os.path.isdir(sd): continue
        fl = os.path.join(sd, "frames_left.csv"); md = os.path.join(sd, "metadata.json")
        vid = sd + "_left.h264"
        if not (os.path.exists(fl) and os.path.exists(md) and os.path.exists(vid)): continue
        try:
            off = json.load(open(md))["clock_map_start"]["wall_minus_boottime_s"]
            tm = np.array([int(r["t_ms"]) for r in csv.DictReader(open(fl))])
        except Exception:
            continue
        if len(tm) < 30: continue
        S.append(dict(sess=os.path.basename(sd), off=float(off), t0=tm[0], t1=tm[-1], tms=tm, video=os.path.relpath(vid, ROOT)))
    return S


def aggancia(S, t_ms, off_riga):
    for s in S:
        if abs(s["off"] - off_riga) < 2.0 and s["t0"] <= t_ms <= s["t1"]:
            k = int(np.argmin(np.abs(s["tms"] - t_ms)))
            return s["sess"], k, s["video"]
    return "", None, ""


def main():
    files = sorted(glob.glob(os.path.join(LOG, "_sensors", "sensors", "sensors_*.csv")))
    S = sessioni_video()
    rows, finfo = [], []
    for f in files:
        name = os.path.basename(f)[8:-4]
        try:
            hd = pd.read_csv(f, nrows=1)
        except Exception:
            finfo.append(dict(file=os.path.relpath(f, ROOT), esito="illeggibile")); continue
        if "enc_wheel_cum" not in hd.columns:
            finfo.append(dict(file=os.path.relpath(f, ROOT), esito="senza encoder ruota")); continue
        G.S = f.replace(name, "%s")
        try:
            d = G.load(name, CIRC)
        except Exception as e:
            finfo.append(dict(file=os.path.relpath(f, ROOT), esito=f"errore {e}")); continue
        if len(d) < 500:
            finfo.append(dict(file=os.path.relpath(f, ROOT), esito="encoder vuoto")); continue
        gps = pd.read_csv(f, usecols=["t_ms", "gps_lat", "gps_lon", "gps_fix"], low_memory=False)
        gps = gps[(gps.gps_fix == 1) & gps.gps_lat.notna()]
        last = d.iloc[-1]; off_true = epoch(last.wall) - last.t_ms / 1000.0
        data0 = datetime.datetime.fromtimestamp(d.t_ms.iloc[0] / 1000 + off_true).isoformat()
        c, cnota = centro(data0, d.enc_steer_raw.values)
        G.CENTER = c
        d["steer_deg"] = (d.enc_steer_raw - c) * G.DEG_STEP
        from scipy.signal import savgol_filter
        d["steer_rate"] = savgol_filter(d.steer_deg.values, 15, 2, deriv=1, delta=1 / G.HZ)
        segs = G.moto_segments(d)
        metri = float(sum(d.v.values[i:j].clip(min=0).sum() / G.HZ for i, j in segs))
        B = G.brake_events(d, segs, None, None); ST = G.steer_events(d, segs, None, None)
        wall_ep = np.array([epoch(w) if not w.startswith(FINTA) else np.nan for w in d.wall.values]) if (B or ST) else None
        for tipo, EV in (("frenata", B), ("sterzata", ST)):
            for e in EV:
                k = int(np.searchsorted(d.t_ms.values, e["t_ms0"]))
                k = min(k, len(d) - 1)
                off_riga = (wall_ep[k] - d.t_ms.values[k] / 1000.0) if np.isfinite(wall_ep[k]) else epoch(d.wall.values[k]) - d.t_ms.values[k] / 1000.0
                sess, fr, vid = aggancia(S, e["t_ms0"], off_riga)
                g = gps.iloc[int(np.argmin(np.abs(gps.t_ms.values - e["t_ms0"])))] if len(gps) else None
                gok = g is not None and abs(g.t_ms - e["t_ms0"]) < 2000
                r = dict(unita="asmile-001", tipo=tipo, file_sensori=os.path.relpath(f, ROOT), t_ms=e["t_ms0"],
                         ora=datetime.datetime.fromtimestamp(e["t_ms0"] / 1000 + off_true).isoformat(timespec="seconds"),
                         ora_affidabile=bool(np.isfinite(wall_ep[k])), sessione_video=sess, frame=fr, video=vid,
                         gps_lat=float(g.gps_lat) if gok else None, gps_lon=float(g.gps_lon) if gok else None,
                         centro_sterzo=cnota, fonte_v="encoder_ruota", qualita="alta")
                if tipo == "frenata":
                    r.update(chi="Daniele" if e["classe"] in ("umano", "stop_umano") else "limiter", classe=e["classe"],
                             v0_kmh=round(e["v0_kmh"], 2), v1_kmh=round(e["v1_kmh"], 2), durata_s=round(e["dur_s"], 2),
                             dec_media=round(e["a_mean"], 3), dec_picco=round(e["a_peak"], 3), spazio_m=round(e["sp_m"], 2),
                             servo_max_deg=e["brake_out_max"], limiter_frac=round(e["lim_frac"], 2))
                    i0 = k; i1 = min(len(d) - 1, k + int(e["dur_s"] * G.HZ))
                    r.update(sterzo_medio_deg=round(float(np.nanmean(np.abs(d.steer_deg.values[i0:i1 + 1]))), 1))
                else:
                    r.update(chi="Daniele", classe="sterzata", v0_kmh=round(e["v_kmh"], 2), durata_s=round(e["dur_s"], 2),
                             sterzo_ampiezza_deg=round(e["amp_deg"], 1), sterzo_vel_picco_dps=round(e["rate_peak"], 1),
                             imbardata_picco_dps=round(e["gz_peak"], 1), curvatura_1_m=round(e["k_med"], 3), anticipo_s=e["anticipo_s"])
                rows.append(r)
        finfo.append(dict(file=os.path.relpath(f, ROOT), esito="ok", inizio=data0, metri_moto=round(metri), segmenti=len(segs),
                          frenate=len(B), sterzate=len(ST), centro=cnota))
        print(name, data0[:16], "metri", round(metri), "fren", len(B), "sterz", len(ST), flush=True)
    keys = []
    for r in rows:
        for k in r:
            if k not in keys: keys.append(k)
    rows.sort(key=lambda r: (r["ora"], r["tipo"]))
    with open(OUT, "w", newline="") as fo:
        w = csv.DictWriter(fo, keys); w.writeheader(); w.writerows(rows)
    fk = []
    for r in finfo:
        for k in r:
            if k not in fk: fk.append(k)
    with open(OUTF, "w", newline="") as fo:
        w = csv.DictWriter(fo, fk); w.writeheader(); w.writerows(finfo)
    print("manovre", len(rows), "con video", sum(1 for r in rows if r["sessione_video"]))


if __name__ == "__main__":
    main()
