#!/usr/bin/env python3
"""inventario.py — INVENTARIO delle sessioni video in asmile-loggers/ per costruire il set di manovre
(frenate e sterzate di Daniele). Tre unita', MAI confuse:
  asmile-001        = #001: 2 OV9281 separate (session_<ts>_left/right.h264 + session_<ts>/ con frames_*.csv, metadata.json)
                      sensori _sensors/sensors/*.csv a 50 Hz (t_ms = boottime del Pi)
  asmile-logger001  = cartella asmile-loggers/asmile-logger: Camarray SBS 2560x800, clip_<ts>_<n>.h264, IMU (+ ruota BLE a volte), niente GPS/sterzo
  logger02          = HW3, schede A e B: clip_<ts>_<A|B>_<n>.h264 + _frames.csv per clip; IMU sulla A (sensors_<ts>_<n>.csv)

Leggero e deterministico: solo stdlib + pandas/numpy, ffprobe per l'intestazione, ffmpeg per AL MASSIMO 3 fotogrammi
per sessione (luminosita'), mai un video intero. Stessa entrata -> stessa uscita, righe ordinate per unita'+sessione.
Uso:  nice -n 10 python3 inventario.py [--no-luma] [--out FILE]

Orari: tutto in ora locale italiana (Europe/Rome; a novembre CET = UTC+1).
#001: t_wall = t_ms/1000 + wall_minus_boottime_s. Il Pi parte con orologio FALSO (fake-hwclock fermo al 2026-10-30 18:00):
      nomi file e prime righe dei CSV possono avere data 30/10 ma contenere altri giorni. Per ogni CSV sensori si usa
      l'offset (wall - t_ms) delle ULTIME righe (dopo la sincronizzazione NTP); per ogni video il clock_map_end se e'
      buono, altrimenti il clock_map_start. Video e sensori si abbinano per offset di boot (+-0.05 s) E per intervallo t_ms.
logger001: frames.csv ha solo t_ms; l'offset viene dai CSV sensori dello stesso boot (stesso metodo).
logger02: frames.csv per clip (t_us scheda; sulla B t_a_us = orologio della A); IMU nei sensors della A (t_us).
"""
import argparse, csv, datetime, glob, hashlib, io, json, os, re, subprocess, sys
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ASMILE = os.path.abspath(os.path.join(HERE, "..", ".."))
LOG = os.path.join(ASMILE, "asmile-loggers")
D001 = os.path.join(LOG, "asmile-001")
DLOG = os.path.join(LOG, "asmile-logger")
D02 = os.path.join(LOG, "logger02")
CALIB = os.path.join(ASMILE, "logger", "depth")
TZ = ZoneInfo("Europe/Rome")
FUSO = "Europe/Rome (CET UTC+1)"

BOGUS_001 = 1793379610.5          # wall_minus_boottime con orologio fermo al 30/10 18:00 (#001)
BOGUS_LIM = 1793500000.0          # offset sotto questa soglia (= prima del 31/10/2026) -> orologio mai sincronizzato
M_PER_COUNT = 2.1219e-5           # encoder ruota #001 (fleet/DEPLOY_LOG.md 2026-11-09: 0.3477 m/giro encoder)
V_MOVE = 0.5                      # m/s, soglia "in moto"
LOW_LIGHT = 60.0                  # luminosita' media sotto cui luce scarsa (stessa soglia di training/sim2real/harvest.py)
DARK = 15.0                       # sotto: video nero/notte/obiettivo coperto -> non usabile
HOLD = {"imu": 0.5, "encoder_ruota": 0.5, "encoder_sterzo": 0.5, "gps": 2.0, "ruota_ble": 3.0}
GRID = 0.5                        # passo (s) della griglia su cui si misura la copertura


def ep_local(s):
    """'2026-11-25T10:55:48.157' (ora locale italiana, naive) -> epoch."""
    return datetime.datetime.fromisoformat(s).replace(tzinfo=TZ).timestamp()


def fmt(ep):
    d = datetime.datetime.fromtimestamp(ep, TZ)
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M:%S")


def name_ep(ts):
    """'20261125_104101' (ora locale) -> epoch."""
    return datetime.datetime.strptime(ts, "%Y%m%d_%H%M%S").replace(tzinfo=TZ).timestamp()


def r1(x, n=1):
    return "" if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


def rel(p):
    return os.path.relpath(p, ASMILE) if p else ""


def read_csv_clean(path, **kw):
    """CSV tollerante: toglie i byte NUL (coda di file troncati sul Pi) e le righe rotte."""
    with open(path, "rb") as f:
        raw = f.read().replace(b"\x00", b"")
    if not raw.strip():
        return pd.DataFrame()
    try:
        return pd.read_csv(io.BytesIO(raw), on_bad_lines="skip", low_memory=False, **kw)
    except (pd.errors.EmptyDataError, ValueError):
        return pd.DataFrame()


def num(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def coverage(sample_t, w0, w1, hold):
    """frazione (0-1) della finestra [w0,w1] (stesse unita' di sample_t, secondi) coperta da campioni validi."""
    if w1 is None or w0 is None or w1 <= w0:
        return None
    s = np.sort(np.asarray(sample_t, dtype=float))
    if len(s) == 0:
        return 0.0
    g = np.arange(w0, w1, GRID)
    i = np.searchsorted(s, g, side="right") - 1
    ok = (i >= 0) & ((g - s[np.clip(i, 0, None)]) <= hold)
    return float(ok.mean()) if len(g) else None


def pct(x):
    return "" if x is None else f"{round(100 * x)}%"


# ----------------------------------------------------------------------------------------------- ffprobe / luminosita'
_probe = {}


def probe_res(path):
    if path in _probe:
        return _probe[path]
    try:
        out = subprocess.run(["nice", "-n", "10", "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=width,height", "-of", "csv=p=0", path], capture_output=True, text=True, timeout=30).stdout
        w, h = out.strip().split("\n")[0].split(",")[:2]
        _probe[path] = f"{int(w)}x{int(h)}"
    except Exception:
        _probe[path] = ""
    return _probe[path]


def luma(path, nframe=0):
    """luminosita' media (0-255) di UN fotogramma: il numero nframe (decodifica solo fino a li', h264 grezzo senza pts)."""
    vf = (f"select=eq(n\\,{int(nframe)})," if nframe else "") + "scale=64:40,format=gray"
    cmd = ["nice", "-n", "10", "ffmpeg", "-v", "error", "-nostdin", "-threads", "1", "-i", path,
           "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-"]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=60).stdout
        if len(out) >= 64 * 40:
            return float(np.frombuffer(out[:64 * 40], np.uint8).mean())
    except Exception:
        pass
    return None


