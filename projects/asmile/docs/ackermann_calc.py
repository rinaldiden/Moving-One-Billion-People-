#!/usr/bin/env python3
"""
Ackermann steering geometry calculator — Asmile

Modello: cremagliera (rack) + tiranti + bracci di sterzo.

La ruota/pignone (Ø160 mm, r=80 mm) converte rotazione in
traslazione laterale della cremagliera a y = 55 mm davanti all'asse.

Coordinate (vista dall'alto):
  x = laterale (positivo a destra)
  y = longitudinale (positivo in avanti)
  Origine = centro asse anteriore
"""

import numpy as np
from scipy.optimize import brentq, minimize
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

OUT = os.path.dirname(os.path.abspath(__file__))

# ═══════════════════════════════════════════════════════════
#  PARAMETRI VEICOLO
# ═══════════════════════════════════════════════════════════
L     = 1150.0   # wheelbase [mm]
T     = 950.0    # track (contatto–contatto) [mm]
HT    = T / 2.0  # semi-track = 475 mm

# ═══════════════════════════════════════════════════════════
#  PARAMETRI MECCANISMO (fissi)
# ═══════════════════════════════════════════════════════════
Y_RACK   = 55.0    # posizione y della cremagliera (55 mm avanti asse)
R_PINION = 80.0    # raggio pignone (ruota Ø160 mm)
SA_LEN   = 160.0   # lunghezza braccio di sterzo lato ruota [mm]

# ═══════════════════════════════════════════════════════════
#  GEOMETRIA
# ═══════════════════════════════════════════════════════════
def rot2d(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s], [s, c]])


def rack_end(dx, d_rack, side):
    """Posizione attacco tirante sulla cremagliera.
    dx     = spostamento laterale rack (positivo = verso destra)
    d_rack = semi-span punti di attacco tirante sulla rack
    """
    sign = 1.0 if side == "right" else -1.0
    return np.array([sign * d_rack + dx, Y_RACK])


def sa_end(beta, delta, side):
    """Posizione attacco tirante sul braccio di sterzo.
    beta  = angolo Ackermann del braccio [rad] (dall'asse trasversale verso il retro)
    delta = angolo di sterzata della ruota [rad] (CCW positivo = svolta a sinistra)
    """
    kp_x = HT if side == "right" else -HT
    kp = np.array([kp_x, 0.0])
    # Braccio punta verso l'interno e verso il retro
    if side == "right":
        arm0 = np.array([-SA_LEN * np.cos(beta), -SA_LEN * np.sin(beta)])
    else:
        arm0 = np.array([ SA_LEN * np.cos(beta), -SA_LEN * np.sin(beta)])
    return kp + rot2d(delta) @ arm0


def trod_len(beta, d_rack, side):
    """Lunghezza tirante a ruote dritte."""
    rk = rack_end(0.0, d_rack, side)
    sa = sa_end(beta, 0.0, side)
    return np.linalg.norm(rk - sa)


def solve_delta(dx, d_rack, beta, l_tr, side):
    """Trova l'angolo sterzata per un dato spostamento rack."""
    rk = rack_end(dx, d_rack, side)

    def res(delta):
        sa = sa_end(beta, delta, side)
        return np.linalg.norm(rk - sa) - l_tr

    try:
        return brentq(res, -np.radians(60), np.radians(60))
    except ValueError:
        return np.nan


def ideal_outer(delta_inner):
    """Angolo esterno Ackermann ideale."""
    if abs(delta_inner) < 1e-10:
        return 0.0
    cot_o = 1.0 / np.tan(abs(delta_inner)) + T / L
    return np.sign(delta_inner) * np.arctan(1.0 / cot_o)


