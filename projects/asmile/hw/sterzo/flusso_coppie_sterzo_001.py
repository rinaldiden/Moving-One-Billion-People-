#!/usr/bin/env python3
"""Genera flusso_coppie_sterzo_001.pdf: come passano forze e coppie nello sterzo di asmile #001.

Uso:  python3 flusso_coppie_sterzo_001.py
Immagini 3D: img/fusion_*.png (catturate dal documento Fusion «Asmile» con cattura_fusion/,
evidenziazioni come customGraphics temporanee, modello NON modificato, NON salvato).
Proiezioni dei punti 3D: img/fusion_*.json (coordinate vista, Retina x2).
Tutti i numeri sono calcolati qui sotto: MISURA = dal 3D o dai registri; IPOTESI = dichiarata.
"""
import json, math, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle, Polygon, Arc
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "img")
OUT = os.path.join(HERE, "flusso_coppie_sterzo_001.pdf")

# ---------------------------------------------------------------- dati
POLE_PAIRS = 7                 # 14 poli (mcconf si_motor_poles=14)
FLUX = 0.004918                # Wb, calibrazione 11/11 (xml vecchio: 0.00503688)
FLUX_OLD = 0.00503688
KT = 1.5 * POLE_PAIRS * FLUX   # Nm/A
KT_KV = 8.27 / 190             # Nm/A, formula pratica da 190 KV (0.0435)
KT_HI = 1.5 * POLE_PAIRS * FLUX_OLD
I_MAX = 80                     # A, tetto Daniele, max 5 s
R5, R20 = 5, 20
ETA = 0.90                     # IPOTESI rendimento riduttore
ETA_LO, ETA_HI = 0.85, 0.95
ARM = 0.325                    # m, manubrio 650 mm -> manopola
G = 9.81

def t_col(I, ratio=R5, kt=KT, eta=ETA):
    return I * kt * ratio * eta

def kg(T):
    return T / ARM / G

# prove reali 12-13/11 (REGISTRO_20261112.md)
PROVE = [  # (A min, A max, etichetta, esito)
    (7, 10, "a terra, senza persona", "gira"),
    (11, 19, "senza persona, Daniele sale", "gira"),
    (30, 30, "Daniele seduto, fermo", "STALLO"),
    (45, 45, "Daniele seduto, fermo", "a strappi"),
    (60, 60, "Daniele seduto, fermo", "arriva"),
]

# geometria dal 3D (documento Fusion «Asmile», cm -> m)  MISURA
R_WHEEL = 0.266          # raggio esterno pneumatico 20" (cilindro r=26,60 cm)
R_RIM = 0.200
WHEEL_W = 0.060          # larghezza ruota (bounding box 6,0 cm)
KP_X, WHEEL_X = 0.400, 0.463   # perno fuso (asse z r=1,75 cm a x=40) e piano medio ruota
SCRUB = WHEEL_X - KP_X   # 0.063 m offset laterale perno-impronta
TRACK = 2 * WHEEL_X      # carreggiata ~0.93 m
WHEELBASE = 1.15         # asse ant y=0, mozzo post y=-115 cm
COL = (0.0, 0.055)       # asse piantone (x,y)
PITMAN = (0.051, 0.121, 0.0805)   # snodo sferico sul piantone
KNUCKLE_BALL = (0.400, 0.155, 0.002)
MOTOR_AX_X, MOTOR_AX_Z = 0.0185, 0.105   # asse motore (orizzontale, lungo y)
# leveraggio piantone -> fuso (in pianta, al centro)
def _arm(c, b, k):
    u = np.array([k[0] - b[0], k[1] - b[1]]); u /= np.linalg.norm(u)
    r = np.array([b[0] - c[0], b[1] - c[1]])
    return abs(r[0] * u[1] - r[1] * u[0]), u
ARM_COL, _u = _arm(COL, PITMAN, KNUCKLE_BALL)
_r = np.array([0.0, KNUCKLE_BALL[1]])
ARM_KP = abs(_r[0] * _u[1] - _r[1] * _u[0])
I_LINK = ARM_KP / ARM_COL       # ~2.5: il piantone gira ~2.5 volte l'angolo ruota

# ipotesi carichi e gomma
M_VEH, M_PERS = 35.0, 80.0           # kg IPOTESI
X_VEH, X_PERS = 0.55, 0.75           # m dietro l'asse anteriore IPOTESI
P_TYRE = 2.5e5                       # Pa IPOTESI (2,5 bar)
MU = 0.8                             # IPOTESI gomma-asfalto
T_PN = 0.015                         # m IPOTESI avancorsa pneumatica in marcia

def front_load(with_person=True):
    m = M_VEH * (WHEELBASE - X_VEH) / WHEELBASE
    if with_person:
        m += M_PERS * (WHEELBASE - X_PERS) / WHEELBASE
    return m / 2 * G   # N per ruota

N_SEAT, N_EMPTY = front_load(True), front_load(False)

def patch_a(N):
    return math.sqrt(N / P_TYRE / math.pi)

def trail(alpha_deg):          # asse passa a quota mozzo (snodo dentato coassiale al mozzo)
    return R_WHEEL * math.tan(math.radians(alpha_deg))

def lift(alpha, delta, side):
    a, dl = math.radians(alpha), math.radians(delta)
    n = np.array([0, -math.sin(a), math.cos(a)])
    th = np.linspace(0, 2 * np.pi, 8001)
    pts = np.stack([np.full_like(th, side * SCRUB), R_WHEEL * np.cos(th), R_WHEEL * np.sin(th)], 1)
    K = np.array([[0, -n[2], n[1]], [n[2], 0, -n[0]], [-n[1], n[0], 0]])
    Rm = np.eye(3) + math.sin(dl) * K + (1 - math.cos(dl)) * K @ K
    q = pts @ Rm.T
    return -(q[:, 2].min() + R_WHEEL)

def t3_kp(alpha, delta, N):   # coppia (somma 2 fusi) dal termine di gravita'; + = si oppone
    e = 0.05
    d = sum((lift(alpha, delta + e, s) - lift(alpha, delta - e, s)) / math.radians(2 * e) for s in (1, -1))
    return N * d

def static_col(alpha, N, ilink=None):
    ilink = ilink or I_LINK
    a = patch_a(N)
    t1 = 2 * (2 / 3) * MU * N * a
    t2 = 2 * MU * N * abs(trail(alpha))
    t3 = t3_kp(alpha, 10, N)
    return t1 / ilink, t2 / ilink, t3 / ilink

