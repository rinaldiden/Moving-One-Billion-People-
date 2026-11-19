#!/usr/bin/env python3
"""Genera logger_hw4.kicad_pcb dalla netlist (netlist_hw4.json scritta da genera_schema.py): contorno, footprint con le
net, PIAZZAMENTO, piani, regole. Lo sbroglio lo fa `sbroglia.py` (Freerouting) sul file prodotto qui.

Va lanciato col Python di KiCad:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 genera_pcb.py
Stack-up 4 strati: F.Cu segnali + GND · In1.Cu GND pieno · In2.Cu 3V3_A (sinistra) / 3V3_B (destra) · B.Cu segnali + GND.
Piazzamento (19/11, per lo sbroglio):
  - fissi: moduli, connettori al bordo, fori; FFC delle camere ACCANTO ai pad CSI del modulo (MIPI ~10 mm; il cavo
    va dalla camera, a x = 25 / 225, al connettore: ~60 mm, cavo Pi standard da 100-150 mm), SD accanto ai pad SD;
  - gli altri: vicino ai pad a cui sono collegati (peso 1/(pin della net − 1), GND escluso), ricerca a spirale del
    primo posto libero (ingombro = courtyard ∪ pad + 0,3 mm). Posizioni = proposta, la meccanica la conferma il Doppio.
"""
import json, math, os
import pcbnew

QUI = os.path.dirname(os.path.abspath(__file__))
FPLIB = os.path.join(QUI, "lib", "hw4.pretty")
W, H = 250.0, 50.0                     # mm
MM = pcbnew.FromMM
MARGINE_BORDO = 0.8

FISSI = {  # ref: (x, y, rotazione)
    "U10": (71.5, 21.0, 0), "U20": (178.5, 21.0, 0),
    # FFC sotto l'angolo dei pad CSI (41-46, in basso a destra del modulo); apertura verso il bordo (y = 50)
    "J60": (79.0, 45.5, 0), "J70": (186.0, 45.5, 0),
    "J61": (95.0, 46.5, 0), "J71": (202.0, 46.5, 0),
    "J1": (125.0, 46.0, 0),
    # SD: A a destra del modulo A (pad SD 67-72 in alto a destra), B a sinistra del modulo B (pista sopra il modulo)
    "J80": (94.0, 12.0, 0), "J90": (154.0, 12.0, 0),
    "J2": (112.0, 6.0, 0), "J3": (138.0, 6.0, 0),
    "J12": (50.0, 46.5, 90), "J22": (157.0, 46.5, 90), "J100": (45.5, 39.0, 90),
    "H1": (3.5, 3.5, 0), "H2": (246.5, 3.5, 0), "H3": (3.5, 46.5, 0), "H4": (246.5, 46.5, 0),
    # fori delle camere (passo 21 × 12,5 mm dei moduli Pi; DA VERIFICARE sul modulo scelto)
    "H11": (14.5, 16, 0), "H12": (35.5, 16, 0), "H13": (14.5, 28.5, 0), "H14": (35.5, 28.5, 0),
    "H15": (214.5, 16, 0), "H16": (235.5, 16, 0), "H17": (214.5, 28.5, 0), "H18": (235.5, 28.5, 0),
}
ZONE_VIETATE = [(6, 6, 44, 38), (206, 6, 244, 38)]   # sotto i moduli camera (stanno sui distanziali)
# gruppi stretti: ogni buck con induttore e condensatori in un'area sua (nodo SW corto), la catena USB → OVP →
# caricatore → power-path attorno a J1 (VBUS corta). I pezzi del gruppo si cercano posto SOLO dentro l'area.
GRUPPI = {
    "buck A": ((44.5, 1.0, 57.8, 18.0), ["U4", "L1", "C5", "C6", "C7", "R18", "R19"]),
    "buck B": ((192.6, 1.0, 205.5, 18.0), ["U5", "L2", "C8", "C9", "C13", "R20", "R21", "R30", "R31", "R32"]),
    "USB e carica": ((104.0, 26.0, 146.0, 49.2), ["U1", "R36", "U7", "C36", "C37", "C1", "D6", "R1", "R2", "R3", "R4",
                                                  "U2", "R5", "R7", "RT1", "R33", "R34", "C2", "Q3", "D8", "R35", "D5",
                                                  "R12", "R13", "U3", "Q1", "R8", "R9", "C3", "TP1", "TP7"]),
}
GRUPPO_DI = {r: area for (area, refs) in GRUPPI.values() for r in refs}

