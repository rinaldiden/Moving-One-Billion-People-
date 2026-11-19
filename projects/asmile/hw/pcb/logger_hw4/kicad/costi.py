#!/usr/bin/env python3
"""Costo per scheda del logger HW4, stesso fornitore (JLCPCB) per PCB + montaggio, più IVA/dazio. Ripetibile.
Ingressi: costi_bom.json (genera_bom.py, API JLC) + i numeri qui sotto, ognuno con fonte e data. Uscita: tabella markdown.
"""
import json, os

QUI = os.path.dirname(os.path.abspath(__file__))
B = json.load(open(os.path.join(QUI, "costi_bom.json")))
EUR = 1.10                                   # $ per €, da aggiornare
Q = (10, 100, 1000)

# PCB nudo JLCPCB 4 strati 250×50 ENIG 1u", 1,6 mm (cart.jlcpcb.com/quote, 18/11/2026, screenshot preventivo/jlcpcb_*.jpg)
# 19/11: preventivo CON I GERBER VERI caricati (cart.jlcpcb.com/quote, "Detected 4 layer board of 50x250mm"):
#   10 pz 60,00 $ (3-4 gg, nessun sovrapprezzo); 100 pz 279,05 $ con consegna 5-6 gg (388,15 $ a 3-4 gg)
PCB = {10: 60.00, 100: 279.05, 1000: None}          # $ per ordine; 1000 non quotato → stima 2,0 $/scheda
SPED = {10: 31.07, 100: 81.30, 1000: None}          # UPS Express Saver DDP (paese di default della pagina)
# PCBWay per confronto (orderonline.aspx 18/11): 130,89 $ / 350,89 $ + DHL 40,28 / 77,25 $
# montaggio JLCPCB standard (jlcpcb.com/help/article/pcb-assembly-price e /98-pcb-assembly-faqs, letti 18/11)
SETUP, STENCIL, EXT, GIUNTO = 25.56, 15.72, 3.07, 0.0016
MANO_GIUNTO, MANO_ORDINE = 0.0164, 3.58             # saldatura a mano (moduli castellati forniti da noi, consegna)
PAD_SMD, PAD_MODULI = 552, 176                      # da conta.py sul PCB generato (127 pezzi montati, 18/11 23:02)
MODULO = {10: 10.99, 100: 9.99, 1000: 9.99}         # waveshare.com, prezzo sito (variante IPEX senza prezzo proprio)
ANTENNA = {10: 1.0, 100: 0.6, 1000: 0.4}            # stima
IVA, DAZIO_PCBA = 0.22, 0.035                        # IVA import Italia; dazio PCBA 0-3,5 % (TARIC da verificare), PCB nudo 0 %
SDOGANAMENTO = 50.0                                  # € a spedizione (25-75 € spedizioniere); con DDP già incluso → 0


def riga(n):
    pcb = (PCB[n] + SPED[n]) / n if PCB[n] else 2.30
    parti = B["pezzi_lcsc"][str(n)]
    fisso = SETUP + STENCIL + EXT * B["n_estesi"] + MANO_ORDINE
    mont = fisso / n + (PAD_SMD - PAD_MODULI) * GIUNTO + PAD_MODULI * MANO_GIUNTO
    moduli = 2 * MODULO[n] + 2 * ANTENNA[n]
    netto = pcb + parti + mont + moduli
    return pcb, parti, mont, moduli, netto


def main():
    print("| per scheda | " + " | ".join("%d pz" % n for n in Q) + " |")
    print("|---|" + "---|" * len(Q))
    rr = {n: riga(n) for n in Q}
    nomi = ["PCB nudo + spedizione (JLC)", "pezzi LCSC", "montaggio JLC (macchina + moduli a mano)",
            "2 moduli Waveshare + 2 antenne"]
    for i, nm in enumerate(nomi):
        print("| %s | %s |" % (nm, " | ".join("%.2f $" % rr[n][i] for n in Q)))
    print("| **netto (senza IVA)** | %s |" % " | ".join("**%.2f $ = %.1f €**" % (rr[n][4], rr[n][4] / EUR) for n in Q))
    # con IVA non recuperabile e dazio sul montato (caso peggiore: acquisto senza P.IVA)
    for n in Q:
        netto_eur = rr[n][4] / EUR
        dazio = (rr[n][4] - 2 * MODULO[n]) / EUR * DAZIO_PCBA
        lordo = (netto_eur + dazio) * (1 + IVA)
        rr[n] = rr[n] + (lordo,)
    print("| con dazio 3,5 %% + IVA 22 %% (IVA non recuperata) | %s |" % " | ".join("%.1f €" % rr[n][5] for n in Q))
    print("\nIVA recuperabile se l'acquisto è fatto con la P.IVA della ditta individuale di Daniele: "
          "allora conta la riga netta. Spedizione JLC in DDP = dazi già pagati alla consegna; altrimenti +25-75 € di "
          "sdoganamento a spedizione (≈ +0,5 € a scheda su 100).")


if __name__ == "__main__":
    main()
