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
    return np.where(ok, flag, True), info, ok


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
    if os.path.isfile(npz) and not force and int(np.load(npz)["sig"]) == int(sig[:12], 16):
        blocks = np.load(npz)["blocks"]
    else:
        gray = decode_metric(left, crop_left_half=not is001)
        blocks = scene_changed_blocks(gray)
        np.savez(npz, blocks=blocks, sig=int(sig[:12], 16))
    nfr = min(len(blocks), len(fr))
    notes = []
    if len(blocks) != len(fr):
        notes.append(f"frame decodificati {len(blocks)} != righe csv {len(fr)}: uso i primi {nfr}")
    fr = fr.iloc[:nfr]
    blocks = blocks[:nfr]
    tms = fr.t_ms.values.astype(float)
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
            notes.append(f"sensori coprono solo {ok.mean()*100:.0f}% dei frame: gli scoperti sono trattati come in movimento (non taglio)")
    still = (~bike) & (~scene_moving)
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
             "note": notes, "tratti": jseg, "video_solo_movimento": [], "grezzi_toccati": False}
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
            write_frames_csv(fcsv, os.path.join(out_dir, f"{sess}_frames.csv"), keep_ms)
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
