#!/usr/bin/env python3
"""Stacco del cavo USB in registrazione (VETO 2, antipattern A12): quanto resta la scheda sul diodo di body di Q3?

Fasi dopo lo stacco: (1) il carico svuota la capacità di VBUS attraverso D5 finché VBUS ≈ VSYS_IN + Vf;
(2) VSYS_IN è tenuta dal diodo di body di Q3 (cella − Vsd) finché il gate non scende sotto VSYS_IN − |Vgs| di
conduzione; (3) Q3 conduce, VSYS_IN ≈ cella − I·Rds.
Si confrontano: A) gate collegato a VBUS (come prima) con R35 100k e 10k; B) gate da VBUS attraverso un diodo
(D8, SS14) con R35 10k: il gate non vede più i 10 µF di VBUS, si scarica solo con la sua Ciss.
Numeri e fonti:
  AO3401A (C15127, datasheet AOS): Ciss 645 pF, Vgs(th) −0,5/−0,9/−1,3 V, Vsd ≤ 1 V a 1 A (tip. ~0,8 V);
    per far passare ~1,5 A serve Vgs ≈ −1,8 V (curva di trasferimento) → soglia di "presa" = VSYS_IN − 1,8 V
  TLV62569 SLVSDG1C §7.3.2: VIN(MIN) = VOUT + I·(RDS + RL), RDS ~0,13 Ω a 3 V (100 mΩ a 5 V, §6.5), RL 58 mΩ
  Capacità su VBUS: C1 10 µF/25 V X5R 0805 (≈ 9 µF a 3-4 V di polarizzazione) + COUT AW32901 1 µF + CIN 0,1 µF
  Scarica resistiva di VBUS: R35, R12+R13 = 168k, R7+NTC = 16,8k (25 °C); TP4056 in sleep sotto VBAT (µA)
Carico in registrazione: ~1,2 A dalla cella (2 moduli + 2 camere, picchi C6) — DA MISURARE (prova P6).
"""
import math

C_VBUS = 9e-6 + 1e-6 + 0.1e-6
CISS = 645e-12 + 60e-12          # Q3 + diodo D8 + pista
VSD, VF_D5, VF_D8 = 0.80, 0.45, 0.20
I_LOAD, I_BUCK = 1.2, 0.8
R_BUCK = 0.13 + 0.058
V_PRESA = 1.8                    # |Vgs| a cui Q3 porta la corrente del carico


def par(*r):
    return 1 / sum(1 / x for x in r)


def caso(nome, r35, gate_su_vbus, cella):
    vsys_body = cella - VSD - 0.05                       # sul diodo di body (meno cavo/interruttore)
    vsys_on = cella - I_LOAD * (0.085 + 0.05) - 0.05     # Q3 acceso (85 mΩ a Vgs −2,5 V) + FS8205A + cavo
    v3_body = min(3.30, vsys_body - I_BUCK * R_BUCK)
    v3_on = min(3.30, vsys_on - I_BUCK * R_BUCK)
    if gate_su_vbus:
        # il gate È VBUS: dopo la fase 1 (VBUS ≈ VSYS_IN + Vf) scende solo con la RC di VBUS
        tau = par(r35, 168e3, 16.8e3) * C_VBUS
        v_gate0, v_gate1 = vsys_body + VF_D5, vsys_body - V_PRESA
        t = tau * math.log(v_gate0 / v_gate1)
        return nome, cella, tau, t, vsys_body, v3_body
    # gate da VBUS via D8: appena VBUS scende il diodo si interdice e il gate cala con la sua Ciss (τ µs),
    # più in fretta di VBUS che si svuota sul carico: Q3 si accende prima che VSYS_IN arrivi al diodo di body
    tau = r35 * CISS
    t = tau * math.log((5.0 - VF_D8) / max(0.1, vsys_on - V_PRESA))
    return nome, cella, tau, t, vsys_on, v3_on


def main():
    print("| caso | cella | τ gate | tempo prima che Q3 porti il carico | VSYS in quel tempo | 3V3 in quel tempo |")
    print("|---|---|---|---|---|---|")
    for cella in (4.0, 3.7, 3.5):
        for nome, r35, su in (("A: gate su VBUS, R35 100k", 100e3, True), ("A: gate su VBUS, R35 10k", 10e3, True),
                              ("B: gate da VBUS via D8 (SS14), R35 10k", 10e3, False)):
            n, c, tau, t, vs, v3 = caso(nome, r35, su, cella)
            ts = "%.0f ms" % (t * 1e3) if t > 1e-3 else "%.0f µs" % (t * 1e6)
            nota = " (sul diodo di body)" if su else " (VBUS ancora sopra: nessun buco)"
            print("| %s | %.1f V | %s | **%s** | %.2f V%s | %.2f V%s |" % (
                n, c, ("%.0f ms" % (tau * 1e3)) if tau > 1e-3 else ("%.1f µs" % (tau * 1e6)), ts, vs, nota, v3,
                " ⚠ < 3,0 V" if v3 < 3.0 else ""))
    c_vsys = 2 * 10e-6                                   # C5, C8: ingresso dei due buck
    print("\nTempo prima che VSYS arrivi al diodo di body se nessuno la tenesse (B): VBUS e VSYS si svuotano sul carico")
    for cella in (4.0, 3.7, 3.5):
        vb = cella - VSD - 0.05
        q = C_VBUS * (5.0 - (vb + VF_D5)) + c_vsys * ((5.0 - VF_D5) - vb)
        print("- cella %.1f V: %.0f µs (contro %.0f µs del gate di Q3 in B) → Q3 è già acceso" %
              (cella, q / I_LOAD * 1e6, caso("", 10e3, False, cella)[3] * 1e6))
    print("Con A il buco dura 60-170 ms e la 3V3 scende a 2,5-3,0 V: reset possibile della P4. DA MISURARE: COLLAUDO passo 4.")

if __name__ == "__main__":
    main()
