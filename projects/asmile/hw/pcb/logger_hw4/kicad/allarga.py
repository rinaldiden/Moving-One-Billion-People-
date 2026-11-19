#!/usr/bin/env python3
"""Allarga le piste di potenza dopo lo sbroglio (Freerouting le tiene alla larghezza minima della classe):
VBUS/VBUS_RAW/VBUS_C → 0,5 mm (fino a ~2,2 A: carica 1 A + scheda via D5), VSYS/VSYS_IN/BATP/BAT_N/PROT_D → 0,6 mm.
Non tocca i segmenti entro 1,2 mm dal CSP AW32901 (U7, pad a passo 0,4). Poi DRC: i segmenti che creano violazioni
tornano alla larghezza di prima (più giri). Uso (Python di KiCad): python3 allarga.py /percorso/kicad-cli
"""
import json, math, os, subprocess, sys, tempfile
import pcbnew

QUI = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(QUI, "logger_hw4.kicad_pcb")
MM, TO = pcbnew.FromMM, pcbnew.ToMM
LARGHE = {"VBUS": 0.5, "VBUS_RAW": 0.5, "VBUS_C": 0.5, "VSYS": 0.6, "VSYS_IN": 0.6, "BATP": 0.6, "BAT_N": 0.6,
          "PROT_D": 0.6}


def chiave(t):
    s, e = t.GetStart(), t.GetEnd()
    return (t.GetNetname(), s.x, s.y, e.x, e.y, t.GetLayer())


def drc(cli):
    f = tempfile.mktemp(suffix=".json")
    subprocess.run([cli, "pcb", "drc", "--severity-error", "--format", "json", "-o", f, PCB], capture_output=True)
    d = json.load(open(f))
    os.remove(f)
    return d


def main():
    cli = sys.argv[1]
    b = pcbnew.LoadBoard(PCB)
    u7 = [fp for fp in b.GetFootprints() if fp.GetReference() == "U7"][0].GetPosition()
    tr = b.Tracks()
    prima = {}
    for i in range(tr.size()):
        t = tr[i]
        n = t.GetNetname()
        if t.GetClass() != "PCB_TRACK" or n not in LARGHE:
            continue
        vicino = any(math.hypot(TO(p.x - u7.x), TO(p.y - u7.y)) < 1.2 for p in (t.GetStart(), t.GetEnd()))
        if vicino or t.GetWidth() >= MM(LARGHE[n]):
            continue
        prima[chiave(t)] = t.GetWidth()
        t.SetWidth(MM(LARGHE[n]))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print("allargati %d segmenti" % len(prima))
    for giro in range(6):
        d = drc(cli)
        cattivi = []
        for v in d["violations"]:
            for it in v["items"]:
                if it["description"].startswith("Track [") and any(it["description"].startswith("Track [%s]" % n) for n in LARGHE):
                    cattivi.append((it["pos"]["x"], it["pos"]["y"], it["description"]))
        if not cattivi and not d["unconnected_items"]:
            print("DRC pulito dopo %d giri" % giro)
            break
        b = pcbnew.LoadBoard(PCB)
        tr = b.Tracks()
        rimessi = 0
        for i in range(tr.size()):
            t = tr[i]
            k = chiave(t)
            if k not in prima:
                continue
            s, e = t.GetStart(), t.GetEnd()
            for x, y, desc in cattivi:
                # il punto del DRC sta sul segmento?
                ax, ay, cx, cy = TO(s.x), TO(s.y), TO(e.x), TO(e.y)
                vx, vy = cx - ax, cy - ay
                l2 = vx * vx + vy * vy
                q = 0 if l2 == 0 else max(0, min(1, ((x - ax) * vx + (y - ay) * vy) / l2))
                if math.hypot(x - ax - q * vx, y - ay - q * vy) < TO(t.GetWidth()) / 2 + 0.05:
                    t.SetWidth(prima[k])
                    rimessi += 1
                    break
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        b.Save(PCB)
        print("giro %d: %d violazioni, %d segmenti rimessi stretti" % (giro + 1, len(cattivi), rimessi))
        if rimessi == 0:
            print("ATTENZIONE: violazioni non dovute alle piste allargate:", len(d["violations"]))
            break


if __name__ == "__main__":
    main()
