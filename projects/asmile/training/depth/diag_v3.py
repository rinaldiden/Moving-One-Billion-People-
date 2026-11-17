#!/usr/bin/env python3
"""diag_v3.py f1 f2 ... — diagnosi per stadio sui casi fissi (v2): per ogni frame elenca TUTTE le componenti con il motivo di scarto
(stessa logica di obstacles_v2) e salva L / disparita' / altezza in out_20261110/diag_v3/. Solo diagnosi, nessuna soglia cambia."""
import json, os, sys, cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import depth_seg_001 as D, obstacles_v2 as O
SESS = "session_20261109_094146"
fr = [int(x) for x in sys.argv[1:]]
OUT = os.path.join(HERE, "out_20261110/diag_v3"); os.makedirs(OUT, exist_ok=True)
rc = D.Rect(); vL = os.path.join(D.LOGS, f"{SESS}_right.h264"); vR = os.path.join(D.LOGS, f"{SESS}_left.h264")
H, W, B, CAM_H = O.H, O.W, O.B, O.CAM_H
for i, (Lr, Rr) in enumerate(zip(D.gray_frames(vL), D.gray_frames(vR))):
    if i > max(fr): break
    if i not in fr: continue
    L, R = rc(Lr, Rr); disp = O.disparity_v2(L, R); g = O.ground_plane(disp, rc.cx)
    print(f"=== frame {i} piano {None if g is None else [round(x,3) for x in g]}  disp valida {100*(disp>4).mean():.0f}%")
    a, vh, b = g
    v = np.arange(H, dtype=np.float32)[:, None]; u = np.arange(W, dtype=np.float32)[None, :]
    dg = np.maximum(a * (v - vh) + b * (u - rc.cx), 0.1); valid = disp > 4
    Z = np.where(valid, rc.f * B / np.maximum(disp, 1e-3), 0); X = (u - rc.cx) * Z / rc.f
    y = CAM_H * (disp - dg) / np.maximum(disp, 1e-3)
    m0 = valid & (Z >= 2) & (Z <= 15) & (np.abs(X) <= 4.5) & (y >= O.HPIX_MIN + 1.5 * CAM_H / np.maximum(disp, 1.0)) & (y <= 3.0)
    m = cv2.morphologyEx(m0.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)); m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    vis = cv2.cvtColor(L, cv2.COLOR_GRAY2BGR)
    for k in range(1, n):
        x0, y0, bw, bh, area = st[k]
        if area < 300: continue
        mk = lab == k; zz = Z[mk]; z20, z80 = np.percentile(zz, [20, 80]); zm = np.median(zz)
        wm, hm_ = bw * zm / rc.f, bh * zm / rc.f
        ys_, xs_ = np.nonzero(mk); base = ys_ >= np.percentile(ys_, 85); yb = float(np.median(y[ys_[base], xs_[base]]))
        hv = y[mk]; hmed, h90 = float(np.median(hv)), float(np.percentile(hv, 90))
        xc = float((x0 + bw / 2 - rc.cx) * z20 / rc.f)
        why = []
        if wm < O.W_MIN_M or hm_ < O.H_BOX_MIN_M: why.append(f"dim {wm:.2f}x{hm_:.2f}")
        if z80 > 1.3 * z20 + 0.4: why.append(f"coer z20={z20:.1f} z80={z80:.1f}")
        if yb > 0.5: why.append(f"base_y={yb:.2f}")
        if hmed < O.HMED_MIN or h90 < O.HPEAK_MIN: why.append(f"h {hmed:.2f}/{h90:.2f}")
        print(f"  comp box=({x0},{y0},{x0+bw},{y0+bh}) area={area} Z20={z20:.1f} Z80={z80:.1f} X={xc:+.1f} h_med={hmed:.2f} h90={h90:.2f} -> {'OK' if not why else 'SCARTO '+'; '.join(why)}")
        cv2.rectangle(vis, (x0, y0), (x0 + bw, y0 + bh), (0, 255, 0) if not why else (0, 0, 255), 2)
        cv2.putText(vis, f"{z20:.1f}", (x0, max(15, y0 - 4)), 0, 0.6, (0, 255, 255), 2)
    dv = cv2.applyColorMap(np.clip(disp * 255 / 160, 0, 255).astype(np.uint8), cv2.COLORMAP_JET); dv[~valid] = 0
    hv_ = cv2.applyColorMap(np.clip((y + 0.5) * 100, 0, 255).astype(np.uint8), cv2.COLORMAP_JET); hv_[~valid] = 0
    cv2.imwrite(f"{OUT}/f{i:05d}.jpg", np.vstack([np.hstack([vis, dv]), np.hstack([cv2.cvtColor(L, cv2.COLOR_GRAY2BGR), hv_])]))