CLASSI = {  # nome: (pista, isolamento, pattern delle net)
    "Power": (0.4, 0.15, ["VSYS", "VSYS_IN", "BATP", "BAT_N", "PROT_D", "SW_A", "SW_B", "3V3_A", "3V3_B", "VBUS_C",
                          "SD_VCC_A", "SD_VCC_B"]),
    "VBUS_CSP": (0.3, 0.1, ["VBUS", "VBUS_RAW"]),      # entra fra i pad da 0,23 mm dell'AW32901
    "MIPI": (0.15, 0.15, ["CSI_*"]),
    "USB": (0.2, 0.15, ["USB_D*"]),
    "Default": (0.15, 0.12, []),
}


def rect_fp(fp, margine=0.3):
    c = fp.GetCourtyard(pcbnew.F_CrtYd)
    bb = c.BBox() if c.OutlineCount() else fp.GetBoundingBox(False, False)
    for pad in fp.Pads():
        bb.Merge(pad.GetBoundingBox())
    return (pcbnew.ToMM(bb.GetLeft()) - margine, pcbnew.ToMM(bb.GetTop()) - margine,
            pcbnew.ToMM(bb.GetRight()) + margine, pcbnew.ToMM(bb.GetBottom()) + margine)


def libero(r, occ):
    if r[0] < MARGINE_BORDO or r[1] < MARGINE_BORDO or r[2] > W - MARGINE_BORDO or r[3] > H - MARGINE_BORDO:
        return False
    return all(r[2] <= o[0] or r[0] >= o[2] or r[3] <= o[1] or r[1] >= o[3] for o in occ)


def spirale(cx, cy, w, h, occ, passo=0.5, rmax=140, area=None):
    for k in range(0, int(rmax / passo)):
        rad = k * passo
        n = max(1, int(2 * math.pi * rad / passo))
        for i in range(n):
            a = 2 * math.pi * i / n
            x, y = cx + rad * math.cos(a) - w / 2, cy + rad * math.sin(a) - h / 2
            r = (x, y, x + w, y + h)
            if area and not (r[0] >= area[0] and r[1] >= area[1] and r[2] <= area[2] and r[3] <= area[3]):
                continue
            if libero(r, occ):
                return r
    return None


