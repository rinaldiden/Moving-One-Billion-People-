#!/usr/bin/env python3
"""Sbroglio del logger HW4 con Freerouting (dopo genera_pcb.py). Col Python di KiCad:
  .../KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 sbroglia.py --jar freerouting.jar
1) carica il PCB con le classi di rete del progetto; 2) toglie i riempimenti GND di F.Cu/B.Cu (bloccherebbero le piste);
3) esporta il DSN (In1/In2 = piani GND: le net GND si chiudono con vie verso i piani); 4) Freerouting senza grafica;
5) importa il SES; 6) salva. I riempimenti GND di F.Cu/B.Cu e le vie GND li mette finitura.py (processo separato: in 10.0.8 il Python
di KiCad perde i tipi SWIG dopo un Remove/Import nello stesso processo). Il risultato va riletto (DRC + occhi).
"""
import argparse, os, subprocess, time
import pcbnew

QUI = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(QUI, "logger_hw4.kicad_pcb")
MM = pcbnew.FromMM


def zone_gnd(b, layer):
    W, H = 250.0, 50.0                     # (GetBoardEdgesBoundingBox dà oggetti SWIG rotti in 10.0.8)
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    z.SetNet(b.FindNet("GND"))
    ol = z.Outline()
    ol.NewOutline()
    for (x, y) in [(0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)]:
        ol.Append(MM(x), MM(y))
    z.SetMinThickness(MM(0.2))
    z.SetLocalClearance(MM(0.25))
    z.SetThermalReliefGap(MM(0.25))
    z.SetThermalReliefSpokeWidth(MM(0.3))
    b.Add(z)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", required=True)
    ap.add_argument("--java", default="/opt/homebrew/opt/openjdk/bin/java")
    ap.add_argument("--passi", default="40")
    a = ap.parse_args()
    b = pcbnew.LoadBoard(PCB)              # arriva da genera_pcb.py: niente piste, niente zone su F/B
    dsn, ses = os.path.join(QUI, "sbroglio.dsn"), os.path.join(QUI, "sbroglio.ses")
    if not pcbnew.ExportSpecctraDSN(b, dsn):
        raise SystemExit("export DSN fallito")
    # margine di 0,01 mm sugli isolamenti per Freerouting (arrotonda: 0,118 contro 0,12); il DRC resta sui valori veri
    import re
    txt = open(dsn).read()
    txt = re.sub(r"\(clearance (\d+)\)", lambda m: "(clearance %d)" % (int(m.group(1)) + 10), txt)
    open(dsn, "w").write(txt)
    t0 = time.time()
    r = subprocess.run([a.java, "-jar", a.jar, "-de", dsn, "-do", ses, "-mp", a.passi, "-mt", "8"],
                       capture_output=True, text=True)
    log = os.path.join(QUI, "sbroglio.log")
    open(log, "w").write(r.stdout[-20000:] + r.stderr[-5000:])
    print("freerouting: exit %d, %.0f s, log %s" % (r.returncode, time.time() - t0, log))
    if not os.path.exists(ses):
        raise SystemExit("nessun SES prodotto")
    if not pcbnew.ImportSpecctraSES(b, ses):
        raise SystemExit("import SES fallito")
    b.Save(PCB)
    txt = open(PCB).read()                  # conto dal file (b.Tracks() dà oggetti SWIG non iterabili in 10.0.8)
    print("piste %d, vie %d" % (txt.count("\n\t(segment"), txt.count("\n\t(via")))


if __name__ == "__main__":
    main()