# ═══════════════════════════════════════════════════════════
#  SWEEP & COST
# ═══════════════════════════════════════════════════════════
def sweep(beta, d_rack, n=100):
    """Sweep spostamento rack, ritorna angoli."""
    l_tr = trod_len(beta, d_rack, "right")
    dx_max = R_PINION  # dx max ≈ raggio pignone (θ=90°)
    dxs = np.linspace(0, dx_max, n)

    th_pinion, d_in, d_out, d_ideal = [], [], [], []
    for dx in dxs:
        # Svolta a sinistra: bellcrank inverte → rack si muove a DESTRA
        dL = solve_delta(dx, d_rack, beta, l_tr, "left")   # interna
        dR = solve_delta(dx, d_rack, beta, l_tr, "right")  # esterna
        if np.isnan(dL) or np.isnan(dR):
            break
        th_pinion.append(np.degrees(np.arcsin(dx / R_PINION)))
        d_in.append(np.degrees(dL))
        d_out.append(np.degrees(dR))
        d_ideal.append(np.degrees(ideal_outer(dL)))

    return (np.array(th_pinion), np.array(d_in),
            np.array(d_out), np.array(d_ideal))


def cost(params):
    """Errore Ackermann cumulativo."""
    beta, d_rack = params
    if beta < np.radians(2) or beta > np.radians(50):
        return 1e6
    if d_rack < 20 or d_rack > 400:
        return 1e6
    l_tr = trod_len(beta, d_rack, "right")
    dxs = np.linspace(R_PINION * 0.05, R_PINION * 0.95, 60)
    err = 0.0
    for dx in dxs:
        dL = solve_delta(dx, d_rack, beta, l_tr, "left")
        dR = solve_delta(dx, d_rack, beta, l_tr, "right")
        if np.isnan(dL) or np.isnan(dR):
            return 1e6
        err += (dR - ideal_outer(dL)) ** 2
    return err


def cost_beta_only(beta, d_rack):
    """Errore Ackermann variando solo beta, d_rack fisso."""
    return cost([beta, d_rack])


# ═══════════════════════════════════════════════════════════
#  CALCOLO
# ═══════════════════════════════════════════════════════════
print("=" * 65)
print("  ACKERMANN CALCULATOR  —  Asmile")
print("=" * 65)
print(f"  Wheelbase              L = {L:.0f} mm")
print(f"  Track                  T = {T:.0f} mm")
print(f"  Rack y-position            = {Y_RACK:.0f} mm (avanti)")
print(f"  Raggio pignone             = {R_PINION:.0f} mm  (Ø{2*R_PINION:.0f})")
print(f"  Braccio sterzo lato ruota  = {SA_LEN:.0f} mm")
print()

geom_angle = np.degrees(np.arctan(HT / L))
print(f"  Angolo Ackermann geometrico puro: {geom_angle:.1f}°")
print()

# ── Ottimizzazione globale (beta + d_rack) ──
from scipy.optimize import differential_evolution

bounds_global = [(np.radians(5), np.radians(45)),   # beta
                 (30, 350)]                          # d_rack
res_global = differential_evolution(cost, bounds_global, seed=42,
                                     maxiter=200, tol=1e-10)
beta_g, d_rack_g = res_global.x

print(f"  ═══ OTTIMO GLOBALE (beta + d_rack liberi) ═══")
print(f"    β ottimale  = {np.degrees(beta_g):.2f}°")
print(f"    d_rack      = {d_rack_g:.1f} mm")

sa_R = sa_end(beta_g, 0.0, "right")
sa_L = sa_end(beta_g, 0.0, "left")
l_tr_g = trod_len(beta_g, d_rack_g, "right")
dx_R = abs(HT - sa_R[0])
dy_R = abs(sa_R[1])
print(f"    Tirante lunghezza     = {l_tr_g:.1f} mm")
print(f"    Attacco DX su braccio = ({sa_R[0]:.1f}, {sa_R[1]:.1f}) mm")
print(f"      ↳ dal kingpin: {dx_R:.1f} mm laterale, {dy_R:.1f} mm indietro")
print()

# ── Ottimizzazione con diversi d_rack fissi ──
print(f"  ═══ SENSIBILITÀ: β ottimale per diversi d_rack ═══")
print(f"  {'d_rack':>8}  {'β_opt':>8}  {'lat':>8}  {'long':>8}  {'l_trod':>8}  {'err_max':>8}")
print(f"  {'[mm]':>8}  {'[°]':>8}  {'[mm]':>8}  {'[mm]':>8}  {'[mm]':>8}  {'[°]':>8}")
print("  " + "-" * 56)

d_rack_values = [50, 80, 100, 120, 150, 200, 250, 300]
best_configs = {}