def main():
    parts = json.load(open(os.path.join(QUI, "netlist_hw4.json")))
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(4)
    ds = b.GetDesignSettings()
    ds.SetBoardThickness(MM(1.6))
    # regole compatibili con JLCPCB e PCBWay 4 strati (traccia/spazio 0,1 mm = 4 mil, foro via 0,3 mm)
    ds.m_TrackMinWidth = MM(0.1)
    ds.m_MinClearance = MM(0.1)
    ds.m_ViasMinSize = MM(0.5)
    ds.m_MinThroughDrill = MM(0.25)
    ds.m_ViasMinAnnularWidth = MM(0.1)
    ds.m_HoleClearance = MM(0.25)
    ds.m_HoleToHoleMin = MM(0.25)                 # JLC: via foro-foro 0,2 mm (pagina capacità, 19/11)
    ds.m_CopperEdgeClearance = MM(0.3)
    ds.m_SolderMaskMinWidth = MM(0.0)
    b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    b.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)
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
    fps = {}
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
            if p["fp"].startswith("PinHeader") and n == "GND":
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)   # header DNP: niente raggi termici monchi
        if not p["ref"].startswith(("J", "SW", "TP", "U", "H", "BZ")):
            fp.Reference().SetLayer(pcbnew.F_Fab)          # scheda fitta: i riferimenti dei passivi sul layer Fab
        fps[p["ref"]] = (p, fp)
    occ = list(ZONE_VIETATE)
    piazzati = set()
    for ref, (p, fp) in fps.items():
        if ref in FISSI:
            x, y, r = FISSI[ref]
            fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
            if r:
                fp.SetOrientationDegrees(r)
            rr = rect_fp(fp, 0.0)
            for r2 in occ[len(ZONE_VIETATE):]:
                if not (rr[2] <= r2[0] or rr[0] >= r2[2] or rr[3] <= r2[1] or rr[1] >= r2[3]):
                    print("ATTENZIONE: pezzo fisso sovrapposto:", ref)
            # attorno ai moduli P4 un canale libero di 2,5 mm: i pad a castello devono poter uscire (fanout)
            occ.append(rect_fp(fp, 2.5 if ref in ("U10", "U20") else 0.3))
            piazzati.add(ref)
    npin = {}
    for p in parts:
        for n in set(p["pins"].values()):
            npin[n] = npin.get(n, 0) + 1

    def bersaglio(ref):
        p, fp = fps[ref]
        sx = sy = sw = 0.0
        for n in set(p["pins"].values()):
            if n == "GND" or npin[n] < 2:
                continue
            wgt = 1.0 / (npin[n] - 1)
            for r2 in piazzati:
                p2, fp2 = fps[r2]
                for pad in fp2.Pads():
                    if pad.GetNetname() == n:
                        c = pad.GetPosition()
                        sx += wgt * pcbnew.ToMM(c.x)
                        sy += wgt * pcbnew.ToMM(c.y)
                        sw += wgt
        return (sx / sw, sy / sw, sw) if sw else None

    # ordine: prima chi è più legato a quello già piazzato (greedy); i pezzi grandi prima a parità
    da_fare = [r for r in fps if r not in piazzati and not r.startswith("H")]
    while da_fare:
        migliore, bt = None, None
        candidati = [r for r in da_fare if r in GRUPPO_DI] or da_fare     # prima i gruppi
        for r in candidati:
            t = bersaglio(r)
            if t and (bt is None or t[2] * (1 + 0.02 * len(fps[r][1].Pads())) > bt[2]):
                migliore, bt = r, (t[0], t[1], t[2] * (1 + 0.02 * len(fps[r][1].Pads())))
        if migliore is None:
            migliore = candidati[0]
            a0 = GRUPPO_DI.get(migliore)
            bt = (((a0[0] + a0[2]) / 2, (a0[1] + a0[3]) / 2, 0) if a0 else (125.0, 25.0, 0))
        p, fp = fps[migliore]
        fp.SetPosition(pcbnew.VECTOR2I(0, 0))
        r0 = rect_fp(fp)
        w, h = r0[2] - r0[0], r0[3] - r0[1]
        area = GRUPPO_DI.get(migliore)
        if area and not (area[0] <= bt[0] <= area[2] and area[1] <= bt[1] <= area[3]):
            bt = (min(max(bt[0], area[0]), area[2]), min(max(bt[1], area[1]), area[3]), bt[2])
        r = spirale(bt[0], bt[1], w, h, occ, area=area)
        if r is None and area:
            print("gruppo pieno, piazzo fuori:", migliore)
            r = spirale(bt[0], bt[1], w, h, occ)
        if r is None:
            print("NON PIAZZATO:", migliore)
            fp.SetPosition(pcbnew.VECTOR2I(MM(W + 10), MM(10)))
        else:
            fp.SetPosition(pcbnew.VECTOR2I(MM(r[0] - r0[0]), MM(r[1] - r0[1])))
            occ.append(r)
        piazzati.add(migliore)
        da_fare.remove(migliore)
    for ref, (p, fp) in fps.items():
        b.Add(fp)
    # piani: In1.Cu GND pieno (riferimento di F.Cu); In2.Cu diviso: 3V3_A a sinistra (modulo A), 3V3_B a destra
    # (modulo B) → le due 3V3 non hanno bisogno di piste. F.Cu/B.Cu: riempimento GND messo da finitura.py dopo lo sbroglio.
    def zona(layer, net, x0, x1):
        z = pcbnew.ZONE(b)
        z.SetLayer(layer)
        z.SetNet(nets[net])
        ol = z.Outline()
        ol.NewOutline()
        for (x, y) in [(x0, 0.3), (x1, 0.3), (x1, H - 0.3), (x0, H - 0.3)]:
            ol.Append(MM(x), MM(y))
        z.SetMinThickness(MM(0.2))
        z.SetLocalClearance(MM(0.25))
        z.SetThermalReliefGap(MM(0.25))
        z.SetThermalReliefSpokeWidth(MM(0.3))
        b.Add(z)
    zona(pcbnew.In1_Cu, "GND", 0.3, W - 0.3)
    # fascia di 0,6 mm lungo il bordo: niente piste né vie (Freerouting la legge come keepout)
    for (x0, y0, x1, y1) in [(0, 0, W, 0.6), (0, H - 0.6, W, H), (0, 0, 0.6, H), (W - 0.6, 0, W, H)]:
        k = pcbnew.ZONE(b)
        k.SetIsRuleArea(True)
        k.SetDoNotAllowTracks(True)
        k.SetDoNotAllowVias(True)
        k.SetDoNotAllowPads(False)
        k.SetDoNotAllowFootprints(False)
        k.SetDoNotAllowZoneFills(False)
        k.SetLayerSet(pcbnew.LSET.AllCuMask())
        ok = k.Outline()
        ok.NewOutline()
        for (x, y) in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
            ok.Append(MM(x), MM(y))
        b.Add(k)
    zona(pcbnew.In2_Cu, "3V3_A", 0.3, 124.6)
    zona(pcbnew.In2_Cu, "3V3_B", 125.4, W - 0.3)
    out = os.path.join(QUI, "logger_hw4.kicad_pcb")
    b.Save(out)
    # classi di rete nel progetto (le legge KiCad, l'export DSN e il DRC)
    pro = os.path.join(QUI, "logger_hw4.kicad_pro")
    d = json.load(open(pro))
    classi = []
    patt = []
    for nome, (pista, iso, pats) in CLASSI.items():
        classi.append({"name": nome, "track_width": pista, "clearance": iso, "via_diameter": 0.6, "via_drill": 0.3,
                       "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.15, "diff_pair_gap": 0.15,
                       "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0, "pcb_color":
                       "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": len(classi)})
        for pt in pats:
            patt.append({"netclass": nome, "pattern": pt})
    d.setdefault("net_settings", {})
    d["net_settings"]["classes"] = classi
    d["net_settings"]["netclass_patterns"] = patt
    d["net_settings"]["meta"] = {"version": 4}
    # regole minime del progetto = capacità JLCPCB/PCBWay 4 strati usate nel preventivo (4/4 mil, foro 0,3 mm)
    regole = d.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {})
    regole.update({"min_track_width": 0.1, "min_clearance": 0.1, "min_via_diameter": 0.5, "min_through_hole_diameter": 0.25,
                   "min_via_annular_width": 0.1, "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25,
                   "min_copper_edge_clearance": 0.3, "min_connection": 0.0, "solder_mask_to_copper_clearance": 0.0})
    json.dump(d, open(pro, "w"), indent=2)
    print("pcb:", out, len(parts), "footprint,", len(nets), "net")


if __name__ == "__main__":
    main()
