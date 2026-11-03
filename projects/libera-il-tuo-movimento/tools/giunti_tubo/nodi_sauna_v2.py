"""
Pipeline NODI SAUNA — v0.2 (recepisce il tavolo 2026-11-03: giunti-pipeline-{laser,strutturista,energy}.md)
==========================================================================================================

Cambia rispetto alla v0.1 (nodi_sauna.py, tenuta come storico):
  D6  DISEGNO FISSO (piastra e posizioni di asole e fori nominali) contro TUBI REALI variati in modo indipendente
      (anello e montante da barre diverse: b ±1 %, t ±10 %, ro 4-6) × zinco 0 / 0,085 / 0,15 (acciaio reattivo)
  D2  quota di riferimento = BOCCOLA dell'anello: la piastra è appesa alla boccola; spalle (PA-A) e orecchie
      (PA-B) restano staccate ≥ 0,3 a regime e servono solo in calata
  D3  il bullone batte PRIMA dei ganci: corsa libera dei ganci ≥ corsa della boccola + 0,2
  D4  foro piastra Ø21,2 / foro tubo Ø20,8; finestra poka-yoke dopo lo zinco fra 0,3 e 1,0
  D5  boccola 20×4 E355, L = 79 FISSA (non b−1); se (b−L)/2 > 0,5 serve la rondella di spessore
  L   asola larga 6,8 con angoli R1; scarichi Ø2,5 negli spigoli concavi della piastra; cordone interno
      modellato (1,5×3 sulla faccia laterale ±Y, prescritto); PA-A spostata di +slide/2 (asola simmetrica)
  E   verso dei bulloni: testa bassa DIN 7984 verso il vano caldo, dado verso la camera ventilata

Uso:  .venv/bin/python -W ignore nodi_sauna_v2.py      → output/nodi_sauna_v2/<nodo>/
"""
from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, asdict, replace
from pathlib import Path

import numpy as np
from build123d import Box, Cylinder, Plane, Polygon, Pos, Rot, RectangleRounded, extrude, Compound

import nodi_sauna as v1   # tubo_q, lungo_x, piastra, cil_y, vol, zinca, render, sezione, esporta

QUI = Path(__file__).resolve().parent
OUT = QUI / "output" / "nodi_sauna_v2"
TOL_V = 0.5


@dataclass
class Disegno:            # quote di DISEGNO (nominali, uguali per tutti i pezzi del lotto)
    nodo: str = "PA-A"
    b: float = 80.0; t: float = 2.5
    wP: float = 60.0; c: float = 5.0; tP: float = 6.0
    slide: float = 10.0; collo: float = 14.0; testa: float = 24.0; h_testa: float = 8.0
    z_testa_gancio: float = -41.3      # sopra della testa, dal centro anello (piastra concentrica)
    stacco: float = 1.6                # spalle/orecchie rialzate rispetto alla faccia nominale
    sale: float = 160.0
    asola_w: float = 6.8; asola_gL: float = 1.6; R_asola: float = 1.0; r_scarico: float = 1.25
    foro_piastra: float = 21.2; foro_tubo: float = 21.0
    zinco_boccola: float = 0.01        # boccola zincata elettrolitica/lamellare, NON a caldo
    d_boccola: float = 20.0; s_boccola: float = 4.0; L_boccola: float = 79.0
    z_bull_m: float = 50.0
    orecchie: float = 58.0; h_orecchie: float = 15.0
    asola_foro2: float = 0.0           # allungamento verso il basso del foro 2 in piastra (PA-B: 0,8)

    @property
    def hang(self):  # discesa della piastra appesa alla boccola (nominale, sul nero)
        return (self.foro_piastra - self.d_boccola) / 2


@dataclass
class TuboReale:
    nome: str; b: float; t: float; ro: float


