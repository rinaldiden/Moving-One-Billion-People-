"""
STRUTTURA SAUNA A INCASTRO — telaio completo dal modello dell'ultima tavola (sauna-model.js) + nodi collaudati v0.2
=================================================================================================================

Ingresso: sauna_membri.json (dump di window.SAUNA_MODEL.membri('ferro'), ultima tavola: porta, finestra e montanti
così come sono).

Regole di kit (tavolo 2026-11-03, laser-nodi-elettrico.md §3 + SINTESI):
  - pilastri d'angolo fino a terra; anelli di base e di testa accostati alle facce dei pilastri
  - montanti: piede PA-A61-off5 sull'anello di base, testa PA-B68 sotto l'anello di testa (PA-Bα sugli anelli
    laterali inclinati: orecchie in pendenza, asole verticali nel tubo inclinato, taglio inclinato del montante)
  - correnti e traversi spezzati fra i montanti; montanti spezzati alla finestra
  - travetti appoggiati SOPRA gli anelli di testa (+80, §3c) e 2 travetti di gronda (rotazione attorno al proprio
    asse non modellata)
  - nodi ancora da progettare (SG angolo, T anelli, CL correnti, PA-C travetti) → SEGNAPOSTO a parte, non finti
Uscite: output/struttura_sauna/{tubi,piastre,boccole,controventi,piedini,segnaposto}.step + report.json + render.png
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from build123d import Box, Compound, Cylinder, Pos, Rot, export_step, RectangleRounded, extrude

import nodi_sauna as v1
import nodi_sauna_v2 as V

QUI = Path(__file__).resolve().parent
OUT = QUI / "output" / "struttura_sauna"
B, T, RO = 80.0, 2.5, 5.0
H = B / 2
TN = V.TUBI[0]
DA = V.VARIANTI[1]                    # PA-A61-off5
DB = V.VARIANTI[3]                    # PA-B68 (foro 2 asolato)
CP = (DA.foro_piastra - (DA.d_boccola + 2 * DA.zinco_boccola)) / 2   # piastra appesa (nominale)
P1 = v1.Param()

M = json.loads((QUI / "sauna_membri.json").read_text())
E = M["env"]
W, DH, DT = E["W"] * 1000, E["Dhot"] * 1000, E["Dtot"] * 1000
HB, HF = E["hBack"] * 1000, E["hFront"] * 1000
HR = E["hrail"] * 1000
ALFA = math.atan((HF - HB) / DT)       # pendenza falda lungo +Y (negativa)


def g(p):  # modello [x, y_su, z_prof] m → mm [X, Y, Z_su]
    return np.array([p[0] * 1000, p[2] * 1000, p[1] * 1000])


def roof(Y):
    return HB + (HF - HB) * (Y / DT)


def tubo_tra(p0, p1):
    """Tubo 80×80×2,5 dall'estremo p0 a p1 (mm), facce allineate a verticale/orizzontale."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    L = float(np.linalg.norm(d))
    tub = v1.tubo_q(P1, L)
    u = d / L
    if abs(u[2]) > 0.99:                                     # verticale
        return Pos(*p0) * tub
    if abs(u[0]) > abs(u[1]):                                # lungo X (eventuale pendenza trascurata: X-ring orizzontali)
        return Pos(*p0) * Rot(0, 90 if u[0] > 0 else -90, 0) * tub
    e = math.degrees(math.atan2(u[2], abs(u[1])))            # lungo ±Y con elevazione e
    s = 1 if u[1] > 0 else -1
    return Pos(*p0) * Rot(s * (-90) + (e if s > 0 else -e), 0, 0) * tub


# --------------------------------------------------------------------------- classificazione membri
mem = M["membri"]
verticali = [m for m in mem if m["tipo"] == "montante"]
oriz = [m for m in mem if m["tipo"] in ("corrente", "traverso")]
anelli_b = [m for m in mem if m["tipo"] == "base"]
anelli_t = [m for m in mem if m["tipo"] == "testa"]
trav = [m for m in mem if m["tipo"] == "travetto"]
contr = [m for m in mem if m["tipo"] == "controvento"]