for dr in d_rack_values:
    from scipy.optimize import minimize_scalar
    res_b = minimize_scalar(lambda b: cost_beta_only(b, dr),
                            bounds=(np.radians(5), np.radians(45)),
                            method="bounded")
    b_opt = res_b.x
    sa = sa_end(b_opt, 0.0, "right")
    lt = trod_len(b_opt, dr, "right")
    dx_k = abs(HT - sa[0])
    dy_k = abs(sa[1])

    # Errore massimo
    _, di, do, did = sweep(b_opt, dr)
    if len(do) > 0 and len(did) > 0:
        err_max = np.max(np.abs(do - did))
    else:
        err_max = 99.9

    print(f"  {dr:>8.0f}  {np.degrees(b_opt):>8.2f}  {dx_k:>8.1f}  {dy_k:>8.1f}  {lt:>8.1f}  {err_max:>8.2f}")
    best_configs[dr] = b_opt

print()

# ── Configurazione scelta: d_rack = 80 mm (~ 1 raggio pignone) ──
D_RACK = 80.0
BETA_OPT = best_configs.get(int(D_RACK), best_configs[80])
l_tr_opt = trod_len(BETA_OPT, D_RACK, "right")

sa_opt_R = sa_end(BETA_OPT, 0.0, "right")
sa_opt_L = sa_end(BETA_OPT, 0.0, "left")
dx_opt = abs(HT - sa_opt_R[0])
dy_opt = abs(sa_opt_R[1])

print(f"  ═══ CONFIGURAZIONE SCELTA: d_rack = {D_RACK:.0f} mm ═══")
print(f"    β ottimale                    = {np.degrees(BETA_OPT):.2f}°")
print(f"    Braccio sterzo                = {SA_LEN:.0f} mm")
print(f"    Proiezione laterale (→centro) = {dx_opt:.1f} mm")
print(f"    Proiezione longitudinale (→retro) = {dy_opt:.1f} mm")
print(f"    Attacco tirante DX            = ({sa_opt_R[0]:.1f}, {sa_opt_R[1]:.1f}) mm")
print(f"    Attacco tirante SX            = ({sa_opt_L[0]:.1f}, {sa_opt_L[1]:.1f}) mm")
print(f"    Lunghezza tirante             = {l_tr_opt:.1f} mm")
print()

# Angoli a max sterzata
dx_max = R_PINION * np.sin(np.radians(45))
dL_max = solve_delta(dx_max, D_RACK, BETA_OPT, l_tr_opt, "left")
dR_max = solve_delta(dx_max, D_RACK, BETA_OPT, l_tr_opt, "right")
if not np.isnan(dL_max):
    R_min = L / np.tan(abs(dL_max)) + HT
    print(f"    A pignone 45° (dx={dx_max:.1f} mm):")
    print(f"      Ruota interna: {np.degrees(dL_max):.1f}°")
    print(f"      Ruota esterna: {np.degrees(dR_max):.1f}°  (ideale: {np.degrees(ideal_outer(dL_max)):.1f}°)")
    print(f"      Raggio min curvatura: {R_min:.0f} mm = {R_min/1000:.2f} m")

dx_max2 = R_PINION  # pignone a 90°
dL_max2 = solve_delta(dx_max2, D_RACK, BETA_OPT, l_tr_opt, "left")
dR_max2 = solve_delta(dx_max2, D_RACK, BETA_OPT, l_tr_opt, "right")
if not np.isnan(dL_max2):
    R_min2 = L / np.tan(abs(dL_max2)) + HT
    print(f"    A pignone 90° (dx={dx_max2:.1f} mm, max):")
    print(f"      Ruota interna: {np.degrees(dL_max2):.1f}°")
    print(f"      Ruota esterna: {np.degrees(dR_max2):.1f}°  (ideale: {np.degrees(ideal_outer(dL_max2)):.1f}°)")
    print(f"      Raggio min curvatura: {R_min2:.0f} mm = {R_min2/1000:.2f} m")
print()


# ═══════════════════════════════════════════════════════════
#  TABELLA ANGOLI
# ═══════════════════════════════════════════════════════════
print("=" * 65)
print("  TABELLA ANGOLI (configurazione scelta)")
print("=" * 65)
print(f"  {'θ pignone':>10}  {'Δx rack':>8}  {'δ int':>8}  {'δ ext':>8}  {'δ ideale':>8}  {'errore':>8}")
print(f"  {'[°]':>10}  {'[mm]':>8}  {'[°]':>8}  {'[°]':>8}  {'[°]':>8}  {'[°]':>8}")
print("  " + "-" * 58)

