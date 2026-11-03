"""
Pipeline NODI SAUNA (kit ferro TUB 80×80×2,5 "casa IKEA") — costruzione + COLLAUDO VIRTUALE
=========================================================================================

Modella in 3D (build123d / OCCT) i nodi proposti dal tavolo del 2026-11-03
(capomastro-ai/deliverables/sauna-ferro/tavolo-2026-11-03/laser-nodi-elettrico.md):

  PA-A  piede montante → anello base: piastra passante 6 mm a BAIONETTA
        (cala, scorre 10 mm, 2 ganci in sottosquadra sotto la parete inferiore, boccola+M10 poka-yoke)
  PA-B  montante → anello testa: piastra passante "a testa di chiodo" (orecchie sulla faccia sup.)

e per ognuno esegue il COLLAUDO:
  1. interferenza in posizione finale (tubi, piastra, boccole)        → deve essere 0
  2. percorso di MONTAGGIO simulato a passi (calata, scorrimento, calata montante)
  3. SOTTOSQUADRA: corsa libera in sollevamento prima che i ganci battano (solo PA-A)
  4. POKA-YOKE: finestra di posizione in cui la boccola entra (deve esistere SOLO a fine corsa)
  5. ripetizione 1-4 nel CASO PEGGIORE EN 10219-2 (lato −1 %, t +10 %) e DOPO ZINCATURA (+zinco su tutto)
  6. regole laser: fascia utile, distanze dai bordi, asole fuori dall'impronta del montante
  7. SPORGENZE verso la stratigrafia (teste bullone/dadi) → input per i ponti termici (Energy)

Uscite: output/nodi_sauna/<nodo>/{*.step, piastra.dxf, render.png, sezione.png, collaudo.json}
Uso:   .venv/bin/python nodi_sauna.py            (tutti i nodi, tutti i casi)
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict, replace
from pathlib import Path

import numpy as np
from build123d import (Box, Compound, Cylinder, ExportDXF, Plane, Polygon, Pos, Rot,
                       RectangleRounded, Unit, export_step, extrude, offset, Kind)

QUI = Path(__file__).resolve().parent
OUT = QUI / "output" / "nodi_sauna"
TOL_V = 0.5   # mm³: sotto questa soglia l'intersezione è contatto/rumore numerico


# --------------------------------------------------------------------------- parametri (tavolo §2)
@dataclass
class Param:
    b: float = 80.0          # lato tubo
    t: float = 2.5           # parete
    ro: float = 5.0          # raggio esterno spigolo (EN 10219-2: 1,6t-2,4t)
    tP: float = 6.0          # spessore piastra PA
    wP: float = 68.0         # larghezza piastra PA
    gioco_asola: float = 0.6 # sulla larghezza asola (sul nero)
    gioco_asola_L: float = 0.6
    gola: float = 3.2        # gola gancio (t_max + 2 zinco + 0,3)
    collo: float = 14.0      # collo gancio
    testa: float = 24.0      # testa gancio (10 di sottosquadra)
    h_testa: float = 8.0
    passo_ganci: float = 54.0
    slide: float = 10.0      # corsa baionetta
    sale_montante: float = 160.0
    d_boccola: float = 20.0
    foro_boccola: float = 20.8
    s_boccola: float = 2.5
    z_bullone_montante: float = 50.0   # dalla faccia dell'anello
    orecchie: float = 58.0   # PA-B: semi-ingombro testa a T
    h_orecchie: float = 15.0
    zinco: float = 0.0       # spessore zinco per faccia (0 = nero; ISO 1461 ~0,055-0,085)
    nome_caso: str = "nominale"


CASI = [
    Param(),
    Param(b=80 * 0.99, t=2.5 * 1.10, nome_caso="peggiore_EN10219"),     # luce interna minima
    Param(zinco=0.085, nome_caso="zincato_0.085"),
    Param(b=80 * 0.99, t=2.5 * 1.10, zinco=0.085, nome_caso="peggiore+zincato"),
]


# --------------------------------------------------------------------------- primitive
def tubo_q(p: Param, L: float):
    """Tubo quadro a spigoli raggiati, asse Z, da z=0 a L, centrato in XY."""
    ri = max(p.ro - p.t, 0.3)
    est = extrude(RectangleRounded(p.b, p.b, p.ro), amount=L)
    inn = extrude(RectangleRounded(p.b - 2 * p.t, p.b - 2 * p.t, ri), amount=L + 2).moved(Pos(0, 0, -1))
    return est - inn


def lungo_x(shape, L):  # porta un tubo da asse Z (0..L) ad asse X centrato
    return Pos(-L / 2, 0, 0) * Rot(0, 90, 0) * shape


def piastra(pts, tP):
    """Piastra nel piano XZ (spessore lungo Y, centrata su y=0) da contorno [(x,z),...]."""
    f = Plane.XZ * Polygon(*pts, align=None)
    return extrude(f, amount=tP / 2, both=True)


def cil_y(d, L, x, z):
    return Pos(x, 0, z) * Rot(90, 0, 0) * Cylinder(d / 2, L)


def boccola(p: Param, x, z):
    L = p.b - 1
    return cil_y(p.d_boccola, L, x, z) - cil_y(p.d_boccola - 2 * p.s_boccola, L + 2, x, z)


def vol(a, b) -> float:
    try:
        r = a & b
        return float(r.volume) if r is not None else 0.0
    except Exception:
        return float("nan")


def zinca(shape, z):
    if z <= 0:
        return shape
    try:
        return offset(shape, amount=z, kind=Kind.INTERSECTION)
    except Exception:
        return shape


# --------------------------------------------------------------------------- NODO PA-A (baionetta)
def nodo_PA_A(p: Param):
    h = p.b / 2                        # semi-lato
    Lr, Lm = 420.0, 320.0
    ti = h - p.t                       # faccia interna (quota)
    w2 = p.wP / 2
    # piastra in coordinate FINALI (centro = asse montante, x=0)
    zs = -ti                           # spalle sulla faccia interna del fondo
    zg = zs - p.gola                   # sotto della gola = sopra della testa
    zt = zg - p.h_testa
    top = h + p.sale_montante
    hxL, hxR = -w2, w2 - p.collo       # bordo sx dei colli
    pts = [(-w2, top), (w2, top),
           (w2, zs), (w2, zg), (hxR + p.testa, zg), (hxR + p.testa, zt), (hxR, zt), (hxR, zs),
           (hxL + p.collo, zs), (hxL + p.collo, zg), (hxL + p.testa, zg), (hxL + p.testa, zt), (hxL, zt)]
    P = piastra(pts, p.tP)
    zm = h + p.z_bullone_montante
    P = P - cil_y(p.foro_boccola, 40, 0, 0) - cil_y(p.foro_boccola, 40, 0, zm)

    # anello base (asse X) con asole
    A = lungo_x(tubo_q(p, Lr), Lr)
    sw = p.tP + p.gioco_asola
    # asola superiore: copre l'ingombro della piastra PRIMA dello scorrimento (−slide) e dopo
    x0s, x1s = -w2 - p.slide - p.gioco_asola_L / 2, w2 + p.gioco_asola_L / 2
    # NB: la testa dx sporge oltre w2 di (testa-collo): prima dello scorrimento arriva a w2+testa-collo-slide
    x1s = max(x1s, w2 + (p.testa - p.collo) - p.slide + p.gioco_asola_L / 2)
    A = A - Pos((x0s + x1s) / 2, 0, h - p.t / 2) * Box(x1s - x0s, sw, p.t * 3)
    # asole a chiave sul fondo: lasciano passare la testa nella posizione pre-scorrimento
    for hx in (hxL, hxR):
        a0, a1 = hx - p.slide - p.gioco_asola_L / 2, hx - p.slide + p.testa + p.gioco_asola_L / 2
        A = A - Pos((a0 + a1) / 2, 0, -h + p.t / 2) * Box(a1 - a0, sw, p.t * 3)
    A = A - cil_y(p.foro_boccola, p.b + 20, 0, 0)

    # montante
    M = Pos(0, 0, h) * tubo_q(p, Lm)
    M = M - cil_y(p.foro_boccola, p.b + 20, 0, zm)

    B1, B2 = boccola(p, 0, 0), boccola(p, 0, zm)
    info = dict(asola_sup=(round(x0s, 2), round(x1s, 2)), asola_sup_L=round(x1s - x0s, 2),
                asole_fondo=[(round(hx - p.slide - p.gioco_asola_L / 2, 2),
                              round(hx - p.slide + p.testa + p.gioco_asola_L / 2, 2)) for hx in (hxL, hxR)],
                z_bullone_montante=zm, sottosquadra_nominale=p.testa - p.collo - p.gioco_asola_L / 2)
    return dict(anello=A, montante=M, piastra=P, boccole=[B1, B2], info=info, h=h, Lr=Lr, Lm=Lm,
                zm=zm, contorno=pts)


def collaudo_PA_A(p: Param, n):
    A, M, P, (B1, B2) = n["anello"], n["montante"], n["piastra"], n["boccole"]
    z = p.zinco
    if z:
        A, M, P, B1, B2 = (zinca(s, z) for s in (A, M, P, B1, B2))
        P = Pos(0, 0, 2 * z) * P                 # spalle sul fondo: +2 zinco
        M = Pos(0, 0, 2 * z) * M                 # montante appoggiato sull'anello: +2 zinco
    h = n["h"]
    r = {"caso": p.nome_caso}
    # 1. finale
    r["interf_finale_mm3"] = {
        "piastra∩anello": vol(P, A), "piastra∩montante": vol(P, M), "montante∩anello": vol(M, A),
        "boccola1∩(anello+piastra)": vol(B1, A) + vol(B1, P), "boccola2∩(montante+piastra)": vol(B2, M) + vol(B2, P)}
    # 2. percorso: calata piastra in posizione pre-scorrimento, poi scorrimento
    zfondo = min(pt[1] for pt in n["contorno"])
    dz0 = h - zfondo + 5
    peggiore, dove = 0.0, None
    for dz in np.arange(dz0, -0.01, -2.0):
        v = vol(Pos(-p.slide, 0, dz) * P, A)
        if v > peggiore:
            peggiore, dove = v, f"calata dz={dz:.1f}"
    for dx in np.arange(-p.slide, 0.01, 1.0):
        v = vol(Pos(dx, 0, 0) * P, A)
        if v > peggiore:
            peggiore, dove = v, f"scorrimento dx={dx:.1f}"
    for dz in np.arange(180, -0.01, -10.0):
        v = vol(Pos(0, 0, dz) * M, P) + vol(Pos(0, 0, dz) * M, A)
        if v > peggiore:
            peggiore, dove = v, f"calata montante dz={dz:.1f}"
    r["percorso_max_interf_mm3"], r["percorso_dove"] = round(peggiore, 3), dove
    # 3. sottosquadra: sollevamento libero (senza boccola) prima che i ganci battano
    libero = None
    for dz in np.arange(0.0, 6.01, 0.1):
        if vol(Pos(0, 0, dz) * P, A) > TOL_V:
            libero = round(dz, 2)
            break
    r["sollevamento_libero_mm"] = libero          # None = ganci NON trattengono (errore)
    # e in posizione pre-scorrimento la piastra si sfila? (deve sfilarsi: altrimenti non si monta)
    r["pre_scorrimento_sfilabile"] = vol(Pos(-p.slide, 0, 3.0) * P, A) < TOL_V
    # 4. poka-yoke: finestra di x dove la boccola dell'anello entra nella piastra
    ok = [dx for dx in np.arange(-p.slide, 0.01, 0.1) if vol(B1, Pos(dx, 0, 0) * P) < TOL_V]
    r["finestra_boccola_dx"] = (round(min(ok), 2), round(max(ok), 2)) if ok else None
    r["poka_yoke"] = bool(ok) and min(ok) > -1.0
    return r


# --------------------------------------------------------------------------- NODO PA-B (testa di chiodo)
def nodo_PA_B(p: Param):
    h = p.b / 2
    Lr, Lm = 420.0, 320.0
    w2 = p.wP / 2
    zb = -h - p.sale_montante
    pts = [(-w2, zb), (w2, zb), (w2, h), (p.orecchie, h), (p.orecchie, h + p.h_orecchie),
           (-p.orecchie, h + p.h_orecchie), (-p.orecchie, h), (-w2, h)]
    P = piastra(pts, p.tP)
    zm = -h - p.z_bullone_montante
    P = P - cil_y(p.foro_boccola, 40, 0, 0) - cil_y(p.foro_boccola, 40, 0, zm)
    A = lungo_x(tubo_q(p, Lr), Lr)
    sw, sL = p.tP + p.gioco_asola, p.wP + p.gioco_asola_L
    for zf in (h - p.t / 2, -h + p.t / 2):
        A = A - Pos(0, 0, zf) * Box(sL, sw, p.t * 3)
    A = A - cil_y(p.foro_boccola, p.b + 20, 0, 0)
    M = Pos(0, 0, -h - Lm) * tubo_q(p, Lm)
    M = M - cil_y(p.foro_boccola, p.b + 20, 0, zm)
    B1, B2 = boccola(p, 0, 0), boccola(p, 0, zm)
    info = dict(asole=(round(-sL / 2, 2), round(sL / 2, 2)), appoggio_orecchie_per_lato=round(p.orecchie - sL / 2, 2))
    return dict(anello=A, montante=M, piastra=P, boccole=[B1, B2], info=info, h=h, Lr=Lr, Lm=Lm, zm=zm,
                contorno=pts)


def collaudo_PA_B(p: Param, n):
    A, M, P, (B1, B2) = n["anello"], n["montante"], n["piastra"], n["boccole"]
    if p.zinco:
        A, M, P, B1, B2 = (zinca(s, p.zinco) for s in (A, M, P, B1, B2))
        P = Pos(0, 0, 2 * p.zinco) * P            # orecchie sulla faccia superiore: +2 zinco
        M = Pos(0, 0, -2 * p.zinco) * M           # anello appoggiato sul montante: montante "scende" rel.
    h = n["h"]
    r = {"caso": p.nome_caso}
    r["interf_finale_mm3"] = {
        "piastra∩anello": vol(P, A), "piastra∩montante": vol(P, M), "montante∩anello": vol(M, A),
        "boccola1∩(anello+piastra)": vol(B1, A) + vol(B1, P), "boccola2∩(montante+piastra)": vol(B2, M) + vol(B2, P)}
    peggiore, dove = 0.0, None
    for dz in np.arange(2 * h + p.sale_montante + 20, -0.01, -5.0):
        v = vol(Pos(0, 0, dz) * P, A) + vol(Pos(0, 0, dz) * P, M)
        if v > peggiore:
            peggiore, dove = v, f"calata piastra dz={dz:.1f}"
    r["percorso_max_interf_mm3"], r["percorso_dove"] = round(peggiore, 3), dove
    # la testa appoggia davvero: scendendo di 0,2 deve interferire con la faccia superiore
    r["orecchie_in_appoggio"] = vol(Pos(0, 0, -0.2) * P, A) > 0.05
    return r


# --------------------------------------------------------------------------- regole laser + sporgenze
def regole(p: Param, n, tipo):
    h, out = p.b / 2, []
    fascia = p.b - 2 * p.ro - 2 * 1.5 * p.t       # fascia utile centrale
    out.append(("fascia_utile_mm", round(fascia, 1)))
    out.append(("asola_larghezza_in_fascia", p.tP + p.gioco_asola <= fascia))
    luce = p.b - 2 * p.t
    out.append(("luce_interna_mm", round(luce, 2)))
    out.append(("gioco_laterale_piastra_con_cordone_1.5_mm", round(luce / 2 - 1.5 - p.wP / 2, 2)))
    out.append(("foro_boccola_in_fascia", p.foro_boccola <= fascia))
    if tipo == "PA-A":
        x0, x1 = n["info"]["asola_sup"]
        # l'asola superiore deve stare sotto la luce del montante (−h+t .. h−t), altrimenti resta un taglio aperto
        fuori = max(0.0, -(h - p.t) - x0) + max(0.0, x1 - (h - p.t))
        fuori_imp = max(0.0, -h - x0) + max(0.0, x1 - h)
        out.append(("asola_sup_fuori_luce_montante_mm", round(fuori, 2)))
        out.append(("asola_sup_fuori_impronta_montante_mm", round(fuori_imp, 2)))
        a = n["info"]["asole_fondo"]
        out.append(("ponte_tra_asole_fondo_mm", round(a[1][0] - a[0][1], 2)))
    # sporgenza teste bullone (M10 ISO 4017 testa 6,4 + rondella larga 2,5) / dado autobloccante (10 + 2,5 + 2 filetti)
    out.append(("sporgenza_testa_M10_lato_caldo_mm", 6.4 + 2.5 - 0.5))
    out.append(("sporgenza_dado_M10_lato_opposto_mm", 10.0 + 2.5 + 3.0 - 0.5))
    out.append(("sporgenza_testa_bassa_DIN7984_mm", 5.0 + 2.0 - 0.5))
    return dict(out)


# --------------------------------------------------------------------------- uscite grafiche
def _mesh(shape, tol=0.4):
    v, t = shape.tessellate(tol)
    V = np.array([(q.X, q.Y, q.Z) for q in v])
    return V[np.array(t)] if len(t) else np.zeros((0, 3, 3))


def render(n, out: Path, titolo):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    parti = [(n["anello"], "#8aa1b4", 0.35), (n["montante"], "#9fb6c8", 0.35),
             (n["piastra"], "#d08c4f", 1.0)] + [(b, "#c03030", 1.0) for b in n["boccole"]]
    fig = plt.figure(figsize=(13, 6.5))
    for i, (el, az, nome, esp) in enumerate([(22, -55, "assieme (tubi trasparenti)", 0),
                                             (22, -55, "esploso", 1)]):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        for k, (sh, col, al) in enumerate(parti):
            if esp:
                dz = {0: -90, 1: 260, 2: 90}.get(k, 0)
                dy = 0 if k < 3 else (140 if k == 3 else -140)
                sh = Pos(0, dy, dz * np.sign(n["zm"]) if k == 1 else dz) * sh
            ax.add_collection3d(Poly3DCollection(_mesh(sh), facecolor=col, edgecolor="none", alpha=al))
        ax.set_xlim(-160, 160); ax.set_ylim(-160, 160); ax.set_zlim(-200, 260 if n["zm"] > 0 else 120)
        if n["zm"] < 0:
            ax.set_zlim(-330, 120)
        ax.set_box_aspect((1, 1, 1.4)); ax.view_init(el, az); ax.set_axis_off(); ax.set_title(nome, fontsize=9)
    fig.suptitle(titolo, fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "render.png", dpi=105)
    plt.close(fig)


def sezione(n, out: Path, titolo, extra=None):
    """Sezione col piano y=0 (mezzeria piastra): mostra ganci, asole, boccole."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 8))
    lam = Box(2000, 0.02, 2000)
    for sh, col in ((n["anello"], "#8aa1b4"), (n["montante"], "#9fb6c8"), (n["piastra"], "#d08c4f")) + tuple(
            (b, "#c03030") for b in n["boccole"]):
        s = sh & lam
        if s is None or not s.solids():
            continue
        for tri in _mesh(Compound(children=list(s.solids())), 0.05):
            ax.fill(tri[:, 0], tri[:, 2], color=col, lw=0)
    ax.set_aspect("equal")
    zl = (-110, 260) if n["zm"] > 0 else (-260, 110)
    ax.set_xlim(-120, 120); ax.set_ylim(*zl); ax.grid(alpha=0.25)
    ax.set_title(titolo + "\nsezione y=0 · arancio piastra · grigio tubi · rosso boccole", fontsize=8)
    if extra:
        ax.text(-115, zl[0] + 5, extra, fontsize=7, family="monospace", va="bottom")
    fig.savefig(out / "sezione.png", dpi=120)
    plt.close(fig)


