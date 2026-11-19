#!/usr/bin/env python3
"""Coppie MIPI CSI instradate PRIMA di Freerouting (che non sa fare le coppie), col router A* e piste bloccate
(Freerouting le riceve come fisse). Per ogni lato (A, B) e ogni lane: pad del modulo → pad dell'FFC, P e N uno dopo
l'altro: partono e arrivano a 1 mm di distanza, quindi i percorsi più corti vengono quasi uguali. Stampa lunghezze e
differenza P/N. Pista 0,15 mm: con lo stack-up JLC04161H-3313 (prepreg 0,1 mm) ≈ 50 Ω, coppia ≈ 100 Ω (DESIGN §8).
Col Python di KiCad, dopo fanout.py e prima di sbroglia.py.
"""
import os
import pcbnew
from router_astar import carica_ostacoli, instrada

QUI = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(QUI, "logger_hw4.kicad_pcb")
TO = pcbnew.ToMM
LATI = {"A": ("U10", "J60"), "B": ("U20", "J70")}
ORDINE = ["D0N", "D0P", "CKN", "CKP", "D1N", "D1P"]


def main():
    b = pcbnew.LoadBoard(PCB)
    rame, vietate = carica_ostacoli(b)
    pos = {}
    for fp in b.GetFootprints():
        if fp.GetReference() in ("U10", "U20", "J60", "J70"):
            for pad in fp.Pads():
                n = pad.GetNetname()
                if n.startswith("CSI_"):
                    c = pad.GetPosition()
                    pos.setdefault(n, []).append((TO(c.x), TO(c.y), 0))
    lung = {}
    for s in LATI:
        for lane in ORDINE:
            net = "CSI_%s_%s" % (lane, s)
            p = pos[net]
            ok, l, nv = instrada(b, rame, vietate, net, p[0], p[1], pista=0.15, iso=0.15, margine=8.0, blocca=True)
            lung[net] = l if ok else None
            print("%s: %s" % (net, ("%.1f mm, %d vie" % (l, nv)) if ok else "NON INSTRADATA (la farà Freerouting)"))
    for s in LATI:
        for lane in ("D0", "D1", "CK"):
            a, c = lung.get("CSI_%sP_%s" % (lane, s)), lung.get("CSI_%sN_%s" % (lane, s))
            if a and c:
                print("coppia %s %s: differenza %.2f mm" % (s, lane, abs(a - c)))
    b.Save(PCB)


if __name__ == "__main__":
    main()
