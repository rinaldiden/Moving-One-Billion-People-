#!/usr/bin/env python3
"""estrai_manovre_logger.py — manovre dei LOGGER per il set (qualita' BASSA, mai mischiate con #001).
asmile-logger001: riusa gli eventi gia' estratti e passati dallo scettico (agents/registro_guide, unita asmile-logger001:
  frenate 'candidata_imu' da IMU con mapping assi 09/11 NON verificato con la ruota, sterzate da imbardata). Nessuna soglia nuova.
  Aggancio al video come training/eventi/logger_guide.py: ora di ogni fotogramma = mtime fine clip - (N-1-k)/15 (N = pacchetti
  contati da ffprobe). L'ora dell'evento nel registro ha risoluzione 1 s -> fotogramma +-15.
logger02: NIENTE estrazione automatica oggi (IMU sulla A senza convenzione assi verificata e senza velocita'): dichiarato.
Uscita: training/set_manovre/manovre_logger.csv
"""
import csv, datetime, glob, os, subprocess
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
REG = os.path.join(ROOT, "agents", "registro_guide")
LOG = os.path.join(ROOT, "asmile-loggers", "asmile-logger")
DATA = {"20261109_ride1050": ("2026-11-09", "clip_20261109_100554"), "20261109_ride1109": ("2026-11-09", "clip_20261109_100554")}


def clips(prefix):
    out = []
    for f in sorted(glob.glob(os.path.join(LOG, f"{prefix}_*.h264"))):
        o = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
                            "-of", "csv=p=0", f], capture_output=True, text=True).stdout.strip()
        if not o.isdigit(): continue           # clip illeggibile
        n = int(o)
        m = os.path.getmtime(f)
        out.append((m - (n - 1) / 15.0, m, n, f))
    return out


def main():
    rows = []
    cache = {}
    for tipo, fn in (("frenata", "frenate.csv"), ("sterzata", "sterzate.csv")):
        d = pd.read_csv(os.path.join(REG, fn))
        d = d[d.unita == "asmile-logger001"]
        for _, r in d.iterrows():
            data, pref = DATA.get(r.sess, (None, None))
            vid = fr = None
            if pref and isinstance(r.get("wall"), str):   # le sterzate nel registro non hanno l'ora: niente aggancio
                ep = datetime.datetime.fromisoformat(f"{data}T{r.wall}").timestamp()
                if pref not in cache: cache[pref] = clips(pref)
                for t0, t1, n, f in cache[pref]:
                    if t0 <= ep <= t1:
                        vid = os.path.relpath(f, ROOT); fr = int(round((ep - t0) * 15)); break
            rows.append(dict(unita="asmile-logger001", tipo=tipo, sessione=r.sess, t_ms=r.t_ms0, ora=f"{data}T{r.get('wall', '')}" if data else "",
                             chi="Daniele", classe=r.get("classe", "sterzata" if tipo == "sterzata" else ""), video=vid or "", frame=fr, meta_video="sx (camera sinistra del file side-by-side)",
                             durata_s=r.get("dur_s"), dec_imu_media=r.get("a_imu_mean"), imbardata_picco_dps=r.get("gz_peak"),
                             fonte_v=r.get("fonte_v"), qualita=r.get("qualita", "bassa"), nota="registro_guide 13/11; aggancio video da mtime clip +-1 s"))
    pd.DataFrame(rows).to_csv(os.path.join(HERE, "manovre_logger.csv"), index=False)
    print(len(rows), "manovre logger001;", sum(1 for r in rows if r["video"]), "con video")


if __name__ == "__main__":
    main()
