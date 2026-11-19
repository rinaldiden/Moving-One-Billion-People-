#!/usr/bin/env python3
"""File di produzione del logger HW4 in ../produzione/ (gerber, foratura, BOM e CPL per JLCPCB/PCBWay). Python normale.
  python3 esporta_produzione.py [--kicad /Applications/KiCad/KiCad.app]
- gerber 4 strati + maschere + paste + serigrafie + contorno (kicad-cli, formato Protel come vuole JLC), foratura
  Excellon PTH/NPTH separati, mappa fori; tutto zippato in produzione/gerber_logger_hw4.zip;
- BOM_JLC.csv: Comment, Designator, Footprint, LCSC — solo pezzi montati e con codice LCSC (i 2 moduli Waveshare e
  le antenne sono forniti da noi: elenco a parte in produzione/FORNITI_DA_NOI.csv);
- CPL_JLC.csv: Designator, Mid X, Mid Y, Layer, Rotation — dalla posizione di kicad-cli, stesso insieme della BOM.
Rotazioni: i footprint dei pezzi LCSC vengono da easyeda2kicad (lo stesso disegno della libreria JLC) → correzione 0;
passivi KiCad simmetrici → 0; LED 0603 KiCad (catodo pin 1 a sinistra) = orientamento JLC 0° → 0. Da RICONTROLLARE
nel visualizzatore DFM del fornitore prima dell'ordine (pezzi polarizzati: U*, Q*, D*, J1, J2, J3, J60, J70).
"""
import argparse, csv, json, os, subprocess, zipfile
import netlist_hw4 as NL

QUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(QUI), "produzione")
PCB = os.path.join(QUI, "logger_hw4.kicad_pcb")
CORREZIONE = {}            # ref o prefisso → gradi da sommare (nessuna oggi: vedi docstring)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kicad", default="/Applications/KiCad/KiCad.app")
    a = ap.parse_args()
    cli = os.path.join(a.kicad, "Contents/MacOS/kicad-cli")
    gdir = os.path.join(OUT, "gerber")
    os.makedirs(gdir, exist_ok=True)
    for f in os.listdir(gdir):
        os.remove(os.path.join(gdir, f))
    strati = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    subprocess.run([cli, "pcb", "export", "gerbers", "--layers", strati, "--use-drill-file-origin",
                    "--subtract-soldermask", "-o", gdir + "/", PCB], check=True, capture_output=True)
    # origine: l'origine di foratura non è impostata (0,0) → coordinate assolute uguali per gerber, fori e CPL
    subprocess.run([cli, "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
                    "--drill-origin", "absolute", "--generate-map", "--map-format", "gerberx2", "-o", gdir + "/", PCB],
                   check=True, capture_output=True)
    z = os.path.join(OUT, "gerber_logger_hw4.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zz:
        for f in sorted(os.listdir(gdir)):
            zz.write(os.path.join(gdir, f), f)
    pos = os.path.join(OUT, "_pos.csv")
    subprocess.run([cli, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
                    "--use-drill-file-origin", "--exclude-dnp", "-o", pos, PCB], check=True, capture_output=True)
    montati = {p["ref"]: p for p in NL.PARTS if not p["dnp"] and p["lcsc"]}
    forniti = [p for p in NL.PARTS if not p["dnp"] and not p["lcsc"] and not p["ref"].startswith(("H", "TP", "#"))]
    righe = {}
    for p in montati.values():
        righe.setdefault((p["value"], p["fp"], p["lcsc"]), []).append(p["ref"])
    with open(os.path.join(OUT, "BOM_JLC.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC"])
        for (val, fp, lc), refs in sorted(righe.items(), key=lambda kv: kv[1][0]):
            w.writerow([val, ",".join(sorted(refs)), fp, lc])
    with open(os.path.join(OUT, "FORNITI_DA_NOI.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Valore", "Footprint", "Nota"])
        for p in forniti:
            w.writerow([p["ref"], p["value"], p["fp"], p.get("nota", "")])
    n = 0
    with open(pos) as fi, open(os.path.join(OUT, "CPL_JLC.csv"), "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in csv.DictReader(fi):
            ref = r["Ref"]
            if ref not in montati:
                continue
            rot = (float(r["Rot"]) + CORREZIONE.get(ref, 0)) % 360
            w.writerow([ref, "%.4fmm" % float(r["PosX"]), "%.4fmm" % float(r["PosY"]),
                        "Top" if r["Side"] == "top" else "Bottom", "%g" % rot])
            n += 1
    os.remove(pos)
    print("produzione:", z, "| BOM", len(righe), "righe,", len(montati), "pezzi | CPL", n, "pezzi | forniti da noi",
          len(forniti))
    if n != len(montati):
        print("ATTENZIONE: CPL e BOM non coincidono")


if __name__ == "__main__":
    main()