TUBI = [TuboReale("nom", 80.0, 2.5, 5.0), TuboReale("stretto", 79.2, 2.75, 6.0), TuboReale("largo", 80.8, 2.25, 4.0)]
ZINCO = [0.0, 0.085, 0.15]


def _p(tr: TuboReale):
    return v1.Param(b=tr.b, t=tr.t, ro=tr.ro)


def cordone(tr: TuboReale, L, asse):
    """Cordone interno 1,5×3 sulla faccia laterale +Y (prescritto)."""
    y = tr.b / 2 - tr.t - 0.75
    if asse == "x":
        return Pos(0, y, 0) * Box(L, 1.5, 3)
    return Pos(0, y, L / 2) * Box(3, 1.5, L)


def asola(cx, w, L, z_faccia, t, R):
    """Taglierina asola a raggi R, lunga L lungo x, larga w lungo y, passante la parete a quota z_faccia."""
    f = RectangleRounded(L, w, min(R, w / 2 - 0.01))
    return Pos(cx, 0, z_faccia - 1.5 * t) * extrude(f, amount=3 * t)


def scarichi(pts, r):
    """Cerchi negli spigoli concavi del contorno (antiorario o orario: decide l'area)."""
    P = np.array(pts); n = len(P)
    area = 0.5 * sum(P[i, 0] * P[(i + 1) % n, 1] - P[(i + 1) % n, 0] * P[i, 1] for i in range(n))
    out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if cr * area < 0:          # concavo
            out.append((float(b[0]), float(b[1])))
    return out


# --------------------------------------------------------------------------- costruzione
def costruisci(D: Disegno, ta: TuboReale, tm: TuboReale):
    h0 = D.b / 2
    Lr, Lm = 420.0, 320.0
    w2, c = D.wP / 2, D.c
    if D.nodo == "PA-A":
        zs = -(h0 - D.t) + D.stacco
        zg = D.z_testa_gancio
        zt = zg - D.h_testa
        top = h0 + D.sale
        hxL, hxR = c - w2, c + w2 - D.collo
        pts = [(c - w2, top), (c + w2, top),
               (c + w2, zs), (c + w2, zg), (hxR + D.testa, zg), (hxR + D.testa, zt), (hxR, zt), (hxR, zs),
               (hxL + D.collo, zs), (hxL + D.collo, zg), (hxL + D.testa, zg), (hxL + D.testa, zt), (hxL, zt)]
        z2 = h0 + D.z_bull_m + D.hang     # foro 2 in piastra, compensato per la piastra appesa
    else:  # PA-B
        zb = -h0 - D.sale
        ze = h0 + D.stacco
        pts = [(-w2, zb), (w2, zb), (w2, ze), (D.orecchie, ze), (D.orecchie, ze + D.h_orecchie),
               (-D.orecchie, ze + D.h_orecchie), (-D.orecchie, ze), (-w2, ze)]
        z2 = -h0 - D.z_bull_m + D.hang
    P = v1.piastra(pts, D.tP)
    for (x, z) in scarichi(pts, D.r_scarico):
        P = P - v1.cil_y(2 * D.r_scarico, 40, x, z)
    P = P - v1.cil_y(D.foro_piastra, 40, 0, 0) - v1.cil_y(D.foro_piastra, 40, 0, z2)
    if D.asola_foro2 > 0:
        e = D.asola_foro2
        P = P - v1.cil_y(D.foro_piastra, 40, 0, z2 - e) - Pos(0, 0, z2 - e / 2) * Box(D.foro_piastra, 40, e)

    # ANELLO reale con lavorazioni a disegno
    pa = _p(ta); ha = ta.b / 2
    A = v1.lungo_x(v1.tubo_q(pa, Lr), Lr) + cordone(ta, Lr, "x")
    if D.nodo == "PA-A":
        x0 = c - w2 - D.slide - D.asola_gL / 2
        x1 = max(c + w2, c + w2 + (D.testa - D.collo) - D.slide) + D.asola_gL / 2
        A = A - asola((x0 + x1) / 2, D.asola_w, x1 - x0, ha - ta.t / 2, ta.t, D.R_asola)
        fondo = []
        for hx in (hxL, hxR):
            a0, a1 = hx - D.slide - D.asola_gL / 2, hx - D.slide + D.testa + D.asola_gL / 2
            fondo.append((a0, a1))
            A = A - asola((a0 + a1) / 2, D.asola_w, a1 - a0, -ha + ta.t / 2, ta.t, D.R_asola)
        info = dict(asola_sup=(round(x0, 2), round(x1, 2)), asole_fondo=[tuple(round(v, 2) for v in f) for f in fondo])
    else:
        sL = D.wP + D.asola_gL
        for zf in (ha - ta.t / 2, -ha + ta.t / 2):
            A = A - asola(0, D.asola_w, sL, zf, ta.t, D.R_asola)
        info = dict(asole=(round(-sL / 2, 2), round(sL / 2, 2)))
    A = A - v1.cil_y(D.foro_tubo, D.b + 30, 0, 0)

    # MONTANTE reale
    pm = _p(tm)
    if D.nodo == "PA-A":
        zm0 = ha                                  # piede sull'anello
        zmh = zm0 + D.z_bull_m
        M = Pos(0, 0, zm0) * (v1.tubo_q(pm, Lm) + cordone(tm, Lm, "z"))
    else:
        zm0 = -ha - Lm
        zmh = -ha - D.z_bull_m
        M = Pos(0, 0, zm0) * (v1.tubo_q(pm, Lm) + cordone(tm, Lm, "z"))
    M = M - v1.cil_y(D.foro_tubo, D.b + 30, 0, zmh)
    info.update(z_foro_montante=round(zmh, 2), z_foro2_piastra=round(z2, 2))
    return dict(anello=A, montante=M, piastra=P, pts=pts, info=info, zmh=zmh, z2=z2, ha=ha, zm=zmh)