# angolo che spiega la misura (seduto, fermo): coppia di distacco ~9 Nm (tra 30 A stallo e 45 A a strappi)
T_MEAS = 9.0
def _fit_alpha():
    t1 = 2 * (2 / 3) * MU * N_SEAT * patch_a(N_SEAT)
    need = T_MEAS * I_LINK - t1
    t = need / (2 * MU * N_SEAT)
    return -math.degrees(math.atan(t / R_WHEEL)), t
ALPHA_FIT, TRAIL_FIT = _fit_alpha()

# ---------------------------------------------------------------- stile
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5})
A4 = (8.27, 11.69)
C_MOT, C_RID, C_COL, C_BAR, C_WHE, C_LNK = "#d62828", "#f77f00", "#3a6ea5", "#8338ec", "#2a9d8f", "#e9c46a"
INK = "#1d1d1d"

def page(title, sub=None):
    fig = plt.figure(figsize=A4)
    fig.text(0.06, 0.955, title, fontsize=17, weight="bold", color=INK)
    if sub:
        fig.text(0.06, 0.932, sub, fontsize=10, color="#555")
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.925, 0.925], color="#bbb", lw=0.8))
    return fig

def foot(fig, n):
    fig.text(0.06, 0.025, "asmile #001 · flusso delle coppie nello sterzo · 18/11/2026 · generato da hw/sterzo/flusso_coppie_sterzo_001.py",
             fontsize=7, color="#888")
    fig.text(0.94, 0.025, str(n), fontsize=8, color="#888", ha="right")

def para(fig, x, y, txt, size=9.5, w=0.88, color=INK, lh=1.45, **kw):
    """testo a capo automatico; ritorna la y sotto il paragrafo"""
    import textwrap
    chars = int(w * 8.27 * 72 / (size * 0.53))
    lines = []
    for p in txt.split("\n"):
        lines += textwrap.wrap(p, chars) or [""]
    fig.text(x, y, "\n".join(lines), fontsize=size, va="top", color=color, linespacing=lh, **kw)
    return y - len(lines) * size * lh / 72 / 11.69 - 0.006

def load_img(name):
    im = Image.open(os.path.join(IMG, f"fusion_{name}.png")).convert("RGB")
    pj = json.load(open(os.path.join(IMG, f"fusion_{name}.json")))
    W, H = im.size
    pts = {k: (v[0] / 2 * W, v[1] / 2 * H) for k, v in pj.items() if k not in ("w", "h")}
    return np.asarray(im), pts

def tag(ax, xy, txt, dxy, color, num=None):
    x, y = xy
    lab = f"{num}  {txt}" if num else txt
    ax.annotate(lab, xy=(x, y), xytext=(x + dxy[0], y + dxy[1]), fontsize=8.5, color="white", weight="bold",
                ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.35", fc=color, ec="white", lw=0.8),
                arrowprops=dict(arrowstyle="-|>", color="white", lw=1.6, shrinkA=0, shrinkB=2))

pdf = PdfPages(OUT)
pn = 0

# ================================================================ p1 copertina / in breve
pn += 1
fig = page("Sterzo di asmile #001: dove vanno forze e coppie",
           "dagli ampere del motore alla gomma sull'asfalto · per Daniele")
y = 0.90
y = para(fig, 0.06, y, "IN BREVE", size=11, weight="bold")
rows = [
    ("Motore Flipsky 6354", f"Kt = 1,5 × 7 × {FLUX*1000:.3f} mWb = {KT:.4f} Nm/A (da 190 KV: {KT_KV:.4f})"),
    ("Riduzione conica 1:5", f"× 5 × rendimento 0,9 (stimato) → {t_col(1):.3f} Nm al piantone per ogni ampere"),
    ("Manopola (manubrio 650 mm)", f"braccio 0,325 m → forza = coppia / 0,325 ;  kg = N / 9,81"),
    ("30 A (stallo, seduto)", f"{t_col(30):.1f} Nm al piantone = {kg(t_col(30)):.1f} kg su una manopola"),
    ("45 A (a strappi)", f"{t_col(45):.1f} Nm = {kg(t_col(45)):.1f} kg"),
    ("60 A (arriva)", f"{t_col(60):.1f} Nm = {kg(t_col(60)):.1f} kg"),
    ("80 A (tetto, max 5 s)", f"{t_col(80):.1f} Nm = {kg(t_col(80)):.1f} kg"),
    ("Con la 1:20 (ordinata)", f"{t_col(1,R20):.3f} Nm/A → 12 Nm a {12/t_col(1,R20):.0f} A, 14 Nm a {14/t_col(1,R20):.0f} A"),
]
for a, b in rows:
    fig.text(0.08, y, a, fontsize=9.5, weight="bold", va="top")
    fig.text(0.40, y, b, fontsize=9.5, va="top")
    y -= 0.026
y -= 0.01
y = para(fig, 0.06, y, "COSA VUOL DIRE", size=11, weight="bold")
y = para(fig, 0.06, y,
    "Da fermo, con Daniele seduto, per staccare lo sterzo servono circa 8-10 Nm al piantone "
    "(sta fra lo stallo a 30 A e i 45 A che vanno a strappi), cioè circa 3 kg di spinta su una manopola. "
    "Senza persona ne bastano 1,6-2,3 Nm. In movimento la gomma rotola e la coppia crolla.\n"
    "Con la riduzione 1:5 il motore deve stare sopra 40-45 A per questo: troppo vicino al tetto. "
    "Con la 1:20 gli stessi 12-14 Nm arrivano con 13-15 A.\n"
    "NOVITÀ dal 3D (pag. 6-7): la geometria delle ruote anteriori pesa più del motore. "
    "Il perno di ogni ruota anteriore, nel 3D, è verticale e passa dal centro della ruota (avancorsa 0). "
    "Daniele dice che oggi sulla bici l'angolo è NEGATIVO: ogni grado sposta il punto dove l'asse tocca terra di "
    f"{trail(1)*1000:.1f} mm, e da fermo la gomma deve strisciare di lato su quel braccio. "
    f"Con le ipotesi di pag. 7 i ~9 Nm misurati si spiegano con circa {ALPHA_FIT:.0f}° (avancorsa ≈ {TRAIL_FIT*1000:.0f} mm, "
    "da misurare). Portare l'angolo a 0° taglierebbe la coppia da fermo a circa un quinto (più gli attriti interni, non misurati).")
