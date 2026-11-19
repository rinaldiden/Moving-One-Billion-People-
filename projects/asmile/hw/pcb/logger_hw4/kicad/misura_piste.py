#!/usr/bin/env python3
"""Misura dello sbroglio per le net veloci (MIPI, USB, SDIO): lunghezza, vie, strati, differenza P/N. Python di KiCad."""
import math, os, re, collections
import pcbnew
QUI = os.path.dirname(os.path.abspath(__file__))
b = pcbnew.LoadBoard(os.path.join(QUI, "logger_hw4.kicad_pcb"))
TO = pcbnew.ToMM
LW = collections.defaultdict(lambda: collections.defaultdict(float))
L = collections.defaultdict(float); V = collections.Counter(); S = collections.defaultdict(set); Wd = collections.defaultdict(set)
tr = b.Tracks()
for i in range(tr.size()):
    t = tr[i]; n = t.GetNetname()
    if t.GetClass() == "PCB_VIA":
        V[n] += 1
    else:
        s, e = t.GetStart(), t.GetEnd()
        LW[n][round(TO(t.GetWidth()), 2)] += math.hypot(TO(s.x - e.x), TO(s.y - e.y))
        L[n] += math.hypot(TO(s.x - e.x), TO(s.y - e.y)); S[n].add(t.GetLayerName()); Wd[n].add(round(TO(t.GetWidth()), 3))
print("| net | lunghezza mm | vie | strati | larghezze mm |")
print("|---|---|---|---|---|")
sel = sorted(n for n in L if re.match(r"(CSI_|USB_D|SD_CLK|SD_CMD|SD_D0)", n))
for n in sel:
    print("| %s | %.1f | %d | %s | %s |" % (n, L[n], V[n], "+".join(sorted(S[n])), ",".join(map(str, sorted(Wd[n])))))
print()
for s in ("A", "B"):
    for lane in ("D0", "D1", "CK"):
        p, nn = "CSI_%sP_%s" % (lane, s), "CSI_%sN_%s" % (lane, s)
        print("coppia %s lane %s: P %.1f mm, N %.1f mm, differenza %.1f mm" % (s, lane, L[p], L[nn], abs(L[p] - L[nn])))
for n in ("VBUS", "VBUS_RAW", "VSYS", "VSYS_IN", "BATP", "SW_A", "SW_B"):
    print("potenza %s: %.1f mm, vie %d; mm per larghezza: %s" % (n, L[n], V[n],
          ", ".join("%.2f→%.1f" % (w, l) for w, l in sorted(LW[n].items()))))
