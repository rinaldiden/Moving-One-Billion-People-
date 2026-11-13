#!/usr/bin/env python3
"""corridoio_replay_001.py — replay CAUSALE di pi/autonomous/corridoio.py sul log sensor_hub del 09/11 (#001, calib sterzo di allora: centro 6606).
Verita' = traiettoria poi percorsa (odometria ruota + imbardata gz integrata, bias a bici ferma), vista nel riferimento di t0.
Metà sessione A per scegliere i parametri (griglia), metà B (held-out) per misurare. Confronto: offline ego_001 (media mobile centrata, zero fase), rettilineo, solo sterzo."""
import os, sys, csv, json, time, itertools, copy
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pi", "autonomous")); sys.path.insert(0, HERE)
from corridoio import Corridoio
from ego_001 import path_xz
SF = os.path.join(ROOT, "asmile-loggers", "asmile-001", "_sensors", "sensors", "sensors_20261109_085334.csv")
CAL_0911 = {"unit": "asmile-001", "encoder_center_raw": 6606, "deg_per_step": 0.02197, "encoder_pos_increases_to": "DX (destra)", "encoder_bits": 14,
            "delta_dx_deg": 45.0, "delta_sx_deg": -45.0}
ZS = (3.0, 5.0, 10.0)

def carica():
    T, C, G, S = [], [], [], []
    for r in csv.DictReader(open(SF)):
        if r["enc_wheel_cum"] and r["imu_gz_dps"] and r["enc_steer_raw"]:
            T.append(float(r["t_ms"]) / 1000); C.append(float(r["enc_wheel_cum"])); G.append(float(r["imu_gz_dps"])); S.append(int(float(r["enc_steer_raw"])))
    return np.array(T), np.array(C), np.array(G), np.array(S)

def vcausale(t, s, w=0.2):
    j = np.searchsorted(t, t - w); j = np.minimum(j, np.arange(len(t)) - 1).clip(0)
    return np.where(t > t[j], (s - s[j]) / np.maximum(t - t[j], 1e-6), 0.0)

def verita(t, s, yaw_dx_dps):
    psi = np.concatenate([[0], np.cumsum(np.radians(yaw_dx_dps[1:]) * np.diff(t))])      # + destra
    ds = np.diff(s, prepend=s[0]); px = np.cumsum(ds * np.sin(psi)); pz = np.cumsum(ds * np.cos(psi))   # px destra, pz avanti nel frame iniziale
    return psi, px, pz

def errori(ks, idx, t, s, psi, px, pz, par_L, zs=ZS, zmax=12.0):
    """ks[i] = curvatura prevista a idx[i]; errore laterale |x_prev(Z) - x_reale(Z)| ai Z."""
    out = {z: [] for z in zs}; sg = {z: [] for z in zs}
    for k0, i in zip(ks, idx):
        p0 = psi[i]; dz = pz - pz[i]; dx = px - px[i]
        j1 = np.searchsorted(s, s[i] + zmax * 1.2); sl = slice(i, j1)
        zl = dz[sl] * np.cos(p0) + dx[sl] * np.sin(p0); xl = -dz[sl] * np.sin(p0) + dx[sl] * np.cos(p0)   # frame di t0: z avanti, x destra
        zp, xp = path_xz(k0, L=par_L, smax=zmax * 1.3)
        for z in zs:
            if zl[-1] < z: continue
            xr = np.interp(z, zl, xl); out[z].append(abs(float(np.interp(z, zp, xp)) - xr)); sg[z].append(float(np.interp(z, zp, xp)) - xr)
    return out, sg

def stat(o):
    return {z: (float(np.median(v)), float(np.percentile(v, 90)), len(v)) if v else (np.nan, np.nan, 0) for z, v in o.items()}

def run_corr(par, t, cum, g, st, calib=CAL_0911, mpc=2.1219e-5):
    base = json.load(open(os.path.join(ROOT, "config", "corridoio_001.json"))); base["parametri"].update(par)
    c = Corridoio("asmile-001", calib=calib, params=base)
    v = vcausale(t, cum * mpc); K = np.empty(len(t)); t0 = time.perf_counter()
    for i in range(len(t)):
        c.update(t[i], st[i], v[i], g[i]); K[i] = c.k
    dtu = (time.perf_counter() - t0) / len(t) * 1e3
    return K, v, c, dtu