y -= 0.01
y = para(fig, 0.06, y, "NON VERIFICATO (va misurato sul pezzo)", size=11, weight="bold", color=C_MOT)
y = para(fig, 0.06, y,
    "• rapporto della conica (BOM: «da verificare»); nel 3D la scatola è solo un ingombro senza denti e l'asse del motore "
    "è spostato 18,5 mm dall'asse del piantone (in una conica pura si incontrano).\n"
    "• rendimento della riduzione (0,9 stimato) e Kt vero sotto carico (forbice 0,0435-0,0529 Nm/A).\n"
    "• angolo e avancorsa reali delle ruote anteriori (il 3D ha 0°, la bici è negativa).\n"
    f"• rapporto del leveraggio piantone→ruote: dal 3D ≈ {I_LINK:.2f} (il piantone gira {I_LINK:.1f} volte l'angolo ruota); da controllare.\n"
    "• masse, pressione gomme, attrito gomma-asfalto: ipotesi dichiarate a pag. 7.")
foot(fig, pn); pdf.savefig(fig); plt.close(fig)

# ================================================================ p2 vista 3D con catena
pn += 1
fig = page("1. Dove sono i pezzi sul 3D di asmile",
           "documento Fusion «Asmile» · colori aggiunti solo per la foto (modello non toccato)")
im, P = load_img("v_iso2")
ax = fig.add_axes([0.04, 0.42, 0.92, 0.49]); ax.imshow(im); ax.axis("off")
tag(ax, P["motore"], "motore 6354", (-230, 10), C_MOT, "1")
tag(ax, P["conica"], "scatola conica", (-170, -40), C_RID, "2")
tag(ax, (P["piantone_basso"][0], (P["piantone_basso"][1] + P["piantone_alto"][1]) / 2), "piantone", (-120, -10), C_COL, "3")
tag(ax, P["manopola_dx"], "manubrio (schema 650 mm)", (130, 40), C_BAR, "4")
tag(ax, P["pitman_dx"], "tiranti", (-60, 175), "#b08900", "5")
tag(ax, P["impronta_sx"], "impronta a terra", (160, -10), C_WHE, "6")
tag(ax, P["impronta_dx"], "impronta a terra", (150, 40), C_WHE, "6")
tag(ax, P["ruota_post"], "ruota posteriore", (-60, -230), "#555")
y = 0.40
y = para(fig, 0.06, y, "La catena, nell'ordine in cui passa la coppia:", size=10.5, weight="bold")
y = para(fig, 0.06, y,
    "1  Motore Flipsky 6354 (rosso). Asse orizzontale, lungo la bici, dietro il piantone, a 10,5 cm sopra il mozzo. "
    "Gli ampere del VESC diventano coppia: Kt ≈ 0,052 Nm/A.\n"
    "2  Scatola conica (arancio). Gira il moto di 90°: da orizzontale a verticale. Moltiplica la coppia ×5 e ne perde ~10%.\n"
    "3  Piantone (blu, Ø 48 mm, verticale nel 3D). Sopra porta camere e manubrio: la coppia del motore e quella delle mani si sommano qui.\n"
    "4  Manubrio: nel 3D non c'è, è disegnato a schema (650 mm). Serve solo a tradurre la coppia in kg sulla manopola.\n"
    f"5  Tiranti (giallo): due bracci sul piantone (≈ {ARM_COL*100:.1f} cm utili) spingono i bracci dei fusi (≈ {ARM_KP*100:.1f} cm). "
    f"Il piantone gira ≈ {I_LINK:.1f} volte più delle ruote e la coppia arriva ai fusi ×{I_LINK:.1f} (dal 3D, da controllare).\n"
    "6  Ruote anteriori 20\" (verde): asmile è un triciclo con DUE ruote sterzanti davanti. La coppia che si oppone nasce "
    "nelle due impronte a terra: torsione della gomma, strisciamento sul braccio dell'avancorsa, peso (pag. 7).\n"
    "Le linee bianche verticali sono gli assi di rotazione: piantone e perni delle ruote.")
foot(fig, pn); pdf.savefig(fig); plt.close(fig)

# ================================================================ p3 schema a blocchi
pn += 1
fig = page("2. La catena in numeri", "una formula per anello · numeri per 1 A e per i punti delle prove")
ax = fig.add_axes([0.03, 0.40, 0.94, 0.50]); ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
blocks = [
    (0.1, 7.2, "VESC\ncorrente di fase\nI  [A]", "#444"),
    (2.6, 7.2, f"MOTORE 6354\nT_m = Kt · I\nKt = 1,5·7·Φ\n= {KT:.4f} Nm/A", C_MOT),
    (5.1, 7.2, f"CONICA 1:5\nT_p = T_m · 5 · η\nη = 0,9 (stima)\n= {t_col(1):.3f} Nm/A", C_RID),
    (7.6, 7.2, "PIANTONE\ncoppia T_p\n(+ mani di\nchi guida)", C_COL),
]
for x, y0, t, c in blocks:
    ax.add_patch(FancyBboxPatch((x, y0), 2.1, 2.2, boxstyle="round,pad=0.05", fc=c, ec="none", alpha=0.92))
    ax.text(x + 1.05, y0 + 1.1, t, ha="center", va="center", color="white", fontsize=9, weight="bold")
def arr(ax, a, b, c="#333"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=16, lw=2, color=c))
for x in (2.6, 5.1, 7.6):
    arr(ax, (x - 0.38, 8.3), (x - 0.02, 8.3))
# second row
blocks2 = [
    (7.2, 3.6, f"MANOPOLA\nF = T_p / 0,325 m\nkg = F / 9,81", C_BAR),
    (4.2, 3.6, f"TIRANTI → FUSI\nT_fusi = T_p · {I_LINK:.2f}\n(leveraggio, 3D)", "#b08900"),
    (1.2, 3.6, "2 IMPRONTE A TERRA\nT1 torsione\nT2 avancorsa · T3 peso", C_WHE),
]
for x, y0, t, c in blocks2:
    ax.add_patch(FancyBboxPatch((x, y0), 2.4, 2.2, boxstyle="round,pad=0.05", fc=c, ec="none", alpha=0.92))
    ax.text(x + 1.2, y0 + 1.1, t, ha="center", va="center", color="white", fontsize=9, weight="bold")
arr(ax, (8.6, 7.1), (8.6, 5.9), C_BAR)
arr(ax, (7.6, 7.1), (5.4, 5.9))
arr(ax, (4.1, 4.7), (3.7, 4.7))
ax.text(5.0, 2.8, "la coppia del piantone deve vincere quella che nasce a terra (riportata al piantone: ÷ leveraggio)",
        ha="center", fontsize=8.5, color="#555", style="italic")