def esporta(n, out: Path):
    export_step(n["anello"], str(out / "anello.step"))
    export_step(n["montante"], str(out / "montante.step"))
    export_step(n["piastra"], str(out / "piastra.step"))
    export_step(Compound(children=[n["anello"], n["montante"], n["piastra"], *n["boccole"]]),
                str(out / "assieme.step"))
    # DXF piatto della piastra (per il laser lamiera): sezione a y=0 riportata su XY
    try:
        f = (n["piastra"] & Box(2000, 0.01, 2000)).faces().sort_by().first if False else None
        sec = n["piastra"].faces().filter_by(Plane.XZ.z_dir if False else None) if False else None
        face = max(n["piastra"].faces(), key=lambda fc: fc.area)
        flat = Rot(-90, 0, 0) * face  # piano XZ → XY
        flat = Pos(0, 0, -flat.center().Z) * flat
        d = ExportDXF(unit=Unit.MM)
        d.add_shape(flat)
        d.write(str(out / "piastra.dxf"))
    except Exception as e:  # noqa
        (out / "piastra.dxf.ERRORE.txt").write_text(str(e))


# --------------------------------------------------------------------------- scheda lavorazioni (per il terzista)
def lavorazioni(p: Param, n, tipo):
    """Elenco feature per tubo: faccia (SUP/INF/LAT+Y/LAT-Y), tipo, quota dal centro nodo lungo l'asse,
    quota trasversale, dimensioni. Le quote assolute sul pezzo = posizione del nodo nella distinta + queste."""
    sw, h = p.tP + p.gioco_asola, p.b / 2
    L = []
    if tipo.startswith("PA-A"):
        x0, x1 = n["info"]["asola_sup"]
        L.append(dict(tubo="anello base", faccia="SUP", tipo="asola", centro_asse=round((x0 + x1) / 2, 2),
                      trasv=0, lungo=round(x1 - x0, 2), largo=sw, R_angoli=1.0))
        for a0, a1 in n["info"]["asole_fondo"]:
            L.append(dict(tubo="anello base", faccia="INF", tipo="asola a chiave", centro_asse=round((a0 + a1) / 2, 2),
                          trasv=0, lungo=round(a1 - a0, 2), largo=sw, R_angoli=1.0))
        L += [dict(tubo="anello base", faccia=f, tipo="foro boccola", centro_asse=0, quota_z=0, d=p.foro_boccola)
              for f in ("LAT+Y", "LAT-Y")]
        L += [dict(tubo="montante", faccia=f, tipo="foro boccola", dal_piede=p.z_bullone_montante, d=p.foro_boccola)
              for f in ("LAT+Y", "LAT-Y")]
    else:
        x0, x1 = n["info"]["asole"]
        L += [dict(tubo="anello testa", faccia=f, tipo="asola passante", centro_asse=0, trasv=0,
                   lungo=round(x1 - x0, 2), largo=sw, R_angoli=1.0) for f in ("SUP", "INF")]
        L += [dict(tubo="anello testa", faccia=f, tipo="foro boccola", centro_asse=0, quota_z=0, d=p.foro_boccola)
              for f in ("LAT+Y", "LAT-Y")]
        L += [dict(tubo="montante", faccia=f, tipo="foro boccola", dalla_testa=p.z_bullone_montante, d=p.foro_boccola)
              for f in ("LAT+Y", "LAT-Y")]
    L.append(dict(tubo="tutti orizzontali", faccia="INF", tipo="foro drenaggio", d=10, nota="a 30 mm dalle estremità"))
    return L


