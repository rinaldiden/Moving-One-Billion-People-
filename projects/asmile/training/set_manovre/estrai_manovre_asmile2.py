#!/usr/bin/env python3
"""estrai_manovre_asmile2.py — frenate e sterzate di Daniele sui giri di asmile2 (aprile-maggio 2026), per il set del maestro.
Sorgenti (sola lettura, i video NON si copiano):
  projects/asmile/segmentazione/da_segmentare/session_*        (16/04-08/05, sorgente di training/sim2real/harvest.py)
  /Users/danielerinaldi/Desktop/asmile2_poschiavo_20260519-20/session_*   (10/05-20/05, Poschiavo e altri)
Ogni sessione: video.h264 (Camarray SBS, 2560x800 o 1280x400) + sensors.csv (10 Hz) + metadata.json (start_time, fps).
asmile2 NON ha encoder ruota: velocita' = GPS (10 Hz, solo con fix), quindi frenate di qualita' 'media'. Ha l'encoder sterzo
(encoder_pos) e l'IMU: sterzate di qualita' 'alta' per il manubrio, che e' cio' che serve allo STILE DI STERZATA.
Soglie (dichiarate prima, decisione registrata):
  moto: v_GPS>1.0 m/s per >5 s (il GPS fermo oscilla fino a ~0.5 m/s)
  frenata: decelerazione da GPS (Savitzky-Golay 1.5 s) < -0.5 m/s2, estesa finche' < -0.15; durata >=1 s, calo >=0.8 m/s, v0 >=1.5 m/s
  sterzata: |gyro_z - bias| > 22 gradi/s con v>1 m/s per >=0.5 s (come #001); ampiezza in passi encoder dal valore a inizio
            manovra; gradi = passi*360/4096 SOLO se l'encoder e' sull'asse del manubrio 1:1 (NON verificato: dichiarato)
Fotogramma video = (t - start_time)*fps (nessun timestamp per fotogramma: aggancio +-1 fotogramma presunto, non verificato).
Calibrazione stereo: asmile2 ha la SUA; qui nessuna distanza (mai la calib di #001 o dei logger).
Uscita: training/set_manovre/manovre_asmile2.csv + sessioni_asmile2.csv
"""
import datetime, glob, json, os
import numpy as np, pandas as pd
from scipy.signal import savgol_filter

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOTS = [os.path.join(ROOT, "segmentazione", "da_segmentare"), "/Users/danielerinaldi/Desktop/asmile2_poschiavo_20260519-20"]
HZ = 10.0


def runs(mask, gap=3):
    idx = np.where(mask)[0]
    if len(idx) == 0: return []
    cut = np.where(np.diff(idx) > gap)[0]
    st = np.r_[0, cut + 1]; en = np.r_[cut, len(idx) - 1]
    return [(idx[a], idx[b]) for a, b in zip(st, en)]


