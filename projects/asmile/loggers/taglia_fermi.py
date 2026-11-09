#!/usr/bin/env python3
"""taglia_fermi.py - toglie dai video le parti con FRAME FERMI (bici ferma E scena immobile per >= MIN_STILL_S).

Regola di Daniele 2026-11-09. Si lancia da on_new_videos.sh PRIMA della percezione.
 - FERMO  = velocita' (encoder #001 / BLE logger) < 0.3 m/s E IMU quieta E differenza fra frame bassa.
   Bici ferma ma scena che si muove (pedoni, auto, cancello) -> NON fermo, si tiene.
   Fallback: mancano i sensori -> solo differenza frame (dichiarato nell'indice).
 - Si tagliano solo i tratti fermi lunghi >= 5 s, tenendo ~1 s di margine attorno al movimento.
 - ECCEZIONE: calibrazione/metro non si tagliano (nome calib_*, file NON_TAGLIARE nella cartella sessione,
   loggers/non_tagliare.txt, o pattern di soste regolari). Nel dubbio NON si taglia, e si scrive nel log.
 - I GREZZI NON si toccano. Uscita in asmile-loggers/_solo_movimento/<unita>/<sessione>/:
     index.json (tratti tenuti/tagliati con t_ms e frame), frames_*.csv ritagliati (+orig_frame),
     video "solo movimento" (#001: <sess>_left/right.h264 sincronizzati; logger: <sess>.h264 concatenato),
     metrics.npz (cache). Idempotente (firma ingressi nell'indice).
Uso: taglia_fermi.py [BASE] [--sessione ID] [--dry-run] [--force]
"""
import argparse, glob, hashlib, json, os, re, subprocess, sys, time
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DEF_BASE = os.path.normpath(os.path.join(HERE, "..", "asmile-loggers"))
FPS = 15.0
V_STILL = 0.3          # m/s
MIN_STILL_S = 5.0
MARGIN_S = 1.0
M_PER_COUNT = 2.1219e-5  # encoder ruota #001 (m per count encoder)
DIFF_PIX = 12          # soglia |diff| (0-255) su un blocco 10x10 per dirlo "cambiato" (dopo media del blocco)
DIFF_BLOCKS = 3        # blocchi cambiati (su 160) sopra cui la scena si muove
IMU_ACC_STD = 0.03     # g, std su 1 s (somma 3 assi)
IMU_GYR_STD = 1.5      # dps, std su 1 s (somma 3 assi)
LAG = 3                # confronto frame i vs i-LAG (0.2 s)
PREFIX_UNITS = {"asmile-001": "sessions", "asmile-logger": "clips"}


