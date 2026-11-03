"""
Generatore di giunti per tubo-laser — v0.1
==========================================

Giunto a T / a Y fra un tubo CORRENTE (asse X) e un tubo RAMO (inclinato di `alfa`
rispetto al corrente, nel piano XZ), con:

  - taglio a "bocca di pesce" (coping) del ramo sulla superficie esterna del corrente
  - 2 LINGUETTE (tab) ricavate dalla parete del ramo, sui fianchi ±Y, che entrano in
    2 ASOLE (slot) tagliate nella parete superiore del corrente
  - 1 BULLONE di sicurezza lungo Y che attraversa il corrente e le due linguette
    (stessa logica dei nodi del kit sauna: tab-and-slot + 1 bullone inox)

Tutto è "taglio su parete di tubo" → realizzabile da un laser-tubo (TubesT/CypTube,
Lantek, Almacam ...) partendo dallo STEP. Zero saldatura.

Sezioni supportate: "tondo" e "quadro" (per corrente e ramo, combinabili).
v0.1: tubo quadro con spigoli vivi (niente raggio di piega), alfa in [30°, 90°].

Uscite in output/<nome>/:
  corrente.step, ramo.step, assieme.step (+ .stl)
  dima_ramo.pdf/.svg      sviluppo 1:1 del ramo (da avvolgere sul tubo)
  dima_corrente.pdf/.svg  sviluppo 1:1 del corrente con asole e fori
  render.png              vista 3D di controllo
  report.json             parametri, volumi, interferenza, avvisi

Uso:
  .venv/bin/python giunti.py --preset sauna_50_su_60
  .venv/bin/python giunti.py --preset tondo_42_su_60_y60
  .venv/bin/python giunti.py --tutti
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict, field
from pathlib import Path

import numpy as np
from build123d import (Align, Box, Cylinder, Pos, Rot, export_step, export_stl,
                       Compound)

QUI = Path(__file__).resolve().parent
MIN = (Align.CENTER, Align.CENTER, Align.MIN)


# --------------------------------------------------------------------------- parametri
@dataclass
class Tubo:
    sezione: str          # "tondo" | "quadro"
    D: float              # diametro esterno (tondo) o lato esterno (quadro), mm
    s: float              # spessore parete, mm

    @property
    def r(self) -> float:  # raggio / semilato esterno
        return self.D / 2


@dataclass
class Giunto:
    nome: str
    corrente: Tubo
    ramo: Tubo
    alfa: float = 90.0            # angolo ramo/corrente, gradi
    gioco: float = 0.2            # gioco linguetta/asola per lato, mm (laser ~0.1-0.3)
    d_bullone: float = 8.0        # foro bullone, mm (M8 → 8.5 reale; qui foro = d)
    margine_bullone: float = 2.0  # distanza min foro ↔ parete interna corrente, mm
    bordo: float | None = None    # materiale sotto il foro nella linguetta (default = d)
    w_linguetta: float | None = None  # larghezza linguetta (default 60% luce interna ramo)
    L_corrente: float | None = None
    L_ramo: float | None = None
    avvisi: list = field(default_factory=list)


PRESET = {
    # kit sauna (variante ferro): sottostruttura TUB 50x50x2 su primario TUB 60x60x3
    "sauna_50_su_60": Giunto("sauna_50_su_60", Tubo("quadro", 60, 3), Tubo("quadro", 50, 2),
                             alfa=90, d_bullone=8.5),
    # tondo commerciale EN 10219: Ø42,4x2 su Ø60,3x2,9 a 90°
    "tondo_42_su_60_t": Giunto("tondo_42_su_60_t", Tubo("tondo", 60.3, 2.9), Tubo("tondo", 42.4, 2.0),
                               alfa=90, d_bullone=6.5),
    # stesso, a Y 60° (controvento / puntone)
    "tondo_42_su_60_y60": Giunto("tondo_42_su_60_y60", Tubo("tondo", 60.3, 2.9), Tubo("tondo", 42.4, 2.0),
                                 alfa=60, d_bullone=6.5),
    # tondo su quadro (montante tondo su cordolo quadro)
    "tondo_42_su_quadro_60": Giunto("tondo_42_su_quadro_60", Tubo("quadro", 60, 3), Tubo("tondo", 42.4, 2.0),
                                    alfa=90, d_bullone=8.5),
}


# --------------------------------------------------------------------------- geometria analitica
class Geo:
    """Tutte le relazioni analitiche del giunto (servono sia ai solidi che alle dime)."""

    def __init__(self, g: Giunto):
        self.g = g
        a = math.radians(g.alfa)
        self.sa, self.ca = math.sin(a), math.cos(a)
        self.R, self.sm = g.corrente.r, g.corrente.s
        self.r, self.sr = g.ramo.r, g.ramo.s
        self.c = g.gioco
        self.d = g.d_bullone
        self.bordo = g.bordo if g.bordo is not None else g.d_bullone
        luce = 2 * (self.r - self.sr)
        self.w = g.w_linguetta if g.w_linguetta is not None else round(0.6 * luce, 1)
        self.Lm = g.L_corrente or round(4 * self.R + 2 * (self.r / self.sa) + 40)
        self.Lb = g.L_ramo or round(self.R / self.sa + 5 * self.r + 30)
        self._dimensiona()

    # superficie esterna / interna del corrente in funzione di y (z della parete superiore)
    def z_est(self, y):
        if self.g.corrente.sezione == "tondo":
            return math.sqrt(max(self.R**2 - y**2, 0.0))
        return self.R

    def z_int(self, y):
        Ri = self.R - self.sm
        if self.g.corrente.sezione == "tondo":
            return math.sqrt(max(Ri**2 - y**2, 0.0))
        return Ri

    def y_parete_laterale(self, z):
        """|y| della parete esterna del corrente alla quota z (dove passa il bullone)."""
        if self.g.corrente.sezione == "tondo":
            return math.sqrt(max(self.R**2 - z**2, 0.0))
        return self.R

    def _dimensiona(self):
        g, av = self.g, self.g.avvisi
        r, sr, R, sm, c = self.r, self.sr, self.R, self.sm, self.c
        # la linguetta (parete ramo a |y|≈r) deve stare dentro la luce del corrente
        if r + c >= R - sm - 0.5:
            av.append(f"RAMO TROPPO LARGO: semilarghezza ramo {r}+gioco >= luce interna corrente "
                      f"{R - sm}. Linguette sui fianchi impossibili → serve variante linguette nel piano.")
        if self.w / 2 >= r - sr:
            av.append("linguetta più larga della luce del ramo: ridotta")
            self.w = round(1.2 * (r - sr), 1)
        # quota del bullone: sotto la parete interna del corrente, nel punto dove passa la linguetta
        zi = self.z_int(r + c)
        self.z0 = zi - self.d / 2 - g.margine_bullone
        self.u_b = self.z0 / self.sa
        self.x0 = self.u_b * self.ca
        self.u_min = self.u_b - self.d / 2 - self.bordo
        if self.u_min <= 1.0:
            av.append(f"linguetta troppo corta (u_min={self.u_min:.1f}): ridurre d_bullone o bordo")
        # lunghezza bullone consigliata: larghezza esterna corrente alla quota z0 + rondelle/dado
        yw = self.y_parete_laterale(self.z0)
        Lb = 2 * yw + 2 * 1.6 + 0.8 * self.d + 2
        self.yw = yw
        self.L_bullone = int(math.ceil(Lb / 5.0) * 5)
        # lunghezza linguetta (dalla superficie esterna del corrente al fondo linguetta)
        self.L_linguetta = self.z_est(r) - self.u_min * self.sa

    # punto locale ramo (a, y, u) → globale
    def glob(self, a, y, u):
        return (a * self.sa + u * self.ca, y, -a * self.ca + u * self.sa)

    def loc(self, x, z):
        return (x * self.sa - z * self.ca, x * self.ca + z * self.sa)  # (a, u)

    def u_coping(self, a, y):
        """u dove la generatrice (a, y) del ramo incontra la superficie esterna del corrente."""
        return (self.z_est(y) + a * self.ca) / self.sa

    def in_parete_ramo_cresciuta(self, a, y):
        r, sr, c = self.r, self.sr, self.c
        if self.g.ramo.sezione == "tondo":
            q = a * a + y * y
            return ((r - sr - c) ** 2 <= q) & (q <= (r + c) ** 2)
        fuori = (np.abs(a) <= r + c) & (np.abs(y) <= r + c)
        dentro = (np.abs(a) < r - sr - c) & (np.abs(y) < r - sr - c)
        return fuori & ~dentro


# --------------------------------------------------------------------------- solidi
def _tubo_z(t: Tubo, L, z0=0.0, cresci=0.0):
    """Tubo lungo Z da z0 a z0+L. cresci>0 → parete ingrossata di `cresci` per lato (taglierina asola)."""
    ro, ri = t.r + cresci, t.r - t.s - cresci
    if t.sezione == "tondo":
        s = Cylinder(ro, L, align=MIN) - Cylinder(ri, L + 2, align=MIN).moved(Pos(0, 0, -1))
    else:
        s = Box(2 * ro, 2 * ro, L, align=MIN) - Box(2 * ri, 2 * ri, L + 2, align=MIN).moved(Pos(0, 0, -1))
    return s.moved(Pos(0, 0, z0))


def _pieno_z(t: Tubo, L, z0=0.0):
    if t.sezione == "tondo":
        s = Cylinder(t.r, L, align=MIN)
    else:
        s = Box(2 * t.r, 2 * t.r, L, align=MIN)
    return s.moved(Pos(0, 0, z0))


def costruisci(G: Geo):
    g = G.g
    beta = 90.0 - g.alfa
    a_corr = Rot(0, 90, 0)          # Z → X
    a_ramo = Rot(0, beta, 0)        # Z → direzione ramo

    # corrente
    corrente = a_corr * _tubo_z(g.corrente, G.Lm, -G.Lm / 2)
    M_pieno = a_corr * _pieno_z(g.corrente, G.Lm + 200, -(G.Lm + 200) / 2)

    # ramo pieno da u=0 (asse corrente) a Lb
    ramo_full = a_ramo * _tubo_z(g.ramo, G.Lb, 0.0)

    # box linguette in locale: |a|<=w/2, u>=u_min
    H = G.Lb - G.u_min
    box_tab = a_ramo * Box(G.w, 4 * G.r + 20, H, align=MIN).moved(Pos(0, 0, G.u_min))
    linguette = ramo_full & box_tab & M_pieno
    ramo = (ramo_full - M_pieno) + linguette

    # asole nel corrente: parete ramo ingrossata del gioco ∩ box linguette ingrossato
    box_tab_g = a_ramo * Box(G.w + 2 * G.c, 4 * G.r + 20, H + G.c,
                             align=MIN).moved(Pos(0, 0, G.u_min - G.c))
    taglierina = (a_ramo * _tubo_z(g.ramo, G.Lb + G.c, G.u_min - G.c, cresci=G.c)) & box_tab_g
    corrente = corrente - taglierina

    # foro bullone lungo Y
    foro = Pos(G.x0, 0, G.z0) * Rot(90, 0, 0) * Cylinder(G.d / 2, 4 * G.R + 40)
    corrente = corrente - foro
    ramo = ramo - foro
    return corrente, ramo


# --------------------------------------------------------------------------- dime 1:1
def _perimetro(t: Tubo, n=1440, partenza="a+"):
    """Punti (s, p, q) sul perimetro esterno della sezione. Per il ramo (p,q)=(a,y); per il
    corrente (p,q)=(y,z) con partenza in cima."""
    r = t.r
    if t.sezione == "tondo":
        th = np.linspace(0, 2 * np.pi, n, endpoint=False)
        return r * th, r * np.cos(th), r * np.sin(th)
    P = 8 * r
    s = np.linspace(0, P, n, endpoint=False)
    p, q = np.empty_like(s), np.empty_like(s)
    for i, si in enumerate(s):       # parte da (p=r, q=0), giro antiorario
        if si < r:
            p[i], q[i] = r, si
        elif si < 3 * r:
            p[i], q[i] = r - (si - r), r
        elif si < 5 * r:
            p[i], q[i] = -r, r - (si - 3 * r)
        elif si < 7 * r:
            p[i], q[i] = -r + (si - 5 * r), -r
        else:
            p[i], q[i] = r, -r + (si - 7 * r)
    return s, p, q


def _figura_1a1(larg_mm, alt_mm):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(larg_mm / 25.4, alt_mm / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, larg_mm)
    ax.set_ylim(0, alt_mm)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax, plt


def _scala(ax, x, y):
    ax.plot([x, x + 50], [y, y], "k-", lw=1.2)
    for xx in (x, x + 50):
        ax.plot([xx, xx], [y - 2, y + 2], "k-", lw=1.2)
    ax.text(x + 25, y + 3, "50 mm — verifica stampa al 100%", ha="center", fontsize=6)


def dima_ramo(G: Geo, out: Path):
    g = G.g
    s, a, y = _perimetro(g.ramo)
    P = s[-1] + (s[1] - s[0])
    tab = np.abs(a) <= G.w / 2
    u_cop = np.array([G.u_coping(ai, yi) for ai, yi in zip(a, y)])
    u_cut = np.where(tab, G.u_min, u_cop)
    u_lo, u_hi = u_cut.min() - 15, u_cop.max() + 40
    m = 15
    W, Hh = P + 2 * m, (u_hi - u_lo) + 2 * m + 12
    fig, ax, plt = _figura_1a1(W, Hh)
    X = lambda ss: ss + m
    Y = lambda uu: uu - u_lo + m + 12
    # contorno di taglio (chiuso: linea di taglio + bordo superiore a u_hi)
    xs = np.concatenate([X(s), [X(P)], [X(P)], [X(0)], [X(0)]])
    ys = np.concatenate([Y(u_cut), [Y(u_cut[0])], [Y(u_hi)], [Y(u_hi)], [Y(u_cut[0])]])
    ax.plot(xs, ys, "k-", lw=0.6)
    ax.plot(X(s), Y(u_cop), color="0.6", lw=0.4, ls="--")  # linea coping (riferimento)
    # fori bullone sulle linguette: a=0, y=±r
    for yy in (G.r, -G.r):
        k = np.argmin(np.abs(a) + np.abs(y - yy))
        ax.add_patch(plt.Circle((X(s[k]), Y(G.u_b)), G.d / 2, fill=False, lw=0.6))
    # spigoli del quadro / generatrici
    if g.ramo.sezione == "quadro":
        for k in range(1, 8, 2):
            ax.plot([X(k * G.r)] * 2, [Y(u_lo + 10), Y(u_hi)], color="0.75", lw=0.3, ls=":")
    ax.text(X(0), Y(u_hi) + 3,
            f"DIMA RAMO {g.nome} — {g.ramo.sezione} {g.ramo.D}x{g.ramo.s} su {g.corrente.sezione} "
            f"{g.corrente.D}x{g.corrente.s}, α={g.alfa}° — avvolgere sull'esterno, giunzione = linea verticale",
            fontsize=5)
    _scala(ax, m, 6)
    for ext in ("pdf", "svg"):
        fig.savefig(out / f"dima_ramo.{ext}")
    plt.close(fig)


def dima_corrente(G: Geo, out: Path):
    g = G.g
    # perimetro corrente parametrizzato da (y,z), partenza in cima (y=0, z=R)
    if g.corrente.sezione == "tondo":
        n = 2400
        ph = np.linspace(-np.pi, np.pi, n)
        sp, yp, zp = G.R * ph, G.R * np.sin(ph), G.R * np.cos(ph)
    else:
        s0, p, q = _perimetro(g.corrente, n=3200)
        # ruoto: voglio partenza in cima (y=0,z=R); _perimetro parte da (p=R,q=0) → z=p, y=q
        zp, yp = p, q
        sp = np.where(s0 > 4 * G.R, s0 - 8 * G.R, s0)
        o = np.argsort(sp)
        sp, yp, zp = sp[o], yp[o], zp[o]
    half_x = G.w / 2 / G.sa + G.R + 30
    xg = np.linspace(-half_x, half_x, 1400)
    XX, SS = np.meshgrid(xg, sp)
    YY = np.broadcast_to(yp[:, None], XX.shape)
    ZZ = np.broadcast_to(zp[:, None], XX.shape)
    A, U = G.loc(XX, ZZ)
    mask = (np.abs(A) <= G.w / 2 + G.c) & (U >= G.u_min - G.c) & G.in_parete_ramo_cresciuta(A, YY)
    P = sp.max() - sp.min()
    m = 15
    W, Hh = 2 * half_x + 2 * m, P + 2 * m + 12
    fig, ax, plt = _figura_1a1(W, Hh)
    X = lambda xx: xx + half_x + m
    Y = lambda ss: ss - sp.min() + m + 12
    ax.contour(X(XX), Y(SS), mask.astype(float), levels=[0.5], colors="k", linewidths=0.6)
    ax.plot([X(-half_x), X(half_x), X(half_x), X(-half_x), X(-half_x)],
            [Y(sp.min()), Y(sp.min()), Y(sp.max()), Y(sp.max()), Y(sp.min())], color="0.7", lw=0.3)
    ax.plot([X(-half_x), X(half_x)], [Y(0), Y(0)], color="0.6", lw=0.3, ls="-.")  # generatrice in cima
    # fori bullone: (x0, ±yw, z0) sulla parete esterna
    for sgn in (1, -1):
        if g.corrente.sezione == "tondo":
            sb = G.R * math.atan2(sgn * G.yw, G.z0)
        else:
            sb = sgn * (G.R + (G.R - G.z0))
        ax.add_patch(plt.Circle((X(G.x0), Y(sb)), G.d / 2, fill=False, lw=0.6))
    ax.text(X(-half_x), Y(sp.max()) + 3,
            f"DIMA CORRENTE {g.nome} — asole e fori; linea -. = generatrice superiore (asse ramo a x=0)",
            fontsize=5)
    _scala(ax, m, 6)
    for ext in ("pdf", "svg"):
        fig.savefig(out / f"dima_corrente.{ext}")
    plt.close(fig)


# --------------------------------------------------------------------------- render di controllo
def render(corrente, ramo, out: Path, titolo: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(12, 6))
    viste = [(25, -60, "assonometria"), (5, -90, "fronte (piano del giunto)"), (60, 0, "dall'alto/fianco")]
    mesh = []
    for sh, col in ((corrente, "#8aa1b4"), (ramo, "#d08c4f")):
        v, t = sh.tessellate(0.3)
        V = np.array([(p.X, p.Y, p.Z) for p in v])
        mesh.append((V[np.array(t)], col))
    allv = np.concatenate([m[0].reshape(-1, 3) for m in mesh])
    lo, hi = allv.min(0), allv.max(0)
    ctr, span = (lo + hi) / 2, (hi - lo).max() / 2
    for i, (el, az, nome) in enumerate(viste):
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        for tri, col in mesh:
            pc = Poly3DCollection(tri, facecolor=col, edgecolor="none", alpha=1.0)
            pc.set_facecolor(col)
            ax.add_collection3d(pc)
        for k, f in enumerate((ax.set_xlim, ax.set_ylim, ax.set_zlim)):
            f(ctr[k] - span, ctr[k] + span)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(el, az)
        ax.set_title(nome, fontsize=9)
        ax.set_axis_off()
    fig.suptitle(titolo, fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "render.png", dpi=110)
    plt.close(fig)


def render_spaccato(corrente, ramo, G: Geo, out: Path):
    """Sezione col piano y = r - s/2 (taglia a metà la linguetta +Y): mostra linguetta, asola e bullone."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from build123d import Plane
    fig, ax = plt.subplots(figsize=(7, 6))
    yc = G.r - G.sr / 2
    for sh, col in ((corrente, "#8aa1b4"), (ramo, "#d08c4f")):
        sez = sh & Box(G.Lm + 50, 0.01, 4 * G.R + 4 * G.Lb).moved(Pos(0, yc, 0))
        if sez is None:
            continue
        sez = Compound(children=list(sez.solids()))
        v, t = sez.tessellate(0.1)
        V = np.array([(p.X, p.Z) for p in v])
        for tri in t:
            ax.fill(V[list(tri), 0], V[list(tri), 1], color=col, lw=0)
    ax.add_patch(plt.Circle((G.x0, G.z0), G.d / 2, fill=False, color="r", lw=1))
    ax.set_aspect("equal")
    ax.set_xlim(-G.R - 2 * G.r, G.R + 2 * G.r)
    ax.set_ylim(-G.R - 5, G.R + 2.5 * G.r)
    ax.set_title(f"Spaccato y={yc:.1f} mm (linguetta +Y) — grigio corrente, arancio ramo, rosso bullone",
                 fontsize=8)
    ax.grid(alpha=0.2)
    fig.savefig(out / "spaccato.png", dpi=120)
    plt.close(fig)


