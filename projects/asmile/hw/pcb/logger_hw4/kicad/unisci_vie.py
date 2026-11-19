#!/usr/bin/env python3
"""Fonde le vie della stessa net troppo vicine (fanout + Freerouting mettono a volte due vie GND a 0,4 mm: fori a 0,14 mm,
sotto il minimo di foratura). Tiene la prima, sposta sulle sue coordinate le estremità delle piste che arrivavano alla
seconda (stesso strato, stessa larghezza: il segmento nuovo resta dentro il rame delle due vie), poi toglie la seconda.
Col Python di KiCad, dopo sbroglia.py e prima di finitura.py (processo separato: i Remove rompono SWIG in 10.0.8).
"""
import math, os
import pcbnew

QUI = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(QUI, "logger_hw4.kicad_pcb")
MM, TO = pcbnew.FromMM, pcbnew.ToMM
DIST_MIN = 0.3 + 0.3                     # centro-centro: foro 0,3 + 0,3 mm di foro-foro (JLC 0,2 → margine)


def main():
    b = pcbnew.LoadBoard(PCB)
    tr = b.Tracks()
    vie, piste = [], []
    for i in range(tr.size()):
        t = tr[i]
        (vie if t.GetClass() == "PCB_VIA" else piste).append(t)
    togliere = []
    tenute = []
    for v in vie:
        p = v.GetPosition()
        doppione = None
        for k in tenute:
            q = k.GetPosition()
            if k.GetNetCode() == v.GetNetCode() and math.hypot(TO(p.x - q.x), TO(p.y - q.y)) < DIST_MIN:
                doppione = k
                break
        if doppione is None:
            tenute.append(v)
            continue
        q = doppione.GetPosition()
        for t in piste:
            if t.GetNetCode() != v.GetNetCode():
                continue
            for estremo in ("S", "E"):
                e = t.GetStart() if estremo == "S" else t.GetEnd()
                if abs(e.x - p.x) < MM(0.01) and abs(e.y - p.y) < MM(0.01):
                    n = pcbnew.PCB_TRACK(b)
                    n.SetStart(p)
                    n.SetEnd(q)
                    n.SetWidth(t.GetWidth())
                    n.SetLayer(t.GetLayer())
                    n.SetNet(t.GetNet())
                    b.Add(n)
        togliere.append(v)
    # vie pendenti: le toglie togli_vie_pendenti.py SOLO dove le segnala il DRC di KiCad (un criterio mio ha rotto
    # 3 collegamenti il 19/11: antipattern A16)
    for v in togliere:
        b.Remove(v)
    b.Save(PCB)
    print("unisci_vie: %d vie doppie fuse" % len(togliere))


if __name__ == "__main__":
    main()