for th_p in range(0, 95, 5):
    dx = R_PINION * np.sin(np.radians(th_p))
    dL = solve_delta(dx, D_RACK, BETA_OPT, l_tr_opt, "left")
    dR = solve_delta(dx, D_RACK, BETA_OPT, l_tr_opt, "right")
    if np.isnan(dL) or np.isnan(dR):
        print(f"  {th_p:>10}  {dx:>8.1f}  {'---':>8}  {'---':>8}  {'---':>8}  {'---':>8}")
        continue
    di = ideal_outer(dL)
    err = np.degrees(dR) - np.degrees(di)
    print(f"  {th_p:>10}  {dx:>8.1f}  {np.degrees(dL):>8.1f}  {np.degrees(dR):>8.1f}"
          f"  {np.degrees(di):>8.1f}  {err:>+8.2f}")

print()
print("  + = esterna sterza TROPPO  |  − = esterna sterza POCO")
print()

# ═══════════════════════════════════════════════════════════
#  VERIFICA CONVERGENZA ACKERMANN
# ═══════════════════════════════════════════════════════════
print("  ═══ VERIFICA LINEE ACKERMANN ═══")
print("  Le prolunghe degli assi delle ruote devono convergere")
print("  sull'asse posteriore (y = -1150 mm).")
print()

for th_p in [15, 30, 45, 60]:
    dx = R_PINION * np.sin(np.radians(th_p))
    dL = solve_delta(dx, D_RACK, BETA_OPT, l_tr_opt, "left")
    dR = solve_delta(dx, D_RACK, BETA_OPT, l_tr_opt, "right")
    if np.isnan(dL) or np.isnan(dR):
        continue
    # Intersezione asse ruota interna con y = -L
    # Ruota interna (sinistra) al kingpin (-475, 0), angolo dL
    # Direzione: (sin(dL), -cos(dL))  → per angolo positivo gira a sx
    # Retta: (-475 + t*sin(dL), -t*cos(dL))
    # y = -L → t = L/cos(dL)
    t_L = L / np.cos(dL)
    x_int_L = -HT + t_L * np.sin(dL)

    t_R = L / np.cos(dR)
    x_int_R = HT + t_R * np.sin(dR)

    print(f"  θ={th_p:>2}°  int={np.degrees(dL):>5.1f}°  ext={np.degrees(dR):>5.1f}°"
          f"  → convergenza asse post: int→x={x_int_L:>+7.0f}  ext→x={x_int_R:>+7.0f}"
          f"  Δ={abs(x_int_L - x_int_R):>5.0f} mm")

print(f"  (ideale: entrambi convergono a x=0, Δ=0)")
print()


# ═══════════════════════════════════════════════════════════
#  GRAFICI
# ═══════════════════════════════════════════════════════════

# ── GRAFICO 1: Angoli sterzata ──
fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

# Configurazione ottimale
th1, di1, do1, did1 = sweep(BETA_OPT, D_RACK)

# Stima dal disegno (β ≈ 20°)
beta_dwg = np.radians(20)
th2, di2, do2, did2 = sweep(beta_dwg, D_RACK)

# Ackermann geometrico puro
beta_geom = np.radians(geom_angle)
th3, di3, do3, did3 = sweep(beta_geom, D_RACK)

ax1.set_title("Angoli di sterzata — confronto", fontsize=13, fontweight="bold")
ax1.plot(di1, did1, "k--", lw=2, label="Ackermann ideale")
ax1.plot(di1, do1, "g-", lw=2.5,
         label=f"Ottimale β={np.degrees(BETA_OPT):.1f}°")
ax1.plot(di2, do2, "r-", lw=2,
         label=f"Disegno β≈{np.degrees(beta_dwg):.0f}° (stima)")
ax1.plot(di3, do3, "b-", lw=1.5, ls="-.",
         label=f"Geometrico β={geom_angle:.1f}°")