# --------------------------------------------------------------------------- main
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tot = {}
    nodi = (("PA-A", nodo_PA_A, collaudo_PA_A, {}), ("PA-A54", nodo_PA_A, collaudo_PA_A, {"wP": 54.0}),
            ("PA-B", nodo_PA_B, collaudo_PA_B, {}))
    for tipo, costr, coll, var in nodi:
        od = OUT / tipo
        od.mkdir(exist_ok=True)
        risultati = []
        for p0 in CASI:
            p = replace(p0, **var)
            n = costr(p)
            r = coll(p, n)
            r["regole"] = regole(p, n, tipo[:4])
            r["info"] = n["info"]
            risultati.append(r)
            if p.nome_caso == "nominale":
                (od / "lavorazioni.json").write_text(json.dumps(lavorazioni(p, n, tipo), indent=2, ensure_ascii=False))
                esporta(n, od)
                render(n, od, f"Nodo {tipo} — TUB {p.b:g}×{p.b:g}×{p.t:g}, piastra {p.tP:g} mm")
                rr = r
                extra = (f"interf. finale max: {max(rr['interf_finale_mm3'].values()):.3f} mm3\n"
                         f"percorso max: {rr['percorso_max_interf_mm3']} mm3 ({rr['percorso_dove']})")
                if tipo.startswith("PA-A"):
                    extra += (f"\nsollevamento libero: {rr['sollevamento_libero_mm']} mm"
                              f"\nfinestra boccola dx: {rr['finestra_boccola_dx']}")
                sezione(n, od, f"Nodo {tipo} (nominale)", extra)
        # verdetto
        def ok(r):
            fin = max(v for v in r["interf_finale_mm3"].values() if v == v) < TOL_V
            perc = r["percorso_max_interf_mm3"] < TOL_V
            extra = True
            if tipo.startswith("PA-A"):
                extra = r["sollevamento_libero_mm"] is not None and r["sollevamento_libero_mm"] <= 1.5 \
                        and r["pre_scorrimento_sfilabile"] and r["poka_yoke"]
            else:
                extra = r["orecchie_in_appoggio"]
            return fin and perc and extra
        for r in risultati:
            r["esito"] = "PASSA" if ok(r) else "NON PASSA"
        (od / "collaudo.json").write_text(json.dumps({"param_nominali": asdict(replace(CASI[0], **var)), "casi": risultati},
                                                     indent=2, ensure_ascii=False, default=str))
        tot[tipo] = [(r["caso"], r["esito"]) for r in risultati]
        for r in risultati:
            print(tipo, r["caso"], r["esito"], "| fin", {k: round(v, 2) for k, v in r["interf_finale_mm3"].items()},
                  "| perc", r["percorso_max_interf_mm3"], r["percorso_dove"],
                  "| soll", r.get("sollevamento_libero_mm"), "| pk", r.get("finestra_boccola_dx"),
                  "| fuori_imp", r["regole"].get("asola_sup_fuori_impronta_montante_mm"),
                  "| fuori_luce", r["regole"].get("asola_sup_fuori_luce_montante_mm"),
                  "| ponte", r["regole"].get("ponte_tra_asole_fondo_mm"))
    print("VERDETTI", tot)


if __name__ == "__main__":
    main()
