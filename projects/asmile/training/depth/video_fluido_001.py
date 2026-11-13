#!/usr/bin/env python3
"""video_fluido_001.py — STADIO B del video fluido v6 (12/11/2026), SOLO #001. Legge le misure per fotogramma di depth_fluido_a_001.py (regole v5),
fa tracking per oggetto con ID stabili (Hungarian su IoU di box con moto costante del centro: 'ByteTrack-lite', un solo stadio), filtra la distanza per traccia
con un Kalman a stato [Z, w] (w = velocita' propria dell'oggetto lungo l'asse; Z' = Z - (v_enc - w) dt: coerente con la velocita' encoder), definisce il
corridoio come ARCO (curvatura da ego_001: giroscopio + encoder) e disegna: maschere tinte col colore della distanza (scala fissa 0-20 m), contorno per famiglia,
etichette solo su oggetti nel corridoio o a <8 m, banner primo ostacolo + TTC, barra con t, velocita', sterzo, curvatura.
Uso: video_fluido_001.py SESSIONE [--jpg f1,f2] [--stats-only]
"""
import os, sys, json, pickle, subprocess, argparse, csv
import numpy as np, cv2
from scipy.optimize import linear_sum_assignment
import depth_seg_001 as D
import bordi_001 as BD
from ego_001 import Ego, x_path, x_arc, CENTER, DEG_STEP
sys.path.insert(0, os.path.join(D.HERE, "..", "..", "pi", "autonomous"))
from corridoio import Corridoio, VelRuota     # corridoio UNICO bordo/Mac (2026-11-13): largo come la bici, curvatura causale da sterzo+giroscopio+velocita'
CAL_0911 = {"unit": "asmile-001", "encoder_center_raw": CENTER, "deg_per_step": DEG_STEP, "encoder_pos_increases_to": "DX (destra)", "encoder_bits": 14, "delta_dx_deg": 45.0, "delta_sx_deg": -45.0}   # calib sterzo dei video del 09/11 (centro 6606)
CORRIDOIO = Corridoio("asmile-001", calib=CAL_0911)   # solo per il disegno del percorso (k imposto), la calib dello sterzo conta in k_causale


def corr_path(k):
    """percorso del corridoio (z, x) per la curvatura k, fino a 45 m (per il disegno e la classificazione), dal modulo corridoio"""
    CORRIDOIO.k = float(k); CORRIDOIO.psi0 = 0.0; CORRIDOIO.x0 = 0.0; CORRIDOIO._cache = None
    return CORRIDOIO.percorso(45.0)


def k_causale(ego):
    """curvatura CAUSALE del corridoio sull'intera sessione (stessi ingressi che avra' lo shadow mode: sterzo grezzo, velocita', gz); salva in ego.k_c e ego.corr_log (sorgenti, orizzonte, sigma)"""
    c = Corridoio("asmile-001", calib=CAL_0911 if ego.center == CENTER else None); K = np.empty(len(ego.t)); LOG = []    # 13/11: calib sterzo attuale (centro 4112) dal json dell'unita'
    gz = ego.bias - ego.yaw_dx; raw = np.rint(ego.center + ego.steer / DEG_STEP)
    vr = VelRuota(1.0)      # velocita' CAUSALE del modulo (differenza all'indietro 0.2 s sull'odometria in m), non quella centrata +-0.25 s di ego.v
    for i in range(len(ego.t)):
        c.update(ego.t[i] / 1000.0, raw[i], vr.update(ego.t[i] / 1000.0, float(ego.s[i])), gz[i]); K[i] = c.k
    ego.k_c = K
    return K

W, H, BAR = 1280, 800, 100
MODE = os.environ.get("VFMODE", "v14")          # "v6"/"v7" = regole dei giri 6/7 (per il prima/dopo), "v8" = v7 + correzioni bug del giro 8
V7 = MODE in ("v7", "v8", "v9", "v10", "v11", "v12", "v13", "v14")
V8 = MODE in ("v8", "v9", "v10", "v11", "v12", "v13", "v14")
V10 = MODE in ("v10", "v11", "v12", "v13", "v14")     # giro 10: H_ALTO 2.0 m (Daniele: da terra a 2 m e' ostacolo anche sospeso) + BORDI (muri/cordoli/marciapiede paralleli: allarme di distanza laterale, non primo ostacolo)
V9 = MODE in ("v9", "v10", "v11", "v12", "v13", "v14")       # giro 9: quota da terra misurata sui pixel bassi/alti della MASCHERA (zmap), non sul box; esclude solo cio' che sta tutto sopra H_ALTO o sotto il piano
V12 = MODE in ("v12", "v13", "v14")
V14 = MODE == "v14"     # giro 3 (13/11): salti di Z >3 m non agiscono (conferma 3 fotogrammi), STERZA solo verso lato MISURATO libero, maschere non sulla sagoma/troppo piccole non agiscono, NON MISURATO con tessitura
V13 = MODE in ("v13", "v14")     # giro 13/11 (VETO 1/3 giri): Z = Z della maschera coerente con le dimensioni note, FRENA solo con maschera sulla sagoma e non in coast, maschere dentro veicolo escluse, stato NON MISURATO, orari da sensori     # giro 12: (a) laterali grandi/edificio 'altro'/blob |X|>0.8 solo bordo, mai FRENA; (b) blob STRETTI (<=1.0 m) dentro la sagoma non sono bordo; (c) oggetto vero sul percorso: STERZA se c'e' spazio libero dall'altro lato, altrimenti FRENA
V11 = MODE in ("v11", "v12", "v13", "v14")     # giro 11: blob/altro LATERALI o paralleli declassati a bordo prima del primo ostacolo; STERZA solo con bordo entro margine+rallenta_entro+base misurata; FRENA/RALLENTA solo se tocca terra nel corridoio o la sagoma 0-2 m interseca la bici; FRENA <2 m con Z coerente (encoder) salvo persone
PURE = os.environ.get("VF_PURE", "1") == "1"      # v7: terza ipotesi = arco a curvatura costante (il percorso reale in curva stretta si avvolge piu' del previsto)
EXTRA = float(os.environ.get("VF_EXTRA", "0.0"))   # allargamento aggiuntivo del corridoio per m di distanza (m/m), 0 = nessuno
OUT_A = os.environ.get("VF_OUT_A", os.path.join(D.HERE, "out_20261112_v6"))  # stadio A (misure per fotogramma) INVARIATO: riletto da v6
OUT = os.environ.get("VF_OUT", os.path.join(D.HERE, "out_20261113_giri_v3" if V14 else "out_20261113_giri_v2" if V13 else "out_20261112_v12" if V12 else ("out_20261112_v11" if V11 else ("out_20261112_v10" if V10 else "out_20261112_v9"))))
os.makedirs(OUT, exist_ok=True)
Z_JUMP, Z_COH, Z_CONF = 3.0, 1.5, 3   # giro 3 punto 1 (fissate PRIMA): salto > 3.0 m, misure coerenti se adiacenti entro 1.5 m (2.5 sigma stereo a 16 m), conferma 3 misure
Z_RAW_GAP, Z_RAW_MAXZ = 0.7, 8.0   # v7 punto 3: se Z_filtrata - Z_grezza > 0.7 m sotto 8 m si usa la grezza (vince la piu' vicina)
HITS_BLOB_NEAR, ZNEAR_BLOB = 3, 5.0  # v7 punto 1: sotto 5 m un blob senza classe conferma a 3 fotogrammi come gli altri
SAM_DIR = os.path.join(D.HERE, "..", "..", "asmile-loggers", "_seg_sam3")
FAMCOL = {"veicolo": (255, 144, 30), "persona": (64, 64, 255), "bici-moto": (255, 60, 180), "paletto-palo": (0, 215, 255),
          "barriera-cancello": (200, 200, 0), "altro": (170, 170, 170), "ostacolo": (0, 140, 255), "bordo": (0, 0, 255)}
FAMNAME = {"veicolo": "veicolo", "persona": "persona", "bici-moto": "bici/moto", "paletto-palo": "paletto", "barriera-cancello": "barriera", "altro": "altro", "ostacolo": "ostacolo", "bordo": "bordo"}
FAMCLASS = {"car": "veicolo", "van": "veicolo", "truck": "veicolo", "bus": "veicolo", "tractor": "veicolo", "person": "persona", "child": "persona", "stroller": "persona",
            "wheelchair": "persona", "bicycle": "bici-moto", "motorcycle": "bici-moto", "pole": "paletto-palo", "bollard": "paletto-palo", "traffic cone": "paletto-palo",
            "barrier": "barriera-cancello", "fence": "barriera-cancello", "gate": "barriera-cancello", "ostacolo": "ostacolo"}
STATIC = {"paletto-palo", "barriera-cancello", "ostacolo", "altro"}
CORR = (255, 255, 255)
F_PX, B_M = 1379.8882680918412, 0.19656132417315123
CONFIRM, MAXMISS = 3, 8
COAST = 4            # un oggetto confermato non visto per <=4 fotogrammi (0.27 s) resta candidato 'primo ostacolo' con la Z predetta dal Kalman (niente maschera disegnata)
HITS_BLOB = 8        # un ostacolo senza classe (blob) deve durare >=8 fotogrammi (0.53 s) per contare/comparire
ZMAX_SCALE = 20.0
TURBO = cv2.applyColorMap(np.arange(256, dtype=np.uint8).reshape(-1, 1), cv2.COLORMAP_TURBO).reshape(256, 3)


def zcol(Z):
    return tuple(int(c) for c in TURBO[int(255 * (1 - min(max(Z, 0.0), ZMAX_SCALE) / ZMAX_SCALE))])


def wband(Z): return CORRIDOIO.hw      # corridoio largo come la bici (1.10 m dalla tabella); l'incertezza della previsione e' a parte (CORRIDOIO.incertezza)


def corr_edges(xc, Z):
    """bordi laterali del corridoio disegnato: v6 = banda attorno al percorso curvo; v7 = inviluppo delle due ipotesi (percorso curvo e dritto)"""
    return xc - wband(Z), xc + wband(Z)   # corridoio = sagoma della bici sul percorso causale (niente inviluppo con la dritta, niente bande larghe);  # (l'arco puro, terza ipotesi, vale per la classificazione degli oggetti; il disegno mostra l'inviluppo dritto/decrescente)


