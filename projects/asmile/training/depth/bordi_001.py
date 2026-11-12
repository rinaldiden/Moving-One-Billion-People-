#!/usr/bin/env python3
"""bordi_001.py — giro 10 (12/11/2026), SOLO #001. Bordi del percorso (muri/facciate/recinzioni, cordoli, marciapiede) e distanza laterale libera dalla sagoma della bici.
Decisione di Daniele 2026-11-12 (opzione A): un bordo parallelo al percorso NON e' 'primo ostacolo', ma diventa ostacolo se la bici e' troppo vicina (sterza o frena).
Ingressi per fotogramma: mappa Z 320x200 (stadio A), piano strada gp, curvatura k, velocita' v, etichette stuff Mapillary (Mask2Former, 5 Hz, il piu' vicino entro 2 fotogrammi),
poligoni delle maschere con classe (esclusi dai bordi: persone/veicoli/paletti non sono muro) e dei blob classificati 'bordo' dalla geometria.
Geometria: punti 3D (X,Z,h) dalla mappa Z; vista dall'alto (X +-8 m, Z 0..Zc) a celle 0.2x0.25 m, componenti connesse; per ogni componente PCA (Z,X): PARALLELA se estensione >= 1.5 m,
allungamento >= 2 e angolo col percorso <= 35 gradi; altrimenti 'frontale' (oggetto: ostacolo se entra nella sagoma + 0.10 m). Cordolo/marciapiede (classi basse): conta solo il BORDO fra
strada e marciapiede (pixel marciapiede/cordolo adiacenti a pixel strada), mai la superficie (una pista ciclabile su marciapiede non allarma); z dal piano strada se la mappa Z non e' valida.
Distanza laterale libera = (distanza laterale dal centro del percorso, 10 percentile per fascia Z di 0.5 m, >=5 punti) - HW."""
import numpy as np, cv2
from ego_001 import path_xz
F_PX, B_M, CX = 1379.8882680918412, 0.19656132417315123, 660.142
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "pi", "autonomous"))
from soglie import Soglie      # tabella UNICA config/soglie_attuazione_001.json (Daniele 2026-11-12): nessuna soglia di attuazione scritta qui
SOG = Soglie("asmile-001"); HW = SOG.p["larghezza_asmile_m"] / 2.0     # semilarghezza sagoma dalla tabella (1.1 m: ASMILE_WIDTH_M di pi/autonomous/object_depth.py)
V_MIN_ALLARME = 0.3          # parametro di rumore (non di attuazione): sotto 0.3 m/s (bici ferma) nessun allarme
LOW_ON = os.environ.get('BD_LOW', '0') == '1'   # cordolo/marciapiede come bordo: SPENTO di default (giro 10: su pavimentazioni miste di vicolo/piazza il bordo strada/marciapiede della segmentazione era un cambio di superficie, non un bordo: falsi)
ZMIN_B = 2.0                 # sotto 2 m la stereo (288 disparita') non e' affidabile: nessun punto bordo
ANG_MAX, EXT_MIN, ELONG_MIN, N_MIN = 35.0, 1.5, 2.0, 25
CL_WALL, CL_LOW, CL_ROAD = (6, 7), (2, 3), (0, 1)       # indici STUFF: edifici, muri | marciapiede, cordolo | strada, strisce


def margin(v): return SOG.a(v)["bordo_margine_m"]
def zlook(v): return max(SOG.a(v)["rallenta_entro_m"], 2.5)     # si guarda fino a rallenta_entro; FRENA solo entro frena_entro (azione, vedi video_fluido_001)


def _fill(polys, shape=(200, 320)):
    m = np.zeros(shape, np.uint8)
    for p in polys:
        if p is not None and len(p) >= 3: cv2.fillPoly(m, [(np.asarray(p, np.float32) / 4.0).astype(np.int32)], 1)
    return m > 0