def calib_for(unit, date):
    if unit == "asmile-001":
        f = "calib_asmile-001.json"
        if not os.path.exists(os.path.join(CALIB, f)):
            return "mancante"
        s = rel(os.path.join(CALIB, f)) + " (VALIDATA 25/11, set camere attuale"
        return s + (")" if (date and date >= "2026-11-11") else "; montaggio camere a quella data non verificato)")
    if unit == "asmile-logger001":
        have = [f for f in ("calib_asmile-logger_metro.json", "calib_asmile-logger001.CANDIDATO_20261121.json")
                if os.path.exists(os.path.join(CALIB, f))]
        if not have:
            return "mancante"
        out = []
        if "calib_asmile-logger_metro.json" in have:
            out.append("logger/depth/calib_asmile-logger_metro.json (metro 08/11, in uso in logger_guide.py)")
        if "calib_asmile-logger001.CANDIDATO_20261121.json" in have:
            out.append("logger/depth/calib_asmile-logger001.CANDIDATO_20261121.json (CANDIDATO, non validata)")
        return " + ".join(out)
    return "non definitiva (solo CANDIDATI logger/depth/calib_logger02.CANDIDATO_*)"


# ================================================================================================ asmile #001
def sensor_index_001():
    """per ogni CSV sensori #001: offset finale (dopo NTP), offset iniziale, intervallo t_ms."""
    files = sorted(glob.glob(os.path.join(D001, "_sensors", "sensors", "sensors_*.csv"))) + \
        sorted(glob.glob(os.path.join(D001, "_sensors", "sensors_*.csv"))) + \
        sorted(glob.glob(os.path.join(D001, "_sensors", "da_pi_*", "sensors_*.csv")))
    idx = []
    for f in files:
        d = read_csv_clean(f, usecols=["t_ms", "wall"], dtype=str)
        if d.empty:
            continue
        d = num(d, ["t_ms"]).dropna()
        tail = d.tail(200)
        off_end = float(np.median([ep_local(w) - t / 1000 for t, w in zip(tail.t_ms, tail.wall)]))
        off_0 = ep_local(d.wall.iloc[0]) - d.t_ms.iloc[0] / 1000
        idx.append(dict(path=f, off=off_end, off0=off_0, t0=float(d.t_ms.min()), t1=float(d.t_ms.max()),
                        nome_falso=abs(off_0 - off_end) > 2.0))
    return idx


_cache = {}


def load_001(path):
    if path not in _cache:
        cols = ["t_ms", "imu_ax_g", "enc_t_ms", "enc_wheel_cum", "enc_steer_raw", "gps_t_ms", "gps_fix", "gps_speed_ms", "gps_hdop", "brake_out_deg"]
        d = read_csv_clean(path, usecols=lambda c: c in cols, dtype=str)
        _cache[path] = num(d, cols)
    return _cache[path]


def limiter_index_001():
    """limiter_v3 (attivo_/ombra_) e speed_limiter v2: offset di boot e intervallo t per abbinarli alle sessioni."""
    out = []
    for f in sorted(glob.glob(os.path.join(D001, "_sensors", "limiter_v3", "*.csv"))):
        try:
            with open(f, "rb") as fh:
                lines = [l for l in fh.read().replace(b"\x00", b"").decode(errors="ignore").splitlines() if l.strip()]
            h = lines[0].split(",")
            iw, it = h.index("t_wall"), h.index("t")
            a, b = lines[1].split(","), lines[-1].split(",")
            out.append(dict(path=f, tipo=os.path.basename(f).split("_")[0], off=float(b[iw]) - float(b[it]),
                            t0=float(a[it]), t1=float(b[it])))
        except Exception:
            continue
    return out


def lim_load(path):
    if path not in _cache:
        cols = ["t", "v_enc", "enc_fresco", "v_fus", "imu_ok", "angolo"]
        d = read_csv_clean(path, usecols=lambda c: c in cols, dtype=str)
        _cache[path] = num(d, ["t", "v_enc", "v_fus", "angolo"]).dropna(subset=["t"])
    return _cache[path]


def sessions_001():
    names = set()
    for p in os.listdir(D001):
        m = re.match(r"session_(\d{8}_\d{6})(?:_(left|right)\.h264)?$", p)
        if m:
            names.add(m.group(1))
    return sorted(names)


def frames_001(path):
    if not os.path.exists(path):
        return None
    d = read_csv_clean(path)
    if d.empty or "t_ms" not in d.columns:
        return None
    d = num(d, ["t_ms", "exposure_us"]).dropna(subset=["t_ms"])
    return d if len(d) else None


def legacy_001(w0, w1):
    """sessioni senza clock_map (30/10 pomeriggio, 07/11): sensori nei CSV vecchi con timestamp wall nell'orologio del Pi."""
    res = {}
    src = []
    for f in sorted(glob.glob(os.path.join(D001, "_sensors", "speed_limiter", "*.csv"))):
        d = read_csv_clean(f, dtype=str)
        if d.empty or "timestamp_iso" not in d.columns:
            continue
        t = np.array([ep_local(x) for x in d.timestamp_iso])
        m = (t >= w0 - 5) & (t <= w1 + 5)
        if m.sum() == 0:
            continue
        src.append(f)
        d = num(d, ["enc_speed_ms", "enc_fresh", "accel_x_g", "fix"])
        dm = d[m]; tm = t[m]
        res.setdefault("encoder_ruota", []).extend(tm[dm.enc_fresh.values == 1])
        res.setdefault("imu", []).extend(tm[dm.accel_x_g.notna().values])
        res.setdefault("gps", []).extend(tm[(dm.fix.values > 0)])
        res.setdefault("_v", []).extend(zip(tm[dm.enc_fresh.values == 1], dm.enc_speed_ms.values[dm.enc_fresh.values == 1]))
    for f in sorted(glob.glob(os.path.join(D001, "_sensors", "training_data_pi", "*.csv"))):
        day = os.path.basename(f)[9:17]
        if day != datetime.datetime.fromtimestamp(w0, TZ).strftime("%Y%m%d"):
            continue
        d = read_csv_clean(f, dtype=str)
        if d.empty or "timestamp" not in d.columns:
            continue
        t = np.array([ep_local(x) for x in d.timestamp])
        m = (t >= w0 - 5) & (t <= w1 + 5)
        if m.sum() == 0:
            continue
        src.append(f)
        d = num(d, ["imu_accel_x", "encoder_pos", "gps_lat"])
        dm = d[m]; tm = t[m]
        res.setdefault("imu", []).extend(tm[dm.imu_accel_x.notna().values])
        res.setdefault("encoder_sterzo", []).extend(tm[dm.encoder_pos.notna().values])
        res.setdefault("gps", []).extend(tm[dm.gps_lat.notna().values & (dm.gps_lat.values != 0)])
    return res, src


