#!/usr/bin/env python3
"""
Stadio 1 — asmile-log-harvester (implementazione eseguibile)
============================================================
Rende trainabili le ore di guida di Asmile: scopre le sessioni grezze in locale
(video stereo + sensors.csv), sincronizza video<->sensori, applica i gate di
qualita' e produce un CORPUS PULITO E INDICIZZATO su cui girano gli stadi 2-7.

Tesi e vincoli: projects/asmile/.collegio/CONTEXT.md
Linee rosse:    projects/asmile/.collegio/GLOSSARIO.md
Metodo (lenti/gate/perimetro): .claude/agents/asmile-log-harvester.md

Perimetro (NON negoziabile, dall'agente):
  - NON cancella e NON modifica MAI i grezzi. Marca, non butta.
  - NON etichetta gli eventi guida (stadio 2, event-miner).
  - NON calcola depth (stadio 3, scene-reconstructor).
  - static_rig / low_light / dropout si MARCANO, non si spingono a valle "per completezza".

Dipendenze: solo stdlib. `ffprobe`/`ffmpeg` sono opzionali (best-effort per durata
video e brightness); se assenti, i gate CSV restano validi e la luce resta 'unknown'.

Uso:
  python3 harvest.py                         # scopre le sessioni di default, scrive il corpus
  python3 harvest.py --roots DIR1 DIR2       # aggiunge cartelle radice da scandire
  python3 harvest.py --no-video              # salta ffprobe/brightness (solo CSV, veloce)
  python3 harvest.py --out CORPUS_DIR        # cartella corpus (default: ./corpus)
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# --- Soglie dei gate (dall'agente asmile-log-harvester + GLOSSARIO) ---------
SPEED_MOVING_MS = 0.3      # gps_speed sopra cui la bici e' "in movimento"
GYRO_MOVING_DPS = 3.0      # |gyro_z| sopra cui c'e' guida (sterzata/imbardata)
ENC_MOVING_COUNTS = 2      # delta encoder (12-bit) oltre il rumore = sterzo attivo
STATIC_RIG_MAX_FRAC = 0.02 # < 2% di righe in movimento -> sessione a bici ferma
DROPOUT_GAP_S = 0.5        # buco fra due campioni oltre cui e' un dropout
WARMUP_S = 2.0             # primi 2s / frame 0-30 = warm-up esposizione, si saltano
LOW_LIGHT_YAVG = 60.0      # brightness media sotto cui e' probabile notte/gst-launch
SYNC_TOL_S = 1.5           # tolleranza |durata_video - durata_sensori| per dirsi sync

# Radici di default: i log gia' scaricati sul Mac (guide reali di Asmile).
# __file__ = .../asmile/training/sim2real/harvest.py -> parents[2] = .../asmile
DEFAULT_ROOTS = [
    Path(__file__).resolve().parents[2] / "segmentazione" / "da_segmentare",
]


def _parse_ts(s: str) -> float | None:
    """ISO 8601 -> epoch secondi. Tollera 'Z' e microsecondi assenti."""
    s = s.strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _enc_delta(a: int, b: int, span: int = 4096) -> int:
    """Delta encoder assoluto 12-bit con wrap-around (0<->4095)."""
    d = abs(a - b) % span
    return min(d, span - d)


def analyze_sensors(csv_path: Path) -> dict:
    """Legge sensors.csv e calcola durata, %-in-movimento, dropout, gps-fix.

    E' il cuore del gate segnale-vs-rumore: separa una guida vera da una
    sessione sul cavalletto (l'errore del 2026-05-18, GB di video statici).
    """
    rows = 0
    moving = 0
    gps_fix = 0
    ts_first = ts_last = None
    prev_ts = None
    prev_enc = None
    dropouts = 0
    dropout_s = 0.0
    speed_sum = 0.0
    speed_max = 0.0

    with csv_path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            ts = _parse_ts(r.get("timestamp", ""))
            if ts is None:
                continue
            rows += 1
            if ts_first is None:
                ts_first = ts
            ts_last = ts

            # dropout: buco temporale fra due campioni consecutivi
            if prev_ts is not None:
                gap = ts - prev_ts
                if gap > DROPOUT_GAP_S:
                    dropouts += 1
                    dropout_s += gap
            prev_ts = ts

            # segnali di movimento
            try:
                speed = float(r.get("gps_speed_ms", 0) or 0)
            except ValueError:
                speed = 0.0
            try:
                gz = abs(float(r.get("imu_gyro_z", 0) or 0))
            except ValueError:
                gz = 0.0
            try:
                enc = int(float(r.get("encoder_pos", 0) or 0))
            except ValueError:
                enc = prev_enc if prev_enc is not None else 0

            enc_moved = prev_enc is not None and _enc_delta(enc, prev_enc) > ENC_MOVING_COUNTS
            prev_enc = enc

            speed_sum += speed
            speed_max = max(speed_max, speed)
            if speed > SPEED_MOVING_MS or gz > GYRO_MOVING_DPS or enc_moved:
                moving += 1

            try:
                lat = float(r.get("gps_lat", 0) or 0)
                lon = float(r.get("gps_lon", 0) or 0)
            except ValueError:
                lat = lon = 0.0
            if lat != 0.0 or lon != 0.0:
                gps_fix += 1

    if rows == 0 or ts_first is None:
        return {"rows": 0, "usable": False, "reason": "csv vuoto o senza timestamp"}

    duration = max(0.0, ts_last - ts_first)
    move_frac = moving / rows if rows else 0.0
    return {
        "rows": rows,
        "duration_s": round(duration, 1),
        "sample_hz": round(rows / duration, 2) if duration > 0 else 0.0,
        "move_fraction": round(move_frac, 3),
        "moving_seconds": round(move_frac * duration, 1),
        "speed_avg_ms": round(speed_sum / rows, 3),
        "speed_max_ms": round(speed_max, 3),
        "gps_fix_fraction": round(gps_fix / rows, 3),
        "dropouts": dropouts,
        "dropout_seconds": round(dropout_s, 1),
        "ts_start": datetime.fromtimestamp(ts_first).isoformat(timespec="seconds"),
        "usable": True,
    }


def probe_video(video: Path) -> dict:
    """Best-effort: durata + risoluzione via ffprobe. Silenzioso se assente."""
    if not shutil.which("ffprobe") or not video.exists():
        return {"present": video.exists(), "probe": False}
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:format=duration",
             "-of", "json", str(video)],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(out.stdout or "{}")
        st = (data.get("streams") or [{}])[0]
        dur = float((data.get("format") or {}).get("duration", 0) or 0)
        w, h = st.get("width"), st.get("height")
        return {
            "present": True, "probe": True,
            "duration_s": round(dur, 1),
            "width": w, "height": h,
            "stereo_2560x800": (w == 2560 and h == 800),
        }
    except (subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return {"present": True, "probe": False}


def sample_brightness(video: Path, n_samples: int = 3) -> float | None:
    """Brightness media (YAVG) su pochi frame campionati, dopo il warm-up.

    Best-effort con ffmpeg+signalstats. Ritorna None se ffmpeg manca/fallisce:
    in quel caso la luce resta 'unknown' e NON si marca low_light a caso.
    """
    if not shutil.which("ffmpeg") or not video.exists():
        return None
    try:
        # 1 frame ogni ~150 (a 15fps ~ ogni 10s), salta i primi frame di warm-up.
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats",
             "-ss", str(WARMUP_S), "-i", str(video),
             "-vf", "select='not(mod(n,150))',signalstats,metadata=print",
             "-frames:v", str(n_samples), "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=60,
        )
        vals = []
        for line in proc.stderr.splitlines():
            if "lavfi.signalstats.YAVG" in line:
                try:
                    vals.append(float(line.split("=")[-1].strip()))
                except ValueError:
                    pass
        if vals:
            return round(sum(vals) / len(vals), 1)
    except subprocess.SubprocessError:
        return None
    return None


def harvest_session(session: Path, want_video: bool) -> dict | None:
    """Analizza una sessione e ne compila il manifest con i flag di qualita'."""
    csv_path = session / "sensors.csv"
    if not csv_path.exists():
        return None

    manifest: dict = {
        "session": session.name,
        "path": str(session),
        "raw": {
            "sensors_csv": str(csv_path),
            "video_h264": str(session / "video.h264") if (session / "video.h264").exists() else None,
            "video_mp4": str(session / "video.mp4") if (session / "video.mp4").exists() else None,
        },
        "sensors": analyze_sensors(csv_path),
        "flags": [],
    }

    s = manifest["sensors"]
    if not s.get("usable"):
        manifest["flags"].append("empty")
        manifest["decision"] = "scarta"
        return manifest

    # --- Gate 1: bici ferma sul cavalletto -> static_rig ---
    if s["move_fraction"] < STATIC_RIG_MAX_FRAC:
        manifest["flags"].append("static_rig")

    # --- Gate 2: dropout ---
    if s["dropouts"] > 0:
        manifest["flags"].append("dropout")

    # --- Gate 3: no gps-fix (utile ma non squalificante: gyro+encoder restano) ---
    if s["gps_fix_fraction"] < 0.05:
        manifest["flags"].append("no_gps_fix")

    # --- Video: probe + brightness (best-effort) + sync ---
    video = session / "video.mp4"
    if not video.exists():
        video = session / "video.h264"
    if want_video:
        vinfo = probe_video(video)
        manifest["video"] = vinfo
        yavg = sample_brightness(video)
        manifest["video"]["brightness_yavg"] = yavg
        if yavg is not None and yavg < LOW_LIGHT_YAVG:
            manifest["flags"].append("low_light")
        # sync video<->sensori
        if vinfo.get("probe") and vinfo.get("duration_s"):
            drift = abs(vinfo["duration_s"] - s["duration_s"])
            manifest["video"]["sync_drift_s"] = round(drift, 1)
            if drift > SYNC_TOL_S:
                manifest["flags"].append("sync_drift")
    else:
        manifest["video"] = {"present": video.exists(), "probe": False}

    # --- Decisione dell'harvester (marca, non cancella) ---
    if "static_rig" in manifest["flags"]:
        # Linea rossa dell'agente: se e' 100% static_rig, si ferma qui, non a valle.
        manifest["decision"] = "escludi_da_training(static_rig)"
    elif "empty" in manifest["flags"]:
        manifest["decision"] = "scarta"
    else:
        manifest["decision"] = "ammetti_al_corpus"
    return manifest


def discover_sessions(roots: list[Path]) -> list[Path]:
    """Trova ricorsivamente le cartelle session_* che contengono sensors.csv."""
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for sc in root.rglob("sensors.csv"):
            found.append(sc.parent)
    # dedup + ordina per nome (cronologico: session_YYYYMMDD_HHMMSS)
    return sorted(set(found), key=lambda p: p.name)


def main() -> int:
    ap = argparse.ArgumentParser(description="Stadio 1 harvester — corpus pulito e indicizzato")
    ap.add_argument("--roots", nargs="*", default=None,
                    help="cartelle radice da scandire (oltre a quelle di default)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "corpus"),
                    help="cartella di output del corpus (default: ./corpus)")
    ap.add_argument("--no-video", action="store_true",
                    help="salta ffprobe/brightness (solo gate CSV, veloce)")
    args = ap.parse_args()

    roots = list(DEFAULT_ROOTS)
    if args.roots:
        roots += [Path(os.path.expanduser(r)).resolve() for r in args.roots]

    out_dir = Path(args.out)
    (out_dir / "manifests").mkdir(parents=True, exist_ok=True)

    sessions = discover_sessions(roots)
    print(f"[harvester] scoperte {len(sessions)} sessioni in {len(roots)} radici")

    index = {
        "generated_by": "asmile-log-harvester (stage 1)",
        "roots": [str(r) for r in roots],
        "sessions": [],
        "totals": {},
    }
    tot_sessions = tot_moving = 0.0
    n_static = n_low = n_drop = n_admit = 0

    for sess in sessions:
        m = harvest_session(sess, want_video=not args.no_video)
        if m is None:
            continue
        (out_dir / "manifests" / f"{m['session']}.json").write_text(
            json.dumps(m, indent=2, ensure_ascii=False))
        index["sessions"].append({
            "session": m["session"],
            "moving_seconds": m["sensors"].get("moving_seconds", 0),
            "move_fraction": m["sensors"].get("move_fraction", 0),
            "duration_s": m["sensors"].get("duration_s", 0),
            "flags": m["flags"],
            "decision": m["decision"],
        })
        dur = m["sensors"].get("duration_s", 0) or 0
        mv = m["sensors"].get("moving_seconds", 0) or 0
        tot_sessions += dur
        if "static_rig" in m["flags"]:
            n_static += 1
        else:
            tot_moving += mv
        if "low_light" in m["flags"]:
            n_low += 1
        if "dropout" in m["flags"]:
            n_drop += 1
        if m["decision"] == "ammetti_al_corpus":
            n_admit += 1
        flagstr = ",".join(m["flags"]) or "clean"
        print(f"  {m['session']:>26}  mov={mv:6.1f}s / {dur:6.1f}s  [{flagstr}] -> {m['decision']}")

    index["totals"] = {
        "sessions": len(index["sessions"]),
        "admitted_to_corpus": n_admit,
        "static_rig": n_static,
        "low_light": n_low,
        "dropout": n_drop,
        "total_recorded_seconds": round(tot_sessions, 1),
        "moving_seconds_admitted": round(tot_moving, 1),
        "moving_hours_admitted": round(tot_moving / 3600, 2),
    }
    (out_dir / "corpus_index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False))

    t = index["totals"]
    print("\n[harvester] --- corpus ---")
    print(f"  ammesse al corpus : {t['admitted_to_corpus']}/{t['sessions']}")
    print(f"  static_rig marcate: {t['static_rig']}  low_light: {t['low_light']}  dropout: {t['dropout']}")
    print(f"  ore in movimento  : {t['moving_hours_admitted']} h  (registrate: {round(t['total_recorded_seconds']/3600,2)} h)")
    print(f"  indice           -> {out_dir / 'corpus_index.json'}")
    # Q1 (QUESTIONI_APERTE): BC gia' ora; PPO fedele quando il corpus in movimento > ~5h.
    if t["moving_hours_admitted"] < 5:
        print(f"  nota Q1: {t['moving_hours_admitted']}h < 5h -> BC ok, PPO ancora prematuro (vedi QUESTIONI_APERTE Q1).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