ax1.set_xlabel("Angolo ruota INTERNA [°]", fontsize=11)
ax1.set_ylabel("Angolo ruota ESTERNA [°]", fontsize=11)
ax1.legend(fontsize=10)
ax1.grid(True, alpha=0.3)

# Errore
ax2.set_title("Errore Ackermann (δ_ext − δ_ideale)", fontsize=13, fontweight="bold")
ax2.plot(di1, do1 - did1, "g-", lw=2.5,
         label=f"Ottimale β={np.degrees(BETA_OPT):.1f}°")
ax2.plot(di2, do2 - did2, "r-", lw=2,
         label=f"Disegno β≈{np.degrees(beta_dwg):.0f}°")
ax2.plot(di3, do3 - did3, "b-", lw=1.5, ls="-.",
         label=f"Geometrico β={geom_angle:.1f}°")
ax2.axhline(0, color="k", lw=0.5)
ax2.set_xlabel("Angolo ruota INTERNA [°]", fontsize=11)
ax2.set_ylabel("Errore [°]", fontsize=11)
ax2.legend(fontsize=10)
ax2.grid(True, alpha=0.3)

fig1.tight_layout()
fig1.savefig(os.path.join(OUT, "ackermann_angles.png"), dpi=150)
print("  Salvato: ackermann_angles.png")


# ── GRAFICO 2: Vista dall'alto ──
fig2, ax3 = plt.subplots(figsize=(14, 12))
ax3.set_title("Vista dall'alto — geometria sterzo ottimale\n"
              f"(β={np.degrees(BETA_OPT):.1f}°, d_rack={D_RACK:.0f} mm)",
              fontsize=13, fontweight="bold")
ax3.set_aspect("equal")
ax3.grid(True, alpha=0.15)

# Assi
ax3.plot([-HT-80, HT+80], [0, 0], "k-", lw=1, alpha=0.4)
ax3.plot([-HT-80, HT+80], [-L, -L], "k-", lw=1, alpha=0.4)
ax3.annotate("ASSE ANT.", (HT+20, 5), fontsize=8, alpha=0.5)
ax3.annotate("ASSE POST.", (HT+20, -L+5), fontsize=8, alpha=0.5)
ax3.plot(0, -L, "k+", ms=12, mew=2)

# Rack line
ax3.plot([-HT, HT], [Y_RACK, Y_RACK], ":", color="gray", lw=1, alpha=0.5)
ax3.annotate(f"rack y={Y_RACK:.0f}", (HT+5, Y_RACK), fontsize=8, color="gray")

# Kingpins
for side, kp_x, lbl in [("right", HT, "KP dx"), ("left", -HT, "KP sx")]:
    ax3.plot(kp_x, 0, "ks", ms=9, zorder=5)
    offset = (10, 10) if side == "right" else (-60, 10)
    ax3.annotate(lbl, (kp_x, 0), textcoords="offset points",
                 xytext=offset, fontsize=9)

# Bellcrank pivot
ax3.plot(0, Y_RACK, "ko", ms=7, zorder=5)
ax3.annotate(f"Fulcro pignone\n(0, {Y_RACK:.0f})", (0, Y_RACK),
             textcoords="offset points", xytext=(10, 10), fontsize=9)

# Linee Ackermann ideali (kingpin → centro asse post.)
ax3.plot([HT, 0], [0, -L], "k:", lw=1, alpha=0.4, label="Ackermann ideale")
ax3.plot([-HT, 0], [0, -L], "k:", lw=1, alpha=0.4)

# Disegna per vari angoli di sterzata
colors = ["#2196F3", "#4CAF50", "#FF9800", "#F44336", "#9C27B0"]
th_pinions = [0, 15, 30, 45, 60]