def need_hits(r):
    """fotogrammi richiesti perche' un oggetto conti come candidato/si disegni: blob 8 (v6); in v7 sotto 5 m anche i blob 3"""
    if r["src"] != "blob": return CONFIRM
    if V7 and r["Z"] < ZNEAR_BLOB: return HITS_BLOB_NEAR
    return HITS_BLOB


def inside_frac(b):
    """frazione dell'area del box dentro l'immagine rettificata W x H"""
    a = max(1e-9, (b[2] - b[0]) * (b[3] - b[1]))
    return max(0, min(b[2], W) - max(b[0], 0)) * max(0, min(b[3], H) - max(b[1], 0)) / a


MIN_INSIDE = 0.5      # v8: un box con meno del 50% dentro l'immagine non puo' essere primo ostacolo
H_BASE_MIN, Z_BASE_MAX = 0.25, 5.0   # v8: base a meno di 0.25 m dal piano strada (come hmin delle versioni 2/3); regola solo sotto 5 m
BASE_EXEMPT = ("persona", "veicolo")
# v9: quota da terra. H_ALTO = altezza massima di cio' che la bici+passeggero seduto puo' colpire: manubrio ~1.0 m, testa del passeggero seduto ~1.4 m (dichiarata, non misurata su Asmile).
# Si esclude solo un oggetto con la base (pixel bassi della maschera) sopra H_ALTO, o con tutta la maschera entro H_SOTTO dal piano (ombre/macchie).
H_ALTO, H_SOTTO = (BD.SOG.p["altezza_max_ostacolo_m"] if V10 else 1.4), 0.10   # v10: dalla tabella soglie (2.0 m, Daniele 2026-11-12, sostituisce la stima 1.4 m)
V9_EXEMPT = ("persona", "veicolo", "bici-moto", "paletto-palo")   # mai esclusi dalla quota
HP = D.CAM_H * np.cos(D.PITCH)


def mask_heights(poly, zm_f, gp):
    """(h_basso, h_alto) in m sul piano strada: mediana delle quote dei pixel validi nel 20% di righe piu' basso / piu' alto della MASCHERA (zmap 320x200, 4x), ognuno con la propria Z:
    h = HP (1 - dg/d), d = F B / Z_pixel, dg = disparita' del piano alla riga. None se mancano dati o piano."""
    if zm_f is None or gp is None or poly is None or len(poly) < 3: return None
    ga, gvh, gb = gp
    m = np.zeros(zm_f.shape, np.uint8); cv2.fillPoly(m, [(np.asarray(poly, np.float32) / 4.0).astype(np.int32)], 1)
    rows = np.nonzero(m.any(1))[0]
    if len(rows) == 0: return None
    y0, y1 = rows[0], rows[-1]; band = max(2, int(0.2 * (y1 - y0 + 1)))
    out = []
    for lo, hi in ((y1 - band + 1, y1), (y0, y0 + band - 1)):
        sel = np.zeros_like(m, bool); sel[lo:hi + 1] = True; sel &= m > 0; sel &= (zm_f != 255) & (zm_f < 250) & (zm_f >= 3)
        vs, us = np.nonzero(sel)
        if len(vs) < 6: return None
        Zp = zm_f[vs, us].astype(np.float32) / 10.0; d = F_PX * B_M / Zp; dg = ga * ((vs + 0.5) * 4.0 - gvh)
        out.append(float(np.median(HP * (1 - dg / d))))
    return tuple(out)


def base_height(r, gp):
    """altezza (m) sul piano strada del punto piu' basso del box alla distanza misurata Z: h = CAM_H (d - d_g)/d, d = F B / Z, d_g = disparita' della strada nella riga y1 del box
    (stessa formula di depth_seg_001.obstacles). None se la base non e' visibile (box tagliato dal bordo basso) o se non c'e' piano."""
    if gp is None: return None
    b = r["box"]
    if b[3] >= H - 6: return None
    ga, gvh, gb = gp
    d = F_PX * B_M / max(r["Z"], 0.3); dg = ga * (b[3] - gvh)
    if dg <= 0: return D.CAM_H
    return float(D.CAM_H * (d - dg) / d)


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    return i / max(1e-9, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)


# giro 13/11 v13: dimensioni FISICHE note per classe (m): (estensione max visibile min, max, tipica) = max(larghezza, altezza) della maschera alla Z misurata.
# Se la Z misurata dà un'estensione impossibile per la classe (persona alta 0.15 m, auto larga 0.2 m, bidone 0.16 m) la Z non e' quella dell'oggetto: si usa la Z da dimensione (tipica/estensione in px, +-50%, segnata 'Zdim').
SIZE_M = {"person": (0.45, 2.2, 1.5), "child": (0.3, 1.6, 1.1), "stroller": (0.4, 1.6, 1.0), "wheelchair": (0.5, 1.6, 1.1), "car": (1.0, 6.0, 2.2), "van": (1.0, 7.5, 2.5), "truck": (1.2, 14.0, 3.0),
          "bus": (1.5, 14.0, 6.0), "tractor": (1.0, 8.0, 3.0), "bicycle": (0.5, 2.4, 1.3), "motorcycle": (0.6, 2.8, 1.6), "trash can": (0.35, 1.8, 0.9), "bench": (0.4, 2.8, 1.2),
          "traffic cone": (0.15, 1.0, 0.6), "pole": (0.25, 1e9, 1.5), "bollard": (0.25, 1.5, 0.8)}
SIZE_LEAK = 1.3     # la maschera puo' sbordare di un 30% oltre la dimensione massima
FPICCO_MIN = 0.30   # il picco (cluster piu' vicino) e' la Z della maschera solo se contiene >=30% dei pixel validi, altrimenti la mediana


def mask_z(o):
    """Z della maschera: picco se dominante (frac_picco>=0.30), altrimenti mediana dei pixel validi; poi controllo di coerenza con le dimensioni note della classe. Ritorna (Z, flag)."""
    if o["src"] == "blob" or not V13: return o["Z_picco"], ""
    Z = o["Z_picco"] if o.get("frac_picco", 1.0) >= FPICCO_MIN else o["Z_med"]
    sz = SIZE_M.get(o["classe"])
    if sz is None: return Z, ""
    b = o["box"]; w = b[2] - b[0]; h = b[3] - b[1]; ext = max(w, h)
    trunc = b[0] <= 2 or b[1] <= 2 or b[2] >= W - 2 or b[3] >= H - 2      # box tagliato dal bordo: la estensione e' per difetto, niente controllo del minimo
    em = ext * Z / F_PX
    if em > sz[1] * SIZE_LEAK or (em < sz[0] and not trunc): return float(F_PX * sz[2] / max(ext, 1)), "dim"
    return Z, ""


def fam_obj(o, famv2, frame):
    if o["src"] == "blob": return "ostacolo"
    if o["src"] == "sam":
        f = famv2.get((frame, o["sam_idx"]))
        if f and f not in ("unknown", "altro"): return f
    return FAMCLASS.get(o["classe"], "altro")


class Track:
    nid = 0

    def __init__(s, o, fam, Z, t):
        Track.nid += 1; s.id = Track.nid; s.src = o["src"]; s.fam = fam; s.fams = [fam]; s.classe = o["classe"]
        s.box = list(o["box"]); s.cen = np.array([(o["box"][0] + o["box"][2]) / 2, (o["box"][1] + o["box"][3]) / 2]); s.vel = np.zeros(2)
        s.hits = 1; s.miss = 0; s.born = t; s.zs = [Z]
        s.stat = fam in STATIC
        sa = 0.3 if s.stat else 1.0
        s.sa = sa; s.x = np.array([Z, 0.0]); sg = s.sig(Z); s.P = np.diag([sg ** 2, (0.3 if s.stat else 1.0) ** 2])
        s.out = 0; s.tan = o["X"] / max(o["Z_picco"], 0.1); s.decl = [bool(o["declassato"])]; s.sosp = [bool(o["sospetto"])]
        s.in_arc = False; s.in_str = False; s.lastfirst = False; s.lab_xy = None; s.o = o; s.Zraw = [o["Z_picco"]]; s.t_obs = [t]; s.Zf = [Z]; s.s_obs = []; s.hb = []; s.ht = []; s.bd = []; s.fp = []; s.wb = []; s.bpar = []

    @staticmethod
    def sig(Z): return float(np.hypot(0.03 * Z, Z * Z * 0.4 / (F_PX * B_M)))

    def box_now(s):
        """box nella posizione corrente del centro (tr.cen e' gia' stato avanzato di vel+rot a ogni fotogramma perso): v8 usa questo, NON un ulteriore passo di vel"""
        w = s.box[2] - s.box[0]; h = s.box[3] - s.box[1]
        return [s.cen[0] - w / 2, s.cen[1] - h / 2, s.cen[0] + w / 2, s.cen[1] + h / 2]

    def pred_box(s, rot=0.0):
        c = s.cen + s.vel + np.array([rot, 0.0]); w = s.box[2] - s.box[0]; h = s.box[3] - s.box[1]
        return [c[0] - w / 2, c[1] - h / 2, c[0] + w / 2, c[1] + h / 2]

    def predict(s, dt, v):
        F = np.array([[1, dt], [0, 1]]); s.x = F @ s.x; s.x[0] -= v * dt
        Q = s.sa ** 2 * np.array([[dt ** 3 / 3, dt ** 2 / 2], [dt ** 2 / 2, dt]]); Q[0, 0] += 0.02 * dt
        s.P = F @ s.P @ F.T + Q; s.x[0] = max(s.x[0], 0.3)

    def update(s, z):
        r = s.sig(z) ** 2; S = s.P[0, 0] + r; y = z - s.x[0]
        if y * y / S > 9.0:           # outlier a 3 sigma: nessun aggiornamento (la predizione dell'encoder regge)
            s.out += 1
            if s.out >= 4: s.x = np.array([z, 0.0]); s.P = np.diag([r, 1.0]); s.out = 0
            return False
        K = s.P[:, 0] / S; s.x = s.x + K * y; s.P = s.P - np.outer(K, s.P[0]); s.out = 0
        return True