# table
cols = ["A", "T motore\n[Nm]", "T piantone\n1:5 [Nm]", "kg manopola\n1:5", "T piantone\n1:20 [Nm]", "kg manopola\n1:20"]
data = []
for I in (1, 10, 15, 20, 30, 45, 60, 80):
    data.append([f"{I}", f"{KT*I:.2f}", f"{t_col(I):.2f}", f"{kg(t_col(I)):.2f}", f"{t_col(I,R20):.1f}", f"{kg(t_col(I,R20)):.1f}"])
axt = fig.add_axes([0.06, 0.12, 0.88, 0.30]); axt.axis("off")
tb = axt.table(cellText=data, colLabels=cols, loc="upper center", cellLoc="center")
tb.auto_set_font_size(False); tb.set_fontsize(9); tb.scale(1, 1.6)
for c_ in range(6): tb[0, c_].set_height(tb[0, c_].get_height() * 1.7)
for (r, c), cell in tb.get_celld().items():
    cell.set_edgecolor("#ccc")
    if r == 0: cell.set_facecolor("#eee"); cell.set_text_props(weight="bold")
    if r > 0 and data[r - 1][0] in ("30", "45", "60"): cell.set_facecolor("#fff3e0")
    if r > 0 and data[r - 1][0] == "80": cell.set_facecolor("#fde2e2")
para(fig, 0.06, 0.10, "arancio = punti delle prove con Daniele seduto (12-13/11) · rosso = tetto 80 A per max 5 s · "
         "kg = spinta su UNA manopola (spinta+tiro con due mani: metà per mano) · 1:20 con η 0,9 ipotizzato", size=7.8, color="#555")
foot(fig, pn); pdf.savefig(fig); plt.close(fig)

# ================================================================ p4 dettaglio conica (3D + schema)
pn += 1
fig = page("3. La scatola conica da vicino", "cosa dice il 3D e come si dividono le forze sui denti")
im, P = load_img("v_det")
ax = fig.add_axes([0.04, 0.60, 0.92, 0.31]); ax.imshow(im); ax.axis("off")
tag(ax, P["motore"], "motore: asse orizzontale lungo la bici", (190, 120), C_MOT)
tag(ax, P["conica"], "scatola conica", (-200, -150), C_RID)
tag(ax, (P["piantone_basso"][0] + 30, P["piantone_basso"][1] - 330), "piantone (asse verticale)", (-250, 0), C_COL)
tag(ax, P["pitman_dx"], "snodo del tirante sul piantone", (-170, 120), "#b08900")
# schema 2D conica
ax2 = fig.add_axes([0.05, 0.27, 0.44, 0.31]); ax2.set_aspect("equal"); ax2.axis("off")
ax2.set_xlim(-6, 6); ax2.set_ylim(-4.5, 7)
ax2.add_patch(Polygon([[-0.2, 0], [4.8, 0.9], [4.8, -0.9]], closed=True, fc=C_MOT, alpha=0.25, ec=C_MOT))
ax2.add_patch(Rectangle((4.8, -1.6), 2.2, 3.2, fc=C_MOT, alpha=0.85))
ax2.text(5.9, 0, "motore", color="white", ha="center", va="center", fontsize=8, rotation=90, weight="bold")
ax2.add_patch(Polygon([[-4.5, 0.3], [4.5, 0.3], [0, 1.2]], closed=True, fc=C_RID, alpha=0.30, ec=C_RID))
ax2.plot([0, 0], [-4, 6.8], color=C_COL, lw=6, alpha=0.7, solid_capstyle="butt")
ax2.plot([-0.5, 7.2], [0, 0], "--", color=C_MOT, lw=1)
ax2.text(0.3, 6.5, "piantone", color=C_COL, fontsize=8.5, weight="bold")
ax2.add_patch(Arc((6.0, 0), 1.6, 3.8, theta1=40, theta2=320, color=C_MOT, lw=1.6))
ax2.annotate("", xy=(6.6, 1.3), xytext=(6.75, 1.0), arrowprops=dict(arrowstyle="-|>", color=C_MOT, lw=1.5))
ax2.add_patch(Arc((0, 3.2), 3.4, 1.1, theta1=200, theta2=520, color=C_COL, lw=1.6))
ax2.annotate("", xy=(1.55, 3.0), xytext=(1.6, 3.25), arrowprops=dict(arrowstyle="-|>", color=C_COL, lw=1.5))
ax2.text(2.6, -1.7, f"T_m = Kt·I\n(60 A: {KT*60:.2f} Nm)", color=C_MOT, fontsize=8, ha="center")
ax2.text(-3.9, 3.9, f"T_p = 5·η·T_m\n(60 A: {t_col(60):.1f} Nm)", color=C_COL, fontsize=8, ha="center")
ax2.text(0, -4.4, "schema: pignone sul motore (rosso), corona sul piantone (arancio)", fontsize=7.5, ha="center", color="#555")
y = 0.585
para(fig, 0.52, y,
    "Cosa si legge dal 3D (MISURA):\n"
    "• motore Ø 63 × 60 mm, asse orizzontale lungo la bici, 10,5 cm sopra il mozzo, centro 1 cm dietro il piantone;\n"
    "• piantone verticale (Ø 48 mm), cuscinetti/collari Ø 54-58 mm subito sopra la scatola;\n"
    "• scatola 92 × 88 × 78 mm, solo ingombro: dentro c'è un cilindro Ø 18 mm sull'asse motore e un anello Ø 22,75 mm "
    "sul piantone, SENZA denti → diametri e rapporto veri NON leggibili;\n"
    "• l'asse del motore passa 18,5 mm di lato all'asse del piantone. In una coppia conica pura i due assi si incontrano: "
    "o il 3D è schematico, o la riduzione è sghemba (ipoide/vite). Da guardare sul pezzo.\n\n"
    "Verso di rotazione: nella prova del 13/11 il comando «verso destra» ha fatto salire l'encoder sterzo "
    "(verso giusto, REGISTRO 13/11). Il verso dipende da che lato della corona sta il pignone: se si gira la scatola, si inverte.",
    size=8.3, w=0.43)
# forze sui denti
d1s = [0.015, 0.020, 0.025]
phi, delta1 = math.radians(20), math.atan(1 / 5)
y = 0.255
y = para(fig, 0.06, y, "Spinte sui denti (formula; diametri DA MISURARE — i valori sotto sono esempi, non misure)", size=9.5, weight="bold")
y = para(fig, 0.06, y,
    "Forza tangenziale Ft = 2·T_m / d_m (d_m = diametro medio del pignone). Pignone: radiale Fr1 = Ft·tan20°·cos δ1, assiale "
    f"Fa1 = Ft·tan20°·sin δ1, con δ1 = atan(1/5) = {math.degrees(delta1):.1f}°. Sulla corona si scambiano: la spinta assiale "
    "sul piantone (verso l'alto o il basso) è uguale alla radiale del pignone. Esempio a 60 A (T_m = "
    f"{KT*60:.2f} Nm):", size=8.5)