for i, th_p in enumerate(th_pinions):
    dx = R_PINION * np.sin(np.radians(th_p))
    col = colors[i]
    alpha = 1.0 if th_p == 0 else 0.6

    dL = solve_delta(dx, D_RACK, BETA_OPT, l_tr_opt, "left")
    dR = solve_delta(dx, D_RACK, BETA_OPT, l_tr_opt, "right")
    if np.isnan(dL) or np.isnan(dR):
        continue

    # Rack endpoints
    rk_R = rack_end(-dx, D_RACK, "right")
    rk_L = rack_end(-dx, D_RACK, "left")
    ax3.plot([rk_L[0], rk_R[0]], [rk_L[1], rk_R[1]], "-", color=col, lw=2, alpha=alpha)
    ax3.plot(*rk_R, "o", color=col, ms=5, alpha=alpha)
    ax3.plot(*rk_L, "o", color=col, ms=5, alpha=alpha)

    # Steering arms
    for side, delta in [("right", dR), ("left", dL)]:
        kp_x = HT if side == "right" else -HT
        sa = sa_end(BETA_OPT, delta, side)
        ax3.plot([kp_x, sa[0]], [0, sa[1]], "-", color=col, lw=3, alpha=alpha)
        ax3.plot(*sa, "o", color=col, ms=5, alpha=alpha)

        # Tie rod
        rk = rack_end(-dx, D_RACK, side)
        ax3.plot([rk[0], sa[0]], [rk[1], sa[1]], "--", color=col, lw=1.5, alpha=alpha*0.7)

    # Prolunghe assi ruota (convergenza)
    if th_p > 0:
        for side, delta, kp_x in [("left", dL, -HT), ("right", dR, HT)]:
            direction = rot2d(delta) @ np.array([0, -1])
            t_end = 1.4 * L
            ax3.plot([kp_x, kp_x + direction[0]*t_end],
                     [0, direction[1]*t_end],
                     ":", color=col, lw=0.8, alpha=0.3)

    lbl = (f"θ_p={th_p}° (Δx={dx:.0f}mm)"
           f" → int={np.degrees(dL):.1f}° ext={np.degrees(dR):.1f}°")
    ax3.plot([], [], "-", color=col, lw=2, label=lbl)

ax3.legend(fontsize=8, loc="lower left")
ax3.set_xlabel("x [mm] — laterale", fontsize=11)
ax3.set_ylabel("y [mm] — longitudinale (avanti ↑)", fontsize=11)
ax3.set_xlim(-620, 620)
ax3.set_ylim(-L - 250, 200)

fig2.tight_layout()
fig2.savefig(os.path.join(OUT, "ackermann_topview.png"), dpi=150)
print("  Salvato: ackermann_topview.png")


# ── GRAFICO 3: Sensibilità β ──
fig3, ax4 = plt.subplots(figsize=(10, 6))
betas = np.linspace(np.radians(5), np.radians(45), 80)
costs_80 = [cost_beta_only(b, 80) for b in betas]
costs_120 = [cost_beta_only(b, 120) for b in betas]
costs_200 = [cost_beta_only(b, 200) for b in betas]

ax4.set_title("Sensibilità: errore Ackermann vs angolo braccio", fontsize=13, fontweight="bold")
ax4.plot(np.degrees(betas), costs_80, "b-", lw=2, label="d_rack=80 mm")
ax4.plot(np.degrees(betas), costs_120, "c-", lw=2, label="d_rack=120 mm")
ax4.plot(np.degrees(betas), costs_200, "m-", lw=2, label="d_rack=200 mm")
ax4.axvline(np.degrees(BETA_OPT), color="g", lw=2, ls="--",
            label=f"β ottimale ({np.degrees(BETA_OPT):.1f}°)")
ax4.axvline(geom_angle, color="gray", lw=1, ls=":",
            label=f"Geometrico ({geom_angle:.1f}°)")
ax4.set_xlabel("Angolo braccio β [°]", fontsize=11)
ax4.set_ylabel("Errore cumulativo [rad²]", fontsize=11)
ax4.legend(fontsize=10)
ax4.grid(True, alpha=0.3)

fig3.tight_layout()
fig3.savefig(os.path.join(OUT, "ackermann_sensitivity.png"), dpi=150)
print("  Salvato: ackermann_sensitivity.png")


# ── GRAFICO 4: Posizione braccio nel CAD ──
fig4, ax5 = plt.subplots(figsize=(8, 8))
ax5.set_title("Dettaglio braccio sterzo DX — posizione ottimale\n"
              "(da riportare nel CAD)", fontsize=13, fontweight="bold")
ax5.set_aspect("equal")
ax5.grid(True, alpha=0.2)

# Kingpin
ax5.plot(HT, 0, "ks", ms=12, zorder=5)
ax5.annotate(f"Kingpin\n({HT:.0f}, 0)", (HT, 0),
             textcoords="offset points", xytext=(15, 10), fontsize=10)