tubi, piastre, boccole, segnaposto, note = [], [], [], [], []
taglierine = {}            # id anello → lista taglierine
distinta = []


def seg(nome, p0, p1, ruolo, pezzi=None):
    s = tubo_tra(p0, p1)
    tubi.append([nome, s, ruolo])
    distinta.append(dict(pezzo=nome, ruolo=ruolo, L_mm=round(float(np.linalg.norm(np.subtract(p1, p0))), 1)))
    return s


def marker(p, tipo):
    segnaposto.append((tipo, Pos(*p) * Box(46, 46, 46)))


# --------------------------------------------------------------------------- 1. pilastri d'angolo (fino a terra)
angoli = {(0, 0), (W, 0), (0, DT), (W, DT)}
for m in verticali:
    a = g(m["p0"])
    if m["role"] == "post" and (round(a[0]), round(a[1])) in {(round(x), round(y)) for x, y in angoli}:
        seg(f"PIL {m['id']}", (a[0], a[1], -H), (a[0], a[1], roof(a[1]) + H), "pilastro d'angolo")

# --------------------------------------------------------------------------- 2. anelli di base e di testa
def anello(m, livello):
    a, b = g(m["p0"]), g(m["p1"])
    u = (b - a) / np.linalg.norm(b - a)
    # accorcia di H agli estremi che toccano un pilastro o un anello trasversale
    a2, b2 = a + u * H, b - u * H
    if livello == "base":
        a2[2] = b2[2] = 0.0
    nome = f"ANELLO {livello} {m['id']}"
    if abs(u[2]) > 1e-4:   # anello inclinato: tubo più lungo e taglio con piani VERTICALI alle facce dei pilastri
        s = seg(nome, a2 - u * 12, b2 + u * 12, f"anello {livello}")
        up = u[:2] / np.linalg.norm(u[:2])
        for q, sg in ((a2, -1), (b2, 1)):
            c = np.r_[q[:2] + up * sg * 300, q[2]]
            tubi[-1][1] = tubi[-1][1] - Pos(*c) * Rot(0, 0, math.degrees(math.atan2(up[1], up[0]))) * Box(600, 400, 600)
        distinta[-1]["L_mm"] = round(float(np.linalg.norm((b2 - a2))), 1)
    else:
        s = seg(nome, a2, b2, f"anello {livello}")
    for p in (a2 - u * H, b2 + u * H):
        marker((p[0], p[1], 0.0 if livello == "base" else roof(p[1])), "SG/T anello↔pilastro o anello (da progettare)")
    return dict(nome=nome, a=a2, b=b2, u=u, livello=livello)


AB = [anello(m, "base") for m in anelli_b]
AT = [anello(m, "testa") for m in anelli_t]


def anello_sotto(X, Y, lista):
    """Anello (in pianta) che passa per (X,Y)."""
    for r in lista:
        a, b, u = r["a"], r["b"], r["u"]
        v = np.array([X - a[0], Y - a[1]])
        L = np.linalg.norm((b - a)[:2])
        t = np.dot(v, u[:2] / np.linalg.norm(u[:2]))
        perp = abs(v[0] * u[1] - v[1] * u[0]) / np.linalg.norm(u[:2])
        if perp < 5 and -H - 1 <= t <= L + H + 1:
            return r
    return None


