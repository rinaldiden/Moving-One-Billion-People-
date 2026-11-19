#!/usr/bin/env python3
"""Ogni pad del PCB ha la net che dice netlist_hw4.py? (Python di KiCad)"""
import os, pcbnew, netlist_hw4 as NL
b = pcbnew.LoadBoard(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logger_hw4.kicad_pcb"))
voluto = {(p["ref"], k): v for p in NL.PARTS for k, v in p["pins"].items()}
diff = n = 0
for fp in b.GetFootprints():
    for pad in fp.Pads():
        k = (fp.GetReference(), pad.GetNumber())
        if k in voluto:
            n += 1
            if pad.GetNetname() != voluto[k]:
                diff += 1; print("DIVERSO", k, pad.GetNetname(), voluto[k])
print("pad del PCB controllati: %d, differenze: %d" % (n, diff))