def load_famv2(sess):
    fn = os.path.join(SAM_DIR, sess + "_001_fluido_v2", "index.jsonl"); m = {}
    if not os.path.exists(fn): return m
    for l in open(fn):
        r = json.loads(l)
        for d in r["detections"]:
            m[(r["frame"], d["idx"])] = d["family"]
            for a in d.get("alternatives", []): m[(r["frame"], a["idx"])] = d["family"]
    return m


def run_tracking(frames, ego, famv2):
    Track.nid = 0; tracks = []; per = []; prev_t = None
    for fr in frames:
        t = fr["t_ms"]; v = float(ego.at(t, "v_s")); dt = 1 / 15 if prev_t is None else (t - prev_t) / 1000.0; prev_t = t
        rot = -F_PX * np.radians(float(ego.at(t, "yaw_s"))) * dt     # spostamento orizzontale dell'immagine dovuto alla rotazione della bici (imbardata a destra -> scena a sinistra)
        for tr in tracks: tr.predict(dt, v)
        if V13:
            for o in fr["objs"]:
                if "Z_picco0" in o: continue
                o["Z_picco0"] = o["Z_picco"]; Zn, fl = mask_z(o)
                if o["src"] != "blob" and Zn != o["Z_picco"]: o["X"] = o["X"] * Zn / max(o["Z_picco"], 0.1)      # stessa direzione (tan) alla nuova Z
                o["Z_picco"] = Zn; o["Zdim"] = fl == "dim"
        obs = [o for o in fr["objs"] if o["Z_picco"] <= 60]
        fams = [fam_obj(o, famv2, fr["frame"]) for o in obs]
        C = np.full((len(tracks), len(obs)), 1e6)
        for a, tr in enumerate(tracks):
            pb = tr.pred_box(rot)
            for b, (o, f) in enumerate(zip(obs, fams)):
                if (tr.src == "blob") != (o["src"] == "blob"): continue
                if tr.fam != f and not (tr.src == "blob"): continue
                sc = iou(pb, o["box"])
                if sc < 0.05: continue
                if tr.hits >= CONFIRM and abs(np.log(max(o["Z_picco"], .3) / max(tr.x[0], .3))) > 0.45: continue
                C[a, b] = 1 - sc
        ma, mb = set(), set()
        if C.size:
            ri, ci = linear_sum_assignment(C)
            for a, b in zip(ri, ci):
                if C[a, b] < 0.95: ma.add(a); mb.add(b); tr = tracks[a]; o = obs[b]
                else: continue
                nb = o["box"]; nc = np.array([(nb[0] + nb[2]) / 2, (nb[1] + nb[3]) / 2])
                tr.vel = 0.5 * tr.vel + 0.5 * (nc - tr.cen - np.array([rot, 0.0])); tr.cen = nc; tr.box = list(nb)
                xpred_ = float(tr.x[0]); tr.update(o["Z_picco"]); tr.hits += 1; tr.miss = 0; tr.o = o; tr.fams.append(fams[b]); tr.decl.append(bool(o["declassato"])); tr.sosp.append(bool(o["sospetto"]))
                tr.tan = 0.6 * tr.tan + 0.4 * o["X"] / max(o["Z_picco"], 0.1); tr.Zraw.append(o["Z_picco"]); tr.t_obs.append(t); tr.Zf.append(float(tr.x[0])); tr.s_obs.append(float(ego.at(t, "s")))
                tr.classe = o["classe"]
                if V14:
                    # giro 3 punto 1: salto di Z fra due misure consecutive della traccia (riportate a oggi con l'encoder) > Z_JUMP => la traccia ha cambiato oggetto/misura: nessuna azione finche' non ci sono >= Z_CONF misure coerenti (differenze adiacenti <= Z_COH)
                    zr_, sr_ = tr.Zraw, tr.s_obs
                    if (len(zr_) >= 2 and len(sr_) >= 2 and abs(zr_[-1] - (zr_[-2] - (sr_[-1] - sr_[-2]))) > Z_JUMP) or (tr.hits >= CONFIRM + 2 and abs(zr_[-1] - xpred_) > Z_JUMP): tr.zpend = True; tr.njump = getattr(tr, "njump", 0) + 1      # salto fra misure consecutive OPPURE misura lontana >3 m dalla previsione del filtro (storia+encoder) di una traccia gia' stabile
                    run_ = 1
                    for j_ in range(len(zr_) - 1, 0, -1):
                        if j_ < len(sr_) and abs(zr_[j_] - (zr_[j_ - 1] - (sr_[j_] - sr_[j_ - 1]))) <= Z_COH: run_ += 1
                        else: break
                    tr.zrun = run_
                    if run_ >= Z_CONF: tr.zpend = False
        for a, tr in enumerate(tracks):
            if a not in ma: tr.miss += 1; tr.cen = tr.cen + tr.vel + np.array([rot, 0.0])
        for b, (o, f) in enumerate(zip(obs, fams)):
            if b not in mb:
                tracks.append(Track(o, f, o["Z_picco"], t)); tracks[-1].s_obs.append(float(ego.at(t, "s")))
                if V14:   # la traccia nuova nasce sopra un oggetto gia' tracciato (stesso box, famiglia) ma con Z incompatibile (il gate Z della vecchia l'ha rifiutata): e' lo stesso oggetto con una misura sospetta -> eredita 'da confermare'
                    for a_, tp_ in enumerate(tracks[:-1]):
                        if a_ in ma or tp_.hits < CONFIRM or tp_.fam != f or (tp_.src == "blob") != (o["src"] == "blob"): continue
                        if iou(tp_.box_now(), o["box"]) > 0.5 and abs(np.log(max(o["Z_picco"], .3) / max(tp_.x[0], .3))) > 0.30: tracks[-1].zpend = True; break
        tracks = [tr for tr in tracks if tr.miss <= (MAXMISS if tr.hits >= CONFIRM else 2)]
        rows = []
        for tr in tracks:
            if tr.hits >= CONFIRM and (tr.miss <= COAST):
                tr.fam = max(set(tr.fams[-15:]), key=tr.fams[-15:].count)
                pb = ([int(v) for v in (tr.box_now() if V8 else tr.pred_box(0.0))]) if tr.miss else list(tr.o["box"])
                zf = float(tr.x[0]); zr = float(tr.o["Z_picco"]); zu = zf
                if V7 and not tr.miss and zf - zr > Z_RAW_GAP and zf < Z_RAW_MAXZ: zu = zr    # punto 3: il filtro non allontana: vince la grezza (piu' vicina)
                if V13:
                    # Z scritta = Z della MASCHERA di questa traccia: se il filtro se ne allontana (>0.5 m e >15%) vince la misura della maschera; in coast (nessuna maschera ora) = ultima Z della maschera - strada percorsa dall'encoder
                    if not tr.miss:
                        if abs(zf - zr) > max(0.5, 0.15 * zr): zu = zr
                    else: zu = max(0.3, float(tr.Zraw[-1]) - (float(ego.at(t, "s")) - tr.s_obs[-1])) if tr.s_obs else zf
                rows.append(dict(inside=inside_frac(pb), id=tr.id, fam=tr.fam, src=tr.src, classe=tr.classe, Z=zu, Zf=zf, rawfix=zu != zf, w=float(tr.x[1]), Zraw=float(tr.o["Z_picco"]), tan=float(tr.tan), box=pb, poly=None if tr.miss else tr.o["poly"],
                                 decl=bool(np.mean(tr.decl[-8:]) > 0.5), sosp=bool(np.mean(tr.sosp[-8:]) > 0.5), ext=tr.o.get("ext", False), hits=tr.hits, coast=tr.miss > 0, Zdim=bool(tr.o.get('Zdim', False)) and not tr.miss, zpend=bool(getattr(tr, "zpend", False)), track=tr))
        per.append(rows)
    return per


TINY_M = 0.15
NARROW_W, LATW_BIG, LATW_X, LATW_WALL = 0.4, 0.40, 0.8, 0.5    # giro 12: larghezza max blob "stretto" (m); frazione immagine "grande"; |X| laterale (m); frazione pixel edificio/muro
SHIFT_MAX = 1.0      # giro 12: STERZA attorno a un oggetto solo se lo spostamento laterale necessario e' <= 1.0 m
Z_COERENZA = 2.0     # v11: sotto 2 m FRENA richiede Z coerente (salvo persone)


def z_coerente(tr, tol=0.35):
    """v11: gli ultimi 3 fotogrammi MISURATI (non predetti) dell'oggetto, riportati a oggi con lo spostamento encoder (Zraw_i - (s_ora - s_i)), devono stare entro 0.35 m (errore stereo a 1-2 m ~ 0.05 m + encoder):
    un oggetto fermo che si avvicina con la velocita' della bici e' coerente; un salto di Z (facciata lontana con profondita' sbagliata) no. Meno di 3 misure = non coerente."""
    n = min(len(tr.Zraw), len(tr.s_obs))
    if n < 3: return False
    Z3 = tr.Zraw[-3:]; s3 = tr.s_obs[-3:]; adj = [z - (s3[-1] - si) for z, si in zip(Z3, s3)]
    return bool(max(adj) - min(adj) <= tol)


def lat_gaps(r, pz, px, use_fp=True):
    """v11: spazio libero laterale (m, <0 = interseca) fra l'oggetto e la sagoma della bici, per l'arco e per il percorso dritto. Impronta dei punti se c'e', altrimenti estremi laterali di maschera/box alla Z misurata."""
    fp = None
    tr = r.get("track")
    if tr is not None and use_fp and not r.get("coast"): fp = next((x for x in reversed(tr.fp[-3:]) if x is not None), None)
    if fp is not None: return fp["gap"], fp["gap_s"]
    if r.get("poly") is not None and len(r["poly"]) >= 3: xs = np.asarray(r["poly"], np.float32)[:, 0]; x0, x1 = float(xs.min()), float(xs.max())
    else: x0, x1 = float(r["box"][0]), float(r["box"][2])
    x0, x1 = max(x0, 0.0), min(x1, float(W)); Z = r["Z"]
    Xl, Xr = (x0 - BD.CX) * Z / F_PX, (x1 - BD.CX) * Z / F_PX; xa = float(np.interp(Z, pz, px))
    return max(Xl - xa - BD.HW, xa - Xr - BD.HW), max(Xl - BD.HW, -BD.HW - Xr)