def boccola(D: Disegno, x, z, zinco):
    L = D.L_boccola
    return v1.cil_y(D.d_boccola + 2 * zinco, L, x, z) - v1.cil_y(D.d_boccola - 2 * D.s_boccola, L + 2, x, z)


# --------------------------------------------------------------------------- collaudo di un caso
def collaudo(D: Disegno, ta: TuboReale, tm: TuboReale, z: float, percorso=True):
    n = costruisci(D, ta, tm)
    A, M, P = n["anello"], n["montante"], n["piastra"]
    if z:
        A, M, P = (v1.zinca(s, z) for s in (A, M, P))
    # contatti: montante sull'anello (+2z) per PA-A; anello sul montante per PA-B
    M = Pos(0, 0, 2 * z if D.nodo == "PA-A" else -2 * z) * M
    zmh = n["zmh"] + (2 * z if D.nodo == "PA-A" else -2 * z)
    zb = D.zinco_boccola
    cp = (D.foro_piastra - 2 * z - (D.d_boccola + 2 * zb)) / 2     # gioco radiale boccola/piastra
    ct = (D.foro_tubo - 2 * z - (D.d_boccola + 2 * zb)) / 2        # gioco radiale boccola/tubo
    hang = -cp                                                     # piastra appesa alla boccola 1
    Ph = Pos(0, 0, hang) * P
    B1 = boccola(D, 0, 0, zb)
    # boccola 2: deve stare nel foro del montante e nel foro 2 della piastra appesa
    zp2 = n["z2"] + hang
    lo, hi = max(zmh - ct, zp2 - cp - D.asola_foro2), min(zmh + ct, zp2 + cp)
    b2_ok = lo <= hi + 1e-9
    zb2 = (lo + hi) / 2 if b2_ok else zmh
    B2 = boccola(D, 0, zb2, zb)
    r = dict(anello=ta.nome, montante=tm.nome, zinco=z)
    fin = {"P∩A": v1.vol(Ph, A), "P∩M": v1.vol(Ph, M), "M∩A": v1.vol(M, A),
           "B1∩(A+P)": v1.vol(B1, A) + v1.vol(B1, Ph), "B2∩(M+P)": v1.vol(B2, M) + v1.vol(B2, Ph)}
    r["interf_finale"] = {k: round(v, 2) for k, v in fin.items()}
    r["boccola2_entra"] = b2_ok
    r["scarto_foro2_mm"] = round(zp2 - zmh, 2)
    r["finestra_pokayoke_mm"] = round(min(cp, ct), 3)       # semi-ampiezza utile (assiale e verticale)
    # stacco spalle/orecchie a regime (deve essere ≥ 0,3): primo contatto scendendo dalla posizione appesa
    st = None
    for d in np.arange(0, 3.01, 0.05):
        if v1.vol(Pos(0, 0, hang - d) * P, A) > 0.05:
            st = round(d, 2); break
    r["stacco_a_regime_mm"] = st if st is not None else ">3"
    # corsa del bullone (dalla posizione appesa a quella in cui la boccola batte sotto) = 2·cp
    r["corsa_bullone_mm"] = round(2 * cp, 3)
    if D.nodo == "PA-A":
        lib = None
        for d in np.arange(0, 6.01, 0.05):
            if v1.vol(Pos(0, 0, hang + d) * P, A) > 0.05:
                lib = round(d, 2); break
        r["corsa_ganci_mm"] = lib
        r["D3_bullone_prima_dei_ganci"] = lib is not None and lib >= 2 * cp + 0.2
        # pre-scorrimento: non deve agganciare (si sfila) e la boccola NON deve entrare (poka-yoke)
        r["pre_scorr_sfilabile"] = v1.vol(Pos(-D.slide, 0, hang + 3.0) * P, A) < TOL_V
        r["pre_scorr_boccola_bloccata"] = v1.vol(B1, Pos(-D.slide, 0, hang) * P) > TOL_V
        # PA-A: la piastra resta appesa solo se la boccola 1 c'è; con zinco l'appeso usa cp reale
    # flessione pareti col serraggio: (b − L)/2
    r["flessione_parete_anello_mm"] = round((ta.b - D.L_boccola) / 2, 2)
    r["rondella_spessore"] = (ta.b - D.L_boccola) / 2 > 0.5 or (tm.b - D.L_boccola) / 2 > 0.5
    # percorso di montaggio
    if percorso:
        worst, dove = 0.0, None
        zbot = min(q[1] for q in n["pts"])
        if D.nodo == "PA-A":
            # in calata la piastra poggia sulle spalle: quota di montaggio = contatto spalle
            za = hang - (st if isinstance(st, float) else 0.0)
            for dz in np.arange(ta.b / 2 - zbot + 5, -0.01, -2.0):
                v = v1.vol(Pos(-D.slide, 0, za + dz) * P, A)
                if v > worst: worst, dove = v, f"calata dz={dz:.0f}"
            for dx in np.arange(-D.slide, 0.01, 1.0):
                v = v1.vol(Pos(dx, 0, za + 0.05) * P, A)
                if v > worst: worst, dove = v, f"scorrimento dx={dx:.0f}"
            for dz in np.arange(180, -0.01, -15.0):
                v = v1.vol(Pos(0, 0, dz) * M, Ph) + v1.vol(Pos(0, 0, dz) * M, A)
                if v > worst: worst, dove = v, f"calata montante dz={dz:.0f}"
            r["alzata_con_spina_mm"] = round(abs(za - hang), 2)   # quanto si alza la piastra per infilare B1
        else:
            for dz in np.arange(ta.b + D.sale + 20, -0.01, -5.0):
                v = v1.vol(Pos(0, 0, hang + dz) * P, A) + v1.vol(Pos(0, 0, hang + dz) * P, M)
                if v > worst: worst, dove = v, f"calata dz={dz:.0f}"
            r["alzata_con_spina_mm"] = round(st, 2) if isinstance(st, float) else None
        r["percorso_max_mm3"], r["percorso_dove"] = round(worst, 2), dove
    # gioco minimo laterale piastra/asola dopo lo zinco (tavolo: 0,2-0,3 totale)
    r["gioco_asola_totale_mm"] = round(D.asola_w - 2 * z - (D.tP + 2 * z), 3)
    # verdetto del caso
    ok = r["gioco_asola_totale_mm"] >= 0.2 and max(fin.values()) < TOL_V and b2_ok and isinstance(st, float) and st >= 0.3 \
        and 0.3 <= r["finestra_pokayoke_mm"] <= 1.0 and r.get("percorso_max_mm3", 0) < TOL_V
    if D.nodo == "PA-A":
        ok = ok and r["D3_bullone_prima_dei_ganci"] and r["pre_scorr_sfilabile"] and r["pre_scorr_boccola_bloccata"]
    r["esito"] = "PASSA" if ok else "NON PASSA"
    return r, n