# --------------------------------------------------------------------------- 2b. travetti SOPRA gli anelli (+ gronda)
TRV = []
_ys = sorted(set(round(g(m["p0"])[1], 1) for m in trav))
for i, Y in enumerate([0.0] + _ys + [DT]):
    gronda = Y in (0.0, DT)
    hz_ring = H if gronda else H / math.cos(ALFA)
    Z = roof(Y) + hz_ring + (H if gronda else H / math.cos(ALFA))
    nome = f"TRAVETTO {i+1}{' gronda' if gronda else ''}"
    tub = v1.tubo_q(P1, W + B)
    tub = Pos(-H, Y, Z) * (Rot(0, 0, 0) if gronda else Rot(math.degrees(ALFA), 0, 0)) * Rot(0, 90, 0) * Pos(0, 0, 0) * tub
    tubi.append([nome, tub, "travetto"]); distinta.append(dict(pezzo=nome, ruolo="travetto", L_mm=W + B))
    TRV.append(dict(nome=nome, Y=Y, gronda=gronda))
    for X in (0.0, W):
        marker((X, Y, Z - H), ("PA-P pilastro→gronda" if gronda else "CL cavaliere travetto↔anello") + " (da progettare)")


def travetto_sopra(X, Y):
    for t in TRV:
        if abs(t["Y"] - Y) < 5:
            return t
    return None


# --------------------------------------------------------------------------- 3. montanti + nodi PA-A / PA-B / PA-C
nA = V.costruisci(DA, TN, TN)
taglia_A = v1.lungo_x(v1.tubo_q(P1, 420.0), 420.0) - nA["anello"]        # asole + fori nell'anello (locale)
piastra_A = nA["piastra"]


def psi(r):  # angolo in pianta dell'anello (gradi) per ruotare il nodo locale (anello lungo X locale)
    u = r["u"]
    return math.degrees(math.atan2(u[1], u[0]))


def nodo_B(X, Y, r, Ztop_m, sale=None, trav=None):
    """PA-B / PA-Bα in un riferimento locale (s lungo l'anello in pianta, w spessore, z su)."""
    ps = psi(r)
    # pendenza dell'anello lungo s
    a = math.atan2(r["u"][2], np.linalg.norm(r["u"][:2]))
    ta = math.tan(a)
    hz = H / math.cos(a)                      # semi-altezza verticale del tubo inclinato
    w2 = DB.wP / 2
    zb = -hz - (sale or DB.sale)
    if trav is None:   # PA-B / PA-Bα: testa di chiodo
        e = lambda s: hz + s * ta + DB.stacco   # sotto orecchie
        pts = [(-w2, zb), (w2, zb), (w2, e(w2)), (DB.orecchie, e(DB.orecchie)), (DB.orecchie, e(DB.orecchie) + DB.h_orecchie),
               (-DB.orecchie, e(-DB.orecchie) + DB.h_orecchie), (-DB.orecchie, e(-DB.orecchie)), (-w2, e(-w2))]
    else:              # PA-C: linguetta con gancio nel fondo del travetto (collo 26, testa 36, sottosquadra 10)
        tf = T / math.cos(ALFA if not trav["gronda"] else 0.0)
        eb = lambda s: hz + s * ta                       # sommità corpo = faccia sup. anello
        eh = lambda s: hz + s * ta + tf + CP + 0.6       # sotto testa: parete travetto + piastra appesa + 0,6 (D3)
        cn, ct_, ht = 13.0, 23.0, 8.0
        pts = [(-w2, zb), (w2, zb), (w2, eb(w2)), (cn, eb(cn)), (cn, eh(cn)), (ct_, eh(ct_)), (ct_, eh(ct_) + ht),
               (-cn, eh(-cn) + ht), (-cn, eb(-cn)), (-w2, eb(-w2))]
    P = v1.piastra(pts, DB.tP)
    for (x, z) in V.scarichi(pts, DB.r_scarico):
        P = P - v1.cil_y(2 * DB.r_scarico, 40, x, z)
    z2 = -hz - DB.z_bull_m + CP
    P = P - v1.cil_y(DB.foro_piastra, 40, 0, 0) - v1.cil_y(DB.foro_piastra, 40, 0, z2) \
          - v1.cil_y(DB.foro_piastra, 40, 0, z2 - DB.asola_foro2) - Pos(0, 0, z2 - DB.asola_foro2 / 2) * Box(DB.foro_piastra, 40, DB.asola_foro2)
    # asole verticali (piastra verticale che attraversa il tubo inclinato) + foro boccola
    from build123d import RectangleRounded, extrude
    L = DB.wP + DB.asola_gL
    cut = Pos(0, 0, -hz - 3 * T) * extrude(RectangleRounded(L, DB.asola_w, DB.R_asola), amount=2 * hz + 6 * T + abs(L * ta))
    cut = Pos(0, 0, -abs(L * ta) / 2) * cut
    # (taglierina limitata alle sole pareti sup/inf: il prisma è largo 6,8 in w → non tocca le pareti laterali)
    cut = cut + v1.cil_y(DB.foro_tubo, B + 30, 0, 0)
    Zax = Ztop_m
    T_glob = lambda sh: Pos(X, Y, Zax) * Rot(0, 0, ps) * sh
    tipo = ("PA-C" if trav else ("PA-Bα" if abs(a) > 1e-3 else "PA-B")) + (" corta" if sale and sale < DB.sale else "")
    piastre.append((tipo, T_glob(Pos(0, 0, -CP) * P)))
    if trav is not None:   # asola a chiave nel fondo del travetto (prima dello scorrimento di 10 copre la testa)
        Ls0, Ls1 = -13.0 - 10 - 0.8, 13.0 + 0.8
        kc = Pos((Ls0 + Ls1) / 2, 0, hz - 1.0 - abs((Ls1 - Ls0) * ta)) * extrude(
            RectangleRounded(Ls1 - Ls0, DB.asola_w, DB.R_asola), amount=8 + 2 * abs((Ls1 - Ls0) * ta))
        taglierine.setdefault(trav["nome"], []).append(T_glob(kc))
    boccole.append(T_glob(V.boccola(DB, 0, 0, DB.zinco_boccola)))
    zmh = -hz - DB.z_bull_m
    boccole.append(T_glob(V.boccola(DB, 0, zmh, DB.zinco_boccola)))
    taglierine.setdefault(r["nome"], []).append(T_glob(cut))
    return Zax - hz, a, ps, T_glob(v1.cil_y(DB.foro_tubo, B + 30, 0, zmh))


