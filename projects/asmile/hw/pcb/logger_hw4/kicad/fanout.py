#!/usr/bin/env python3
"""Fanout verso i piani (prima dello sbroglio): Freerouting non scende da solo ai piani interni.
Per ogni pad SMD su F.Cu delle net di piano (GND → In1, 3V3_A/3V3_B → In2 nella loro metà) mette una via 0,6/0,3 mm
a 0,8-2,5 mm dal pad e una pista corta da 0,3 mm, controllando la distanza (≥ 0,15 mm) da tutto il rame di altre net,
dal bordo (0,5 mm) e dalle zone vietate (sotto i moduli P4). Col Python di KiCad, dopo genera_pcb.py.
"""
import math, os
import pcbnew

QUI = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(QUI, "logger_hw4.kicad_pcb")
MM, TO = pcbnew.FromMM, pcbnew.ToMM
VIA_D, VIA_H, PISTA, ISO = 0.6, 0.3, 0.3, 0.15
W, H = 250.0, 50.0
PIANI = {"GND": None, "3V3_A": (0.3, 124.6), "3V3_B": (125.4, 249.7)}


def d_punto_rett(px, py, r):
    dx = max(r[0] - px, 0, px - r[2])
    dy = max(r[1] - py, 0, py - r[3])
    return math.hypot(dx, dy)


def d_punto_seg(px, py, a, b):
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    l2 = vx * vx + vy * vy
    t = 0 if l2 == 0 else max(0, min(1, ((px - ax) * vx + (py - ay) * vy) / l2))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def main():
    b = pcbnew.LoadBoard(PCB)
    ostacoli = []      # (tipo, geometria, net, strati) — strati: set di "F"/"B"/"*"
    pads = []
    for fp in b.GetFootprints():
        if fp.IsDNP():
            pass                                       # i pad dei DNP ci sono comunque sul rame
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            r = (TO(bb.GetLeft()), TO(bb.GetTop()), TO(bb.GetRight()), TO(bb.GetBottom()))
            th = pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            lay = "*" if th else ("F" if pad.IsOnLayer(pcbnew.F_Cu) else "B")
            ostacoli.append(("rett", r, pad.GetNetname(), lay))
            pads.append((fp, pad, r, lay))
    vietate = []
    zz = list(b.Zones())
    for fp in b.GetFootprints():
        zz += list(fp.Zones())                           # zona vietata sotto i moduli: dentro il footprint
    for z in zz:
        if z.GetIsRuleArea():
            bb = z.GetBoundingBox()
            vietate.append((TO(bb.GetLeft()), TO(bb.GetTop()), TO(bb.GetRight()), TO(bb.GetBottom())))
    n_ok = n_ko = 0
    mancati = []
    for fp, pad, r, lay in pads:
        net = pad.GetNetname()
        if net not in PIANI or lay != "F" or fp.IsDNP():
            continue
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        if PIANI[net] and not (PIANI[net][0] + 1 < cx < PIANI[net][1] - 1):
            mancati.append((fp.GetReference(), pad.GetNumber(), net, "fuori dalla metà del piano"))
            continue
        semi = max(r[2] - r[0], r[3] - r[1]) / 2
        fc = fp.GetPosition()
        ang0 = math.atan2(cy - TO(fc.y), cx - TO(fc.x))      # prima prova: via verso l'esterno del footprint
        messo = False
        for k in range(0, 15):
            rad = semi + VIA_D / 2 + ISO + 0.1 * k + 0.2
            for j in range(24):
                a = ang0 + (j // 2 + 1) * (math.pi / 12) * (1 if j % 2 else -1) if j else ang0
                vx, vy = cx + rad * math.cos(a), cy + rad * math.sin(a)
                if vx < 0.8 or vy < 0.8 or vx > W - 0.8 or vy > H - 0.8:
                    continue
                if any(v[0] - 0.4 < vx < v[2] + 0.4 and v[1] - 0.4 < vy < v[3] + 0.4 for v in vietate):
                    continue
                if PIANI[net] and not (PIANI[net][0] + 0.6 < vx < PIANI[net][1] - 0.6):
                    continue
                ok = True
                for tipo, g, n2, l2 in ostacoli:
                    if n2 == net:
                        continue
                    # via: tutti gli strati
                    dv = d_punto_rett(vx, vy, g) if tipo == "rett" else (
                        d_punto_seg(vx, vy, g[0], g[1]) - g[2] / 2 if tipo == "seg" else math.hypot(vx - g[0], vy - g[1]) - g[2] / 2)
                    if dv < VIA_D / 2 + ISO:
                        ok = False
                        break
                    # pista su F.Cu dal centro del pad alla via (campionata)
                    if l2 in ("F", "*") and tipo == "rett":
                        for s in range(1, 10):
                            px, py = cx + (vx - cx) * s / 10, cy + (vy - cy) * s / 10
                            if d_punto_rett(px, py, g) < PISTA / 2 + ISO:
                                ok = False
                                break
                        if not ok:
                            break
                if not ok:
                    continue
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(pcbnew.VECTOR2I(MM(vx), MM(vy)))
                v.SetWidth(MM(VIA_D))
                v.SetDrill(MM(VIA_H))
                v.SetNet(pad.GetNet())
                b.Add(v)
                t = pcbnew.PCB_TRACK(b)
                t.SetStart(pcbnew.VECTOR2I(MM(cx), MM(cy)))
                t.SetEnd(pcbnew.VECTOR2I(MM(vx), MM(vy)))
                t.SetWidth(MM(PISTA))
                t.SetLayer(pcbnew.F_Cu)
                t.SetNet(pad.GetNet())
                b.Add(t)
                ostacoli.append(("via", (vx, vy, VIA_D), net, "*"))
                ostacoli.append(("seg", ((cx, cy), (vx, vy), PISTA), net, "F"))
                messo = True
                break
            if messo:
                break
        if messo:
            n_ok += 1
        else:
            n_ko += 1
            mancati.append((fp.GetReference(), pad.GetNumber(), net, "nessun posto libero"))
    b.Save(PCB)
    print("fanout: %d vie messe, %d pad senza posto" % (n_ok, n_ko))
    for m in mancati:
        print("  NON FATTO:", *m)


if __name__ == "__main__":
    main()