NM_VALID, NM_SAT = 0.15, 0.25     # v13 punto 3 (fissate PRIMA): quota di depth valida sulla strada nel corridoio < 0.15 oppure > 25% di pixel saturi (>=250) nel corridoio => NON MISURATO
IV_FRAC, IV_DZ = 0.7, 1.0         # v13 punto 2: >=70% della maschera dentro la maschera di un veicolo e Z non piu' vicina di 1.0 m al veicolo => e' dentro il veicolo (finestrino), non ostacolo separato
NMDBG = {}
TEX_G, TEX_CELL = 8.0, 0.25
TEXQ = {}
NM_TEX_MIN, NM_VT, NM_VALID_FLOOR = 0.08, 0.35, 0.05      # giro 3 punto 4 (fissate PRIMA di guardare i risultati): tessitura nel corridoio >= 8% e valid/tessitura < 0.35 => la stereo doveva misurare e non l'ha fatto => NON MISURATO; tessitura < 8% (strada liscia): NON MISURATO solo se la depth valida e' < 5% (niente da misurare)
SATQ = {}                         # fotogramma -> immagine rettificata 320x200 (per la quota di saturazione), riempita da main


def corr_poly_full(k, gp, zmax=30.0):
    ga, gvh, gb = gp; Zs = np.geomspace(1.8, zmax, 40); pz, px = corr_path(k); Lp, Rp = [], []
    for Z in Zs:
        xc = float(np.interp(Z, pz, px)); d = F_PX * B_M / Z; lo, hi = corr_edges(xc, Z)
        for X, o in ((lo, Lp), (hi, Rp)):
            u = 660.142 + X * F_PX / Z; o.append((u, gvh + (d - gb * (u - 660.142)) / ga))
    return np.array(Lp + Rp[::-1], np.float32)


def nonmis(fr, k, gp, zf_, zmax):
    """(quota_valida, quota_satura, nonmisurato) nel poligono del corridoio proiettato sulla strada"""
    if gp is None or zf_ is None: return None, None, True
    m = np.zeros(zf_.shape, np.uint8); cv2.fillPoly(m, [(corr_poly_full(k, gp, zmax) / 4.0).astype(np.int32)], 1); n = int(m.sum())
    if n < 50: return None, None, True
    vq = float(((zf_ != 255) & (zf_ < 250) & (zf_ >= 3))[m > 0].mean()); sq = None
    sm = SATQ.get(fr["frame"]); tq = None
    if sm is not None:
        sq = float((sm[m > 0] >= 250).mean())
        tmap = TEXQ.get(fr["frame"]); tm = (tmap >= TEX_CELL) & (sm < 250)      # celle 4x4 px (a risoluzione piena) con >= 25% di pixel a gradiente >= TEX_G: ci sono dettagli da abbinare
        tq = float(tm[m > 0].mean()); vt = float((((zf_ != 255) & (zf_ < 250) & (zf_ >= 3)) & tm)[m > 0].sum()) / max(1.0, float(tm[m > 0].sum()))      # fra le celle con tessitura, quante hanno depth valida
        NMDBG[fr["frame"]] = (vq, sq, tq, vt)
    if V14 and sm is not None: nmf = bool(sq > NM_SAT or (tq >= NM_TEX_MIN and vt < NM_VT) or (tq < NM_TEX_MIN and vq < NM_VALID_FLOOR))
    else: nmf = bool(vq < NM_VALID or (sq is not None and sq > NM_SAT))
    return vq, sq, nmf     # (la decisione finale in corridor_logic: saturo => sempre NON MISURATO; poca depth => NON MISURATO solo se nessuna maschera misurata nel corridoio)


def mark_in_vehicle(rows):
    """v13: persona/bici/altro la cui maschera sta dentro la maschera di un veicolo (non coast) alla stessa distanza o dietro = visto dal finestrino"""
    vs = [q for q in rows if q["fam"] == "veicolo" and not q["coast"] and q.get("poly") is not None and len(q["poly"]) >= 3]
    for r in rows:
        r["iv_now"] = False
        if r["fam"] == "veicolo" or r["src"] == "blob" or r["coast"] or r.get("poly") is None or len(r["poly"]) < 3: continue
        m = np.zeros((200, 320), np.uint8); cv2.fillPoly(m, [(np.asarray(r["poly"], np.float32) / 4.0).astype(np.int32)], 1); a = max(1, int(m.sum()))
        for q in vs:
            if q is r or r["Z"] < q["Z"] - IV_DZ: continue
            mv = np.zeros((200, 320), np.uint8); cv2.fillPoly(mv, [(np.asarray(q["poly"], np.float32) / 4.0).astype(np.int32)], 1)
            if (m & mv).sum() / a >= IV_FRAC: r["iv_now"] = True; break
        tr = r["track"]; tr.iv = getattr(tr, "iv", []) + [r["iv_now"]]
    for r in rows:
        tr = r["track"]; h = getattr(tr, "iv", [])[-5:]; r["in_veh"] = bool(h and sum(h) >= (2 if len(h) >= 2 else 1))


