#!/usr/bin/env python3
"""Chiude i collegamenti che Freerouting lascia aperti (pochi, corti) col router A* di router_astar.py.
Uso (Python di KiCad, dopo finitura.py):  python3 completa.py drc.json
Legge le coppie non collegate dal DRC JSON di kicad-cli (salta le isole di zona: le toglie finitura), instrada pista
0,15 mm / isolamento 0,15 mm, riempie di nuovo le zone, salva. Il risultato va riletto (DRC).
"""
import json, os, re, sys
import pcbnew
from router_astar import carica_ostacoli, instrada

QUI = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(QUI, "logger_hw4.kicad_pcb")


def main():
    d = json.load(open(sys.argv[1]))
    b = pcbnew.LoadBoard(PCB)
    rame, vietate = carica_ostacoli(b)
    fatti = 0
    for u in d["unconnected_items"]:
        it = u["items"]
        if any(x["description"].startswith("Zone") for x in it):
            print("salto (isola di zona):", it[0]["description"][:50])
            continue
        net = re.search(r"\[([^\]]+)\]", it[0]["description"]).group(1)
        pts = [(x["pos"]["x"], x["pos"]["y"], 1 if "B.Cu" in x["description"] else 0) for x in it]
        ok, lung, nv = instrada(b, rame, vietate, net, pts[0], pts[1])
        if not ok:
            ok, lung, nv = instrada(b, rame, vietate, net, pts[0], pts[1], margine=15.0)
        if not ok:
            ok, lung, nv = instrada(b, rame, vietate, net, pts[0], pts[1], margine=30.0)
        print(("chiuso %s: %.1f mm, %d vie" % (net, lung, nv)) if ok else ("NON CHIUSO: %s %s" % (net, pts)))
        fatti += ok
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print("completa: %d collegamenti chiusi su %d" % (fatti, len(d["unconnected_items"])))


if __name__ == "__main__":
    main()
