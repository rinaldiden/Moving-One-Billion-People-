#!/usr/bin/env python3
"""Partitore batteria contro la sequenza del firmware (VETO 2, antipattern A11).

logger02_imu.c:77-84 (leggi_batteria): pull-down interno ON → 2 ms → lettura di controllo (<150 mV = scollegato) →
pull-down OFF → 2 ms → lettura vera → V = mV × 133/33; sotto 2,0 V = "scollegato".
Nodo ADC = Thevenin del partitore (Vth = V·R11/(R10+R11), Rth = R10‖R11) + pull-down interno (~45 kΩ, commento del
firmware) + capacità del nodo C. Si simula la carica/scarica di C con queste costanti e si confronta la lettura vera
con il valore ideale. Due casi: 1M/330k con C4 100 nF (giro precedente) e 100k/33k con C4 NON montato (come HW3).
Capacità del nodo senza C4: pad + pista + ingresso ADC ≈ 20 pF (stima prudente; il campionamento del SAR aggiunge
pochi pF e si ricarica in ~0,1 µs con 25 kΩ).
Errore da tolleranze (1 % sulle due R): rapporto 33/133 da 0,2444 a 0,2518 → ±1,5 % nel caso peggiore, ±0,7 % RSS.
"""
import math
import random

R_PD = 45e3
T_PD, T_WAIT = 2e-3, 2e-3


def lettura(v, r10, r11, c):
    vth, rth = v * r11 / (r10 + r11), r10 * r11 / (r10 + r11)
    # fase 1: pull-down ON (nodo parte da vth: lettura precedente 1 s prima, assestato)
    v_pd = vth * R_PD / (R_PD + rth)
    r_pd = rth * R_PD / (rth + R_PD)
    v1 = v_pd + (vth - v_pd) * math.exp(-T_PD / (r_pd * c))
    controllo = v1 * 1000 >= 150                     # True = "collegato"
    # fase 2: pull-down OFF, il nodo risale verso vth con τ = Rth·C
    v2 = vth + (v1 - vth) * math.exp(-T_WAIT / (rth * c))
    vlet = v2 * 133.0 / 33.0                          # costante del firmware HW3
    return controllo, vlet


def main():
    print("| partitore | C nodo | cella | letto | errore | controllo 'collegato' |")
    print("|---|---|---|---|---|---|")
    peggiore = {}
    for nome, r10, r11, c in (("1M/330k + C4 100 nF (prima)", 1e6, 330e3, 100e-9),
                              ("100k/33k, C4 non montato (ora = HW3)", 100e3, 33e3, 20e-12),
                              ("100k/33k, C nodo 1 nF (caso pessimo: sporco/flussante)", 100e3, 33e3, 1e-9)):
        for v in (3.0, 3.45, 3.7, 4.2):
            ok, l = lettura(v, r10, r11, c)
            err = (l - v) / v * 100
            peggiore[nome] = max(peggiore.get(nome, 0), abs(err))
            print("| %s | %s | %.2f V | %.3f V | %+.3f %% | %s |" % (nome, "%.0f pF" % (c * 1e12) if c < 1e-9 else "%.0f nF" % (c * 1e9),
                                                                v, l, err, "sì" if ok else "NO"))
    print()
    for k, e in peggiore.items():
        print("- %s: errore massimo del modello RC fra 3,0 e 4,2 V = %.3f %%" % (k, e))
    random.seed(1)
    errs = []
    for _ in range(20000):
        r10 = 100e3 * (1 + random.uniform(-0.01, 0.01))
        r11 = 33e3 * (1 + random.uniform(-0.01, 0.01))
        errs.append((r11 / (r10 + r11)) / (33 / 133) - 1)
    errs.sort()
    print("- tolleranza 1 %% delle due resistenze (Monte Carlo 20 000, uniforme): 99 %% delle schede entro ±%.2f %%,"
          " estremi ±%.2f %%" % (max(abs(errs[100]), abs(errs[-100])) * 100, max(abs(errs[0]), abs(errs[-1])) * 100))


if __name__ == "__main__":
    main()