def regole_disegno(D: Disegno, info):
    out = {}
    luce_min = 79.2 - 2 * 2.75           # luce interna minima del montante (caso stretto)
    if D.nodo == "PA-A":
        x0, x1 = info["asola_sup"]
        out["asola_sup"] = info["asola_sup"]
        out["margine_asola_in_luce_montante_min_mm"] = round(luce_min / 2 - max(-x0, x1), 2)
        f = info["asole_fondo"]
        out["ponte_asole_fondo_mm"] = round(f[1][0] - f[0][1], 2)
    out["e2_foro_piastra_mm"] = round(D.wP / 2 - abs(D.c), 2)
    out["e2_min_1.2d0_mm"] = round(1.2 * D.foro_piastra, 2)
    out["e2_ok"] = out["e2_foro_piastra_mm"] >= out["e2_min_1.2d0_mm"]
    out["gioco_piastra_parete_lato_off_min_mm"] = round(luce_min / 2 - (D.wP / 2 + abs(D.c)), 2)
    out["verso_bulloni"] = "testa bassa DIN 7984 + rondella verso il vano CALDO (sporge 6,5); dado autobloccante verso la camera ventilata"
    out["fresata_strato_continuo"] = "Ø35×9 sopra ogni testa; viti listelli ≥ 30 mm dai bulloni (Energy)"
    return out