# --------------------------------------------------------------------------- main
def genera(g: Giunto) -> dict:
    out = QUI / "output" / g.nome
    out.mkdir(parents=True, exist_ok=True)
    G = Geo(g)
    corrente, ramo = costruisci(G)
    interf = corrente & ramo
    v_interf = interf.volume if interf is not None else 0.0
    export_step(corrente, str(out / "corrente.step"))
    export_step(ramo, str(out / "ramo.step"))
    assieme = Compound(children=[corrente, ramo])
    export_step(assieme, str(out / "assieme.step"))
    export_stl(corrente, str(out / "corrente.stl"))
    export_stl(ramo, str(out / "ramo.stl"))
    dima_ramo(G, out)
    dima_corrente(G, out)
    render(corrente, ramo, out, f"{g.nome}: {g.ramo.sezione} {g.ramo.D}x{g.ramo.s} su "
                                f"{g.corrente.sezione} {g.corrente.D}x{g.corrente.s}, α={g.alfa}°")
    render_spaccato(corrente, ramo, G, out)
    rep = {
        "giunto": asdict(g),
        "derivati_mm": {
            "larghezza_linguetta": G.w, "lunghezza_linguetta_sotto_superficie": round(G.L_linguetta, 2),
            "quota_bullone_z0": round(G.z0, 2), "x_bullone": round(G.x0, 2),
            "fondo_linguetta_u_min": round(G.u_min, 2), "bullone_consigliato": f"M{int(G.d)} x {G.L_bullone}",
            "L_corrente": G.Lm, "L_ramo": G.Lb,
        },
        "verifiche": {
            "volume_corrente_mm3": round(corrente.volume, 1),
            "volume_ramo_mm3": round(ramo.volume, 1),
            "interferenza_mm3": round(v_interf, 4),
            "esito": "OK" if v_interf < 1e-3 and not g.avvisi else ("ATTENZIONE" if v_interf < 1e-3 else "INTERFERENZA"),
        },
        "avvisi": g.avvisi,
    }
    (out / "report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=sorted(PRESET))
    ap.add_argument("--tutti", action="store_true")
    a = ap.parse_args()
    nomi = sorted(PRESET) if a.tutti or not a.preset else [a.preset]
    for n in nomi:
        r = genera(PRESET[n])
        print(n, json.dumps(r["derivati_mm"], ensure_ascii=False), r["verifiche"], r["avvisi"])