cells = []
for d in d1s:
    Ft = 2 * KT * 60 / d
    cells.append([f"{d*1000:.0f} mm (esempio)", f"{Ft:.0f} N", f"{Ft*math.tan(phi)*math.cos(delta1):.0f} N",
                  f"{Ft*math.tan(phi)*math.sin(delta1):.0f} N", f"{Ft*math.tan(phi)*math.cos(delta1):.0f} N"])
axt = fig.add_axes([0.06, 0.05, 0.88, 0.10]); axt.axis("off")
tb = axt.table(cellText=cells, colLabels=["d_m pignone", "Ft", "radiale\npignone", "assiale pignone\n(spinge il motore)", "assiale\nsul piantone"],
               loc="upper center", cellLoc="center")
tb.auto_set_font_size(False); tb.set_fontsize(8.5); tb.scale(1, 1.35)
for (r, c), cell in tb.get_celld().items():
    cell.set_edgecolor("#ccc")
    if r == 0: cell.set_facecolor("#eee"); cell.set_height(cell.get_height() * 1.7)
foot(fig, pn); pdf.savefig(fig); plt.close(fig)

# ================================================================ p5 grafico + tabella
pn += 1
fig = page("4. Ampere → coppia al piantone → kg sulla manopola", "linee = calcolo · fascia = incertezza Kt e rendimento · punti = prove reali 12-13/11")
ax = fig.add_axes([0.11, 0.47, 0.80, 0.40])
I = np.linspace(0, 85, 200)
for ratio, c, lab in ((R5, C_RID, "conica 1:5 (oggi)"), (R20, C_COL, "riduzione 1:20 (ordinata)")):
    lo = t_col(I, ratio, KT_KV, ETA_LO); hi = t_col(I, ratio, KT_HI, ETA_HI)
    ax.fill_between(I, lo, hi, color=c, alpha=0.15, lw=0)
    ax.plot(I, t_col(I, ratio), color=c, lw=2.4, label=lab)
ax.axhspan(8, 10, color="#999", alpha=0.18)
ax.text(84, 9, "serve da fermo, seduto\n(stima 8-10 Nm)", ha="right", va="center", fontsize=8, color="#444")
ax.axvline(80, color="#c00", lw=1, ls="--"); ax.text(79, 2, "tetto 80 A\n(max 5 s)", ha="right", fontsize=8, color="#c00")
for a0, a1, lab, es in PROVE:
    col = {"gira": "#2a9d8f", "STALLO": "#c00", "a strappi": "#f77f00", "arriva": "#2a9d8f"}[es]
    if a0 == a1:
        ax.plot(a0, t_col(a0), "o", ms=9, color=col, mec="white", zorder=5)
        ax.annotate(f"{a0} A {es}", (a0, t_col(a0)), xytext=(a0 + 2, t_col(a0) - 2.1), fontsize=8, color=col, weight="bold")
    else:
        ax.plot([a0, a1], [t_col(a0), t_col(a1)], lw=6, color=col, alpha=0.8, solid_capstyle="round", zorder=5)
        ax.annotate(f"{a0}-{a1} A {lab}", ((a0 + a1) / 2, t_col(a1)), xytext=(a1 + 3, t_col(a0) - 0.5), fontsize=7.5, color=col)
ax.set_xlim(0, 85); ax.set_ylim(0, 30)
ax.set_xlabel("corrente del motore (VESC) [A]"); ax.set_ylabel("coppia al piantone [Nm]")
ax.grid(alpha=0.3); ax.legend(loc="upper left", fontsize=8.5, frameon=False)
ax2 = ax.twinx(); ax2.set_ylim(0, kg(30)); ax2.set_ylabel("kg su una manopola (braccio 0,325 m)")
fig.text(0.11, 0.405, f"Fascia: Kt da {KT_KV:.4f} (da 190 KV) a {KT_HI:.4f} Nm/A (flux vecchio 5,04 mWb nel file xml), rendimento 0,85-0,95. "
         "\nLinea: Kt 0,0516 (flux 4,918 mWb, calibrazione 11/11), η 0,9.", fontsize=7.8, color="#555", va="top")
cols = ["A", "Nm\npiantone 1:5", "kg\nmanopola 1:5", "fascia\n1:5 [Nm]", "Nm\npiantone 1:20", "kg\n1:20", "cosa è successo (12-13/11)"]
rows = [
    (8.5, "a terra senza persona: 7-10 A, gira"),
    (15, "senza persona, Daniele sale: 11-19 A"),
    (30, "Daniele seduto: STALLO"),
    (45, "seduto: arriva a strappi (3,3 s)"),
    (60, "seduto: arriva (3,7 s)"),
    (80, "tetto, mai oltre 5 s"),
]
data = [[f"{a:g}", f"{t_col(a):.1f}", f"{kg(t_col(a)):.1f}",
         f"{t_col(a,R5,KT_KV,ETA_LO):.1f}-{t_col(a,R5,KT_HI,ETA_HI):.1f}", f"{t_col(a,R20):.1f}", f"{kg(t_col(a,R20)):.1f}", s] for a, s in rows]
axt = fig.add_axes([0.04, 0.10, 0.92, 0.27]); axt.axis("off")
tb = axt.table(cellText=data, colLabels=cols, loc="upper center", cellLoc="center",
               colWidths=[0.05, 0.12, 0.12, 0.11, 0.13, 0.06, 0.33])
tb.auto_set_font_size(False); tb.set_fontsize(8.0); tb.scale(1, 1.6)
for (r, c), cell in tb.get_celld().items():
    cell.set_edgecolor("#ccc")
    if r == 0: cell.set_facecolor("#eee"); cell.set_text_props(weight="bold"); cell.set_height(cell.get_height() * 1.6)
para(fig, 0.06, 0.115,
    "Lettura: con la 1:5 i 8-10 Nm da fermo arrivano solo fra 35 e 45 A; la prova lo conferma (30 A stallo, 45 A a strappi). "
    f"Con la 1:20 (Kt e η uguali) 12 Nm = {12/t_col(1,R20):.0f} A, 14 Nm = {14/t_col(1,R20):.0f} A: margine largo sotto il tetto, "
    "ma il motore gira 4 volte più veloce per la stessa velocità di sterzo.", size=8.5)
foot(fig, pn); pdf.savefig(fig); plt.close(fig)

