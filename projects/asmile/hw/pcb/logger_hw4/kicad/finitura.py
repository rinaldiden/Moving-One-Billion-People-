#!/usr/bin/env python3
"""Dopo sbroglia.py (processo separato): riempimenti GND su F.Cu e B.Cu, vie di cucitura GND a griglia dove c'è posto
(collegano le isole dei riempimenti al piano In1), riempimento delle zone, salvataggio. Col Python di KiCad.
"""
import math, os
import pcbnew

QUI = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(QUI, "logger_hw4.kicad_pcb")
MM, TO = pcbnew.FromMM, pcbnew.ToMM
W, H = 250.0, 50.0
VIA_D, VIA_H, ISO = 0.6, 0.3, 0.3          # cucitura: isolamento abbondante (0,3) dal rame di altre net


def zona_gnd(b, net, layer):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    z.SetNet(net)
    ol = z.Outline()
    ol.NewOutline()
    for (x, y) in [(0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)]:
        ol.Append(MM(x), MM(y))
    z.SetMinThickness(MM(0.2))
    z.SetLocalClearance(MM(0.25))
    z.SetThermalReliefGap(MM(0.25))
    z.SetThermalReliefSpokeWidth(MM(0.3))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)   # niente isole GND scollegate
    b.Add(z)


def d_punto_seg(px, py, a, c):
    vx, vy = c[0] - a[0], c[1] - a[1]
    l2 = vx * vx + vy * vy
    t = 0 if l2 == 0 else max(0, min(1, ((px - a[0]) * vx + (py - a[1]) * vy) / l2))
    return math.hypot(px - (a[0] + t * vx), py - (a[1] + t * vy))


def main():
    b = pcbnew.LoadBoard(PCB)
    gnd = b.FindNet("GND")
    # ostacoli: pad, piste e vie di altre net + zone vietate + fori
    rett, segs, vie = [], [], []
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            r = (TO(bb.GetLeft()), TO(bb.GetTop()), TO(bb.GetRight()), TO(bb.GetBottom()))
            if pad.GetNetname() != "GND" or pad.GetAttribute() in (pcbnew.PAD_ATTRIB_NPTH, pcbnew.PAD_ATTRIB_PTH):
                rett.append(r)
    tr = b.Tracks()
    for i in range(tr.size()):
        t = tr[i]
        if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND":
            p = t.GetPosition()
            vie.append((TO(p.x), TO(p.y), 0.6 + 0.4))    # foro-foro: anche le vie GND tengono distanza
            continue
        if t.GetNetname() == "GND":
            continue
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            vie.append((TO(p.x), TO(p.y), TO(t.GetWidth())))
        else:
            s, e = t.GetStart(), t.GetEnd()
            segs.append(((TO(s.x), TO(s.y)), (TO(e.x), TO(e.y)), TO(t.GetWidth())))
    zone_vietate = list(b.Zones())
    for fp in b.GetFootprints():
        zone_vietate += list(fp.Zones())                 # la zona vietata sotto i moduli sta nel footprint
    for z in zone_vietate:
        if z.GetIsRuleArea():
            bb = z.GetBoundingBox()
            rett.append((TO(bb.GetLeft()), TO(bb.GetTop()), TO(bb.GetRight()), TO(bb.GetBottom())))
    # Freerouting a volte strozza a 0,075 mm l'uscita da un pad: porto a 0,1 mm (minimo del fornitore) quei segmenti
    n_str = 0
    for i in range(tr.size()):
        t = tr[i]
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < MM(0.1):
            t.SetWidth(MM(0.1))
            n_str += 1
    print("segmenti strozzati portati a 0,1 mm:", n_str)
    zona_gnd(b, gnd, pcbnew.F_Cu)
    zona_gnd(b, gnd, pcbnew.B_Cu)
    n = 0
    passo = 3.0
    y = 1.5
    while y < H - 1.0:
        x = 1.5
        while x < W - 1.0:
            ok = all(math.hypot(max(r[0] - x, 0, x - r[2]), max(r[1] - y, 0, y - r[3])) >= VIA_D / 2 + ISO for r in rett)
            ok = ok and all(d_punto_seg(x, y, s[0], s[1]) - s[2] / 2 >= VIA_D / 2 + ISO for s in segs)
            ok = ok and all(math.hypot(x - v[0], y - v[1]) - v[2] / 2 >= VIA_D / 2 + ISO for v in vie)
            if ok:
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                v.SetWidth(MM(VIA_D))
                v.SetDrill(MM(VIA_H))
                v.SetNet(gnd)
                b.Add(v)
                n += 1
            x += passo
        y += passo
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print("finitura: riempimenti GND F/B, %d vie di cucitura" % n)


if __name__ == "__main__":
    main()