def corridor_logic(per, frames, ego, zm=None, stuff=None):
    """per ogni fotogramma: arco (k), appartenenza arco/dritta con isteresi, primo ostacolo (isteresi 0.5 m)"""
    res = []; prev_first = {"arc": None, "str": None}; bhist = {"L": [], "R": []}; bclr = {"L": [], "R": []}
    skeys = np.array(sorted(int(x[1:]) for x in stuff.files)) if stuff is not None else None
    for fi, (fr, rows) in enumerate(zip(frames, per)):
        k = float(ego.at(fr["t_ms"], "k_c")); pz, px = corr_path(k); gpf = smooth_gp(frames, fi) if V8 else None
        zf_ = zm[f"f{fr['frame']}"] if (zm is not None and f"f{fr['frame']}" in zm.files) else None
        wcl, wpar = None, {}; lab0 = None
        if V12 and skeys is not None:
            nk1 = int(skeys[np.argmin(np.abs(skeys - fr["frame"]))])
            if abs(nk1 - fr["frame"]) <= 2: lab0 = stuff[f"f{nk1}"]
        if V11 and skeys is not None and zf_ is not None and gpf is not None:      # v11: componenti muro (stuff) con PCA, per i blob-fette di muro
            nk0 = int(skeys[np.argmin(np.abs(skeys - fr["frame"]))])
            if abs(nk0 - fr["frame"]) <= 2: wcl, wpar = BD.wall_components(zf_, gpf, stuff[f"f{nk0}"], [q["poly"] for q in rows if q["src"] != "blob" and not q["coast"]], k, HP)
        if V13: mark_in_vehicle(rows)
        for r in rows:
            Z = r["Z"]; X = r["tan"] * Z; r["X"] = X
            dx_arc = X - float(np.interp(Z, pz, px)); tr = r["track"]
            lim = (wband(Z) + (EXTRA * Z if V7 else 0.0)) * (1.15 if tr.in_arc else 1.0)
            tr.in_arc = abs(dx_arc) <= lim; r["in_arc"] = tr.in_arc
            r["in_str"] = abs(X) <= wband(Z)
            if V7:   # punto 2: corridoio = unione delle ipotesi (percorso curvo O dritto), ognuna con la sua banda
                lim2 = (wband(Z) + EXTRA * Z) * (1.15 if tr.in_str else 1.0)
                tr.in_str = abs(X) <= lim2
                r["in_arc_pure"] = r["in_arc"]; r["in_arc"] = bool(r["in_arc"] or tr.in_str); r["in_str"] = bool(r["in_str"] or tr.in_str)
                if PURE and not r["in_arc"]:
                    r["in_arc"] = bool(abs(X - float(x_arc(k, Z))) <= wband(Z) + EXTRA * Z)
            r["cand"] = (not r["decl"]) and (not r["sosp"]) and r["hits"] >= need_hits(r)
            r["fuori_img"] = bool(V8 and r["inside"] < MIN_INSIDE)
            if V9:
                tr = r["track"]
                if not r["coast"]:
                    mh = mask_heights(r["poly"], zf_, gpf)
                    if mh is not None: tr.hb.append(mh[0]); tr.ht.append(mh[1])
                hb = float(np.median(tr.hb[-5:])) if tr.hb else None; ht = float(np.median(tr.ht[-5:])) if tr.ht else None
                r["h_base"] = hb; r["h_top"] = ht; r["escl"] = ""
                if hb is not None and r["fam"] not in V9_EXEMPT:
                    if hb > H_ALTO: r["escl"] = "sopra"
                    elif ht < H_SOTTO: r["escl"] = "sotto_piano"
                r["senza_base"] = bool(r["escl"])
            else:
                hb = base_height(r, gpf) if (V8 and r["Z"] < Z_BASE_MAX and r["fam"] not in BASE_EXEMPT) else None
                r["h_base"] = hb; r["senza_base"] = bool(hb is not None and hb >= H_BASE_MIN)
            if V10:
                tr = r["track"]; r["bordo"] = False
                if V11 and r["src"] == "blob":
                    # v11: il blob (o 'altro') e' un BORDO se parallelo al percorso (PCA come i bordi) OPPURE interamente laterale (fuori sagoma + margine: non puo' urtare; se la sua impronta torna a intersecare la sagoma ridiventa ostacolo): voto 3 su 5
                    if not r["coast"]:
                        fp = BD.blob_footprint(r["poly"], zf_, gpf, HP, k); r["fp"] = fp
                        if fp is None: tr.bd.append(None)
                        else:
                            par = fp["ext"] >= BD.EXT_MIN and fp["el"] >= BD.ELONG_MIN and fp["ang"] <= BD.ANG_MAX
                            lat = min(fp["gap"], fp["gap_s"]) >= BD.margin(max(0.0, float(ego.at(fr["t_ms"], "v_s"))))
                            wp = False
                            if wcl is not None:   # blob-fetta di muro: >= 50% dei suoi pixel (con Z valida) cadono in componenti muro PARALLELE al percorso
                                mm = BD._fill([r["poly"]]) & (zf_ != 255) & (zf_ < 250) & (zf_ >= 3); ids = wcl[mm]
                                if len(ids) >= 12: wp = bool(np.mean([wpar.get(int(i), {}).get("par", False) for i in ids]) >= 0.5)
                            r["wpar"] = wp; par = par or wp
                            tr.bd.append(bool(par or lat)); tr.bpar.append(bool(par)); r["bgeo"] = [bool(par), bool(lat)] + [round(float(fp[x]), 2) for x in ("gap", "zspan", "ext", "el", "ang")]
                        tr.fp.append(fp)
                    hist = [x for x in tr.bd[-5:] if x is not None]; lastfp = next((x for x in reversed(tr.fp) if x is not None), None)
                    if r["coast"] and lastfp is not None: gA_, gS_ = lat_gaps(r, pz, px, use_fp=False); lastfp = dict(gap=gA_, gap_s=gS_)      # traccia non vista: la posizione ATTUALE (box predetto, Z predetta), non l'impronta vecchia   # v11: bordo se >= 2 voti su 5 (1 solo se e' l'unico campione) E l'ultima impronta non interseca la sagoma (gap >= 0 sia sull'arco sia sul dritto; PROVATA l'esenzione per i muri paralleli che intersecano: perdeva pilastri a 0.4 m dalla traiettoria senza allarme, RIFIUTATA: sicurezza prima): il flicker dell'allungamento non riporta un muro a ostacolo
                    r["bordo"] = bool(hist and (sum(hist) >= (2 if len(hist) >= 2 else 1)) and (lastfp is None or max(lastfp["gap"], lastfp["gap_s"]) >= 0.0))
                    if V12 and r["bordo"] and not r["coast"] and (r["box"][2] - r["box"][0]) * r["Z"] / F_PX <= NARROW_W:   # giro 12: blob STRETTO (pilastro/palo) la cui sagoma (box alla Z misurata) interseca la sagoma bici = ostacolo, non fetta di muro
                        gA_, gS_ = lat_gaps(r, pz, px, use_fp=False)
                        if min(gA_, gS_) <= BD.LAT_GAP_TOL: r["bordo"] = False; r["stretto"] = True
                elif r["src"] == "blob" and not V11:
                    if not r["coast"]:
                        g = BD.blob_geometry(r["poly"], zf_, gpf, HP, k); tr.bd.append(None if g is None else bool(g[0])); r["bgeo"] = None if g is None else [bool(g[0])] + [round(float(x), 2) for x in g[1:]]
                    hist = [x for x in tr.bd[-5:] if x is not None]; r["bordo"] = bool(hist and np.mean(hist) > 0.5)
            if V12 and r["fam"] in ("altro", "ostacolo") and r["src"] != "bordo":
                # giro 12 (a): 'altro'/blob GRANDI o parte di edificio/muro (>=50% dei pixel della maschera in classe edificio/muro dello sfondo), laterali (|X|>0.8 m): al piu' BORDO, mai FRENA/RALLENTA. Voto 2 su 5 (1 se unico).
                tr = r["track"]
                if not r["coast"] and r.get("poly") is not None:
                    bx = r["box"]; big = (max(0, min(bx[2], W) - max(bx[0], 0)) * max(0, min(bx[3], H) - max(bx[1], 0))) / float(W * H) > LATW_BIG
                    wf = 0.0
                    if lab0 is not None:
                        mm = BD._fill([r["poly"]]).astype(bool)
                        if mm.sum() >= 12: wf = float(np.isin(lab0, BD.CL_WALL)[mm].mean())
                    rf = 0.0
                    if V13 and lab0 is not None:
                        mm = BD._fill([r["poly"]]).astype(bool)
                        if mm.sum() >= 12: rf = float(np.isin(lab0, BD.CL_ROAD + BD.CL_LOW)[mm].mean())
                    wide = (bx[2] - bx[0]) > 0.6 * W
                    # v13: superficie (fondo strada/marciapiede) segmentata come 'altro' = non e' un ostacolo: >=50% dei pixel in strada/marciapiede (stuff), oppure larga >60% dell'immagine e alta <0.5 m sul piano
                    if V13 and (rf >= 0.5 or (wide and r.get("h_top") is not None and r["h_top"] < 0.5)): r["superficie"] = True; r["cand"] = False
                    r["wf"] = round(wf, 2); tr.wb.append(bool(abs(r["X"]) > LATW_X and (big or wf >= LATW_WALL)))
                hw_ = tr.wb[-5:]
                if hw_ and sum(hw_) >= (2 if len(hw_) >= 2 else 1) and abs(r["X"]) > LATW_X and not r.get("stretto"): r["bordo"] = True; r["lat_grande"] = True
            if V14:
                bx_ = r["box"]; tr_ = bx_[0] <= 2 or bx_[1] <= 2 or bx_[2] >= W - 2 or bx_[3] >= H - 2
                r["tiny"] = bool(r["fam"] in ("altro", "ostacolo") and not tr_ and max(bx_[2] - bx_[0], bx_[3] - bx_[1]) * r["Z"] / F_PX < TINY_M)      # giro 3 punto 3: estensione fisica alla Z scritta < 0.15 m (semaforo 0.08 m a 1.5 m): la Z non e' di un ostacolo
                if r["tiny"] or r.get("zpend"): r["cand"] = False
            if V13 and (r.get("in_veh") or r["coast"]): r["cand"] = False      # v13: in coast non c'e' maschera in questo fotogramma -> non puo' essere "primo ostacolo" (banner/azione) con una Z che non e' di una maschera
            if r["fuori_img"] or r["senza_base"] or r.get("bordo") or r.get("superficie"): r["cand"] = False
        bsum = None; v_ = max(0.0, float(ego.at(fr["t_ms"], "v_s")))
        if V10:
            lab = None
            if skeys is not None:
                nk = int(skeys[np.argmin(np.abs(skeys - fr["frame"]))])
                if abs(nk - fr["frame"]) <= 2: lab = stuff[f"f{nk}"]
            bf = BD.border_frame(zf_, gpf, k, v_, lab, [r["poly"] for r in rows if r["src"] != "blob" and not r["coast"]], [r["poly"] for r in rows if r.get("bordo") and not r["coast"]], HP)
            bsum = dict(bf=bf, alarm=None, lab=lab is not None)
            for si, side in enumerate(("L", "R")):
                vi = None if bf is None else bf[side]["viol"]; bhist[side].append(bool(vi is not None and v_ >= BD.V_MIN_ALLARME)); bclr[side].append(None if bf is None else bf[side]["clear"])
                cl_ok = [x for x in bclr[side][-5:] if x is not None]
                # v11 punto 4 (2973): provata la mediana degli ultimi 5 fotogrammi (BD_MED=1): allarmi 69->122 fotogrammi, molti episodi da 1 fotogramma = piu' falsi; RIFIUTATA, resta 3 consecutivi (causa: la misura laterale salta fra fotogrammi, vedi rapporto)
                if os.environ.get('BD_MED') == '1' and V11: trig = bool(bhist[side][-1] and len(cl_ok) >= 3 and float(np.median(cl_ok)) < bf['margin'])
                else: trig = len(bhist[side]) >= 3 and all(bhist[side][-3:])
                if trig:
                    Zv, cv_, kd = vi; nm = "sx" if side == "L" else "dx"
                    rows.append(dict(inside=1.0, id=-1 - si, fam="bordo", src="bordo", classe=kd, Z=Zv, Zf=Zv, rawfix=False, w=0.0, Zraw=Zv, tan=0.0, box=[0, 0, 0, 0], poly=None, decl=False, sosp=False, ext=False, hits=99, coast=False, track=None,
                                     X=0.0, in_arc=True, in_str=True, in_arc_pure=True, cand=True, fuori_img=False, h_base=0.0, h_top=0.0, escl="", senza_base=False, bordo=False, side=nm, clear=float(cv_), kind=kd))
                    if bsum["alarm"] is None or Zv < bsum["alarm"]["Z"]: bsum["alarm"] = dict(side=nm, Z=float(Zv), clear=float(cv_), kind=kd)
        first = {}
        _fk = lambda: None
        for key, flag in (("arc", "in_arc"), ("str", "in_str")):
            c = [r for r in rows if r[flag] and r["cand"]]
            best = min(c, key=lambda r: r["Z"], default=None)
            pf = prev_first[key]
            if pf is not None and best is not None:
                pr = next((r for r in c if r["id"] == pf), None)
                if pr is not None and best["Z"] > pr["Z"] - 0.5: best = pr
            prev_first[key] = None if best is None else best["id"]; first[key] = best
        act = None
        if V10:
            sg = BD.SOG.a(v_); f_ = first["arc"]
            if f_ is not None and v_ >= BD.V_MIN_ALLARME:
                Zf_ = f_["Z"]
                if f_["fam"] == "bordo" and f_["kind"] == "bordo":
                    oth = None if bsum["bf"] is None else bsum["bf"]["R" if f_["side"] == "sx" else "L"]["clear"]
                    libero = (oth is not None and oth >= sg["bordo_margine_m"]) if V14 else (oth is None or oth >= sg["bordo_margine_m"])      # giro 3 punto 2: libero SOLO se il lato opposto e' MISURATO e >= margine (regola di Daniele); non misurato = non libero
                    if V11 and Zf_ > sg["rallenta_entro_m"]: act = None      # v11: nessuna azione se il bordo e' oltre rallenta_entro lungo il percorso
                    elif (f_["clear"] < 0 or not libero) and Zf_ <= sg["frena_entro_m"]: act = ("FRENA", f"bordo {f_['side']}, " + ("nel percorso" if f_["clear"] < 0 else "nessuno spazio dall'altro lato"))
                    elif libero: act = ("STERZA", f"via dal bordo {f_['side']} {max(0, f_['clear']):.1f} m")
                    else: act = ("RALLENTA", f"bordo {f_['side']}, " + ("lato opposto NON MISURATO" if (V14 and oth is None) else "nessuno spazio dall'altro lato"))
                elif V11:
                    gA, gS = lat_gaps(f_, pz, px)
                    ground = f_["fam"] in BASE_EXEMPT or (f_["h_base"] is not None and f_["h_base"] <= H_BASE_MIN)
                    sagoma_int = min(gA, gS) <= BD.LAT_GAP_TOL                      # la sagoma 0-2 m dell'oggetto interseca la sagoma della bici (arco O dritto)
                    corr_ground = ground and min(gA, gS) <= sg["bordo_margine_m"]      # tocca terra dentro il corridoio (sagoma + margine)
                    f_["gap"] = (round(gA, 2), round(gS, 2), bool(ground))
                    if V14 and f_["fam"] in ("altro", "ostacolo") and not sagoma_int: act = None      # giro 3 punto 3: 'altro'/blob agiscono solo se la maschera interseca la sagoma bici (arco o dritta), non per il solo margine
                    elif not (sagoma_int or corr_ground): act = None
                    elif Zf_ <= sg["frena_entro_m"]:
                        if Zf_ < Z_COERENZA and f_["fam"] != "persona" and not z_coerente(f_["track"]): act = ("RALLENTA", "ostacolo davanti (Z<2 m non coerente)")
                        else: act = ("FRENA", "ostacolo davanti")
                    elif Zf_ <= sg["rallenta_entro_m"]: act = ("RALLENTA", "ostacolo davanti")
                elif abs(f_["X"] - float(np.interp(Zf_, pz, px))) > BD.HW + sg["bordo_margine_m"]: act = None    # fuori dalla sagoma + margine: non e' sul percorso (corridoio largo del tracking), nessuna azione
                elif Zf_ <= sg["frena_entro_m"]: act = ("FRENA", "ostacolo davanti")
                elif Zf_ <= sg["rallenta_entro_m"]: act = ("RALLENTA", "ostacolo davanti")
            if V12 and act is not None and act[0] == "FRENA" and f_["fam"] not in ("persona", "bordo") and Zf_ >= Z_COERENZA:
                # giro 12 (c): oggetto VERO sul percorso, la strada gira e c'e' spazio dall'altro lato -> STERZA; altrimenti resta FRENA/RALLENTA. Spazio = distanza libera dall'altro lato (bordo/muro misurato) >= spostamento necessario + margine bordo,
                # e nessun altro candidato sul lato libero entro Zf+3 m. Persone mai (si muovono: FRENA).
                xa_ = float(np.interp(Zf_, pz, px)); rgt = (f_["X"] - xa_) > 0; oth_ = None if bsum["bf"] is None else bsum["bf"]["L" if rgt else "R"]["clear"]
                mg = sg["bordo_margine_m"]; shift = max(0.0, mg - min(gA, gS))
                blocc = any(o_ is not f_ and o_["cand"] and not o_.get("bordo") and o_["Z"] <= Zf_ + 3.0 and ((xa_ - o_["X"]) if rgt else (o_["X"] - xa_)) > -0.2
                            and ((xa_ - o_["X"]) if rgt else (o_["X"] - xa_)) <= BD.HW + shift + mg + 0.3 for o_ in rows)
                if shift <= SHIFT_MAX and ((oth_ is not None) if V14 else True) and (oth_ is None or oth_ >= shift + mg) and not blocc:   # spostamento laterale necessario <= 1.0 m: oggetto largo (sbarra, muro) = FRENA
                    act = ("STERZA", f"via dall'oggetto a {'dx' if rgt else 'sx'}, libero a {'sx' if rgt else 'dx'}" + ("" if oth_ is None else f" {oth_:.1f} m")); f_["sterza_ogg"] = True
            if V13 and act is not None and act[0] == "FRENA" and f_["coast"]: act = ("RALLENTA", "ostacolo davanti (senza maschera ora)")      # FRENA solo con la maschera presente
            act = dict(act=None if act is None else act[0], why=None if act is None else act[1], Z=None if f_ is None else float(f_["Z"]), sg=sg)
        nm = (None, None, False); pend = None
        if V13:
            nm = nonmis(fr, k, gpf, zf_, max(8.0, min(30.0, BD.SOG.a(v_)['rallenta_entro_m']))); sat_ = nm[1] is not None and nm[1] > NM_SAT
            pend = None
            if V14:    # oggetto che sarebbe candidato ma con Z instabile (salto): non agisce, non e' 'strada libera' ne' NON MISURATO: stato a parte 'in conferma'
                pc = [r for r in rows if r.get("zpend") and r["in_arc"] and not r["coast"] and not r["decl"] and not r["sosp"] and not r.get("tiny") and not r["fuori_img"] and not r["senza_base"] and not r.get("bordo") and not r.get("superficie") and not r.get("in_veh") and r["hits"] >= need_hits(r) and r["Z"] <= 30]
                pend = min(pc, key=lambda r: r["Z"], default=None)
            nm = (nm[0], nm[1], bool(sat_ or (nm[2] and first["arc"] is None and pend is None)))      # strada del corridoio fino a rallenta_entro (min 8 m)
        res.append(dict(k=k, first=first, bord=bsum, v=v_, act=act, nm=nm, pend=(pend if V14 and V13 else None)))
    return res