def pca_dir(P, k, pz=None, px=None, either=False):
    """P (n,2) = (Z,X). ritorna (ext, elong, ang, parallela)"""
    if len(P) < N_MIN: return 0.0, 0.0, 90.0, False
    c = P.mean(0); C = np.cov((P - c).T); w, V = np.linalg.eigh(C); v1 = V[:, 1]; l1, l2 = max(w[1], 1e-9), max(w[0], 1e-9)
    pr = (P - c) @ v1; ext = float(np.percentile(pr, 95) - np.percentile(pr, 5)); el = float(np.sqrt(l1 / l2))
    if pz is None: pz, px = path_xz(k)
    sp = float(np.interp(c[0], pz[:-1], np.diff(px) / np.maximum(np.diff(pz), 1e-6))); dr = np.array([1.0, sp]); dr /= np.linalg.norm(dr)
    ang = float(np.degrees(np.arccos(min(1.0, abs(float(v1 @ dr))))))
    if either: ang = min(ang, float(np.degrees(np.arccos(min(1.0, abs(float(v1[0])))))))      # v11: parallelo se lo e' all'arco O al percorso dritto (le due ipotesi del corridoio)
    return ext, el, ang, bool(ext >= EXT_MIN and el >= ELONG_MIN and ang <= ANG_MAX)


def blob_geometry(poly, zf, gp, hp, k):
    """classificazione geometrica di un blob (solo i suoi punti): (parallelo, ext, elong, ang) oppure None se pochi punti"""
    if zf is None or gp is None or poly is None or len(poly) < 3: return None
    ga, gvh, gb = gp; m = _fill([poly]); vs, us = np.nonzero(m & (zf != 255) & (zf < 250) & (zf >= 3))
    if len(vs) < N_MIN: return None
    Z = zf[vs, us].astype(np.float32) / 10.0; X = ((us * 4 + 2.0) - CX) * Z / F_PX
    d = F_PX * B_M / Z; h = hp * (1 - ga * ((vs * 4 + 2.0) - gvh) / d); s = (h >= 0.15) & (h <= 2.2)
    if s.sum() < N_MIN: return None
    Z, X = Z[s], X[s]; lo, hi = np.percentile(Z, (10, 90)); q = (Z >= lo) & (Z <= hi)
    ext, el, ang, par = pca_dir(np.stack([Z[q], X[q]], 1), k)
    return par, ext, el, ang


def consistent(zf, tol=0.12, nmin=8):
    """toglie i punti isolati (speckle stereo): un pixel Z resta se >= nmin dei 24 vicini (finestra 5x5) hanno Z entro +-12%"""
    Z = zf.astype(np.float32); ok = (zf != 255) & (zf < 250) & (zf >= 3); cnt = np.zeros(zf.shape, np.int32)
    P = np.pad(Z, 2, constant_values=-1e3); Pk = np.pad(ok, 2, constant_values=False)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dy == 0 and dx == 0: continue
            n = P[2 + dy:2 + dy + zf.shape[0], 2 + dx:2 + dx + zf.shape[1]]; nk = Pk[2 + dy:2 + dy + zf.shape[0], 2 + dx:2 + dx + zf.shape[1]]
            cnt += (nk & (np.abs(n - Z) <= tol * Z)).astype(np.int32)
    return ok & (cnt >= nmin)


BASE_MAX_M = 0.5      # v11: base a terra misurata = punti della fascia a quota <= 0.5 m dal piano strada (errore piano 0.1-0.2 m): dichiarato, non tarato sui fotogrammi
H_MURO = 1.0          # un muro e' ALTO: la mediana del 90 percentile di quota delle fasce della catena >= 1.0 m (toglie linee a terra mal etichettate)
CH_DZ, CH_DX, CH_LEN = 0.8, 0.35, 2.0      # catena di fasce Z: passo <= 0.8 m, salto laterale <= 0.35 m per fascia, lunghezza >= 2.0 m (un bordo vero e' una LINEA lungo il percorso)