# ================================================================ p6 geometria sterzo (3D + disegno)
pn += 1
fig = page("5. Geometria dello sterzo (aggiunta richiesta da Daniele)",
           "angolo del perno ruota, avancorsa, offset laterale · misurato sul 3D, angolo reale da misurare")
for k, (name, box, ttl) in enumerate((("v_side", [0.04, 0.66, 0.45, 0.25], "di fianco (da destra)"),
                                       ("v_front", [0.51, 0.66, 0.45, 0.25], "da davanti (ruota destra)"))):
    im, P = load_img(name)
    ax = fig.add_axes(box); ax.imshow(im); ax.axis("off"); ax.set_title(ttl, fontsize=9)
    if name == "v_side":
        tag(ax, P["perno_dx"], "perno ruota (asse sterzo ruota)", (-260, -230), "#333")
        tag(ax, P["impronta_dx"], "impronta", (-200, -40), C_WHE)
    else:
        tag(ax, P["terra_perno_dx"], "asse perno a terra", (230, -30), "#333")
        tag(ax, P["impronta_dx"], "impronta", (-170, -40), C_WHE)
# disegno laterale quotato
ax = fig.add_axes([0.05, 0.27, 0.55, 0.37]); ax.set_aspect("equal"); ax.axis("off")
R = R_WHEEL * 1000; al = ALPHA_FIT
ax.add_patch(Circle((0, R), R, fill=False, lw=2.5, color="#333"))
ax.add_patch(Circle((0, R), R_RIM * 1000, fill=False, lw=1, color="#999"))
ax.plot([-420, 420], [0, 0], color="#6b4f2a", lw=3)
ax.plot([0, 0], [-40, 620], color="#888", lw=1, ls=":")
ax.text(4, 600, "verticale", fontsize=8, color="#666")
a = math.radians(al)
top = (-math.sin(a) * 340, R + math.cos(a) * 340)
gx = R * math.tan(a)
ax.plot([gx, top[0]], [0, top[1]], color=C_MOT, lw=2.2)
ax.text(top[0] + 12, top[1] - 10, f"asse perno (oggi negativo:\nesempio {al:.0f}°, da misurare)", color=C_MOT, fontsize=8, va="top")
ax.add_patch(Arc((0, R), 260, 260, theta1=90, theta2=90 - al if al < 0 else 90, color=C_MOT, lw=1.2))
ax.text(20, R + 140, f"α = {al:.0f}°", color=C_MOT, fontsize=9, weight="bold")
ax.plot(0, 0, "o", color=C_WHE, ms=8); ax.text(0, -38, "centro impronta", ha="center", fontsize=8, color=C_WHE)
ax.plot(gx, 0, "s", color=C_MOT, ms=6)
ax.annotate("", xy=(gx, -75), xytext=(0, -75), arrowprops=dict(arrowstyle="<->", color="#000"))
ax.text(gx / 2 + 40, -140, f"avancorsa t = R·tan α = {gx:.0f} mm\n(negativa: asse a terra DIETRO l'impronta)", ha="center", fontsize=8)
ax.annotate("", xy=(330, R), xytext=(330, 0), arrowprops=dict(arrowstyle="<->"))
ax.text(340, R / 2, f"R = {R:.0f} mm\n(20\", 3D)", fontsize=8)
ax.annotate("avanti →", (300, 470), fontsize=9, weight="bold")
ax.plot(0, R, "+", color="#000", ms=10)
ax.text(-410, R + 20, "lo snodo dentato è coassiale al mozzo:\nruotandolo cambia α, il perno\npassa sempre a quota mozzo", fontsize=7.5, color="#555")
ax.set_xlim(-430, 470); ax.set_ylim(-190, 640)
# disegno frontale
ax = fig.add_axes([0.62, 0.30, 0.34, 0.33]); ax.set_aspect("equal"); ax.axis("off")
ax.add_patch(Rectangle((-WHEEL_W * 500, 0), WHEEL_W * 1000, 2 * R, fill=False, lw=2, color="#333"))
ax.plot([-160, 120], [0, 0], color="#6b4f2a", lw=3)
kx = -SCRUB * 1000
ax.plot([kx, kx], [0, 600], color=C_MOT, lw=2)
ax.text(kx - 6, 610, "perno\n(verticale nel 3D)", ha="right", fontsize=7.5, color=C_MOT)
ax.annotate("", xy=(kx, -40), xytext=(0, -40), arrowprops=dict(arrowstyle="<->"))
ax.text(kx / 2, -70, f"offset laterale {SCRUB*1000:.0f} mm", ha="center", fontsize=8, va="top")
ax.plot(0, 0, "o", color=C_WHE, ms=7)
ax.text(70, 300, "ruota\ndestra", fontsize=8)
ax.text(-150, 470, "← centro bici", fontsize=8)
ax.set_xlim(-180, 140); ax.set_ylim(-120, 680)
y = 0.255
rows = [
    ("Ruota anteriore", f"20\", Ø esterno {2*R:.0f} mm (cerchio Ø {2*R_RIM*1000:.0f}), larghezza ~{WHEEL_W*1000:.0f} mm", "MISURA 3D"),
    ("Angolo perno (laterale, «caster»)", "0° nel 3D (perno verticale) · oggi NEGATIVO sulla bici (Daniele)", "da misurare"),
    ("Avancorsa (asse a terra − impronta)", f"0 mm nel 3D · {trail(-5)*1000:.0f} mm a −5°, {trail(-10)*1000:.0f} mm a −10° (R·tan α)", "calcolo"),
    ("Inclinazione frontale del perno", "0° nel 3D (perno verticale anche visto da davanti)", "MISURA 3D"),
    ("Offset laterale perno-impronta", f"{SCRUB*1000:.0f} mm (perno a x = 400, piano ruota a 463 mm)", "MISURA 3D"),
    ("Offset forcella", "non c'è forcella: fuso a sbalzo, perno passa a quota mozzo", "MISURA 3D"),
    ("Carreggiata / passo", f"{TRACK*1000:.0f} mm / {WHEELBASE*1000:.0f} mm", "MISURA 3D"),
    ("Carico per ruota anteriore", f"{N_SEAT:.0f} N ({N_SEAT/G:.0f} kg) con Daniele · {N_EMPTY:.0f} N ({N_EMPTY/G:.0f} kg) senza", "IPOTESI pag. 7"),
]
for a_, b_, c_ in rows:
    fig.text(0.06, y, a_, fontsize=8.3, weight="bold", va="top")
    fig.text(0.37, y, b_, fontsize=8.3, va="top")
    fig.text(0.94, y, c_, fontsize=7.8, va="top", ha="right", color=C_MOT if "misurare" in c_ or "IPOTESI" in c_ else "#2a9d8f")
    y -= 0.022