def lavorazioni(D: Disegno, info):
    L = []
    if D.nodo == "PA-A":
        x0, x1 = info["asola_sup"]
        L.append(dict(tubo="anello base", faccia="SUP", tipo="asola R1", centro=round((x0 + x1) / 2, 2), lungo=round(x1 - x0, 2), largo=D.asola_w))
        for a0, a1 in info["asole_fondo"]:
            L.append(dict(tubo="anello base", faccia="INF", tipo="asola a chiave R1", centro=round((a0 + a1) / 2, 2), lungo=round(a1 - a0, 2), largo=D.asola_w))
        L.append(dict(tubo="montante", faccia="LAT±Y", tipo="foro boccola", dal_piede=D.z_bull_m, d=D.foro_tubo))
    else:
        L += [dict(tubo="anello testa", faccia=f, tipo="asola passante R1", centro=0, lungo=D.wP + D.asola_gL, largo=D.asola_w) for f in ("SUP", "INF")]
        L.append(dict(tubo="montante", faccia="LAT±Y", tipo="foro boccola", dalla_testa=D.z_bull_m, d=D.foro_tubo))
    L.append(dict(tubo="anello", faccia="LAT±Y", tipo="foro boccola", centro=0, quota="asse", d=D.foro_tubo))
    L.append(dict(tubo="tutti", nota="CORDONE interno sulla faccia LAT +Y (lontano da piastra e spalle) — orientare in macchina, marcare 'W'"))
    L.append(dict(tubo="orizzontali", faccia="INF", tipo="foro drenaggio", d=10, nota="a 30 mm dalle estremità"))
    L.append(dict(piastra=D.nodo, nota=f"foro boccola Ø{D.foro_piastra} (2), scarichi Ø{2*D.r_scarico} negli spigoli concavi, smussi 2×45° in punta, kerf compensato dal terzista"))
    return L