def do_001(luma_on):
    sidx = sensor_index_001()
    lidx = limiter_index_001()
    rows, problemi = [], []
    for s in sessions_001():
        base = os.path.join(D001, "session_" + s)
        meta = {}
        try:
            meta = json.load(open(os.path.join(base, "metadata.json")))
        except Exception:
            pass
        vids = [base + "_left.h264", base + "_right.h264"]
        vsz = [os.path.getsize(v) if os.path.exists(v) else 0 for v in vids]
        nvid = sum(1 for z in vsz if z > 0)
        fl = frames_001(os.path.join(base, "frames_left.csv"))
        fr = frames_001(os.path.join(base, "frames_right.csv"))
        ff = fl if fl is not None else fr
        cs = (meta.get("clock_map_start") or {}).get("wall_minus_boottime_s")
        ce = (meta.get("clock_map_end") or {}).get("wall_minus_boottime_s")
        bog = lambda x: x is not None and abs(x - BOGUS_001) < 60
        off = ce if (ce is not None and not bog(ce)) else (cs if (cs is not None and not bog(cs)) else None)
        note = []
        if s.startswith("20261030_18"):
            note.append("nome con orologio falso 30/10")
        t0 = t1 = fps = None
        if ff is not None:
            t0, t1 = float(ff.t_ms.iloc[0]), float(ff.t_ms.iloc[-1])
            dt = np.diff(ff.t_ms.values)
            fps = 1000.0 / np.median(dt) if len(dt) else None
        if fl is not None and fr is not None and abs(len(fl) - len(fr)) > 2:
            note.append(f"fotogrammi sx/dx diversi {len(fl)}/{len(fr)}")
        # --- inizio e durata
        ep0, ora_fonte = None, ""
        if off is not None and t0 is not None:
            ep0, ora_fonte = off + t0 / 1000, "t_ms frames + clock_map " + ("end" if off == ce and not bog(ce) and off != cs else "start")
        elif cs is None and meta.get("start_time") and not s.startswith("20261030_18"):
            ep0, ora_fonte = ep_local(meta["start_time"]), "metadata start_time (orologio Pi, senza clock_map)"
        elif meta.get("start_time") and s.startswith("20261030_18") and cs is None:
            ora_fonte = "mancante: orologio falso (fake-hwclock 30/10 18:00), data reale sconosciuta"
        elif bog(cs) and (ce is None or bog(ce)):
            ora_fonte = "mancante: orologio falso per tutta la sessione, data reale sconosciuta"
        else:
            ora_fonte = "mancante"
        if t0 is not None:
            dur, dfonte = (t1 - t0) / 1000 + (1 / fps if fps else 0), "frames_left.csv t_ms"
        elif meta.get("duration_seconds"):
            dur, dfonte = float(meta["duration_seconds"]), "metadata duration_seconds"
        else:
            dur, dfonte = None, "mancante"
        data, ora = fmt(ep0) if ep0 else ("", "")
        if not data and s[:8] != "20261030" or (not data and s.startswith("20261030_15")):
            pass
        res = meta.get("resolution", "")
        if nvid:
            pr = probe_res(vids[0] if vsz[0] else vids[1])
            if pr and res and pr != res:
                note.append(f"ffprobe {pr} != metadata {res}")
            res = res or pr
        bcfg = meta.get("bitrate")
        bkbps = (np.mean([z for z in vsz if z > 0]) * 8 / dur / 1000) if (nvid and dur) else None
        expo = float(ff.exposure_us.median()) if (ff is not None and "exposure_us" in ff.columns) else None
        lum = None
        if luma_on and nvid and dur:
            # fotogramma 75 (= 5 s a 15 fps, dopo il riscaldamento dell'esposizione) o meta' sessione se piu' corta
            lum = luma(vids[0] if vsz[0] else vids[1], nframe=int(min(75, dur * 15 / 2)))
        # --- sensori
        cov, files, mov_s, dist, brake_s, brake_max, mfonte, dis = {}, [], None, None, None, None, "", False
        if off is not None and t0 is not None:
            match = [x for x in sidx if abs(x["off"] - off) < 0.05 and x["t1"] >= t0 and x["t0"] <= t1]
            # stesso file in due cartelle (sensors/ e radice _sensors/): preferisco sensors/
            seen = {}
            for x in match:
                k = os.path.basename(x["path"])
                if k not in seen or "/sensors/sensors_" in x["path"]:
                    seen[k] = x
            match = sorted(seen.values(), key=lambda x: x["t0"])
            files = [x["path"] for x in match]
            for x in match:
                if x["nome_falso"]:
                    note.append(f"{os.path.basename(x['path'])}: nome/prime righe con data falsa, contenuto del {fmt(x['off'] + x['t1'] / 1000)[0]}")
            if match:
                d = pd.concat([load_001(f) for f in files], ignore_index=True).drop_duplicates("t_ms").sort_values("t_ms")
                d = d[(d.t_ms >= t0 - 1000) & (d.t_ms <= t1 + 1000)]
                ts = d.t_ms.values / 1000
                w0, w1 = t0 / 1000, t1 / 1000
                cov["imu"] = coverage(ts[d.imu_ax_g.notna().values], w0, w1, HOLD["imu"])
                encf = d.enc_t_ms.notna().values & ((d.t_ms - d.enc_t_ms).abs().values < 500)
                cov["encoder_ruota"] = coverage(ts[encf & d.enc_wheel_cum.notna().values], w0, w1, HOLD["encoder_ruota"])
                cov["encoder_sterzo"] = coverage(ts[encf & d.enc_steer_raw.notna().values], w0, w1, HOLD["encoder_sterzo"])
                gpsok = d.gps_fix.notna().values & (d.gps_fix.fillna(0).values > 0)
                cov["gps"] = coverage(ts[gpsok], w0, w1, HOLD["gps"])
                cov["ruota_ble"] = None
                e = d[encf & d.enc_wheel_cum.notna().values & (d.t_ms >= t0) & (d.t_ms <= t1)]
                if len(e) > 50:
                    # velocita' su passi di 0.5 s
                    g = np.arange(e.t_ms.iloc[0], e.t_ms.iloc[-1], 500.0)
                    c = np.interp(g, e.t_ms.values, e.enc_wheel_cum.values)
                    v = np.abs(np.diff(c)) * M_PER_COUNT / 0.5
                    hole = np.diff(np.searchsorted(e.t_ms.values, g)) == 0   # nessun campione nel passo -> non contare
                    v[hole] = 0
                    mov_s = float((v > V_MOVE).sum() * 0.5)
                    dist = float(np.sum(v[v < 15]) * 0.5)
                    mfonte = "encoder ruota |v|>0.5 m/s"
                # controllo incrociato col GPS (fix e velocita' > 1 m/s): se il GPS vede moto e l'encoder no -> encoder sospetto
                # (solo fix buoni: hdop < 1.5 e 1 < v < 15 m/s; al chiuso il GPS da' hdop 2-7 e velocita' fasulle fino a 35 m/s)
                gv = d.gps_speed_ms.fillna(0).values
                gm = gpsok & (gv > 1.0) & (gv < 15) & (d.gps_hdop.fillna(99).values < 1.5)
                gps_mov = (coverage(ts[gm], w0, w1, HOLD["gps"]) or 0) * (w1 - w0)
                if mov_s is not None and gps_mov > 3 * max(mov_s, 1) and gps_mov - mov_s > 60:
                    note.append(f"DISACCORDO moto: encoder {r1(mov_s, 0)} s vs GPS {r1(gps_mov, 0)} s in moto: encoder ruota sospetto")
                    dis = True
                b = d[(d.t_ms >= t0) & (d.t_ms <= t1)].brake_out_deg
                if b.notna().any():
                    brake_max = float(b.max())
                    brake_s = float(coverage(ts[(d.t_ms >= t0).values & (d.t_ms <= t1).values & (d.brake_out_deg.fillna(0).values > 1)],
                                             w0, w1, 0.05) * (w1 - w0))
        elif ep0 is not None and dur:
            lg, src = legacy_001(ep0, ep0 + dur)
            files = src
            if src:
                note.append("sensori dai CSV vecchi (speed_limiter/training_data_pi) abbinati per orologio del Pi")
                for k in ("imu", "encoder_ruota", "encoder_sterzo", "gps"):
                    cov[k] = coverage(lg.get(k, []), ep0, ep0 + dur, HOLD[k] if k != "encoder_ruota" else 1.0)
                cov["ruota_ble"] = None
                vv = sorted(lg.get("_v", []))
                if vv:
                    tt = np.array([a for a, _ in vv]); sp = np.array([b for _, b in vv], float)
                    g = np.arange(ep0, ep0 + dur, 0.5)
                    i = np.clip(np.searchsorted(tt, g, side="right") - 1, 0, None)
                    ok = (g - tt[i]) <= 1.0
                    mov_s = float(((sp[i] > V_MOVE) & ok).sum() * 0.5)
                    mfonte = "speed_limiter enc_speed_ms>0.5 (CSV vecchio)"
        # --- limiter (limiter_v3: anche controllo incrociato del moto e ripiego se mancano i CSV sensori)
        lim = ""
        if off is not None and t0 is not None:
            lm = [x for x in lidx if abs(x["off"] - off) < 0.2 and x["t1"] >= t0 / 1000 and x["t0"] <= t1 / 1000]
            if lm:
                lim = "+".join(sorted(set(f"{x['tipo']}_v3" for x in lm))) + " (" + ",".join(os.path.basename(x["path"]) for x in lm) + ")"
                L = pd.concat([lim_load(x["path"]) for x in lm], ignore_index=True).sort_values("t")
                w0, w1 = t0 / 1000, t1 / 1000
                L = L[(L.t >= w0 - 1) & (L.t <= w1 + 1)]
                if len(L) > 50:
                    dtl = 0.02
                    fresh = L.enc_fresco.astype(str).str.lower().eq("true").values
                    mov_enc_l = float(((L.v_enc.values > V_MOVE) & fresh).sum() * dtl)
                    mov_fus_l = float((L.v_fus.values > V_MOVE).sum() * dtl)
                    if not cov:
                        files = [x["path"] for x in lm]
                        note.append("CSV sensori 50 Hz mancanti sul Mac: encoder ruota/IMU dal limiter_v3 (niente sterzo, niente GPS)")
                        cov["encoder_ruota"] = coverage(L.t.values[fresh], w0, w1, HOLD["encoder_ruota"])
                        cov["imu"] = coverage(L.t.values[L.imu_ok.astype(str).str.lower().eq("true").values], w0, w1, HOLD["imu"])
                        cov["encoder_sterzo"] = None; cov["gps"] = None; cov["ruota_ble"] = None
                        mov_s, mfonte = mov_enc_l, "limiter_v3 v_enc>0.5 (encoder fresco)"
                        fa = L.angolo.values > 1 if "angolo" in L.columns else np.zeros(len(L), bool)
                        brake_s = float(fa.sum() * dtl); brake_max = float(L.angolo.max()) if "angolo" in L.columns else None
                    if mov_fus_l > 3 * max(mov_enc_l, 1) and mov_fus_l - mov_enc_l > 60:
                        note.append(f"info: v_fus del limiter {r1(mov_fus_l, 0)} s in moto vs encoder {r1(mov_enc_l, 0)} s (v_fus deriva, non usata)")
        if not lim:
            for f in sorted(glob.glob(os.path.join(D001, "_sensors", "speed_limiter", "limiter_*.csv"))):
                ts_ = os.path.basename(f)[8:23]
                if abs(name_ep(ts_) - name_ep(s)) <= 3:
                    lim = f"speed_limiter v2 ({os.path.basename(f)})"
        if not lim:
            lim = "nessun file limiter abbinato"
        # --- giudizio
        sp = ";".join(f"{k}:{pct(cov[k]) if cov.get(k) is not None else 'assente'}" for k in
                      ("encoder_ruota", "encoder_sterzo", "imu", "gps", "ruota_ble"))
        us, mot = giudizio_001(nvid, dur, cov, mov_s, brake_s, data, lum)
        if dis and us == "no" and mot.startswith("bici ferma"):
            us, mot = "forse", "encoder dice ferma ma il GPS vede moto: verificare encoder ruota a quella data"
        rows.append(dict(unita="asmile-001", sessione="session_" + s, data=data, ora_inizio=ora, fuso=FUSO if ora else "",
                         ora_fonte=ora_fonte, durata_s=r1(dur), durata_fonte=dfonte, n_file_video=nvid,
                         byte_video=sum(vsz), risoluzione=res, fps=r1(fps if fps else meta.get("fps"), 2),
                         bitrate_kbps=r1(bkbps, 0), bitrate_cfg_kbps=r1(bcfg / 1000, 0) if bcfg else "",
                         luminosita_media=r1(lum), esposizione_us_mediana=r1(expo, 0), sensori_presenti=sp,
                         file_sensori=";".join(rel(f) for f in files) if files else "mancante",
                         in_movimento_s=r1(mov_s) if mov_s is not None else "non misurato", movimento_fonte=mfonte,
                         dist_m=r1(dist, 0), freno_auto_s=r1(brake_s), brake_out_max_deg=r1(brake_max), limiter=lim,
                         calib=calib_for("asmile-001", data), usabile_manovre=us, motivo=mot, note="; ".join(note)))
    return rows