# Braccio ottimale
sa = sa_end(BETA_OPT, 0.0, "right")
ax5.plot([HT, sa[0]], [0, sa[1]], "g-", lw=4, zorder=4, label="Braccio ottimale")
ax5.plot(*sa, "go", ms=10, zorder=5)
ax5.annotate(f"Attacco tirante\n({sa[0]:.1f}, {sa[1]:.1f})",
             sa, textcoords="offset points", xytext=(-120, -25), fontsize=10,
             arrowprops=dict(arrowstyle="->", color="green"))

# Quote
ax5.annotate("", xy=(sa[0], 15), xytext=(HT, 15),
             arrowprops=dict(arrowstyle="<->", color="blue", lw=1.5))
ax5.text((sa[0]+HT)/2, 22, f"{dx_opt:.1f} mm", ha="center", fontsize=10, color="blue")

ax5.annotate("", xy=(HT+15, sa[1]), xytext=(HT+15, 0),
             arrowprops=dict(arrowstyle="<->", color="red", lw=1.5))
ax5.text(HT+25, sa[1]/2, f"{dy_opt:.1f} mm", ha="left", fontsize=10, color="red")

# Angolo
arc_r = 60
arc_angles = np.linspace(-np.pi/2, -np.pi/2 - BETA_OPT, 30)
# Ackermann angle is measured from transverse axis toward rear
# The arm goes from kingpin at angle β below the negative-x direction
arc_angles2 = np.linspace(np.pi, np.pi + BETA_OPT, 30)
ax5.plot(HT + arc_r*np.cos(arc_angles2), arc_r*np.sin(arc_angles2),
         "g-", lw=1.5)
ax5.text(HT - arc_r - 15, -25, f"β={np.degrees(BETA_OPT):.1f}°",
         fontsize=11, color="green", fontweight="bold")

# Braccio da disegno (stima)
sa_dwg = sa_end(beta_dwg, 0.0, "right")
ax5.plot([HT, sa_dwg[0]], [0, sa_dwg[1]], "r--", lw=2, alpha=0.5,
         label=f"Disegno β≈{np.degrees(beta_dwg):.0f}° (stima)")
ax5.plot(*sa_dwg, "ro", ms=7, alpha=0.5)

# Rack endpoint
rk = rack_end(0, D_RACK, "right")
ax5.plot(*rk, "^", color="gray", ms=8)
ax5.annotate(f"Rack\n({rk[0]:.0f}, {rk[1]:.0f})", rk,
             textcoords="offset points", xytext=(-60, 15), fontsize=9, color="gray")

# Tirante
ax5.plot([rk[0], sa[0]], [rk[1], sa[1]], "g--", lw=1.5, alpha=0.5)

ax5.legend(fontsize=10, loc="lower left")
ax5.set_xlabel("x [mm]", fontsize=11)
ax5.set_ylabel("y [mm]", fontsize=11)
ax5.set_xlim(sa[0]-60, HT+60)
ax5.set_ylim(sa[1]-40, Y_RACK+40)

fig4.tight_layout()
fig4.savefig(os.path.join(OUT, "ackermann_arm_detail.png"), dpi=150)
print("  Salvato: ackermann_arm_detail.png")

print()
print("  ══════════════════════════════════════════")
print("  ISTRUZIONI PER IL CAD:")
print("  ══════════════════════════════════════════")
print(f"  1. Braccio sterzo: {SA_LEN:.0f} mm di lunghezza")
print(f"  2. Angolo β = {np.degrees(BETA_OPT):.1f}° dall'asse trasversale verso il retro")
print(f"  3. Attacco tirante DX a ({sa_opt_R[0]:.1f}, {sa_opt_R[1]:.1f}) mm")
print(f"     → {dx_opt:.1f} mm verso il centro + {dy_opt:.1f} mm verso il retro dal kingpin")
print(f"  4. Attacco tirante SX simmetrico a ({sa_opt_L[0]:.1f}, {sa_opt_L[1]:.1f}) mm")
print(f"  5. Cremagliera: semi-span = {D_RACK:.0f} mm, a y = {Y_RACK:.0f} mm")
print(f"  6. Tirante: {l_tr_opt:.1f} mm")
print()