def smooth_gp(frames, i, win=15):
    g = [f["gp"] for f in frames[max(0, i - win):i + win + 1] if f["gp"] is not None]
    if not g: return None
    # disegno: piano strada senza pendenza trasversale (gb=0), pendenza ga da geometria (altezza camera, pitch), solo l'orizzonte gvh = mediana temporale +-1 s delle stime per fotogramma
    return (B_M / (D.CAM_H * np.cos(D.PITCH)), float(np.median([x[1] for x in g])), 0.0)


def chip(img, x, y, txt, col, sc=0.7, th=2):
    (w, h), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, sc, th)
    x = int(min(max(0, x), W - w - 8)); y = int(min(max(h + 6, y), H - 4))
    cv2.rectangle(img, (x, y - h - 6), (x + w + 8, y + 4), col, -1)
    cv2.putText(img, txt, (x + 4, y - 1), cv2.FONT_HERSHEY_DUPLEX, sc, (0, 0, 0), th, cv2.LINE_AA)
    return (x, y - h - 6, x + w + 8, y + 4)


def shadow(img, x, y, txt, sc, col, th=2):
    for dx, dy in ((2, 2), (-1, -1), (2, -1), (-1, 2)): cv2.putText(img, txt, (x + dx, y + dy), cv2.FONT_HERSHEY_DUPLEX, sc, (0, 0, 0), th, cv2.LINE_AA)
    cv2.putText(img, txt, (x, y), cv2.FONT_HERSHEY_DUPLEX, sc, col, th, cv2.LINE_AA)


def ztxt(Z): return "> 25 m" if Z > 25 else f"{Z:.1f} m"