def giudizio_001(nvid, dur, cov, mov_s, brake_s, data, lum):
    if not nvid:
        return "no", "video mancante sul Mac (solo metadati/frames)"
    if not dur:
        return "no", "durata mancante (sessione vuota o interrotta)"
    if dur < 60:
        return "no", "video corto <60 s"
    if lum is not None and lum < DARK:
        return "no", f"video nero/troppo buio (luma {r1(lum)})"
    if not cov:
        return "no", "sensori mancanti (nessun CSV sensori abbinato)"
    er = cov.get("encoder_ruota") or 0
    if er < 0.5 and mov_s is None:
        return "no", "encoder ruota mancante: moto non misurabile"
    if mov_s is not None and mov_s < 30:
        return "no", f"bici ferma ({r1(mov_s)} s in moto): officina/cavalletto/prova da fermo"
    forse = []
    if mov_s is not None and mov_s < 60:
        forse.append(f"poco moto ({r1(mov_s)} s)")
    if er < 0.8:
        forse.append(f"encoder ruota solo {pct(er)}")
    st = cov.get("encoder_sterzo")
    if st is None or st < 0.8:
        forse.append(f"encoder sterzo {pct(st) if st is not None else 'assente'}: sterzate solo da IMU")
    if (cov.get("imu") or 0) < 0.8:
        forse.append(f"IMU {pct(cov.get('imu'))}")
    if brake_s and brake_s > 1:
        forse.append(f"freno automatico attivo {r1(brake_s, 0)} s: separare frenate auto da quelle di Daniele")
    if not data:
        forse.append("data reale sconosciuta")
    if lum is not None and lum < LOW_LIGHT:
        forse.append(f"luce scarsa (luma {r1(lum, 0)})")
    if forse:
        return "forse", "; ".join(forse)
    return "si", f"in moto {r1(mov_s, 0)} s, encoder ruota+sterzo e IMU completi"


