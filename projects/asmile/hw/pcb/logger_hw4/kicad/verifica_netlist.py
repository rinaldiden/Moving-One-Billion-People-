#!/usr/bin/env python3
"""Confronta la netlist esportata da KiCad (kicad-cli sch export netlist --format kicadxml) con netlist_hw4.py.
Uso: python3 verifica_netlist.py net.xml  → stampa le differenze; esce 1 se ce ne sono."""
import sys, xml.etree.ElementTree as ET
import netlist_hw4 as NL
t = ET.parse(sys.argv[1]).getroot()
kicad = {}
for net in t.iter("net"):
    for n in net.iter("node"):
        if n.get("ref").startswith("#"):
            continue
        kicad[(n.get("ref"), n.get("pin"))] = net.get("name").lstrip("/")
atteso = {(p["ref"], k): v for p in NL.PARTS for k, v in p["pins"].items()}
diff = 0
for k, v in atteso.items():
    if kicad.get(k) != v:
        diff += 1; print("ATTESO", k, v, "KICAD", kicad.get(k))
for k, v in kicad.items():
    if k not in atteso and not v.startswith("unconnected-"):
        diff += 1; print("IN PIU' su KiCad", k, v)
# due net diverse del mio elenco non devono finire fuse in KiCad
inv = {}
for k, v in atteso.items():
    inv.setdefault(kicad.get(k), set()).add(v)
for kn, mine in inv.items():
    if len(mine) > 1:
        diff += 1; print("NET FUSE in KiCad:", kn, mine)
print("pin controllati:", len(atteso), "differenze:", diff)
sys.exit(1 if diff else 0)