def draw(img, fr, rows, cs, gp, zthumb, ego, sess, t0, i):
    out = img.copy(); cx = 660.142
    k = cs["k"]
    if gp:
        ga, gvh, gb = gp
        Zs = np.geomspace(1.8, 30.0, 40); pz, px = corr_path(k); Lp, Rp, Cp = [], [], []
        for Z in Zs:
            xc = float(np.interp(Z, pz, px)); d = F_PX * B_M / Z
            lo, hi = corr_edges(xc, Z)
            for X, o in ((lo, Lp), (hi, Rp), (xc, Cp)):
                u = cx + X * F_PX / Z; o.append((u, gvh + (d - gb * (u - cx)) / ga))
        poly = np.array(Lp + Rp[::-1], np.int32)
        lay = out.copy(); cv2.fillPoly(lay, [poly], CORR); out = cv2.addWeighted(lay, 0.13, out, 0.87, 0)
        for P in (Lp, Rp): cv2.polylines(out, [np.array(P, np.int32)], False, CORR, 2, cv2.LINE_AA)
        for Zt in (3, 5, 10, 20):
            xc = float(np.interp(Zt, pz, px)); d = F_PX * B_M / Zt
            pts = []
            for X in corr_edges(xc, Zt):
                u = cx + X * F_PX / Zt; pts.append((int(u), int(gvh + (d - gb * (u - cx)) / ga)))
            if 0 < pts[0][1] < H - 10:
                cv2.line(out, pts[0], pts[1], CORR, 1, cv2.LINE_AA); shadow(out, min(pts[0][0], pts[1][0]) + 8, pts[0][1] - 5, f"{Zt} m", 0.5, CORR, 1)
    bs_ = cs.get("bord"); bf = None if bs_ is None else bs_["bf"]
    if gp and bf:
        ga, gvh, gb = gp; mg = bf["margin"]
        for side in ("L", "R"):
            byz = {}
            for z, xb, c, par, _h, *_r in bf[side]["bins"]:
                if par and (z not in byz or c < byz[z][1]): byz[z] = (xb, c)
            pts = []
            for z in sorted(byz):
                xb, c = byz[z]; u = cx + xb * F_PX / z; pts.append((z, u, gvh + (F_PX * B_M / z - gb * (u - cx)) / ga, c))
            for a_, b_ in zip(pts[:-1], pts[1:]):
                if b_[0] - a_[0] > 1.01: continue
                c = min(a_[3], b_[3]); col = (0, 0, 255) if c < mg else ((0, 165, 255) if c < 2 * mg else (0, 220, 0))
                cv2.line(out, (int(a_[1]), int(a_[2])), (int(b_[1]), int(b_[2])), col, 5, cv2.LINE_AA)
    first = cs["first"]["arc"]; fid = None if first is None else first["id"]
    draw_rows = [r for r in rows if not r["coast"] and r["Z"] <= 40 and not r["decl"] and not (r["src"] == "blob" and r["hits"] < need_hits(r)) and not r["sosp"] and not r.get("fuori_img") and not r.get("senza_base") and not r.get("superficie") and not r.get("in_veh") and not r.get("tiny") and r["fam"] != "bordo" and not r.get("bordo")
                 and (r["src"] != "blob" or (r["in_arc"] and r["Z"] <= 8)) and (r["fam"] in ("persona", "veicolo", "bici-moto", "paletto-palo", "barriera-cancello", "ostacolo") or r["in_arc"] or r["Z"] < 8)]
    solid = [r for r in draw_rows if r["src"] != "blob"]
    cont_ = lambda a, b: max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1])) / max(1e-9, (a[2] - a[0]) * (a[3] - a[1]))
    draw_rows = [r for r in draw_rows if not (r["src"] == "blob" and r["id"] != fid and any(cont_(r["box"], q["box"]) > 0.5 for q in solid))]
    ov = out.copy()
    for r in sorted(draw_rows, key=lambda r: -r["Z"]):
        if r["poly"] is not None and len(r["poly"]) >= 3: cv2.fillPoly(ov, [np.asarray(r["poly"], np.int32)], zcol(r["Z"]))
        elif r["src"] != "blob":
            b = r["box"]; cv2.rectangle(ov, (b[0], b[1]), (b[2], b[3]), zcol(r["Z"]), -1)
    out = cv2.addWeighted(ov, 0.5, out, 0.5, 0)
    for r in sorted(draw_rows, key=lambda r: -r["Z"]):
        fc = FAMCOL[r["fam"]]; th = 3 if r["in_arc"] else 2
        if r["poly"] is not None and len(r["poly"]) >= 3: cv2.polylines(out, [np.asarray(r["poly"], np.int32)], True, fc, th, cv2.LINE_AA)
        else: b = r["box"]; cv2.rectangle(out, (b[0], b[1]), (b[2], b[3]), fc, th)
    for r in [q for q in rows if not q["coast"]]:   # scartati/declassati: contorno grigio sottile se vicini
        if (r["decl"] or r["sosp"] or r.get("senza_base") or r.get("bordo")) and r["Z"] < 8 and r["poly"] is not None and len(r["poly"]) >= 3: cv2.polylines(out, [np.asarray(r["poly"], np.int32)], True, (110, 110, 110), 1, cv2.LINE_AA)
    if first is not None and not first["coast"] and first["fam"] != "bordo":
        b = first["box"]; cv2.rectangle(out, (b[0] - 4, b[1] - 4), (b[2] + 4, b[3] + 4), (255, 255, 255), 3)
    placed = []
    lab = [r for r in draw_rows if (r["in_arc"] or r["Z"] < 8) and not (r["src"] == "blob" and r["Z"] > 8)]
    for r in sorted(lab, key=lambda r: r["Z"]):
        tr = r["track"]; b = r["box"]; txt = f"{FAMNAME[r['fam']]} {'~' if r.get('Zdim') else ''}{ztxt(r['Z'])}{' ? (da confermare)' if r.get('zpend') else ''}"
        tx, ty = b[0], max(b[1] - 8, 96)
        if tr.lab_xy is not None: tx = 0.5 * tr.lab_xy[0] + 0.5 * tx; ty = 0.5 * tr.lab_xy[1] + 0.5 * ty
        (w_, h_), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 0.7, 2)
        for _ in range(8):
            rc_ = (tx, ty - h_ - 6, tx + w_ + 8, ty + 4)
            if all(not (rc_[0] < q[2] and q[0] < rc_[2] and rc_[1] < q[3] and q[1] < rc_[3]) for q in placed): break
            ty -= (h_ + 8)
            if ty < 96: ty = b[3] + 24; break
        tr.lab_xy = (tx, ty); placed.append(chip(out, tx, ty, txt, FAMCOL[r["fam"]], 0.7, 2))
    t = (fr["t_ms"] - t0) / 1000; v = max(0.0, float(ego.at(fr["t_ms"], "v_s"))); st = float(ego.at(fr["t_ms"], "steer_s")); ttc = None
    nm_ = bool(V13 and cs.get("nm") is not None and cs["nm"][2])
    if nm_:
        vq, sq, _ = cs["nm"]; cv2.rectangle(out, (W // 2 - 270, 8), (W // 2 + 270, 76), (0, 0, 0), -1); cv2.rectangle(out, (W // 2 - 270, 8), (W // 2 + 270, 76), (150, 150, 150), 3)
        shadow(out, W // 2 - 258, 38, "CORRIDOIO NON MISURATO (grigio = nessuna misura valida)", 0.55, (170, 170, 170), 1)
        shadow(out, W // 2 - 258, 66, "depth valida " + ("-" if vq is None else f"{100 * vq:.0f}%") + "  saturo " + ("-" if sq is None else f"{100 * sq:.0f}%") + ("" if first is None else f"  | parziale: {ztxt(first['Z'])} {FAMNAME[first['fam']]}"), 0.6, (170, 170, 170), 1)
        ttc = None
    elif first is None and cs.get("pend") is not None:
        pe = cs["pend"]; cv2.rectangle(out, (W // 2 - 270, 8), (W // 2 + 270, 76), (0, 0, 0), -1); cv2.rectangle(out, (W // 2 - 270, 8), (W // 2 + 270, 76), (0, 200, 255), 3)
        shadow(out, W // 2 - 258, 34, "OSTACOLO IN CONFERMA (Z instabile: nessuna azione)", 0.55, (0, 200, 255), 1)
        shadow(out, W // 2 - 258, 66, f"{FAMNAME[pe['fam']]}  misura {ztxt(pe['Z'])} ?", 0.8, (0, 200, 255), 2); ttc = None
    elif first is not None:
        cl = v if (first["fam"] in STATIC or first["fam"] == "bordo") else v - first["w"]   # famiglie ferme (paletti, barriere, senza classe): velocita' propria 0, TTC = Z/v_encoder; veicoli/persone/bici: Z/(v - w) con w dal Kalman
        ttc = first["Z"] / cl if cl > 0.3 else None
        col = FAMCOL[first["fam"]]
        cv2.rectangle(out, (W // 2 - 270, 8), (W // 2 + 270, 76), (0, 0, 0), -1); cv2.rectangle(out, (W // 2 - 270, 8), (W // 2 + 270, 76), col, 3)
        shadow(out, W // 2 - 258, 34, "PRIMO OSTACOLO NEL CORRIDOIO", 0.55, (255, 255, 255), 1)
        if first["fam"] == "bordo":
            lt = f"bordo {first['side']} " + (f"{first['clear']:.1f} m" if first["clear"] >= 0 else "nel percorso") if first["kind"] == "bordo" else f"muro davanti {ztxt(first['Z'])}"
            shadow(out, W // 2 - 258, 66, f"{lt} - sterza/frena  ({ztxt(first['Z'])})", 0.8, col, 2)
        else: shadow(out, W // 2 - 258, 66, f"{'~' if first.get('Zdim') else ''}{ztxt(first['Z'])}  {FAMNAME[first['fam']]}   TTC " + (f"{ttc:.1f} s" if ttc is not None and ttc < 60 else "-"), 0.95, col, 2)
    elif V13 and cs.get("nm") is not None and cs["nm"][2]:
        vq, sq, _ = cs["nm"]; cv2.rectangle(out, (W // 2 - 270, 8), (W // 2 + 270, 76), (0, 0, 0), -1); cv2.rectangle(out, (W // 2 - 270, 8), (W // 2 + 270, 76), (150, 150, 150), 3)
        shadow(out, W // 2 - 258, 40, "CORRIDOIO NON MISURATO", 0.9, (170, 170, 170), 2)
        shadow(out, W // 2 - 258, 66, "depth valida " + ("-" if vq is None else f"{100 * vq:.0f}%") + "  saturo " + ("-" if sq is None else f"{100 * sq:.0f}%") + "  (non e' strada libera)", 0.6, (170, 170, 170), 1)
    else:
        cv2.rectangle(out, (W // 2 - 270, 8), (W // 2 + 270, 52), (0, 0, 0), -1); shadow(out, W // 2 - 258, 40, "corridoio: nessun ostacolo misurato", 0.8, (0, 255, 0), 2)
    ac = cs.get("act")
    if ac is not None and ac["act"] is not None:
        ccol = {"FRENA": (0, 0, 255), "RALLENTA": (0, 165, 255), "STERZA": (0, 230, 255)}[ac["act"]]
        cv2.rectangle(out, (W // 2 - 270, 80), (W // 2 + 270, 124), (0, 0, 0), -1); cv2.rectangle(out, (W // 2 - 270, 80), (W // 2 + 270, 124), ccol, 3)
        shadow(out, W // 2 - 258, 114, f"{ac['act']}: {ac['why']}", 0.7, ccol, 2)
    if nm_ and (ac is None or ac["act"] is None) and v >= BD.V_MIN_ALLARME:      # giro 3 punto 4: PROPOSTA per Daniele (non decisa, non contata come azione): in NON MISURATO il lato sicuro e' RALLENTA
        cv2.rectangle(out, (W // 2 - 270, 80), (W // 2 + 270, 124), (0, 0, 0), -1); cv2.rectangle(out, (W // 2 - 270, 80), (W // 2 + 270, 124), (150, 150, 150), 1)
        shadow(out, W // 2 - 258, 110, "PROPOSTA (non decisa): RALLENTA, corridoio non misurato", 0.55, (170, 170, 170), 1)
    # scala distanza + legenda famiglie
    x0, y0 = 14, 20
    for j in range(260): cv2.line(out, (x0 + j, y0), (x0 + j, y0 + 16), zcol(ZMAX_SCALE * j / 259), 1)
    cv2.rectangle(out, (x0 - 1, y0 - 1), (x0 + 260, y0 + 16), (255, 255, 255), 1)
    for m in (0, 5, 10, 15, 20): shadow(out, x0 + int(m / 20 * 259) - (8 if m else 0), y0 + 38, f"{m}", 0.5, (255, 255, 255), 1)
    shadow(out, x0, y0 + 56, "distanza (m): rosso vicino, blu lontano", 0.45, (255, 255, 255), 1)
    lay = out.copy(); yy = H - 150; cv2.rectangle(lay, (8, yy - 18), (196, yy + 7 * 17 + 4), (0, 0, 0), -1); out = cv2.addWeighted(lay, 0.6, out, 0.4, 0)
    for n_, kf in enumerate(("veicolo", "persona", "bici-moto", "paletto-palo", "barriera-cancello", "ostacolo")):
        cv2.rectangle(out, (14, yy + n_ * 17 - 10), (30, yy + n_ * 17 + 2), FAMCOL[kf], -1); shadow(out, 38, yy + n_ * 17 + 2, FAMNAME[kf] + (" (senza classe)" if kf == "ostacolo" else ""), 0.42, (255, 255, 255), 1)
    cv2.rectangle(out, (14, yy + 6 * 17 - 10), (30, yy + 6 * 17 + 2), CORR, 2); shadow(out, 38, yy + 6 * 17 + 2, "corridoio (percorso previsto)", 0.42, (255, 255, 255), 1)
    if zthumb is not None:
        zt = np.where(zthumb == 255, 0, 255 - np.clip(zthumb.astype(np.float32) / 10 / ZMAX_SCALE * 255, 0, 255)).astype(np.uint8)
        c = TURBO[zt.reshape(-1)].reshape(zt.shape + (3,)); c[zthumb == 255] = 0; c = cv2.resize(c, (256, 160), interpolation=cv2.INTER_AREA)
        x0, y0 = W - 264, H - 188; out[y0:y0 + 160, x0:x0 + 256] = c; cv2.rectangle(out, (x0 - 1, y0 - 1), (x0 + 256, y0 + 160), (255, 255, 255), 1)
        shadow(out, x0, y0 - 6, "depth stereo (stessa scala)", 0.45, (255, 255, 255), 1)
    canvas = np.zeros((H + BAR, W, 3), np.uint8); canvas[:H] = out
    Rm = "rett." if abs(k) < 0.004 else f"R {1 / abs(k):.0f} m"
    txt = f"{sess[-6:]}  f{i}  {WALL(fr['t_ms']) if WALL else ''}  t = {t:.1f} s   v = {v:.1f} m/s ({v * 3.6:.0f} km/h)   sterzo {st:+.0f} gradi (+ = destra)   curvatura {k:+.3f} 1/m ({Rm})"
    cv2.putText(canvas, txt, (12, H + 31), cv2.FONT_HERSHEY_DUPLEX, 0.68, (0, 255, 0), 1, cv2.LINE_AA)
    ac = cs.get("act")
    if ac is not None:
        sg = ac["sg"]; cv2.putText(canvas, f"tabella soglie_attuazione_001 v{BD.SOG.versione} ({BD.SOG.stato.split(' ')[0]}): v = {v:.1f} m/s  frena_entro {sg['frena_entro_m']:.1f} m  rallenta_entro {sg['rallenta_entro_m']:.1f} m  bordo_margine {sg['bordo_margine_m']:.2f} m  sagoma {BD.HW * 2:.1f} m  h max {H_ALTO:.1f} m",
                                   (12, H + 90), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 220, 120), 1, cv2.LINE_AA)
    if bf is not None:
        ft = lambda s_: "-" if bf[s_]["clear"] is None else f"{bf[s_]['clear']:.1f} m"
        al = bs_["alarm"]; t2 = f"margini laterali (sagoma 0.70 m): sx {ft('L')}  dx {ft('R')}   soglia {bf['margin']:.2f} m" + (f"   ALLARME bordo {al['side']}" if al is not None else "")
        t2 = t2.replace("(sagoma 0.70 m)", f"(sagoma {BD.HW * 2:.1f} m)"); cv2.putText(canvas, t2, (12, H + 60), cv2.FONT_HERSHEY_DUPLEX, 0.68, (0, 0, 255) if al is not None else (0, 255, 0), 1, cv2.LINE_AA)
    return canvas, ttc


WALL = None


def load_wall(sess):
    """orario di parete di ogni t_ms dei fotogrammi: frames_*.csv t_ms e sensors_*.csv t_ms sono lo STESSO orologio (metodo unico), wall = colonna 'wall' dei sensori interpolata"""
    import glob, datetime as dtm
    sf = sorted(glob.glob(os.path.join(D.LOGS, "_sensors", "sensors", "sensors_" + sess.replace("session_", "")[:8] + "_*.csv")))
    T, Wl = [], []
    for fn in sf:
        for r in csv.DictReader(open(fn)):
            try: T.append(float(r["t_ms"])); Wl.append(dtm.datetime.fromisoformat(r["wall"]).timestamp())
            except Exception: pass
    o = np.argsort(T); T = np.array(T)[o]; Wl = np.array(Wl)[o]
    return lambda t_ms: dtm.datetime.fromtimestamp(float(np.interp(t_ms, T, Wl))).strftime("%H:%M:%S.%f")[:-5]


def main():
    global WALL
    ap = argparse.ArgumentParser(); ap.add_argument("session"); ap.add_argument("--jpg", default=""); ap.add_argument("--out", default=None); ap.add_argument("--stats-only", action="store_true"); a = ap.parse_args()
    sess = "session_" + a.session.replace("session_", ""); sid = sess[8:]
    frames = pickle.load(open(os.path.join(OUT_A, sess + "_A", "frames.pkl"), "rb")); zf_ = os.path.join(OUT_A, sess + "_A", "zmap.npz"); zm = np.load(zf_) if os.path.exists(zf_) else None
    sf_ = os.environ.get("VF_STUFF") or os.path.join(D.HERE, "out_20261112_v10", f"stuff_{sid}.npz"); stuff = np.load(sf_) if (V10 and os.path.exists(sf_) and not os.environ.get("VF_NOSTUFF")) else None
    ego = Ego(sess); k_causale(ego); famv2 = load_famv2(sess)
    f0, f1 = frames[0]["frame"], frames[-1]["frame"]
    if V13:
        rc0 = D.Rect(); fm0 = {f["frame"] for f in frames}
        for i, Lr in enumerate(D.gray_frames(os.path.join(D.LOGS, sess + "_right.h264"))):
            if i > f1: break
            if i < f0 or i not in fm0: continue
            Lf = cv2.remap(Lr, rc0.r["m1x"], rc0.r["m1y"], cv2.INTER_LINEAR); SATQ[i] = cv2.resize(Lf, (320, 200), interpolation=cv2.INTER_AREA)
            gb_ = cv2.GaussianBlur(Lf, (3, 3), 0).astype(np.float32); TEXQ[i] = cv2.resize((np.hypot(cv2.Sobel(gb_, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(gb_, cv2.CV_32F, 0, 1, ksize=3)) / 8.0 >= TEX_G).astype(np.float32), (320, 200), interpolation=cv2.INTER_AREA)
    per = run_tracking(frames, ego, famv2); cs = corridor_logic(per, frames, ego, zm, stuff); t0 = D.read_t(sess, "right")[0]
    name = f"video_fluido_{sid[-6:]}.mp4" if sid.endswith("093909") else f"video_fluido_{sid[-6:]}_{int(round((frames[0]['t_ms'] - t0) / 1000))}-{int(round((frames[-1]['t_ms'] - t0) / 1000))}.mp4"
    mp4 = a.out or os.path.join(OUT, name)
    WALL = load_wall(sess)

    if os.environ.get("VF_NMDUMP"):
        with open(os.environ["VF_NMDUMP"], "w") as fh_:
            fh_.write("frame,valid,sat,tex,valid_su_tex,nm_attuale\n")
            for fr_, c_ in zip(frames, cs):
                d_ = NMDBG.get(fr_["frame"]); fh_.write(f"{fr_['frame']},{','.join('' if x is None else '%.3f' % x for x in (d_ or (None,) * 4))},{int(c_['nm'][2])}\n")
    jpg = {int(x) for x in a.jpg.split(",") if x}
    stats_rows = []
    if not a.stats_only:
        ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H + BAR}", "-r", "15", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                               "-crf", "20", "-preset", "medium", "-movflags", "+faststart", mp4], stdin=subprocess.PIPE)
        rc = D.Rect(); fmap = {f["frame"]: n for n, f in enumerate(frames)}
        for i, Lr in enumerate(D.gray_frames(os.path.join(D.LOGS, sess + "_right.h264"))):
            if i > f1: break
            if i < f0: continue
            n = fmap[i]; L = cv2.remap(Lr, rc.r["m1x"], rc.r["m1y"], cv2.INTER_LINEAR)
            img = cv2.convertScaleAbs(cv2.cvtColor(L, cv2.COLOR_GRAY2BGR), alpha=1.15, beta=8)
            canvas, ttc = draw(img, frames[n], per[n], cs[n], smooth_gp(frames, n), (zm[f"f{i}"] if zm is not None and f"f{i}" in zm.files else None), ego, sess, t0, i)
            ff.stdin.write(canvas.tobytes())
            if i in jpg: cv2.imwrite(os.path.join(D.ROOT, "agents", "rapporti", "img", f"video_fluido_{sid[-6:]}_f{i}.jpg"), canvas, [cv2.IMWRITE_JPEG_QUALITY, 88])
        ff.stdin.close(); ff.wait(); print(mp4)
    pickle.dump(dict(per=[[{k: v for k, v in r.items() if k not in ("track", "poly")} for r in rows] for rows in per], cs=[dict(k=c["k"], first={kk: (None if v is None else v["id"]) for kk, v in c["first"].items()},
                firstZ={kk: (None if v is None else v["Z"]) for kk, v in c["first"].items()},
                v=c["v"], nm=c.get("nm"), pendZ=None if c.get("pend") is None else c["pend"]["Z"], wall=WALL(frames[ci]["t_ms"]), act=None if c["act"] is None else dict(act=c["act"]["act"], why=c["act"]["why"], Z=c["act"]["Z"], sg=c["act"]["sg"]), bord=None if c["bord"] is None else dict(alarm=c["bord"]["alarm"], lab=c["bord"]["lab"], margin=None if c["bord"]["bf"] is None else c["bord"]["bf"]["margin"],
                clearL=None if c["bord"]["bf"] is None else c["bord"]["bf"]["L"]["clear"], clearR=None if c["bord"]["bf"] is None else c["bord"]["bf"]["R"]["clear"],
                nL=0 if c["bord"]["bf"] is None else len(c["bord"]["bf"]["L"]["bins"]), nR=0 if c["bord"]["bf"] is None else len(c["bord"]["bf"]["R"]["bins"]))) for ci, c in enumerate(cs)], frames=[f["frame"] for f in frames], t_ms=[f["t_ms"] for f in frames]),
                open(os.path.join(OUT, f"tracks_{sid}.pkl"), "wb"))


if __name__ == "__main__":
    main()