para(fig, 0.06, y - 0.004,
    "Nota: su un triciclo con due ruote davanti il «manubrio» non tocca direttamente le ruote: ogni ruota gira attorno al suo perno, "
    "spinta da un tirante. Gli angoli che contano sono quelli dei due perni, non quello del piantone.", size=8.2)
foot(fig, pn); pdf.savefig(fig); plt.close(fig)

# ================================================================ p7 scomposizione T1 T2 T3
pn += 1
fig = page("6. Da dove viene la coppia resistente da fermo", "tre pezzi, calcolati con ipotesi dichiarate e confrontati con la prova")
y = 0.905
y = para(fig, 0.06, y, "IPOTESI (non misure)", size=10, weight="bold", color=C_MOT)
y = para(fig, 0.06, y,
    f"• massa bici {M_VEH:.0f} kg con baricentro {X_VEH*100:.0f} cm dietro l'asse anteriore; Daniele {M_PERS:.0f} kg a {X_PERS*100:.0f} cm "
    f"(sella nel 3D a ~80 cm); passo {WHEELBASE*1000:.0f} mm dal 3D → {N_SEAT:.0f} N per ruota anteriore con Daniele, {N_EMPTY:.0f} N senza.\n"
    f"• gomma 2,5 bar → impronta = carico/pressione = {N_SEAT/P_TYRE*1e4:.1f} cm² → raggio equivalente a = {patch_a(N_SEAT)*1000:.1f} mm "
    f"({patch_a(N_EMPTY)*1000:.1f} mm senza persona). Attrito gomma-asfalto μ = 0,8.\n"
    f"• leveraggio piantone→fusi {I_LINK:.2f} dal 3D (coppia a terra ÷ {I_LINK:.2f} = coppia al piantone). Ruote libere di rotolare "
    "(il 13/11 la ruota girava sterzando: confermato).", size=8.5)
y -= 0.004
y = para(fig, 0.06, y, "I TRE PEZZI (somma delle due ruote, riportata al piantone)", size=10, weight="bold")
t1, t2, t3 = static_col(ALPHA_FIT, N_SEAT)
y = para(fig, 0.06, y,
    f"T1 torsione dell'impronta ≈ (2/3)·μ·N·a per ruota. La gomma ferma deve ruotare su se stessa. Con Daniele: "
    f"{2*(2/3)*MU*N_SEAT*patch_a(N_SEAT):.1f} Nm ai fusi → {t1:.1f} Nm al piantone. Non dipende dall'angolo.\n"
    f"T2 strisciamento sull'avancorsa ≈ μ·N·|t| per ruota. Se l'asse tocca terra a t mm dall'impronta, sterzando l'impronta deve "
    f"scivolare DI LATO (di lato la gomma non rotola). Dipende solo da |t|: −5° e +5° costano uguale da fermo.\n"
    f"L'offset laterale di {SCRUB*1000:.0f} mm invece fa muovere l'impronta in avanti/indietro: lì la ruota ROTOLA, costa poco "
    f"(resistenza al rotolamento ~{0.008*N_SEAT*SCRUB*2/I_LINK:.2f} Nm). Se però la ruota fosse frenata o bloccata, varrebbe "
    f"μ·N·{SCRUB*1000:.0f} mm = {2*MU*N_SEAT*SCRUB/I_LINK:.1f} Nm al piantone: da solo spiegherebbe la prova. Da escludere (freno anteriore? no, nel 3D il freno è dietro).\n"
    "T3 peso (si alza o si abbassa l'avantreno?). Con il perno inclinato in avanti/indietro e l'offset laterale, sterzando una ruota "
    "sale e l'altra scende della stessa quantità (±d·sin α·sin δ): il triciclo si inclina un poco ma il baricentro quasi non si muove. "
    f"Resta un piccolo abbassamento (a 10° di sterzata e α = {ALPHA_FIT:.0f}°: {1000*(lift(ALPHA_FIT,10,1)+lift(ALPHA_FIT,10,-1)):.2f} mm) "
    f"che AIUTA ad allontanarsi dal centro: {t3:+.2f} Nm al piantone, trascurabile. A 0° è zero. "
    "Il termine di peso diventa grande solo se il perno è inclinato visto DA DAVANTI (non è il caso nel 3D).", size=8.5)
y -= 0.004
y = para(fig, 0.06, y, "CONFRONTO CON LA PROVA", size=10, weight="bold")
y = para(fig, 0.06, y,
    f"Misura (seduto, fermo): ~9 Nm per staccare (30 A = 7,0 Nm stallo; 45 A = 10,5 Nm a strappi). "
    f"Il modello arriva a 9 Nm con avancorsa ≈ {TRAIL_FIT*1000:.0f} mm, cioè α ≈ {ALPHA_FIT:.0f}°. "
    f"Controprova senza persona: il modello dà {sum(static_col(ALPHA_FIT, N_EMPTY)[:2]):.1f} Nm (= {sum(static_col(ALPHA_FIT, N_EMPTY)[:2])/t_col(1):.0f} A), "
    "misurati 7-10 A a terra e 11-19 A mentre Daniele sale: stesso ordine di grandezza. "
    "Non è una misura dell'angolo: è l'angolo che renderebbe coerenti i conti. Va misurato con un inclinometro sul perno.", size=8.5)
# tabella varianti
alphas = [(ALPHA_FIT, f"{ALPHA_FIT:.0f}° stima oggi"), (-10, "−10°"), (-5, "−5°"), (0, "0°"), (5, "+5°"), (10, "+10°")]
cells = []
for al_, lab in alphas:
    a1, a2, a3 = static_col(al_, N_SEAT)
    tot = a1 + a2 + a3
    # in marcia: curva 10 km/h raggio 6 m
    ay = (10 / 3.6) ** 2 / 6
    Fy = N_SEAT / G * ay
    mz = 2 * Fy * (trail(al_) + T_PN) / I_LINK    # + = riporta al centro
    cells.append([lab, f"{trail(al_)*1000:+.0f}", f"{a1:.1f}", f"{a2:.1f}", f"{a3:+.2f}", f"{tot:.1f}", f"{kg(tot):.1f}",
                  f"{tot/t_col(1):.0f}", f"{tot/t_col(1,R20):.0f}", f"{mz:+.2f}"])