def taglio_inclinato(tub, X, Y, Zpiano, a, ps):
    """Toglie dal montante tutto ciò che sta sopra il piano inclinato (pendenza a lungo la direzione ps)."""
    from build123d import Align
    bx = Box(400, 400, 600, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return tub - (Pos(X, Y, Zpiano) * Rot(0, 0, ps) * Rot(0, -math.degrees(a), 0) * bx)


n_pa_a = n_pa_b = 0
montanti_info = []
for m in verticali:
    a0, a1 = g(m["p0"]), g(m["p1"])
    X, Y = a0[0], a0[1]
    if (round(X), round(Y)) in {(round(x), round(y)) for x, y in angoli}:
        continue
    piede_base = m["p0"][1] == 0
    testa_anello = abs(a1[2] - roof(Y)) < 1
    z0 = H if piede_base else a0[2] + H
    rB = anello_sotto(X, Y, AB) if piede_base else None
    rT = anello_sotto(X, Y, AT) if testa_anello else None
    extra = []
    if testa_anello and rT is not None:
        a_r0 = math.atan2(rT["u"][2], np.linalg.norm(rT["u"][:2]))
        Lm_est = roof(Y) - H / math.cos(a_r0) - z0
        sale = min(DB.sale, Lm_est - 30)
        tv = travetto_sopra(X, Y)
        zbot_ring, a_r, ps, foro_m = nodo_B(X, Y, rT, roof(Y), sale=sale, trav=tv)
        tub = v1.tubo_q(P1, roof(Y) + 60 - z0).moved(Pos(X, Y, z0))
        tub = taglio_inclinato(tub, X, Y, zbot_ring, a_r, ps)
        tub = tub - foro_m
        n_pa_b += 1
    else:
        ztop = a1[2] - H
        tub = v1.tubo_q(P1, ztop - z0).moved(Pos(X, Y, z0))
        marker((X, Y, a1[2]), "CL montante→traverso/corrente (da progettare)")
    if piede_base and rB is not None:
        ps = psi(rB)
        Tg = lambda sh: Pos(X, Y, 0) * Rot(0, 0, ps) * sh
        taglierine.setdefault(rB["nome"], []).append(Tg(taglia_A))
        piastre.append(("PA-A", Tg(Pos(0, 0, -CP) * piastra_A)))
        boccole.append(Tg(V.boccola(DA, 0, 0, DA.zinco_boccola)))
        boccole.append(Tg(V.boccola(DA, 0, H + DA.z_bull_m, DA.zinco_boccola)))
        tub = tub - Tg(v1.cil_y(DA.foro_tubo, B + 30, 0, H + DA.z_bull_m))
        n_pa_a += 1
    elif not piede_base:
        marker((X, Y, a0[2]), "CL montante su traverso/corrente (da progettare)")
    nome = f"MONT {m['id']}"
    tubi.append([nome, tub, "montante"])
    distinta.append(dict(pezzo=nome, ruolo="montante", L_mm=None))
    montanti_info.append(dict(id=m["id"], X=round(X), Y=round(Y), piede="PA-A" if piede_base else "CL",
                              testa=(piastre[-1][0] if testa_anello else "CL")))


# --------------------------------------------------------------------------- 4. correnti e traversi spezzati
def verticali_su_linea(a, b, z):
    """Posizioni (parametro t in mm lungo la linea) dei verticali che attraversano la quota z sulla linea a→b."""
    u = (b - a)[:2]; L = np.linalg.norm(u); u = u / L
    ts = []
    for m in verticali:
        p0, p1 = g(m["p0"]), g(m["p1"])
        v = p0[:2] - a[:2]
        if abs(v[0] * u[1] - v[1] * u[0]) > 5:
            continue
        t = float(np.dot(v, u))
        if not (-H - 1 <= t <= L + H + 1):
            continue
        is_post = m["role"] == "post"
        zb, zt = (-H, 1e9) if is_post else (p0[2], p1[2])
        if zb < z - 50 and zt > z + 50:
            ts.append(t)
    return sorted(set(round(t, 1) for t in ts)), L, u


fix = []
for m in oriz:
    a, b = g(m["p0"]), g(m["p1"])
    z = a[2]
    ts, L, u = verticali_su_linea(a, b, z)
    lo, hi = 0.0, L
    # estremi senza verticale: estendi al verticale più vicino (es. traverso finestra senza stipiti)
    if not any(abs(t - 0) < 50 for t in ts):
        prev = [t for t in ts if t < 0] or [t for t in verticali_su_linea(a - np.r_[u, 0] * 2000, b, z)[0]]
        cand = [t for t in verticali_su_linea(a - np.r_[u * 1500, 0], a, z)[0]]
        if cand:
            lo = -(1500 - max(cand)); fix.append(f"{m['id']}: estremo iniziale esteso di {-lo:.0f} mm al verticale più vicino")
    if not any(abs(t - L) < 50 for t in ts):
        cand = verticali_su_linea(b, b + np.r_[u * 1500, 0], z)[0]
        if cand:
            hi = L + min(cand); fix.append(f"{m['id']}: estremo finale esteso di {hi - L:.0f} mm al verticale più vicino")
    ts_all, _, _ = verticali_su_linea(a + np.r_[u * lo, 0], a + np.r_[u * hi, 0], z)
    ts_all = [t + lo for t in ts_all]
    pts = sorted(set([lo] + [t for t in ts_all if lo - 1 < t < hi + 1] + [hi]))
    for i in range(len(pts) - 1):
        t0, t1 = pts[i] + H, pts[i + 1] - H
        if t1 - t0 < 60:
            continue
        p0 = a + np.r_[u * t0, 0]; p1 = a + np.r_[u * t1, 0]
        seg(f"{m['tipo'].upper()} {m['id']}.{i+1}", p0, p1, m["tipo"])
        for t in (t0 - H, t1 + H):
            q = a + np.r_[u * t, 0]
            marker(q, "CL corrente/traverso↔montante (da progettare)")

# --------------------------------------------------------------------------- 6. controventi (piatto 40×5) e piedini
def piatto(p0, p1, fuori):
    p0, p1 = g(p0) + fuori, g(p1) + fuori
    d = p1 - p0; L = float(np.linalg.norm(d)); u = d / L
    yaw = math.degrees(math.atan2(u[1], u[0])); pitch = -math.degrees(math.asin(u[2]))
    return Pos(*((p0 + p1) / 2)) * Rot(0, 0, yaw) * Rot(0, pitch, 0) * (Box(L, 5, 40) if abs(fuori[1]) > 0 else Box(L, 40, 5))
cv = []
for m in contr:
    a = g(m["p0"])
    if abs(a[1] - 0) < 1 and abs(g(m["p1"])[1]) < 1:
        f = np.array([0, -H - 3, 0])
    elif a[0] > W / 2:
        f = np.array([H + 3, 0, 0])
    else:
        f = np.array([-H - 3, 0, 0])
    cv.append(piatto(m["p0"], m["p1"], f))
piedi = [Pos(X, Y, -H - 140) * Cylinder(12, 140, align=None) for X, Y in [(0, 0), (W, 0), (0, DT), (W, DT), (0, DH), (W, DH)]]
piedi = [Pos(0, 0, 70) * p for p in piedi]

# --------------------------------------------------------------------------- 7. applica le taglierine agli anelli
for t in tubi:
    if t[0] in taglierine:
        for c in taglierine[t[0]]:
            t[1] = t[1] - c

# --------------------------------------------------------------------------- 8. collaudo interferenze del telaio
def bb(s):
    b = s.bounding_box(); return (b.min.X, b.min.Y, b.min.Z, b.max.X, b.max.Y, b.max.Z)


def sovrap(a, b, tol=0.5):
    return all(a[i] <= b[i + 3] - tol and b[i] <= a[i + 3] - tol for i in range(3))


parti = [(n, s) for n, s, _ in tubi] + [(f"piastra {k} {i}", s) for i, (k, s) in enumerate(piastre)] + \
        [(f"boccola {i}", s) for i, s in enumerate(boccole)]
B_ = [bb(s) for _, s in parti]
interf = []
for i in range(len(parti)):
    for j in range(i + 1, len(parti)):
        if sovrap(B_[i], B_[j]):
            v = v1.vol(parti[i][1], parti[j][1])
            if v > 0.5:
                interf.append((parti[i][0], parti[j][0], round(v, 1)))

OUT.mkdir(parents=True, exist_ok=True)
export_step(Compound(children=[s for _, s, _ in tubi]), str(OUT / "tubi.step"))
export_step(Compound(children=[s for _, s in piastre]), str(OUT / "piastre.step"))
export_step(Compound(children=boccole), str(OUT / "boccole.step"))
export_step(Compound(children=cv), str(OUT / "controventi.step"))
export_step(Compound(children=piedi), str(OUT / "piedini.step"))
export_step(Compound(children=[s for _, s in segnaposto]), str(OUT / "segnaposto.step"))
ml = sum(d["L_mm"] or 0 for d in distinta) / 1000
import collections
rep = dict(membri_modello=len(mem), tubi=len(tubi), piastre=dict(collections.Counter(k for k, _ in piastre)), boccole=len(boccole),
           nodi_da_progettare=len(segnaposto), tipi_da_progettare=sorted(set(k for k, _ in segnaposto)),
           pendenza_falda_gradi=round(math.degrees(ALFA), 2), interferenze=interf, estensioni=fix,
           ml_tubi_orizzontali_e_pilastri=round(ml, 2), montanti=montanti_info)
(OUT / "report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
print(json.dumps({k: v for k, v in rep.items() if k != "montanti"}, ensure_ascii=False, indent=1))