def log(base, msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] taglia_fermi: {msg}"
    print(line, flush=True)
    try:
        with open(os.path.join(base, "ingest.log"), "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------- metrica frame
def decode_metric(files, crop_left_half):
    """Decodifica i file (in ordine) a 160x100 grigio. Ritorna array (N,100,160) uint8."""
    vf = ("crop=1280:800:0:0," if crop_left_half else "") + "scale=160:100:flags=area,format=gray"
    frames = []
    for f in files:
        p = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-f", "h264", "-framerate", str(int(FPS)), "-i", f,
                            "-vf", vf, "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True)
        a = np.frombuffer(p.stdout, np.uint8)
        frames.append(a[: (len(a) // 16000) * 16000].reshape(-1, 100, 160))
    return np.concatenate(frames) if frames else np.zeros((0, 100, 160), np.uint8)


def decode_per_clip(files, crop_left_half):
    """Logger: metrica per chunk SEPARATAMENTE (i buchi fra chunk non generano falsi movimenti)."""
    bl, cnt = [], []
    for f in files:
        g = decode_metric([f], crop_left_half)
        bl.append(scene_changed_blocks(g) if len(g) else np.zeros(0, np.int32))
        cnt.append(len(g))
    return (np.concatenate(bl) if bl else np.zeros(0, np.int32)), np.array(cnt, int)


def map_logger(files, counts, fr, sd):
    """Mapping CORRETTO clip->righe frames.csv (non indice cumulato: mancano clip -> deriva).
    Per ogni clip: fine = mtime convertito in t_ms con la colonna wall dei sensori; inizio = fine - n/FPS;
    le righe frames.csv si agganciano per t_ms (n righe consecutive dall'inizio piu' vicino).
    Ritorna (vrow per frame video (-1 = senza riga), tms per frame video, buchi[list], note)."""
    t_csv = fr.t_ms.values.astype(float)
    w = pd.to_datetime(sd["wall"], errors="coerce")
    okw = w.notna().values
    wsec = (w[okw] - pd.Timestamp("1970-01-01")).dt.total_seconds().values   # epoch s naive locale
    tsen = sd.t_ms.values[okw].astype(float)
    vrow, tms, gaps, notes = [], [], [], []
    prev_end = None
    prev_r1 = None
    extrap = False
    for f, n in zip(files, counts):
        mt = pd.Timestamp(os.path.getmtime(f), unit="s", tz="UTC").tz_convert("Europe/Rome").tz_localize(None)
        mts = (mt - pd.Timestamp("1970-01-01")).total_seconds()
        if wsec[0] <= mts <= wsec[-1]:
            end_ms = float(np.interp(mts, wsec, tsen))
        else:   # oltre la fine dei sensori (sensor_hub fermo/scaricato prima): offset costante t_ms = wall + off
            end_ms = float(mts * 1000 + np.median(tsen - wsec * 1000))
            if not extrap:
                notes.append("mtime oltre l'ultimo wall dei sensori: t_ms estrapolato con offset costante monotonic-wall")
                extrap = True
        st_ms = end_ms - n / FPS * 1000
        r0 = int(np.abs(t_csv - st_ms).argmin())
        # clip contigue (inizio stimato entro 1.5 s dalla fine della precedente): righe consecutive esatte
        if prev_r1 is not None and abs(st_ms - prev_end) < 1500 and prev_r1 + 1 < len(t_csv):
            r0 = prev_r1 + 1
            st_ms = t_csv[r0]
        # se la stima cade fuori dal csv di oltre 2 s non aggancio
        ok0 = abs(t_csv[r0] - st_ms) < 2000
        for k in range(n):
            r = r0 + k
            if ok0 and r < len(t_csv):
                vrow.append(r); tms.append(t_csv[r])
            else:
                vrow.append(-1); tms.append(st_ms + k * 1000 / FPS)
        if not ok0:
            notes.append(f"{os.path.basename(f)}: inizio stimato {st_ms:.0f} ms lontano dal csv ({t_csv[r0]:.0f}): senza righe")
        if prev_end is not None and st_ms - prev_end > 1500:
            gaps.append({"prima_di": os.path.basename(f), "buco_s": round((st_ms - prev_end) / 1000, 1)})
        prev_end = end_ms if not ok0 else t_csv[min(r0 + n - 1, len(t_csv) - 1)] + 1000 / FPS
        prev_r1 = r0 + n - 1 if ok0 else None
    return np.array(vrow), np.array(tms), gaps, notes


def scene_changed_blocks(fr):
    """Per frame: n blocchi 10x10 con |diff| medio > DIFF_PIX rispetto al frame i-LAG."""
    n = len(fr)
    out = np.zeros(n, np.int32)
    f = fr.astype(np.int16)
    for i in range(LAG, n):
        d = np.abs(f[i] - f[i - LAG])
        b = d.reshape(10, 10, 16, 10).mean(axis=(1, 3))
        out[i] = int((b > DIFF_PIX).sum())
    out[:LAG] = out[LAG] if n > LAG else 0
    return out


# ---------------------------------------------------------------- sensori
def load_sensors(sens_dir, t0, t1, start=None):
    cols = ["t_ms", "imu_ax_g", "imu_ay_g", "imu_az_g", "imu_gx_dps", "imu_gy_dps", "imu_gz_dps",
            "enc_wheel_cum", "ble_speed_ms", "ble_wheel_rev"]
    parts = []
    for f in sorted(glob.glob(os.path.join(sens_dir, "sensors_*.csv"))):
        try:
            hdr = pd.read_csv(f, nrows=0).columns
            uc = [c for c in cols if c in hdr]
            d = pd.read_csv(f, usecols=uc + (["wall"] if "wall" in hdr else []), low_memory=False)
        except Exception:
            continue
        d["t_ms"] = pd.to_numeric(d["t_ms"], errors="coerce")
        d = d.dropna(subset=["t_ms"])
        d = d[(d.t_ms >= t0 - 3000) & (d.t_ms <= t1 + 3000)]
        # t_ms e' CLOCK_MONOTONIC dal boot: boot diversi si sovrappongono -> tengo solo il file il cui
        # orario (wall) a t0 coincide con l'inizio sessione (+-2 min)
        if len(d) and start is not None and "wall" in d:
            w = pd.to_datetime(d["wall"], errors="coerce")
            w0 = w.iloc[(d.t_ms - t0).abs().values.argmin()]
            if pd.isna(w0) or abs((w0 - start).total_seconds()) > 120:
                continue
        if len(d):
            parts.append(d)
    if not parts:
        return None
    d = pd.concat(parts).sort_values("t_ms").drop_duplicates("t_ms").reset_index(drop=True)
    return d


def bike_active(d, tf):
    """Per ogni t_ms frame (array tf): True se bici in moto/IMU non quieta. Ritorna (flag, info) o (None, info)."""
    if d is None or len(d) < 50 or "imu_ax_g" not in d:
        return None, {"sensori": "assenti"}, None
    t = d.t_ms.values.astype(float)
    W = 50  # ~1 s a 50 Hz
    def rstd(c):
        return pd.Series(pd.to_numeric(d[c], errors="coerce").values).rolling(W, center=True, min_periods=10).std().values
    acc = rstd("imu_ax_g") + rstd("imu_ay_g") + rstd("imu_az_g")
    gyr = rstd("imu_gx_dps") + rstd("imu_gy_dps") + rstd("imu_gz_dps")
    imu_act = (np.nan_to_num(acc, nan=9) > IMU_ACC_STD) | (np.nan_to_num(gyr, nan=99) > IMU_GYR_STD)
    speed = np.full(len(d), np.nan)
    src = "solo_imu"
    if "enc_wheel_cum" in d and pd.to_numeric(d.enc_wheel_cum, errors="coerce").notna().sum() > 50:
        e = pd.to_numeric(d.enc_wheel_cum, errors="coerce").ffill().values
        k = 25
        dc = np.abs(e[k:] - e[:-k])
        dt = (t[k:] - t[:-k]) / 1000.0
        v = np.where((dt > 0.2) & (dc < 5e5), dc * M_PER_COUNT / np.maximum(dt, 1e-3), np.nan)
        speed[k // 2: k // 2 + len(v)] = v
        src = "encoder_ruota"
    elif "ble_speed_ms" in d and pd.to_numeric(d.ble_speed_ms, errors="coerce").notna().sum() > 20:
        s = pd.to_numeric(d.ble_speed_ms, errors="coerce").ffill().values
        speed = pd.Series(s).rolling(25, center=True, min_periods=1).max().values
        src = "ble_speed"
    mov = np.nan_to_num(speed, nan=0.0) > V_STILL
    act = imu_act | mov
    # copertura: frame lontani da un campione sensore (>0.5 s) -> sconosciuti
    idx = np.clip(np.searchsorted(t, tf), 1, len(t) - 1)
    near = np.where(np.abs(t[idx] - tf) < np.abs(t[idx - 1] - tf), idx, idx - 1)
    ok = np.abs(t[near] - tf) < 500
    flag = act[near]
    info = {"sensori": src + "+imu", "frac_frame_con_sensori": float(ok.mean()),
            "frac_imu_attiva": float(imu_act[near][ok].mean()) if ok.any() else None,
            "frac_vel_sopra_soglia": float(mov[near][ok].mean()) if ok.any() else None,
            "vel_max_ms": float(np.nanmax(speed)) if np.isfinite(speed).any() else None}
    return np.where(ok, flag, False), info, ok   # senza sensori: solo diff frame (fallback)


# ---------------------------------------------------------------- tratti
def runs(mask):
    """Run consecutivi True -> lista (i0,i1) inclusivi."""
    out, s = [], None
    for i, m in enumerate(mask):
        if m and s is None:
            s = i
        if not m and s is not None:
            out.append((s, i - 1)); s = None
    if s is not None:
        out.append((s, len(mask) - 1))
    return out


def decide_cuts(still, tms):
    """still: bool per frame. Ritorna lista di (i0,i1) frame da tagliare (run >= MIN_STILL_S, meno margine)."""
    n = len(still)
    m = int(round(MARGIN_S * FPS))
    cuts = []
    for a, b in runs(still):
        dur = (tms[b] - tms[a]) / 1000.0
        if dur < MIN_STILL_S:
            continue
        a2 = a + (m if a > 0 else 0)
        b2 = b - (m if b < n - 1 else 0)
        if b2 - a2 >= 1:
            cuts.append((a2, b2))
    return cuts


def calib_suspect(name, sessdir, still_runs_s, move_frac):
    if name.startswith("calib_") or "calib" in name.lower() or "metro" in name.lower():
        return "nome calib/metro"
    if sessdir and os.path.exists(os.path.join(sessdir, "NON_TAGLIARE")):
        return "marcatore NON_TAGLIARE"
    lst = os.path.join(HERE, "non_tagliare.txt")
    if os.path.isfile(lst):
        for ln in open(lst):
            ln = ln.split("#")[0].strip()
            if ln and ln in name:
                return f"in loggers/non_tagliare.txt ({ln})"
    r = np.array(still_runs_s)
    if len(r) >= 3 and r.mean() > 0 and r.std() / r.mean() < 0.35 and move_frac < 0.25:
        return f"pattern soste regolari ({len(r)} soste, durate {r.round(1).tolist()} s) -> sospetta calibrazione"
    return None


# ---------------------------------------------------------------- scrittura
def write_video(srcs_cat, keep_idx, out_path, fps=int(FPS)):
    """Ricodifica tenendo i frame con indice globale in keep_idx (lista di (a,b) inclusivi)."""
    expr = "+".join(f"between(n\\,{a}\\,{b})" for a, b in keep_idx)
    script = out_path + ".filter.txt"
    with open(script, "w") as f:
        f.write(f"select='{expr}',setpts=N/({fps}*TB)")
    cmd = ["ffmpeg", "-v", "error", "-y", "-nostdin", "-f", "h264", "-framerate", str(fps), "-i", "pipe:0",
           "-fps_mode", "passthrough", "-filter_script:v", script, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-f", "h264", out_path + ".tmp"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in srcs_cat:
        with open(f, "rb") as fh:
            while True:
                b = fh.read(1 << 20)
                if not b:
                    break
                try:
                    p.stdin.write(b)
                except BrokenPipeError:
                    break
    try:
        p.stdin.close()
    except Exception:
        pass
    rc = p.wait()
    os.remove(script)
    if rc != 0:
        raise RuntimeError("ffmpeg fallito")
    os.replace(out_path + ".tmp", out_path)


def write_frames_csv(src_csv, out_csv, keep_ranges_ms):
    d = pd.read_csv(src_csv).dropna().reset_index(drop=True)
    m = np.zeros(len(d), bool)
    for a, b in keep_ranges_ms:
        m |= ((d.t_ms >= a) & (d.t_ms <= b)).values
    o = d[m].copy()
    o.insert(1, "orig_frame", o["frame"].values)
    o["frame"] = np.arange(len(o))
    o.to_csv(out_csv, index=False)
    return int(m.sum()), len(d)


def signature(files):
    h = hashlib.sha1()
    for f in sorted(files):
        st = os.stat(f)
        h.update(f"{os.path.basename(f)}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()


# ---------------------------------------------------------------- sessioni
def sessions_001(udir):
    out = []
    for l in sorted(glob.glob(os.path.join(udir, "session_*_left.h264"))):
        sess = os.path.basename(l)[:-len("_left.h264")]
        r = os.path.join(udir, sess + "_right.h264")
        if os.path.isfile(r) and os.path.isdir(os.path.join(udir, sess)) \
                and os.path.isfile(os.path.join(udir, sess, "frames_left.csv")):
            out.append((sess, [l], [r], os.path.join(udir, sess)))
    return out


def sessions_logger(udir):
    g = {}
    for f in sorted(glob.glob(os.path.join(udir, "clip_*_[0-9][0-9][0-9][0-9][0-9].h264"))):
        m = re.match(r"(clip_\d{8}_\d{6})_(\d{5})\.h264$", os.path.basename(f))
        if m:
            g.setdefault(m.group(1), []).append(f)
    return [(s, fs, None, None) for s, fs in g.items()
            if os.path.isfile(os.path.join(udir, "_sensors", "frames", s + "_frames.csv"))]


def process(base, unit, sess, left, right, sessdir, dry, force):
    udir = os.path.join(base, unit)
    out_dir = os.path.join(base, "_solo_movimento", unit, sess)
    idx_path = os.path.join(out_dir, "index.json")
    allin = left + (right or [])
    sig = signature(allin)
    if not force and os.path.isfile(idx_path):
        try:
            if json.load(open(idx_path)).get("firma_ingressi") == sig:
                return json.load(open(idx_path))
        except Exception:
            pass
    is001 = right is not None
    fcsv = os.path.join(sessdir, "frames_left.csv") if is001 else os.path.join(udir, "_sensors", "frames", sess + "_frames.csv")
    fr = pd.read_csv(fcsv).dropna().reset_index(drop=True)
    os.makedirs(out_dir, exist_ok=True)
    npz = os.path.join(out_dir, "metrics.npz")
    notes = []
    vrow = None
    gaps = []
    if os.path.isfile(npz) and not force and int(np.load(npz)["sig"]) == int(sig[:12], 16):
        z = np.load(npz); blocks = z["blocks"]; counts = z["counts"]
    else:
        if is001:
            blocks = scene_changed_blocks(decode_metric(left, crop_left_half=False)); counts = np.array([len(blocks)])
        else:
            blocks, counts = decode_per_clip(left, True)
        np.savez(npz, blocks=blocks, counts=counts, sig=int(sig[:12], 16))
    if is001:
        nfr = min(len(blocks), len(fr))
        if len(blocks) != len(fr):
            notes.append(f"frame decodificati {len(blocks)} != righe csv {len(fr)}: uso i primi {nfr}")
        fr = fr.iloc[:nfr]
        blocks = blocks[:nfr]
        tms = fr.t_ms.values.astype(float)
    else:
        mm0 = re.search(r"(\d{8})_(\d{6})", sess)
        st0 = pd.to_datetime(mm0.group(1) + mm0.group(2), format="%Y%m%d%H%M%S") if mm0 else None
        sdir0 = os.path.join(udir, "_sensors", "sensors")
        sd0 = load_sensors(sdir0, fr.t_ms.min() - 600000, fr.t_ms.max() + 600000, st0)
        if sd0 is None or "wall" not in sd0:
            raise RuntimeError("niente sensori con wall per mappare le clip sul t_ms: NON taglio")
        vrow, tms, gaps, n2 = map_logger(left, counts, fr, sd0)
        notes += n2
        nfr = len(blocks)
        nunm = int((vrow < 0).sum())
        if nunm:
            notes.append(f"{nunm} frame video senza riga csv (clip oltre la fine del csv)")
        if gaps:
            notes.append(f"clip mancanti/buchi: {gaps}")
            # dopo un buco la sequenza e' discontinua: il frame subito dopo non puo' far parte di un fermo continuo
        gapmask = np.zeros(nfr, bool)
        gapmask[1:] = np.diff(tms) > 1500
    scene_moving = pd.Series(blocks > DIFF_BLOCKS).rolling(int(FPS), center=True, min_periods=1).max().values.astype(bool)
    sens_dir = os.path.join(udir, "_sensors", "sensors") if os.path.isdir(os.path.join(udir, "_sensors", "sensors")) \
        else os.path.join(udir, "_sensors")
    mm = re.search(r"(\d{8})_(\d{6})", sess)
    start = pd.to_datetime(mm.group(1) + mm.group(2), format="%Y%m%d%H%M%S") if mm else None
    sd = load_sensors(sens_dir, tms[0], tms[-1], start)
    res = bike_active(sd, tms)
    if res[0] is None:
        bike = np.zeros(nfr, bool); sens_info = res[1]; ok = None; notes.append("sensori assenti: fallback solo differenza frame")
    else:
        bike, sens_info, ok = res
        if ok.mean() < 0.9:
            notes.append(f"sensori coprono solo {ok.mean()*100:.0f}% dei frame: dove mancano si usa solo la differenza frame (fallback)")
    still = (~bike) & (~scene_moving)
    if not is001:
        still &= ~gapmask
    still_runs = [(tms[b] - tms[a]) / 1000 for a, b in runs(still) if (tms[b] - tms[a]) / 1000 >= MIN_STILL_S]
    cuts = decide_cuts(still, tms)
    susp = calib_suspect(sess, sessdir, still_runs, float(1 - still.mean()))
    if susp:
        notes.append(f"NON TAGLIATA: {susp}")
        cuts = []
    # tratti tenuti/tagliati
    segs, pos = [], 0
    for a, b in cuts + [(nfr, nfr)]:
        if a > pos:
            segs.append(("tenuto", pos, a - 1))
        if b >= a and a < nfr:
            segs.append(("tagliato", a, b))
        pos = b + 1
    jseg = [{"stato": s, "frame_da": int(a), "frame_a": int(b), "t_ms_da": int(tms[a]), "t_ms_a": int(tms[b]),
             "durata_s": round((tms[b] - tms[a]) / 1000 + 1 / FPS, 2)} for s, a, b in segs]
    cut_s = sum(x["durata_s"] for x in jseg if x["stato"] == "tagliato")
    tot_s = nfr / FPS
    keep_ms = [(x["t_ms_da"], x["t_ms_a"]) for x in jseg if x["stato"] == "tenuto"]
    keep_fr = [(x["frame_da"], x["frame_a"]) for x in jseg if x["stato"] == "tenuto"]
    index = {"unita": unit, "sessione": sess, "firma_ingressi": sig, "fps_nominale": FPS,
             "parametri": {"v_still_ms": V_STILL, "min_fermo_s": MIN_STILL_S, "margine_s": MARGIN_S,
                           "diff_pix": DIFF_PIX, "diff_blocchi": DIFF_BLOCKS, "imu_acc_std_g": IMU_ACC_STD,
                           "imu_gyr_std_dps": IMU_GYR_STD},
             "frame_totali": int(nfr), "durata_s": round(tot_s, 1), "tagliato_s": round(cut_s, 1),
             "tagliato_pct": round(100 * cut_s / tot_s, 1) if tot_s else 0.0,
             "sensori": sens_info, "frac_scena_in_movimento": round(float(scene_moving.mean()), 3),
             "note": notes, "buchi_clip": gaps, "mapping": "mtime->t_ms (wall sensori), non indice cumulato" if not is001 else "frames csv diretto", "tratti": jseg, "video_solo_movimento": [], "grezzi_toccati": False}
    if dry:
        return index
    if cuts:
        if is001:
            for side, files in (("left", left), ("right", right)):
                o = os.path.join(out_dir, f"{sess}_{side}.h264")
                # right: seleziono per t_ms con i propri frames csv (se i conteggi differiscono)
                fc = pd.read_csv(os.path.join(sessdir, f"frames_{side}.csv")).dropna().reset_index(drop=True)
                m = np.zeros(len(fc), bool)
                for a, b in keep_ms:
                    m |= ((fc.t_ms >= a) & (fc.t_ms <= b)).values
                ids = np.flatnonzero(m)
                rg = [(int(s), int(e)) for s, e in runs(m)]
                write_video(files, rg, o)
                write_frames_csv(os.path.join(sessdir, f"frames_{side}.csv"), os.path.join(out_dir, f"frames_{side}.csv"), keep_ms)
                index["video_solo_movimento"].append(os.path.basename(o))
        else:
            o = os.path.join(out_dir, sess + ".h264")
            write_video(left, keep_fr, o)
            kr = np.concatenate([np.arange(a, b + 1) for a, b in keep_fr]) if keep_fr else np.array([], int)
            rows = vrow[kr]; rows = rows[rows >= 0]
            oc = pd.read_csv(fcsv).dropna().reset_index(drop=True).iloc[rows].copy()
            oc.insert(1, "orig_frame", oc["frame"].values); oc["frame"] = np.arange(len(oc))
            oc.to_csv(os.path.join(out_dir, f"{sess}_frames.csv"), index=False)
            index["video_solo_movimento"].append(os.path.basename(o))
        if not keep_fr:
            notes.append("tutto fermo: nessun tratto tenuto")
    json.dump(index, open(idx_path, "w"), indent=1)
    return index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default=DEF_BASE)
    ap.add_argument("--sessione")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    base = os.path.abspath(a.base)
    for unit, kind in PREFIX_UNITS.items():
        udir = os.path.join(base, unit)
        if not os.path.isdir(udir):
            continue
        ss = sessions_001(udir) if kind == "sessions" else sessions_logger(udir)
        for sess, left, right, sessdir in ss:
            if a.sessione and a.sessione not in sess:
                continue
            if not a.sessione and not a.force:
                # le sessioni vecchie senza indice vengono comunque elaborate (idempotente); salta clip vuote
                if sum(os.path.getsize(f) for f in left) < 2_000_000:
                    continue
            try:
                ix = process(base, unit, sess, left, right, sessdir, a.dry_run, a.force)
                log(base, f"{unit}/{sess}: {ix['durata_s']} s, tagliato {ix['tagliato_s']} s ({ix['tagliato_pct']}%) "
                          f"sensori={ix['sensori'].get('sensori')} {'; '.join(ix['note'])}")
            except Exception as e:
                log(base, f"{unit}/{sess}: ERRORE {e!r} -> NON taglio (si usa il grezzo)")


if __name__ == "__main__":
    main()