def chain_filter(bins):
    """tiene solo le fasce che stanno in una catena continua lungo Z (>= CH_LEN m): toglie speckle e salti laterali (linee trasversali alla strada)"""
    n = len(bins)
    if n == 0: return bins
    par = list(range(n))
    def f(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    for i in range(n):
        for j in range(n):
            dz = bins[j][0] - bins[i][0]
            if 0.2 < dz <= CH_DZ and abs(bins[j][1] - bins[i][1]) <= CH_DX: par[f(i)] = f(j)
    comp = {}
    for i in range(n): comp.setdefault(f(i), []).append(i)
    keep = []
    for idx in comp.values():
        z = [bins[i][0] for i in idx]
        if max(z) - min(z) + 0.5 >= CH_LEN and len(set(z)) >= 3 and float(np.median([bins[i][4] for i in idx])) >= H_MURO: keep += [bins[i] for i in idx]
    return keep


def border_frame(zf, gp, k, v, lab, cls_polys, bord_polys, hp):
    if zf is None or gp is None: return None
    ga, gvh, gb = gp; zl = zlook(v); Zc = max(zl, 10.0); mg = margin(v)
    uu = (np.arange(320) * 4 + 2.0)[None, :]; vv = (np.arange(200) * 4 + 2.0)[:, None]
    valid = consistent(zf); Z = zf.astype(np.float32) / 10.0
    with np.errstate(all="ignore"):
        d = F_PX * B_M / np.where(valid, Z, 1.0); dg = ga * (vv - gvh); h = hp * (1 - dg / d)
        Zg = np.where(dg > 1.0, F_PX * B_M / np.maximum(dg, 1.0), np.nan) * np.ones((200, 320), np.float32)
    X = (uu - CX) * Z / F_PX; clsm = _fill(cls_polys); bm = _fill(bord_polys)
    zeros = np.zeros((200, 320), bool)
    if lab is not None:
        wall = np.isin(lab, CL_WALL); low = np.isin(lab, CL_LOW); road = np.isin(lab, CL_ROAD)
        lowe = low & (cv2.dilate(road.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0)
    else: wall = lowe = zeros
    mo = ((wall & ~clsm) | bm) & valid & (h >= 0.2) & (h <= 2.0)
    Zl = np.where(valid & (np.abs(Z - Zg) < 0.3 * Zg), Z, Zg); Xl = (uu - CX) * Zl / F_PX
    ml = lowe & np.isfinite(Zl) & ~clsm & LOW_ON
    pz, px = path_xz(k); hyps = [(pz, px)] + ([(pz, np.zeros_like(px))] if os.environ.get('BD_HYP2') == '1' else [])      # v11: PROVATE le due ipotesi (arco e dritto) per l'allarme (BD_HYP2=1): allarmi 69->94 fotogrammi e nuovi FRENA in curva (2751-2758) = piu' falsi; RIFIUTATO: l'allarme resta sull'arco come v10 (le due ipotesi servono solo per dire che un muro e' parallelo)
    out = dict(L=dict(bins=[], bh=[[], []], clear=None, viol=None), R=dict(bins=[], bh=[[], []], clear=None, viol=None), zl=zl, margin=mg, ncomp=0, par=0, front=0, npts=int(mo.sum() + ml.sum()))
    for kind, mk, XX, ZZ, HH in (("obj", mo, X, Z, h), ("low", ml, Xl, Zl, np.zeros_like(h))):
        Xp = XX[mk].astype(np.float64); Zp = ZZ[mk].astype(np.float64); Hp = HH[mk].astype(np.float64); s = (Zp >= ZMIN_B) & (Zp <= Zc) & (np.abs(Xp) < 8)
        Xp, Zp, Hp = Xp[s], Zp[s], Hp[s]
        if len(Xp) < N_MIN: continue
        ix = np.clip(((Xp + 8) / 0.2).astype(int), 0, 79); iz = (Zp / 0.25).astype(int); nz = int(Zc / 0.25) + 2
        g = np.zeros((nz, 80), np.float32); np.add.at(g, (iz, ix), 1.0)
        zc_ = ((np.arange(nz) + .5) * .25)[:, None] * np.ones((1, 80)); xc_ = ((np.arange(80) + .5) * .2 - 8)[None, :] * np.ones((nz, 1))
        bx = lambda a: cv2.boxFilter(a.astype(np.float32), -1, (9, 7), normalize=False, borderType=cv2.BORDER_CONSTANT)   # finestra 1.8 m (X) x 1.75 m (Z)
        S = bx(g); mz = bx(g * zc_) / np.maximum(S, 1); mx = bx(g * xc_) / np.maximum(S, 1)
        czz = bx(g * zc_ ** 2) / np.maximum(S, 1) - mz ** 2; cxx = bx(g * xc_ ** 2) / np.maximum(S, 1) - mx ** 2; czx = bx(g * zc_ * xc_) / np.maximum(S, 1) - mz * mx
        tr_ = czz + cxx; det_ = np.sqrt(np.maximum(((czz - cxx) / 2) ** 2 + czx ** 2, 0)); l1 = tr_ / 2 + det_; l2 = np.maximum(tr_ / 2 - det_, 1e-6)
        th = 0.5 * np.arctan2(2 * czx, czz - cxx)            # angolo dell'asse maggiore rispetto a Z (in (Z,X))
        for hyp, (pzh, pxh) in enumerate(hyps):
            slope = np.interp(zc_, pzh[:-1], np.diff(pxh) / np.maximum(np.diff(pzh), 1e-6)); pa = np.arctan(slope)
            da = np.degrees(np.abs(((th - pa + np.pi / 2) % np.pi) - np.pi / 2))
            el = np.sqrt(l1 / l2); cellpar = (S >= 12) & (el >= ELONG_MIN) & (da <= ANG_MAX) & (np.sqrt(l1) * 3.5 >= EXT_MIN / 2)
            cellfr = (S >= 12) & ~cellpar
            ppar = cellpar[iz, ix]; pfr = cellfr[iz, ix]; out["par"] += int(ppar.sum()); out["front"] += int(pfr.sum()); out["ncomp"] += 1
            for isp, sel in ((True, ppar), (False, pfr)):
                if not isp: continue      # i muri FRONTALI restano ostacoli normali del tracking/blob (Daniele: opzione A): qui solo i bordi paralleli (il frontale da stereo grezza dava falsi dal rumore in alto/centro)
                q = sel & (Zp <= zl)
                if q.sum() < 5: continue
                P = np.stack([Zp[q], Xp[q]], 1); Hq = Hp[q]; rel = P[:, 1] - np.interp(P[:, 0], pzh, pxh); bz = (P[:, 0] / 0.5).astype(int)
                for side, sm in (("L", rel < 0), ("R", rel >= 0)):
                    for b_ in np.unique(bz[sm]):
                        mb = sm & (bz == b_)
                        if mb.sum() < 5: continue
                        sep = float(np.percentile(np.abs(rel[mb]), 10)); xb = float(np.interp((b_ + .5) * .5, pzh, pxh) + (-sep if side == "L" else sep))
                        out[side]["bh"][hyp].append(((b_ + 0.5) * 0.5, xb, sep - HW, isp, float(np.percentile(Hq[mb], 90)), float(np.percentile(Hq[mb], 5))))
    for side in ("L", "R"):
        out[side]["bins"] = sum((chain_filter(b) for b in out[side]["bh"][:len(hyps)]), [])
        bs = out[side]["bins"]; pb = [b for b in bs if b[3]]
        if pb: out[side]["clear"] = min(b[2] for b in pb)
        vi = [b for b in bs if (b[2] < mg if b[3] else b[2] < 0.0) and b[0] <= SOG.a(v)["rallenta_entro_m"] and b[5] <= BASE_MAX_M]      # v11: allarme solo entro rallenta_entro lungo il percorso E con base a terra MISURATA (quota del 5 percentile della fascia <= 0.5 m: un muro tocca terra; striscia piatta/muro senza punti bassi no)
        if vi: bz_ = min(vi, key=lambda b: b[0]); out[side]["viol"] = (bz_[0], bz_[2], "bordo" if bz_[3] else "muro davanti")
    return out


LAT_GAP_TOL = 0.10     # v11: tolleranza (errore laterale stereo a 2-4 m ~0.1 m) per dire che un oggetto interseca la sagoma


def blob_footprint(poly, zf, gp, hp, k):
    """v11: impronta dei punti di una maschera sul percorso (Z,X, quota da piano strada, 0.15<=h<=2.0): ext/elong/angolo (PCA, come i bordi), estensione lungo Z (5-95 percentile),
    intervallo laterale (5-95 percentile) rispetto al centro del percorso e spazio libero dalla sagoma gap = max(lo - HW, -HW - hi) (<0 = interseca), quota minima (5 percentile).
    None se meno di 12 punti validi."""
    if zf is None or gp is None or poly is None or len(poly) < 3: return None
    ga, gvh, gb = gp; m = _fill([poly]); vs, us = np.nonzero(m & (zf != 255) & (zf < 250) & (zf >= 3))
    if len(vs) < 12: return None
    Z = zf[vs, us].astype(np.float32) / 10.0; X = ((us * 4 + 2.0) - CX) * Z / F_PX
    d = F_PX * B_M / Z; h = hp * (1 - ga * ((vs * 4 + 2.0) - gvh) / d); s = (h >= 0.15) & (h <= 2.0)
    if s.sum() < 12: return None
    Z, X, h = Z[s].astype(np.float64), X[s].astype(np.float64), h[s]
    lo, hi = np.percentile(Z, (10, 90)); q = (Z >= lo) & (Z <= hi)
    ext, el, ang, _ = pca_dir(np.stack([Z[q], X[q]], 1), k, either=True) if q.sum() >= N_MIN else (0.0, 0.0, 90.0, False)
    pz, px = path_xz(k); rel = X - np.interp(Z, pz, px); rlo, rhi = np.percentile(rel, (5, 95))
    return dict(n=int(s.sum()), ext=float(ext), el=float(el), ang=float(ang), zspan=float(np.percentile(Z, 95) - np.percentile(Z, 5)), rlo=float(rlo), rhi=float(rhi),
                gap=float(max(rlo - HW, -HW - rhi)), gap_s=float(max(np.percentile(X, 5) - HW, -HW - np.percentile(X, 95))), h5=float(np.percentile(h, 5)), zmed=float(np.median(Z)))


def wall_components(zf, gp, lab, cls_polys, k, hp):
    """v11: un blob e' una FETTA a profondita' costante di un muro (la sua impronta non e' allungata): per sapere se e' un muro parallelo si guarda l'INTERA componente connessa di pixel
    'edificio/muro' (stuff Mapillary) con Z valida e quota 0.2-2.0 m, esclusi persone/veicoli/paletti. PCA della componente (Z,X) con lo stesso criterio dei bordi (estensione >= 1.5 m,
    allungamento >= 2, angolo col percorso <= 35 gradi). Ritorna (mappa componenti 200x320 int32, {id: dict(par, ext, el, ang, n)}) oppure (None, {})."""
    if zf is None or gp is None or lab is None: return None, {}
    ga, gvh, gb = gp; valid = consistent(zf); Z = zf.astype(np.float32) / 10.0
    uu = (np.arange(320) * 4 + 2.0)[None, :]; vv = (np.arange(200) * 4 + 2.0)[:, None]
    with np.errstate(all="ignore"):
        d = F_PX * B_M / np.where(valid, Z, 1.0); h = hp * (1 - ga * (vv - gvh) / d)
    wall = np.isin(lab, CL_WALL) & ~_fill(cls_polys)
    cn, cl = cv2.connectedComponents(wall.astype(np.uint8), connectivity=8)
    X = (uu - CX) * Z / F_PX; out = {}
    for i in range(1, cn):
        m = (cl == i) & valid & (h >= 0.2) & (h <= 2.0) & (Z >= ZMIN_B) & (Z <= 15.0)
        if m.sum() < 60: continue
        P = np.stack([Z[m], X[m]], 1).astype(np.float64); lo, hi = np.percentile(P[:, 0], (5, 95)); P = P[(P[:, 0] >= lo) & (P[:, 0] <= hi)]
        ext, el, ang, par = pca_dir(P, k, either=True); out[i] = dict(par=bool(par), ext=float(ext), el=float(el), ang=float(ang), n=int(m.sum()))
    return cl, out