# ================================================================================================ asmile-logger001
def sensor_index_logger():
    idx = []
    for f in sorted(glob.glob(os.path.join(DLOG, "_sensors", "sensors", "sensors_*.csv"))):
        d = read_csv_clean(f, usecols=["t_ms", "wall"], dtype=str)
        if d.empty:
            continue
        d = num(d, ["t_ms"]).dropna()
        tail = d.tail(200)
        off = float(np.median([ep_local(w) - t / 1000 for t, w in zip(tail.t_ms, tail.wall)]))
        off0 = ep_local(d.wall.iloc[0]) - d.t_ms.iloc[0] / 1000
        idx.append(dict(path=f, nome=os.path.basename(f)[8:23], off=off, off0=off0, t0=float(d.t_ms.min()),
                        t1=float(d.t_ms.max()), falso=off < BOGUS_LIM, nome_falso=abs(off - off0) > 2.0))
    return idx


def load_logger(path):
    if path not in _cache:
        cols = ["t_ms", "imu_ax_g", "imu_gz_dps", "ble_t_ms", "ble_speed_ms"]
        d = read_csv_clean(path, usecols=lambda c: c in cols, dtype=str)
        _cache[path] = num(d, cols)
    return _cache[path]


def frames_versions_logger():
    """tutte le versioni dei frames.csv (cartella frames/ e per_boot/*), senza doppioni (md5)."""
    out, seen = [], set()
    for f in sorted(glob.glob(os.path.join(DLOG, "_sensors", "frames", "clip_*_frames.csv"))) + \
            sorted(glob.glob(os.path.join(DLOG, "_sensors", "frames", "per_boot", "*", "clip_*_frames.csv"))):
        h = hashlib.md5(open(f, "rb").read()).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        d = read_csv_clean(f)
        if d.empty or "t_ms" not in d.columns:
            continue
        d = num(d, ["t_ms"]).dropna(subset=["t_ms"])
        if len(d) < 2:
            continue
        dt = np.diff(d.t_ms.values)
        out.append(dict(path=f, prefix=os.path.basename(f)[5:20], t0=float(d.t_ms.iloc[0]), t1=float(d.t_ms.iloc[-1]),
                        n=len(d), fps=1000.0 / np.median(dt), mtime=os.path.getmtime(f)))
    return out


def clips_logger():
    g = {}
    for f in sorted(os.listdir(DLOG)):
        m = re.match(r"clip_(\d{8}_\d{6})(?:_[0-9a-f]{8})?_(\d{5})\.h264$", f)
        if m:
            p = os.path.join(DLOG, f)
            g.setdefault(m.group(1), []).append((os.path.getmtime(p), int(m.group(2)), p, os.path.getsize(p)))
    subs = []
    for pref in sorted(g):
        cl = sorted(g[pref])
        cur = [cl[0]]
        parts = []
        for c in cl[1:]:
            # nuova registrazione: indice che riparte (stesso nome con orologio falso) o buco > 5 min
            # (buco ammesso se coerente coi numeri di clip mancanti: <= 40 s per clip + 2 min)
            if c[1] <= cur[-1][1] or c[0] - cur[-1][0] > (c[1] - cur[-1][1]) * 40 + 120:
                parts.append(cur); cur = [c]
            else:
                cur.append(c)
        parts.append(cur)
        for k, p in enumerate(parts):
            subs.append(dict(prefix=pref, sess=f"clip_{pref}" + (f"_p{k + 1}" if len(parts) > 1 else ""), clips=p,
                             nparts=len(parts)))
    return subs


