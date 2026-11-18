#!/usr/bin/env python3
"""Genera logger_hw4.kicad_pcb dalla netlist (netlist_hw4.json scritta da genera_schema.py).

Va lanciato col Python di KiCad (serve il modulo pcbnew):
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 genera_pcb.py
Fa: scheda 4 strati 250 × 45 mm, footprint con le net, piazzamento per zone, piani GND su In1 e B.Cu, collegamento
schema↔PCB (path = uuid del simbolo). NON sbroglia: le piste si tirano in KiCad (o Freerouting) dopo che la
meccanica (fori camere, case) è fissata col Doppio. Posizioni = proposta, DA VERIFICARE con la meccanica.
"""
import json, os
import pcbnew

QUI = os.path.dirname(os.path.abspath(__file__))
FPLIB = os.path.join(QUI, "lib", "hw4.pretty")
W, H = 250.0, 50.0                     # mm
CAM_X = (25.0, 225.0)                  # assi ottici: baseline 200 mm
MM = pcbnew.FromMM

# zone di piazzamento per blocco (x0, y0, x1, y1) in mm, provate in ordine; origine in alto a sinistra
ZONE = {
    "camera A": [(30, 30, 46, 49), (6, 1, 46, 8)], "camera B": [(204, 30, 220, 49), (204, 1, 244, 8)],
    "modulo A": [(46, 1, 97, 10), (46, 35, 97, 49)], "modulo B": [(153, 1, 204, 10), (153, 35, 204, 49)],
    "SD A": [(97, 24, 120, 33), (97, 1, 153, 24)], "SD B": [(130, 24, 153, 33), (97, 1, 153, 24)],
    "alimentazione": [(97, 1, 153, 24)], "A-B": [(97, 1, 153, 24), (46, 35, 97, 49)],
    "sensori e segnali": [(97, 1, 153, 24), (153, 35, 204, 49), (46, 35, 97, 49)],
    "meccanica": [(0, 0, W, H)],
}
FISSI = {  # ref: (x, y, rotazione) — posizione decisa da meccanica/funzione (PROPOSTA, da concordare col Doppio)
    "U10": (71.5, 22.5, 0), "U20": (178.5, 22.5, 0),
    "J60": (25, 44, 0), "J70": (225, 44, 0), "J61": (12, 44, 0), "J71": (238, 44, 0),
    "J1": (125, 46.0, 0), "J80": (106, 40, 0), "J90": (144, 40, 0),
    "J12": (58, 46, 90), "J22": (185, 46, 90), "J100": (116, 34, 90),
    "H1": (3.5, 3.5, 0), "H2": (246.5, 3.5, 0), "H3": (3.5, 46.5, 0), "H4": (246.5, 46.5, 0),
    "H11": (14.5, 16, 0), "H12": (35.5, 16, 0), "H13": (14.5, 28.5, 0), "H14": (35.5, 28.5, 0),
    "H15": (214.5, 16, 0), "H16": (235.5, 16, 0), "H17": (214.5, 28.5, 0), "H18": (235.5, 28.5, 0),
}


def rect_fp(fp, margine=0.3):
    c = fp.GetCourtyard(pcbnew.F_CrtYd)
    bb = c.BBox() if c.OutlineCount() else fp.GetBoundingBox(False, False)
    for pad in fp.Pads():                   # alcuni footprint easyeda hanno il courtyard più stretto dei pad
        bb.Merge(pad.GetBoundingBox())
    return (pcbnew.ToMM(bb.GetLeft()) - margine, pcbnew.ToMM(bb.GetTop()) - margine,
            pcbnew.ToMM(bb.GetRight()) + margine, pcbnew.ToMM(bb.GetBottom()) + margine)


def libero(r, occ):
    return all(r[2] <= o[0] or r[0] >= o[2] or r[3] <= o[1] or r[1] >= o[3] for o in occ)


def main():
    parts = json.load(open(os.path.join(QUI, "netlist_hw4.json")))
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(4)
    ds = b.GetDesignSettings()
    ds.SetBoardThickness(MM(1.6))
    # contorno
    pts = [(0, 0), (W, 0), (W, H), (0, H)]
    for i in range(4):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(MM(pts[i][0]), MM(pts[i][1])))
        s.SetEnd(pcbnew.VECTOR2I(MM(pts[(i + 1) % 4][0]), MM(pts[(i + 1) % 4][1])))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        b.Add(s)
    nets = {}
    for p in parts:
        for n in p["pins"].values():
            if n not in nets:
                ni = pcbnew.NETINFO_ITEM(b, n)
                b.Add(ni)
                nets[n] = ni
    fps = []
    for p in parts:
        fp = pcbnew.FootprintLoad(FPLIB, p["fp"])
        if fp is None:
            raise SystemExit("footprint mancante: " + p["fp"])
        fp.SetReference(p["ref"])
        fp.SetValue(p["value"])
        fp.SetPath(pcbnew.KIID_PATH("/" + p["uuid"]))
        if p.get("dnp"):
            fp.SetDNP(True)
        for pad in fp.Pads():
            n = p["pins"].get(pad.GetNumber())
            if n:
                pad.SetNet(nets[n])
        fps.append((p, fp))
    occ = []
    for p, fp in fps:                       # prima i fissi: diventano ostacoli
        if p["ref"] in FISSI:
            x, y, r = FISSI[p["ref"]]
            fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
            if r:
                fp.SetOrientationDegrees(r)
            occ.append(rect_fp(fp))
    for p, fp in fps:                       # poi gli altri, nella prima posizione libera delle zone del blocco
        if p["ref"] in FISSI:
            continue
        fp.SetPosition(pcbnew.VECTOR2I(0, 0))
        r0 = rect_fp(fp)
        w, h = r0[2] - r0[0], r0[3] - r0[1]
        messo = False
        for z in ZONE.get(p["blocco"], ZONE["alimentazione"]):
            y = z[1]
            while not messo and y + h <= z[3]:
                x = z[0]
                while x + w <= z[2]:
                    r = (x, y, x + w, y + h)
                    if libero(r, occ):
                        fp.SetPosition(pcbnew.VECTOR2I(MM(x - r0[0]), MM(y - r0[1])))
                        occ.append(r)
                        messo = True
                        break
                    x += 0.5
                y += 0.5
            if messo:
                break
        if not messo:
            print("NON PIAZZATO (zona piena):", p["ref"], p["blocco"])
            fp.SetPosition(pcbnew.VECTOR2I(MM(W + 10), MM(10)))
    for p, fp in fps:
        b.Add(fp)
    # piani GND su In1.Cu e B.Cu (riferimento continuo per CSI/USB/SDIO)
    for layer in (pcbnew.In1_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b)
        z.SetLayer(layer)
        z.SetNet(nets["GND"])
        ol = z.Outline()
        ol.NewOutline()
        for (x, y) in [(0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)]:
            ol.Append(MM(x), MM(y))
        z.SetMinThickness(MM(0.2))
        b.Add(z)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    out = os.path.join(QUI, "logger_hw4.kicad_pcb")
    b.Save(out)
    print("pcb:", out, len(parts), "footprint,", len(nets), "net")


if __name__ == "__main__":
    main()