axt = fig.add_axes([0.04, 0.12, 0.92, 0.22]); axt.axis("off")
tb = axt.table(cellText=cells, colLabels=["angolo perno", "avancorsa\n[mm]", "T1\n[Nm]", "T2\n[Nm]", "T3\n[Nm]", "totale\npiantone", "kg\nmanopola",
                                         "A con\n1:5", "A con\n1:20", "in curva*\n[Nm]"],
               loc="upper center", cellLoc="center", colWidths=[0.16]+[0.093]*9)
tb.auto_set_font_size(False); tb.set_fontsize(8.2); tb.scale(1, 1.75)
for (r, c), cell in tb.get_celld().items():
    cell.set_edgecolor("#ccc")
    if r == 0: cell.set_facecolor("#eee"); cell.set_text_props(weight="bold")
    if r == 4: cell.set_facecolor("#e6f4ea")
para(fig, 0.06, 0.115,
    "Totale = da fermo con Daniele, al piantone, SENZA attriti interni (cuscinetti, snodi, scatola). "
    f"*In curva a 10 km/h su raggio 6 m: momento della gomma (forza laterale × (avancorsa + {T_PN*1000:.0f} mm di avancorsa pneumatica, IPOTESI)); "
    "+ = riporta al centro (stabile), − = porta FUORI dal centro: il motore deve tenere, come dice Daniele.", size=7.6)
foot(fig, pn); pdf.savefig(fig); plt.close(fig)

# ================================================================ p8 cosa vuol dire / cosa manca
pn += 1
fig = page("7. Cosa vuol dire e cosa manca", "per decidere: riduzione, angolo del perno, misure da fare")
y = 0.90
y = para(fig, 0.06, y, "COSA VUOL DIRE", size=11, weight="bold")
z0 = sum(static_col(0, N_SEAT))
y = para(fig, 0.06, y,
    "1. Da fermo con persona servono circa 8-10 Nm al piantone (≈ 3 kg su una manopola). Con la conica 1:5 sono 35-45 A: "
    "il motore lavora vicino al tetto e va a strappi. È quello che si è visto il 12-13/11.\n"
    "2. In movimento la gomma rotola: la torsione dell'impronta e lo strisciamento quasi spariscono e bastano pochi ampere "
    "(10 giri a vuoto il 13/11: corrente media 8-11 A, ruote a terra senza persona).\n"
    "3. Con la 1:20 (ordinata) gli stessi 12-14 Nm arrivano con 13-15 A: margine largo, ma il motore deve girare 4 volte più "
    "veloce (a 30°/s di sterzo: 100 giri/min al motore invece di 25) e serve ricalcolare i fattori negli script.\n"
    f"4. La geometria pesa almeno quanto la riduzione. Se l'angolo del perno fosse 0° (avancorsa 0), da fermo resterebbe "
    f"circa {z0:.1f} Nm (≈ {kg(z0):.1f} kg, {z0/t_col(1):.0f} A con la 1:5) + attriti interni. Lo snodo dentato coassiale al mozzo permette di "
    "cambiare l'angolo senza toccare la ruota.\n"
    "5. Il segno conta in movimento, non da fermo: un angolo positivo (+5°…+10°) costa da fermo quanto il negativo uguale, "
    "ma in marcia riporta le ruote al centro da solo. Il negativo le porta fuori: il motore deve tenere sempre, e se il "
    "motore si spegne lo sterzo tende ad andare in fondo. Per la sicurezza meglio 0° o poco positivo.", size=9)
y -= 0.01
y = para(fig, 0.06, y, "COSA NON È VERIFICATO", size=11, weight="bold", color=C_MOT)
y = para(fig, 0.06, y,
    "• Rapporto della conica: 1:5 dalla BOM «da verificare». Nel 3D non ci sono denti e gli assi sono sfalsati di 18,5 mm.\n"
    "• Rendimento della riduzione: 0,9 è una stima (una conica dritta 0,93-0,97; un ipoide o una vite molto meno).\n"
    f"• Kt: 0,0516 Nm/A dalla calibrazione (flux 4,918 mWb); da 190 KV verrebbe 0,0435 (−16%); il file xml ha ancora 5,04 mWb.\n"
    "• Angolo e avancorsa veri delle ruote anteriori (3D = 0°, bici = negativo).\n"
    f"• Leveraggio piantone→fusi {I_LINK:.2f} (dal 3D, al centro; cambia con l'angolo di sterzo).\n"
    "• Carichi, pressione gomme, μ, avancorsa pneumatica: ipotesi (pag. 7).\n"
    "• Attriti interni (cuscinetti piantone, snodi sferici, scatola): non separati dalla prova.", size=9)
y -= 0.01
y = para(fig, 0.06, y, "MISURE CHE CHIUDONO I DUBBI (semplici, senza motore acceso)", size=11, weight="bold")
y = para(fig, 0.06, y,
    "a) Conica: girare il piantone di 1 giro e contare i giri del motore (segno sul rotore) → rapporto vero. Aprire la scatola: foto dei denti, contare.\n"
    "b) Angolo del perno: inclinometro (anche quello del telefono) appoggiato sul perno, bici in piano → α e segno.\n"
    "c) Leveraggio: girare il manubrio di 20° e misurare l'angolo della ruota (goniometro o foto dall'alto).\n"
    "d) Attriti interni: ruote anteriori sollevate, chiave dinamometrica o bilancia da valigia sulla manopola → coppia a vuoto.\n"
    "e) Peso sull'avantreno: due bilance pesapersone sotto le ruote anteriori, Daniele seduto → N vero.\n"
    "f) Da fermo con Daniele: bilancia da valigia sulla manopola, motore spento → coppia vera da vincere (confronta coi 9 Nm).\n"
    "Con a-f si rifà questo PDF con numeri misurati al posto delle ipotesi.", size=9)
foot(fig, pn); pdf.savefig(fig); plt.close(fig)

pdf.close()
print("scritto", OUT)
print(f"Kt={KT:.4f}  Nm/A 1:5={t_col(1):.4f}  1:20={t_col(1,R20):.4f}  I_LINK={I_LINK:.3f} (col {ARM_COL*100:.2f} cm, fuso {ARM_KP*100:.2f} cm)")
print(f"N_seat={N_SEAT:.0f} N  N_empty={N_EMPTY:.0f} N  a={patch_a(N_SEAT)*1000:.1f} mm  alpha_fit={ALPHA_FIT:.1f} deg trail={TRAIL_FIT*1000:.0f} mm")
for al_ in (ALPHA_FIT, -10, -5, 0, 5, 10):
    print(al_, [round(v, 2) for v in static_col(al_, N_SEAT)], round(sum(static_col(al_, N_SEAT)), 2))