def main():
    t, cum, g, st = carica(); n = len(t); s = cum * 2.1219e-5
    vfer = vcausale(t, s, 1.0)
    bias = float(np.median(g[vfer < 0.02]))
    psi, px, pz = verita(t, s, -(g - bias))
    v = vcausale(t, s)
    mid = n // 2
    cand = np.arange(0, n, 25)                       # ogni 0.5 s
    cand = cand[(v[cand] > 1.5) & (cand < n - 2000)]
    mid = cand[len(cand) // 2]; A = cand[cand < mid]; B = cand[cand >= mid]   # meta' cronologica dei campioni IN MOVIMENTO (la prima meta' del file e' ferma)
    cand_low = np.arange(0, n, 25); cand_low = cand_low[(v[cand_low] > 0.5) & (v[cand_low] <= 1.5) & (cand_low < n - 2000)]
    print(f"righe {n}, bias gz {bias:.2f}; candidati v>1.5: A {len(A)} B {len(B)}; 0.5<v<=1.5: {len(cand_low)}")
    grid = dict(L_decadimento_m=[2.5, 3.5, 5.0, 8.0], tau_yaw_s=[0.1, 0.2, 0.4], peso_imu_max=[0.5, 0.8, 1.0], rapporto_ruota_colonna=[0.47, 0.55, 0.646, 0.75], v_imu_hi_ms=[1.5, 2.5])
    res = []
    keys = list(grid)
    cache = {}
    for vals in itertools.product(*[grid[k] for k in keys]):
        par = dict(zip(keys, vals)); par["v_imu_lo_ms"] = 1.0 if par["v_imu_hi_ms"] == 1.5 else 1.5
        key = tuple(vals[1:])
        K, vv, c, dtu = run_corr({k: par[k] for k in par if k != "L_decadimento_m"}, t, cum, g, st) if key not in cache else cache[key]
        cache[key] = (K, vv, c, dtu)
        o, _ = errori(K[A[::2]], A[::2], t, s, psi, px, pz, par["L_decadimento_m"])
        st_ = stat(o); score = sum(st_[z][0] + 0.5 * st_[z][1] for z in ZS)
        res.append((score, par))
    res.sort(key=lambda r: r[0]); best = res[0][1]
    print("miglior parametro su A:", best, "score", round(res[0][0], 3))
    # held-out B
    pb = {k: best[k] for k in best if k != "L_decadimento_m"}
    K, vv, c, dtu = run_corr(pb, t, cum, g, st)
    ob, sgb = errori(K[B], B, t, s, psi, px, pz, best["L_decadimento_m"]); sb = stat(ob)
    oa, sga = errori(K[A], A, t, s, psi, px, pz, best["L_decadimento_m"]); sa = stat(oa)
    # iniziale (parametri ego_001 portati nel causale senza tarare)
    K0, _, _, _ = run_corr({}, t, cum, g, st); o0, _ = errori(K0[B], B, t, s, psi, px, pz, 3.5); s0 = stat(o0)
    # offline ego_001: media mobile centrata +-0.2 s, k = w k_imu + (1-w) k_st
    n_ = 21; ker = np.ones(n_) / n_; sm = lambda x: np.convolve(np.pad(x, n_ // 2, mode="edge"), ker, mode="valid")
    yaw = sm(-(g - bias)); stg = sm((st - 6606) * 0.02197); vs = sm(vcausale(t, s, 0.5) * 0 + np.gradient(s, t))
    # velocita' centrata come ego_001 (+-0.25 s)
    vc = (np.interp(t + 0.25, t, s) - np.interp(t - 0.25, t, s)) / 0.5; vs = sm(vc)
    wk = np.clip((vs - 1.0) / 0.5, 0, 1); koff = wk * np.radians(yaw) / np.maximum(vs, 1.0) + (1 - wk) * 0.00968 * stg
    oo, _ = errori(koff[B], B, t, s, psi, px, pz, 3.5); so = stat(oo)
    kst = 0.00968 * (st - 6606) * 0.02197; ost, _ = errori(kst[B], B, t, s, psi, px, pz, 3.5); sst = stat(ost)
    od, _ = errori(np.zeros(len(B)), B, t, s, psi, px, pz, 3.5); sd = stat(od)
    # bassa velocita'
    ol, _ = errori(K[cand_low], cand_low, t, s, psi, px, pz, best["L_decadimento_m"], zs=(3.0, 5.0)); sl = stat(ol)
    ol2, _ = errori(kst[cand_low], cand_low, t, s, psi, px, pz, 3.5, zs=(3.0, 5.0)); sl2 = stat(ol2)
    od2, _ = errori(np.zeros(len(cand_low)), cand_low, t, s, psi, px, pz, 3.5, zs=(3.0, 5.0)); sl3 = stat(od2)
    # incertezza: p68 su A (tabella), copertura su B
    zt = [0.0, 3.0, 5.0, 10.0, 20.0]; sig = [0.05] + [float(np.percentile(oa[z], 68)) for z in ZS]
    oa20, _ = errori(K[A[::2]], A[::2], t, s, psi, px, pz, best["L_decadimento_m"], zs=(20.0,), zmax=24.0); sig.append(float(np.percentile(oa20[20.0], 68)))
    cop = {z: float(np.mean(np.array(ob[z]) <= np.interp(z, zt, sig))) for z in ZS}
    def fmt(S): return "  ".join(f"{z:.0f} m: {S[z][0]:.2f}/{S[z][1]:.2f} (n={S[z][2]})" for z in S)
    print("\nHELD-OUT B  v>1.5  mediana/p90 errore laterale (m)")
    for nome, S in (("causale tarato", sb), ("causale iniziale (ego_001 params)", s0), ("offline ego_001 (zero fase)", so), ("solo sterzo", sst), ("rettilineo", sd)):
        print(f"  {nome:36s} {fmt(S)}")
    print("sessione A (taratura) causale tarato:", fmt(sa))
    print("\nBASSA VELOCITA' 0.5<v<=1.5 (tutta la sessione)  causale / solo sterzo / dritto"); print("  ", fmt(sl)); print("  ", fmt(sl2)); print("  ", fmt(sl3))
    print("\nincertezza p68 da A:", dict(zip(zt, [round(x, 3) for x in sig])), " copertura su B:", {z: round(c_, 2) for z, c_ in cop.items()})
    print(f"costo update: {dtu*1000:.1f} us/aggiornamento (python puro, Mac); latenza dichiarata {c.latenza:.3f} s a v alta")
    c.update(t[B[0]], st[B[0]], v[B[0]], g[B[0]]); t0 = time.perf_counter()
    for _ in range(2000): c.update(t[B[0]], st[B[0]], v[B[0]], g[B[0]]); c.percorso(); c.dentro(0.3, 6.0)
    print(f"costo update + percorso + dentro: {(time.perf_counter()-t0)/2000*1e6:.1f} us")
    json.dump(dict(best=best, sigma_z=zt, sigma_m=sig), open(os.path.join(os.environ.get("TMPOUT", "/tmp"), "corridoio_best.json"), "w"))
if __name__ == "__main__":
    main()
