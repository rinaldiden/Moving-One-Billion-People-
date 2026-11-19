#!/usr/bin/env python3
"""Toglie solo le vie e le piste che il DRC di KiCad segnala come 'via_dangling' / 'track_dangling' (coordinate esatte
dal JSON di kicad-cli).
Uso (Python di KiCad): python3 togli_vie_pendenti.py drc_tutto.json   — poi riempire di nuovo le zone e rifare il DRC."""
import json, os, sys
import pcbnew
QUI = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(QUI, "logger_hw4.kicad_pcb")
d = json.load(open(sys.argv[1]))
punti = [(i["pos"]["x"], i["pos"]["y"]) for v in d["violations"] if v["type"] == "via_dangling" for i in v["items"]
         if i["description"].startswith("Via")]
b = pcbnew.LoadBoard(PCB)
tr = b.Tracks()
via = [tr[i] for i in range(tr.size()) if tr[i].GetClass() == "PCB_VIA"]
togli = [v for v in via if any(abs(pcbnew.ToMM(v.GetPosition().x) - x) < 0.005 and abs(pcbnew.ToMM(v.GetPosition().y) - y) < 0.005
                               for x, y in punti)]
moncone = [(i["pos"]["x"], i["pos"]["y"]) for v in d["violations"] if v["type"] == "track_dangling" for i in v["items"]
           if i["description"].startswith("Track")]
piste = [tr[i] for i in range(tr.size()) if tr[i].GetClass() == "PCB_TRACK"]
for t in piste:
    for x, y in moncone:
        for e in (t.GetStart(), t.GetEnd()):
            if abs(pcbnew.ToMM(e.x) - x) < 0.005 and abs(pcbnew.ToMM(e.y) - y) < 0.005 and t not in togli:
                togli.append(t)
for v in togli:
    b.Remove(v)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print("vie/piste pendenti tolte:", len(togli), "(segnalate: %d vie, %d piste)" % (len(punti), len(moncone)))