def do_logger(luma_on):
    sidx = sensor_index_logger()
    fv = frames_versions_logger()
    subs = clips_logger()
    # durata tipica di una clip (s): da sessioni con frames.csv e indici completi
    per_clip = []
    for s in subs:
        cand = [v for v in fv if v["prefix"] == s["prefix"]]
        idx = [c[1] for c in s["clips"]]
        if s["nparts"] == 1 and len(cand) == 1 and idx == list(range(idx[0], idx[0] + len(idx))) and idx[0] == 0:
            per_clip.append((cand[0]["t1"] - cand[0]["t0"]) / 1000 / len(idx))
    clip_s = float(np.median(per_clip)) if per_clip else 30.0
    rows, used = [], set()
    for s in subs:
        cl = s["clips"]
        mt0, mt1 = cl[0][0], cl[-1][0]
        nbytes = sum(c[3] for c in cl)
        note = []
        # frames.csv: stesso nome e (se il nome e' condiviso da piu' registrazioni) mtime vicino all'ultima clip
        cand = [v for v in fv if v["prefix"] == s["prefix"] and v["path"] not in used]
        fr = None
        if cand:
            if s["nparts"] == 1 and len(cand) == 1:
                fr = cand[0]
            else:
                best = min(cand, key=lambda v: abs(v["mtime"] - mt1))
                if abs(best["mtime"] - mt1) < 300:
                    fr = best
        if fr:
            used.add(fr["path"])
        # boot dei sensori
        boot = None
        if fr:
            ov = [x for x in sidx if x["t1"] >= fr["t0"] and x["t0"] <= fr["t1"]]
            real = [x for x in ov if not x["falso"] and abs(x["off"] + fr["t1"] / 1000 - mt1) < 300]
            if real:
                boot = real[0]["off"]
            else:
                # sensori mai sincronizzati: solo se anche il frames.csv e' rimasto con l'orologio falso e gli intervalli t_ms combaciano
                fr_falso = datetime.datetime.fromtimestamp(fr["mtime"], TZ).strftime("%Y%m%d") == s["prefix"][:8]
                fake = [x for x in ov if fr_falso and x["falso"] and 0 <= name_ep(x["nome"]) - name_ep(s["prefix"]) <= 15
                        and abs(x["t0"] - fr["t0"]) < 5000 and abs(x["t1"] - fr["t1"]) < 5000]
                if fake:
                    boot = min(fake, key=lambda x: abs(x["t0"] - fr["t0"]) + abs(x["t1"] - fr["t1"]))["off"]
        else:
            # senza frames: boot reale il cui intervallo wall copre le clip
            real = [x for x in sidx if not x["falso"] and x["off"] + x["t0"] / 1000 <= mt1 and x["off"] + x["t1"] / 1000 >= mt0 - clip_s]
            if real:
                boot = real[0]["off"]
        bfiles = sorted([x for x in sidx if boot is not None and abs(x["off"] - boot) < 0.05], key=lambda x: x["t0"])
        bfalso = bool(bfiles) and bfiles[0]["falso"]
        for x in bfiles:
            if x["nome_falso"]:
                note.append(f"{os.path.basename(x['path'])}: nome/prime righe con data falsa, contenuto del {fmt(x['off'] + x['t1'] / 1000)[0]}")
        # inizio / durata
        if fr:
            dur, dfonte = (fr["t1"] - fr["t0"]) / 1000 + 1 / fr["fps"], "frames.csv t_ms" + (" (per_boot)" if "per_boot" in fr["path"] else "")
            fps = fr["fps"]
        else:
            dur, dfonte, fps = (mt1 - mt0) + clip_s, f"stima da mtime clip (+{r1(clip_s)} s/clip)", None
        idxs = [c[1] for c in cl]
        manc = (max(idxs) - min(idxs) + 1) - len(set(idxs))
        if manc > 0:
            note.append(f"{manc} clip mancanti fra indice {min(idxs)} e {max(idxs)}")
        if fr and boot is not None and not bfalso:
            ep0, ofonte = boot + fr["t0"] / 1000, "t_ms frames + offset boot dai CSV sensori"
        elif s["prefix"][:8] != "20261029" and s["nparts"] == 1:
            ep0, ofonte = name_ep(s["prefix"]), "nome file"
        elif datetime.datetime.fromtimestamp(mt0, TZ).strftime("%Y%m%d") != "20261029":
            ep0, ofonte = mt0 - clip_s, "mtime prima clip - durata clip (nome con orologio falso)"
        else:
            ep0, ofonte = None, "mancante: orologio falso 29/10 (nome e mtime), data reale sconosciuta"
        data, ora = fmt(ep0) if ep0 else ("", "")
        res = probe_res(cl[0][2])
        lum = None
        if luma_on:
            pick = sorted(set([0, len(cl) // 2, len(cl) - 1]))
            vals = [luma(cl[i][2]) for i in pick]
            vals = [v for v in vals if v is not None]
            lum = float(np.mean(vals)) if vals else None
        # sensori
        cov = {"encoder_ruota": None, "encoder_sterzo": None, "gps": None}
        mov_s, mfonte = None, ""
        if bfiles:
            d = pd.concat([load_logger(x["path"]) for x in bfiles], ignore_index=True).drop_duplicates("t_ms").sort_values("t_ms")
            ts = d.t_ms.values / 1000
            if fr:
                w0, w1 = fr["t0"] / 1000, fr["t1"] / 1000
            else:
                w0, w1 = mt0 - clip_s - boot, mt1 - boot
            cov["imu"] = coverage(ts[d.imu_ax_g.notna().values], w0, w1, HOLD["imu"])
            if "ble_speed_ms" in d.columns:
                bok = d.ble_speed_ms.notna().values & ((d.t_ms - d.ble_t_ms).abs().values < 3000)
                cov["ruota_ble"] = coverage(ts[bok], w0, w1, HOLD["ruota_ble"])
                if cov["ruota_ble"] and cov["ruota_ble"] >= 0.5:
                    g = np.arange(w0, w1, 0.5)
                    tb = ts[bok]; vb = d.ble_speed_ms.values[bok]
                    i = np.clip(np.searchsorted(tb, g, side="right") - 1, 0, None)
                    ok = (g - tb[i]) <= HOLD["ruota_ble"]
                    mov_s = float(((vb[i] > V_MOVE) & ok).sum() * 0.5)
                    mfonte = f"ruota BLE >0.5 m/s (copertura {pct(cov['ruota_ble'])})"
            else:
                cov["ruota_ble"] = 0.0
            if not fr:
                note.append("copertura sensori su finestra stimata da mtime")
        sp = ";".join(f"{k}:{pct(cov[k]) if cov.get(k) is not None else 'assente'}" for k in
                      ("encoder_ruota", "encoder_sterzo", "imu", "gps", "ruota_ble"))
        us, mot = giudizio_logger(dur, cov, mov_s, lum, data)
        rows.append(dict(unita="asmile-logger001", sessione=s["sess"], data=data, ora_inizio=ora, fuso=FUSO if ora else "",
                         ora_fonte=ofonte, durata_s=r1(dur), durata_fonte=dfonte, n_file_video=len(cl), byte_video=nbytes,
                         risoluzione=res, fps=r1(fps, 2), bitrate_kbps=r1(nbytes * 8 / dur / 1000, 0) if dur else "",
                         bitrate_cfg_kbps="", luminosita_media=r1(lum), esposizione_us_mediana="", sensori_presenti=sp,
                         file_sensori=";".join(rel(x["path"]) for x in bfiles) if bfiles else "mancante",
                         in_movimento_s=r1(mov_s) if mov_s is not None else "non misurato (metodo repo = flusso ottico sul video, non eseguito)",
                         movimento_fonte=mfonte, dist_m="", freno_auto_s="", brake_out_max_deg="", limiter="",
                         calib=calib_for("asmile-logger001", data), usabile_manovre=us, motivo=mot, note="; ".join(note)))
    return rows


def giudizio_logger(dur, cov, mov_s, lum, data):
    if not dur or dur < 60:
        return "no", "video corto <60 s"
    if lum is not None and lum < DARK:
        return "no", f"video nero/troppo buio (luma {r1(lum)})"
    imu = cov.get("imu")
    if imu is None or imu < 0.5:
        return "no", "IMU mancante: niente frenate/sterzate misurabili"
    if mov_s is not None and mov_s < 30:
        return "no", f"bici ferma secondo la ruota BLE ({r1(mov_s)} s in moto)"
    forse = []
    if mov_s is None:
        forse.append("moto non misurato (niente ruota BLE)")
    elif mov_s < 60:
        forse.append(f"poco moto ({r1(mov_s)} s)")
    if imu < 0.8:
        forse.append(f"IMU solo {pct(imu)}")
    if lum is not None and lum < LOW_LIGHT:
        forse.append(f"luce scarsa (luma {r1(lum, 0)})")
    if not data:
        forse.append("data reale sconosciuta")
    forse.append("niente encoder sterzo: sterzate solo da IMU gz, frenate da IMU (qualita' bassa)")
    if mov_s is not None and mov_s >= 60 and imu >= 0.8 and len(forse) == 1:
        return "si", f"in moto {r1(mov_s, 0)} s (ruota BLE), IMU {pct(imu)}; " + forse[0]
    return "forse", "; ".join(forse)


# ================================================================================================ logger02
def do_logger02(luma_on):
    clips = {}
    for f in sorted(os.listdir(D02)):
        m = re.match(r"clip_((?:\d{8}_\d{6})|(?:boot\d+))_([AB])_(\d{5})\.h264$", f)
        if m:
            clips.setdefault((m.group(1), m.group(2)), []).append((int(m.group(3)), os.path.join(D02, f)))
    # sensori (IMU sulla A): per prefisso
    sens = {}
    for f in sorted(glob.glob(os.path.join(D02, "sensors_*.csv"))):
        m = re.match(r"sensors_((?:\d{8}_\d{6})|(?:boot\d+))(?:_\d{5})?\.csv$", os.path.basename(f))
        if m:
            sens.setdefault(m.group(1), []).append(f)
    scache = {}

    def sload(pref):
        if pref not in scache:
            ds = [read_csv_clean(f, usecols=lambda c: c in ("t_us", "imu_ax_g", "batt_v"), dtype=str) for f in sens.get(pref, [])]
            ds = [num(d, ["t_us", "imu_ax_g", "batt_v"]) for d in ds if not d.empty and "t_us" in d.columns]
            scache[pref] = pd.concat(ds, ignore_index=True).dropna(subset=["t_us"]).sort_values("t_us") if ds else pd.DataFrame()
        return scache[pref]

    rows = []
    keys = sorted(clips)
    for (pref, sch) in keys:
        cl = sorted(clips[(pref, sch)])
        note = []
        tot = 0.0; nfr = 0; dts = []; win = []; nbytes = 0; nfcsv = 0
        for i, p in cl:
            nbytes += os.path.getsize(p)
            fc = p[:-5] + "_frames.csv"
            if not os.path.exists(fc):
                continue
            d = read_csv_clean(fc)
            if d.empty or "t_us" not in d.columns:
                continue
            d = num(d, ["t_us", "t_a_us"]).dropna(subset=["t_us"])
            if len(d) < 2:
                continue
            nfcsv += 1
            dt = np.diff(d.t_us.values) / 1e6
            dts.append(np.median(dt))
            tot += (d.t_us.iloc[-1] - d.t_us.iloc[0]) / 1e6 + np.median(dt)
            nfr += len(d)
            col = "t_us" if sch == "A" else ("t_a_us" if "t_a_us" in d.columns else None)
            if col:
                win.append((d[col].iloc[0] / 1e6, d[col].iloc[-1] / 1e6))
        if nfcsv < len(cl):
            note.append(f"frames.csv mancanti per {len(cl) - nfcsv} clip")
        idxs = [i for i, _ in cl]
        manc = (max(idxs) - min(idxs) + 1) - len(set(idxs))
        if manc:
            note.append(f"{manc} clip mancanti fra indice {min(idxs)} e {max(idxs)}")
        dur = tot if nfcsv else None
        fps = 1 / float(np.median(dts)) if dts else None
        if pref.startswith("boot"):
            data, ora, ofonte = "", "", "mancante: scheda senza orologio (nome boot)"
        else:
            data, ora = fmt(name_ep(pref)); ofonte = "nome file (ora locale)"
        # IMU: A -> suoi sensori; B -> sensori della A con nome piu' vicino (t_a_us = orologio A)
        cov_imu, sfiles, batt = None, [], None
        spref = None
        if sch == "A":
            spref = pref if pref in sens else None
        elif win and not pref.startswith("boot"):
            cands = [k for k in sens if not k.startswith("boot") and abs(name_ep(k) - name_ep(pref)) < 1800]
            best = None
            for k in sorted(cands, key=lambda k: abs(name_ep(k) - name_ep(pref))):
                d = sload(k)
                if len(d) and d.t_us.iloc[0] / 1e6 <= win[-1][1] and d.t_us.iloc[-1] / 1e6 >= win[0][0]:
                    best = k; break
            spref = best
            if best:
                note.append(f"IMU dalla scheda A (sensors_{best}), abbinata con t_a_us")
        elif win and pref.startswith("boot"):
            note.append("B senza orologio: IMU della A non abbinabile")
        if spref:
            d = sload(spref)
            sfiles = sens.get(spref, [])
            if len(d) and win:
                ts = d.t_us.values[d.imu_ax_g.notna().values] / 1e6
                tot_w = sum(b - a for a, b in win)
                cov_imu = sum((coverage(ts, a, b, HOLD["imu"]) or 0) * (b - a) for a, b in win) / tot_w if tot_w > 0 else None
                if "batt_v" in d.columns and d.batt_v.notna().any():
                    batt = float(d.batt_v.median())
        cov = {"encoder_ruota": None, "encoder_sterzo": None, "gps": None, "ruota_ble": None, "imu": cov_imu}
        sp = ";".join(f"{k}:{pct(cov[k]) if cov.get(k) is not None else 'assente'}" for k in
                      ("encoder_ruota", "encoder_sterzo", "imu", "gps", "ruota_ble"))
        res = probe_res(cl[0][1])
        lum = None
        if luma_on:
            pick = sorted(set([0, len(cl) // 2, len(cl) - 1]))
            vals = [v for v in (luma(cl[i][1]) for i in pick) if v is not None]
            lum = float(np.mean(vals)) if vals else None
        if batt:
            note.append(f"batt_v mediana {r1(batt, 2)} V")
        if not dur or dur < 60:
            us, mot = "no", "video corto <60 s" if dur else "durata mancante (frames.csv assenti)"
        elif lum is not None and lum < DARK:
            us, mot = "no", f"video nero/troppo buio (luma {r1(lum)})"
        elif cov_imu is None or cov_imu < 0.5:
            us, mot = "no", "IMU mancante/non abbinata: niente frenate/sterzate misurabili"
        else:
            m = ["moto non misurato (niente velocita' su logger02)", "calib non definitiva",
                 "sterzate solo da IMU gz, frenate da IMU"]
            if cov_imu < 0.8:
                m.insert(0, f"IMU solo {pct(cov_imu)}")
            if lum is not None and lum < LOW_LIGHT:
                m.insert(0, f"luce scarsa (luma {r1(lum, 0)})")
            us, mot = "forse", "; ".join(m)
        rows.append(dict(unita="logger02", sessione=f"clip_{pref}_{sch}", data=data, ora_inizio=ora, fuso=FUSO if ora else "",
                         ora_fonte=ofonte, durata_s=r1(dur), durata_fonte="frames.csv t_us" if dur else "mancante",
                         n_file_video=len(cl), byte_video=nbytes, risoluzione=res, fps=r1(fps, 2),
                         bitrate_kbps=r1(nbytes * 8 / dur / 1000, 0) if dur else "", bitrate_cfg_kbps="",
                         luminosita_media=r1(lum), esposizione_us_mediana="", sensori_presenti=sp,
                         file_sensori=(rel(os.path.join(D02, f"sensors_{spref}_*.csv")) + f" ({len(sfiles)} file)") if sfiles else "mancante",
                         in_movimento_s="non misurato (nessun metodo nel repo per logger02)", movimento_fonte="",
                         dist_m="", freno_auto_s="", brake_out_max_deg="", limiter="", calib=calib_for("logger02", data),
                         usabile_manovre=us, motivo=mot, note="; ".join(note)))
    return rows


COLS = ["unita", "sessione", "data", "ora_inizio", "fuso", "ora_fonte", "durata_s", "durata_fonte", "n_file_video",
        "byte_video", "risoluzione", "fps", "bitrate_kbps", "bitrate_cfg_kbps", "luminosita_media", "esposizione_us_mediana",
        "sensori_presenti", "file_sensori", "in_movimento_s", "movimento_fonte", "dist_m", "freno_auto_s",
        "brake_out_max_deg", "limiter", "calib", "usabile_manovre", "motivo", "note"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-luma", action="store_true", help="salta i 3 fotogrammi per la luminosita'")
    ap.add_argument("--out", default=os.path.join(HERE, "inventario_sessioni.csv"))
    ap.add_argument("--unita", nargs="*", default=["asmile-001", "asmile-logger001", "logger02"])
    a = ap.parse_args()
    rows = []
    if "asmile-001" in a.unita:
        rows += do_001(not a.no_luma); print("asmile-001 fatto", file=sys.stderr)
    if "asmile-logger001" in a.unita:
        rows += do_logger(not a.no_luma); print("asmile-logger001 fatto", file=sys.stderr)
    if "logger02" in a.unita:
        rows += do_logger02(not a.no_luma); print("logger02 fatto", file=sys.stderr)
    rows.sort(key=lambda r: (r["unita"], r["sessione"]))
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader(); w.writerows(rows)
    # riepilogo
    df = pd.DataFrame(rows)
    df["d"] = pd.to_numeric(df.durata_s, errors="coerce").fillna(0)
    for u, g in df.groupby("unita"):
        print(f"{u}: {len(g)} sessioni, video {g.d.sum() / 3600:.2f} h; si {int((g.usabile_manovre == 'si').sum())} "
              f"({g[g.usabile_manovre == 'si'].d.sum() / 3600:.2f} h), forse {int((g.usabile_manovre == 'forse').sum())} "
              f"({g[g.usabile_manovre == 'forse'].d.sum() / 3600:.2f} h), no {int((g.usabile_manovre == 'no').sum())}")
    print("scritto", a.out)


if __name__ == "__main__":
    main()