# --------------------------------------------------------------------------- main
VARIANTI = [
    Disegno(nodo="PA-A", wP=60, c=5, ),             # proposta Laser (D1)
    Disegno(nodo="PA-A", wP=61, c=5),               # e2 ≥ 1,2·d0 col foro Ø21,2 (Capomastro)
    Disegno(nodo="PA-A", wP=54, c=0),               # riserva (Strutturista D1)
    Disegno(nodo="PA-B", wP=68, c=0, stacco=1.6, asola_foro2=0.8),
]


def nome(D):
    return f"{D.nodo}{int(D.wP)}" + (f"-off{D.c:g}" if D.c else "")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sintesi = {}
    for D in VARIANTI:
        od = OUT / nome(D); od.mkdir(exist_ok=True)
        casi = []
        for ta, tm, z in itertools.product(TUBI, TUBI, ZINCO):
            r, n = collaudo(D, ta, tm, z, percorso=(tm.nome == "nom"))
            casi.append(r)
        n0 = costruisci(D, TUBI[0], TUBI[0])
        reg = regole_disegno(D, n0["info"])
        npass = sum(c["esito"] == "PASSA" for c in casi)
        falliti = [c for c in casi if c["esito"] != "PASSA"]
        res = dict(disegno=asdict(D), regole=reg, casi_totali=len(casi), passa=npass,
                   falliti=falliti, casi=casi, info=n0["info"])
        (od / "collaudo.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
        (od / "lavorazioni.json").write_text(json.dumps(lavorazioni(D, n0["info"]), indent=1, ensure_ascii=False))
        # uscite del caso nominale (piastra appesa)
        nn = dict(n0)
        cp = (D.foro_piastra - D.d_boccola) / 2
        nn["piastra"] = Pos(0, 0, -cp) * n0["piastra"]
        zb2 = n0["zmh"]
        nn["boccole"] = [boccola(D, 0, 0, 0), boccola(D, 0, zb2, 0)]
        v1.esporta(nn, od)
        v1.render(nn, od, f"{nome(D)} v0.2 — TUB 80×80×2,5, piastra {D.tP:g}, boccola 20×4 L79")
        rn = next(c for c in casi if c["anello"] == "nom" and c["montante"] == "nom" and c["zinco"] == 0)
        v1.sezione(nn, od, f"{nome(D)} v0.2 (nominale, piastra appesa alla boccola)",
                   f"{npass}/{len(casi)} casi PASSA\nstacco a regime {rn['stacco_a_regime_mm']} mm · corsa bullone {rn['corsa_bullone_mm']}"
                   + (f" · corsa ganci {rn.get('corsa_ganci_mm')}" if D.nodo == "PA-A" else ""))
        sintesi[nome(D)] = dict(passa=f"{npass}/{len(casi)}", regole=reg,
                               falliti=[(c["anello"], c["montante"], c["zinco"],
                                         {k: c[k] for k in ("boccola2_entra", "stacco_a_regime_mm", "finestra_pokayoke_mm",
                                                            "corsa_bullone_mm") if k in c},
                                         c.get("corsa_ganci_mm"), c.get("D3_bullone_prima_dei_ganci"),
                                         max(c["interf_finale"].values()), c.get("percorso_max_mm3"))
                                        for c in falliti][:12])
        print(nome(D), sintesi[nome(D)]["passa"], json.dumps(reg, ensure_ascii=False))
        for f in sintesi[nome(D)]["falliti"]:
            print("   FALLITO", f)
    (OUT / "sintesi.json").write_text(json.dumps(sintesi, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