def main():
    M, SS = [], []
    for root in ROOTS:
        for sd in sorted(glob.glob(os.path.join(root, "session_*"))):
            name = os.path.basename(sd)
            info = dict(unita="asmile2", sessione=name, cartella=sd)
            try:
                md = json.load(open(os.path.join(sd, "metadata.json")))
                d = pd.read_csv(os.path.join(sd, "sensors.csv"))
            except Exception as e:
                info.update(esito=f"illeggibile: {e}"); SS.append(info); continue
            if len(d) < 100 or not os.path.exists(os.path.join(sd, "video.h264")):
                info.update(esito="corta o senza video"); SS.append(info); continue
            t0 = datetime.datetime.fromisoformat(md["start_time"]).timestamp(); fps = float(md.get("video_fps", 15))
            d = d[d.timestamp.apply(lambda x: isinstance(x, str))].reset_index(drop=True)      # righe troncate/vuote a fine file
            if len(d) < 100:
                info.update(esito="corta"); SS.append(info); continue
            d["t"] = [datetime.datetime.fromisoformat(x).timestamp() for x in d.timestamp]
            for c in ("gps_lat", "gps_speed_ms", "imu_gyro_z", "encoder_pos"): d[c] = pd.to_numeric(d[c], errors="coerce")
            fix = d.gps_lat.abs() > 0.1
            v = d.gps_speed_ms.where(fix).interpolate(limit=20).fillna(0).values
            n = len(v)
            win = 15 if n > 15 else (n // 2) * 2 - 1
            vs = savgol_filter(v, win, 2); a = savgol_filter(v, win, 2, deriv=1, delta=1 / HZ)
            still = vs < 0.3
            bias = float(d.imu_gyro_z[still].median()) if still.sum() > 30 else float(d.imu_gyro_z.median())
            gz = savgol_filter(d.imu_gyro_z.values - bias, 5 if n > 5 else 1, 1) if n > 5 else d.imu_gyro_z.values - bias
            enc = d.encoder_pos.values.astype(float)
            enc_ok = np.isfinite(enc).mean() > 0.9 and np.nanstd(enc) > 2
            moto = [(i, j) for i, j in runs(vs > 1.0, gap=20) if (j - i) / HZ > 5]
            info.update(esito="ok", data=md["start_time"][:19], durata_s=round((d.t.iloc[-1] - d.t.iloc[0]), 1), fix_gps=round(float(fix.mean()), 2),
                        moto_s=round(sum((j - i) / HZ for i, j in moto), 1), metri=round(float(sum(vs[i:j].sum() / HZ for i, j in moto)), 1),
                        risoluzione=f"{md.get('video_width')}x{md.get('video_height')}", bitrate_kbps=int(md.get("video_bitrate", 0)) // 1000,
                        encoder_sterzo=bool(enc_ok), vesc="vesc_rpm" in d.columns)
            nb = ns = 0
            for i0, j0 in moto:
                for i, j in runs(a[i0:j0] < -0.5, gap=3):
                    i += i0; j += i0
                    while i > i0 and a[i - 1] < -0.15: i -= 1
                    while j < j0 - 1 and a[j + 1] < -0.15: j += 1
                    dur = (j - i) / HZ; v0 = float(vs[i]); v1 = float(vs[j])
                    if dur < 1.0 or v0 - v1 < 0.8 or v0 < 1.5: continue
                    tt = float(d.t.iloc[i])
                    M.append(dict(unita="asmile2", tipo="frenata", sessione=name, cartella=sd, video=os.path.join(sd, "video.h264"),
                                  frame=int(round((tt - t0) * fps)), ora=datetime.datetime.fromtimestamp(tt).isoformat(timespec="seconds"), chi="Daniele",
                                  classe="stop_umano" if v1 * 3.6 < 2 else "umano", v0_kmh=round(v0 * 3.6, 2), v1_kmh=round(v1 * 3.6, 2), durata_s=round(dur, 2),
                                  dec_media=round((v0 - v1) / dur, 3), dec_picco=round(float(-a[i:j + 1].min()), 3),
                                  gps_lat=float(d.gps_lat.iloc[i]) if fix.iloc[i] else None, gps_lon=float(d.gps_lon.iloc[i]) if fix.iloc[i] else None,
                                  fonte_v="gps", qualita="media")); nb += 1
                m = np.zeros(n, bool); m[i0:j0] = (np.abs(gz[i0:j0]) > 22) & (vs[i0:j0] > 1.0)
                for i, j in runs(m, gap=3):
                    if (j - i) / HZ < 0.5: continue
                    k = max(i0, i - 15)
                    amp = float(np.nanmax(np.abs(enc[i:j + 1] - enc[k]))) if enc_ok else None
                    rate = float(np.nanmax(np.abs(np.gradient(enc[k:j + 1]) * HZ))) if enc_ok and j + 1 - k > 2 else None
                    tt = float(d.t.iloc[i])
                    M.append(dict(unita="asmile2", tipo="sterzata", sessione=name, cartella=sd, video=os.path.join(sd, "video.h264"),
                                  frame=int(round((tt - t0) * fps)), ora=datetime.datetime.fromtimestamp(tt).isoformat(timespec="seconds"), chi="Daniele", classe="sterzata",
                                  v0_kmh=round(float(vs[i:j + 1].mean()) * 3.6, 2), durata_s=round((j - i) / HZ, 2),
                                  imbardata_picco_dps=round(float(np.abs(gz[i:j + 1]).max()), 1),
                                  sterzo_ampiezza_passi=None if amp is None else round(amp, 1),
                                  sterzo_ampiezza_deg_se_1a1=None if amp is None else round(amp * 360 / 4096, 1),
                                  sterzo_vel_picco_passi_s=None if rate is None else round(rate, 1),
                                  vesc_corrente_max_a=round(float(d.vesc_i_motor.iloc[i:j + 1].abs().max()), 2) if "vesc_i_motor" in d.columns else None,
                                  gps_lat=float(d.gps_lat.iloc[i]) if fix.iloc[i] else None, gps_lon=float(d.gps_lon.iloc[i]) if fix.iloc[i] else None,
                                  fonte_v="gps", qualita="alta (sterzo) / media (velocita')" if enc_ok else "media")); ns += 1
            info.update(frenate=nb, sterzate=ns)
            SS.append(info)
            print(name, info.get("moto_s"), "s moto", nb, "fren", ns, "sterz", flush=True)
    pd.DataFrame(M).to_csv(os.path.join(HERE, "manovre_asmile2.csv"), index=False)
    pd.DataFrame(SS).to_csv(os.path.join(HERE, "sessioni_asmile2.csv"), index=False)
    S = pd.DataFrame(SS)
    print("sessioni", len(S), "ore video", round(S.durata_s.sum() / 3600, 2), "ore moto", round(S.moto_s.sum() / 3600, 2), "manovre", len(M))


if __name__ == "__main__":
    main()
