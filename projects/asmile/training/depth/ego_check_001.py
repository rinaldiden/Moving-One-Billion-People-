#!/usr/bin/env python3
"""ego_check_001.py — verifiche dei dati di moto proprio usate dal video fluido v6 (094146, v>2 m/s). Uscita JSON in out_20261112_v6/ego_check.json"""
import json, os, numpy as np
import ego_001 as E
e = E.Ego("session_20261109_094146"); t = e.t / 1000.0; v = e.v_s; m = v > 2.0
import csv, datetime as dt
S = np.load("/private/tmp/claude-501/-Users-danielerinaldi-progetti-Moving-One-Billion-People-/1b32ebd7-24f0-43c1-a686-c4879d52bcb7/scratchpad/S094146.npy") if os.path.exists("/private/tmp/claude-501/-Users-danielerinaldi-progetti-Moving-One-Billion-People-/1b32ebd7-24f0-43c1-a686-c4879d52bcb7/scratchpad/S094146.npy") else None
out = dict(bias_gz_dps=e.bias, n_campioni=int(len(e.t)), frac_v_gt_2=float(m.mean()))
if S is not None:
    st = (S[:, 5] - 6606) * 0.02197; v2 = np.gradient(S[:, 1] * 2.1219e-5, S[:, 0] / 1000); vs = np.convolve(v2, np.ones(25) / 25, "same"); mm = vs > 2.0
    out["corr_giroscopio_vs_sterzo_v>2"] = {n: round(float(np.corrcoef(S[mm, k] - np.median(S[:, k]), st[mm])[0, 1]), 3) for k, n in ((2, "gx"), (3, "gy"), (4, "gz"))}
sm = lambda x, n=11: np.convolve(np.pad(x, n // 2, mode="edge"), np.ones(n) / n, mode="valid")
yaw = e.yaw_s; stv = e.steer_s
out["lag_corr_yaw_vs_sterzo"] = {str(l): round(float(np.corrcoef(np.interp(e.t / 1000 + l, e.t / 1000, stv)[m], yaw[m])[0, 1]), 3) for l in (-0.3, -0.1, 0.0, 0.1, 0.3)}
out["k_imu_vs_k_sterzo_v>2"] = dict(corr=round(float(np.corrcoef(e.k_imu[m], e.k_st[m])[0, 1]), 4), rms_diff_1_per_m=round(float(np.sqrt(np.mean((e.k_imu[m] - e.k_st[m]) ** 2))), 4),
                                     rms_k_imu=round(float(np.sqrt(np.mean(e.k_imu[m] ** 2))), 4), c_fit_1_per_m_per_deg=E.C_STEER)
out["effetto_ruota_+3%"] = dict(v_scala=round(E.PROP, 4), k_scala=round(1 / E.PROP, 4), ttc_scala=round(1 / E.PROP, 4), nota="v e distanza percorsa +3.05% se si adotasse wheel_circum 0.3477: k = yaw/v scende del 3%, TTC = Z/(v-w) scende del 3%; Z stereo non cambia")
json.dump(out, open(os.path.join(E.HERE, "out_20261112_v6", "ego_check.json"), "w"), indent=1); print(json.dumps(out, indent=1))
